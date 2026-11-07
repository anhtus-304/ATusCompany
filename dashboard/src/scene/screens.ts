/** Nội dung màn hình máy tính: mã chạy khi đang code, giao diện thử khi kiểm thử, tranh khi vẽ. */
import type { Graphics } from 'pixi.js';
import type { DeskKind } from './layout';

export type ScreenMode = 'off' | 'idle' | 'work' | 'alert';

const CODE_COLORS = [0x7fd3ff, 0xf3d36b, 0xc792ea, 0x9be29b, 0xf78c6c, 0xe8ebf0];

export class ScreenDisplay {
  private lines: { indent: number; parts: { w: number; c: number }[] }[] = [];
  private tick = 0;

  constructor(
    private g: Graphics,
    private rect: { x: number; y: number; w: number; h: number },
    private kind: DeskKind,
    private seed: number,
  ) {
    for (let i = 0; i < 8; i++) this.lines.push(this.randomLine());
  }

  private rand() {
    this.seed = (this.seed * 1103515245 + 12345) & 0x7fffffff;
    return this.seed / 0x7fffffff;
  }

  private randomLine() {
    const indent = Math.floor(this.rand() * 3) * 3;
    const n = 1 + Math.floor(this.rand() * 3);
    const parts = Array.from({ length: n }, () => ({
      w: 3 + Math.floor(this.rand() * 9),
      c: CODE_COLORS[Math.floor(this.rand() * CODE_COLORS.length)],
    }));
    return { indent, parts };
  }

  private acc = 0;
  private last: ScreenMode | null = null;

  /** Gọi mỗi khung hình; chỉ vẽ lại vài lần mỗi giây. */
  update(mode: ScreenMode, dt: number) {
    this.tick += dt;
    this.acc += dt;
    if (this.acc < 0.15 && mode === this.last) return;
    this.acc = 0;
    if (mode === 'work' && this.tick > 0.3) {
      this.tick = 0;
      this.lines.shift();
      this.lines.push(this.randomLine());
    }
    this.last = mode;
    this.draw(mode);
  }

  private draw(mode: ScreenMode) {
    const { x, y, w, h } = this.rect;
    const g = this.g;
    g.clear();
    const R = (rx: number, ry: number, rw: number, rh: number, c: number, a = 1) =>
      g.rect(Math.round(rx), Math.round(ry), Math.round(rw), Math.round(rh)).fill({ color: c, alpha: a });

    if (mode === 'off') {
      R(x, y, w, h, 0x1a2030);
      R(x + 2, y + 2, 6, 2, 0xffffff, 0.12);
      return;
    }
    if (mode === 'alert') {
      R(x, y, w, h, 0x5a1620);
      const blink = Math.floor(performance.now() / 400) % 2 === 0;
      R(x + w / 2 - 2, y + 4, 4, h - 12, blink ? 0xff6b6b : 0xffb3b3);
      R(x + w / 2 - 2, y + h - 6, 4, 3, blink ? 0xff6b6b : 0xffb3b3);
      return;
    }
    if (mode === 'idle') {
      // màn hình chờ: logo nhỏ trôi
      R(x, y, w, h, 0x1d2a44);
      const t = performance.now() / 1000;
      const lx = x + 4 + ((Math.sin(t * 0.7 + this.seed) + 1) / 2) * (w - 14);
      const ly = y + 3 + ((Math.cos(t * 0.9 + this.seed) + 1) / 2) * (h - 10);
      R(lx, ly, 8, 5, 0x3b82f6);
      R(lx + 2, ly + 1, 4, 3, 0x9fd4fb);
      return;
    }

    if (this.kind === 'code' || this.kind === 'lead') {
      R(x, y, w, h, 0x1e2433);
      R(x, y, w, 3, 0x2f3850);
      R(x + 2, y + 1, 2, 1, 0xf78c6c);
      R(x + 5, y + 1, 2, 1, 0xf3d36b);
      R(x + 8, y + 1, 2, 1, 0x9be29b);
      this.lines.forEach((ln, i) => {
        let cx = x + 3 + ln.indent;
        const cy = y + 5 + i * 2.6;
        if (cy > y + h - 2) return;
        for (const p of ln.parts) {
          const pw = Math.min(p.w, x + w - 2 - cx);
          if (pw > 0) R(cx, cy, pw, 1.4, p.c);
          cx += p.w + 2;
        }
      });
      // con trỏ nhấp nháy
      if (Math.floor(performance.now() / 300) % 2 === 0) R(x + 3 + this.lines[7].indent, y + h - 3, 2, 2, 0xffffff);
    } else if (this.kind === 'test') {
      // trang web đang được thử
      R(x, y, w, h, 0xf6f8fb);
      R(x, y, w, 4, 0x3b82f6);
      R(x + 3, y + 7, w * 0.5, 3, 0x2b2b38);
      R(x + 3, y + 12, w * 0.7, 2, 0x9aa3b2);
      R(x + 3, y + 16, 12, 4, 0xf08c3a);
      R(x + w - 16, y + 7, 13, 13, 0xb5e2b8);
      // quét kiểm thử
      const t = (performance.now() / 1200) % 1;
      R(x, y + 4 + t * (h - 5), w, 1, 0x53c08a, 0.9);
      R(x + w - 9, y + h - 6, 7, 4, 0x53c08a);
    } else {
      // designer: bảng màu + hình vẽ
      R(x, y, w, h, 0xfdf6ec);
      R(x, y, 6, h, 0x3a3f4b);
      [0xe0483e, 0xf3d36b, 0x53c08a, 0x3b82f6, 0xc792ea].forEach((c, i) => R(x + 1, y + 2 + i * 4, 4, 3, c));
      const t = performance.now() / 1000;
      R(x + 10, y + 4, 14, 10, 0xffb3c7);
      R(x + 20, y + 10, 14, 10, 0x9fd4fb);
      const bx = x + 12 + ((Math.sin(t * 1.4) + 1) / 2) * (w - 22);
      const by = y + 6 + ((Math.cos(t * 1.1) + 1) / 2) * (h - 12);
      R(bx, by, 3, 3, 0x7a5bc4);
    }
  }
}
