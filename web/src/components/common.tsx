// 通用小部件：等级/状态 badge、页面标题等
import { Tag } from 'antd';
import type { ReactNode } from 'react';

// 缺陷/工单等级三值
export function LevelTag({ level }: { level?: string }) {
  const colorMap: Record<string, string> = {
    一般: 'green',
    严重: 'orange',
    危急: 'red',
  };
  return level ? <Tag color={colorMap[level] ?? 'default'}>{level}</Tag> : <span>-</span>;
}

// 设备状态四值
export function StatusTag({ status }: { status?: string }) {
  const colorMap: Record<string, string> = {
    运行: 'green',
    停运: 'default',
    检修: 'orange',
    备用: 'blue',
  };
  return status ? <Tag color={colorMap[status] ?? 'default'}>{status}</Tag> : <span>-</span>;
}

// 告警等级三值
export function AlarmLevelTag({ level }: { level?: string }) {
  const colorMap: Record<string, string> = {
    提示: 'blue',
    重要: 'orange',
    紧急: 'red',
  };
  return level ? <Tag color={colorMap[level] ?? 'default'}>{level}</Tag> : <span>-</span>;
}

// 四态 state
export function StateTag({ state }: { state?: string }) {
  const colorMap: Record<string, string> = {
    正常: 'green',
    注意: 'orange',
    异常: 'red',
    严重: 'magenta',
  };
  return state ? <Tag color={colorMap[state] ?? 'default'}>{state}</Tag> : <span>-</span>;
}

// 案例状态
export function CaseStatusTag({ status }: { status?: string }) {
  const colorMap: Record<string, string> = {
    草稿: 'orange',
    已审核: 'green',
    已驳回: 'red',
    已废止: 'default',
  };
  return status ? <Tag color={colorMap[status] ?? 'default'}>{status}</Tag> : <span>-</span>;
}

export function PageTitle({ children, extra }: { children: ReactNode; extra?: ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
      <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>{children}</h2>
      {extra}
    </div>
  );
}

// 只读/写 badge
export function ReadWriteTag({ readOnly }: { readOnly: boolean }) {
  return readOnly ? <Tag color="green">只读</Tag> : <Tag color="orange">写</Tag>;
}
