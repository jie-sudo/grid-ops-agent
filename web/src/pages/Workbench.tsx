import { useEffect, useRef, useState } from 'react';
import { Button, Card, Input, Select, Space, Tag, Alert, Popconfirm, Tooltip, Typography, Empty } from 'antd';
import { SendOutlined, NodeIndexOutlined, FolderOpenOutlined, SearchOutlined } from '@ant-design/icons';
import { api, streamChat } from '@/api';
import { useAppStore } from '@/store/app';
import { canDo, requiredLabel } from '@/utils/permissions';
import { LevelTag } from '@/components/common';
import type { ChatEvent, Device, WorkOrderDraft } from '@/types';
import { useNavigate } from 'react-router-dom';

interface ChatMsg {
  id: string;
  role: 'user' | 'assistant' | 'sys';
  text: string;
  sources?: string[];
  verification?: { passed: boolean; issues: string[] };
  draft?: WorkOrderDraft;
}

export function WorkbenchPage() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [devices, setDevices] = useState<Device[]>([]);
  const [currentDevice, setCurrentDevice] = useState<Device | null>(null);
  const [deviceSearch, setDeviceSearch] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const user = useAppStore((s) => s.user);

  const addMsg = (m: ChatMsg) => setMessages((prev) => [...prev, m]);
  const addSys = (text: string) => addMsg({ id: String(Date.now()) + Math.random(), role: 'sys', text });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  // 设备选择器：输入触发搜索
  useEffect(() => {
    const timer = setTimeout(() => {
      api.listDevices(deviceSearch, 20).then((list) => setDevices(list as Device[]));
    }, 300);
    return () => clearTimeout(timer);
  }, [deviceSearch]);

  useEffect(() => {
    api.listDevices('', 20).then((list) => setDevices(list as Device[]));
  }, []);

  const handleEvent = (evt: ChatEvent) => {
    switch (evt.type) {
      case 'session':
        setSessionId(evt.session_id ?? null);
        break;
      case 'intent':
        addSys(`🔍 识别意图：${evt.intent}（置信 ${Math.round((evt.confidence ?? 0) * 100)}%）`);
        break;
      case 'tool_call':
        addSys(`🔧 调用工具 ${evt.tool} ...`);
        break;
      case 'tool_result':
        // 工具结果可不展示，或轻量展示
        break;
      case 'degraded':
        addSys(`⚠️ ${evt.reason || '建议人工复核'}`);
        break;
      case 'clarify':
        addMsg({ id: String(Date.now()) + Math.random(), role: 'assistant', text: evt.question ?? '' });
        break;
      case 'confirm_required':
        addMsg({
          id: String(Date.now()) + Math.random(),
          role: 'assistant',
          text: evt.message ?? '工单草稿待确认',
          draft: evt.preview,
        });
        break;
      case 'final_answer':
        addMsg({
          id: String(Date.now()) + Math.random(),
          role: 'assistant',
          text: evt.answer ?? '',
          sources: evt.sources,
          verification: evt.verification,
        });
        break;
    }
  };

  const send = async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || sending) return;
    setInput('');
    addMsg({ id: String(Date.now()), role: 'user', text: msg });

    // 若选中设备且消息里没带设备编号，自动拼入
    let finalMsg = msg;
    if (currentDevice && !/DEV\d+/.test(msg)) {
      finalMsg = `设备 ${currentDevice.device_id}：${msg}`;
    }

    setSending(true);
    try {
      await streamChat(finalMsg, sessionId, handleEvent);
    } catch (e) {
      addSys(`请求失败：${(e as Error).message}`);
    } finally {
      setSending(false);
    }
  };

  const confirmDraft = async (ok: boolean) => {
    addMsg({ id: String(Date.now()), role: 'user', text: ok ? '确认' : '取消' });
    setSending(true);
    try {
      await streamChat(ok ? '确认' : '取消', sessionId, handleEvent);
    } catch (e) {
      addSys(`请求失败：${(e as Error).message}`);
    } finally {
      setSending(false);
    }
  };

  const canDraft = canDo(user?.role, 'draftWorkOrder');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 96px)' }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12 }}>
        <Typography.Text strong>对话工作台</Typography.Text>
        <Select
          showSearch
          value={currentDevice?.device_id}
          placeholder="选择设备（可选）"
          style={{ width: 260 }}
          allowClear
          onClear={() => setCurrentDevice(null)}
          onSearch={setDeviceSearch}
          filterOption={false}
          options={devices.map((d) => ({
            value: d.device_id,
            label: `${d.device_name}（${d.device_type} · ${d.station}）`,
          }))}
          onChange={(v) => {
            const d = devices.find((x) => x.device_id === v);
            setCurrentDevice(d ?? null);
          }}
          notFoundContent={<Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无匹配设备" />}
        />
        {currentDevice && <Tag color="blue">{currentDevice.device_name}</Tag>}
        <div style={{ flex: 1 }} />
        {sessionId && (
          <Tooltip title="查看本次运行链路">
            <Button icon={<NodeIndexOutlined />} onClick={() => navigate(`/runs?session_id=${sessionId}`)}>
              运行链路
            </Button>
          </Tooltip>
        )}
        <Button icon={<FolderOpenOutlined />} onClick={() => setMessages([])}>
          新会话
        </Button>
      </div>

      <Card
        style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
        styles={{ body: { flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 0 } }}
      >
        <div ref={scrollRef} style={{ flex: 1, overflow: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {messages.length === 0 && (
            <Empty
              style={{ margin: 'auto' }}
              description={
                <span>
                  新会话就绪。试试输入：
                  <br />
                  「变压器的缺陷分级有哪几级」「诊断变压器油温」「生成一个工单」
                </span>
              }
            />
          )}
          {messages.map((m) => (
            <MessageBubble key={m.id} m={m} onConfirm={confirmDraft} canConfirm={canDraft} />
          ))}
        </div>
        <div style={{ borderTop: '1px solid var(--border)', padding: 12, display: 'flex', gap: 8 }}>
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={() => send()}
            placeholder="输入问题，回车发送..."
            disabled={sending}
          />
          <Button type="primary" icon={<SendOutlined />} onClick={() => send()} loading={sending}>
            发送
          </Button>
        </div>
      </Card>
    </div>
  );
}

function MessageBubble({
  m,
  onConfirm,
  canConfirm,
}: {
  m: ChatMsg;
  onConfirm: (ok: boolean) => void;
  canConfirm: boolean;
}) {
  if (m.role === 'sys') {
    return <div style={{ alignSelf: 'center', color: 'var(--muted)', fontSize: 12 }}>{m.text}</div>;
  }
  const isUser = m.role === 'user';
  return (
    <div
      style={{
        alignSelf: isUser ? 'flex-end' : 'flex-start',
        maxWidth: '80%',
        background: isUser ? 'var(--accent)' : '#f1f4f7',
        color: isUser ? '#fff' : 'var(--text)',
        padding: '10px 14px',
        borderRadius: 8,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        lineHeight: 1.6,
      }}
    >
      <div>{m.text}</div>

      {/* 证据来源 */}
      {m.sources && m.sources.length > 0 && (
        <div style={{ marginTop: 8, paddingTop: 6, borderTop: '1px dashed var(--border)', fontSize: 12, color: 'var(--muted)' }}>
          <SearchOutlined /> 来源：{m.sources.join('；')}
        </div>
      )}

      {/* 溯源校验标记 */}
      {m.verification && (
        <div style={{ marginTop: 6, fontSize: 12 }}>
          {m.verification.passed ? (
            <Tag color="green">溯源通过</Tag>
          ) : (
            <Tag color="red">溯源异常</Tag>
          )}
          {m.verification.issues?.map((it, i) => (
            <div key={i} style={{ color: 'var(--danger)' }}>{it}</div>
          ))}
        </div>
      )}

      {/* 工单草稿确认框 */}
      {m.draft && (
        <div style={{ marginTop: 10, background: '#fff8e6', border: '1px solid #f0d68a', borderRadius: 8, padding: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>工单草稿（待二次确认）</div>
          <div style={{ fontSize: 13, lineHeight: 1.8 }}>
            {m.draft.device_id && <div>设备：<Typography.Text code>{m.draft.device_id}</Typography.Text></div>}
            <div>
              等级：<LevelTag level={m.draft.level} />
              {m.draft.deadline && <span style={{ marginLeft: 8, color: 'var(--muted)' }}>消缺时限：{m.draft.deadline}</span>}
            </div>
            <div>内容：{m.draft.content}</div>
          </div>
          <Space style={{ marginTop: 10 }}>
            <Popconfirm
              title="确认落库该工单？"
              description="确认后工单将正式下发，动作不可撤销。"
              onConfirm={() => onConfirm(true)}
              disabled={!canConfirm}
            >
              <Button type="primary" size="small" disabled={!canConfirm}>
                确认落库
              </Button>
            </Popconfirm>
            <Button size="small" onClick={() => onConfirm(false)}>
              取消
            </Button>
          </Space>
          {!canConfirm && (
            <Alert
              style={{ marginTop: 8 }}
              type="info"
              showIcon
              message={`当前角色无确认权限，需要 ${requiredLabel('confirmWorkOrder')} 权限`}
            />
          )}
        </div>
      )}
    </div>
  );
}
