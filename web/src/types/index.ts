// 全局类型定义（对齐后端返回结构）
// 后端统一返回 { code, message, data }

export type Role = 'admin' | 'operator' | 'monitor' | 'manager';

export interface ApiResp<T = unknown> {
  code: number;
  message: string;
  data: T;
}

export interface LoginData {
  token: string;
  user_id: string;
  role: Role;
}

export interface UserInfo {
  user_id: string;
  role: Role;
  name: string;
}

// ---- 对话（SSE 事件）----
export type ChatEventType =
  | 'session'
  | 'intent'
  | 'tool_call'
  | 'tool_result'
  | 'degraded'
  | 'clarify'
  | 'confirm_required'
  | 'final_answer';

export interface ChatEvent {
  type: ChatEventType;
  session_id?: string;
  intent?: string;
  confidence?: number;
  tool?: string;
  params?: Record<string, unknown>;
  result?: Record<string, unknown>;
  reason?: string;
  question?: string;
  preview?: WorkOrderDraft;
  message?: string;
  answer?: string;
  sources?: string[];
  verification?: { passed: boolean; issues: string[] };
  budget?: { requests: number; charged_tokens: number };
}

export interface WorkOrderDraft {
  ref_type?: string;
  content?: string;
  level?: string;
  deadline?: string;
  status?: string;
  device_id?: string;
  assignee?: string;
}

// ---- 设备 ----
export interface Device {
  device_id: string;
  device_name: string;
  device_type: string;
  voltage_level?: string;
  station?: string;
  status?: string;
}

export interface Measurement {
  point_id: string;
  ts: string;
  value: number;
  quality: string;
}

export interface DeviceState {
  found: boolean;
  state: string;
  basis: string[];
}

export interface DeviceOverview {
  found: boolean;
  device: Device;
  state: { state?: string; basis?: string[] };
  measurements: Record<string, number>;
  alarms: Alarm[];
  alarm_count: number;
}

// ---- 告警 ----
export interface Alarm {
  alarm_id: string;
  device_id: string;
  alarm_type: string;
  level: string;
  trigger_time?: string;
  status?: string;
}

// ---- 缺陷 ----
export interface Defect {
  defect_id: string;
  device_id?: string;
  description: string;
  level: string;
  status?: string;
  source?: string;
}

// ---- 诊断 ----
export interface Diagnosis {
  fault_type: string;
  confidence: number;
  basis: string[];
  degraded: boolean;
  reason: string | null;
}

// ---- 工单 ----
export interface WorkOrder {
  order_id: string;
  ref_type?: string;
  ref_id?: string;
  content: string;
  level: string;
  status: string;
  assignee?: string | null;
  deadline?: string;
}

// ---- 知识库 ----
export interface KbDoc {
  title: string;
  source: string;
  status: string;
  superseded_by?: string;
}

export interface KbChunk {
  content: string;
  source: string;
  title: string;
  device_domain?: string;
  status?: string;
}

// ---- 工具 ----
export interface ToolInfo {
  name: string;
  description: string;
  params: Record<string, string>;
  read_only: boolean;
}

// ---- 运行链路 ----
export interface TraceStep {
  step: number;
  tool: string;
  params: Record<string, unknown>;
  result: Record<string, unknown>;
  sources: string[];
  elapsed_ms: number;
  degraded: boolean;
}

// ---- 会话 ----
export interface Session {
  session_id: string;
  intent?: string;
  created_at?: string;
}

// ---- 复盘案例 ----
export interface ReviewCase {
  case_id: string;
  title: string;
  device_type: string;
  symptom: string;
  root_cause?: string;
  action?: string;
  status: string;
  superseded_by?: string;
}

// ---- 健康 / 指标 ----
export interface HealthData {
  status: string;
  dependencies: Record<string, string>;
}

export interface Metric {
  name: string;
  value: number | string;
  label?: string;
}
