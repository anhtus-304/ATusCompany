/**
 * Nhân vật pixel vẽ bằng ma trận ký tự, dùng chung cho cảnh PixiJS và avatar HTML.
 * Mỗi ký tự là một ô pixel; '.' là trong suốt.
 */

export interface Look {
  hair: number;
  skin: number;
  shirt: number;
  pants: number;
  hairStyle: 'short' | 'long' | 'spiky' | 'bun' | 'cap';
  extra?: 'glasses' | 'tie' | 'headphones' | 'beret' | 'none';
  extraColor?: number;
}

export const SPRITE_W = 12;

// Phần đầu + thân (dùng chung đứng/ngồi)
const HEAD = [
  '...hhhhhh...',
  '..hhhhhhhh..',
  '.hhhhhhhhhh.',
  '.hssssssssh.',
  '.ssessssess.',
  '.ssessssess.',
  '.skssssssks.',
  '..sssmmsss..',
  '...ssssss...',
];
const BODY = [
  '..cccCCccc..',
  '.cccccccccc.',
  'sccccCCccccs',
  'sccccCCccccs',
  '.cccccccccc.',
];
const LEGS_STAND = ['..pppppppp..', '..ppp..ppp..', '..ppp..ppp..', '..bbb..bbb..'];
const LEGS_WALK_A = ['..pppppppp..', '..ppp...pp..', '..ppp...pp..', '..bbb...bb..'];
const LEGS_WALK_B = ['..pppppppp..', '..pp...ppp..', '..pp...ppp..', '..bb...bbb..'];
const LAP = ['..pppppppp..', '..pppppppp..'];

export type Pose = 'stand' | 'walkA' | 'walkB' | 'sit' | 'sitType';

function base(pose: Pose): string[] {
  const body = [...BODY];
  if (pose === 'sitType') {
    // tay đưa ra trước để gõ phím
    body[2] = '.cccccCcccc.';
    body[3] = '.ssccCCccss.';
  }
  const legs =
    pose === 'walkA' ? LEGS_WALK_A : pose === 'walkB' ? LEGS_WALK_B : pose === 'stand' ? LEGS_STAND : LAP;
  return [...HEAD, ...body, ...legs];
}

type Cell = { x: number; y: number; k: string };

function overlays(look: Look): Cell[] {
  const c: Cell[] = [];
  const put = (x: number, y: number, k: string) => c.push({ x, y, k });
  switch (look.hairStyle) {
    case 'long':
      for (let y = 3; y <= 9; y++) {
        put(0, y, 'h');
        put(11, y, 'h');
      }
      put(1, 3, 'h');
      put(10, 3, 'h');
      break;
    case 'spiky':
      put(2, 0, 'h');
      put(5, -1, 'h');
      put(8, -1, 'h');
      put(10, 0, 'h');
      break;
    case 'bun':
      for (let x = 4; x <= 7; x++) put(x, -1, 'h');
      put(5, -2, 'h');
      put(6, -2, 'h');
      break;
    case 'cap':
      for (let x = 1; x <= 11; x++) put(x, 2, 'x');
      for (let x = 2; x <= 9; x++) put(x, 1, 'x');
      break;
    default:
      put(2, 3, 'h');
      put(3, 3, 'h');
  }
  switch (look.extra) {
    case 'glasses':
      for (const x of [2, 3, 4, 7, 8, 9]) put(x, 4, 'g');
      put(5, 4, 'g');
      put(6, 4, 'g');
      break;
    case 'tie':
      put(5, 10, 'x');
      put(6, 10, 'x');
      put(5, 11, 'x');
      put(6, 11, 'x');
      put(5, 12, 'x');
      put(6, 12, 'x');
      break;
    case 'headphones':
      for (let x = 1; x <= 10; x++) put(x, 0, 'x');
      put(0, 4, 'x');
      put(0, 5, 'x');
      put(11, 4, 'x');
      put(11, 5, 'x');
      put(0, 3, 'x');
      put(11, 3, 'x');
      break;
    case 'beret':
      for (let x = 1; x <= 10; x++) put(x, 0, 'x');
      for (let x = 2; x <= 11; x++) put(x, -1, 'x');
      put(6, -2, 'x');
      break;
  }
  return c;
}

const darken = (c: number, f = 0.75) => {
  const r = Math.round(((c >> 16) & 255) * f);
  const g = Math.round(((c >> 8) & 255) * f);
  const b = Math.round((c & 255) * f);
  return (r << 16) | (g << 8) | b;
};

export function colorFor(k: string, look: Look): number | null {
  switch (k) {
    case 'h':
      return look.hair;
    case 's':
      return look.skin;
    case 'e':
      return 0x2b2235;
    case 'k':
      return 0xf2a0a0;
    case 'm':
      return 0xc0605a;
    case 'c':
      return look.shirt;
    case 'C':
      return darken(look.shirt);
    case 'p':
      return look.pants;
    case 'b':
      return 0x3a2e2a;
    case 'g':
      return 0x30303a;
    case 'x':
      return look.extraColor ?? 0xe0483e;
    default:
      return null;
  }
}

/** Danh sách ô pixel (x, y, màu). y có thể âm (tóc búi, mũ nồi). */
export function pixels(look: Look, pose: Pose): { x: number; y: number; color: number }[] {
  const out: { x: number; y: number; color: number }[] = [];
  const rows = base(pose);
  const grid = new Map<string, string>();
  rows.forEach((row, y) => [...row].forEach((k, x) => k !== '.' && grid.set(`${x},${y}`, k)));
  for (const o of overlays(look)) {
    // kính không đè lên tóc hai bên
    grid.set(`${o.x},${o.y}`, o.k);
  }
  for (const [key, k] of grid) {
    const [x, y] = key.split(',').map(Number);
    const color = colorFor(k, look);
    if (color !== null) out.push({ x, y, color });
  }
  return out;
}

export function spriteRows(pose: Pose): number {
  return base(pose).length;
}

const LOOKS: Record<string, Look> = {
  leader: { hair: 0x3b2a20, skin: 0xf6d2b0, shirt: 0x2f3e66, pants: 0x2a2a35, hairStyle: 'short', extra: 'tie', extraColor: 0xe0483e },
  senior: { hair: 0x1f1c24, skin: 0xe9be98, shirt: 0x3e7bd6, pants: 0x34405a, hairStyle: 'short', extra: 'glasses' },
  junior: { hair: 0x6b3f22, skin: 0xf6d2b0, shirt: 0xf08c3a, pants: 0x3a4660, hairStyle: 'spiky' },
  intern: { hair: 0x2c2330, skin: 0xfadcbc, shirt: 0x53c08a, pants: 0x3a4660, hairStyle: 'cap', extraColor: 0xe9b949 },
  reviewer: { hair: 0x8a8f99, skin: 0xe2b48e, shirt: 0x7a5bc4, pants: 0x2f2f3f, hairStyle: 'short', extra: 'glasses' },
  designer: { hair: 0xb2456b, skin: 0xfadcbc, shirt: 0xf3d36b, pants: 0x4a3f5f, hairStyle: 'long', extra: 'beret', extraColor: 0xd94a6a },
  tester: { hair: 0x3a2a1e, skin: 0xd9a77f, shirt: 0x2fb5b0, pants: 0x34405a, hairStyle: 'bun', extra: 'headphones', extraColor: 0x2b2b38 },
};

const SHIRTS = [0x3e7bd6, 0xf08c3a, 0x53c08a, 0x7a5bc4, 0xe46b8a, 0x2fb5b0];
const HAIRS = [0x1f1c24, 0x6b3f22, 0x3b2a20, 0xb2456b, 0x8a8f99];
const STYLES: Look['hairStyle'][] = ['short', 'long', 'spiky', 'bun', 'cap'];

/** Ngoại hình theo id agent; agent lạ được sinh ngẫu nhiên ổn định từ id. */
export function lookFor(id: string): Look {
  if (LOOKS[id]) return LOOKS[id];
  let h = 0;
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return {
    hair: HAIRS[h % HAIRS.length],
    skin: [0xf6d2b0, 0xe9be98, 0xd9a77f][h % 3],
    shirt: SHIRTS[(h >> 3) % SHIRTS.length],
    pants: 0x34405a,
    hairStyle: STYLES[(h >> 5) % STYLES.length],
    extra: 'none',
  };
}
