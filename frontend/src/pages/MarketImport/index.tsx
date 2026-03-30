import { useEffect, useState, useCallback } from 'react'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import {
  Typography,
  Card,
  Form,
  Input,
  Select,
  DatePicker,
  Button,
  Row,
  Col,
  Progress,
  Tag,
  Alert,
  Descriptions,
  Space,
  message,
  Spin,
} from 'antd'
import {
  marketImportApi,
  type MarketImportTaskData,
} from '../../services/marketImport'

const { RangePicker } = DatePicker

const IMPORT_TYPE_OPTIONS = [
  { label: 'K线 (kline)', value: 'kline' },
  { label: '聚合成交 (trades)', value: 'trades' },
  { label: '订单簿 (orderbook)', value: 'orderbook' },
  { label: '资金费率 (funding_rate)', value: 'funding_rate' },
  { label: '持仓量 (open_interest)', value: 'open_interest' },
]

const POLL_MS = 2000

/**
 * Convert a calendar date range to UTC ISO strings (inclusive end-of-day for `end`).
 */
function buildUtcIsoRange(start: Dayjs, end: Dayjs): { start_date: string; end_date: string } {
  const start_date = `${start.format('YYYY-MM-DD')}T00:00:00.000Z`
  const end_date = `${end.format('YYYY-MM-DD')}T23:59:59.999Z`
  return { start_date, end_date }
}

function statusTag(status: MarketImportTaskData['status']) {
  const map: Record<MarketImportTaskData['status'], { color: string; text: string }> = {
    pending: { color: 'default', text: '等待中' },
    running: { color: 'processing', text: '运行中' },
    completed: { color: 'success', text: '已完成' },
    failed: { color: 'error', text: '失败' },
  }
  const x = map[status]
  return <Tag color={x.color}>{x.text}</Tag>
}

export default function MarketImport() {
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)
  const [activeTaskId, setActiveTaskId] = useState<number | null>(null)
  const [task, setTask] = useState<MarketImportTaskData | null>(null)

  const fetchTask = useCallback(async (taskId: number) => {
    const res: { data?: MarketImportTaskData } = await marketImportApi.getTask(taskId)
    const data = res?.data
    if (data) setTask(data)
    return data
  }, [])

  useEffect(() => {
    if (activeTaskId == null) return

    let timer: ReturnType<typeof setInterval> | undefined

    const poll = async () => {
      try {
        const data = await fetchTask(activeTaskId)
        if (!data) return
        if (data.status === 'completed' || data.status === 'failed') {
          if (timer) clearInterval(timer)
          timer = undefined
        }
      } catch {
        if (timer) clearInterval(timer)
      }
    }

    poll()
    timer = setInterval(poll, POLL_MS)
    return () => {
      if (timer) clearInterval(timer)
    }
  }, [activeTaskId, fetchTask])

  const onFinish = async (values: {
    name?: string
    exchange: string
    market_type: string
    symbol: string
    timeframe: string
    dateRange: [Dayjs, Dayjs]
    import_types: string[]
  }) => {
    const [start, end] = values.dateRange || []
    if (!start || !end) {
      message.warning('请选择导入时间范围')
      return
    }
    if (!values.import_types?.length) {
      message.warning('请至少选择一种导入类型')
      return
    }

    const { start_date, end_date } = buildUtcIsoRange(start, end)

    setSubmitting(true)
    try {
      const res: { data?: { task_id?: number } } = await marketImportApi.create({
        name: values.name,
        exchange: values.exchange,
        market_type: values.market_type,
        symbol: values.symbol,
        timeframe: values.timeframe,
        start_date,
        end_date,
        import_types: values.import_types,
      })
      const taskId = res?.data?.task_id
      if (taskId == null) {
        message.error('未返回任务 ID')
        return
      }
      setActiveTaskId(taskId)
      setTask(null)
      message.success('任务已创建')
      await fetchTask(taskId)
    } catch {
      message.error('创建任务失败')
    } finally {
      setSubmitting(false)
    }
  }

  const summary = task?.result_json?.summary
  const typeResults = task?.result_json?.type_results
  const errors = task?.result_json?.errors

  return (
    <div>
      <Typography.Title level={3}>导入行情</Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
        从交易所拉取历史行情数据到本地数据库。创建任务后约每 {POLL_MS / 1000} 秒自动刷新进度。
      </Typography.Paragraph>

      <Card title="新建导入任务" style={{ marginBottom: 16 }}>
        <Form
          form={form}
          layout="vertical"
          onFinish={onFinish}
          initialValues={{
            exchange: 'binance',
            symbol: 'BTCUSDT',
            market_type: 'spot',
            timeframe: '1h',
            import_types: ['kline'],
            dateRange: [dayjs().subtract(7, 'day'), dayjs()],
          }}
        >
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item label="任务名称（可选）" name="name">
                <Input placeholder="例如：BTC 现货 K 线回补" allowClear />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item label="交易所" name="exchange" rules={[{ required: true }]}>
                <Input readOnly placeholder="binance" />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item label="交易对" name="symbol" rules={[{ required: true }]}>
                <Input placeholder="BTCUSDT" />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item label="市场类型" name="market_type" rules={[{ required: true }]}>
                <Select
                  options={[
                    { label: '现货', value: 'spot' },
                    { label: '合约', value: 'futures' },
                  ]}
                />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item label="K 线周期" name="timeframe" rules={[{ required: true }]}>
                <Select
                  options={[
                    { label: '1 小时', value: '1h' },
                    { label: '4 小时', value: '4h' },
                    { label: '1 天', value: '1d' },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="时间范围（UTC 日界线）"
                name="dateRange"
                rules={[{ required: true, message: '请选择时间范围' }]}
              >
                <RangePicker style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={24}>
              <Form.Item
                label="导入类型（多选）"
                name="import_types"
                rules={[{ required: true, message: '至少选择一项' }]}
              >
                <Select
                  mode="multiple"
                  placeholder="选择要导入的数据类型"
                  options={IMPORT_TYPE_OPTIONS}
                  optionFilterProp="label"
                />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={submitting} size="large">
              创建导入任务
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {activeTaskId != null && (
        <Card title="任务进度">
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Alert
              type="info"
              showIcon
              message={
                <span>
                  任务 ID：<Typography.Text code>{activeTaskId}</Typography.Text>
                </span>
              }
            />

            {!task && (
              <div style={{ textAlign: 'center', padding: 24 }}>
                <Spin tip="加载任务状态…" />
              </div>
            )}

            {task && (
              <>
                <div>
                  <Space wrap>
                    <span>状态</span>
                    {statusTag(task.status)}
                    {task.last_error && task.status === 'failed' && (
                      <Typography.Text type="danger">{task.last_error}</Typography.Text>
                    )}
                  </Space>
                </div>
                <Progress
                  percent={Math.round((task.progress ?? 0) * 100)}
                  status={task.status === 'failed' ? 'exception' : 'active'}
                />

                {task.status === 'completed' && summary && (
                  <Descriptions bordered size="small" column={1}>
                    <Descriptions.Item label="总行数 (rows_total)">
                      {summary.rows_total ?? '—'}
                    </Descriptions.Item>
                    <Descriptions.Item label="请求的类型">
                      {(summary.import_types_requested ?? []).join(', ') || '—'}
                    </Descriptions.Item>
                    <Descriptions.Item label="已完成的类型">
                      {(summary.import_types_completed ?? []).join(', ') || '—'}
                    </Descriptions.Item>
                  </Descriptions>
                )}

                {task.status === 'completed' && typeResults && Object.keys(typeResults).length > 0 && (
                  <Card type="inner" title="各类型结果 (type_results)">
                    <pre
                      style={{
                        margin: 0,
                        maxHeight: 360,
                        overflow: 'auto',
                        fontSize: 12,
                        background: '#141414',
                        padding: 12,
                        borderRadius: 6,
                      }}
                    >
                      {JSON.stringify(typeResults, null, 2)}
                    </pre>
                  </Card>
                )}

                {errors != null && Array.isArray(errors) && errors.length > 0 && (
                  <Alert
                    type="warning"
                    showIcon
                    message="导入过程中的错误"
                    description={
                      <pre
                        style={{
                          margin: 0,
                          whiteSpace: 'pre-wrap',
                          fontSize: 12,
                        }}
                      >
                        {JSON.stringify(errors, null, 2)}
                      </pre>
                    }
                  />
                )}
              </>
            )}
          </Space>
        </Card>
      )}
    </div>
  )
}
