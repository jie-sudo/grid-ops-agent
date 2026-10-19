import { useState } from 'react';
import { Table, Card, Form, InputNumber, Select, Button, Result, Space, Typography, Row, Col } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api';
import { PageTitle, AlarmLevelTag } from '@/components/common';
import type { Alarm } from '@/types';

export function AlarmsPage() {
  const [analyzeResult, setAnalyzeResult] = useState<{ level: string; basis: string } | null>(null);
  const [form] = Form.useForm();

  const { data: alarms, isLoading } = useQuery({
    queryKey: ['alarms'],
    queryFn: () => api.listAlarms(undefined, 24),
  });

  const onAnalyze = async (values: { alarm_type: string; over_ratio: number }) => {
    const r = await api.analyzeAlarm(values.alarm_type, values.over_ratio);
    setAnalyzeResult(r as { level: string; basis: string });
  };

  return (
    <div>
      <PageTitle>告警管理</PageTitle>
      <Row gutter={16}>
        <Col span={16}>
          <Card title={`告警列表（${alarms?.length ?? 0}）`} size="small">
            <Table<Alarm>
              rowKey="alarm_id"
              loading={isLoading}
              dataSource={alarms as Alarm[]}
              size="small"
              pagination={{ pageSize: 20 }}
              columns={[
                { title: '告警编号', dataIndex: 'alarm_id', render: (v) => <Typography.Text code>{v}</Typography.Text> },
                { title: '设备', dataIndex: 'device_id', render: (v) => <Typography.Text code>{v}</Typography.Text> },
                { title: '类型', dataIndex: 'alarm_type' },
                { title: '等级', dataIndex: 'level', render: (v) => <AlarmLevelTag level={v} /> },
                { title: '触发时间', dataIndex: 'trigger_time', render: (v) => v ?? '-' },
                { title: '状态', dataIndex: 'status' },
              ]}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card title="告警等级判定" size="small">
            <Form form={form} layout="vertical" onFinish={onAnalyze}>
              <Form.Item name="alarm_type" label="告警类型" rules={[{ required: true, message: '请输入告警类型' }]}>
                <Select
                  placeholder="选择告警类型"
                  options={['过温', '油温过高', '局放', '过流', '气压低'].map((t) => ({ value: t, label: t }))}
                />
              </Form.Item>
              <Form.Item name="over_ratio" label="越限比例（0~1）" rules={[{ required: true, message: '请输入越限比例' }]}>
                <InputNumber min={0} max={1} step={0.1} style={{ width: '100%' }} />
              </Form.Item>
              <Button type="primary" htmlType="submit" block>
                判定等级
              </Button>
            </Form>
            {analyzeResult && (
              <Result
                style={{ padding: '16px 0' }}
                status={analyzeResult.level === '紧急' ? 'error' : 'warning'}
                title={
                  <Space>
                    判定等级：
                    <AlarmLevelTag level={analyzeResult.level} />
                  </Space>
                }
                subTitle={analyzeResult.basis}
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
