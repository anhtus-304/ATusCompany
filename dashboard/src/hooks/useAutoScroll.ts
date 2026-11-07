import { useEffect, useLayoutEffect, useRef, useState } from 'react';

/**
 * Tự cuộn xuống cuối khi có mục mới, trừ khi người dùng đang cuộn lên đọc.
 * Trả về số mục mới chưa xem để hiện nút "xuống cuối".
 */
export function useAutoScroll<T extends HTMLElement>(count: number) {
  const ref = useRef<T>(null);
  const pinned = useRef(true);
  const lastCount = useRef(count);
  const [unseen, setUnseen] = useState(0);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onScroll = () => {
      pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
      if (pinned.current) setUnseen(0);
    };
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  useLayoutEffect(() => {
    const el = ref.current;
    const added = count - lastCount.current;
    lastCount.current = count;
    if (!el) return;
    if (pinned.current) el.scrollTop = el.scrollHeight;
    else if (added > 0) setUnseen((u) => u + added);
  }, [count]);

  const toBottom = () => {
    const el = ref.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    pinned.current = true;
    setUnseen(0);
  };

  return { ref, unseen, toBottom };
}
