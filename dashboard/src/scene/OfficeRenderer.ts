/**
 * Cảnh văn phòng PixiJS. Không chứa logic điều phối: chỉ nhận danh sách agent/task
 * qua update() và vẽ lại cho khớp, kèm chuyển động mượt và hiệu ứng.
 */
import { Application, Container } from 'pixi.js';
import type { Agent, Task } from '../types';
import { Character } from './Character';
import { Effects } from './effects';
import {
  bookshelf,
  chair,
  desk,
  drawBackground,
  easel,
  leadTable,
  partition,
  plant,
  printer,
  sofa,
  waterCooler,
} from './furniture';
import { assignSeats, MEETING_SPOTS, route, SEATS, WORLD_H, WORLD_W, type Seat, type Spot } from './layout';
import { SCENE_PALETTES, type ThemeId } from './palette';
import { ScreenDisplay, type ScreenMode } from './screens';

export interface SceneHandlers {
  onHover: (agentId: string | null, pos: { x: number; y: number } | null) => void;
  onSelect: (agentId: string) => void;
}

export class OfficeRenderer {
  private app = new Application();
  private ready = false;
  private destroyed = false;
  private world = new Container();
  private staticLayer = new Container();
  private sorted = new Container();
  private overlay = new Container();
  private effects = new Effects();
  private furniture: Container[] = [];
  private screens: { seat: Seat; display: ScreenDisplay }[] = [];
  private chars = new Map<string, Character>();
  private seatOf = new Map<string, Spot>();
  private taskStatus = new Map<string, Task['status']>();
  private firstUpdate = true;
  private theme: ThemeId = 'sky';
  private selected: string | null = null;
  private handlers: SceneHandlers = { onHover: () => {}, onSelect: () => {} };
  private host: HTMLElement | null = null;
  private resizeObs: ResizeObserver | null = null;
  private pending: { agents: Agent[]; tasks: Task[] } | null = null;
  /** dịch khung nhìn khi văn phòng lớn hơn màn hình (điện thoại) */
  private pan = { x: 0, y: 0 };
  private drag: { x: number; y: number; px: number; py: number } | null = null;

  async init(host: HTMLElement, theme: ThemeId) {
    this.host = host;
    this.theme = theme;
    await Promise.all([
      document.fonts.load('16px VT323'),
      document.fonts.load('14px "Be Vietnam Pro"'),
    ]).catch(() => undefined);
    await this.app.init({
      width: Math.max(1, host.clientWidth),
      height: Math.max(1, host.clientHeight),
      antialias: false,
      background: SCENE_PALETTES[theme].bg,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
      autoDensity: true,
    });
    if (this.destroyed) {
      this.app.destroy(true, { children: true });
      return;
    }
    host.appendChild(this.app.canvas);
    this.app.canvas.style.display = 'block';
    this.sorted.sortableChildren = true;
    this.world.addChild(this.staticLayer, this.sorted, this.overlay, this.effects.layer);
    this.app.stage.addChild(this.world);
    this.buildStatic();
    this.enablePan();
    this.app.ticker.add((t) => this.tick(t.deltaMS / 1000));
    this.resizeObs = new ResizeObserver(() => this.fit());
    this.resizeObs.observe(host);
    this.fit();
    this.ready = true;
    if (this.pending) this.update(this.pending.agents, this.pending.tasks);
  }

  setHandlers(h: SceneHandlers) {
    this.handlers = h;
  }

  setTheme(theme: ThemeId) {
    if (theme === this.theme) return;
    this.theme = theme;
    if (!this.ready) return;
    this.app.renderer.background.color = SCENE_PALETTES[theme].bg;
    this.buildStatic();
  }

  setSelected(id: string | null) {
    this.selected = id;
    for (const c of this.chars.values()) c.setSelected(c.id === id);
  }

  /** Gọi mỗi khi dữ liệu thay đổi. */
  update(agents: Agent[], tasks: Task[]) {
    if (!this.ready) {
      this.pending = { agents, tasks };
      return;
    }
    const seats = assignSeats(agents);
    const meeting = agents.filter((a) => a.location === 'meeting');

    // xoá nhân vật không còn
    for (const [id, c] of this.chars) {
      if (!agents.find((a) => a.id === id)) {
        c.destroy();
        this.chars.delete(id);
      }
    }

    for (const a of agents) {
      const home = seats.get(a.id)!;
      this.seatOf.set(a.id, home);
      const mi = meeting.indexOf(a);
      const target: Spot =
        mi >= 0
          ? { ...MEETING_SPOTS[mi % MEETING_SPOTS.length], seated: false, exit: MEETING_SPOTS[mi % MEETING_SPOTS.length] }
          : home;
      let c = this.chars.get(a.id);
      if (!c) {
        c = new Character(
          a,
          (ch) => this.hover(ch),
          () => this.handlers.onHover(null, null),
          (ch) => this.handlers.onSelect(ch.id),
        );
        c.place(target);
        c.setSelected(a.id === this.selected);
        this.chars.set(a.id, c);
        this.sorted.addChild(c.body);
        this.overlay.addChild(c.overlay);
      } else {
        c.setAgent(a);
        const cur = c.spot;
        if (cur && (Math.abs(cur.x - target.x) > 0.5 || Math.abs(cur.y - target.y) > 0.5)) {
          const fromExit = c.walking ? { x: c.x, y: c.y } : cur.exit;
          c.walk(route({ x: c.x, y: c.y }, fromExit, target), target);
        }
      }
    }

    // hiệu ứng khi task chuyển sang hoàn thành
    for (const t of tasks) {
      const prev = this.taskStatus.get(t.id);
      if (!this.firstUpdate && t.status === 'done' && prev !== 'done') {
        const who = this.chars.get(t.assignee);
        if (who) {
          const h = who.headPos();
          this.effects.celebrate(h.x, h.y);
        }
      }
      this.taskStatus.set(t.id, t.status);
    }
    this.firstUpdate = false;
  }

  private hover(c: Character) {
    const rect = this.app.canvas.getBoundingClientRect();
    const s = this.world.scale.x;
    const head = c.headPos();
    this.handlers.onHover(c.id, {
      x: rect.left + this.world.x + c.x * s,
      y: rect.top + this.world.y + head.y * s,
    });
  }

  private fit() {
    if (!this.host) return;
    const w = Math.max(1, this.host.clientWidth);
    const h = Math.max(1, this.host.clientHeight);
    if (this.app.screen.width !== w || this.app.screen.height !== h) this.app.renderer.resize(w, h);
    // màn hình hẹp: không thu nhỏ quá mức, cho phép kéo để xem phần còn lại
    const s = Math.max(Math.min(w / WORLD_W, h / WORLD_H), Math.min(0.62, h / WORLD_H));
    this.world.scale.set(s);
    const ww = WORLD_W * s;
    const wh = WORLD_H * s;
    const clamp = (v: number, over: number) => (over > 0 ? Math.max(-over / 2, Math.min(over / 2, v)) : 0);
    this.pan.x = clamp(this.pan.x, ww - w);
    this.pan.y = clamp(this.pan.y, wh - h);
    this.world.position.set(Math.round((w - ww) / 2 + this.pan.x), Math.round((h - wh) / 2 + this.pan.y));
  }

  private enablePan() {
    const stage = this.app.stage;
    stage.eventMode = 'static';
    stage.hitArea = this.app.screen;
    stage.on('pointerdown', (e) => {
      this.drag = { x: e.global.x, y: e.global.y, px: this.pan.x, py: this.pan.y };
    });
    stage.on('globalpointermove', (e) => {
      if (!this.drag) return;
      this.pan.x = this.drag.px + (e.global.x - this.drag.x);
      this.pan.y = this.drag.py + (e.global.y - this.drag.y);
      this.fit();
    });
    const end = () => (this.drag = null);
    stage.on('pointerup', end);
    stage.on('pointerupoutside', end);
  }

  private buildStatic() {
    const p = SCENE_PALETTES[this.theme];
    this.staticLayer.removeChildren().forEach((c) => c.destroy({ children: true }));
    for (const f of this.furniture) f.destroy({ children: true });
    this.furniture = [];
    this.screens = [];

    this.staticLayer.addChild(drawBackground(p));

    const add = (...items: Container[]) => {
      for (const it of items) {
        this.furniture.push(it);
        this.sorted.addChild(it);
      }
    };

    add(partition(381, p), partition(639, p));
    add(bookshelf(296, 112, 68, p), bookshelf(890, 112, 76, p));
    add(plant(36, 126), plant(408, 128, 0.9), plant(612, 128, 0.9), plant(962, 200));
    add(plant(28, 624, 1.1), plant(972, 624, 1.1), plant(360, 500, 0.8), plant(660, 500, 0.8));
    add(printer(110, 622), waterCooler(560, 622), sofa(860, 628, p.accent));
    add(easel(910, 300));

    const lt = leadTable(p);
    add(lt.table, lt.plate, ...lt.chairs);
    add(chair(SEATS.lead[0].x, SEATS.lead[0].y, 0x6b7bb0));

    let seed = 7;
    for (const seat of [...SEATS.code, ...SEATS.creative]) {
      const d = desk(seat, p);
      add(chair(seat.x, seat.y, seat.kind === 'code' ? 0x4a6fb5 : 0x4f9a6a), d.g, d.screen);
      this.screens.push({ seat, display: new ScreenDisplay(d.screen, d.screenRect, seat.kind, seed++ * 977) });
    }
  }

  private tick(dt: number) {
    const clamped = Math.min(dt, 0.05);
    for (const c of this.chars.values()) c.update(clamped);
    this.effects.update(clamped);

    // màn hình: theo trạng thái người ngồi bàn
    for (const { seat, display } of this.screens) {
      let mode: ScreenMode = 'off';
      for (const c of this.chars.values()) {
        if (this.seatOf.get(c.id)?.seat !== seat) continue;
        const a = c.agent;
        const atDesk = c.seated && !c.walking;
        mode = a.status === 'blocked' ? 'alert' : a.status === 'working' && atDesk ? 'work' : 'idle';
      }
      display.update(mode, clamped);
    }
  }

  destroy() {
    this.destroyed = true;
    this.resizeObs?.disconnect();
    if (this.ready) {
      this.ready = false;
      this.app.destroy(true, { children: true });
    }
  }
}
