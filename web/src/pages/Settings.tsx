import { Card, Descriptions, Typography, Tag, Divider } from 'antd';
import { PageTitle } from '@/components/common';
import { useAppStore } from '@/store/app';
import { USE_MOCK } from '@/config';

const ROLE_LABEL: Record<string, string> = {
  admin: '管理员',
  operator: '运维',
  monitor: '监控',
  manager: '管理',
};

export function SettingsPage() {
  const user = useAppStore((s) => s.user);

  return (
    <div>
      <PageTitle>设置</PageTitle>
      <Card size="small" title="当前账户">
        <Descriptions column={1} bordered size="small">
          <Descriptions.Item label="用户 ID">{user?.user_id}</Descriptions.Item>
          <Descriptions.Item label="角色">
            <Tag color="blue">{user ? ROLE_LABEL[user.role] : '-'}</Tag>
          </Descriptions.Item>
        </Descriptions>
      </Card>
      <Card size="small" title="运行环境" style={{ marginTop: 16 }}>
        <Descriptions column={1} bordered size="small">
          <Descriptions.Item label="数据模式">
            {USE_MOCK ? <Tag color="orange">演示模式（模拟数据）</Tag> : <Tag color="green">生产（真实后端）</Tag>}
          </Descriptions.Item>
          <Descriptions.Item label="后端地址">http://localhost:8000/api/v1</Descriptions.Item>
        </Descriptions>
        <Divider />
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          切换真实后端：编辑 <Typography.Text code>src/config.ts</Typography.Text> 中 <Typography.Text code>USE_MOCK</Typography.Text> 为 <Typography.Text code>false</Typography.Text> 后重启开发服务。
        </Typography.Text>
      </Card>
    </div>
  );
}
