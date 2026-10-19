import { useState } from 'react';
import { Card, Input, Button, Table, Space, Select, Alert, Tag, Typography, message } from 'antd';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api';
import { PageTitle, CaseStatusTag } from '@/components/common';
import { useAppStore } from '@/store/app';
import { canDo, requiredLabel } from '@/utils/permissions';
import type { ReviewCase } from '@/types';

export function ReviewCasesPage() {
  const user = useAppStore((s) => s.user);
  const qc = useQueryClient();
  const [status, setStatus] = useState<string | undefined>();
  const [q, setQ] = useState('');

  const canReview = canDo(user?.role, 'reviewCase');

  const { data: cases, isLoading } = useQuery({
    queryKey: ['review-cases', status],
    queryFn: () => api.listCases(status),
  });

  const search = async () => {
    if (!q.trim()) return;
    // 检索后临时替换展示（简化处理，直接复用列表查询）
    const r = await api.searchCases(q.trim());
    qc.setQueryData(['review-cases', status], r);
  };

  const review = async (id: string, action: 'approve' | 'reject' | 'supersede') => {
    await api.reviewCase(id, action);
    message.success('操作成功');
    qc.invalidateQueries({ queryKey: ['review-cases'] });
  };

  return (
    <div>
      <PageTitle
        extra={
          !canReview && (
            <Alert type="info" showIcon message={`审核案例需要 ${requiredLabel('reviewCase')} 权限`} style={{ maxWidth: 320 }} />
          )
        }
      >
        复盘案例库
      </PageTitle>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space>
          <Select
            allowClear
            placeholder="状态筛选"
            style={{ width: 160 }}
            value={status}
            onChange={setStatus}
            options={['草稿', '已审核', '已驳回', '已废止'].map((s) => ({ value: s, label: s }))}
          />
          <Input
            placeholder="检索案例（现象/根因关键词）"
            style={{ width: 280 }}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onPressEnter={search}
          />
          <Button onClick={search}>检索</Button>
        </Space>
      </Card>

      <Card size="small" title={`已审核案例会被 Agent 诊断时检索（共 ${cases?.length ?? 0} 条）`}>
        <Table<ReviewCase>
          rowKey="case_id"
          loading={isLoading}
          dataSource={cases as ReviewCase[]}
          size="small"
          pagination={{ pageSize: 20 }}
          columns={[
            { title: '案例编号', dataIndex: 'case_id', render: (v) => <Typography.Text code>{v}</Typography.Text> },
            { title: '标题', dataIndex: 'title' },
            { title: '设备类型', dataIndex: 'device_type', render: (v) => <Tag>{v}</Tag> },
            { title: '现象', dataIndex: 'symptom', ellipsis: true },
            { title: '根因', dataIndex: 'root_cause', render: (v) => v ?? '待补充' },
            { title: '处置', dataIndex: 'action', render: (v) => v ?? '待补充' },
            { title: '状态', dataIndex: 'status', render: (v) => <CaseStatusTag status={v} /> },
            {
              title: '操作',
              render: (_, r) => {
                if (!canReview) return <span style={{ color: 'var(--muted)' }}>-</span>;
                if (r.status === '草稿') {
                  return (
                    <Space>
                      <Button size="small" type="primary" onClick={() => review(r.case_id, 'approve')}>
                        通过
                      </Button>
                      <Button size="small" danger onClick={() => review(r.case_id, 'reject')}>
                        驳回
                      </Button>
                    </Space>
                  );
                }
                if (r.status === '已审核') {
                  return (
                    <Button size="small" onClick={() => review(r.case_id, 'supersede')}>
                      废止
                    </Button>
                  );
                }
                return <span style={{ color: 'var(--muted)' }}>-</span>;
              },
            },
          ]}
        />
      </Card>
    </div>
  );
}
