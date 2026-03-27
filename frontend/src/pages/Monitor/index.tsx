import { useState, useEffect } from 'react'
import {
  Typography,
  Table,
  Tag,
  Button,
  message,
  Modal,
  Form,
  Input,
  Select,
  Popconfirm,
  Space,
} from 'antd'
import { PlusOutlined, ReloadOutlined, DeleteOutlined } from '@ant-design/icons'
import { monitorApi, type MonitorWatch } from '@/services/monitor.ts'

export default function Monitor() {
  const [watches, setWatches] = useState<MonitorWatch[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [form] = Form.useForm()

  const fetchWatches = async () => {
    setLoading(true)
    try {
      const res = await monitorApi.listWatches()
      setWatches((res?.data as MonitorWatch[]) || [])
    } catch {
      message.error('获取监控列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleAddWatch = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)
      await monitorApi.addWatch({
        exchange: values.exchange,
        symbol: values.symbol.toUpperCase().trim(),
        market_type: values.market_type,
        event_type: values.event_type,
      })
      message.success('监控添加成功')
      setModalOpen(false)
      form.resetFields()
      await fetchWatches()
    } catch (error) {
      if (error instanceof Error && error.message) {
        message.error(error.message)
      }
    } finally {
      setSubmitting(false)
    }
  }

  const handleDeleteWatch = async (watchId: number) => {
    try {
      await monitorApi.deleteWatch(watchId)
      message.success('监控已删除')
      await fetchWatches()
    } catch {
      message.error('删除监控失败')
    }
  }

  useEffect(() => { fetchWatches() }, [])

  const columns = [
    { title: '交易对', dataIndex: 'symbol', key: 'symbol' },
    { title: '交易所', dataIndex: 'exchange', key: 'exchange' },
    { title: '市场类型', dataIndex: 'market_type', key: 'market_type' },
    {
      title: '状态',
      dataIndex: 'watch_status',
      key: 'watch_status',
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'default'}>
          {status === 'active' ? '监控中' : status}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, row: MonitorWatch) => (
        <Popconfirm
          title="确认删除该监控吗？"
          onConfirm={() => handleDeleteWatch(row.id)}
          okText="删除"
          cancelText="取消"
        >
          <Button danger type="text" icon={<DeleteOutlined />}>
            删除
          </Button>
        </Popconfirm>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={3}>实时监控</Typography.Title>
        <div>
          <Button icon={<ReloadOutlined />} onClick={fetchWatches} style={{ marginRight: 8 }}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            添加监控
          </Button>
        </div>
      </div>
      <Table
        columns={columns}
        dataSource={watches}
        rowKey="id"
        loading={loading}
        pagination={false}
      />

      <Modal
        title="添加监控币对"
        open={modalOpen}
        onCancel={() => {
          setModalOpen(false)
          form.resetFields()
        }}
        onOk={handleAddWatch}
        confirmLoading={submitting}
        okText="确认添加"
        cancelText="取消"
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            exchange: 'binance',
            market_type: 'spot',
            event_type: 'all',
          }}
        >
          <Form.Item
            label="交易所"
            name="exchange"
            rules={[{ required: true, message: '请选择交易所' }]}
          >
            <Select
              options={[
                { label: 'Binance', value: 'binance' },
              ]}
            />
          </Form.Item>

          <Form.Item
            label="交易对"
            name="symbol"
            rules={[
              { required: true, message: '请输入交易对，如 BTCUSDT' },
              { min: 6, message: '交易对格式不正确' },
            ]}
          >
            <Input placeholder="例如：BTCUSDT" />
          </Form.Item>

          <Space style={{ width: '100%' }} size={12}>
            <Form.Item
              label="市场类型"
              name="market_type"
              style={{ flex: 1 }}
              rules={[{ required: true, message: '请选择市场类型' }]}
            >
              <Select
                options={[
                  { label: '现货 (spot)', value: 'spot' },
                  { label: '合约 (perp)', value: 'perp' },
                ]}
              />
            </Form.Item>

            <Form.Item
              label="事件类型"
              name="event_type"
              style={{ flex: 1 }}
              rules={[{ required: true, message: '请选择事件类型' }]}
            >
              <Select
                options={[
                  { label: '全部 (all)', value: 'all' },
                  { label: 'K线 (kline)', value: 'kline' },
                  { label: '成交 (trade)', value: 'trade' },
                  { label: '深度 (depth)', value: 'depth' },
                  { label: '资金费率 (funding)', value: 'funding' },
                ]}
              />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </div>
  )
}
