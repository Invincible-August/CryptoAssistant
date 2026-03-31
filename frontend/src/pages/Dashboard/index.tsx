import { Card, Col, Row, Statistic, Typography, List, Tag } from 'antd'
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  MonitorOutlined,
  FundOutlined,
  RobotOutlined,
  RocketOutlined,
} from '@ant-design/icons'

export default function Dashboard() {
  return (
    <div>
      <Typography.Title level={3}>仪表盘</Typography.Title>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="监控交易对"
              value={3}
              prefix={<MonitorOutlined />}
              suffix="个"
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="已注册指标"
              value={6}
              prefix={<FundOutlined />}
              suffix="个"
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="回测任务"
              value={0}
              prefix={<RocketOutlined />}
              suffix="个"
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="AI分析"
              value={0}
              prefix={<RobotOutlined />}
              suffix="次"
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="系统状态">
            <List
              size="small"
              dataSource={[
                { label: '后端服务', status: '运行中', color: 'green' },
                { label: 'PostgreSQL', status: '已连接', color: 'green' },
                { label: 'Redis', status: '已连接', color: 'green' },
                { label: 'AI模块', status: '未启用', color: 'default' },
              ]}
              renderItem={(item: any) => (
                <List.Item>
                  <span>{item.label}</span>
                  <Tag color={item.color}>{item.status}</Tag>
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="快速操作">
            <List
              size="small"
              dataSource={[
                '查看实时监控 → /monitor',
                '分析图表 → /chart',
                '管理指标 → /indicators',
                '运行回测 → /backtest',
                '系统设置 → /settings',
              ]}
              renderItem={(item: string) => <List.Item>{item}</List.Item>}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
