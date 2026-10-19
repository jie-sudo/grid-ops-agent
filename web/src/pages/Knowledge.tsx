import { useState } from 'react';
import { Card, Input, Button, Table, Space, Tag, Alert, Empty, Typography } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api';
import { PageTitle } from '@/components/common';
import { useAppStore } from '@/store/app';
import { canDo, requiredLabel } from '@/utils/permissions';
import type { KbChunk, KbDoc } from '@/types';

export function KnowledgePage() {
  const user = useAppStore((s) => s.user);
  const [question, setQuestion] = useState('');
  const [chunks, setChunks] = useState<KbChunk[] | null>(null);
  const [searching, setSearching] = useState(false);

  const canIngest = canDo(user?.role, 'ingestKnowledge');

  const { data: docs } = useQuery({
    queryKey: ['kb-docs'],
    queryFn: () => api.listDocs(),
  });

  const search = async () => {
    if (!question.trim()) return;
    setSearching(true);
    try {
      const r = await api.searchKnowledge(question.trim());
      setChunks(r as KbChunk[]);
    } finally {
      setSearching(false);
    }
  };

  const ingest = async () => {
    await api.ingestKnowledge();
  };

  return (
    <div>
      <PageTitle
        extra={
          <Button type="primary" disabled={!canIngest} onClick={ingest} title={!canIngest ? `需要 ${requiredLabel('ingestKnowledge')} 权限` : ''}>
            重新入库
          </Button>
        }
      >
        知识库
      </PageTitle>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            placeholder="检索知识库（如：危急缺陷消缺时限）"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onPressEnter={search}
          />
          <Button type="primary" onClick={search} loading={searching}>
            检索
          </Button>
        </Space.Compact>
        {chunks !== null && (
          <div style={{ marginTop: 12 }}>
            {chunks.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="未检索到依据" />
            ) : (
              chunks.map((c, i) => (
                <div key={i} style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                  <Space>
                    <Typography.Text strong style={{ color: 'var(--accent)' }}>{c.title}</Typography.Text>
                    <Typography.Text code>{c.source}</Typography.Text>
                    {c.device_domain && <Tag>{c.device_domain}</Tag>}
                  </Space>
                  <div style={{ marginTop: 4, lineHeight: 1.6 }}>{c.content}</div>
                </div>
              ))
            )}
          </div>
        )}
      </Card>

      <Card size="small" title={`语料文档（${docs?.length ?? 0}）`}>
        {!canIngest && <Alert style={{ marginBottom: 12 }} type="info" showIcon message={`重新入库需要 ${requiredLabel('ingestKnowledge')} 权限`} />}
        <Table<KbDoc>
          rowKey={(r) => r.title}
          dataSource={docs as KbDoc[]}
          size="small"
          pagination={{ pageSize: 20 }}
          columns={[
            { title: '标题', dataIndex: 'title' },
            { title: '来源', dataIndex: 'source', render: (v) => <Typography.Text code>{v}</Typography.Text> },
            {
              title: '状态',
              dataIndex: 'status',
              render: (v, r) =>
                v === 'superseded' ? (
                  <Tag color="default">已废止{r.superseded_by ? ` → ${r.superseded_by}` : ''}</Tag>
                ) : (
                  <Tag color="green">有效</Tag>
                ),
            },
          ]}
        />
      </Card>
    </div>
  );
}
