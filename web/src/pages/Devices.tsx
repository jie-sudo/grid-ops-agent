import { useState } from 'react';
import { Table, Input, Drawer, Descriptions, Tabs, Card, Statistic, Row, Col, Typography } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api';
import { PageTitle, StatusTag, StateTag, AlarmLevelTag } from '@/components/common';
import type { Alarm, Device } from '@/types';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

export function DevicesPage() {
  const [keyword, setKeyword] = useState('');
  const [detailId, setDetailId] = useState<string | null>(null);

  const { data: devices, isLoading } = useQuery({
    queryKey: ['devices', keyword],
    queryFn: () => api.listDevices(keyword, 100),
  });

  return (
    <div>
      <PageTitle
        extra={
          <Input.Search
            placeholder="搜索设备名称 / 站所 / 类型"
            allowClear
            style={{ width: 280 }}
            onSearch={setKeyword}
          />
        }
      >
        设备管理
      </PageTitle>
      <Table<Device>
        rowKey="device_id"
        loading={isLoading}
        dataSource={devices as Device[]}
        pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 台` }}
        columns={[
          { title: '设备编号', dataIndex: 'device_id', render: (v) => <Typography.Text code>{v}</Typography.Text> },
          { title: '设备名称', dataIndex: 'device_name' },
          { title: '类型', dataIndex: 'device_type' },
          { title: '电压等级', dataIndex: 'voltage_level', render: (v) => v ?? '-' },
          { title: '站所', dataIndex: 'station', render: (v) => v ?? '-' },
          { title: '状态', dataIndex: 'status', render: (v) => <StatusTag status={v} /> },
          {
            title: '操作',
            render: (_, r) => (
              <a onClick={() => setDetailId(r.device_id)}>详情</a>
            ),
          },
        ]}
      />
      <DeviceDrawer deviceId={detailId} onClose={() => setDetailId(null)} />
    </div>
  );
}

function DeviceDrawer({ deviceId, onClose }: { deviceId: string | null; onClose: () => void }) {
  const { data: overview } = useQuery({
    queryKey: ['device-overview', deviceId],
    queryFn: () => api.getOverview(deviceId!),
    enabled: !!deviceId,
    refetchInterval: 5000, // 实时监控面板轮询
  });

  const { data: measurements } = useQuery({
    queryKey: ['device-measurements', deviceId],
    queryFn: () => api.getMeasurements(deviceId!, '温度', 24),
    enabled: !!deviceId,
  });

  const { data: state } = useQuery({
    queryKey: ['device-state', deviceId],
    queryFn: () => api.getDeviceState(deviceId!),
    enabled: !!deviceId,
  });

  const dev = overview?.device;

  return (
    <Drawer title={dev ? dev.device_name : '设备详情'} width={640} open={!!deviceId} onClose={onClose}>
      {dev && (
        <>
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="设备编号">{dev.device_id}</Descriptions.Item>
            <Descriptions.Item label="类型">{dev.device_type}</Descriptions.Item>
            <Descriptions.Item label="电压等级">{dev.voltage_level ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="站所">{dev.station ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <StatusTag status={dev.status} />
            </Descriptions.Item>
            <Descriptions.Item label="评价状态">
              <StateTag state={state?.state ?? overview?.state?.state} />
            </Descriptions.Item>
          </Descriptions>

          {state?.basis && state.basis.length > 0 && (
            <Card title="状态评价依据" size="small" style={{ marginTop: 12 }}>
              {state.basis.map((b, i) => (
                <div key={i} style={{ fontSize: 13, color: 'var(--muted)' }}>· {b}</div>
              ))}
            </Card>
          )}

          <Tabs
            style={{ marginTop: 12 }}
            items={[
              {
                key: 'measure',
                label: '实时量测',
                children: (
                  <div>
                    <Row gutter={12}>
                      {Object.entries(overview?.measurements ?? {}).map(([k, v]) => (
                        <Col span={12} key={k}>
                          <Card size="small" style={{ marginBottom: 12 }}>
                            <Statistic title={k} value={v} suffix="" />
                          </Card>
                        </Col>
                      ))}
                    </Row>
                    <div style={{ height: 200 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={(measurements as { ts: string; value: number }[]) ?? []}>
                          <defs>
                            <linearGradient id="temp" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#2563eb" stopOpacity={0.3} />
                              <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="ts" tick={{ fontSize: 10 }} />
                          <YAxis tick={{ fontSize: 10 }} />
                          <Tooltip />
                          <Area type="monotone" dataKey="value" stroke="#2563eb" fill="url(#temp)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                ),
              },
              {
                key: 'alarms',
                label: `告警（${overview?.alarm_count ?? 0}）`,
                children: (
                  <Table<Alarm>
                    rowKey="alarm_id"
                    size="small"
                    dataSource={overview?.alarms ?? []}
                    pagination={false}
                    columns={[
                      { title: '告警类型', dataIndex: 'alarm_type' },
                      { title: '等级', dataIndex: 'level', render: (v) => <AlarmLevelTag level={v} /> },
                      { title: '时间', dataIndex: 'trigger_time' },
                      { title: '状态', dataIndex: 'status' },
                    ]}
                  />
                ),
              },
            ]}
          />
        </>
      )}
    </Drawer>
  );
}
