import { Typography, Card, Select, Row, Col, Empty } from 'antd'

export default function ChartAnalysis() {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={3}>图表分析</Typography.Title>
        <div style={{ display: 'flex', gap: 8 }}>
          <Select defaultValue="BTCUSDT" style={{ width: 150 }}
            options={[
              { label: 'BTC/USDT', value: 'BTCUSDT' },
              { label: 'ETH/USDT', value: 'ETHUSDT' },
            ]}
          />
          <Select defaultValue="1h" style={{ width: 100 }}
            options={[
              { label: '1分钟', value: '1m' },
              { label: '5分钟', value: '5m' },
              { label: '15分钟', value: '15m' },
              { label: '1小时', value: '1h' },
              { label: '4小时', value: '4h' },
              { label: '1天', value: '1d' },
            ]}
          />
        </div>
      </div>
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card title="K线图 (主图)" style={{ height: 500 }}>
            <Empty description="图表组件将在接入ECharts后展示K线和指标覆盖层" />
          </Card>
        </Col>
        <Col span={24}>
          <Card title="副图指标">
            <Empty description="在此显示RSI、MACD等副图指标" />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
