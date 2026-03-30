# Changelog

本文件记录 TradingAgent 项目的所有重要变更。

## [Unreleased]

### 新增

- **行情导入服务与 API**：`MarketImportService`（`backend/app/services/market_import_service.py`）从 `market_import_tasks` 读取任务配置，将状态置为 `running`，按 `import_types` 拉取历史数据并写入 `market_service.save_*`（K 线重复行通过嵌套事务跳过唯一约束冲突）。MVP 支持 `kline` / `trades` / `funding_rate` / `open_interest`；`orderbook` 标记为 `unsupported_historical` 不做历史回补。聚合成交按 ≤1 小时窗口分片；持仓量历史裁剪至最近 30 天并在 `type_results` 中标记 `partial`；`result_json` 含 `summary` + `type_results` + `errors`。新增 `POST /api/v1/market/import`（创建任务并 `asyncio.create_task` 后台执行）、`GET /api/v1/market/import/{task_id}`（查询状态与结果）。单元测试见 `tests/backend/unit/test_market_import_service.py`、`tests/backend/unit/test_market_import_api.py`（无网络、无真实 DB）。

- **Binance 行情导入 REST 历史接口**：`BinanceRestClient` 增加现货/合约聚合成交历史（`/api/v3/aggTrades`、`/fapi/v1/aggTrades`）、资金费率历史（`/fapi/v1/fundingRate`）、持仓量历史（`/futures/data/openInterestHist`）；`_request` 支持 `use_proxy=True` 时按优先级解析代理；`settings.BINANCE_PROXY_ENABLED` 为 True 且 `settings.BINANCE_PROXY_URL` 非空时优先使用该 URL，否则回退到 `HTTPS_PROXY`/`HTTP_PROXY`（`BINANCE_PROXY_ENABLED` 为 False 时忽略应用内 URL）。`BinanceAdapter` 提供对应高层方法与解析（`parser.py` 中聚合成交与资金/OI 历史行规范化）。单元测试见 `tests/backend/unit/test_binance_rest_market_import.py`（monkeypatch `_request` / AsyncMock httpx，无网络）。

### 变更

- **文档**：`use_proxy` 与 Binance REST 代理优先级说明已与 `BinanceRestClient._request` 实现对齐；`BINANCE_PROXY_URL` 默认值恢复为 `http://127.0.0.1:7890`（与项目惯例一致，可被 `.env` 覆盖）。
- **行情导入 API 契约**：`MarketImportCreateRequest` 不再包含 `created_by` / `status`（由服务端从认证与默认值写入）；`MarketImportTaskResponse` 仍返回二者。
- **Alembic**：`backend/migrations/env.py` 将 `target_metadata` 设为 `app.core.database.Base.metadata`，并 `import app.models` 以注册全部 ORM 表，使 `alembic revision --autogenerate` 能正确对比模型与数据库。`backend/alembic.ini` 注释改为纯 ASCII，避免在 Windows 下 `ConfigParser` 使用系统 locale 读取 UTF-8 字节时触发 `UnicodeDecodeError`。

### 修复

- **行情导入幂等写入**：为 `market_trades/market_fundings/market_open_interests` 增加唯一约束（交易/资金费率/OI 的 identity key），并在 `market_service` 保存逻辑中使用 PostgreSQL `ON CONFLICT` 实现重复导入不重复写入（funding/OI 冲突时按需要更新）。

### 新增

- **行情导入任务（Market Import）**：新增 `MarketImportTask` ORM 模型与 Pydantic schemas（`backend/app/models/market_import_task.py`、`backend/app/schemas/market_import.py`），并添加 Alembic 迁移创建 `market_import_tasks` 表（`backend/migrations/versions/*_add_market_import_tasks.py`）。提供任务状态 `pending/running/completed/failed`、进度 `progress` 与 `result_json/last_error` 结果字段，便于后续导入服务与前端进度跟踪。
- **测试**：新增无数据库依赖的 `Base.metadata` 注册与 `MarketImportTask.__tablename__` 断言（`tests/backend/unit/test_market_import_metadata.py`），与 Alembic `env.py` 的模型导入方式对齐。
  - 补充 **timezone-aware 时间戳** 与 **ORM 默认值** 的单测，确保任务创建不依赖调用方手动填充默认字段，并明确拒绝 naive datetime。

## [0.3.1] - 2026-03-27

### 变更

- **认证**：密码哈希改为直接使用 `bcrypt`（`app/core/security.py`），移除 `passlib` 依赖，消除 `bcrypt` 4.x 下 `module 'bcrypt' has no attribute '__about__'` 的警告；已存库的 bcrypt 字符串仍可正常校验。
- **前端监控页**：补全“添加监控币对”和“删除监控币对”交互。新增 `frontend/src/services/monitor.ts` 统一封装 `GET/POST/DELETE /monitor/watches`，`frontend/src/pages/Monitor/index.tsx` 增加添加弹窗表单、删除确认和列表刷新逻辑。

### 新增

- **文档**：新增 [docs/开发指南.md](./docs/开发指南.md)，面向二次开发者说明仓库结构、前后端协作方式、14 组 API 与前端路由对照、常见扩展任务及 MVP 功能完成度提示；README 增加入口链接。

## [0.3.0] - 2026-03-27

### 新增

- **数据源层（Datafeeds）**：完整的交易所数据适配器架构
  - `BaseExchangeAdapter` 抽象基类：定义 connect/disconnect、subscribe、REST 查询等统一接口
  - `UnifiedKline` / `UnifiedTrade` / `UnifiedOrderbook` / `UnifiedFunding` / `UnifiedOI` 统一数据结构（dataclass）
  - `DatafeedManager` 数据源管理器：多适配器注册、订阅路由、指数退避自动重连
  - Binance REST 客户端（`httpx`）：现货+合约双市场、速率限制检测、指数退避重试
  - Binance 现货 WebSocket：kline/trade/depth 实时订阅、自动重连、心跳保活
  - Binance 合约 WebSocket：kline/aggTrade/depth/markPrice 实时订阅
  - Binance 数据解析器：REST 和 WebSocket 原始数据 → 统一结构的完整转换
  - `BinanceAdapter` 统一适配器：整合 REST + 现货 WS + 合约 WS，实现 BaseExchangeAdapter 全部接口

- **业务服务层（Services）**：7 个核心业务服务模块
  - `auth_service` - 认证服务：用户登录验证（密码哈希校验 + 账户状态检查）、注册创建、JWT 令牌生成与解析
  - `user_service` - 用户服务：CRUD 操作、分页查询（支持角色/状态过滤）、密码修改
  - `market_service` - 行情数据服务：K线/成交/订单簿/资金费率/持仓量的 DB 存储与查询，Redis 缓存加速
  - `indicator_service` - 指标服务：注册列表、K线数据加载 → 指标计算 → 结果持久化完整流程
  - `factor_service` - 因子服务：多维度数据上下文构建（kline/orderbook/OI/trades）、因子计算与结果保存
  - `module_service` - 模块配置服务：环境变量 + DB 双源优先级判断、upsert 更新逻辑
  - `log_service` - 日志服务：系统日志与错误日志的 DB 写入、多维度分页查询、异常便捷方法

### 技术细节

- 数据源层采用适配器模式（Adapter Pattern），交易所与业务层完全解耦
- WebSocket 客户端支持单连接多流（最多 200 个流/连接），符合 Binance API 限制
- REST 客户端使用 httpx 连接池复用，支持自定义超时和最大重试次数
- 行情服务采用 Cache-Aside 策略：Redis 缓存优先 → 数据库回源 → 缓存回写
- 模块启用判断三级优先级：环境变量 > 数据库配置 > 默认禁用
- 所有服务函数接受 `AsyncSession` 参数，保持无状态和可测试性
- 日志服务同时写入 loguru 文件和数据库，双通道保障

---

## [0.2.0] - 2026-03-27

### 新增

- **因子插件系统**：完整的多因子分析插件化架构
  - `BaseFactor` 基类：统一的因子接口，支持元数据、参数校验、计算、归一化、信号/图表格式化
  - `FactorRegistry` 注册中心：支持自动扫描注册、按 category/source/input_type 多维筛选
  - 自动发现机制：启动时扫描 `builtins/` 和 `custom/` 目录注册所有因子

- **内置因子（5个）**：
  - `momentum` - 动量因子：ROC、加速度、趋势一致性，综合 momentum_score（0-100）
  - `volatility` - 波动率因子：ATR、布林带宽度、历史波动率，综合 volatility_score（0-100）
  - `trade_delta` - 成交Delta因子：基于K线估算买卖量，delta_score（0-100）
  - `orderbook_imbalance` - 盘口失衡因子：加权订单簿分析，imbalance_score（0-100）
  - `oi_change` - 持仓量变化因子：OI变化率与价格皮尔逊相关性，oi_score（0-100）

- **自定义因子示例（1个）**：
  - `main_force_cost_zone` - 主力成本区间因子：VWAP成本区间估算，完整实现 normalize/format_for_signal/format_for_chart

### 技术细节

- 因子与指标的区分：因子支持多数据源（kline/orderbook/open_interest），输出结构化 Dict 而非 DataFrame
- 所有因子评分统一归一化到 0-100，50 为中性基准
- 评分映射使用 sigmoid 函数，参数根据加密货币市场经验标定
- 盘口因子和OI因子实现了数据缺失时的优雅降级
- 成交Delta通过 (close-low)/(high-low) 估算买入比例
- OI因子使用皮尔逊相关系数分析 OI-价格联动关系
- 主力成本区间因子完整展示自定义因子开发范式（normalize + signal + chart）

---

## [0.1.0] - 2026-03-27

### 新增

- **指标插件系统**：完整的技术指标插件化架构
  - `BaseIndicator` 基类：统一的指标接口定义，包含元数据、参数校验、计算、图表格式化、信号格式化等方法
  - `IndicatorRegistry` 注册中心：支持手动注册、自动扫描发现、按来源过滤
  - 自动发现机制：应用启动时自动扫描 `builtins/` 和 `custom/` 目录并注册所有指标

- **内置指标（5个）**：
  - `ma` - 简单移动平均线（SMA），trend 分类，主图叠加
  - `ema` - 指数移动平均线（EMA），trend 分类，主图叠加
  - `rsi` - 相对强弱指标（RSI），momentum 分类，副图独立面板
  - `macd` - MACD 指标（DIF/DEA/柱状图），momentum 分类，副图独立面板
  - `vwap` - 成交量加权平均价（VWAP），volume 分类，主图叠加

- **自定义指标示例（1个）**：
  - `volume_spike` - 成交量异动检测，volume 分类，副图独立面板

### 技术细节

- 所有指标均包含完整的 `params_schema`、`output_schema`、`display_config`
- RSI 使用 Wilder 平滑法（`ewm(com=period-1)`）
- MACD 柱状图采用 `(DIF - DEA) × 2` 公式
- VWAP 使用滚动窗口计算典型价格加权均值
