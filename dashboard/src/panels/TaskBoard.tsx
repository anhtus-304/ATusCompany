import { useEffect, useRef } from 'react';
import { PixelAvatar } from '../components/PixelAvatar';
import type { Agent, Task, TaskStatus } from '../types';
import { TASK_STATUS_LABEL, TASK_STATUS_ORDER } from '../types';

interface Props {
  tasks: Task[];
  agents: Agent[];
  focus: TaskStatus | null;
  selectedTaskId: string | null;
  onSelectTask: (id: string) => void;
}

/** Chế độ "Bảng việc": các cột theo trạng thái task. */
export function TaskBoard({ tasks, agents, focus, selectedTaskId, onSelectTask }: Props) {
  const colRefs = useRef<Partial<Record<TaskStatus, HTMLElement | null>>>({});
  useEffect(() => {
    if (focus) colRefs.current[focus]?.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
  }, [focus]);
  return (
    <div className="board">
      {TASK_STATUS_ORDER.map((s) => {
        const list = tasks.filter((t) => t.status === s).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
        return (
          <section key={s} ref={(el) => void (colRefs.current[s] = el)} className={`board-col col-${s} ${focus === s ? 'focus' : ''}`}>
            <h3>
              <span className={`chip t-${s}`}>{TASK_STATUS_LABEL[s]}</span>
              <span className="muted">{list.length}</span>
            </h3>
            <div className="board-list">
              {list.map((t) => {
                const a = agents.find((x) => x.id === t.assignee);
                return (
                  <button key={t.id} className={`board-card ${selectedTaskId === t.id ? 'selected' : ''}`} onClick={() => onSelectTask(t.id)}>
                    <span className="pixel bc-code">{t.id}</span>
                    <span className="bc-title">{t.title}</span>
                    <span className="bc-who">
                      {a && <PixelAvatar id={a.id} size={20} />}
                      {a?.name ?? t.assignee}
                    </span>
                  </button>
                );
              })}
              {!list.length && <p className="empty small">Trống</p>}
            </div>
          </section>
        );
      })}
    </div>
  );
}
