import { Card, Table, Typography, Tag } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api';
import { PageTitle, ReadWriteTag } from '@/components/common';
import type { ToolInfo } from '@/types';

export function ToolsPage() {
  const { data: tools, isLoading } = useQuery({
    queryKey: ['tools'],
    queryFn: () => api.listTools(),
  });

  return (
    <div>
      <PageTitle>工具注册表</PageTitle>
      <Card size="small" title={`共 ${tools?.length ?? 0} 个工具`}>
        <Table<ToolInfo>
          rowKey="name"
          loading={isLoading}
          dataSource={tools as ToolInfo[]}
          size="small"
          pagination={false}
          columns={[
            { title: '工具', dataIndex: 'name', render: (v) => <Typography.Text code>{v}</Typography.Text> },
            { title: '说明', dataIndex: 'description' },
            {
              title: '参数',
              dataIndex: 'params',
              render: (v) => (
                <div>
                  {Object.entries(v ?? {}).map(([k, t]) => (
                    <Tag key={k}>
                      {k}: <Typography.Text code>{t as string}</Typography.Text>
                    </Tag>
                  ))}
                </div>
              ),
            },
            { title: '权限', dataIndex: 'read_only', render: (v) => <ReadWriteTag readOnly={v} /> },
          ]}
        />
      </Card>
    </div>
  );
}
