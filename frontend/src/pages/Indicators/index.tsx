import { useState, useEffect } from 'react'
import { Typography, Table, Tag, Button, message } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { indicatorApi } from '../../services/indicators'

export default function Indicators() {
  const [indicators, setIndicators] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const fetchIndicators = async () => {
    setLoading(true)
    try {
      const res: any = await indicatorApi.list()
      setIndicators(res?.data || [])
    } catch {
      message.error('获取指标列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchIndicators() }, [])

  const sourceColor: Record<string, string> = {
    system: 'blue', human: 'green', ai: 'purple',
  }

  const columns = [
    { title: '标识', dataIndex: 'indicator_key', key: 'indicator_key', width: 150 },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '分类', dataIndex: 'category', key: 'category' },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      render: (s: string) => <Tag color={sourceColor[s] || 'default'}>{s}</Tag>,
    },
    { title: '版本', dataIndex: 'version', key: 'version' },
    {
      title: '图表', dataIndex: 'chart_compatible', key: 'chart',
      render: (v: boolean) => v ? <Tag color="green">支持</Tag> : <Tag>不支持</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: any) => (
        <Button size="small" type="link">计算</Button>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={3}>技术指标管理</Typography.Title>
        <Button icon={<ReloadOutlined />} onClick={fetchIndicators}>刷新</Button>
      </div>
      <Table columns={columns} dataSource={indicators} rowKey="indicator_key" loading={loading} />
    </div>
  )
}
