import { useMemo } from 'react';
import { Layout, Menu, Tag, Dropdown, Badge } from 'antd';
import {
  ThunderboltOutlined,
  CommentOutlined,
  ClusterOutlined,
  AlertOutlined,
  BugOutlined,
  FileDoneOutlined,
  NodeIndexOutlined,
  BookOutlined,
  FundProjectionScreenOutlined,
  HeartOutlined,
  DashboardOutlined,
  ToolOutlined,
  SettingOutlined,
  LogoutOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/app';
import { clearAuth } from '@/api';
import { USE_MOCK } from '@/config';
import type { Role } from '@/types';

const { Sider, Header, Content } = Layout;

interface NavItem {
  key: string;
  label: string;
  icon: React.ReactNode;
  role?: Role[] | '*';
}

const NAV_ITEMS: NavItem[] = [
  { key: '/workbench', label: '对话工作台', icon: <CommentOutlined /> },
  { key: '/devices', label: '设备管理', icon: <ClusterOutlined /> },
  { key: '/alarms', label: '告警管理', icon: <AlertOutlined /> },
  { key: '/defects', label: '缺陷管理', icon: <BugOutlined /> },
  { key: '/workorders', label: '工单管理', icon: <FileDoneOutlined /> },
  { key: '/runs', label: '运行链路', icon: <NodeIndexOutlined />, role: ['admin'] },
  { key: '/knowledge', label: '知识库', icon: <BookOutlined /> },
  { key: '/review-cases', label: '复盘案例', icon: <FundProjectionScreenOutlined /> },
  { key: '/health', label: '系统健康', icon: <HeartOutlined /> },
  { key: '/metrics', label: '运行指标', icon: <DashboardOutlined />, role: ['admin'] },
  { key: '/tools', label: '工具注册', icon: <ToolOutlined /> },
  { key: '/settings', label: '设置', icon: <SettingOutlined /> },
];

const ROLE_LABEL: Record<Role, string> = {
  admin: '管理员',
  operator: '运维',
  monitor: '监控',
  manager: '管理',
};

const ROLE_COLOR: Record<Role, string> = {
  admin: 'gold',
  operator: 'blue',
  monitor: 'green',
  manager: 'purple',
};

export function AppShell() {
  const user = useAppStore((s) => s.user);
  const navigate = useNavigate();
  const location = useLocation();

  const role = user?.role;

  const items = useMemo(() => {
    return NAV_ITEMS.filter((it) => {
      if (it.role && it.role !== '*' && role && !it.role.includes(role)) return false;
      return true;
    }).map((it) => ({ key: it.key, icon: it.icon, label: it.label }));
  }, [role]);

  const selectedKey = '/' + (location.pathname.split('/')[1] || 'workbench');

  const handleLogout = () => {
    clearAuth();
    useAppStore.getState().setUser(null);
    navigate('/login');
  };

  return (
    <Layout style={{ height: '100vh' }}>
      <Sider width={220} style={{ background: '#0f2440' }} theme="dark">
        <div
          style={{
            height: 56,
            display: 'flex',
            alignItems: 'center',
            padding: '0 20px',
            color: '#fff',
            fontWeight: 600,
            fontSize: 15,
            gap: 8,
            borderBottom: '1px solid #1c3554',
          }}
        >
          <ThunderboltOutlined style={{ color: '#fff', fontSize: 18 }} />
          <span>电网智能运维助手</span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={items}
          onClick={({ key }) => navigate(key)}
          style={{ background: 'transparent', borderRight: 'none', marginTop: 8 }}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: '#fff',
            height: 56,
            lineHeight: '56px',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid var(--border)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Badge status={USE_MOCK ? 'warning' : 'success'} />
            <span style={{ color: 'var(--muted)' }}>
              {USE_MOCK ? '演示模式（模拟数据）' : '生产环境'}
            </span>
          </div>
          <div>
            {user && (
              <Dropdown
                menu={{
                  items: [{ key: 'logout', icon: <LogoutOutlined />, label: '退出登录', onClick: handleLogout }],
                }}
              >
                <span style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                  <Tag color={ROLE_COLOR[user.role]}>{ROLE_LABEL[user.role]}</Tag>
                  <UserOutlined />
                  <span>{user.user_id}</span>
                </span>
              </Dropdown>
            )}
          </div>
        </Header>
        <Content style={{ overflow: 'auto', padding: 20 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
