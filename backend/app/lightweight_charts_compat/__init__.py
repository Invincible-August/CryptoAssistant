"""
Lightweight Charts 兼容层（后端映射工具包）。

本目录用于在**后端**将内部数据结构（K 线、指标序列、信号等）转换为
前端 `lightweight-charts` 组件所消费的 JSON 形状（shape）。

典型用法：
- 后端服务层从数据库/计算模块拿到 K 线与指标结果；
- 调用 `chart_mapping.py` 中的转换函数（例如 `klines_to_tv_format`、`indicator_to_tv_overlay`），
  得到前端可直接渲染的 series 数据结构；
- 最终由前端将这些 series 传给 `lightweight-charts` 的各类 series API 渲染。

注意：
- 这里的“TV format”指的是轻量图表常用的 `{time, open, high, low, close}` 等字段形态，
  并非 TradingView 官方接口。
"""

