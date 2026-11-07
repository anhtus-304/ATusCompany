import { useEffect, useRef, useState } from 'react';
import type { Agent, Task } from '../types';
import { STATUS_LABEL } from '../types';
import { OfficeRenderer } from './OfficeRenderer';
import type { ThemeId } from './palette';

interface Props {
  agents: Agent[];
  tasks: Task[];
  theme: ThemeId;
  selectedAgentId: string | null;
  onSelectAgent: (id: string) => void;
}

/** Bọc OfficeRenderer (PixiJS) thành component React, kèm tooltip HTML khi di chuột. */
export function OfficeScene({ agents, tasks, theme, selectedAgentId, onSelectAgent }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<OfficeRenderer | null>(null);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);
  const selectRef = useRef(onSelectAgent);
  selectRef.current = onSelectAgent;

  useEffect(() => {
    const r = new OfficeRenderer();
    rendererRef.current = r;
    r.setHandlers({
      onHover: (id, pos) => setHover(id && pos ? { id, ...pos } : null),
      onSelect: (id) => selectRef.current(id),
    });
    r.init(hostRef.current!, theme);
    return () => {
      r.destroy();
      rendererRef.current = null;
    };
    // theme ban đầu; đổi theme xử lý ở effect riêng
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => rendererRef.current?.setTheme(theme), [theme]);
  useEffect(() => rendererRef.current?.update(agents, tasks), [agents, tasks]);
  useEffect(() => rendererRef.current?.setSelected(selectedAgentId), [selectedAgentId]);

  const ha = hover ? agents.find((a) => a.id === hover.id) : null;
  const ht = ha?.taskId ? tasks.find((t) => t.id === ha.taskId) : null;

  return (
    <div className="office-scene">
      <div className="office-canvas" ref={hostRef} />
      {hover && ha && (
        <div className="scene-tooltip" style={{ left: hover.x, top: hover.y }} role="tooltip">
          <div className="tt-name">{ha.name}</div>
          <div className="tt-role">{ha.role}</div>
          <div className={`tt-status s-${ha.status}`}>
            <span className="dot" /> {STATUS_LABEL[ha.status]}
          </div>
          <div className="tt-task">{ht ? `${ht.id} · ${ht.title}` : 'Chưa có task'}</div>
        </div>
      )}
    </div>
  );
}
