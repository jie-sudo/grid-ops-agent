import { useState } from 'react';
import { Card, Form, Input, Button, message, Space, Typography } from 'antd';
import { ThunderboltOutlined, UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { login, saveAuth } from '@/api';
import { useAppStore } from '@/store/app';
import { DEMO_ACCOUNTS } from '@/config';

export function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const setUser = useAppStore((s) => s.setUser);

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const data = await login(values.username, values.password);
      saveAuth(data.token, { user_id: data.user_id, role: data.role });
      setUser({ user_id: data.user_id, role: data.role, name: data.user_id });
      message.success('登录成功');
      navigate('/workbench');
    } catch (e) {
      message.error((e as Error).message || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg,#0f2440,#16324f)',
      }}
    >
      <Card style={{ width: 380, boxShadow: '0 18px 46px rgba(0,0,0,.3)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ fontSize: 28, color: '#2563eb' }}>
            <ThunderboltOutlined />
          </div>
          <Typography.Title level={4} style={{ margin: '12px 0 4px' }}>
            电网智能运维助手
          </Typography.Title>
          <Typography.Text type="secondary">智能问答 · 缺陷诊断 · 工单管理</Typography.Text>
        </div>
        <Form form={form} onFinish={onFinish} initialValues={{ username: 'admin', password: 'admin123' }} size="large">
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={loading}>
              登 录
            </Button>
          </Form.Item>
        </Form>
        <div style={{ marginTop: 8 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            演示账号（点击快速填充）：
          </Typography.Text>
          <Space wrap style={{ marginTop: 8 }}>
            {DEMO_ACCOUNTS.map((acc) => (
              <Button
                key={acc.username}
                size="small"
                onClick={() => form.setFieldsValue({ username: acc.username, password: acc.password })}
              >
                {acc.label}
              </Button>
            ))}
          </Space>
        </div>
      </Card>
    </div>
  );
}
