/** Bố cục cố định của văn phòng, tính theo đơn vị "thế giới" (WORLD_W × WORLD_H). */
import type { Agent, GroupId } from '../types';

export const WORLD_W = 1000;
export const WORLD_H = 640;
export const WALL_H = 96; // chiều cao tường phía trên
export const CORRIDOR_Y = 556; // lối đi chung phía dưới các phòng
export const PX = 3; // một pixel sprite = 3 đơn vị thế giới

export type DeskKind = 'code' | 'design' | 'test' | 'lead';

export interface Seat {
  kind: DeskKind;
  /** tâm mặt bàn */
  deskX: number;
  deskY: number;
  /** chân nhân vật khi ngồi */
  x: number;
  y: number;
  /** điểm đứng dậy để rời bàn */
  exit: { x: number; y: number };
}

export interface Room {
  id: GroupId;
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

export const ROOMS: Room[] = [
  { id: 'code', label: 'XƯỞNG CODE', x: 20, y: WALL_H, w: 356, h: 414 },
  { id: 'lead', label: 'BAN LÃNH ĐẠO', x: 386, y: WALL_H, w: 248, h: 414 },
  { id: 'creative', label: 'STUDIO SÁNG TẠO', x: 644, y: WALL_H, w: 336, h: 414 },
];

const codeDesk = (dx: number, dy: number): Seat => ({
  kind: 'code',
  deskX: dx,
  deskY: dy,
  x: dx + 20,
  y: dy - 2,
  exit: { x: dx + 64, y: dy - 2 },
});

export const LEAD_TABLE = { x: 510, y: 300, w: 190, h: 64 };

export const SEATS: Record<GroupId, Seat[]> = {
  lead: [
    {
      kind: 'lead',
      deskX: LEAD_TABLE.x,
      deskY: LEAD_TABLE.y,
      x: LEAD_TABLE.x,
      y: LEAD_TABLE.y - 22,
      exit: { x: 404, y: LEAD_TABLE.y - 22 },
    },
  ],
  code: [codeDesk(112, 230), codeDesk(276, 230), codeDesk(112, 412), codeDesk(276, 412)],
  creative: [
    { kind: 'design', deskX: 740, deskY: 230, x: 760, y: 228, exit: { x: 804, y: 228 } },
    { kind: 'test', deskX: 740, deskY: 412, x: 760, y: 410, exit: { x: 804, y: 410 } },
  ],
};

/** Chỗ đứng quanh bàn họp ban lãnh đạo. */
export const MEETING_SPOTS = [
  { x: 452, y: 384 },
  { x: 510, y: 388 },
  { x: 568, y: 384 },
  { x: 618, y: 300 },
  { x: 404, y: 300 },
];

/** Chỗ đứng dự phòng khi nhóm có nhiều agent hơn số bàn. */
const OVERFLOW = [
  { x: 180, y: 500 },
  { x: 880, y: 500 },
  { x: 330, y: 500 },
  { x: 700, y: 500 },
];

export interface Spot {
  x: number;
  y: number;
  seated: boolean;
  exit: { x: number; y: number };
  seat?: Seat;
}

/** Gán bàn cho từng agent theo thứ tự xuất hiện trong nhóm. */
export function assignSeats(agents: Agent[]): Map<string, Spot> {
  const used: Record<GroupId, number> = { lead: 0, code: 0, creative: 0 };
  let overflow = 0;
  const out = new Map<string, Spot>();
  for (const a of agents) {
    const list = SEATS[a.group] ?? [];
    const seat = list[used[a.group]++];
    if (seat) out.set(a.id, { x: seat.x, y: seat.y, seated: true, exit: seat.exit, seat });
    else {
      const p = OVERFLOW[overflow++ % OVERFLOW.length];
      out.set(a.id, { ...p, seated: false, exit: p });
    }
  }
  return out;
}

/** Đường đi: đứng dậy → ra lối đi chung → đi ngang → vào chỗ mới. */
export function route(from: { x: number; y: number }, fromExit: { x: number; y: number }, to: Spot) {
  const pts: { x: number; y: number }[] = [];
  const sameRoom = roomAt(fromExit.x) === roomAt(to.exit.x) && fromExit.y < CORRIDOR_Y - 40;
  if (Math.hypot(from.x - fromExit.x, from.y - fromExit.y) > 1) pts.push(fromExit);
  if (!sameRoom) {
    pts.push({ x: fromExit.x, y: CORRIDOR_Y });
    pts.push({ x: to.exit.x, y: CORRIDOR_Y });
  }
  pts.push(to.exit);
  pts.push({ x: to.x, y: to.y });
  return pts;
}

export function roomAt(x: number): GroupId | null {
  const r = ROOMS.find((r) => x >= r.x && x <= r.x + r.w);
  return r ? r.id : null;
}
