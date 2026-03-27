import { useState, useEffect } from 'react'
import { Typography, Table, Tag, Button, message } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { factorApi } from '../../services/factors'

export default function Factors() {
  const [factors, setFactors] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const fetchFactors = async () => {
    setLoading(true)
    try {
      const res: any = await factorApi.list()
      setFactors(res?.data || [])
    } catch {
      message.error('获取因子列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchFactors() }, [])

  const columns = [
    { title: '标识', dataIndex: 'factor_key', key: 'factor_key', width: 200 },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '分类', dataIndex: 'category', key: 'category' },
    {
      title: '来源', dataIndex: 'source', key: 'source',
      render: (s: string) => (
        <Tag color={s === 'system' ? 'blue' : s === 'human' ? 'green' : 'purple'}>{s}</Tag>
      ),
    },
    { title: '权重', dataIndex: 'score_weight', key: 'score_weight' },
    {
      title: '操作', key: 'action',
      render: () => <Button size="small" type="link">计算</Button>,
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={3}>量化因子管理</Typography.Title>
        <Button icon={<ReloadOutlined />} onClick={fetchFactors}>刷新</Button>
      </div>
      <Table columns={columns} dataSource={factors} rowKey="factor_key" loading={loading} />
    </div>
  )
}
