/**
 * Chuẩn hoá tin nhắn từ server về đúng kiểu trong types.ts.
 * Chấp nhận cả dạng snake_case (task_id, agent_id, at, level) và trạng thái agent "error"
 * để backend có thể gửi dữ liệu thô mà dashboard vẫn hiển thị được.
 */
import type { Agent, AgentStatus, GroupId, LogEntry, LogKind, ServerMessage, Task, TaskStatus } from '../types';

type Raw = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

const AGENT_STATUS: Record<string, AgentStatus> = { idle: 'idle', working: 'working', blocked: 'blocked', error: 'blocked' };
const TASK_STATUS: TaskStatus[] = ['todo', 'doing', 'review', 'blocked', 'error', 'done'];
const LOG_KIND: LogKind[] = ['start', 'done', 'error', 'blocked', 'review', 'assign', 'info'];
const GROUPS: GroupId[] = ['lead', 'code', 'creative'];

let seq = 0;

export function normAgent(r: Raw): Partial<Agent> & { id: string } {
  const out: Partial<Agent> & { id: string } = { id: String(r.id) };
  if (r.name !== undefined) out.name = r.name;
  if (r.role !== undefined) out.role = r.role;
  if (r.group !== undefined) out.group = GROUPS.includes(r.group) ? r.group : 'code';
  if (r.status !== undefined) out.status = AGENT_STATUS[r.status] ?? 'idle';
  if (r.activity !== undefined) out.activity = r.activity;
  if (r.location !== undefined) out.location = r.location === 'meeting' ? 'meeting' : 'desk';
  const taskId = r.taskId ?? r.task_id;
  if (taskId !== undefined) out.taskId = taskId;
  const note = r.note ?? r.task_text;
  if (note !== undefined) out.note = note ?? '';
  if (r.bubble !== undefined) out.bubble = r.bubble;
  if (r.metrics !== undefined) out.metrics = r.metrics;
  return out;
}

export function fillAgent(p: Partial<Agent> & { id: string }): Agent {
  return {
    name: p.id,
    role: '',
    group: 'code',
    status: 'idle',
    activity: p.status === 'working' ? (p.group === 'lead' ? 'thinking' : 'typing') : 'idle',
    location: 'desk',
    taskId: null,
    note: '',
    ...p,
  } as Agent;
}

export function normTask(r: Raw): Task {
  const ts = new Date().toISOString();
  return {
    id: String(r.id),
    title: r.title ?? String(r.id),
    description: r.description ?? '',
    assigner: r.assigner ?? 'boss',
    assignee: r.assignee ?? '',
    status: TASK_STATUS.includes(r.status) ? r.status : 'todo',
    files: Array.isArray(r.files) ? r.files : [],
    screenshot: r.screenshot ?? null,
    createdAt: r.createdAt ?? r.created_at ?? ts,
    updatedAt: r.updatedAt ?? r.updated_at ?? ts,
  };
}

export function normLog(r: Raw): LogEntry {
  const e = r.entry ?? r;
  const kind = e.kind ?? e.level;
  return {
    id: String(e.id ?? `srv-${Date.now()}-${seq++}`),
    ts: e.ts ?? e.at ?? new Date().toISOString(),
    agentId: e.agentId ?? e.agent_id ?? null,
    taskId: e.taskId ?? e.task_id ?? null,
    kind: LOG_KIND.includes(kind) ? kind : 'info',
    text: String(e.text ?? ''),
  };
}

export function normalize(raw: Raw): ServerMessage | null {
  switch (raw?.type) {
    case 'snapshot':
      return {
        type: 'snapshot',
        company: raw.company,
        agents: (raw.agents ?? []).map((a: Raw) => fillAgent(normAgent(a))),
        tasks: (raw.tasks ?? []).map(normTask),
        log: (raw.log ?? []).map(normLog),
      };
    case 'agent':
      return { type: 'agent', agent: normAgent(raw.agent ?? raw) };
    case 'task':
      return { type: 'task', task: normTask(raw.task ?? raw) };
    case 'log':
      return { type: 'log', entry: normLog(raw) };
    default:
      return null;
  }
}
