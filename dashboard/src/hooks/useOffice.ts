/**
 * Trạng thái dashboard + kết nối. Nếu có VITE_WS_URL thì dùng WebSocket thật
 * (tự kết nối lại), không thì dùng server giả lập trong mock/.
 */
import { useCallback, useEffect, useReducer, useRef, useState } from 'react';
import { createMockServer, type MockSocket } from '../mock/mockServer';
import type { Agent, ClientMessage, ConnectionState, LogEntry, ServerMessage, Task } from '../types';
import { fillAgent, normalize } from './normalize';

export interface OfficeState {
  company: string;
  agents: Agent[];
  tasks: Task[];
  log: LogEntry[];
}

const MAX_LOG = 300;

function reducer(s: OfficeState, m: ServerMessage): OfficeState {
  switch (m.type) {
    case 'snapshot':
      return { company: m.company ?? s.company, agents: m.agents, tasks: m.tasks, log: m.log.slice(-MAX_LOG) };
    case 'agent': {
      const i = s.agents.findIndex((a) => a.id === m.agent.id);
      const agents = [...s.agents];
      if (i >= 0) agents[i] = { ...agents[i], ...m.agent };
      else agents.push(fillAgent(m.agent));
      return { ...s, agents };
    }
    case 'task': {
      const i = s.tasks.findIndex((t) => t.id === m.task.id);
      const tasks = [...s.tasks];
      if (i >= 0) tasks[i] = m.task;
      else tasks.push(m.task);
      return { ...s, tasks };
    }
    case 'log':
      if (s.log.some((l) => l.id === m.entry.id)) return s;
      return { ...s, log: [...s.log, m.entry].slice(-MAX_LOG) };
  }
}

const WS_URL: string | undefined = import.meta.env.VITE_WS_URL || undefined;

export function useOffice() {
  const [state, dispatch] = useReducer(reducer, { company: 'Virtual Tech Dept', agents: [], tasks: [], log: [] });
  const [conn, setConn] = useState<ConnectionState>('connecting');
  const sendRef = useRef<(m: ClientMessage) => boolean>(() => false);

  useEffect(() => {
    if (!WS_URL) {
      const mock: MockSocket = createMockServer(dispatch, () => setConn('open'));
      sendRef.current = (m) => (mock.send(m), true);
      return () => mock.close();
    }

    let ws: WebSocket | null = null;
    let retry = 0;
    let timer: number | undefined;
    let stopped = false;

    const connect = () => {
      setConn('connecting');
      ws = new WebSocket(WS_URL);
      ws.onopen = () => {
        retry = 0;
        setConn('open');
      };
      ws.onmessage = (ev) => {
        try {
          const msg = normalize(JSON.parse(ev.data));
          if (msg) dispatch(msg);
        } catch (err) {
          console.warn('Bỏ qua tin nhắn WebSocket không hợp lệ', err);
        }
      };
      ws.onclose = () => {
        setConn('closed');
        if (stopped) return;
        const delay = Math.min(15000, 800 * 2 ** retry++);
        timer = window.setTimeout(connect, delay);
      };
      ws.onerror = () => ws?.close();
    };
    connect();
    sendRef.current = (m) => {
      if (ws?.readyState !== WebSocket.OPEN) return false;
      ws.send(JSON.stringify(m));
      return true;
    };
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      ws?.close();
    };
  }, []);

  const send = useCallback((m: ClientMessage) => sendRef.current(m), []);
  return { ...state, conn, send, mock: !WS_URL };
}
