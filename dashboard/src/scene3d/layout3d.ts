/**
 * Mặt bằng văn phòng 3D (đơn vị mét). Trục x sang phải, trục z hướng về phía camera.
 * Sàn rộng 28 × 18: Xưởng code bên trái, Studio sáng tạo ở giữa phía sau,
 * phòng kính Ban lãnh đạo bên phải phía trước, góc nghỉ phía trước bên trái.
 */
import type { Agent, GroupId } from '../types';

export const FLOOR_W = 28;
export const FLOOR_D = 18;
export const AISLE_Z = 1.8; // lối đi chung chạy ngang sàn

export type DeskKind = 'code' | 'design' | 'test' | 'lead';
export type ZoneId = GroupId | 'lounge';

export interface Zone {
  id: ZoneId;
  label: string;
  x0: number;
  x1: number;
  z0: number;
  z1: number;
}

export const ZONES: Zone[] = [
  { id: 'code', label: 'Xưởng code', x0: -12.6, x1: -1.6, z0: -7.6, z1: 1.0 },
  { id: 'creative', label: 'Studio sáng tạo', x0: 0.6, x1: 10.2, z0: -7.6, z1: 0.4 },
  { id: 'lead', label: 'Ban lãnh đạo', x0: 3.2, x1: 12.6, z0: 2.8, z1: 8.4 },
  { id: 'lounge', label: 'Góc nghỉ', x0: -12.6, x1: 1.6, z0: 3.0, z1: 8.4 },
];

/** Cửa phòng kính Ban lãnh đạo (trên vách phía sau). */
export const LEAD_DOOR = { x: 4.7, outZ: AISLE_Z, inZ: 3.5, w: 1.6 };
export const LEAD_TABLE = { x: 8.2, z: 5.6, w: 4.2, d: 1.4 };

export interface Desk3D {
  kind: DeskKind;
  x: number;
  z: number;
  /** chỗ robot đứng làm việc */
  stand: { x: number; z: number; face: number };
  /** làn đi dọc bên cạnh bàn để ra lối đi chung */
  laneX: number;
}

const desk = (kind: DeskKind, x: number, z: number, laneX: number): Desk3D => ({
  kind,
  x,
  z,
  stand: { x, z: z + 0.95, face: Math.PI },
  laneX,
});

export const DESKS: Record<GroupId, Desk3D[]> = {
  code: [
    desk('code', -9.6, -4.9, -7.1),
    desk('code', -4.6, -4.9, -7.1),
    desk('code', -9.6, -1.2, -12.2),
    desk('code', -4.6, -1.2, -2.1),
  ],
  creative: [desk('design', 3.0, -4.4, 5.0), desk('test', 7.4, -4.4, 5.0)],
  lead: [
    {
      kind: 'lead',
      x: LEAD_TABLE.x,
      z: LEAD_TABLE.z,
      stand: { x: LEAD_TABLE.x, z: LEAD_TABLE.z - 1.05, face: 0 },
      laneX: LEAD_DOOR.x,
    },
  ],
};

export const MEETING_SPOTS = [
  { x: 7.2, z: 6.75, face: Math.PI },
  { x: 9.2, z: 6.75, face: Math.PI },
  { x: 5.6, z: 5.6, face: Math.PI / 2 },
  { x: 10.8, z: 5.6, face: -Math.PI / 2 },
  { x: 8.2, z: 6.75, face: Math.PI },
];

const LOUNGE_SPOTS = [
  { x: -8.5, z: 6.4, face: 0.4 },
  { x: -3.5, z: 6.4, face: -0.4 },
  { x: -6, z: 4.4, face: 0 },
];

export interface Spot3D {
  x: number;
  z: number;
  face: number;
  zone: ZoneId;
  /** x của làn đi dọc trong khu */
  laneX: number;
  desk?: Desk3D;
}

export function zoneAt(x: number, z: number): ZoneId | null {
  const zn = ZONES.find((zz) => x >= zz.x0 - 0.3 && x <= zz.x1 + 0.3 && z >= zz.z0 - 0.3 && z <= zz.z1 + 0.3);
  return zn ? zn.id : null;
}

export function homeSpots(agents: Agent[]): Map<string, Spot3D> {
  const used: Record<GroupId, number> = { lead: 0, code: 0, creative: 0 };
  let extra = 0;
  const out = new Map<string, Spot3D>();
  for (const a of agents) {
    const d = (DESKS[a.group] ?? [])[used[a.group]++];
    if (d) out.set(a.id, { ...d.stand, zone: a.group, laneX: d.laneX, desk: d });
    else {
      const p = LOUNGE_SPOTS[extra++ % LOUNGE_SPOTS.length];
      out.set(a.id, { ...p, zone: 'lounge', laneX: p.x });
    }
  }
  return out;
}

export function meetingSpot(i: number): Spot3D {
  const p = MEETING_SPOTS[i % MEETING_SPOTS.length];
  return { ...p, zone: 'lead', laneX: LEAD_DOOR.x };
}

type P = { x: number; z: number };

/** Các điểm trên đường từ một chỗ ra lối đi chung (hoặc ngược lại). */
function toAisle(p: P, s: { zone: ZoneId; laneX: number }): P[] {
  if (s.zone === 'lead') {
    const pts: P[] = [];
    if (p.z > LEAD_TABLE.z - 0.75) {
      if (p.x > LEAD_TABLE.x + LEAD_TABLE.w / 2) pts.push({ x: p.x, z: 4.1 });
      else pts.push({ x: LEAD_DOOR.x, z: p.z });
    }
    pts.push({ x: LEAD_DOOR.x, z: LEAD_DOOR.inZ }, { x: LEAD_DOOR.x, z: LEAD_DOOR.outZ });
    return pts;
  }
  if (s.zone === 'lounge') return [{ x: p.x, z: AISLE_Z + 0.4 }];
  return [{ x: s.laneX, z: p.z }, { x: s.laneX, z: AISLE_Z }];
}

/** Đường đi không xuyên bàn: ra làn → lối đi chung → làn khu đích → chỗ đích. */
export function route3d(from: P, fromSpot: { zone: ZoneId; laneX: number }, to: Spot3D): P[] {
  const sameRoom = fromSpot.zone === 'lead' && to.zone === 'lead';
  if (sameRoom) {
    const pts: P[] = [];
    if ((from.z < LEAD_TABLE.z) !== (to.z < LEAD_TABLE.z)) {
      const side = to.x < LEAD_TABLE.x ? LEAD_TABLE.x - LEAD_TABLE.w / 2 - 0.7 : LEAD_TABLE.x + LEAD_TABLE.w / 2 + 0.7;
      pts.push({ x: side, z: from.z }, { x: side, z: to.z });
    }
    pts.push({ x: to.x, z: to.z });
    return pts;
  }
  const out = toAisle(from, fromSpot);
  const back = toAisle({ x: to.x, z: to.z }, to).reverse();
  return [...out, ...back, { x: to.x, z: to.z }];
}
