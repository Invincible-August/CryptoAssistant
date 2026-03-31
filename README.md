# CryptoAssistant - 加密货币交易辅助系统 MVP

事件驱动型加密货币交易辅助系统，提供实时监控、技术分析、行为推断、交易建议、回测和AI分析能力。

## 项目特性

- **实时行情监控** - Binance现货/永续，WebSocket + REST补偿
- **插件化指标系统** - 6个内置指标（MA/EMA/RSI/MACD/VWAP/VolumeSpikeIndicator），支持自定义扩展
- **插件化因子系统** - 6个内置因子（动量/波动率/成交Delta/盘口失衡/OI变化/主力成本区），支持自定义
- **行为分析引擎** - 评分引擎 + 威科夫理论假设引擎 + 交易建议生成
- **K线级回测** - 完整绩效指标（收益率/回撤/胜率/夏普比率）
- **AI分析模块** - OpenAI集成，市场分析和指标/因子建议（独立模块）
- （已移除）TradingView集成 - Webhook信号接入
- **执行辅助** - 模拟/真实下单，拆单/阶梯挂单（默认关闭）
- **Web可视化** - React + Ant Design暗色主题，11个管理页面（含「导入行情」异步任务）
- **权限管理** - JWT认证 + RBAC（管理员/普通用户）

## 技术栈

| 后端 | 前端 | 基础设施 |
|------|------|---------|
| Python 3.12 / FastAPI | React 18 + TypeScript | PostgreSQL 16（本地安装） |
| SQLAlchemy 2.0 (异步) | Ant Design 5 | Redis 7（本地安装） |
| Pydantic v2 | ECharts / Lightweight Charts | Nginx（可选，生产部署） |
| OpenAI SDK | Zustand (状态管理) | APScheduler |

## 快速开始

### 1. 安装必需软件

| 软件 | 版本要求 | 下载地址 |
|------|---------|---------|
| Python | 3.12+ | https://www.python.org/downloads/ |
| Node.js | 20+ | https://nodejs.org/ |
| PostgreSQL | 16+ | https://www.postgresql.org/download/ |
| Redis | 7+（Windows可用Memurai或WSL） | https://redis.io/download/ |

### 2. 配置环境变量

```bash
cd TradingAgent
copy .env.example .env
# 编辑 .env 文件，确保数据库连接信息正确
```

可选：若需在受限网络下通过代理拉取 Binance 历史行情（REST 层 `use_proxy=True`），在 `use_proxy=True` 时解析顺序为：`BINANCE_PROXY_ENABLED=true` 且 `BINANCE_PROXY_URL` 非空则优先使用该 URL（代码默认 `http://127.0.0.1:7890`，可在 `.env` 覆盖），否则使用环境变量 `HTTPS_PROXY` / `HTTP_PROXY`；`BINANCE_PROXY_ENABLED=false` 时忽略应用内 URL，仅使用环境变量。

### 2.1 （可选）Binance 代理配置（内网/中国大陆网络常用）

如果你无法直接访问 Binance，可在 `.env` 中配置：

```bash
BINANCE_PROXY_ENABLED=true
BINANCE_PROXY_URL=http://127.0.0.1:7890
```

该配置会同时影响 WebSocket（K 线/逐笔/深度/标记价格）与 REST（图表页 `live` 拉取 K 线）。

### 2.2 Binance 测试网开关（默认主网）

如果你使用实际交易/实时行情，建议保持默认的 `BINANCE_TESTNET=false`。
当前代码默认主网；如你确实需要测试网，请自行验证 WebSocket 地址在你网络环境下是否可用。

### 3. 初始化数据库

安装 PostgreSQL 后创建数据库：

```sql
-- 连接PostgreSQL后执行
CREATE DATABASE crypto_assistant;
```

### 4. 启动 Redis

```bash
# Windows (如果安装了Redis或Memurai)
redis-server

# Linux / macOS
redis-server
```

### 5. 启动后端

```bash
cd backend
pip install -r requirements.txt
cd ..
python scripts/create_admin.py        # 创建管理员账户
python scripts/seed_demo_data.py      # 导入示例数据（含30天BTCUSDT K线）
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端启动后访问 http://localhost:8000/docs 查看 Swagger API文档。

### 6. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 7. 访问系统

- 前端界面: http://localhost:5173
- 导入行情（导入历史数据）：前端菜单「导入行情」，创建导入任务后会自动轮询进度（支持 `kline` / `trades` / `funding_rate` / `open_interest`；`orderbook` 在 MVP 下会标记为不支持历史回放）
- API文档: http://localhost:8000/docs
- 默认账号: `admin` / `admin123456`

### Windows 一键启动

项目提供了 Windows 批处理脚本：

```bash
# 启动后端
scripts\start_backend.bat

# 启动前端（新开一个终端）
scripts\start_frontend.bat
```

## 项目结构

```
TradingAgent/
├── backend/                    # 后端（Python/FastAPI）
│   ├── app/
│   │   ├── main.py            # 应用入口
│   │   ├── api/v1/            # API 路由（含 admin 插件热重载）
│   │   ├── core/              # 核心配置/安全/数据库/Redis/热重载
│   │   ├── models/            # 数据库模型（23张表）
│   │   ├── schemas/           # Pydantic请求/响应模型
│   │   ├── services/          # 业务逻辑层
│   │   ├── modules/           # 评分/推断/建议引擎
│   │   ├── indicators/        # 技术指标插件系统
│   │   ├── factors/           # 量化因子插件系统
│   │   ├── datafeeds/         # Binance数据源适配器
│   │   ├── ai/                # AI分析模块
│   │   ├── lightweight_charts_compat/  # 图表格式兼容映射层（Lightweight Charts）
│   │   ├── backtest/          # 回测引擎
│   │   ├── execution/         # 执行辅助模块
│   │   ├── tasks/             # 定时任务
│   │   └── utils/             # 工具函数
│   ├── config/                # plugin_runtime.yaml、backtest_strategies/*.yaml
│   └── requirements.txt
├── frontend/                   # 前端（React/TypeScript）
│   ├── src/
│   │   ├── pages/             # 11个页面
│   │   ├── layouts/           # 布局组件
│   │   ├── services/          # API服务
│   │   ├── store/             # 状态管理
│   │   └── router/            # 路由配置
│   └── package.json
├── deploy/                     # 部署配置
│   └── nginx.conf             # Nginx反向代理（可选，生产部署用）
├── docs/                       # 项目文档（中文）
│   ├── 开发指南.md             # 二次开发：结构、API 映射、扩展步骤
│   ├── 图表分析开发指南.md      # 图表模块：文件/函数、前后端 API、数据落库说明
├── scripts/                    # 脚本工具（启动/初始化）
├── DEPLOY_GUIDE.md             # 完整部署指南（Windows + Linux）
├── tests/                      # 测试代码
└── .env.example                # 环境变量模板
```

## 模块开关

| 模块 | 环境变量 | 默认 |
|------|---------|------|
| AI分析 | MODULE_AI_ENABLED | false |
| TradingView（已移除） | - | - |
| 执行辅助 | MODULE_EXECUTION_ENABLED | false |
| 回测 | MODULE_BACKTEST_ENABLED | true |
| 插件热重载 API | PLUGIN_HOT_RELOAD_ENABLED | true（生产可设 false） |

## 插件运行时配置（因子/指标「不加载」）

- 配置文件：`backend/config/plugin_runtime.yaml`（仓库内提供空列表默认；可复制 `backend/config/examples/plugin_runtime.example.yaml` 参考）。
- 字段：`disabled_factors`、`disabled_indicators`（字符串列表）。列入其中的插件仍会出现在列表 API，但 `load_enabled=false`，且 **计算接口** 与 **FeaturePipeline** 会跳过。
- 管理 API（需 **admin** 角色）：`PATCH /api/v1/factors/runtime/load-enabled`、`PATCH /api/v1/indicators/runtime/load-enabled`，请求体 `{ "factor_key"|"indicator_key", "load_enabled": true/false }`。
- 前端：因子页 / 指标页表格「加载」列；管理员可对单行「不加载 / 恢复」；指标页另有「重载插件」按钮（见下）。

## 回测策略预设（YAML）

- 目录：`backend/config/backtest_strategies/*.yaml`（示例见 `backend/config/examples/backtest_strategies/example_strategy.yaml`）。
- 每个文件字段：`id`、`display_name`、`description`（可选）、`strategy_config`（与 `app/backtest/strategy_adapter.py` 中默认键兼容，如 `warmup_period`、`indicators`、`factors` 等）。
- `GET /api/v1/backtest/strategies`：列出预设（短时 mtime 缓存，一般无需重启即可看到新文件）。
- `POST /api/v1/backtest/run`：传 `strategy_preset_id`（对应 YAML 的 `id`）；可选同传 `strategy_config` 与预设 **深度合并**（请求体覆盖叶子字段）。未传 `name` 时使用预设的 `display_name`。仍需传 `symbol`、`exchange`、`market_type`、`timeframe`、`start_date`、`end_date` 等；K 线查询已按交易所与市场类型过滤。
- 前端回测页使用「回测策略」下拉框，提交 `strategy_preset_id` 与上述字段。

## 插件热重载（Python 插件）

- `POST /api/v1/admin/plugins/reload`（**admin** + `PLUGIN_HOT_RELOAD_ENABLED=true`）：从 `sys.modules` 卸载 `app.indicators.{builtins,custom}` 与 `app.factors.{builtins,custom}` 下已加载模块，按 `__module__` 清理注册表后重新扫描注册。
- 若自定义模块之间存在复杂相互 import，可能需要连续重载一次或重启进程；详见 `app/core/plugin_hot_reload.py` 注释。

## 图表分析（K 线 + 可选指标）

- **后端**：`GET /api/v1/chart/bundle`（需登录），查询参数：`symbol`、`timeframe`、`exchange`、`market_type`、`limit`、`indicators`（逗号分隔指标 key，留空则仅 K 线）。返回 `config`、`candlestick`、`overlays`、`subcharts`、`meta`（含 `failed_indicators`）。
  - 新增：`source_mode=cache|live`（默认 `cache`）与 `force_refresh=true`（等价别名，等价于 `source_mode=live`）
  - 新增：`use_proxy=true|false`（默认 `false`）。当 `source_mode=live` 且 `exchange=binance` 时，可通过本地 HTTP 代理访问 Binance REST 接口（用于网络受限环境）。
  - `live` 模式由 `MarketDataProvider` 走交易所实时拉取并回写缓存（当前仅 `binance` adapter 已实现；OKX/Bitget 需后续补充适配器）
- **与 TradingView 模块的关系**：TradingView webhook 与 `TradingView` 兼容接口已移除；本接口仅返回 Lightweight Charts 数据包。
- **前端**：`/chart` 页面使用 `lightweight-charts` 渲染；需已导入 K 线数据（如 `scripts/seed_demo_data.py`）。

## 自定义指标示例

在 `backend/app/indicators/custom/` 下创建新文件，继承 `BaseIndicator` 并实现 `calculate()` 方法：

```python
from app.indicators.base import BaseIndicator

class MyIndicator(BaseIndicator):
    indicator_key = "my_indicator"
    name = "我的自定义指标"
    source = "human"

    @classmethod
    def calculate(cls, df, params):
        # 实现计算逻辑
        ...
```

系统会自动扫描并注册。

## 二次开发

扩展功能、补全页面或对接新业务时，请先阅读 **[docs/开发指南.md](./docs/开发指南.md)**：其中说明仓库分层、API 与前端路由对应关系、请求链路、常见扩展步骤（新接口 / 新页面 / 新指标与因子）。**图表分析**模块的逐文件说明（含函数级与数据是否落库）见 **[docs/图表分析开发指南.md](./docs/图表分析开发指南.md)**。

## 详细部署指南

如果你是第一次部署、不熟悉环境配置，请参阅 **[DEPLOY_GUIDE.md](./DEPLOY_GUIDE.md)**，该文档分别提供了 Windows 和 Linux 的完整步骤说明，从安装软件到验证运行，适合零基础用户按步操作。

## 生产部署（可选）

如果需要在生产环境部署，可以：

1. 构建前端静态文件：`cd frontend && npm run build`
2. 安装 Nginx，将 `deploy/nginx.conf` 复制到 Nginx 配置目录
3. 修改 `nginx.conf` 中的 `root` 路径指向 `frontend/dist`
4. 后端使用 `uvicorn app.main:app --workers 4` 多进程运行

## 运行测试

```bash
pytest tests/ -v
```

## 许可证

MIT License
