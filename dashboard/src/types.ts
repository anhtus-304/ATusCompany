/**
 * Hợp đồng dữ liệu giữa dashboard và server.
 * Dashboard chỉ hiển thị: mọi thay đổi trạng thái đều đến từ server qua WebSocket.
 * Xem README, mục "Hợp đồng WebSocket".
 */

export type GroupId = 'lead' | 'code' | 'creative';

/** Trạng thái agent hiển thị ở cột Đội ngũ (chấm xanh / cam / đỏ). */
export type AgentStatus = 'idle' | 'working' | 'blocked';

/** Hoạt động cụ thể, quyết định biểu tượng trong bong bóng trên đầu nhân vật. */
export type Activity =
  | 'idle'
  | 'typing'
  | 'reading'
  | 'thinking'
  | 'reviewing'
  | 'testing'
  | 'drawing'
  | 'meeting';

/** Vị trí nhân vật trong văn phòng: ngồi ở bàn mình hoặc đứng ở bàn họp. */
export type Location = 'desk' | 'meeting';

export interface Agent {
  id: string;
  name: string;
  role: string;
  group: GroupId;
  status: AgentStatus;
  activity: Activity;
  location: Location;
  /** Task đang làm (nếu có). */
  taskId?: string | null;
  /** Một dòng mô tả ngắn hiện dưới tên ở cột Đội ngũ. */
  note: string;
  /** Ghi đè nội dung bong bóng thoại; mặc định ghép từ task + activity. */
  bubble?: string | null;
  /** Bảng điểm agent (không bắt buộc). */
  metrics?: AgentMetrics | null;
}

export interface AgentMetrics {
  tasksDone?: number;
  firstPassRate?: number; // 0..1
  avgSeconds?: number;
  costUsd?: number;
}

export type TaskStatus = 'todo' | 'doing' | 'review' | 'blocked' | 'error' | 'done';

export interface Task {
  id: string; // ví dụ "TD-43"
  title: string;
  description: string;
  assigner: string; // agent id hoặc "boss"
  assignee: string; // agent id
  status: TaskStatus;
  files: string[];
  screenshot?: string | null; // URL ảnh chụp màn hình
  createdAt: string; // ISO
  updatedAt: string; // ISO
}

export type LogKind = 'start' | 'done' | 'error' | 'blocked' | 'review' | 'assign' | 'info';

export interface LogEntry {
  id: string;
  ts: string; // ISO
  agentId: string | null;
  taskId?: string | null;
  kind: LogKind;
  text: string;
}

/** Server → dashboard */
export type ServerMessage =
  | { type: 'snapshot'; company?: string; agents: Agent[]; tasks: Task[]; log: LogEntry[] }
  | { type: 'agent'; agent: Partial<Agent> & { id: string } }
  | { type: 'task'; task: Task }
  | { type: 'log'; entry: LogEntry };

/** Dashboard → server */
export type ClientMessage = { type: 'assign'; to: string; text: string };

export type ConnectionState = 'connecting' | 'open' | 'closed';

export type Selection = { kind: 'agent'; id: string } | { kind: 'task'; id: string } | null;

export const GROUPS: { id: GroupId; label: string }[] = [
  { id: 'lead', label: 'Ban lãnh đạo' },
  { id: 'code', label: 'Xưởng code' },
  { id: 'creative', label: 'Studio sáng tạo' },
];

export const STATUS_LABEL: Record<AgentStatus, string> = {
  idle: 'Đang rảnh',
  working: 'Đang làm',
  blocked: 'Bị chặn',
};

export const TASK_STATUS_LABEL: Record<TaskStatus, string> = {
  todo: 'Cần làm',
  doing: 'Đang làm',
  review: 'Chờ duyệt',
  blocked: 'Bị chặn',
  error: 'Lỗi',
  done: 'Hoàn thành',
};

export const TASK_STATUS_ORDER: TaskStatus[] = ['todo', 'doing', 'review', 'blocked', 'error', 'done'];

export const ACTIVITY_VERB: Record<Activity, string> = {
  idle: 'đang nghỉ',
  typing: 'đang code',
  reading: 'đang đọc',
  thinking: 'đang suy nghĩ',
  reviewing: 'đang review',
  testing: 'đang kiểm thử',
  drawing: 'đang vẽ',
  meeting: 'đang họp',
};

export function bubbleText(agent: Agent): string | null {
  if (agent.bubble) return agent.bubble;
  if (agent.status === 'blocked') return agent.taskId ? `${agent.taskId} bị chặn` : 'Bị chặn';
  if (agent.status === 'idle' && agent.activity !== 'meeting') return null;
  const verb = ACTIVITY_VERB[agent.activity];
  return agent.taskId ? `${agent.taskId} ${verb}` : verb.charAt(0).toUpperCase() + verb.slice(1);
}
