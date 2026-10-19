import { useState } from 'react';
import { Table, Card, Button, Space, message, Alert, Typography, Tag } from 'antd';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api';
import { PageTitle, LevelTag } from '@/components/common';
import { useAppStore } from '@/store/app';
import { canDo, requiredLabel } from '@/utils/permissions';
import type { WorkOrder } from '@/types';

export function WorkOrdersPage() {
  const user = useAppStore((s) => s.user);
  const qc = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);

  const canConfirm = canDo(user?.role, 'confirmWorkOrder');

  const { data: workorders, isLoading } = useQuery({
    queryKey: ['workorders'],
    queryFn: () => api.listWorkOrders(),
  });

  const handleAction = async (id: string, action: 'confirm' | 'cancel') => {
    setBusy(id);
    try {
      if (action === 'confirm') await api.confirmWorkOrder(id);
      else await api.cancelWorkOrder(id);
      message.success(action === 'confirm' ? '工单已确认下发' : '工单已取消');
      qc.invalidateQueries({ queryKey: ['workorders'] });
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <PageTitle
        extra={
          !canConfirm && (
            <Alert type="info" showIcon message={`确认/取消工单需要 ${requiredLabel('confirmWorkOrder')} 权限`} style={{ maxWidth: 360 }} />
          )
        }
      >
        工单管理
      </PageTitle>
      <Card size="small">
        <Table<WorkOrder>
          rowKey="order_id"
          loading={isLoading}
          dataSource={workorders as WorkOrder[]}
          size="small"
          pagination={{ pageSize: 20 }}
          columns={[
            { title: '工单编号', dataIndex: 'order_id', render: (v) => <Typography.Text code>{v}</Typography.Text> },
            { title: '类型', dataIndex: 'ref_type', render: (v) => v ?? '-' },
            { title: '关联设备', dataIndex: 'ref_id', render: (v) => (v ? <Typography.Text code>{v}</Typography.Text> : '-') },
            { title: '内容', dataIndex: 'content', ellipsis: true },
            { title: '等级', dataIndex: 'level', render: (v) => <LevelTag level={v} /> },
            {
              title: '状态',
              dataIndex: 'status',
              render: (v) => {
                const color = v === '已下发' ? 'green' : v === '草稿' ? 'orange' : 'default';
                return <Tag color={color}>{v}</Tag>;
              },
            },
            { title: '负责人', dataIndex: 'assignee', render: (v) => v ?? '-' },
            { title: '消缺时限', dataIndex: 'deadline', render: (v) => v ?? '-' },
            {
              title: '操作',
              render: (_, r) => {
                if (r.status !== '草稿') return <span style={{ color: 'var(--muted)' }}>-</span>;
                return (
                  <Space>
                    <Button
                      size="small"
                      type="primary"
                      disabled={!canConfirm}
                      loading={busy === r.order_id}
                      onClick={() => handleAction(r.order_id, 'confirm')}
                    >
                      确认
                    </Button>
                    <Button size="small" disabled={!canConfirm} onClick={() => handleAction(r.order_id, 'cancel')}>
                      取消
                    </Button>
                  </Space>
                );
              },
            },
          ]}
        />
      </Card>
    </div>
  );
}
