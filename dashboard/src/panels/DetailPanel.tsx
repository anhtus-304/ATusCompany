import { PixelAvatar } from '../components/PixelAvatar';
import type { Agent, Selection, Task } from '../types';
import { ACTIVITY_VERB, STATUS_LABEL, TASK_STATUS_LABEL } from '../types';

interface Props {
  selection: Selection;
  agents: Agent[];
  tasks: Task[];
  onSelectTask: (id: string) => void;
  onSelectAgent: (id: string) => void;
  onLocate?: (agentId: string) => void;
}

const STEPS = ['Tiếp nhận', 'Lên kế hoạch', 'Thực hiện', 'Kiểm thử', 'Review', 'Hoàn thành'];

/** Vị trí task trong luồng công việc, suy ra từ trạng thái và hoạt động của người nhận. */
function stepIndex(task: Task, assignee?: Agent): number {
  switch (task.status) {
    case 'todo':
      return 1;
    case 'review':
      return 4;
    case 'done':
      return STEPS.length;
    default:
      return assignee?.activity === 'testing' ? 3 : 2;
  }
}

function Workflow({ task, assignee }: { task: Task; assignee?: Agent }) {
  const idx = stepIndex(task, assignee);
  const problem = task.status === 'blocked' || task.status === 'error';
  const pct = Math.round((idx / STEPS.length) * 100);
  return (
    <div className="td-section">
      <h4>Luồng công việc</h4>
      <div className={`progress ${problem ? 'bad' : ''}`} aria-label={`Tiến độ ${pct}%`}>
        <span style={{ width: `${pct}%` }} />
        <em>{pct}%</em>
      </div>
      <ol className="workflow">
        {STEPS.map((st, i) => {
          const state = i < idx ? 'done' : i === idx ? (problem ? 'problem' : 'current') : 'pending';
          return (
            <li key={st} className={`wf-${state}`}>
              <span className="wf-dot" aria-hidden>
                {state === 'done' ? '✓' : state === 'problem' ? '!' : ''}
              </span>
              <span className="wf-label">{st}</span>
              {state === 'current' && assignee && <span className="wf-who">{assignee.name}</span>}
              {state === 'problem' && <span className="wf-who bad">{task.status === 'error' ? 'Lỗi' : 'Bị chặn'}</span>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function TaskCard({ task, agents, onSelectAgent, onLocate }: { task: Task; agents: Agent[]; onSelectAgent: (id: string) => void; onLocate?: (id: string) => void }) {
  const who = (id: string) => (id === 'boss' ? 'Sếp' : agents.find((a) => a.id === id)?.name ?? id);
  const fmt = (iso: string) => new Date(iso).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' });
  return (
    <div className="task-detail">
      <div className="td-head">
        <span className="td-code pixel">{task.id}</span>
        <span className={`chip t-${task.status}`}>{TASK_STATUS_LABEL[task.status]}</span>
      </div>
      <h3>{task.title}</h3>
      {task.description && <p className="td-desc">{task.description}</p>}
      {onLocate && agents.some((a) => a.id === task.assignee) && (
        <button className="btn-locate" onClick={() => onLocate(task.assignee)}>
          ◎ Tìm {who(task.assignee)} trong văn phòng
        </button>
      )}
      <Workflow task={task} assignee={agents.find((a) => a.id === task.assignee)} />
      <dl className="kv">
        <dt>Người giao</dt>
        <dd>{task.assigner in { boss: 1 } ? 'Sếp' : <a onClick={() => onSelectAgent(task.assigner)}>{who(task.assigner)}</a>}</dd>
        <dt>Người nhận</dt>
        <dd>
          <a onClick={() => onSelectAgent(task.assignee)}>{who(task.assignee)}</a>
        </dd>
        <dt>Trạng thái</dt>
        <dd>{TASK_STATUS_LABEL[task.status]}</dd>
        <dt>Cập nhật</dt>
        <dd>{fmt(task.updatedAt)}</dd>
      </dl>
      <div className="td-section">
        <h4>File đã tạo</h4>
        {task.files.length ? (
          <ul className="files">
            {task.files.map((f) => (
              <li key={f}>
                <code>{f}</code>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Chưa có file.</p>
        )}
      </div>
      {task.screenshot && (
        <div className="td-section">
          <h4>Ảnh chụp màn hình</h4>
          <a href={task.screenshot} target="_blank" rel="noreferrer">
            <img className="shot" src={task.screenshot} alt={`Ảnh chụp ${task.id}`} />
          </a>
        </div>
      )}
    </div>
  );
}

export function DetailPanel({ selection, agents, tasks, onSelectTask, onSelectAgent, onLocate }: Props) {
  if (!selection) return <p className="empty">Bấm vào một nhân vật, thành viên hoặc dòng nhật ký để xem chi tiết.</p>;

  if (selection.kind === 'task') {
    const task = tasks.find((t) => t.id === selection.id);
    if (!task) return <p className="empty">Không tìm thấy task {selection.id}.</p>;
    return <TaskCard task={task} agents={agents} onSelectAgent={onSelectAgent} onLocate={onLocate} />;
  }

  const a = agents.find((x) => x.id === selection.id);
  if (!a) return <p className="empty">Không tìm thấy thành viên.</p>;
  const cur = a.taskId ? tasks.find((t) => t.id === a.taskId) : null;
  const theirs = tasks.filter((t) => t.assignee === a.id && t.id !== cur?.id).sort((x, y) => y.updatedAt.localeCompare(x.updatedAt));
  return (
    <div className="agent-detail">
      <div className={`ad-head s-${a.status}`}>
        <PixelAvatar id={a.id} size={56} />
        <div>
          <h3>{a.name}</h3>
          <div className="muted">{a.role}</div>
          <div className="member-status">
            <span className="dot" />
            {STATUS_LABEL[a.status]}
            {a.status === 'working' && ` · ${ACTIVITY_VERB[a.activity]}`}
            {a.location === 'meeting' && ' · ở phòng họp'}
          </div>
        </div>
      </div>
      {onLocate && (
        <button className="btn-locate" onClick={() => onLocate(a.id)}>
          ◎ Tìm trong văn phòng
        </button>
      )}
      {a.note && <p className="td-desc">{a.note}</p>}
      {a.metrics && (
        <dl className="kv">
          {a.metrics.tasksDone != null && (<><dt>Task xong</dt><dd>{a.metrics.tasksDone}</dd></>)}
          {a.metrics.firstPassRate != null && (<><dt>Đạt lần đầu</dt><dd>{Math.round(a.metrics.firstPassRate * 100)}%</dd></>)}
          {a.metrics.avgSeconds != null && (<><dt>TB mỗi task</dt><dd>{Math.round(a.metrics.avgSeconds)} giây</dd></>)}
          {a.metrics.costUsd != null && (<><dt>Chi phí</dt><dd>${a.metrics.costUsd.toFixed(2)}</dd></>)}
        </dl>
      )}
      <div className="td-section">
        <h4>Task hiện tại</h4>
        {cur ? <TaskCard task={cur} agents={agents} onSelectAgent={onSelectAgent} /> : <p className="muted">Đang không có task.</p>}
      </div>
      {theirs.length > 0 && (
        <div className="td-section">
          <h4>Task khác</h4>
          <ul className="task-list">
            {theirs.map((t) => (
              <li key={t.id}>
                <button onClick={() => onSelectTask(t.id)}>
                  <span className={`chip t-${t.status}`}>{t.id}</span>
                  <span className="ellipsis">{t.title}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
