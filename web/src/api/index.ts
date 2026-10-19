// API 层：统一封装后端调用，支持真实接口 / mock 切换（config.USE_MOCK）。
import axios from 'axios';
import { API_BASE, USE_MOCK } from '@/config';
import type { ApiResp, ChatEvent, LoginData, Role } from '@/types';
import * as M from '@/mocks/data';

// ---- 认证状态 ----
const TOKEN_KEY = 'gridops_token';
const USER_KEY = 'gridops_user';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function saveAuth(token: string, user: { user_id: string; role: Role }) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}
export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}
export function getStoredUser(): { user_id: string; role: Role } | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export const http = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

http.interceptors.request.use((cfg) => {
  const token = getToken();
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

http.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      clearAuth();
      if (location.pathname !== '/login') location.href = '/login';
    }
    return Promise.reject(err);
  },
);

// ---- 登录 ----
export async function login(username: string, password: string): Promise<LoginData> {
  if (USE_MOCK) {
    const acc = M.mockDevices.length ? null : null; // placeholder
    void acc;
    const valid =
      (username === 'admin' && password === 'admin123') ||
      (username === 'operator' && password === 'operator123') ||
      (username === 'monitor' && password === 'monitor123') ||
      (username === 'manager' && password === 'manager123');
    if (!valid) throw new Error('用户名或密码错误');
    const roleMap: Record<string, Role> = { admin: 'admin', operator: 'operator', monitor: 'monitor', manager: 'manager' };
    return { token: 'mock-' + Date.now(), user_id: 'U0001', role: roleMap[username] };
  }
  const res = await http.post<ApiResp<LoginData>>('/auth/login', { username, password });
  if (res.data.code !== 0) throw new Error(res.data.message || '登录失败');
  return res.data.data;
}

// ---- 通用 GET ----
async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const res = await http.get<ApiResp<T>>(url, { params });
  if (res.data.code !== 0) throw new Error(res.data.message || '请求失败');
  return res.data.data;
}

async function post<T>(url: string, body?: unknown): Promise<T> {
  const res = await http.post<ApiResp<T>>(url, body);
  if (res.data.code !== 0) throw new Error(res.data.message || '请求失败');
  return res.data.data;
}

// ---- 各业务接口（mock 模式下返回模拟数据）----
export const api = {
  // 设备
  listDevices: (keyword = '', limit = 50) =>
    USE_MOCK
      ? Promise.resolve(M.mockDevices.filter((d) => !keyword || d.device_name.includes(keyword) || d.station?.includes(keyword)).slice(0, limit))
      : get<{ devices: unknown[] }>('/devices', { keyword, limit }).then((d) => d.devices as never),
  getDevice: (id: string) =>
    USE_MOCK
      ? Promise.resolve(M.mockDevices.find((d) => d.device_id === id) ?? null)
      : get<{ device: unknown }>(`/devices/${id}`).then((d) => d.device as never),
  getMeasurements: (id: string, type?: string, hours = 24) =>
    USE_MOCK
      ? Promise.resolve(M.mockMeasurements(id))
      : get<{ values: unknown[] }>(`/devices/${id}/measurements`, { measure_type: type, hours }).then((d) => d.values as never),
  getDeviceState: (id: string) =>
    USE_MOCK
      ? Promise.resolve({ found: true, state: '注意', basis: ['油温=88.5℃，接近上限 90℃'] })
      : get<{ found: boolean; state: string; basis: string[] }>(`/devices/${id}/state`),
  getOverview: (id: string) =>
    USE_MOCK ? Promise.resolve(M.mockOverview(id)) : get<never>(`/devices/${id}/overview`),

  // 告警
  listAlarms: (deviceId?: string, hours = 24) =>
    USE_MOCK
      ? Promise.resolve(M.mockAlarms.filter((a) => !deviceId || a.device_id === deviceId))
      : get<{ alarms: unknown[] }>('/alarms', { device_id: deviceId, hours }).then((d) => d.alarms as never),
  analyzeAlarm: (alarm_type: string, over_ratio: number) =>
    USE_MOCK
      ? Promise.resolve({ level: over_ratio > 0.5 ? '紧急' : '重要', basis: `类型[${alarm_type}]，越限比例=${Math.round(over_ratio * 100)}%` })
      : post<{ level: string; basis: string }>('/alarms/analyze', { alarm_type, over_ratio }),

  // 缺陷
  listDefects: () =>
    USE_MOCK ? Promise.resolve(M.mockDefects) : get<{ defects: unknown[] }>('/defects').then((d) => d.defects as never),
  evaluateDefect: (description: string) =>
    USE_MOCK ? Promise.resolve(M.mockEvaluate(description)) : post<{ level: string; reasons: string[]; degraded: boolean }>('/defects/evaluate', { description }),
  getDeadline: (level: string) =>
    USE_MOCK
      ? Promise.resolve({ hours: level === '危急' ? 24 : level === '严重' ? 72 : 168, label: level === '危急' ? '24 小时内消除' : level === '严重' ? '72 小时内消除' : '168 小时内消除' })
      : get<{ hours: number; label: string }>(`/defects/deadline/${level}`),

  // 诊断
  diagnose: (device_type: string, measurements: Record<string, number>) =>
    USE_MOCK ? Promise.resolve(M.mockDiagnose(device_type, measurements)) : post<never>('/diagnoses', { device_type, measurements }),

  // 工单
  listWorkOrders: () =>
    USE_MOCK ? Promise.resolve(M.mockWorkOrders) : get<{ workorders: unknown[] }>('/workorders').then((d) => d.workorders as never),
  draftWorkOrder: (payload: unknown) =>
    USE_MOCK ? Promise.resolve({ message: '工单草稿已生成，待二次确认后落库' }) : post<{ message: string }>('/workorders/draft', payload),
  confirmWorkOrder: (id: string) =>
    USE_MOCK ? Promise.resolve({ message: 'ok' }) : post<{ message: string }>(`/workorders/${id}/confirm`, {}),
  cancelWorkOrder: (id: string) =>
    USE_MOCK ? Promise.resolve({ message: 'ok' }) : post<{ message: string }>(`/workorders/${id}/cancel`, {}),

  // 知识库
  listDocs: () =>
    USE_MOCK ? Promise.resolve(M.mockDocs) : get<{ docs: unknown[] }>('/knowledge/docs').then((d) => d.docs as never),
  searchKnowledge: (question: string, topK = 5) =>
    USE_MOCK ? Promise.resolve(M.mockKbSearch(question)) : get<{ chunks: unknown[] }>('/knowledge/search', { question, top_k: topK }).then((d) => d.chunks as never),
  ingestKnowledge: () =>
    USE_MOCK ? Promise.resolve({ message: '已触发重新入库' }) : post<{ message: string }>('/knowledge/ingest'),

  // 工具
  listTools: () =>
    USE_MOCK ? Promise.resolve(M.mockTools) : get<{ tools: unknown[] }>('/tools').then((d) => d.tools as never),

  // 运行链路
  getTrace: (sessionId: string) =>
    USE_MOCK ? Promise.resolve(M.mockTraceSteps) : get<{ traces: unknown[] }>(`/traces/${sessionId}`).then((d) => d.traces as never),

  // 会话
  listSessions: () =>
    USE_MOCK ? Promise.resolve(M.mockSessions) : get<{ sessions: unknown[] }>('/sessions').then((d) => d.sessions as never),

  // 复盘案例
  listCases: (status?: string) =>
    USE_MOCK
      ? Promise.resolve(M.mockCases.filter((c) => !status || c.status === status))
      : get<{ cases: unknown[] }>('/review-cases', status ? { status } : undefined).then((d) => d.cases as never),
  searchCases: (q: string) =>
    USE_MOCK
      ? Promise.resolve(M.mockCases.filter((c) => c.symptom.includes(q) || c.root_cause?.includes(q)))
      : get<{ cases: unknown[] }>('/review-cases/search', { q }).then((d) => d.cases as never),
  reviewCase: (id: string, action: string) =>
    USE_MOCK ? Promise.resolve({ message: 'ok' }) : post<{ message: string }>(`/review-cases/${id}/${action}`, {}),

  // 健康 / 指标
  getHealth: () =>
    USE_MOCK
      ? Promise.resolve({ status: 'up', dependencies: { postgres: 'ok', chromadb: 'ok', redis: 'ok' } })
      : get<never>('/health'),
  getMetrics: () =>
    USE_MOCK ? Promise.resolve(M.mockMetrics()) : get<never>('/metrics'),
};

// ---- SSE 流式对话 ----
// 真实模式：fetch + ReadableStream 解析 SSE；mock 模式：用定时器模拟流式事件推送。
export async function streamChat(
  message: string,
  sessionId: string | null,
  onEvent: (evt: ChatEvent) => void,
): Promise<void> {
  if (USE_MOCK) {
    return mockStreamChat(message, sessionId, onEvent);
  }

  const token = getToken();
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (res.status === 401) {
    clearAuth();
    location.href = '/login';
    return;
  }
  if (!res.ok || !res.body) throw new Error('网络错误');
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf('\n\n')) !== -1) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const line = chunk.split('\n').find((l) => l.startsWith('data: '));
      if (line) {
        try {
          onEvent(JSON.parse(line.slice(6)));
        } catch {
          /* 忽略解析失败 */
        }
      }
    }
  }
}

// Mock 流式：模拟后端 SSE 事件序列
async function mockStreamChat(message: string, sessionId: string | null, onEvent: (evt: ChatEvent) => void): Promise<void> {
  const sid = sessionId ?? 's' + Date.now().toString(36);
  const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

  onEvent({ type: 'session', session_id: sid });
  await delay(150);

  const isDefect = /缺陷|分级|定级/.test(message);
  const isDiag = /诊断|故障|温度|局放/.test(message);
  const isOrder = /工单|出单|派单/.test(message);

  const intent = isOrder ? '工单生成' : isDefect ? '缺陷分级' : isDiag ? '故障诊断' : '知识问答';
  onEvent({ type: 'intent', intent, confidence: 0.9 });
  await delay(200);

  if (isDiag) {
    onEvent({ type: 'tool_call', tool: 'query_device', params: { device_id: 'DEV000003' } });
    await delay(300);
    onEvent({ type: 'tool_result', tool: 'query_device', result: { device_name: '城东站变压器T1' } });
    await delay(300);
    onEvent({ type: 'tool_call', tool: 'diagnose', params: { device_type: '变压器' } });
    await delay(500);
    onEvent({
      type: 'final_answer',
      answer: '该设备油温 88.5℃，接近 90℃ 上限，判定为「过热」倾向，建议加强监测并安排测温复测。',
      sources: ['Q/GDW 1906 输变电设备状态评价导则'],
      verification: { passed: true, issues: [] },
    });
  } else if (isDefect) {
    onEvent({ type: 'tool_call', tool: 'evaluate_defect', params: { description: message } });
    await delay(400);
    onEvent({
      type: 'final_answer',
      answer: '缺陷分级结果：严重。命中关键词[超温]，建议 72 小时内消除。',
      sources: ['Q/GDW 745-2012 缺陷分级标准'],
    });
  } else if (isOrder) {
    onEvent({ type: 'tool_call', tool: 'draft_workorder', params: { defect_level: '严重', content: message } });
    await delay(400);
    onEvent({
      type: 'confirm_required',
      preview: { ref_type: '缺陷', content: '变压器油温偏高，需安排测温复测', level: '严重', deadline: '72小时内消除', device_id: 'DEV000003' },
      message: '请确认是否落库',
    });
  } else {
    onEvent({ type: 'tool_call', tool: 'search_knowledge', params: { question: message } });
    await delay(400);
    onEvent({
      type: 'final_answer',
      answer: '危急缺陷应立即安排停电处理；严重缺陷 72 小时内消除；一般缺陷 168 小时内消除。',
      sources: ['Q/GDW 745-2012', 'Q/GDW 1906'],
    });
  }
}
