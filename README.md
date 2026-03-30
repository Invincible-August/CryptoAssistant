# CryptoAssistant - 加密货币交易辅助系统 MVP

事件驱动型加密货币交易辅助系统，提供实时监控、技术分析、行为推断、交易建议、回测和AI分析能力。

## 项目特性

- **实时行情监控** - Binance现货/永续，WebSocket + REST补偿
- **插件化指标系统** - 6个内置指标（MA/EMA/RSI/MACD/VWAP/VolumeSpikeIndicator），支持自定义扩展
- **插件化因子系统** - 6个内置因子（动量/波动率/成交Delta/盘口失衡/OI变化/主力成本区），支持自定义
- **行为分析引擎** - 评分引擎 + 威科夫理论假设引擎 + 交易建议生成
- **K线级回测** - 完整绩效指标（收益率/回撤/胜率/夏普比率）
- **AI分析模块** - OpenAI集成，市场分析和指标/因子建议（独立模块）
- **TradingView集成** - Webhook信号接入（独立模块）
- **执行辅助** - 模拟/真实下单，拆单/阶梯挂单（默认关闭）
- **Web可视化** - React + Ant Design暗色主题，10个管理页面
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
│   │   ├── api/v1/            # API路由（14组）
│   │   ├── core/              # 核心配置/安全/数据库/Redis
│   │   ├── models/            # 数据库模型（23张表）
│   │   ├── schemas/           # Pydantic请求/响应模型
│   │   ├── services/          # 业务逻辑层
│   │   ├── modules/           # 评分/推断/建议引擎
│   │   ├── indicators/        # 技术指标插件系统
│   │   ├── factors/           # 量化因子插件系统
│   │   ├── datafeeds/         # Binance数据源适配器
│   │   ├── ai/                # AI分析模块
│   │   ├── tradingview/       # TradingView集成
│   │   ├── backtest/          # 回测引擎
│   │   ├── execution/         # 执行辅助模块
│   │   ├── tasks/             # 定时任务
│   │   └── utils/             # 工具函数
│   └── requirements.txt
├── frontend/                   # 前端（React/TypeScript）
│   ├── src/
│   │   ├── pages/             # 10个页面
│   │   ├── layouts/           # 布局组件
│   │   ├── services/          # API服务
│   │   ├── store/             # 状态管理
│   │   └── router/            # 路由配置
│   └── package.json
├── deploy/                     # 部署配置
│   └── nginx.conf             # Nginx反向代理（可选，生产部署用）
├── docs/                       # 项目文档（中文）
│   ├── 开发指南.md             # 二次开发：结构、API 映射、扩展步骤
├── scripts/                    # 脚本工具（启动/初始化）
├── DEPLOY_GUIDE.md             # 完整部署指南（Windows + Linux）
├── tests/                      # 测试代码
└── .env.example                # 环境变量模板
```

## 模块开关

| 模块 | 环境变量 | 默认 |
|------|---------|------|
| AI分析 | MODULE_AI_ENABLED | false |
| TradingView | MODULE_TRADINGVIEW_ENABLED | false |
| 执行辅助 | MODULE_EXECUTION_ENABLED | false |
| 回测 | MODULE_BACKTEST_ENABLED | true |

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

扩展功能、补全页面或对接新业务时，请先阅读 **[docs/开发指南.md](./docs/开发指南.md)**：其中说明仓库分层、14 组 API 与前端路由对应关系、请求链路、常见扩展步骤（新接口 / 新页面 / 新指标与因子），并标注了部分页面仍为占位实现（如图表页），便于排期与分工。

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
