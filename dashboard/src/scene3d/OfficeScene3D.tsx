import { useEffect, useRef, useState } from 'react';
import type { Agent, Task } from '../types';
import { STATUS_LABEL } from '../types';
import type { ThemeId } from '../scene/palette';
import { Office3D } from './Office3D';

interface Props {
  agents: Agent[];
  tasks: Task[];
  theme: ThemeId;
  selectedAgentId: string | null;
  onSelectAgent: (id: string) => void;
  /** đổi giá trị để camera bay tới agent */
  focus: { id: string; n: number } | null;
}

/** Bọc Office3D (Three.js) thành component React, kèm nút điều khiển camera và tooltip. */
export function OfficeScene3D({ agents, tasks, theme, selectedAgentId, onSelectAgent, focus }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const ref = useRef<Office3D | null>(null);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);
  const selectRef = useRef(onSelectAgent);
  selectRef.current = onSelectAgent;
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const r = new Office3D();
    try {
      r.init(hostRef.current!, theme);
    } catch (err) {
      console.error('Không khởi tạo được WebGL', err);
      setFailed(true);
      return;
    }
    ref.current = r;
    r.setHandlers({
      onHover: (id, pos) => setHover(id && pos ? { id, ...pos } : null),
      onSelect: (id) => selectRef.current(id),
    });
    return () => {
      r.destroy();
      ref.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => ref.current?.setTheme(theme), [theme]);
  useEffect(() => ref.current?.update(agents, tasks), [agents, tasks]);
  useEffect(() => ref.current?.setSelected(selectedAgentId), [selectedAgentId]);
  useEffect(() => {
    if (focus) ref.current?.focus(focus.id);
  }, [focus]);

  const ha = hover ? agents.find((a) => a.id === hover.id) : null;
  const ht = ha?.taskId ? tasks.find((t) => t.id === ha.taskId) : null;

  return (
    <div className="office-scene">
      <div className="office-canvas" ref={hostRef} />
      {failed && <p className="empty scene-fallback">Trình duyệt không hỗ trợ WebGL. Hãy chuyển sang chế độ Pixel.</p>}
      <div className="cam-tools" role="toolbar" aria-label="Điều khiển camera">
        <button onClick={() => ref.current?.rotate(-1)} title="Xoay trái" aria-label="Xoay trái">⟲</button>
        <button onClick={() => ref.current?.rotate(1)} title="Xoay phải" aria-label="Xoay phải">⟳</button>
        <button onClick={() => ref.current?.zoom(0.8)} title="Phóng to" aria-label="Phóng to">+</button>
        <button onClick={() => ref.current?.zoom(1.25)} title="Thu nhỏ" aria-label="Thu nhỏ">−</button>
        <button onClick={() => ref.current?.resetView()} title="Về góc nhìn ban đầu" aria-label="Về góc nhìn ban đầu">⌂</button>
      </div>
      <div className="cam-hint">Kéo để xoay · chuột phải hoặc Shift+kéo để di chuyển · cuộn để phóng to</div>
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
