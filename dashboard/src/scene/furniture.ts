/** Vẽ phần tĩnh của văn phòng: sàn, tường, cửa sổ, đồ đạc. Tất cả là khối pixel bằng Graphics. */
import { Container, Graphics, Text } from 'pixi.js';
import { CORRIDOR_Y, LEAD_TABLE, ROOMS, SEATS, WALL_H, WORLD_H, WORLD_W, type Seat } from './layout';
import type { ScenePalette } from './palette';

export const PIXEL_FONT = 'VT323, "Be Vietnam Pro", monospace';

type G = Graphics;
const r = (g: G, x: number, y: number, w: number, h: number, c: number, a = 1) =>
  g.rect(Math.round(x), Math.round(y), Math.round(w), Math.round(h)).fill({ color: c, alpha: a });

/** Khối có viền tối 2px (phong cách pixel). */
const box = (g: G, x: number, y: number, w: number, h: number, c: number, edge: number) => {
  r(g, x, y, w, h, edge);
  r(g, x + 2, y + 2, w - 4, h - 4, c);
};

export function pixelText(text: string, size: number, color: number, bold = false) {
  const t = new Text({
    text,
    style: { fontFamily: PIXEL_FONT, fontSize: size, fill: color, fontWeight: bold ? '700' : '400' },
  });
  t.resolution = 3;
  return t;
}

/* ---------------- Sàn và tường (lớp nền, không sắp xếp z) ---------------- */

export function drawBackground(p: ScenePalette): Container {
  const c = new Container();
  const g = new Graphics();
  c.addChild(g);

  // sàn gỗ: các tấm ván so le
  const plank = 16;
  for (let y = WALL_H, row = 0; y < WORLD_H; y += plank, row++) {
    r(g, 0, y, WORLD_W, plank, row % 2 ? p.floorA : p.floorB);
    r(g, 0, y + plank - 2, WORLD_W, 2, p.floorLine);
    for (let x = (row % 3) * 40; x < WORLD_W; x += 120) r(g, x, y, 2, plank - 2, p.floorLine);
  }

  // thảm từng phòng
  const carpet = (x: number, y: number, w: number, h: number, fill: number, edge: number, dots: boolean) => {
    r(g, x, y, w, h, edge);
    r(g, x + 4, y + 4, w - 8, h - 8, fill);
    if (dots)
      for (let yy = y + 14; yy < y + h - 8; yy += 16)
        for (let xx = x + 14 + ((yy / 16) % 2) * 8; xx < x + w - 8; xx += 16) r(g, xx, yy, 2, 2, edge, 0.55);
  };
  const [code, lead, studio] = ROOMS;
  carpet(code.x + 6, code.y + 22, code.w - 12, code.h - 34, p.codeCarpet, p.codeCarpetEdge, true);
  carpet(studio.x + 6, studio.y + 22, studio.w - 12, studio.h - 34, p.studioCarpet, p.studioCarpetEdge, true);
  // thảm dưới bàn họp
  carpet(lead.x + 12, LEAD_TABLE.y - 90, lead.w - 24, 210, p.leadRug, p.leadRugEdge, false);
  for (let x = lead.x + 22; x < lead.x + lead.w - 22; x += 12) {
    r(g, x, LEAD_TABLE.y - 84, 6, 2, p.leadRugEdge);
    r(g, x, LEAD_TABLE.y + 114, 6, 2, p.leadRugEdge);
  }
  // thảm lối đi
  carpet(330, CORRIDOR_Y - 18, 340, 40, p.leadRugEdge, p.wood, false);

  // tường trên
  r(g, 0, 0, WORLD_W, WALL_H, p.wall);
  for (let x = 0; x < WORLD_W; x += 24) r(g, x, 0, 12, WALL_H - 14, p.wallShade, 0.35);
  r(g, 0, WALL_H - 14, WORLD_W, 4, p.wallTrim);
  r(g, 0, WALL_H - 10, WORLD_W, 10, p.wallShade);
  r(g, 0, WALL_H - 2, WORLD_W, 2, p.wallTrim);
  // tường hai bên
  r(g, 0, WALL_H, 8, WORLD_H - WALL_H, p.wallShade);
  r(g, WORLD_W - 8, WALL_H, 8, WORLD_H - WALL_H, p.wallShade);

  // cửa sổ
  const win = (x: number, w: number) => {
    box(g, x, 14, w, 56, p.windowSky, p.wallTrim);
    r(g, x + 2, 14, w - 4, 4, p.window);
    r(g, x + w / 2 - 1, 16, 3, 52, p.window);
    r(g, x + 2, 40, w - 4, 3, p.window);
    // mây
    r(g, x + 10, 26, 16, 5, 0xffffff, 0.85);
    r(g, x + 14, 22, 8, 4, 0xffffff, 0.85);
    r(g, x + w - 30, 50, 14, 4, 0xffffff, 0.7);
    r(g, x - 4, 70, w + 8, 4, p.wallTrim); // bậu cửa
  };
  win(40, 92);
  win(176, 92);
  win(668, 92);
  win(804, 92);

  // bảng trắng phòng lãnh đạo
  box(g, 432, 12, 156, 62, 0xffffff, 0x8a8f99);
  r(g, 442, 24, 50, 3, 0x3b82f6);
  r(g, 442, 32, 70, 3, 0x9aa3b2);
  r(g, 442, 40, 60, 3, 0x9aa3b2);
  r(g, 442, 52, 30, 12, 0x53c08a, 0.7);
  r(g, 476, 46, 30, 18, 0xf08c3a, 0.7);
  r(g, 510, 38, 30, 26, 0x3b82f6, 0.7);
  r(g, 548, 20, 14, 14, 0xffe27a); // giấy note
  r(g, 566, 22, 14, 14, 0xffb3c7);
  r(g, 552, 40, 14, 14, 0xb5e2ff);
  r(g, 436, 74, 148, 4, 0x8a8f99);

  // đồng hồ
  box(g, 604, 18, 20, 20, 0xffffff, p.woodDark);
  r(g, 613, 22, 2, 7, 0x2b2235);
  r(g, 613, 28, 6, 2, 0x2b2235);

  // biển tên phòng gắn tường
  for (const room of ROOMS) {
    const label = pixelText(room.label, 16, p.labelText);
    const w = Math.ceil(label.width) + 16;
    const x = room.x + room.w / 2 - w / 2;
    const plate = new Graphics();
    box(plate, x, WALL_H + 2, w, 20, p.label, p.label === 0x60a5fa ? 0x1e3a8a : 0x1b1f2b);
    label.position.set(x + 8, WALL_H + 3);
    c.addChild(plate, label);
  }

  return c;
}

/* ---------------- Đồ đạc (lớp thế giới, sắp xếp theo y) ---------------- */

function at(z: number, g: Graphics) {
  g.zIndex = z;
  return g;
}

export function partition(x: number, p: ScenePalette) {
  const g = new Graphics();
  const top = WALL_H;
  const bottom = 480;
  r(g, x - 5, top, 10, bottom - top, p.partitionTop);
  r(g, x - 5, top, 2, bottom - top, p.wallTrim, 0.5);
  r(g, x + 3, top, 2, bottom - top, p.wallTrim, 0.5);
  r(g, x - 5, bottom, 10, 18, p.partition);
  r(g, x - 5, bottom + 16, 10, 2, p.wallTrim);
  return at(bottom + 18, g);
}

export function plant(x: number, y: number, size = 1) {
  const g = new Graphics();
  const s = size;
  // lá
  const leaf = (lx: number, ly: number, w: number, h: number, c: number) => r(g, x + lx * s, y + ly * s, w * s, h * s, c);
  leaf(-14, -44, 10, 16, 0x3f9a4a);
  leaf(4, -46, 10, 18, 0x3f9a4a);
  leaf(-8, -54, 16, 20, 0x56b85e);
  leaf(-18, -32, 12, 10, 0x56b85e);
  leaf(6, -32, 12, 10, 0x56b85e);
  leaf(-4, -60, 8, 10, 0x7fd37f);
  leaf(-2, -40, 4, 18, 0x2f7a3a);
  // chậu
  r(g, x - 12 * s, y - 22 * s, 24 * s, 6 * s, 0xc4683f);
  r(g, x - 10 * s, y - 16 * s, 20 * s, 16 * s, 0xd97a4a);
  r(g, x - 10 * s, y - 16 * s, 4 * s, 16 * s, 0xb85c35);
  return at(y, g);
}

export function bookshelf(x: number, y: number, w: number, p: ScenePalette) {
  const g = new Graphics();
  const h = 70;
  box(g, x, y - h, w, h, p.wood, p.woodDark);
  const colors = [0xe0483e, 0x3b82f6, 0xf3d36b, 0x53c08a, 0x7a5bc4, 0xf08c3a, 0xffffff];
  for (let shelf = 0; shelf < 3; shelf++) {
    const sy = y - h + 6 + shelf * 21;
    r(g, x + 4, sy + 16, w - 8, 3, p.woodDark);
    let bx = x + 6;
    let i = shelf * 3;
    while (bx < x + w - 10) {
      const bw = 4 + ((i * 7) % 4);
      const bh = 10 + ((i * 5) % 6);
      r(g, bx, sy + 16 - bh, bw, bh, colors[i % colors.length]);
      bx += bw + 1;
      i++;
    }
  }
  return at(y, g);
}

export function printer(x: number, y: number) {
  const g = new Graphics();
  box(g, x - 26, y - 22, 52, 22, 0x9aa3b2, 0x5b6170); // tủ
  box(g, x - 22, y - 44, 44, 24, 0xe8ebf0, 0x5b6170); // máy
  r(g, x - 16, y - 50, 32, 8, 0xffffff); // giấy
  r(g, x - 14, y - 47, 20, 1, 0x9aa3b2);
  r(g, x + 10, y - 38, 6, 3, 0x53c08a);
  r(g, x - 16, y - 30, 32, 4, 0x3a3f4b);
  return at(y, g);
}

export function waterCooler(x: number, y: number) {
  const g = new Graphics();
  box(g, x - 12, y - 34, 24, 34, 0xe8ebf0, 0x5b6170);
  r(g, x - 9, y - 58, 18, 24, 0x8fd0ff, 0.9);
  r(g, x - 9, y - 58, 4, 24, 0xc4e8ff);
  r(g, x - 4, y - 62, 8, 4, 0x3b82f6);
  r(g, x - 6, y - 26, 4, 4, 0xe0483e);
  r(g, x + 2, y - 26, 4, 4, 0x3b82f6);
  return at(y, g);
}

export function sofa(x: number, y: number, color: number) {
  const g = new Graphics();
  const dark = 0x5b6170;
  box(g, x - 60, y - 40, 120, 22, color, dark); // lưng
  box(g, x - 64, y - 24, 128, 24, color, dark); // đệm
  r(g, x - 2, y - 22, 2, 20, dark, 0.4);
  box(g, x - 68, y - 34, 12, 34, color, dark);
  box(g, x + 56, y - 34, 12, 34, color, dark);
  r(g, x - 40, y - 36, 18, 12, 0xffe27a); // gối
  return at(y, g);
}

export function chair(x: number, y: number, color: number) {
  const g = new Graphics();
  r(g, x - 15, y - 44, 30, 30, 0x2b2b38);
  r(g, x - 13, y - 42, 26, 26, color);
  r(g, x - 13, y - 42, 26, 4, 0xffffff, 0.25);
  r(g, x - 3, y - 14, 6, 8, 0x2b2b38);
  return at(y - 1, g);
}

/** Bàn làm việc; màn hình là Graphics riêng (được vẽ lại khi agent làm việc). */
export function desk(seat: Seat, p: ScenePalette): { g: Graphics; screen: Graphics; screenRect: { x: number; y: number; w: number; h: number } } {
  const { deskX: dx, deskY: dy } = seat;
  const g = new Graphics();
  // mặt bàn + mặt trước
  r(g, dx - 52, dy - 14, 104, 26, p.woodDark);
  r(g, dx - 50, dy - 12, 100, 22, p.deskTop);
  r(g, dx - 50, dy - 12, 100, 3, 0xffffff, 0.35);
  r(g, dx - 52, dy + 10, 104, 14, p.woodDark);
  r(g, dx - 50, dy + 10, 100, 10, p.deskFront);
  r(g, dx - 48, dy + 22, 6, 8, p.woodDark);
  r(g, dx + 42, dy + 22, 6, 8, p.woodDark);
  // màn hình
  const big = seat.kind === 'design' || seat.kind === 'test';
  const mw = big ? 50 : 44;
  const mh = big ? 34 : 30;
  const mx = dx - 50 + 4;
  const my = dy - 16 - mh;
  r(g, mx + mw / 2 - 4, dy - 18, 8, 8, 0x3a3f4b);
  r(g, mx + mw / 2 - 10, dy - 12, 20, 3, 0x3a3f4b);
  r(g, mx, my, mw, mh, 0x2b2b38);
  // bàn phím, chuột, cốc
  if (seat.kind === 'design') {
    r(g, dx + 4, dy - 8, 34, 14, 0x2b2b38); // bảng vẽ
    r(g, dx + 6, dy - 6, 30, 10, 0x4a4f5e);
    r(g, dx + 30, dy - 10, 2, 10, 0xf3d36b); // bút
  } else {
    r(g, dx + 4, dy - 6, 30, 8, 0x5b6170);
    for (let i = 0; i < 6; i++) r(g, dx + 6 + i * 5, dy - 4, 3, 2, 0xe8ebf0);
    r(g, dx + 38, dy - 4, 5, 6, 0xe8ebf0);
  }
  r(g, dx - 2, dy - 6, 7, 9, 0xffffff); // cốc
  r(g, dx + 5, dy - 4, 2, 4, 0xffffff);
  r(g, dx - 1, dy - 5, 5, 2, 0x8a5a3a);
  if (seat.kind === 'test') {
    r(g, dx + 38, dy - 22, 10, 16, 0x2b2b38); // điện thoại thử
    r(g, dx + 39, dy - 21, 8, 13, 0x9fd4fb);
  }
  g.zIndex = dy + 24;
  const screen = new Graphics();
  screen.zIndex = dy + 24.5;
  return { g, screen, screenRect: { x: mx + 3, y: my + 3, w: mw - 6, h: mh - 6 } };
}

export function easel(x: number, y: number) {
  const g = new Graphics();
  r(g, x - 20, y - 4, 4, 4, 0x80552f);
  r(g, x + 16, y - 4, 4, 4, 0x80552f);
  r(g, x - 18, y - 70, 4, 68, 0xb07a4a);
  r(g, x + 14, y - 70, 4, 68, 0xb07a4a);
  r(g, x - 2, y - 78, 4, 60, 0x80552f);
  box(g, x - 26, y - 76, 52, 40, 0xffffff, 0x80552f);
  r(g, x - 20, y - 68, 18, 18, 0xffb3c7);
  r(g, x - 4, y - 60, 22, 14, 0x9fd4fb);
  r(g, x - 14, y - 52, 12, 10, 0xf3d36b);
  r(g, x - 30, y - 34, 60, 4, 0x80552f);
  return at(y, g);
}

export function leadTable(p: ScenePalette) {
  const { x, y, w, h } = LEAD_TABLE;
  const g = new Graphics();
  r(g, x - w / 2 - 2, y - h / 2 - 2, w + 4, h - 8, p.woodDark);
  r(g, x - w / 2, y - h / 2, w, h - 12, p.wood);
  r(g, x - w / 2, y - h / 2, w, 3, 0xffffff, 0.25);
  for (let i = 1; i < 4; i++) r(g, x - w / 2 + 4, y - h / 2 + i * 13, w - 8, 1, p.woodDark, 0.35);
  r(g, x - w / 2 - 2, y + h / 2 - 10, w + 4, 14, p.woodDark);
  r(g, x - w / 2, y + h / 2 - 10, w, 10, p.deskFront);
  // laptop trước mặt trưởng nhóm
  r(g, x - 16, y - 24, 32, 18, 0x3a3f4b);
  r(g, x - 14, y - 22, 28, 14, 0x9fd4fb);
  r(g, x - 18, y - 6, 36, 5, 0xc5cad3);
  // giấy tờ, cốc
  r(g, x - 70, y - 18, 22, 16, 0xffffff);
  r(g, x - 66, y - 14, 14, 2, 0x9aa3b2);
  r(g, x - 66, y - 10, 10, 2, 0x9aa3b2);
  r(g, x + 50, y - 14, 18, 14, 0xffffff);
  r(g, x + 74, y - 18, 7, 9, 0xffffff);
  r(g, x + 75, y - 17, 5, 2, 0x8a5a3a);
  g.zIndex = y + h / 2 + 4;

  // bảng tên "BAN LÃNH ĐẠO" đặt trên bàn
  const plate = new Container();
  const t = pixelText('BAN LÃNH ĐẠO', 14, 0xffffff);
  const pw = Math.ceil(t.width) + 12;
  const bg = new Graphics();
  r(bg, -pw / 2 - 2, -2, pw + 4, 20, 0x1b1f2b);
  r(bg, -pw / 2, 0, pw, 16, p.label === 0x60a5fa ? 0x1e3a8a : p.label);
  r(bg, -pw / 2 + 4, 16, 4, 6, 0x1b1f2b);
  r(bg, pw / 2 - 8, 16, 4, 6, 0x1b1f2b);
  t.position.set(-pw / 2 + 6, -1);
  plate.addChild(bg, t);
  plate.position.set(x, y + 4);
  plate.zIndex = y + h / 2 + 5;

  // ghế quanh bàn (phía dưới)
  const chairs: Graphics[] = [];
  for (const cx of [x - 60, x, x + 60]) {
    const c = new Graphics();
    r(c, cx - 13, y + 32, 26, 12, 0x2b2b38);
    r(c, cx - 11, y + 32, 22, 10, 0x6b7bb0);
    c.zIndex = y + 44;
    chairs.push(c);
  }
  return { table: g, plate, chairs };
}

export function allDesks() {
  return [...SEATS.code, ...SEATS.creative];
}
