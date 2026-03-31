/**
 * 图表分析页：从后端拉取「K 线 + 可选指标」打包数据（ChartBundle），交给 Lightweight Charts 渲染。
 *
 * 数据流简述：
 * - 首次挂载与参数变化时，默认以 `source_mode: 'cache'` 请求 `/api/v1/chart/bundle`（读库/缓存优先）。
 * - 用户可点「强制刷新（实时）」以 `source_mode: 'live'` 拉取最新数据（当前仅 Binance 现货可用）。
 * - `use_proxy` 开关会传给后端，用于受限网络下走代理访问交易所 REST。
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Typography,
  Card,
  Select,
  Row,
  Col,
  Button,
  Switch,
  Space,
  Alert,
  Spin,
} from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import LightweightChartBoard from '../../components/chart/LightweightChartBoard'
import { chartApi, type ChartBundle } from '../../services/chart'
import { indicatorApi } from '../../services/indicators'

/** 交易对下拉选项：label 为展示名，value 为传给后端的 symbol（如 BTCUSDT）。 */
const SYMBOL_OPTIONS = [
  { label: 'BTC/USDT', value: 'BTCUSDT' },
  { label: 'ETH/USDT', value: 'ETHUSDT' },
  { label: 'BNB/USDT', value: 'BNBUSDT' },
]

/** K 线周期选项：与后端 interval/timeframe 约定一致（1m、1h 等）。 */
const TIMEFRAME_OPTIONS = [
  { label: '1分钟', value: '1m' },
  { label: '5分钟', value: '5m' },
  { label: '15分钟', value: '15m' },
  { label: '1小时', value: '1h' },
  { label: '4小时', value: '4h' },
  { label: '1天', value: '1d' },
]

/** 交易所选项：MVP 仅 Binance 可用，其余置灰提示后续扩展。 */
const EXCHANGE_OPTIONS = [
  { label: 'Binance', value: 'binance' },
  { label: 'OKX', value: 'okx', disabled: true },
  { label: 'Bitget', value: 'bitget', disabled: true },
]

/**
 * 图表分析页面组件。
 *
 * 状态与用法说明（变量 → 用途）：
 * - symbol：当前交易对，参与 chart bundle 请求。
 * - timeframe：K 线周期。
 * - exchange：交易所；非 binance 时「强制刷新（实时）」按钮会禁用（与后端能力一致）。
 * - useProxy：是否让后端对 Binance REST 使用代理（`use_proxy` 查询参数）。
 * - indicatorKeys：多选指标 key 列表，会序列化为 `indicators` 查询参数（逗号分隔）。
 * - bundle：最近一次成功返回的 ChartBundle，传给 LightweightChartBoard。
 * - loading：请求进行中，用于 Spin 遮罩。
 * - meta：bundle.meta 副本，用于展示「部分指标计算失败」等提示。
 * - indicatorOptions：从后端指标列表拉取的可选指标下拉数据（过滤掉 chart_compatible === false）。
 */
export default function ChartAnalysis() {
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [timeframe, setTimeframe] = useState('1h')
  const [exchange, setExchange] = useState('binance')
  const [useProxy, setUseProxy] = useState(false)
  const [indicatorKeys, setIndicatorKeys] = useState<string[]>(['ema', 'rsi'])
  const [bundle, setBundle] = useState<ChartBundle | null>(null)
  const [loading, setLoading] = useState(false)
  const [meta, setMeta] = useState<ChartBundle['meta'] | null>(null)

  const [indicatorOptions, setIndicatorOptions] = useState<
    { label: string; value: string }[]
  >([])

  /**
   * 挂载时拉取指标插件列表，填充「指标」多选下拉。
   * 用法：仅执行一次；组件卸载时 `cancelled` 避免 setState 到已卸载组件。
   * 过滤规则：默认展示 chart_compatible !== false 的指标。
   */
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res: any = await indicatorApi.list()
        const list = (res?.data || []) as Array<{
          indicator_key: string
          name: string
          chart_compatible?: boolean
        }>
        const opts = list
          .filter((x) => x.chart_compatible !== false)
          .map((x) => ({
            label: `${x.name} (${x.indicator_key})`,
            value: x.indicator_key,
          }))
        if (!cancelled) setIndicatorOptions(opts)
      } catch {
        /* ignore */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  /**
   * 将所选指标 key 数组序列化为后端所需的逗号分隔字符串。
   * 用法：未选任何指标时传 `undefined`，避免发空字符串。
   */
  const indicatorsParam = useMemo(
    () => (indicatorKeys.length ? indicatorKeys.join(',') : undefined),
    [indicatorKeys],
  )

  /**
   * 请求图表打包数据并更新本地状态。
   *
   * @param mode - `cache`：优先读库/缓存；`live`：强制走实时/回补链路（与后端 source_mode 一致）。
   *
   * 用法说明：
   * - 依赖 symbol / timeframe / exchange / indicatorsParam / useProxy，任一项变化后 `load` 引用会变，
   *   下方 `useEffect` 会再次以 cache 模式拉数。
   * - limit/theme/market_type 此处写死为与本页演示一致；若扩展多市场可改为表单状态。
   */
  const load = useCallback(async (mode: 'cache' | 'live') => {
    setLoading(true)
    try {
      const params: any = {
        symbol,
        timeframe,
        exchange,
        market_type: 'spot',
        limit: 500,
        indicators: indicatorsParam,
        theme: 'dark',
        source_mode: mode,
      }
      if (useProxy) params.use_proxy = true

      const res: any = await chartApi.getBundle(params)
      const data = res?.data as ChartBundle
      setBundle(data)
      setMeta(data?.meta ?? null)
    } catch {
      setBundle(null)
      setMeta(null)
    } finally {
      setLoading(false)
    }
  }, [symbol, timeframe, indicatorsParam, exchange, useProxy])

  /**
   * 当 `load` 函数因依赖变化而更新时，自动以缓存模式重新拉取图表数据。
   * 用法：用户改 symbol/周期/指标等无需手动点「刷新」即可更新（减少一步操作）。
   */
  useEffect(() => {
    void load('cache')
  }, [load])

  /** 后端返回的「未成功绘制的指标」列表，用于顶部 Alert 展示原因。 */
  const failed = meta?.failed_indicators || []

  return (
    <div>
      {/*
        顶部工具栏：交易对 / 周期 / 交易所 / 指标多选 / 代理开关 / 刷新按钮。
        - onChange 直接绑定 setState：受控组件，状态变更会触发 load 依赖链更新。
        - 「强制刷新（实时）」仅在 exchange === 'binance' 时可用，与后端 live 数据源一致。
      */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: 16,
          flexWrap: 'wrap',
          gap: 8,
        }}
      >
        <Typography.Title level={3} style={{ margin: 0 }}>
          图表分析
        </Typography.Title>
        <Space wrap>
          <Select
            value={symbol}
            style={{ width: 150 }}
            options={SYMBOL_OPTIONS}
            onChange={setSymbol}
          />
          <Select
            value={timeframe}
            style={{ width: 120 }}
            options={TIMEFRAME_OPTIONS}
            onChange={setTimeframe}
          />
          <Select
            value={exchange}
            style={{ width: 140 }}
            options={EXCHANGE_OPTIONS}
            onChange={setExchange}
          />
          <Select
            mode="multiple"
            allowClear
            placeholder="指标（可选）"
            style={{ minWidth: 280 }}
            value={indicatorKeys}
            onChange={setIndicatorKeys}
            options={indicatorOptions}
          />
          <Switch
            checked={useProxy}
            onChange={setUseProxy}
            checkedChildren="使用代理"
            unCheckedChildren="不使用代理"
          />
          <Button icon={<ReloadOutlined />} onClick={() => void load('cache')}>
            刷新
          </Button>
          <Button type="primary" onClick={() => void load('live')} disabled={exchange !== 'binance'}>
            强制刷新（实时）
          </Button>
        </Space>
      </div>

      {/* 部分指标计算失败时展示原因列表，不阻塞主图渲染 */}
      {failed.length > 0 && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="部分指标未绘制"
          description={failed.map((f) => `${f.indicator_key}: ${f.reason}`).join('；')}
        />
      )}

      {/* 主图区域：bundle 为空时子组件内部应能优雅处理（如无数据提示） */}
      <Card styles={{ body: { padding: 12 } }}>
        <Spin spinning={loading}>
          <LightweightChartBoard bundle={bundle} />
        </Spin>
      </Card>

      {/* 页脚说明：提示数据来源与无数据时的处理路径 */}
      <Row style={{ marginTop: 12 }}>
        <Col span={24}>
          <Typography.Text type="secondary">
            数据来自后端 /api/v1/chart/bundle（K 线 + 可选指标，Lightweight Charts 渲染）。
            无 K 线时请先在系统中导入或采集行情数据。
          </Typography.Text>
        </Col>
      </Row>
    </div>
  )
}
