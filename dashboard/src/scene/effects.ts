/** Hiệu ứng nhỏ: pháo giấy và sao lấp lánh khi hoàn thành task. */
import { Container, Graphics } from 'pixi.js';

interface Particle {
  g: Graphics;
  vx: number;
  vy: number;
  life: number;
  max: number;
  spin: number;
  star: boolean;
}

const CONFETTI = [0xef4444, 0xf59e0b, 0x22c55e, 0x3b82f6, 0xa855f7, 0xec4899, 0xfacc15];

export class Effects {
  readonly layer = new Container();
  private parts: Particle[] = [];

  celebrate(x: number, y: number) {
    for (let i = 0; i < 34; i++) {
      const g = new Graphics();
      const c = CONFETTI[i % CONFETTI.length];
      g.rect(-2, -3, 4, 6).fill(c);
      g.position.set(x, y);
      const ang = -Math.PI / 2 + (Math.random() - 0.5) * 2.2;
      const sp = 120 + Math.random() * 140;
      this.layer.addChild(g);
      this.parts.push({ g, vx: Math.cos(ang) * sp, vy: Math.sin(ang) * sp, life: 0, max: 1.4 + Math.random() * 0.6, spin: (Math.random() - 0.5) * 12, star: false });
    }
    for (let i = 0; i < 7; i++) {
      const g = new Graphics();
      g.rect(-1, -6, 2, 12).fill(0xfff3a0);
      g.rect(-6, -1, 12, 2).fill(0xfff3a0);
      g.rect(-2, -2, 4, 4).fill(0xffffff);
      g.position.set(x + (Math.random() - 0.5) * 70, y + (Math.random() - 0.5) * 50);
      g.scale.set(0);
      this.layer.addChild(g);
      this.parts.push({ g, vx: 0, vy: -10, life: -i * 0.12, max: 1.1, spin: 0, star: true });
    }
  }

  update(dt: number) {
    for (const p of this.parts) {
      p.life += dt;
      if (p.life < 0) continue;
      const k = p.life / p.max;
      if (p.star) {
        const s = Math.sin(Math.min(k, 1) * Math.PI) * 1.4;
        p.g.scale.set(s);
        p.g.y += p.vy * dt;
      } else {
        p.vy += 380 * dt;
        p.vx *= 0.985;
        p.g.x += p.vx * dt;
        p.g.y += p.vy * dt;
        p.g.rotation += p.spin * dt;
        p.g.alpha = Math.max(0, 1 - Math.max(0, k - 0.6) / 0.4);
      }
    }
    const dead = this.parts.filter((p) => p.life >= p.max);
    for (const p of dead) p.g.destroy();
    this.parts = this.parts.filter((p) => p.life < p.max);
  }
}
