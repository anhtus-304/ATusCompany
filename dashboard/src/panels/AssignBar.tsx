import { useEffect, useRef, useState } from 'react';
import type { Agent } from '../types';

interface Props {
  agents: Agent[];
  onAssign: (to: string, text: string) => boolean;
}

export function AssignBar({ agents, onAssign }: Props) {
  const [to, setTo] = useState('leader');
  const [text, setText] = useState('');
  const [err, setErr] = useState('');
  const ta = useRef<HTMLTextAreaElement>(null);
  const target = agents.find((a) => a.id === to) ?? agents[0];

  useEffect(() => {
    if (agents.length && !agents.find((a) => a.id === to)) setTo((agents.find((a) => a.group === 'lead') ?? agents[0]).id);
  }, [agents, to]);

  useEffect(() => {
    const el = ta.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, [text]);

  const submit = () => {
    const v = text.trim();
    if (!v || !target) return;
    if (onAssign(target.id, v)) {
      setText('');
      setErr('');
    } else setErr('Chưa kết nối server, chưa gửi được.');
  };

  return (
    <form
      className="assign-bar"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <label className="assign-to">
        <span className="sr-only">Người nhận</span>
        <select value={target?.id ?? ''} onChange={(e) => setTo(e.target.value)}>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.group === 'lead' ? 'Leader' : a.name}
            </option>
          ))}
        </select>
      </label>
      <textarea
        ref={ta}
        rows={1}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            submit();
          }
        }}
        placeholder={`Giao việc cho ${target?.group === 'lead' ? 'Leader' : target?.name ?? '...'}... Enter để gửi, Shift+Enter xuống dòng`}
        aria-label="Nội dung công việc"
      />
      {err && <span className="assign-err">{err}</span>}
      <button type="submit" className="btn-assign" disabled={!text.trim()}>
        Giao việc
      </button>
    </form>
  );
}
