# Market Import (导入行情) - Design Spec

## Context
当前系统的图表页数据链路为：
- 前端调用 `GET /api/v1/chart/bundle`；
- 后端 `app/services/chart_data_service.py` 内部通过 `market_data_provider.get_klines(..., source_mode=cache|live)` 读取数据库中的 K 线（缓存/回源策略）。

当数据库中缺少指定 `exchange/symbol/market_type/timeframe` 的 K 线时，图表页会提示“请先导入或采集行情”。

本需求希望实现“导入行情功能”，以便将历史行情写入数据库，从而让图表 bundle 可用，并为后续因子/分析提供更完整的数据。

## Goals
1. 提供一个后端“导入行情任务”能力，支持按时间区间回放并写入数据库。
2. 前端新增一个“导入行情”页面，用户可配置交易参数与区间，并查看导入进度与结果。
3. 导入完成后，无需额外改造图表页：刷新 `GET /api/v1/chart/bundle` 即可渲染。
4. 导入类型尽量覆盖：`kline / trades / orderbook / funding_rate / open_interest`。

## Non-Goals
1. 不实现分布式队列（如 Celery/RQ）；仅在进程内使用后台协程/任务运行。
2. 不承诺交易所对“历史订单簿快照”的完整回放能力（详见 Limitation）。
3. 不为“导入类型”提供文件上传导入（本需求选择的是“后端拉取导入行情”）。

## Assumptions & Limitations
1. Binance K 线历史：`/api/v3/klines`（spot）与 `/fapi/v1/klines`（usds-perp）均支持 `startTime/endTime`。
2. Binance 历史逐笔成交：
   - 现货：`/api/v3/aggTrades` 支持 `startTime/endTime`；
   - 永续（USDS-margined）：`/fapi/v1/aggTrades` 支持 `startTime/endTime`，并要求 `startTime/endTime` 间隔小于约 1 小时（实现需按该约束 chunk）。
3. Binance 历史资金费率：
   - 使用 `/fapi/v1/fundingRate`，支持 `startTime/endTime`。
4. Binance 历史持仓量（Open Interest）：
   - 使用 `/futures/data/openInterestHist`；
   - 该接口通常仅提供“近 30 天”数据（实现需对回放区间做裁剪并在结果里标注）。
5. Binance 历史订单簿（Orderbook depth snapshots）：
   - 标准 REST `GET /api/v3/depth` 仅返回当前订单簿快照，不支持 `startTime/endTime`；
   - 因此“严格历史回放订单簿快照”无法仅靠现有 REST 实现。
   - 本设计选择“可用但不完整”的策略：回放任务对 `orderbook` 类型返回 `partial/unsupported`，并将导入过程中的缺口写入 `result_json` 便于前端展示。

> 结论：本 spec 中“严格历史回放”以 K 线/成交/资金费率/持仓量为主；订单簿历史在当前能力范围内实现为受限/缺口可报告。

## API & Data Model Design

### 1) 新增数据模型：MarketImportTask
新增 ORM 表（建议：`market_import_tasks`）：
- `id`：主键
- `name`：任务名称（可选）
- `created_by`：创建者 user.id
- `exchange`：交易所（本期 MVP 固定 `binance`）
- `market_type`：`spot` / `futures`（实现按现有字段映射）
- `symbol`：如 `BTCUSDT`
- `timeframe`：K 线周期（kline/trades/funding/oi 的粒度策略依赖此字段）
- `start_date/end_date`：导入回放区间
- `import_types`：JSON 数组（例如 `["kline","trades","orderbook","funding_rate","open_interest"]`）
- `status`：`pending | running | completed | failed`
- `progress`：0~1 浮点或百分比（建议 0~1）
- `result_json`：最终汇总（各类型写入条数、缺口、裁剪区间、错误列表等）
- `last_error`：失败原因（失败时）
- `created_at/updated_at/finished_at`

### 2) 后端路由（v1）
新增在 `backend/app/api/v1/market.py`（或拆分新 router，但建议复用 market 域）：

1. `POST /api/v1/market/import`
   - Request body：
     - `symbol: str`
     - `exchange: str = "binance"`
     - `market_type: str = "spot"`
     - `timeframe: str = "1h"`
     - `start_date: datetime`
     - `end_date: datetime`
     - `import_types: list[str]`
     - （可选）`orderbook_sample_limit`：最多抽样次数/深度档位（用于部分支持策略）
     - MVP 注意：当前实现不支持历史订单簿回放，因此该参数在 MVP 中会被忽略（仍返回 unsupported_historical 结果）。
   - Response：
     - `{ data: { task_id: int } }`
   - 行为：
     - 写入 `MarketImportTask` 初始记录；
     - 异步启动后台回放执行器；
     - 返回 task_id 供前端轮询。

2. `GET /api/v1/market/import/{task_id}`
   - Response：
     - `{ data: { status, progress, result_json, last_error } }`

### 3) 后台执行器：MarketImportService
新增文件 `backend/app/services/market_import_service.py`（或类似命名）：
- `create_and_start_import(...) -> int`
- `run_import_task(task_id: int) -> None`

执行流程：
1. 从 DB 加载任务配置与 import_types；
2. 更新任务状态为 `running`；
3. 依次执行各类型导入（建议顺序：kline -> trades -> funding_rate -> open_interest -> orderbook（partial））；
4. 每执行一个 chunk 更新 `progress` 与该类型的 `imported_count`；
5. 完成后写入 `result_json` 并标记 `completed`；
6. 任何异常写入 `last_error` 并标记 `failed`。

### 4) 后台执行模型（MVP 明确化）
1. 启动方式：`POST /api/v1/market/import` 接口返回 `task_id` 后，在同一 FastAPI 进程内使用 `asyncio.create_task(run_import_task(task_id))` 启动后台协程。
2. 并发控制：在 `MarketImportService` 内部使用 `asyncio.Semaphore` 控制进程内最大同时导入任务数（建议默认值：2）。
3. 进程重启语义：
   - 任务状态会持久化到数据库；
   - MVP 不保证“进程重启后自动继续运行 running/pending 任务”；
   - 如果进程重启导致任务未完成，前端应通过“重新导入/新建任务”重新发起。
4. 取消语义：MVP 不提供显式取消接口；实现层面预留“轮询任务状态以便未来扩展取消”的能力。

## Import Algorithm Design (关键实现策略)

### 1) Kline 回放
- 使用现有 `market_data_provider.get_klines(..., source_mode="live", persist_to_db=True)`：
  - 它会调用 datafeed adapter -> binance adapter -> rest_client，并将结果持久化到 `MarketKline`。
- 由于 Binance K 线接口支持 `startTime/endTime`，可以直接按区间分页 chunk：
  - `chunk_size` 由 `limit` 与区间长度估算；
  - 同时为避免边界不足，预留 1~2 个周期的冗余（与 backtest 页类似思路）。

### 2) Trades 回放（历史严格）
现状：当前 `market_data_provider.get_trades(source_mode="live")` 走的是 WS 的“最近 N 条”，无法历史回放。

因此导入执行器必须新增一条“REST 历史 trades”路径：
1. 扩展 Binance REST client：
   - spot：`/api/v3/aggTrades`，支持 `startTime/endTime`；
   - futures：`/fapi/v1/aggTrades`，支持 `startTime/endTime` 且间隔约束需要 chunk（小于 1 小时）。
2. 扩展 BinanceAdapter：
   - 提供 `get_agg_trades_history(symbol, start_time_ms, end_time_ms, limit, use_proxy)`
3. 由 `MarketImportService` 调用并将解析结果写入 `market_service.save_trade`。

chunk 规则（futures）：
- 当 `start_date/end_date` 给定较大区间时，将其切片成不超过 1 小时的窗口；
- 每个窗口内分页拉取（通过返回的 id 或时间推进策略防止重复/遗漏）。

#### Trades 字段映射与去重口径
- 落库 trade_id：使用 aggTrades 的聚合成交 id（实现时以解析到的字段为准，统一转为 `str(a)` 或等价字段）。
- side 映射：遵循现有 WS 解析口径
  - `m=true` 表示“买方是 maker”，则 taker 为卖方；
  - 因此统一映射：`side = "sell" if m==true else "buy"`。
- 幂等/去重：为避免重复 chunk/重试造成重复行，需在数据库层为 `MarketTrade` 增加唯一约束 `(exchange, symbol, market_type, trade_id)`，并在落库时使用 `ON CONFLICT DO NOTHING`（或 DO UPDATE）。

### 3) Funding Rate 回放（历史严格）
1. 扩展 Binance REST client：使用 `/fapi/v1/fundingRate`，支持 `startTime/endTime/limit`。
2. 扩展 BinanceAdapter：增加 `get_funding_rate_history(...)`。
3. `MarketImportService` 以较保守的 chunk（例如按 `limit` 与窗口推进）拉取并持久化到 `MarketFunding`。

注意：
- funding 与市场结算周期相关，最终落库点通常少于 trades/kline。

### 4) Open Interest 回放（历史严格但需裁剪）
1. 扩展 Binance REST client：使用 `/futures/data/openInterestHist`，需要 `period`、`contractType` 等参数。
2. 由于接口通常仅提供“最近 30 天”，当 `start_date` 更早时：
   - 裁剪规则（UTC 闭区间）：
     - `effective_start_date = max(request.start_date, now_utc - 30 days)`
     - `effective_end_date = request.end_date`
   - 若 `effective_start_date > effective_end_date`：
     - 该类型导入不执行（imported_count=0），并标记为 `partial`（reason=out_of_available_history_range）。
   - 在 `result_json` 里写明 `effective_*` 与裁剪原因。
3. 将结果写入 `MarketOpenInterest`。

### 5) Orderbook 导入（partial/unsupported）
为了尽量保留 UI 的一致性与类型选择体验：
- 当导入类型包含 `orderbook` 时：
  - 对“历史区间订单簿快照”标记为 `unsupported_historical`；
  - MVP 中不执行历史深度抽样，因此：
    - `orderbook_sample_limit` 参数在该类型上当前被忽略；
    - `result_json` 写入：`orderbook_imported_samples=0`、reason="Binance depth endpoint doesn't support startTime/endTime"。
- 后续迭代可以在不改变当前 spec 的前提下，接入外部历史深度数据源（如 Binance public data repo/付费订阅）——本需求不在 MVP 内实现。

### 6) 时间语义约定（MVP）
1. 时区：`start_date/end_date` 按 UTC 语义处理（API 请求传入的 datetime 以 UTC 存储与比较）。
2. 区间包含关系：对 Kline/Trades/Funding/OI 视为闭区间（inclusive）。
3. chunk 无重叠策略：以毫秒为边界
   - chunk i 的 end（inclusive）后一个 chunk 的 start = `prev_end + 1ms`，确保不重叠也不丢失边界点。

### 7) `result_json` Schema（前后端对齐）
`MarketImportTask.result_json` 建议保持稳定的外层层级结构，至少包含：
```json
{
  "summary": {
    "requested_start_date": "ISO8601",
    "requested_end_date": "ISO8601",
    "effective_start_date": "ISO8601",
    "effective_end_date": "ISO8601",
    "completed_types": ["kline", "trades", "funding_rate", "open_interest"],
    "partial_types": ["orderbook"],
    "failed_types": [],
    "imported_counts": {
      "klines": 0,
      "trades": 0,
      "funding_rate": 0,
      "open_interest": 0,
      "orderbook_imported_samples": 0
    }
  },
  "type_results": {
    "kline": { "status": "completed", "imported_count": 0 },
    "trades": { "status": "completed", "imported_count": 0, "details": [] },
    "funding_rate": { "status": "completed", "imported_count": 0 },
    "open_interest": { "status": "partial", "imported_count": 0, "effective_range": { "start": "...", "end": "..." }, "reason": "..." },
    "orderbook": { "status": "unsupported_historical", "imported_count": 0, "reason": "..." }
  },
  "errors": [
    { "type": "trades", "chunk_start": "...", "chunk_end": "...", "message": "..." }
  ]
}
```

## Frontend Design (交互要点)
新页面 `frontend/src/pages/MarketImport/index.tsx`：
- 表单提交后调用 `POST /api/v1/market/import` 得到 `task_id`
- 轮询 `GET /api/v1/market/import/{task_id}` 更新：
  - `status`
  - `progress`
  - `result_json.summary`
  - 错误时显示 `last_error`
- 导入完成（completed）后：
  - 给出“跳转图表分析”按钮（`navigate('/chart')`），用户可刷新看到数据。

路由：
- 新增菜单项 + 路由到 `/market-import`

## Error Handling & Resilience
1. Binance HTTP 429、5xx：
   - 复用现有 `BinanceRestClient._request` 的重试与指数退避逻辑。
2. 大区间：
   - 采用 chunk 分片，降低单次请求失败成本；
   - 失败时建议记录当前 chunk 边界到 `result_json.errors`，便于续跑（续跑能力是否实现将在后续 spec）。
3. 并发：
   - 同一用户可重复创建任务；任务之间互不依赖。

## Testing Plan
1. 单元测试（建议）：
   - 时间 chunk 计算正确性（尤其 futures trades 的 1 小时窗口约束）；
   - 裁剪 openInterest 区间与结果标记一致性。
2. 集成测试（建议）：
   - 使用 mock 的 Binance REST client 验证 import 写库逻辑；
   - 验证导入完成后，`GET /api/v1/chart/bundle` 能返回 `klines_loaded > 0`。
3. 手工验收（MVP）：
   - 在页面输入一个较小的区间（例如 1~2 天），检查：
     - 任务完成；
     - chart/bundle 渲染；
     - trades/funding/oi 的导入条数与 result_json 一致。

## Deployment / Operations
1. 导入任务会对数据库产生写入压力；
2. 建议在前端限制最大导入区间（例如最多 N 天），或者通过后端做硬限制防止误操作；
3. 记录导入任务结果便于追溯。

## Open Questions
1. 是否实现“续跑/断点续导入”能力：当任务失败时能否从 `result_json.errors` 所在 chunk 边界继续，而不是重新全量导入。

## Traceability
本设计对应当前需求：
- “实现导入行情功能，以获取数据提供给图表功能使用”
- “前后端都需要实现更新开发日志和使用文档”

其中：
- 图表接口无需大改造；
- 通过导入任务把数据写入 `market_klines` 等表，实现链路闭环。

