import type { ReactElement } from 'react';
import type { ConnectionState, Task, TaskStatus } from '../types';
import { TASK_STATUS_LABEL, TASK_STATUS_ORDER } from '../types';
import { THEMES, type ThemeId } from '../scene/palette';
import { IconBlocked, IconDoing, IconDone, IconError, IconReview, IconTodo } from './Icons';

const STAT_ICON: Record<TaskStatus, () => ReactElement> = {
  todo: () => <IconTodo />,
  doing: () => <IconDoing />,
  review: () => <IconReview />,
  blocked: () => <IconBlocked />,
  error: () => <IconError />,
  done: () => <IconDone />,
};

export type View = 'office' | 'board';

interface Props {
  company: string;
  tasks: Task[];
  view: View;
  onView: (v: View) => void;
  theme: ThemeId;
  onTheme: (t: ThemeId) => void;
  conn: ConnectionState;
  mock: boolean;
  onStat: (s: TaskStatus) => void;
}

const CONN_LABEL: Record<ConnectionState, string> = {
  open: 'Đã kết nối',
  connecting: 'Đang kết nối…',
  closed: 'Mất kết nối',
};

export function Header({ company, tasks, view, onView, theme, onTheme, conn, mock, onStat }: Props) {
  const counts = TASK_STATUS_ORDER.map((s) => [s, tasks.filter((t) => t.status === s).length] as const);
  return (
    <header className="app-header">
      <div className="brand">
        <div className="brand-logo" aria-hidden>
          <span />
        </div>
        <div>
          <div className="brand-title pixel">VĂN PHÒNG</div>
          <div className="brand-company">{company}</div>
        </div>
      </div>

      <div className="stats" role="list" aria-label="Thống kê công việc">
        {counts.map(([s, n]) => (
          <button key={s} className={`stat stat-${s}`} role="listitem" onClick={() => onStat(s)} title={`Xem ${TASK_STATUS_LABEL[s]} trên Bảng việc`}>
            <span className="stat-icon">{STAT_ICON[s]()}</span>
            <span className="stat-num">{n}</span>
            <span className="stat-label">{TASK_STATUS_LABEL[s]}</span>
          </button>
        ))}
      </div>

      <div className="header-right">
        <div className="seg" role="tablist" aria-label="Chế độ xem">
          <button role="tab" aria-selected={view === 'office'} className={view === 'office' ? 'on' : ''} onClick={() => onView('office')}>
            Văn phòng
          </button>
          <button role="tab" aria-selected={view === 'board'} className={view === 'board' ? 'on' : ''} onClick={() => onView('board')}>
            Bảng việc
          </button>
        </div>
        <label className="theme-picker">
          <span className="sr-only">Theme</span>
          <select value={theme} onChange={(e) => onTheme(e.target.value as ThemeId)}>
            {THEMES.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <div className={`conn conn-${conn}`} title={mock ? 'Đang chạy dữ liệu mock (chưa đặt VITE_WS_URL)' : undefined}>
          <span className="dot" />
          {CONN_LABEL[conn]}
          {mock && <span className="conn-mock">mock</span>}
        </div>
      </div>
    </header>
  );
}
