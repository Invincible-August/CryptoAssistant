import { useState } from 'react'
import { Typography, Card, Button, Select, Input, Row, Col, Tag, Empty, message } from 'antd'
import { RobotOutlined } from '@ant-design/icons'
import { aiApi } from '../../services/ai'

export default function AIAnalysis() {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [symbol, setSymbol] = useState('BTCUSDT')

  const runAnalysis = async () => {
    setLoading(true)
    try {
      const res: any = await aiApi.analyze({ symbol })
      setResult(res?.data)
      message.success('AI分析完成')
    } catch {
      message.error('AI分析失败，请确认AI模块已启用')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <Typography.Title level={3}>
        <RobotOutlined style={{ marginRight: 8 }} />
        AI分析
        <Tag color="purple" style={{ marginLeft: 8 }}>source=ai</Tag>
      </Typography.Title>

      <Card title="分析配置" style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col span={6}>
            <Select value={symbol} onChange={setSymbol} style={{ width: '100%' }}
              options={[
                { label: 'BTC/USDT', value: 'BTCUSDT' },
                { label: 'ETH/USDT', value: 'ETHUSDT' },
              ]}
            />
          </Col>
          <Col span={4}>
            <Button type="primary" onClick={runAnalysis} loading={loading} icon={<RobotOutlined />}>
              运行AI分析
            </Button>
          </Col>
        </Row>
      </Card>

      <Card title="分析结果">
        {result ? (
          <pre style={{ whiteSpace: 'pre-wrap', color: '#ffffffd9' }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        ) : (
          <Empty description="点击「运行AI分析」开始分析（需启用AI模块）" />
        )}
      </Card>
    </div>
  )
}
