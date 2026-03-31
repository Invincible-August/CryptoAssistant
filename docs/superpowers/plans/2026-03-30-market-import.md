# Market Import (导入行情) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在后端实现“按时间区间回放并写库”的导入行情任务，并在前端新增“导入行情”页面展示进度与结果，使图表页可直接消费导入后的 K 线数据。

**Architecture:** 后端新增 `MarketImportTask` 任务表与 `POST/GET /api/v1/market/import` 接口，接口创建任务后在同进程内启动后台协程执行导入。导入过程按类型分 chunk 拉取 Binance 历史数据并写入数据库，持续更新任务 `progress/result_json`。前端新增 `/market-import` 页面发起导入并轮询任务状态。

**Tech Stack:** FastAPI + SQLAlchemy Async + PostgreSQL + httpx + React 18 + TypeScript + Ant Design 5

---

## File Structure (新增/修改清单)

**Backend**
- Create: `backend/app/models/market_import_task.py`
- Modify: `backend/app/models/__init__.py`（导出模型）
- Create: `backend/app/schemas/market_import.py`（请求/响应 schema，包含 result_json 类型）
- Create: `backend/migrations/versions/<new>_add_market_import_tasks.py`（新增任务表）
- Modify: `backend/app/api/v1/market.py`（新增 import endpoints）
- Create: `backend/app/services/market_import_service.py`（任务创建、后台执行、chunk 拉取与落库）
- Modify: `backend/app/datafeeds/exchanges/binance/rest_client.py`（新增历史接口：aggTrades、fundingRate、openInterestHist）
- Modify: `backend/app/datafeeds/exchanges/binance/adapter.py`（新增 wrapper：历史 trades/funding/oi）
- Modify: `backend/app/services/market_service.py`（为 trades/funding/oi 落库提供 upsert/ignore 策略，必要时新增方法）
- Create: `backend/migrations/versions/<new>_add_market_data_uniques.py`（为 trades/funding/oi 增加唯一约束/索引）
- Create: `backend/tests/test_market_import_service.py`（pytest-asyncio 单测，覆盖 chunk/裁剪/result_json）
- (Optional) Create: `backend/tests/test_market_import_api.py`（httpx + FastAPI TestClient/AsyncClient）

**Frontend**
- Create: `frontend/src/pages/MarketImport/index.tsx`
- Modify: `frontend/src/router/index.tsx`（新增 route `/market-import`）
- Modify: `frontend/src/layouts/BasicLayout.tsx`（新增菜单项）
- Create: `frontend/src/services/marketImport.ts`（封装 `POST/GET /market/import`）

**Docs**
- Modify: `README.md`（新增“导入行情”使用说明与 API 摘要）
- Modify: `CHANGELOG.md`（新增条目：导入行情功能 + 新页面 + 新 API）

---

### Task 1: Backend - 数据模型与 schema（MarketImportTask）

**Files:**
- Create: `backend/app/models/market_import_task.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/market_import.py`
- Create: `backend/migrations/versions/<new>_add_market_import_tasks.py`

- [ ] **Step 1: 写失败的 schema 单测（result_json 结构最小验证）**

```python
import pytest
from pydantic import ValidationError

from app.schemas.market_import import MarketImportTaskResponse


def test_market_import_task_response_accepts_result_json_schema():
    payload = {
        "id": 1,
        "status": "running",
        "progress": 0.5,
        "result_json": {
            "summary": {
                "requested_start_date": "2026-03-01T00:00:00Z",
                "requested_end_date": "2026-03-02T00:00:00Z",
                "effective_start_date": "2026-03-01T00:00:00Z",
                "effective_end_date": "2026-03-02T00:00:00Z",
                "completed_types": [],
                "partial_types": [],
                "failed_types": [],
                "imported_counts": {
                    "klines": 0,
                    "trades": 0,
                    "funding_rate": 0,
                    "open_interest": 0,
                    "orderbook_imported_samples": 0,
                },
            },
            "type_results": {},
            "errors": [],
        },
        "last_error": None,
        "created_at": "2026-03-30T00:00:00Z",
    }
    obj = MarketImportTaskResponse.model_validate(payload)
    assert obj.result_json["summary"]["imported_counts"]["klines"] == 0


def test_market_import_task_response_rejects_invalid_status():
    with pytest.raises(ValidationError):
        MarketImportTaskResponse.model_validate(
            {
                "id": 1,
                "status": "unknown",
                "progress": 0,
                "result_json": {"summary": {}, "type_results": {}, "errors": []},
                "last_error": None,
                "created_at": "2026-03-30T00:00:00Z",
            }
        )
```

- [ ] **Step 2: 运行测试，确认失败（缺少 schema/字段）**

Run: `pytest backend/tests/test_market_import_service.py -v`
Expected: FAIL（ImportError 或 ValidationError 相关）

- [ ] **Step 3: 实现 ORM 模型 + pydantic schema（最小满足测试）**

要点：
- ORM `MarketImportTask`：字段覆盖 spec（id, exchange, market_type, symbol, timeframe, start_date, end_date, import_types, status, progress, result_json, last_error, created_by, timestamps）
- schema：
  - `MarketImportCreateRequest`
  - `MarketImportCreateResponse`（返回 task_id）
  - `MarketImportTaskResponse`（用于 GET）

- [ ] **Step 3.1: 生成 Alembic migration（创建 market_import_tasks 表）**

Run: `cd backend && alembic revision -m "add market import tasks"`
Then edit the generated file to create table + indexes.

- [ ] **Step 3.2: 运行迁移（本地开发）**

Run: `cd backend && alembic upgrade head`
Expected: 成功创建表（无报错）
- [ ] **Step 4: 再次运行测试，确认通过**

Run: `pytest backend/tests/test_market_import_service.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/models/market_import_task.py backend/app/models/__init__.py backend/app/schemas/market_import.py backend/tests/test_market_import_service.py
git add backend/migrations/versions/*add_market_import_tasks*.py
git commit -m "feat: add market import task schema and model"
```

---

### Task 2: Backend - Binance REST 历史接口扩展（trades/funding/oi）

**Files:**
- Modify: `backend/app/datafeeds/exchanges/binance/rest_client.py`
- Modify: `backend/app/datafeeds/exchanges/binance/adapter.py`
- Modify: `backend/app/datafeeds/exchanges/binance/parser.py`（如需新增 REST aggTrades 解析器）

- [ ] **Step 1: 写失败的单测（验证 REST client 组装参数与路径）**

思路：对 `BinanceRestClient._request` 做 monkeypatch，断言：
- spot aggTrades 调用 `/api/v3/aggTrades` 且包含 `startTime/endTime/limit`
- futures aggTrades 调用 `/fapi/v1/aggTrades`
- fundingRate 调用 `/fapi/v1/fundingRate`
- openInterestHist 调用 `/futures/data/openInterestHist`

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest backend/tests/test_market_import_service.py -v`
Expected: FAIL（缺少方法/路径）

- [ ] **Step 3: 实现 REST client 方法**

新增方法建议：
- `get_spot_agg_trades(symbol: str, start_time: int | None, end_time: int | None, limit: int = 1000, use_proxy: bool = False)`
- `get_futures_agg_trades(...)`
- `get_futures_funding_rate_history(symbol: str, start_time: int | None, end_time: int | None, limit: int = 1000, use_proxy: bool = False)`（命名与 spec 对齐）
- `get_open_interest_hist(symbol: str, period: str, start_time: int | None, end_time: int | None, limit: int = 500, use_proxy: bool = False)`

并在 `BinanceAdapter` 增加对应 wrapper，返回统一 dict 列表（后续 service 负责落库）。

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest backend/tests/test_market_import_service.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/datafeeds/exchanges/binance/rest_client.py backend/app/datafeeds/exchanges/binance/adapter.py backend/app/datafeeds/exchanges/binance/parser.py backend/tests/test_market_import_service.py
git commit -m "feat: add binance historical endpoints for import"
```

---

### Task 3: Backend - 落库幂等与写入统计（market_service）

**Files:**
- Modify: `backend/app/services/market_service.py`
- Modify: `backend/app/models/market_trade.py`
- Modify: `backend/app/models/market_funding.py`
- Modify: `backend/app/models/market_open_interest.py`
- Create: `backend/migrations/versions/<new>_add_market_data_uniques.py`

- [ ] **Step 1: 写失败的单测（重复写入不重复行/不抛错）**

目标：同一 `(exchange,symbol,market_type,trade_id)` 重复插入不会导致任务失败；funding/oi 同理。

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest backend/tests/test_market_import_service.py -v`
Expected: FAIL（唯一约束缺失或 IntegrityError）

- [ ] **Step 3: 增加唯一约束/索引并实现 upsert/ignore**

实现策略（MVP）：
- `MarketTrade`：唯一约束 `(exchange, symbol, market_type, trade_id)`；插入冲突 -> ignore
- `MarketFunding`：唯一约束 `(exchange, symbol, funding_time)`；冲突 -> update/ignore
- `MarketOpenInterest`：唯一约束 `(exchange, symbol, market_type, event_time)`；冲突 -> update/ignore

同时在 `market_service` 新增/改造保存方法使用 SQLAlchemy `insert(...).on_conflict_do_nothing()`（PostgreSQL）。

- [ ] **Step 3.1: 生成 Alembic migration（添加唯一约束/索引）**

Run: `cd backend && alembic revision -m "add market data unique constraints"`
Then edit migration:
- add UniqueConstraint / Index for MarketTrade/MarketFunding/MarketOpenInterest

- [ ] **Step 3.2: 运行迁移并验证**

Run: `cd backend && alembic upgrade head`
Expected: 成功（如遇到历史重复数据，需要先清理/去重后再加约束）

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest backend/tests/test_market_import_service.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/models/market_trade.py backend/app/models/market_funding.py backend/app/models/market_open_interest.py backend/app/services/market_service.py backend/tests/test_market_import_service.py
git add backend/migrations/versions/*add_market_data_unique*.py
git commit -m "feat: make market import writes idempotent"
```

---

### Task 4: Backend - MarketImportService（任务执行、chunk、result_json）

**Files:**
- Create: `backend/app/services/market_import_service.py`
- Modify: `backend/app/api/v1/market.py`
- (Optional) Modify: `backend/app/core/database.py`（如需暴露 session factory；优先不要动）

- [ ] **Step 1: 写失败的服务单测（chunk/裁剪/result_json/progress）**

至少覆盖：
- futures aggTrades chunk（<=1h）拆分正确（下一窗口 start = prev_end + 1ms）
- open interest 裁剪：`effective_start_date` 逻辑与 out-of-range partial
- orderbook 标记 unsupported
- progress 在多个阶段递增（不要求精确，但要单调不降且最终为 1.0）

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest backend/tests/test_market_import_service.py -v`
Expected: FAIL（未实现 service）

- [ ] **Step 3: 实现 MarketImportService（最小让测试通过）**

要点：
- 使用 `asyncio.create_task` 启动；内部 `asyncio.Semaphore` 控制并发
- 执行时创建独立 DB session：使用 `async_sessionmaker`（需要从 `app.core.database` 导入或增加一个 getter）
- 每个类型导入完成更新 `result_json.type_results[type]` 和 `summary.imported_counts`
- 异常捕获写入 `errors[]` + `last_error` 并置 failed

- [ ] **Step 4: 新增 API endpoints（POST/GET）**

`POST /api/v1/market/import`：
- 校验 `source exchange == binance`（MVP）
- 写入任务记录 status=pending
- 从 `get_current_user` 获取当前用户，并写入 `created_by=current_user.id`
- 启动后台任务并返回 task_id

`GET /api/v1/market/import/{task_id}`：
- 返回任务状态

- [ ] **Step 5: 运行测试，确认通过**

Run: `pytest backend/tests/test_market_import_service.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/market_import_service.py backend/app/api/v1/market.py backend/app/schemas/market_import.py backend/tests/test_market_import_service.py
git commit -m "feat: add market import task runner and API"
```

---

### Task 5: Frontend - 新增 MarketImport 页面与 services

**Files:**
- Create: `frontend/src/pages/MarketImport/index.tsx`
- Create: `frontend/src/services/marketImport.ts`
- Modify: `frontend/src/router/index.tsx`
- Modify: `frontend/src/layouts/BasicLayout.tsx`

- [ ] **Step 1: 写最小 UI（表单 + 提交按钮）**
  - symbol/timeframe/start/end/import_types

- [ ] **Step 2: 接入 `marketImportApi.create()`**
  - 成功后保存 `taskId` 并开始轮询

- [ ] **Step 3: 实现轮询 `marketImportApi.getTask(taskId)`**
  - running: 展示进度条 + imported_counts
  - completed: 展示汇总 + “跳转图表分析”
  - failed: 展示 last_error

- [ ] **Step 4: 加入路由与菜单**
  - route: `/market-import`
  - menu label: `导入行情`

- [ ] **Step 5: 手工验证（本地）**
  - 登录后进入导入页能提交请求并看到状态更新（可用 mock 后端或真实后端）

- [ ] **Step 6: 提交**

```bash
git add frontend/src/pages/MarketImport/index.tsx frontend/src/services/marketImport.ts frontend/src/router/index.tsx frontend/src/layouts/BasicLayout.tsx
git commit -m "feat: add market import page"
```

---

### Task 6: Docs - README / CHANGELOG 同步

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: README 增加“导入行情”使用说明**
  - 页面入口 `/market-import`
  - API：`POST /api/v1/market/import`、`GET /api/v1/market/import/{task_id}`
  - 说明限制：orderbook 历史不支持、OI 可能裁剪到近 30 天

- [ ] **Step 2: CHANGELOG 增加 Unreleased 条目（功能级）**
  - 新增：导入行情任务 + 新页面
  - 变更：binance rest client 新增历史端点（如有）

- [ ] **Step 3: 提交**

```bash
git add README.md CHANGELOG.md
git commit -m "docs: document market import feature"
```

---

## Plan Review Evidence Commands (执行前验证)
- Backend tests: `pytest backend/tests/test_market_import_service.py -v`
- Frontend typecheck/build (optional): `cd frontend && npm run build`

