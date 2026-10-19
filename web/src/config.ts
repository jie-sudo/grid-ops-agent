// 全局配置
export const API_BASE = '/api/v1';

// 数据源开关：true = 使用内置 mock（后端未就绪时演示 UI）；false = 连接真实后端
// 后端就绪后（localhost:8000 可访问）改为 false 即可切回真实数据。
export const USE_MOCK = true;

// 默认演示账号（与后端一致）
export const DEMO_ACCOUNTS = [
  { username: 'admin', password: 'admin123', role: 'admin' as const, label: '管理员' },
  { username: 'operator', password: 'operator123', role: 'operator' as const, label: '运维' },
  { username: 'monitor', password: 'monitor123', role: 'monitor' as const, label: '监控' },
  { username: 'manager', password: 'manager123', role: 'manager' as const, label: '管理' },
];
