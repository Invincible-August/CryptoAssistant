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
  Space,
  Popconfirm,
} from 'antd'
import { ReloadOutlined, CalculatorOutlined } from '@ant-design/icons'
import { factorApi } from '../../services/factors'
import { useAuthStore } from '../../store/auth'

export default function Factors() {
  const [factors, setFactors] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [calcOpen, setCalcOpen] = useState(false)
  const [calcRow, setCalcRow] = useState<any>(null)
  const [calcLoading, setCalcLoading] = useState(false)
  const [form] = Form.useForm()
  const user = useAuthStore((s) => s.user)
  const isAdmin = user?.role === 'admin'

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

  useEffect(() => {
    fetchFactors()
  }, [])

  const openCalculate = (record: any) => {
    setCalcRow(record)
    form.setFieldsValue({
      symbol: 'BTCUSDT',
      exchange: 'binance',
      market_type: 'spot',
      timeframe: '1h',
    })
    setCalcOpen(true)
  }

  const submitCalculate = async () => {
    if (!calcRow) return
    try {
      const v = await form.validateFields()
      setCalcLoading(true)
      const res: any = await factorApi.calculate({
        factor_key: calcRow.factor_key,
        symbol: v.symbol,
        exchange: v.exchange,
        market_type: v.market_type,
        timeframe: v.timeframe,
      })
      message.success(`计算完成: score=${res?.data?.result?.score ?? '—'}`)
      setCalcOpen(false)
    } catch {
      /* validation or API */
    } finally {
      setCalcLoading(false)
    }
  }

  const toggleLoad = async (record: any, load_enabled: boolean) => {
    try {
      await factorApi.setLoadEnabled(record.factor_key, load_enabled)
      message.success(load_enabled ? '已恢复加载' : '已设为不加载')
      fetchFactors()
    } catch {
      message.error('更新失败（需管理员权限）')
    }
  }

  const columns = [
    { title: '标识', dataIndex: 'factor_key', key: 'factor_key', width: 200 },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '分类', dataIndex: 'category', key: 'category' },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      render: (s: string) => (
        <Tag color={s === 'system' ? 'blue' : s === 'human' ? 'green' : 'purple'}>
          {s}
        </Tag>
      ),
    },
    {
      title: '加载',
      dataIndex: 'load_enabled',
      key: 'load_enabled',
      render: (enabled: boolean) =>
        enabled ? (
          <Tag color="green">加载</Tag>
        ) : (
          <Tag color="default">不加载</Tag>
        ),
    },
    { title: '权重', dataIndex: 'score_weight', key: 'score_weight' },
    {
      title: '操作',
      key: 'action',
      width: 280,
      render: (_: unknown, record: any) => (
        <Space size="small" wrap>
          <Button
            size="small"
            type="link"
            icon={<CalculatorOutlined />}
            disabled={record.load_enabled === false}
            onClick={() => openCalculate(record)}
          >
            计算
          </Button>
          {isAdmin && record.load_enabled && (
            <Popconfirm
              title="该因子将不参与计算与管线，确认禁用？"
              onConfirm={() => toggleLoad(record, false)}
            >
              <Button size="small" type="link" danger>
                不加载
              </Button>
            </Popconfirm>
          )}
          {isAdmin && record.load_enabled === false && (
            <Button
              size="small"
              type="link"
              onClick={() => toggleLoad(record, true)}
            >
              恢复
            </Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: 16,
        }}
      >
        <Typography.Title level={3}>量化因子管理</Typography.Title>
        <Button icon={<ReloadOutlined />} onClick={fetchFactors}>
          刷新列表
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={factors}
        rowKey="factor_key"
        loading={loading}
      />

      <Modal
        title={calcRow ? `计算因子：${calcRow.factor_key}` : '计算因子'}
        open={calcOpen}
        onCancel={() => setCalcOpen(false)}
        onOk={submitCalculate}
        confirmLoading={calcLoading}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="symbol" label="交易对" rules={[{ required: true }]}>
            <Input placeholder="BTCUSDT" />
          </Form.Item>
          <Form.Item name="exchange" label="交易所">
            <Select options={[{ label: 'binance', value: 'binance' }]} />
          </Form.Item>
          <Form.Item name="market_type" label="市场类型">
            <Select
              options={[
                { label: 'spot', value: 'spot' },
                { label: 'futures', value: 'futures' },
              ]}
            />
          </Form.Item>
          <Form.Item name="timeframe" label="周期">
            <Select
              options={[
                { label: '1h', value: '1h' },
                { label: '4h', value: '4h' },
                { label: '1d', value: '1d' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
