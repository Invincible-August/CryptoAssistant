# 测试说明

## 目录结构

```
tests/
├── backend/
│   ├── unit/           # 单元测试
│   │   ├── conftest.py # 测试配置
│   │   ├── test_indicators.py  # 指标测试
│   │   ├── test_factors.py     # 因子测试
│   │   └── test_backtest.py    # 回测测试
│   ├── integration/    # 集成测试（需要数据库）
│   └── fixtures/       # 测试数据
└── README.md
```

## 运行测试

```bash
cd TradingAgent
pytest tests/ -v
```

## 运行覆盖率报告

```bash
pytest tests/ --cov=backend/app --cov-report=html
```
