/** Màn hình máy tính trong cảnh 3D: vẽ bằng canvas 2D rồi dùng làm texture phát sáng. */
import { CanvasTexture, SRGBColorSpace } from 'three';
import type { DeskKind } from './layout3d';

export type ScreenMode = 'off' | 'idle' | 'work' | 'alert';

const W = 256;
const H = 160;
const CODE = ['#7fd3ff', '#f3d36b', '#c792ea', '#9be29b', '#f78c6c', '#e8ebf0', '#82aaff'];

export class Screen3D {
  readonly texture: CanvasTexture;
  private ctx: CanvasRenderingContext2D;
  private lines: { indent: number; parts: { w: number; c: string }[] }[] = [];
  private acc = 0;
  private tick = 0;
  private last: ScreenMode | null = null;

  constructor(
    private kind: DeskKind,
    private variant: number,
    private seed: number,
  ) {
    const c = document.createElement('canvas');
    c.width = W;
    c.height = H;
    this.ctx = c.getContext('2d')!;
    this.texture = new CanvasTexture(c);
    this.texture.colorSpace = SRGBColorSpace;
    for (let i = 0; i < 14; i++) this.lines.push(this.randomLine());
    this.draw('off');
  }

  private rand() {
    this.seed = (this.seed * 1103515245 + 12345) & 0x7fffffff;
    return this.seed / 0x7fffffff;
  }

  private randomLine() {
    const indent = Math.floor(this.rand() * 4) * 12;
    const n = 1 + Math.floor(this.rand() * 4);
    return {
      indent,
      parts: Array.from({ length: n }, () => ({
        w: 12 + Math.floor(this.rand() * 40),
        c: CODE[Math.floor(this.rand() * CODE.length)],
      })),
    };
  }

  update(mode: ScreenMode, dt: number) {
    this.acc += dt;
    this.tick += dt;
    const animated = mode !== 'off';
    if (mode === this.last && (!animated || this.acc < 0.2)) return;
    this.acc = 0;
    if (mode === 'work' && this.tick > 0.32) {
      this.tick = 0;
      this.lines.shift();
      this.lines.push(this.randomLine());
    }
    this.last = mode;
    this.draw(mode);
    this.texture.needsUpdate = true;
  }

  private draw(mode: ScreenMode) {
    const g = this.ctx;
    const t = performance.now() / 1000;
    if (mode === 'off') {
      g.fillStyle = '#0b0f18';
      g.fillRect(0, 0, W, H);
      return;
    }
    if (mode === 'alert') {
      g.fillStyle = '#3b0a12';
      g.fillRect(0, 0, W, H);
      const on = Math.floor(t * 2.5) % 2 === 0;
      g.fillStyle = on ? '#ff5d5d' : '#ff9a9a';
      g.fillRect(W / 2 - 9, 30, 18, 70);
      g.fillRect(W / 2 - 9, 112, 18, 18);
      g.font = 'bold 16px sans-serif';
      g.textAlign = 'center';
      g.fillText('BLOCKED', W / 2, 150);
      return;
    }
    if (mode === 'idle') {
      g.fillStyle = '#0f1a33';
      g.fillRect(0, 0, W, H);
      const x = 30 + ((Math.sin(t * 0.6 + this.seed) + 1) / 2) * (W - 90);
      const y = 20 + ((Math.cos(t * 0.8 + this.seed) + 1) / 2) * (H - 70);
      g.fillStyle = '#3b82f6';
      g.fillRect(x, y, 34, 22);
      g.fillStyle = '#9fd4fb';
      g.fillRect(x + 8, y + 5, 18, 12);
      return;
    }

    const kind = this.kind === 'lead' ? 'code' : this.kind;
    if (kind === 'code' || (kind === 'test' && this.variant === 1) || (kind === 'design' && this.variant === 1)) {
      // trình soạn mã
      g.fillStyle = '#111827';
      g.fillRect(0, 0, W, H);
      g.fillStyle = '#1f2937';
      g.fillRect(0, 0, W, 14);
      g.fillRect(0, 14, 34, H);
      ['#f87171', '#fbbf24', '#34d399'].forEach((c, i) => {
        g.fillStyle = c;
        g.fillRect(6 + i * 10, 4, 6, 6);
      });
      this.lines.forEach((ln, i) => {
        const y = 22 + i * 9.6;
        if (y > H - 6) return;
        g.fillStyle = '#4b5563';
        g.fillRect(8, y, 16, 4);
        let x = 42 + ln.indent;
        for (const p of ln.parts) {
          const w = Math.min(p.w, W - 6 - x);
          if (w > 0) {
            g.fillStyle = p.c;
            g.fillRect(x, y, w, 5);
          }
          x += p.w + 6;
        }
      });
      if (Math.floor(t * 3) % 2 === 0) {
        g.fillStyle = '#ffffff';
        g.fillRect(42 + this.lines[13].indent, 22 + 13 * 9.6 - 2, 3, 9);
      }
      return;
    }
    if (kind === 'test') {
      // trang web đang được thử + vạch quét
      g.fillStyle = '#f8fafc';
      g.fillRect(0, 0, W, H);
      g.fillStyle = '#3b82f6';
      g.fillRect(0, 0, W, 16);
      g.fillStyle = '#1f2937';
      g.fillRect(14, 28, 120, 12);
      g.fillStyle = '#94a3b8';
      g.fillRect(14, 48, 160, 6);
      g.fillRect(14, 60, 130, 6);
      g.fillStyle = '#f97316';
      g.fillRect(14, 76, 54, 16);
      g.fillStyle = '#bbf7d0';
      g.fillRect(170, 26, 72, 60);
      for (let i = 0; i < 3; i++) {
        g.fillStyle = '#e2e8f0';
        g.fillRect(14 + i * 80, 104, 70, 44);
      }
      const sy = 16 + ((t * 50) % (H - 16));
      g.fillStyle = 'rgba(34,197,94,0.85)';
      g.fillRect(0, sy, W, 3);
      g.fillStyle = '#22c55e';
      g.fillRect(W - 40, H - 22, 30, 14);
      return;
    }
    // designer: canvas vẽ
    g.fillStyle = '#fdf6ec';
    g.fillRect(0, 0, W, H);
    g.fillStyle = '#374151';
    g.fillRect(0, 0, 26, H);
    ['#ef4444', '#f59e0b', '#22c55e', '#3b82f6', '#a855f7', '#ec4899'].forEach((c, i) => {
      g.fillStyle = c;
      g.fillRect(5, 8 + i * 22, 16, 16);
    });
    g.fillStyle = '#fbcfe8';
    g.fillRect(50, 24, 90, 60);
    g.fillStyle = '#bae6fd';
    g.fillRect(110, 60, 110, 70);
    g.fillStyle = '#fde68a';
    g.beginPath();
    g.arc(80, 110, 26, 0, Math.PI * 2);
    g.fill();
    const bx = 50 + ((Math.sin(t * 1.3) + 1) / 2) * 170;
    const by = 20 + ((Math.cos(t * 1.1) + 1) / 2) * 120;
    g.fillStyle = '#7c3aed';
    g.beginPath();
    g.arc(bx, by, 5, 0, Math.PI * 2);
    g.fill();
  }

  dispose() {
    this.texture.dispose();
  }
}
