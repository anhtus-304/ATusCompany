import { useAutoScroll } from '../hooks/useAutoScroll';
import type { Agent, LogEntry } from '../types';

interface Props {
  log: LogEntry[];
  agents: Agent[];
  onPick: (e: LogEntry) => void;
}

const time = (iso: string) => new Date(iso).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

export function LogPanel({ log, agents, onPick }: Props) {
  const { ref, unseen, toBottom } = useAutoScroll<HTMLOListElement>(log.length);
  const name = (id: string | null) => (id ? agents.find((a) => a.id === id)?.name ?? id : 'Sếp');
  return (
    <div className="log-wrap">
      <ol className="log" ref={ref} aria-live="polite">
        {log.map((e) => (
          <li key={e.id} className={`log-row k-${e.kind}`}>
            <button onClick={() => onPick(e)}>
              <time>{time(e.ts)}</time>
              <span className="log-agent">{name(e.agentId)}</span>
              <span className="log-text">{e.text}</span>
            </button>
          </li>
        ))}
        {!log.length && <li className="empty">Chưa có sự kiện.</li>}
      </ol>
      {unseen > 0 && (
        <button className="new-pill" onClick={toBottom}>
          {unseen} sự kiện mới ↓
        </button>
      )}
    </div>
  );
}
