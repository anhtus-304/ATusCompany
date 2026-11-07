import { useCallback, useEffect, useState } from 'react';
import { Header, type View } from './components/Header';
import { IconLog, IconUsers } from './components/Icons';
import { useMediaQuery } from './hooks/useMediaQuery';
import { useOffice } from './hooks/useOffice';
import { AssignBar } from './panels/AssignBar';
import { RightPanel, type RightTab } from './panels/RightPanel';
import { TaskBoard } from './panels/TaskBoard';
import { TeamPanel } from './panels/TeamPanel';
import { OfficeScene } from './scene/OfficeScene';
import type { ThemeId } from './scene/palette';
import type { Selection, TaskStatus } from './types';

const load = <T,>(k: string, d: T): T => {
  try {
    const v = localStorage.getItem(k);
    return v ? (JSON.parse(v) as T) : d;
  } catch {
    return d;
  }
};
const save = (k: string, v: unknown) => {
  try {
    localStorage.setItem(k, JSON.stringify(v));
  } catch {
    /* bỏ qua */
  }
};

export default function App() {
  const office = useOffice();
  const narrow = useMediaQuery('(max-width: 1100px)');

  const [theme, setTheme] = useState<ThemeId>(() => load('vtd.theme', 'sky'));
  const [view, setView] = useState<View>('office');
  const [boardFocus, setBoardFocus] = useState<TaskStatus | null>(null);
  const [selection, setSelection] = useState<Selection>(null);
  const [tab, setTab] = useState<RightTab>('log');
  const [leftOpen, setLeftOpen] = useState(() => load('vtd.left', true));
  const [rightOpen, setRightOpen] = useState(() => load('vtd.right', true));
  const [drawer, setDrawer] = useState<'left' | 'right' | null>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    save('vtd.theme', theme);
  }, [theme]);
  useEffect(() => save('vtd.left', leftOpen), [leftOpen]);
  useEffect(() => save('vtd.right', rightOpen), [rightOpen]);
  useEffect(() => {
    if (!narrow) setDrawer(null);
  }, [narrow]);

  const select = useCallback(
    (s: Selection) => {
      setSelection(s);
      if (!s) return;
      setTab('detail');
      if (narrow) setDrawer('right');
      else setRightOpen(true);
    },
    [narrow],
  );
  const selectAgent = useCallback((id: string) => select({ kind: 'agent', id }), [select]);
  const selectTask = useCallback((id: string) => select({ kind: 'task', id }), [select]);

  const showLeft = narrow ? drawer === 'left' : leftOpen;
  const showRight = narrow ? drawer === 'right' : rightOpen;
  const selectedAgentId = selection?.kind === 'agent' ? selection.id : null;

  const left = (
    <TeamPanel
      agents={office.agents}
      tasks={office.tasks}
      selectedId={selectedAgentId}
      onSelectAgent={selectAgent}
      onSelectTask={selectTask}
      onCollapse={() => (narrow ? setDrawer(null) : setLeftOpen(false))}
      collapseLabel={narrow ? 'Đóng' : 'Thu gọn cột Đội ngũ'}
    />
  );
  const right = (
    <RightPanel
      tab={tab}
      onTab={setTab}
      log={office.log}
      agents={office.agents}
      tasks={office.tasks}
      selection={selection}
      onSelect={select}
      onCollapse={() => (narrow ? setDrawer(null) : setRightOpen(false))}
      collapseLabel={narrow ? 'Đóng' : 'Thu gọn cột Nhật ký'}
    />
  );

  return (
    <div className="app">
      <Header
        company={office.company}
        tasks={office.tasks}
        view={view}
        onView={setView}
        theme={theme}
        onTheme={setTheme}
        conn={office.conn}
        mock={office.mock}
        onStat={(s) => {
          setView('board');
          setBoardFocus(s);
        }}
      />

      <div className={narrow ? 'main is-narrow' : `main ${leftOpen ? '' : 'no-left'} ${rightOpen ? '' : 'no-right'}`}>
        {!narrow &&
          (leftOpen ? (
            left
          ) : (
            <button className="rail rail-left" onClick={() => setLeftOpen(true)} aria-label="Mở cột Đội ngũ" title="Mở cột Đội ngũ">
              <IconUsers />
              <span className="rail-text pixel">Đội ngũ</span>
            </button>
          ))}

        <main className="stage">
          {narrow && (
            <div className="stage-tools">
              <button onClick={() => setDrawer('left')}>
                <IconUsers /> Đội ngũ
              </button>
              <button onClick={() => setDrawer('right')}>
                <IconLog /> Nhật ký
              </button>
            </div>
          )}
          <div className={`stage-view ${view === 'office' ? '' : 'hidden'}`}>
            <OfficeScene
              agents={office.agents}
              tasks={office.tasks}
              theme={theme}
              selectedAgentId={selectedAgentId}
              onSelectAgent={selectAgent}
            />
          </div>
          {view === 'board' && (
            <div className="stage-view">
              <TaskBoard
                tasks={office.tasks}
                agents={office.agents}
                focus={boardFocus}
                selectedTaskId={selection?.kind === 'task' ? selection.id : null}
                onSelectTask={selectTask}
              />
            </div>
          )}
        </main>

        {!narrow &&
          (rightOpen ? (
            right
          ) : (
            <button className="rail rail-right" onClick={() => setRightOpen(true)} aria-label="Mở cột Nhật ký" title="Mở cột Nhật ký">
              <IconLog />
              <span className="rail-text pixel">Nhật ký</span>
            </button>
          ))}

        {narrow && (
          <>
            <div className={`backdrop ${drawer ? 'show' : ''}`} onClick={() => setDrawer(null)} />
            <div className={`drawer drawer-left ${showLeft ? 'open' : ''}`} aria-hidden={!showLeft}>
              {left}
            </div>
            <div className={`drawer drawer-right ${showRight ? 'open' : ''}`} aria-hidden={!showRight}>
              {right}
            </div>
          </>
        )}
      </div>

      <AssignBar agents={office.agents} onAssign={(to, text) => office.send({ type: 'assign', to, text })} />
    </div>
  );
}
