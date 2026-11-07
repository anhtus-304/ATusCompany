import { IconRight } from '../components/Icons';
import type { Agent, LogEntry, Selection, Task } from '../types';
import { DetailPanel } from './DetailPanel';
import { LogPanel } from './LogPanel';

export type RightTab = 'log' | 'detail';

interface Props {
  tab: RightTab;
  onTab: (t: RightTab) => void;
  log: LogEntry[];
  agents: Agent[];
  tasks: Task[];
  selection: Selection;
  onSelect: (s: Selection) => void;
  onCollapse: () => void;
  collapseLabel: string;
}

export function RightPanel({ tab, onTab, log, agents, tasks, selection, onSelect, onCollapse, collapseLabel }: Props) {
  return (
    <aside className="panel right-panel" aria-label="Nhật ký và chi tiết">
      <div className="panel-head">
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === 'log'} className={tab === 'log' ? 'on' : ''} onClick={() => onTab('log')}>
            Nhật ký
          </button>
          <button role="tab" aria-selected={tab === 'detail'} className={tab === 'detail' ? 'on' : ''} onClick={() => onTab('detail')}>
            Chi tiết
          </button>
        </div>
        <button className="icon-btn" onClick={onCollapse} aria-label={collapseLabel} title={collapseLabel}>
          <IconRight />
        </button>
      </div>
      {tab === 'log' ? (
        <LogPanel
          log={log}
          agents={agents}
          onPick={(e) => {
            onSelect(e.taskId ? { kind: 'task', id: e.taskId } : e.agentId ? { kind: 'agent', id: e.agentId } : null);
            onTab('detail');
          }}
        />
      ) : (
        <div className="panel-scroll detail-scroll">
          <DetailPanel
            selection={selection}
            agents={agents}
            tasks={tasks}
            onSelectAgent={(id) => onSelect({ kind: 'agent', id })}
            onSelectTask={(id) => onSelect({ kind: 'task', id })}
          />
        </div>
      )}
    </aside>
  );
}
