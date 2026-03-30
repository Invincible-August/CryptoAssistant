import { useState, useEffect } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Avatar, Dropdown, Typography } from 'antd'
import {
  DashboardOutlined,
  MonitorOutlined,
  LineChartOutlined,
  ImportOutlined,
  FundOutlined,
  ExperimentOutlined,
  RocketOutlined,
  RobotOutlined,
  SettingOutlined,
  FileTextOutlined,
  UserOutlined,
  LogoutOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '../store/auth'
import { authApi } from '../services/auth'

const { Header, Sider, Content } = Layout

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/monitor', icon: <MonitorOutlined />, label: '实时监控' },
  { key: '/chart', icon: <LineChartOutlined />, label: '图表分析' },
  { key: '/market-import', icon: <ImportOutlined />, label: '导入行情' },
  { key: '/indicators', icon: <FundOutlined />, label: '技术指标' },
  { key: '/factors', icon: <ExperimentOutlined />, label: '量化因子' },
  { key: '/backtest', icon: <RocketOutlined />, label: '策略回测' },
  { key: '/ai', icon: <RobotOutlined />, label: 'AI分析' },
  { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
  { key: '/logs', icon: <FileTextOutlined />, label: '系统日志' },
]

export default function BasicLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { user, setUser, logout } = useAuthStore()

  useEffect(() => {
    if (!user) {
      authApi.getMe().then((res: any) => {
        if (res?.data) setUser(res.data)
      }).catch(() => {})
    }
  }, [])

  const userMenu = {
    items: [
      {
        key: 'logout',
        icon: <LogoutOutlined />,
        label: '退出登录',
        onClick: () => {
          logout()
          navigate('/login')
        },
      },
    ],
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
        style={{ background: '#141414' }}
      >
        <div
          style={{
            height: 48,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '16px 0',
          }}
        >
          <Typography.Title
            level={4}
            style={{ color: '#1677ff', margin: 0, whiteSpace: 'nowrap' }}
          >
            {collapsed ? 'CA' : 'CryptoAssistant'}
          </Typography.Title>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ background: 'transparent' }}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: '#1f1f1f',
            padding: '0 24px',
            display: 'flex',
            justifyContent: 'flex-end',
            alignItems: 'center',
          }}
        >
          <Dropdown menu={userMenu} placement="bottomRight">
            <div style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Avatar icon={<UserOutlined />} />
              <span>{user?.username || '用户'}</span>
            </div>
          </Dropdown>
        </Header>
        <Content style={{ margin: 16, padding: 24, background: '#1f1f1f', borderRadius: 8 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
