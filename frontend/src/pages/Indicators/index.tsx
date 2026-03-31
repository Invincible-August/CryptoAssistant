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
import {
  ReloadOutlined,
  CalculatorOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { indicatorApi } from '../../services/indicators'
import { adminApi } from '../../services/admin'
import { useAuthStore } from '../../store/auth'

export default function Indicators() {
  const [indicators, setIndicators] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [reloadLoading, setReloadLoading] = useState(false)
  const [calcOpen, setCalcOpen] = useState(false)
  const [calcRow, setCalcRow] = useState<any>(null)
  const [calcLoading, setCalcLoading] = useState(false)
  const [form] = Form.useForm()
  const user = useAuthStore((s) => s.user)
  const isAdmin = user?.role === 'admin'

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

  useEffect(() => {
    fetchIndicators()
  }, [])

  const hotReload = async () => {
    setReloadLoading(true)
    try {
      await adminApi.reloadPlugins()
      message.success('插件已重载')
      await fetchIndicators()
    } catch {
      message.error('重载失败（需管理员且后端允许 PLUGIN_HOT_RELOAD）')
    } finally {
      setReloadLoading(false)
    }
  }

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
      await indicatorApi.calculate({
        indicator_key: calcRow.indicator_key,
        symbol: v.symbol,
        exchange: v.exchange,
        market_type: v.market_type,
        timeframe: v.timeframe,
      })
      message.success('指标计算完成')
      setCalcOpen(false)
    } catch {
      /* validation or API */
    } finally {
      setCalcLoading(false)
    }
  }

  const toggleLoad = async (record: any, load_enabled: boolean) => {
    try {
      await indicatorApi.setLoadEnabled(record.indicator_key, load_enabled)
      message.success(load_enabled ? '已恢复加载' : '已设为不加载')
      fetchIndicators()
    } catch {
      message.error('更新失败（需管理员权限）')
    }
  }

  const sourceColor: Record<string, string> = {
    system: 'blue',
    human: 'green',
    ai: 'purple',
  }

  const columns = [
    { title: '标识', dataIndex: 'indicator_key', key: 'indicator_key', width: 150 },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '分类', dataIndex: 'category', key: 'category' },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      render: (s: string) => (
        <Tag color={sourceColor[s] || 'default'}>{s}</Tag>
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
    { title: '版本', dataIndex: 'version', key: 'version' },
    {
      title: '图表',
      dataIndex: 'chart_compatible',
      key: 'chart',
      render: (v: boolean) =>
        v ? <Tag color="green">支持</Tag> : <Tag>不支持</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 300,
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
              title="该指标将不参与计算与管线，确认禁用？"
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
          flexWrap: 'wrap',
          gap: 8,
        }}
      >
        <Typography.Title level={3}>技术指标管理</Typography.Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchIndicators}>
            刷新列表
          </Button>
          {isAdmin && (
            <Popconfirm
              title="将从磁盘重新加载 builtins/custom 下的指标与因子插件，确认？"
              onConfirm={hotReload}
            >
              <Button
                type="primary"
                ghost
                icon={<ThunderboltOutlined />}
                loading={reloadLoading}
              >
                重载插件
              </Button>
            </Popconfirm>
          )}
        </Space>
      </div>
      <Table
        columns={columns}
        dataSource={indicators}
        rowKey="indicator_key"
        loading={loading}
      />

      <Modal
        title={calcRow ? `计算指标：${calcRow.indicator_key}` : '计算指标'}
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
