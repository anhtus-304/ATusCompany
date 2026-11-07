/** Phần tĩnh của văn phòng 3D: sàn, khu, tường kính, thành phố phía sau, bàn ghế, cây, đồ đạc. */
import {
  BackSide,
  BoxGeometry,
  CanvasTexture,
  CylinderGeometry,
  DoubleSide,
  Group,
  IcosahedronGeometry,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PlaneGeometry,
  SRGBColorSpace,
  type Material,
} from 'three';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { DESKS, FLOOR_D, FLOOR_W, LEAD_DOOR, LEAD_TABLE, ZONES, type Desk3D } from './layout3d';
import type { Palette3D } from './palette3d';
import { Screen3D } from './screens3d';

const std = (color: string, extra: Partial<ConstructorParameters<typeof MeshStandardMaterial>[0]> = {}) =>
  new MeshStandardMaterial({ color, roughness: 0.7, ...extra });

function box(w: number, h: number, d: number, mat: Material, x = 0, y = 0, z = 0, r = 0) {
  const m = new Mesh(r > 0 ? new RoundedBoxGeometry(w, h, d, 2, r) : new BoxGeometry(w, h, d), mat);
  m.position.set(x, y, z);
  m.castShadow = true;
  m.receiveShadow = true;
  return m;
}

/* ---------- Bầu trời & thành phố ---------- */

function skylineTexture(p: Palette3D) {
  const c = document.createElement('canvas');
  c.width = 2048;
  c.height = 512;
  const g = c.getContext('2d')!;
  const grad = g.createLinearGradient(0, 0, 0, 512);
  grad.addColorStop(0, p.skyTop);
  grad.addColorStop(1, p.skyBottom);
  g.fillStyle = grad;
  g.fillRect(0, 0, 2048, 512);
  let seed = 11;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  // hai lớp nhà: lớp xa nhạt hơn
  for (const layer of [0, 1]) {
    let x = 0;
    while (x < 2048) {
      const w = 50 + rnd() * 110;
      const h = (layer ? 140 : 200) + rnd() * (layer ? 260 : 200);
      g.globalAlpha = layer ? 1 : 0.55;
      g.fillStyle = p.building;
      g.fillRect(x, 512 - h, w, h);
      if (layer) {
        for (let wy = 512 - h + 10; wy < 500; wy += 14) {
          for (let wx = x + 6; wx < x + w - 8; wx += 12) {
            if (rnd() < (p.night ? 0.42 : 0.3)) {
              g.fillStyle = p.windowLit[Math.floor(rnd() * p.windowLit.length)];
              g.globalAlpha = p.night ? 0.55 + rnd() * 0.45 : 0.7;
              g.fillRect(wx, wy, 6, 8);
            }
          }
        }
      }
      x += w + 4 + rnd() * 16;
    }
  }
  g.globalAlpha = 1;
  const t = new CanvasTexture(c);
  t.colorSpace = SRGBColorSpace;
  return t;
}

function backdrop(p: Palette3D) {
  const g = new Group();
  const tex = skylineTexture(p);
  const cyl = new Mesh(
    new CylinderGeometry(60, 60, 34, 48, 1, true),
    new MeshBasicMaterial({ map: tex, side: BackSide, fog: false }),
  );
  cyl.position.y = 10;
  g.add(cyl);
  const ground = new Mesh(new PlaneGeometry(200, 200), new MeshBasicMaterial({ color: p.night ? '#05070d' : '#cbd6e2' }));
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -6.9;
  g.add(ground);
  return g;
}

/* ---------- Text trên sàn ---------- */

function floorLabel(text: string, color: string, night: boolean) {
  const c = document.createElement('canvas');
  c.width = 512;
  c.height = 64;
  const g = c.getContext('2d')!;
  g.font = '600 30px "Be Vietnam Pro", sans-serif';
  g.fillStyle = color;
  g.beginPath();
  g.arc(18, 32, 8, 0, Math.PI * 2);
  g.fill();
  g.fillStyle = night ? 'rgba(226,232,240,0.85)' : 'rgba(30,41,59,0.8)';
  g.fillText(text.toUpperCase(), 36, 43);
  const t = new CanvasTexture(c);
  t.colorSpace = SRGBColorSpace;
  t.anisotropy = 4;
  const m = new Mesh(new PlaneGeometry(4, 0.5), new MeshBasicMaterial({ map: t, transparent: true }));
  m.rotation.x = -Math.PI / 2;
  return m;
}

/* ---------- Đồ đạc ---------- */

export function plant(scale = 1, leaf = '#3fa35b') {
  const g = new Group();
  const pot = new Mesh(new CylinderGeometry(0.22, 0.17, 0.4, 16), std('#e5e7eb', { roughness: 0.4 }));
  pot.position.y = 0.2;
  pot.castShadow = true;
  g.add(pot);
  const leafMat = std(leaf, { roughness: 0.8, flatShading: true });
  const blobs: [number, number, number, number][] = [
    [0, 0.75, 0, 0.32],
    [0.16, 0.6, 0.08, 0.24],
    [-0.15, 0.62, -0.06, 0.25],
    [0.02, 0.98, 0.04, 0.22],
    [-0.06, 0.55, 0.16, 0.2],
  ];
  for (const [x, y, z, r] of blobs) {
    const b = new Mesh(new IcosahedronGeometry(r, 0), leafMat);
    b.position.set(x, y, z);
    b.castShadow = true;
    g.add(b);
  }
  g.scale.setScalar(scale);
  return g;
}

function chair(p: Palette3D) {
  const g = new Group();
  const mat = std(p.chair, { roughness: 0.6 });
  g.add(box(0.46, 0.08, 0.46, mat, 0, 0.46, 0, 0.03));
  g.add(box(0.46, 0.5, 0.07, mat, 0, 0.74, 0.22, 0.03));
  const leg = new Mesh(new CylinderGeometry(0.03, 0.03, 0.4, 8), std('#4b5563'));
  leg.position.y = 0.23;
  const base = new Mesh(new CylinderGeometry(0.24, 0.24, 0.03, 16), std('#374151'));
  base.position.y = 0.03;
  g.add(leg, base);
  return g;
}

/** Bàn làm việc có hai màn hình phía xa (màn hình hướng về phía robot và camera). */
function workDesk(d: Desk3D, p: Palette3D, seed: number) {
  const g = new Group();
  g.position.set(d.x, 0, d.z);
  const top = std(p.desk, { roughness: 0.35 });
  const legMat = std(p.deskLeg, { metalness: 0.4, roughness: 0.4 });
  g.add(box(2.3, 0.06, 1.0, top, 0, 0.75, 0, 0.02));
  for (const sx of [-1.05, 1.05]) g.add(box(0.06, 0.72, 0.9, legMat, sx, 0.37, 0));
  // vách ngăn thấp phía sau
  g.add(box(2.3, 0.4, 0.04, std(p.night ? '#cbd5e1' : '#dbe3ec', { roughness: 0.5 }), 0, 0.98, -0.52));

  const screens: Screen3D[] = [];
  const dark = std('#1f2430', { roughness: 0.4, metalness: 0.3 });
  const offs = d.kind === 'design' ? [-0.48, 0.52] : [-0.5, 0.5];
  offs.forEach((ox, i) => {
    const mon = new Group();
    mon.position.set(ox, 0.78, -0.25);
    mon.rotation.y = i === 0 ? 0.12 : -0.12;
    const wide = d.kind === 'design' && i === 1 ? 1.0 : 0.88;
    mon.add(box(wide, 0.54, 0.05, dark, 0, 0.42, 0, 0.02));
    const sc = new Screen3D(d.kind, i, seed * 13 + i * 7);
    screens.push(sc);
    const plane = new Mesh(new PlaneGeometry(wide - 0.06, 0.48), new MeshBasicMaterial({ map: sc.texture, toneMapped: false }));
    plane.position.set(0, 0.42, 0.027);
    mon.add(plane);
    mon.add(box(0.06, 0.2, 0.06, dark, 0, 0.1, -0.02));
    mon.add(box(0.28, 0.02, 0.18, dark, 0, 0.01, -0.02));
    g.add(mon);
  });
  // bàn phím, chuột, cốc
  g.add(box(0.62, 0.025, 0.2, std('#cbd5e1', { roughness: 0.5 }), -0.05, 0.79, 0.18, 0.01));
  g.add(box(0.08, 0.025, 0.12, std('#cbd5e1'), 0.42, 0.79, 0.2, 0.01));
  const mug = new Mesh(new CylinderGeometry(0.05, 0.045, 0.11, 12), std(seed % 2 ? '#f97316' : '#3b82f6'));
  mug.position.set(0.85, 0.84, 0.05);
  g.add(mug);
  if (d.kind === 'test') {
    g.add(box(0.12, 0.2, 0.02, dark, 0.85, 0.88, -0.2, 0.01));
  }
  if (d.kind === 'design') {
    g.add(box(0.5, 0.02, 0.34, dark, 0.35, 0.79, 0.12, 0.02));
  }
  const ch = chair(p);
  ch.position.set(0, 0, 1.15);
  ch.rotation.y = Math.PI;
  // ghế đặt lệch sau lưng robot để không che robot
  ch.position.x = 0.75;
  g.add(ch);
  return { group: g, screens };
}

function leadRoom(p: Palette3D) {
  const g = new Group();
  const z = ZONES.find((zz) => zz.id === 'lead')!;
  const glass = new MeshStandardMaterial({ color: p.glass, transparent: true, opacity: p.glassOpacity + 0.08, roughness: 0.1, metalness: 0.1, side: DoubleSide, depthWrite: false });
  const frame = std(p.edge.lead, { emissive: p.edge.lead, emissiveIntensity: p.night ? 0.6 : 0.15 });
  const h = 1.15;
  const wall = (x0: number, z0: number, x1: number, z1: number) => {
    const len = Math.hypot(x1 - x0, z1 - z0);
    const m = new Mesh(new PlaneGeometry(len, h), glass);
    m.position.set((x0 + x1) / 2, h / 2, (z0 + z1) / 2);
    m.rotation.y = -Math.atan2(z1 - z0, x1 - x0);
    g.add(m);
    const rail = box(len, 0.04, 0.04, frame, (x0 + x1) / 2, h, (z0 + z1) / 2);
    rail.rotation.y = m.rotation.y;
    rail.castShadow = false;
    g.add(rail);
    const base = box(len, 0.03, 0.05, frame, (x0 + x1) / 2, 0.02, (z0 + z1) / 2);
    base.rotation.y = m.rotation.y;
    g.add(base);
  };
  const dx0 = LEAD_DOOR.x - LEAD_DOOR.w / 2;
  const dx1 = LEAD_DOOR.x + LEAD_DOOR.w / 2;
  wall(z.x0, z.z0, dx0, z.z0);
  wall(dx1, z.z0, z.x1, z.z0);
  wall(z.x0, z.z0, z.x0, z.z1);

  // bàn họp dài
  const top = std(p.night ? '#7a5a40' : '#b07a4a', { roughness: 0.45 });
  const T = LEAD_TABLE;
  g.add(box(T.w, 0.08, T.d, top, T.x, 0.76, T.z, 0.04));
  for (const sx of [-T.w / 2 + 0.3, T.w / 2 - 0.3]) g.add(box(0.12, 0.72, T.d - 0.3, std('#2b2f3a'), T.x + sx, 0.37, T.z));
  // laptop của trưởng nhóm
  const lap = new Group();
  lap.position.set(T.x, 0.8, T.z - 0.35);
  lap.add(box(0.5, 0.02, 0.34, std('#cbd5e1'), 0, 0, 0));
  const screen = new Screen3D('lead', 0, 99);
  const lid = new Mesh(new PlaneGeometry(0.48, 0.3), new MeshBasicMaterial({ map: screen.texture, toneMapped: false, side: DoubleSide }));
  lid.position.set(0, 0.16, -0.15);
  lid.rotation.x = -0.25;
  lid.rotation.y = Math.PI; // màn hình quay về phía trưởng nhóm
  lap.add(lid);
  g.add(lap);
  // bảng tên trên bàn
  const plate = labelPlate('BAN LÃNH ĐẠO', p.edge.lead);
  plate.position.set(T.x, 0.92, T.z + 0.45);
  g.add(plate);
  // ghế quanh bàn
  for (const sx of [-1.3, 0, 1.3]) {
    const c = chair(p);
    c.position.set(T.x + sx, 0, T.z + 1.35);
    c.scale.setScalar(0.9);
    g.add(c);
  }
  // màn hình trình chiếu trên vách phải
  const tv = new Group();
  tv.position.set(z.x1 - 0.15, 0, T.z);
  tv.rotation.y = -Math.PI / 2;
  tv.add(box(2.2, 1.2, 0.06, std('#111827'), 0, 1.45, 0, 0.02));
  const chart = new Mesh(new PlaneGeometry(2.08, 1.08), new MeshBasicMaterial({ map: chartTexture(), toneMapped: false }));
  chart.position.set(0, 1.45, 0.035);
  tv.add(chart);
  tv.add(box(0.1, 0.9, 0.1, std('#374151'), 0, 0.45, -0.05));
  g.add(tv);
  const pl = plant(1.3);
  pl.position.set(z.x1 - 0.5, 0, z.z1 - 0.5);
  g.add(pl);
  return { group: g, screens: [screen] };
}

function labelPlate(text: string, color: string) {
  const c = document.createElement('canvas');
  c.width = 512;
  c.height = 96;
  const g = c.getContext('2d')!;
  g.fillStyle = '#111827';
  g.fillRect(0, 0, 512, 96);
  g.fillStyle = color;
  g.fillRect(0, 0, 10, 96);
  g.fillStyle = '#ffffff';
  g.font = '700 46px "Be Vietnam Pro", sans-serif';
  g.textAlign = 'center';
  g.fillText(text, 262, 64);
  const t = new CanvasTexture(c);
  t.colorSpace = SRGBColorSpace;
  const grp = new Group();
  const m = new Mesh(new PlaneGeometry(0.9, 0.17), new MeshBasicMaterial({ map: t, toneMapped: false }));
  m.rotation.x = -0.35;
  grp.add(m);
  return grp;
}

function chartTexture() {
  const c = document.createElement('canvas');
  c.width = 512;
  c.height = 266;
  const g = c.getContext('2d')!;
  g.fillStyle = '#0f172a';
  g.fillRect(0, 0, 512, 266);
  g.fillStyle = '#e2e8f0';
  g.font = '600 22px "Be Vietnam Pro", sans-serif';
  g.fillText('Tiến độ sprint', 24, 40);
  const bars = [0.4, 0.62, 0.55, 0.8, 0.7, 0.92];
  bars.forEach((v, i) => {
    g.fillStyle = i === bars.length - 1 ? '#f59e0b' : '#3b82f6';
    g.fillRect(40 + i * 72, 236 - v * 160, 44, v * 160);
  });
  g.strokeStyle = '#22c55e';
  g.lineWidth = 4;
  g.beginPath();
  bars.forEach((v, i) => g.lineTo(62 + i * 72, 220 - v * 170));
  g.stroke();
  const t = new CanvasTexture(c);
  t.colorSpace = SRGBColorSpace;
  return t;
}

function lounge(p: Palette3D) {
  const g = new Group();
  const sofaMat = std(p.night ? '#334155' : '#5b6b8c', { roughness: 0.8 });
  const sofa = new Group();
  sofa.add(box(3.0, 0.4, 0.9, sofaMat, 0, 0.25, 0, 0.1));
  sofa.add(box(3.0, 0.55, 0.25, sofaMat, 0, 0.55, -0.35, 0.1));
  sofa.add(box(0.25, 0.5, 0.9, sofaMat, -1.4, 0.4, 0, 0.1));
  sofa.add(box(0.25, 0.5, 0.9, sofaMat, 1.4, 0.4, 0, 0.1));
  sofa.add(box(0.5, 0.36, 0.14, std('#f59e0b'), -0.8, 0.6, -0.15, 0.06));
  sofa.position.set(-9.4, 0, 7.7);
  sofa.rotation.y = Math.PI;
  g.add(sofa);
  // bàn tròn + ghế đẩu
  const roundTable = (x: number, z: number) => {
    const t = new Group();
    const top = new Mesh(new CylinderGeometry(0.55, 0.55, 0.05, 28), std(p.desk, { roughness: 0.35 }));
    top.position.y = 0.74;
    top.castShadow = true;
    const leg = new Mesh(new CylinderGeometry(0.05, 0.05, 0.72, 10), std('#4b5563'));
    leg.position.y = 0.36;
    t.add(top, leg);
    for (let i = 0; i < 3; i++) {
      const a = (i / 3) * Math.PI * 2 + 0.4;
      const s = new Mesh(new CylinderGeometry(0.2, 0.2, 0.45, 16), std(p.chair));
      s.position.set(Math.cos(a) * 0.85, 0.225, Math.sin(a) * 0.85);
      s.castShadow = true;
      t.add(s);
    }
    t.position.set(x, 0, z);
    return t;
  };
  g.add(roundTable(-4.6, 5.6), roundTable(-1.6, 7.0));
  // bình nước, máy in
  const cooler = new Group();
  cooler.add(box(0.4, 0.9, 0.4, std('#e5e7eb'), 0, 0.45, 0, 0.04));
  const bottle = new Mesh(new CylinderGeometry(0.16, 0.16, 0.42, 16), new MeshStandardMaterial({ color: '#7dd3fc', transparent: true, opacity: 0.7, roughness: 0.1 }));
  bottle.position.y = 1.12;
  cooler.add(bottle);
  cooler.position.set(-12.2, 0, 4.0);
  g.add(cooler);
  const printer = new Group();
  printer.add(box(0.9, 0.6, 0.6, std('#9ca3af'), 0, 0.3, 0, 0.03));
  printer.add(box(0.8, 0.3, 0.55, std('#e5e7eb'), 0, 0.75, 0, 0.04));
  printer.add(box(0.5, 0.02, 0.3, std('#ffffff'), 0, 0.92, 0.05));
  printer.position.set(0.6, 0, 7.9);
  g.add(printer);
  // kệ sách
  const shelf = new Group();
  const wood = std(p.night ? '#3b2f2a' : '#b07a4a');
  shelf.add(box(2.2, 1.8, 0.4, wood, 0, 0.9, 0));
  const colors = ['#ef4444', '#3b82f6', '#f59e0b', '#22c55e', '#a855f7', '#e5e7eb'];
  for (let r = 0; r < 3; r++)
    for (let i = 0; i < 9; i++)
      shelf.add(box(0.14, 0.32 + ((i * 7) % 4) * 0.04, 0.3, std(colors[(i + r) % colors.length]), -0.95 + i * 0.22, 0.32 + r * 0.55, 0.05));
  shelf.position.set(-13.6, 0, 6.2);
  shelf.rotation.y = Math.PI / 2;
  g.add(shelf);
  return g;
}

function studioExtras(p: Palette3D) {
  const g = new Group();
  // giá vẽ
  const easel = new Group();
  const wood = std('#b07a4a');
  for (const sx of [-0.3, 0.3]) {
    const l = box(0.05, 1.7, 0.05, wood, sx, 0.85, 0);
    l.rotation.z = sx > 0 ? -0.1 : 0.1;
    easel.add(l);
  }
  const canvas = new Mesh(new PlaneGeometry(0.9, 0.7), new MeshBasicMaterial({ map: artTexture() }));
  canvas.position.set(0, 1.25, 0.05);
  easel.add(canvas, box(0.95, 0.75, 0.03, std('#f8fafc'), 0, 1.25, 0.02));
  easel.position.set(9.3, 0, -2.4);
  easel.rotation.y = -0.6;
  g.add(easel);
  // bảng ghim ý tưởng
  const board = new Group();
  board.add(box(2.6, 1.3, 0.05, std(p.night ? '#1f2937' : '#f1f5f9'), 0, 1.4, 0, 0.02));
  const notes = ['#fde68a', '#fbcfe8', '#bae6fd', '#bbf7d0', '#fed7aa'];
  for (let i = 0; i < 10; i++)
    board.add(box(0.32, 0.32, 0.01, std(notes[i % notes.length]), -1.0 + (i % 5) * 0.5, 1.65 - Math.floor(i / 5) * 0.5, 0.035));
  board.position.set(5.2, 0, -7.75);
  g.add(board);
  return g;
}

function perimeter(p: Palette3D) {
  const g = new Group();
  const hx = FLOOR_W / 2;
  const hz = FLOOR_D / 2;
  const wallMat = std(p.wall, { roughness: 0.85 });
  const glass = new MeshStandardMaterial({ color: p.glass, transparent: true, opacity: p.glassOpacity, roughness: 0.05, metalness: 0.2, side: DoubleSide, depthWrite: false, emissive: p.night ? p.glass : '#000000', emissiveIntensity: p.night ? 0.12 : 0 });
  const frame = std(p.frame, { metalness: 0.4, roughness: 0.4 });
  const H = 2.6;
  // tường thấp + kính cao ở mặt sau và bên trái (hai mặt phía xa camera)
  const side = (len: number, x: number, z: number, rotY: number) => {
    const s = new Group();
    s.position.set(x, 0, z);
    s.rotation.y = rotY;
    s.add(box(len, 0.5, 0.2, wallMat, 0, 0.25, 0));
    const pane = new Mesh(new PlaneGeometry(len, H - 0.5), glass);
    pane.position.y = 0.5 + (H - 0.5) / 2;
    s.add(pane);
    const n = Math.round(len / 2.2);
    for (let i = 0; i <= n; i++) s.add(box(0.08, H, 0.12, frame, -len / 2 + (i * len) / n, H / 2, 0));
    s.add(box(len, 0.1, 0.14, frame, 0, H, 0));
    return s;
  };
  g.add(side(FLOOR_W, 0, -hz, 0));
  g.add(side(FLOOR_D, -hx, 0, Math.PI / 2));
  // gờ thấp ở hai mặt phía trước để không che tầm nhìn
  g.add(box(FLOOR_W, 0.12, 0.12, frame, 0, 0.06, hz));
  g.add(box(0.12, 0.12, FLOOR_D, frame, hx, 0.06, 0));
  // cột góc có cây lớn
  for (const [x, z] of [[-hx + 0.6, -hz + 0.6], [hx - 0.6, -hz + 0.6], [-hx + 0.6, hz - 0.6]] as const) {
    const pl = plant(1.6, '#2f8f4e');
    pl.position.set(x, 0, z);
    g.add(pl);
  }
  return g;
}

export interface StaticScene {
  group: Group;
  screensByDesk: Map<Desk3D, Screen3D[]>;
  leadScreen: Screen3D;
}

export function buildStatic(p: Palette3D): StaticScene {
  const g = new Group();
  g.add(backdrop(p));

  // sàn
  const slab = box(FLOOR_W + 0.6, 0.4, FLOOR_D + 0.6, std(p.slab), 0, -0.2, 0);
  slab.castShadow = false;
  g.add(slab);
  const floor = new Mesh(new PlaneGeometry(FLOOR_W, FLOOR_D), std(p.floor, { roughness: 0.9 }));
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = 0.001;
  floor.receiveShadow = true;
  g.add(floor);

  // khu: thảm + viền phát sáng + nhãn sàn
  for (const z of ZONES) {
    const w = z.x1 - z.x0;
    const d = z.z1 - z.z0;
    const pad = new Mesh(new PlaneGeometry(w, d), std(p.pad[z.id], { roughness: 0.95 }));
    pad.rotation.x = -Math.PI / 2;
    pad.position.set((z.x0 + z.x1) / 2, 0.004, (z.z0 + z.z1) / 2);
    pad.receiveShadow = true;
    g.add(pad);
    const edgeMat = new MeshBasicMaterial({ color: p.edge[z.id], transparent: true, opacity: p.night ? 0.8 : 0.6 });
    const t = 0.05;
    for (const [ex, ez, ew, ed] of [
      [(z.x0 + z.x1) / 2, z.z0, w, t],
      [(z.x0 + z.x1) / 2, z.z1, w, t],
      [z.x0, (z.z0 + z.z1) / 2, t, d],
      [z.x1, (z.z0 + z.z1) / 2, t, d],
    ]) {
      const e = new Mesh(new PlaneGeometry(ew, ed), edgeMat);
      e.rotation.x = -Math.PI / 2;
      e.position.set(ex, 0.006, ez);
      g.add(e);
    }
    const lbl = floorLabel(z.label, p.edge[z.id], p.night);
    lbl.position.set(z.x0 + 2.2, 0.008, z.z1 - 0.4);
    g.add(lbl);
  }

  g.add(perimeter(p));

  const screensByDesk = new Map<Desk3D, Screen3D[]>();
  let seed = 3;
  for (const d of [...DESKS.code, ...DESKS.creative]) {
    const wd = workDesk(d, p, seed++);
    g.add(wd.group);
    screensByDesk.set(d, wd.screens);
  }
  const lr = leadRoom(p);
  g.add(lr.group);
  screensByDesk.set(DESKS.lead[0], lr.screens);
  g.add(lounge(p));
  g.add(studioExtras(p));

  // cây rải rác
  for (const [x, z, s] of [
    [-1.2, -7.2, 1.1],
    [0.2, 1.2, 0.9],
    [-12.4, 1.3, 1],
    [10.8, -7.2, 1.2],
    [2.6, 7.9, 1],
  ] as const) {
    const pl = plant(s);
    pl.position.set(x, 0, z);
    g.add(pl);
  }

  g.traverse((o) => {
    if ((o as Mesh).isMesh && !(o as Mesh).geometry.type.startsWith('Plane')) o.receiveShadow = true;
  });

  return { group: g, screensByDesk, leadScreen: lr.screens[0] };
}

function artTexture() {
  const c = document.createElement('canvas');
  c.width = 256;
  c.height = 200;
  const g = c.getContext('2d')!;
  g.fillStyle = '#fff7ed';
  g.fillRect(0, 0, 256, 200);
  g.fillStyle = '#fda4af';
  g.beginPath();
  g.arc(90, 90, 50, 0, Math.PI * 2);
  g.fill();
  g.fillStyle = '#93c5fd';
  g.fillRect(120, 60, 100, 110);
  g.fillStyle = '#fde047';
  g.beginPath();
  g.arc(190, 50, 26, 0, Math.PI * 2);
  g.fill();
  const t = new CanvasTexture(c);
  t.colorSpace = SRGBColorSpace;
  return t;
}

