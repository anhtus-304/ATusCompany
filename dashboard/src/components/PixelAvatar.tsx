import { useMemo } from 'react';
import { lookFor, pixels, SPRITE_W } from '../scene/sprites';

/** Avatar pixel (phần đầu + vai) vẽ từ cùng sprite với nhân vật trong cảnh. */
export function PixelAvatar({ id, size = 36 }: { id: string; size?: number }) {
  const rects = useMemo(() => {
    const px = pixels(lookFor(id), 'sit').filter((p) => p.y < 12);
    return px.map((p, i) => (
      <rect key={i} x={p.x} y={p.y + 2} width={1.02} height={1.02} fill={`#${p.color.toString(16).padStart(6, '0')}`} />
    ));
  }, [id]);
  return (
    <svg className="pixel-avatar" width={size} height={size} viewBox={`-1 -1 ${SPRITE_W + 2} ${SPRITE_W + 2}`} shapeRendering="crispEdges" aria-hidden>
      {rects}
    </svg>
  );
}
