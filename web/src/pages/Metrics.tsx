import { Card, Row, Col, Statistic, Table, Alert, Typography } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api';
import { PageTitle } from '@/components/common';
import { useAppStore } from '@/store/app';
import { canView } from '@/utils/permissions';

interface MetricItem {
  name: string;
  value: number | string;
  label?: string;
}

export function MetricsPage() {
  const user = useAppStore((s) => s.user);
  const allowed = canView(user?.role, 'metrics');

  const { data } = useQuery({
    queryKey: ['metrics'],
    queryFn: () => api.getMetrics(),
    enabled: allowed,
  });

  if (!allowed) {
    return (
      <div>
        <PageTitle>运行指标</PageTitle>
        <Alert type="warning" showIcon message="运行指标需要 admin 权限查看，当前角色无权限。" />
      </div>
    );
  }

  const summary = (data as { summary?: MetricItem[] })?.summary ?? [];
  const runs = (data as { runs?: Record<string, unknown>[] })?.runs ?? [];

  return (
    <div>
      <PageTitle>运行指标</PageTitle>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        {summary.map((m) => (
          <Col span={Math.floor(24 / Math.max(summary.length, 1)) < 4 ? 4 : 6} key={m.name} style={{ marginBottom: 16 }}>
            <Card size="small">
              <Statistic title={m.name} value={m.value} />
              {m.label && (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {m.label}
                </Typography.Text>
              )}
            </Card>
          </Col>
        ))}
      </Row>
      <Card size="small" title="历史评测运行">
        <Table
          size="small"
          rowKey={(r) => r.id as string}
          dataSource={runs as Record<string, unknown>[]}
          pagination={false}
          columns={[
            { title: '运行 ID', dataIndex: 'id', render: (v) => <Typography.Text code>{v as string}</Typography.Text> },
            { title: '评测套件', dataIndex: 'suite' },
            { title: '时间', dataIndex: 'ts' },
            { title: '结果', dataIndex: 'result' },
            { title: '样本数', dataIndex: 'samples' },
          ]}
        />
      </Card>
    </div>
  );
}
