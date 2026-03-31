import { useEffect, useState } from 'react'
import {
  Typography,
  Card,
  Form,
  Select,
  DatePicker,
  Button,
  Row,
  Col,
  Statistic,
  message,
} from 'antd'
import dayjs, { Dayjs } from 'dayjs'
import { backtestApi } from '../../services/backtest'

const { RangePicker } = DatePicker

type StrategyRow = { id: string; display_name: string; description?: string }

export default function Backtest() {
  const [loading, setLoading] = useState(false)
  const [strategiesLoading, setStrategiesLoading] = useState(true)
  const [strategies, setStrategies] = useState<StrategyRow[]>([])
  const [result, setResult] = useState<any>(null)
  const [form] = Form.useForm()

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setStrategiesLoading(true)
      try {
        const res: any = await backtestApi.listStrategies()
        const rows = (res?.data || []) as StrategyRow[]
        if (!cancelled) {
          setStrategies(rows)
          if (rows.length > 0) {
            form.setFieldsValue({ strategy_preset_id: rows[0].id })
          }
        }
      } catch {
        if (!cancelled) message.error('加载策略预设失败')
      } finally {
        if (!cancelled) setStrategiesLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [form])

  const onFinish = async (values: any) => {
    const range = values.dateRange as [Dayjs, Dayjs] | undefined
    const start = range?.[0]
    const end = range?.[1]
    if (!values.strategy_preset_id) {
      message.warning('请选择回测策略')
      return
    }
    if (!start || !end) {
      message.warning('请选择回测时间范围')
      return
    }
    setLoading(true)
    try {
      const res: any = await backtestApi.run({
        strategy_preset_id: values.strategy_preset_id,
        symbol: values.symbol || 'BTCUSDT',
        exchange: values.exchange || 'binance',
        market_type: values.market_type || 'spot',
        timeframe: values.timeframe || '1h',
        start_date: start.startOf('day').toISOString(),
        end_date: end.endOf('day').toISOString(),
        initial_capital: values.initial_capital ?? 10000,
      })
      setResult(res?.data)
      message.success('回测完成')
    } catch {
      message.error('回测失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <Typography.Title level={3}>策略回测</Typography.Title>

      <Card title="回测配置" style={{ marginBottom: 16 }}>
        <Form
          layout="vertical"
          form={form}
          onFinish={onFinish}
          initialValues={{
            symbol: 'BTCUSDT',
            exchange: 'binance',
            market_type: 'spot',
            timeframe: '1h',
            initial_capital: 10000,
            dateRange: [dayjs('2024-01-01'), dayjs('2024-01-30')],
          }}
        >
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                label="回测策略"
                name="strategy_preset_id"
                rules={[{ required: true, message: '请选择策略' }]}
              >
                <Select
                  loading={strategiesLoading}
                  placeholder="从 YAML 预设中选择"
                  options={strategies.map((s) => ({
                    label: s.display_name,
                    value: s.id,
                  }))}
                  showSearch
                  optionFilterProp="label"
                />
              </Form.Item>
            </Col>
            <Col span={4}>
              <Form.Item label="交易所" name="exchange">
                <Select
                  options={[{ label: 'Binance', value: 'binance' }]}
                />
              </Form.Item>
            </Col>
            <Col span={4}>
              <Form.Item label="市场" name="market_type">
                <Select
                  options={[
                    { label: '现货', value: 'spot' },
                    { label: '合约', value: 'futures' },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="交易对" name="symbol">
                <Select
                  options={[
                    { label: 'BTC/USDT', value: 'BTCUSDT' },
                    { label: 'ETH/USDT', value: 'ETHUSDT' },
                  ]}
                />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item label="K线周期" name="timeframe">
                <Select
                  options={[
                    { label: '1小时', value: '1h' },
                    { label: '4小时', value: '4h' },
                    { label: '1天', value: '1d' },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item label="初始资金" name="initial_capital">
                <Select
                  options={[
                    { label: '10,000 USDT', value: 10000 },
                    { label: '50,000 USDT', value: 50000 },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="回测时间范围"
                name="dateRange"
                rules={[{ required: true, message: '请选择日期范围' }]}
              >
                <RangePicker style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Row>
            <Col>
              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={loading}
                  size="large"
                >
                  开始回测
                </Button>
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Card>

      {result?.metrics && (
        <Card title="回测结果">
          <Row gutter={16}>
            <Col span={4}>
              <Statistic
                title="总收益率"
                value={(result.metrics.total_return * 100).toFixed(2)}
                suffix="%"
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="最大回撤"
                value={(result.metrics.max_drawdown * 100).toFixed(2)}
                suffix="%"
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="胜率"
                value={(result.metrics.win_rate * 100).toFixed(2)}
                suffix="%"
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="盈亏比"
                value={result.metrics.profit_loss_ratio?.toFixed(2)}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="总交易"
                value={result.metrics.total_trades}
                suffix="笔"
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="夏普比率"
                value={result.metrics.sharpe_ratio?.toFixed(4)}
              />
            </Col>
          </Row>
        </Card>
      )}
    </div>
  )
}
