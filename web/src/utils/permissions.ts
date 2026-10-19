import type { Role } from '@/types';

// 角色权限矩阵（前端仅做体验层面的显隐，安全边界由后端 require_role 保证）

interface Perm {
  // 能否访问某页面（路由守卫用）
  canView: Record<string, Role[] | '*'>;
  // 某操作所需的最低角色（按钮禁用 + 原因提示用）
  actions: Record<string, Role[]>;
}

export const PERMISSIONS: Perm = {
  canView: {
    workbench: '*',
    devices: '*',
    alarms: '*',
    defects: '*',
    workorders: '*',
    runs: ['admin'],
    knowledge: '*',
    reviewCases: '*',
    health: '*',
    metrics: ['admin'],
    tools: '*',
    settings: '*',
  },
  actions: {
    confirmWorkOrder: ['manager', 'admin'],
    reviewCase: ['manager', 'admin'],
    ingestKnowledge: ['admin'],
    viewTrace: ['admin'],
    viewMetrics: ['admin'],
    evaluateDefect: ['operator', 'manager', 'admin'],
    draftWorkOrder: ['operator', 'manager', 'admin'],
  },
};

export function canView(role: Role | undefined, page: string): boolean {
  if (!role) return false;
  const rule = PERMISSIONS.canView[page];
  if (rule === undefined) return true;
  if (rule === '*') return true;
  return rule.includes(role);
}

export function canDo(role: Role | undefined, action: string): boolean {
  if (!role) return false;
  const rule = PERMISSIONS.actions[action];
  if (!rule) return true;
  return rule.includes(role);
}

export function requiredLabel(action: string): string {
  const rule = PERMISSIONS.actions[action];
  if (!rule) return '';
  const names: Record<Role, string> = {
    admin: 'admin',
    operator: 'operator',
    monitor: 'monitor',
    manager: 'manager',
  };
  return rule.map((r) => names[r]).join('/');
}
