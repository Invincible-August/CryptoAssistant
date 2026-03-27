import { useState, useEffect } from 'react'
import { Typography, Card, Switch, List, Tag, message } from 'antd'
import { settingsApi } from '../../services/settings'

const moduleLabels: Record<string, string> = {
  ai: 'AI分析模块',
  tradingview: 'TradingView模块',
  execution: '执行辅助模块',
  backtest: '回测模块',
  exchange_binance: 'Binance交易所',
}

export default function Settings() {
  const [modules, setModules] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const fetchModules = async () => {
    setLoading(true)
    try {
      const res: any = await settingsApi.listModules()
      setModules(res?.data || [])
    } catch {
      // 管理员权限可能不足
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchModules() }, [])

  const toggleModule = async (moduleName: string, enabled: boolean) => {
    try {
      await settingsApi.updateModule(moduleName, { enabled })
      message.success(`${moduleLabels[moduleName] || moduleName} 已${enabled ? '启用' : '禁用'}`)
      fetchModules()
    } catch {
      message.error('更新失败')
    }
  }

  return (
    <div>
      <Typography.Title level={3}>系统设置</Typography.Title>
      <Card title="模块管理">
        <List
          loading={loading}
          dataSource={modules}
          renderItem={(item: any) => (
            <List.Item
              actions={[
                <Switch
                  checked={item.enabled}
                  onChange={(checked) => toggleModule(item.module_name, checked)}
                />,
              ]}
            >
              <List.Item.Meta
                title={moduleLabels[item.module_name] || item.module_name}
                description={
                  <Tag color={item.enabled ? 'green' : 'default'}>
                    {item.enabled ? '已启用' : '未启用'}
                  </Tag>
                }
              />
            </List.Item>
          )}
        />
      </Card>
    </div>
  )
}
