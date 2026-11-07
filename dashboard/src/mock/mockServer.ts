/**
 * Server giả lập chạy trong trình duyệt. Phát đúng các ServerMessage như server thật
 * (snapshot rồi các sự kiện agent / task / log), để dashboard chạy được khi chưa có backend.
 */
import type { Activity, Agent, ClientMessage, LogEntry, LogKind, ServerMessage, Task } from '../types';
import { MOCK_AGENTS, MOCK_COMPANY, MOCK_LOG, MOCK_TASKS } from './data';

const NEW_TASKS = [
  'Thêm nút gọi điện nổi trên di động',
  'Viết trang Giới thiệu quán',
  'Làm hiệu ứng cuộn mượt',
  'Kiểm tra độ tương phản màu chữ',
  'Thêm ảnh món mới vào menu',
  'Tối ưu tốc độ tải trang',
  'Thiết kế lại footer',
  'Kiểm thử form trên Safari',
  'Viết test cho bảng giá',
  'Rà soát bảo mật form liên hệ',
];

const WORK_ACTIVITY: Record<string, Activity[]> = {
  leader: ['thinking'],
  senior: ['typing', 'typing', 'thinking'],
  junior: ['typing', 'reading'],
  intern: ['typing', 'reading', 'thinking'],
  reviewer: ['reviewing', 'reading'],
  designer: ['drawing'],
  tester: ['testing'],
};

export interface MockSocket {
  send(msg: ClientMessage): void;
  close(): void;
}

export function createMockServer(onMessage: (m: ServerMessage) => void, onOpen: () => void): MockSocket {
  const agents = new Map<string, Agent>(MOCK_AGENTS.map((a) => [a.id, { ...a }]));
  const tasks = new Map<string, Task>(MOCK_TASKS.map((t) => [t.id, { ...t }]));
  const busy = new Set<string>(); // agent đang trong một chuỗi kịch bản (đi họp...)
  let nextTask = 46;
  let logId = 100;
  let timers: number[] = [];
  let closed = false;

  const later = (ms: number, fn: () => void) => {
    const id = window.setTimeout(() => {
      timers = timers.filter((t) => t !== id);
      if (!closed) fn();
    }, ms);
    timers.push(id);
  };

  const now = () => new Date().toISOString();
  const pick = <T,>(xs: T[]) => xs[Math.floor(Math.random() * xs.length)];

  const setAgent = (id: string, patch: Partial<Agent>) => {
    const a = { ...agents.get(id)!, ...patch };
    agents.set(id, a);
    onMessage({ type: 'agent', agent: a });
  };
  const setTask = (id: string, patch: Partial<Task>) => {
    const t = { ...tasks.get(id)!, ...patch, updatedAt: now() };
    tasks.set(id, t);
    onMessage({ type: 'task', task: t });
  };
  const log = (agentId: string | null, kind: LogKind, text: string, taskId?: string | null) => {
    const entry: LogEntry = { id: `l${logId++}`, ts: now(), agentId, taskId, kind, text };
    onMessage({ type: 'log', entry });
  };
  const name = (id: string) => agents.get(id)?.name ?? id;

  const newTask = (title: string, assignee: string, assigner = 'leader', description = ''): Task => {
    const t: Task = {
      id: `TD-${nextTask++}`,
      title,
      description: description || `${title}. Task tạo tự động trong chế độ mock.`,
      assigner,
      assignee,
      status: 'todo',
      files: [],
      screenshot: null,
      createdAt: now(),
      updatedAt: now(),
    };
    tasks.set(t.id, t);
    onMessage({ type: 'task', task: t });
    return t;
  };

  /** Trưởng nhóm gọi agent lên bàn họp, giao task, rồi agent về bàn bắt đầu làm. */
  const briefAndStart = (agentId: string, task: Task) => {
    busy.add(agentId);
    busy.add('leader');
    const leaderPrev = agents.get('leader')!;
    setAgent('leader', { location: 'meeting', activity: 'meeting', status: 'working', bubble: `Giao ${task.id}` });
    setAgent(agentId, { location: 'meeting', activity: 'meeting', status: 'working', taskId: task.id, bubble: null });
    log('leader', 'assign', `Giao ${task.id} cho ${name(agentId)}: ${task.title}`, task.id);
    later(5200, () => {
      setAgent('leader', {
        location: 'desk',
        activity: leaderPrev.activity === 'meeting' ? 'thinking' : leaderPrev.activity,
        status: leaderPrev.taskId ? 'working' : 'idle',
        bubble: null,
      });
      const act = pick(WORK_ACTIVITY[agentId] ?? ['typing']);
      setAgent(agentId, { location: 'desk', activity: act, status: 'working', note: task.title });
      setTask(task.id, { status: 'doing' });
      log(agentId, 'start', `Bắt đầu ${task.id}: ${task.title}`, task.id);
      busy.delete('leader');
      later(2500, () => busy.delete(agentId));
    });
  };

  const finish = (a: Agent) => {
    const t = a.taskId ? tasks.get(a.taskId) : null;
    if (!t) return;
    const files = t.files.length ? t.files : [`src/${t.id.toLowerCase()}.ts`];
    if (a.id === 'reviewer' || Math.random() < 0.7) {
      setTask(t.id, { status: 'done', files });
      log(a.id, 'done', `Hoàn thành ${t.id}: ${t.title}`, t.id);
    } else {
      setTask(t.id, { status: 'review', files });
      log(a.id, 'review', `${t.id} chuyển sang chờ duyệt`, t.id);
    }
    setAgent(a.id, { status: 'idle', activity: 'idle', taskId: null, note: `Vừa xong ${t.id}`, bubble: null });
  };

  const step = () => {
    const free = [...agents.values()].filter((a) => !busy.has(a.id) && a.id !== 'leader');
    if (!free.length) return;
    const a = pick(free);
    const t = a.taskId ? tasks.get(a.taskId) : null;

    if (a.status === 'blocked' && t) {
      setAgent(a.id, { status: 'working', activity: pick(WORK_ACTIVITY[a.id] ?? ['typing']), note: t.title });
      setTask(t.id, { status: 'doing' });
      log(a.id, 'start', `${t.id} đã gỡ chặn, làm tiếp`, t.id);
      return;
    }
    if (a.status === 'working' && t) {
      const r = Math.random();
      if (r < 0.62) finish(a);
      else if (r < 0.8) {
        setAgent(a.id, { status: 'blocked', note: `Chờ thông tin cho ${t.id}` });
        setTask(t.id, { status: 'blocked' });
        log(a.id, 'blocked', `${t.id} bị chặn: cần thêm thông tin từ khách`, t.id);
      } else if (r < 0.9) {
        setAgent(a.id, { status: 'blocked', note: `Lỗi khi chạy ${t.id}` });
        setTask(t.id, { status: 'error' });
        log(a.id, 'error', `${t.id} lỗi: build thất bại, đang xem lại`, t.id);
      } else {
        const act = pick(WORK_ACTIVITY[a.id] ?? ['typing']);
        setAgent(a.id, { activity: act });
        log(a.id, 'info', `${t.id}: chuyển sang ${act === 'reading' ? 'đọc tài liệu' : act === 'thinking' ? 'suy nghĩ cách làm' : 'làm tiếp'}`, t.id);
      }
      return;
    }
    if (a.status === 'idle') {
      // reviewer nhận task đang chờ duyệt
      if (a.id === 'reviewer') {
        const rv = [...tasks.values()].find((x) => x.status === 'review');
        if (rv) {
          setAgent('reviewer', { status: 'working', activity: 'reviewing', taskId: rv.id, note: `Review ${rv.id}` });
          log('reviewer', 'start', `Bắt đầu review ${rv.id}`, rv.id);
          return;
        }
      }
      let todo = [...tasks.values()].find((x) => x.status === 'todo' && (x.assignee === a.id || !agents.has(x.assignee)));
      if (!todo) todo = [...tasks.values()].find((x) => x.status === 'todo');
      if (!todo || Math.random() < 0.25) todo = newTask(pick(NEW_TASKS), a.id);
      else if (todo.assignee !== a.id) setTask(todo.id, { assignee: a.id });
      briefAndStart(a.id, tasks.get(todo.id)!);
    }
  };

  const loop = () => {
    step();
    later(2600 + Math.random() * 2400, loop);
  };

  // "kết nối" sau một nhịp ngắn
  later(450, () => {
    onOpen();
    onMessage({
      type: 'snapshot',
      company: MOCK_COMPANY,
      agents: [...agents.values()],
      tasks: [...tasks.values()],
      log: MOCK_LOG,
    });
    // kịch bản mở đầu cố định để thấy ngay hiệu ứng
    later(2500, () => finish(agents.get('tester')!));
    later(4000, () => loop());
  });

  return {
    send(msg) {
      if (msg.type !== 'assign') return;
      const to = agents.has(msg.to) ? msg.to : 'leader';
      const title = msg.text.split('\n')[0].slice(0, 80);
      log(null, 'assign', `Sếp giao việc cho ${name(to)}: ${title}`);
      if (to === 'leader') {
        const task = newTask(title, 'leader', 'boss', msg.text);
        later(1500, () => {
          const target =
            [...agents.values()].find((a) => a.status === 'idle' && a.id !== 'leader' && !busy.has(a.id)) ??
            pick([...agents.values()].filter((a) => a.id !== 'leader' && !busy.has(a.id)));
          if (!target) return;
          setTask(task.id, { assignee: target.id });
          briefAndStart(target.id, tasks.get(task.id)!);
        });
      } else {
        const task = newTask(title, to, 'boss', msg.text);
        later(1200, () => {
          if (busy.has(to)) return;
          const cur = agents.get(to)!;
          if (cur.taskId && cur.status === 'working') {
            log(to, 'info', `${name(to)} xếp ${task.id} vào hàng chờ`, task.id);
            return;
          }
          briefAndStart(to, task);
        });
      }
    },
    close() {
      closed = true;
      timers.forEach((t) => window.clearTimeout(t));
      timers = [];
    },
  };
}
