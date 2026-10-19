import { useEffect, useState } from 'react';
import { Card, Timeline, Input, Button, Space, Tag, Collapse, Empty, Typography, Descriptions, Alert } from 'antd';
import { ClockCircleOutlined } from '@ant-design/icons';
import { useSearchParams } from 'react-router-dom';
import { api } from '@/api';
import { PageTitle } from '@/components/common';
import { useAppStore } from '@/store/app';
import { canView } from '@/utils/permissions';
import type { Session, TraceStep } from '@/types';

export function RunsPage() {
  const user = useAppStore((s) => s.user);
  const [params, setParams] = useSearchParams();
  const [sid, setSid] = useState(params.get('session_id') ?? '');
  const [query, setQuery] = useState(params.get('session_id') ?? '');
  const [trace, setTrace] = useState<TraceStep[] | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const allowed = canView(user?.role, 'runs');

  const loadSessions = async () => {
    try {
      const s = await api.listSessions();
      setSessions(s as Session[]);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  const loadTrace = async (id: string) => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const t = await api.getTrace(id);
      setTrace(t as TraceStep[]);
      setParams({ session_id: id });
      setSid(id);
    } catch (e) {
      setError((e as Error).message);
      setTrace(null);
    } finally {
      setLoading(false);
    }
  };

  if (!allowed) {
    return (
      <div>
        <PageTitle>运行链路</PageTitle>
        <Alert type="warning" showIcon message="运行链路需要 admin 权限查看，当前角色无权限。" />
      </div>
    );
  }

  const totalMs = trace?.reduce((acc, t) => acc + t.elapsed_ms, 0) ?? 0;

  return (
    <div>
      <PageTitle>运行链路</PageTitle>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space>
          <Input
            style={{ width: 320 }}
            placeholder="输入 session_id（如 skx1a2b3c）"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onPressEnter={() => loadTrace(query)}
          />
          <Button type="primary" onClick={() => loadTrace(query)} loading={loading}>
            查询
          </Button>
        </Space>
        {sessions.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              历史会话（点击填入）：
            </Typography.Text>
            <div style={{ marginTop: 6 }}>
              {sessions.map((s) => (
                <Tag
                  key={s.session_id}
                  color="blue"
                  style={{ cursor: 'pointer' }}
                  onClick={() => {
                    setQuery(s.session_id);
                    loadTrace(s.session_id);
                  }}
                >
                  {s.session_id}
                  {s.intent ? ` · ${s.intent}` : ''}
                </Tag>
              ))}
            </div>
          </div>
        )}
      </Card>

      {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}

      {trace === null && !error && <Empty description="输入 session_id 查询运行链路" />}

      {trace && (
        <Card size="small">
          <Descriptions size="small" column={3} style={{ marginBottom: 16 }}>
            <Descriptions.Item label="会话">{sid}</Descriptions.Item>
            <Descriptions.Item label="总步骤">{trace.length}</Descriptions.Item>
            <Descriptions.Item label="总耗时">{totalMs}ms</Descriptions.Item>
          </Descriptions>
          <Timeline
            items={trace.map((t) => ({
              color: t.degraded ? 'orange' : 'blue',
              dot: t.degraded ? <ClockCircleOutlined /> : undefined,
              children: (
                <div>
                  <Space>
                    <Tag color="blue">步骤 {t.step}</Tag>
                    <Typography.Text code>{t.tool}</Typography.Text>
                    {t.degraded ? <Tag color="orange">降级</Tag> : <Tag color="green">正常</Tag>}
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {t.elapsed_ms}ms
                    </Typography.Text>
                  </Space>
                  <Collapse
                    size="small"
                    ghost
                    style={{ marginTop: 4 }}
                    items={[
                      {
                        key: 'params',
                        label: '参数',
                        children: <pre style={{ margin: 0, fontSize: 12 }}>{JSON.stringify(t.params, null, 2)}</pre>,
                      },
                      {
                        key: 'result',
                        label: '结果',
                        children: <pre style={{ margin: 0, fontSize: 12 }}>{JSON.stringify(t.result, null, 2)}</pre>,
                      },
                      ...(t.sources?.length
                        ? [
                            {
                              key: 'sources',
                              label: '来源',
                              children: <div>{t.sources.join('；')}</div>,
                            },
                          ]
                        : []),
                    ]}
                  />
                </div>
              ),
            }))}
          />
        </Card>
      )}
    </div>
  );
}
