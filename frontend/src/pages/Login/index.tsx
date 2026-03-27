import { useState } from 'react'
import { Card, Form, Input, Button, Typography, message } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../../services/auth'
import { useAuthStore } from '../../store/auth'

export default function Login() {
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const { setToken, setUser } = useAuthStore()

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      const res: any = await authApi.login(values.username, values.password)
      const token = res?.data?.access_token
      if (token) {
        setToken(token)
        const userRes: any = await authApi.getMe()
        if (userRes?.data) setUser(userRes.data)
        message.success('登录成功')
        navigate('/')
      }
    } catch {
      message.error('登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card
      style={{
        width: 400,
        background: '#1f1f1f',
        border: '1px solid #303030',
        borderRadius: 12,
      }}
    >
      <div style={{ textAlign: 'center', marginBottom: 32 }}>
        <Typography.Title level={2} style={{ color: '#1677ff', margin: 0 }}>
          CryptoAssistant
        </Typography.Title>
        <Typography.Text type="secondary">
          加密货币交易辅助系统
        </Typography.Text>
      </div>
      <Form onFinish={onFinish} size="large">
        <Form.Item
          name="username"
          rules={[{ required: true, message: '请输入用户名' }]}
        >
          <Input prefix={<UserOutlined />} placeholder="用户名" />
        </Form.Item>
        <Form.Item
          name="password"
          rules={[{ required: true, message: '请输入密码' }]}
        >
          <Input.Password prefix={<LockOutlined />} placeholder="密码" />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" block loading={loading}>
            登录
          </Button>
        </Form.Item>
      </Form>
    </Card>
  )
}
