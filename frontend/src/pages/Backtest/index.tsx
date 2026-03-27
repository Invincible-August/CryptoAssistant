import { useState } from 'react'
import { Typography, Card, Form, Input, Select, DatePicker, Button, Row, Col, Statistic, Table, message } from 'antd'
import { backtestApi } from '../../services/backtest'

const { RangePicker } = DatePicker

export default function Backtest() {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)

  const onFinish = async (values: any) => {
    setLoading(true)
    try {
      const [start, end] = values.dateRange || []
      const res: any = await backtestApi.run({
        name: values.name || '默认回测',
        symbol: values.symbol || 'BTCUSDT',
        timeframe: values.timeframe || '1h',
        start_date: start?.format('YYYY-MM-DD') || '2024-01-01',
        end_date: end?.format('YYYY-MM-DD') || '2024-12-31',
        initial_capital: values.initial_capital || 10000,
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
        <Form layout="vertical" onFinish={onFinish}>
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item label="任务名称" name="name">
                <Input placeholder="回测任务名称" />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item label="交易对" name="symbol" initialValue="BTCUSDT">
                <Select options={[
                  { label: 'BTC/USDT', value: 'BTCUSDT' },
                  { label: 'ETH/USDT', value: 'ETHUSDT' },
                ]} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item label="K线周期" name="timeframe" initialValue="1h">
                <Select options={[
                  { label: '1小时', value: '1h' },
                  { label: '4小时', value: '4h' },
                  { label: '1天', value: '1d' },
                ]} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item label="初始资金" name="initial_capital" initialValue={10000}>
                <Input type="number" suffix="USDT" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="回测时间范围" name="dateRange">
                <RangePicker style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12} style={{ display: 'flex', alignItems: 'end' }}>
              <Form.Item>
                <Button type="primary" htmlType="submit" loading={loading} size="large">
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
            <Col span={4}><Statistic title="总收益率" value={(result.metrics.total_return * 100).toFixed(2)} suffix="%" /></Col>
            <Col span={4}><Statistic title="最大回撤" value={(result.metrics.max_drawdown * 100).toFixed(2)} suffix="%" /></Col>
            <Col span={4}><Statistic title="胜率" value={(result.metrics.win_rate * 100).toFixed(2)} suffix="%" /></Col>
            <Col span={4}><Statistic title="盈亏比" value={result.metrics.profit_loss_ratio?.toFixed(2)} /></Col>
            <Col span={4}><Statistic title="总交易" value={result.metrics.total_trades} suffix="笔" /></Col>
            <Col span={4}><Statistic title="夏普比率" value={result.metrics.sharpe_ratio?.toFixed(4)} /></Col>
          </Row>
        </Card>
      )}
    </div>
  )
}
