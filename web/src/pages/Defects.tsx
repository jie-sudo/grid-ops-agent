import { useState } from 'react';
import { Table, Card, Form, Input, Button, Result, Space, Alert, Typography, Row, Col, Tag } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api';
import { PageTitle, LevelTag } from '@/components/common';
import { useAppStore } from '@/store/app';
import { canDo, requiredLabel } from '@/utils/permissions';
import type { Defect } from '@/types';

export function DefectsPage() {
  const user = useAppStore((s) => s.user);
  const [evalResult, setEvalResult] = useState<{ level: string; reasons: string[]; degraded: boolean } | null>(null);
  const [form] = Form.useForm();

  const canEval = canDo(user?.role, 'evaluateDefect');

  const { data: defects, isLoading } = useQuery({
    queryKey: ['defects'],
    queryFn: () => api.listDefects(),
  });

  const onEvaluate = async (values: { description: string }) => {
    const r = await api.evaluateDefect(values.description);
    setEvalResult(r as { level: string; reasons: string[]; degraded: boolean });
  };

  return (
    <div>
      <PageTitle>缺陷管理</PageTitle>
      <Row gutter={16}>
        <Col span={16}>
          <Card title={`缺陷列表（${defects?.length ?? 0}）`} size="small">
            <Table<Defect>
              rowKey="defect_id"
              loading={isLoading}
              dataSource={defects as Defect[]}
              size="small"
              pagination={{ pageSize: 20 }}
              columns={[
                { title: '缺陷编号', dataIndex: 'defect_id', render: (v) => <Typography.Text code>{v}</Typography.Text> },
                { title: '设备', dataIndex: 'device_id', render: (v) => (v ? <Typography.Text code>{v}</Typography.Text> : '-') },
                { title: '描述', dataIndex: 'description', ellipsis: true },
                { title: '等级', dataIndex: 'level', render: (v) => <LevelTag level={v} /> },
                { title: '状态', dataIndex: 'status', render: (v) => v ?? '-' },
                { title: '来源', dataIndex: 'source', render: (v) => v ?? '-' },
              ]}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card title="缺陷分级评估" size="small">
            {!canEval && (
              <Alert
                style={{ marginBottom: 12 }}
                type="info"
                showIcon
                message={`当前角色无评估权限，需要 ${requiredLabel('evaluateDefect')} 权限`}
              />
            )}
            <Form form={form} layout="vertical" onFinish={onEvaluate}>
              <Form.Item name="description" label="缺陷描述" rules={[{ required: true, message: '请输入缺陷描述' }]}>
                <Input.TextArea rows={3} placeholder="如：套管闪络了" disabled={!canEval} />
              </Form.Item>
              <Button type="primary" htmlType="submit" block disabled={!canEval}>
                分级评估
              </Button>
            </Form>
            {evalResult && (
              <Result
                style={{ padding: '16px 0' }}
                status={evalResult.degraded ? 'warning' : 'success'}
                title={
                  <Space>
                    分级结果：
                    {evalResult.level ? <LevelTag level={evalResult.level} /> : <Tag>无法确定</Tag>}
                  </Space>
                }
                subTitle={
                  <div>
                    {evalResult.reasons.map((r, i) => (
                      <div key={i}>· {r}</div>
                    ))}
                    {evalResult.degraded && (
                      <Alert style={{ marginTop: 8 }} type="warning" showIcon message="建议人工复核" />
                    )}
                  </div>
                }
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
