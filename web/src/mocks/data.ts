// Mock 数据源：后端未就绪时提供完整演示数据，字段结构严格对齐后端返回。
// 后端就绪后（config.ts USE_MOCK=false）此模块不再被引用。

import type {
  Alarm,
  Defect,
  Device,
  DeviceOverview,
  Diagnosis,
  KbChunk,
  KbDoc,
  ReviewCase,
  Session,
  ToolInfo,
  TraceStep,
  WorkOrder,
} from '@/types';

export const mockDevices: Device[] = [
  { device_id: 'DEV000001', device_name: '城西站开关柜0001', device_type: '开关柜', voltage_level: '35kV', station: '城西站', status: '运行' },
  { device_id: 'DEV000002', device_name: '城西站开关柜0002', device_type: '开关柜', voltage_level: '35kV', station: '城西站', status: '运行' },
  { device_id: 'DEV000003', device_name: '城东站变压器T1', device_type: '变压器', voltage_level: '110kV', station: '城东站', status: '运行' },
  { device_id: 'DEV000004', device_name: '城东站变压器T2', device_type: '变压器', voltage_level: '110kV', station: '城东站', status: '检修' },
  { device_id: 'DEV000005', device_name: '城南站电缆C01', device_type: '电缆', voltage_level: '10kV', station: '城南站', status: '运行' },
  { device_id: 'DEV000006', device_name: '城南站电缆C02', device_type: '电缆', voltage_level: '10kV', station: '城南站', status: '停运' },
  { device_id: 'DEV000007', device_name: '城北站开关柜0003', device_type: '开关柜', voltage_level: '35kV', station: '城北站', status: '运行' },
  { device_id: 'DEV000008', device_name: '城北站变压器T3', device_type: '变压器', voltage_level: '110kV', station: '城北站', status: '备用' },
];

export const mockAlarms: Alarm[] = [
  { alarm_id: 'AL000001', device_id: 'DEV000001', alarm_type: '过温', level: '重要', trigger_time: '2026-10-19 16:20:11', status: '活动' },
  { alarm_id: 'AL000002', device_id: 'DEV000003', alarm_type: '油温过高', level: '紧急', trigger_time: '2026-10-19 15:58:02', status: '活动' },
  { alarm_id: 'AL000003', device_id: 'DEV000005', alarm_type: '局放', level: '重要', trigger_time: '2026-10-19 14:12:45', status: '活动' },
  { alarm_id: 'AL000004', device_id: 'DEV000007', alarm_type: '过温', level: '提示', trigger_time: '2026-10-19 11:30:00', status: '已恢复' },
];

export const mockDefects: Defect[] = [
  { defect_id: 'DF000001', device_id: 'DEV000001', description: '开关柜触头温度偏高，局部 62.5℃', level: '严重', status: '待处理', source: '巡检' },
  { defect_id: 'DF000002', device_id: 'DEV000003', description: '变压器套管闪络痕迹', level: '危急', status: '待处理', source: '在线监测' },
  { defect_id: 'DF000003', device_id: 'DEV000005', description: '电缆中间接头局放超标', level: '严重', status: '已派单', source: '试验' },
  { defect_id: 'DF000004', device_id: 'DEV000007', description: '开关柜机构卡涩', level: '一般', status: '已消除', source: '巡检' },
];

export const mockWorkOrders: WorkOrder[] = [
  { order_id: 'WO000001', ref_type: '缺陷', ref_id: 'DF000002', content: '变压器套管闪络，需停电检修', level: '危急', status: '已下发', assignee: '张三', deadline: '24小时内消除' },
  { order_id: 'WO000002', ref_type: '缺陷', ref_id: 'DF000001', content: '开关柜触头过热，建议测温复测', level: '严重', status: '草稿', assignee: null, deadline: '72小时内消除' },
  { order_id: 'WO000003', ref_type: '缺陷', ref_id: 'DF000003', content: '电缆中间接头局放超标处理', level: '严重', status: '已下发', assignee: '李四', deadline: '72小时内消除' },
];

export const mockTools: ToolInfo[] = [
  { name: 'query_device', description: '按设备编号查询台账', params: { device_id: 'str' }, read_only: true },
  { name: 'query_measurements', description: '查询设备量测值', params: { device_id: 'str', measure_type: 'str' }, read_only: true },
  { name: 'query_alarms', description: '查询设备告警', params: { device_id: 'str' }, read_only: true },
  { name: 'evaluate_defect', description: '缺陷分级评估', params: { description: 'str' }, read_only: true },
  { name: 'diagnose', description: '设备故障诊断', params: { device_type: 'str', measurements: 'dict' }, read_only: true },
  { name: 'analyze_alarm', description: '告警等级判定', params: { alarm_type: 'str', over_ratio: 'float' }, read_only: true },
  { name: 'search_knowledge', description: '知识库检索', params: { question: 'str' }, read_only: true },
  { name: 'draft_workorder', description: '生成工单草稿', params: { defect_level: 'str', content: 'str' }, read_only: false },
  { name: 'confirm_workorder', description: '确认工单落库', params: { order_id: 'str' }, read_only: false },
];

export const mockDocs: KbDoc[] = [
  { title: '配电网设备缺陷分类与分级标准（摘编）', source: 'Q/GDW 745-2012 / Q/GDW 1519-2014', status: 'active' },
  { title: '输变电设备状态评价导则', source: 'Q/GDW 1906', status: 'active' },
  { title: '变压器运行规程', source: 'DL/T 572-2021', status: 'active' },
  { title: '开关柜运行维护导则', source: 'DL/T 593-2016', status: 'active' },
  { title: '电力电缆线路运行规程', source: 'DL/T 1253-2013', status: 'superseded', superseded_by: 'DL/T 1253-2023' },
];

export const mockCases: ReviewCase[] = [
  { case_id: 'RC000001', title: '变压器油温异常升高的处置', device_type: '变压器', symptom: '油温持续 85℃ 以上', root_cause: '散热器堵塞', action: '清洗散热器、补油', status: '已审核' },
  { case_id: 'RC000002', title: '开关柜局部放电超标', device_type: '开关柜', symptom: '局放 150pC 超上限', root_cause: '绝缘受潮', action: '干燥处理', status: '草稿' },
  { case_id: 'RC000003', title: '电缆接头过热', device_type: '电缆', symptom: '中间接头 70℃', status: '已驳回' },
];

export const mockSessions: Session[] = [
  { session_id: 'skx1a2b3c', intent: '故障诊断', created_at: '2026-10-19 16:40:00' },
  { session_id: 'skx4d5e6f', intent: '缺陷分级', created_at: '2026-10-19 15:20:00' },
  { session_id: 'skx7g8h9i', intent: '问答', created_at: '2026-10-19 14:05:00' },
];

export const mockTraceSteps: TraceStep[] = [
  { step: 1, tool: 'query_device', params: { device_id: 'DEV000003' }, result: { device_name: '城东站变压器T1' }, sources: [], elapsed_ms: 18, degraded: false },
  { step: 2, tool: 'query_measurements', params: { device_id: 'DEV000003', measure_type: '油温' }, result: { value: 88.5 }, sources: [], elapsed_ms: 22, degraded: false },
  { step: 3, tool: 'diagnose', params: { device_type: '变压器' }, result: { fault_type: '油温过高' }, sources: ['Q/GDW 1906 状态评价导则'], elapsed_ms: 1450, degraded: false },
];

// 模拟量测曲线
export function mockMeasurements(deviceId: string): { point_id: string; ts: string; value: number; quality: string }[] {
  const base = deviceId === 'DEV000003' ? 70 : 40;
  return Array.from({ length: 24 }, (_, i) => ({
    point_id: `PT${String(i + 1).padStart(3, '0')}`,
    ts: `2026-10-19 ${String(i).padStart(2, '0')}:00`,
    value: Math.round((base + Math.sin(i / 3) * 8 + (i % 5)) * 10) / 10,
    quality: i % 9 === 0 ? '缺失' : '正常',
  }));
}

export function mockOverview(deviceId: string): DeviceOverview {
  const device = mockDevices.find((d) => d.device_id === deviceId) ?? mockDevices[0];
  const alarms = mockAlarms.filter((a) => a.device_id === deviceId);
  return {
    found: true,
    device,
    state: { state: '注意', basis: ['油温=88.5℃，接近上限 90℃'] },
    measurements: { 温度: 62.5, 电流: 210.3, 电压: 35.2, 局放: 30.7 },
    alarms,
    alarm_count: alarms.length,
  };
}

export function mockEvaluate(description: string): { level: string; reasons: string[]; degraded: boolean } {
  if (/闪络|击穿|爆炸/.test(description)) return { level: '危急', reasons: ['命中关键词[闪络]'], degraded: false };
  if (/超温|过热|局放|放电/.test(description)) return { level: '严重', reasons: ['命中关键词[超温/局放]'], degraded: false };
  if (/卡涩|渗漏|锈蚀/.test(description)) return { level: '一般', reasons: ['命中关键词[卡涩]'], degraded: false };
  return { level: '一般', reasons: ['未命中强关键词，按一般定级'], degraded: true };
}

export function mockDiagnose(_deviceType: string, measurements: Record<string, number>): Diagnosis {
  const pdt = measurements['局放'] ?? 0;
  const tmp = measurements['温度'] ?? measurements['油温'] ?? 0;
  if (pdt > 100) return { fault_type: '局放超标', confidence: 0.82, basis: [`局放=${pdt}pC，上限=100pC`], degraded: false, reason: null };
  if (tmp > 80) return { fault_type: '过热', confidence: 0.75, basis: [`温度=${tmp}℃，上限=80℃`], degraded: false, reason: null };
  return { fault_type: '运行正常', confidence: 0.9, basis: ['各项量测均在阈值内'], degraded: false, reason: null };
}

export function mockKbSearch(question: string): KbChunk[] {
  const kw = question.includes('危急') ? '危急缺陷' : '缺陷分级';
  return [
    { content: `${kw}需在最短时限内消除，一般缺陷 24~72 小时内消除，严重缺陷 72 小时内，危急缺陷应立即安排停电处理。`, source: 'Q/GDW 745-2012', title: '配电网设备缺陷分类与分级标准', device_domain: '通用', status: 'active' },
    { content: '缺陷分级依据设备重要程度、对供电可靠性的影响程度进行综合判定。', source: 'Q/GDW 1906', title: '输变电设备状态评价导则', device_domain: '输变电', status: 'active' },
  ];
}

export function mockMetrics() {
  return {
    summary: [
      { name: '缺陷分级准确率', value: '100%', label: '10/10' },
      { name: '意图识别准确率', value: '91.7%', label: '11/12' },
      { name: '检索 Recall@5', value: '89.7%', label: '混合检索+rerank' },
      { name: '单问 LLM 成本', value: '¥0.0008', label: 'DeepSeek' },
      { name: '稳态端到端延迟', value: '3.0s', label: '目标 <15s' },
    ],
    runs: [
      { id: 'run-20261019', suite: '缺陷分级', ts: '2026-10-19 16:00', result: '100%', samples: 10 },
      { id: 'run-20261018', suite: '知识检索', ts: '2026-10-18 20:00', result: '89.7%', samples: 300 },
    ],
  };
}
