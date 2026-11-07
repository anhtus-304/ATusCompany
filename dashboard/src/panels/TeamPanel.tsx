import { useMemo, useState } from 'react';
import { PixelAvatar } from '../components/PixelAvatar';
import { IconLeft, IconSearch } from '../components/Icons';
import type { Agent, Task } from '../types';
import { GROUPS, STATUS_LABEL } from '../types';

interface Props {
  agents: Agent[];
  tasks: Task[];
  selectedId: string | null;
  onSelectAgent: (id: string) => void;
  onSelectTask: (id: string) => void;
  onCollapse: () => void;
  collapseLabel: string;
}

const norm = (s: string) =>
  s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/đ/g, 'd');

export function TeamPanel({ agents, tasks, selectedId, onSelectAgent, onSelectTask, onCollapse, collapseLabel }: Props) {
  const [q, setQ] = useState('');
  const nq = norm(q.trim());

  const { matchAgents, matchTasks } = useMemo(() => {
    if (!nq) return { matchAgents: agents, matchTasks: [] as Task[] };
    const mt = tasks.filter((t) => norm(`${t.id} ${t.title}`).includes(nq));
    const ma = agents.filter(
      (a) => norm(`${a.name} ${a.role} ${a.note} ${a.taskId ?? ''}`).includes(nq) || mt.some((t) => t.assignee === a.id),
    );
    return { matchAgents: ma, matchTasks: mt };
  }, [agents, tasks, nq]);

  return (
    <aside className="panel team-panel" aria-label="Đội ngũ">
      <div className="panel-head">
        <h2 className="pixel">Đội ngũ</h2>
        <span className="muted">{agents.length} thành viên</span>
        <button className="icon-btn" onClick={onCollapse} aria-label={collapseLabel} title={collapseLabel}>
          <IconLeft />
        </button>
      </div>
      <label className="search">
        <IconSearch size={14} />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tìm thành viên hoặc công việc" />
      </label>

      <div className="panel-scroll">
        {matchTasks.length > 0 && (
          <section className="group">
            <div className="group-head g-task">
              <span className="group-label">Công việc</span>
              <span className="group-count">{matchTasks.length}</span>
            </div>
            {matchTasks.map((t) => (
              <button key={t.id} className="task-hit" onClick={() => onSelectTask(t.id)}>
                <span className={`chip t-${t.status}`}>{t.id}</span>
                <span className="ellipsis">{t.title}</span>
              </button>
            ))}
          </section>
        )}
        {GROUPS.map((g) => {
          const list = matchAgents.filter((a) => a.group === g.id);
          const total = agents.filter((a) => a.group === g.id).length;
          if (!list.length) return null;
          return (
            <section key={g.id} className="group">
              <div className={`group-head g-${g.id}`}>
                <span className="group-label">{g.label}</span>
                <span className="group-count">{total}</span>
              </div>
              {list.map((a) => (
                <button
                  key={a.id}
                  className={`member s-${a.status} ${selectedId === a.id ? 'selected' : ''}`}
                  onClick={() => onSelectAgent(a.id)}
                >
                  <PixelAvatar id={a.id} />
                  <span className="member-body">
                    <span className="member-top">
                      <span className="member-name">{a.name}</span>
                      <span className="member-status">
                        <span className="dot" />
                        {STATUS_LABEL[a.status]}
                      </span>
                    </span>
                    <span className="member-role">{a.role}</span>
                    <span className="member-note ellipsis">
                      {a.taskId && <b>{a.taskId}{a.note ? ' · ' : ''}</b>}
                      {a.note}
                    </span>
                  </span>
                </button>
              ))}
            </section>
          );
        })}
        {!matchAgents.length && !matchTasks.length && <p className="empty">Không tìm thấy “{q}”.</p>}
      </div>
    </aside>
  );
}
