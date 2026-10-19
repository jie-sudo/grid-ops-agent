import { Card, Row, Col, Badge, Typography, Statistic } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api';
import { PageTitle } from '@/components/common';
import type { HealthData } from '@/types';

const DEP_NAMES: Record<string, string> = {
  postgres: 'PostgreSQL',
  chromadb: 'ChromaDB',
  redis: 'Redis',
};

export function HealthPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.getHealth(),
    refetchInterval: 10000,
  });

  const health = data as HealthData | undefined;
  const deps = health?.dependencies ?? {};

  return (
    <div>
      <PageTitle>系统健康</PageTitle>
      <Row gutter={16}>
        {Object.entries(deps).map(([k, v]) => (
          <Col span={8} key={k}>
            <Card size="small" loading={isLoading}>
              <Statistic
                title={DEP_NAMES[k] ?? k}
                value={v === 'ok' ? '健康' : '异常'}
                valueStyle={{ color: v === 'ok' ? '#16803c' : '#c2410c' }}
                prefix={<Badge status={v === 'ok' ? 'success' : 'error'} />}
              />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {v === 'ok' ? '连接正常' : '连接失败，请检查服务'}
              </Typography.Text>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}
