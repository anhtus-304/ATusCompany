/** Một nhân vật trong văn phòng: sprite pixel, di chuyển theo đường đi, bong bóng, cảnh báo, nhãn tên. */
import { Container, Graphics, Rectangle, Text } from 'pixi.js';
import type { Activity, Agent } from '../types';
import { bubbleText } from '../types';
import { PX, type Spot } from './layout';
import { PIXEL_FONT } from './furniture';
import { lookFor, pixels, spriteRows, SPRITE_W, type Look, type Pose } from './sprites';

const ICONS: Record<string, string[]> = {
  typing: ['........', '.kkkkkk.', 'kwkwkwkk', 'kkwkwkwk', 'kwwwwwkk', '.kkkkkk.', '........'],
  reading: ['........', '.bb..bb.', 'bwwbbwwb', 'bwwbbwwb', 'bwwbbwwb', '.bbbbbb.', '........'],
  thinking: ['..kkkk..', '.kwwwwk.', 'kwkwkwwk', 'kwwwwwwk', '.kwwwwk.', '..kk....', '.k......'],
  reviewing: ['.kkk....', 'kwwwk...', 'kwwwk...', 'kwwwk...', '.kkkkk..', '....kk..', '.....kk.'],
  testing: ['..k..k..', '...kk...', '.kgggk..', 'kkgggkk.', '.kgggk..', 'k.kkk.k.', '........'],
  drawing: ['......kk', '.....kpk', '....kpk.', '...kpk..', '..kyk...', '.kyk....', 'kk......'],
  meeting: ['.kk..kk.', 'kwwkkwwk', '.kk..kk.', 'kwwkkwwk', 'kwwkkwwk', '........', '........'],
  idle: ['........', 'kkkk....', '..k.....', '.k..kkk.', 'kkkk..k.', '.....k..', '....kkk.'],
};
const ICON_COLORS: Record<string, number> = {
  k: 0x2b2b38,
  w: 0xffffff,
  b: 0x3b82f6,
  g: 0x53c08a,
  p: 0xe46b8a,
  y: 0xf3d36b,
};

function drawIcon(g: Graphics, name: string, x: number, y: number, s = 2) {
  const map = ICONS[name] ?? ICONS.thinking;
  map.forEach((row, iy) =>
    [...row].forEach((k, ix) => {
      const c = ICON_COLORS[k];
      if (c !== undefined) g.rect(x + ix * s, y + iy * s, s, s).fill(c);
    }),
  );
}

export class Character {
  readonly id: string;
  /** phần nằm trong lớp thế giới (sắp xếp theo y) */
  readonly body = new Container();
  /** phần nằm trên cùng (nhãn, bong bóng) */
  readonly overlay = new Container();

  private sprite = new Graphics();
  private shadow = new Graphics();
  private ring = new Graphics();
  private bubble = new Container();
  private bubbleBg = new Graphics();
  private bubbleIcon = new Graphics();
  private bubbleText: Text;
  private warn = new Graphics();
  private nameTag = new Container();
  private nameBg = new Graphics();
  private nameText: Text;

  private look: Look;
  private pose: Pose | null = null;
  private path: { x: number; y: number }[] = [];
  private walkT = 0;
  private animT = Math.random() * 10;
  x = 0;
  y = 0;
  seated = false;
  spot: Spot | null = null;
  agent: Agent;
  selected = false;

  constructor(agent: Agent, onOver: (c: Character) => void, onOut: () => void, onTap: (c: Character) => void) {
    this.id = agent.id;
    this.agent = agent;
    this.look = lookFor(agent.id);

    this.body.addChild(this.shadow, this.sprite);
    this.body.eventMode = 'static';
    this.body.cursor = 'pointer';
    const w = SPRITE_W * PX;
    this.body.hitArea = new Rectangle(-w / 2 - 4, -20 * PX, w + 8, 20 * PX + 6);
    this.body.on('pointerover', () => onOver(this));
    this.body.on('pointerout', onOut);
    this.body.on('pointertap', () => onTap(this));

    this.bubbleText = new Text({ text: '', style: { fontFamily: PIXEL_FONT, fontSize: 17, fill: 0x2b2b38 } });
    this.bubbleText.resolution = 3;
    this.bubble.addChild(this.bubbleBg, this.bubbleIcon, this.bubbleText);

    this.nameText = new Text({ text: agent.name, style: { fontFamily: PIXEL_FONT, fontSize: 16, fill: 0xffffff } });
    this.nameText.resolution = 3;
    this.nameTag.addChild(this.nameBg, this.nameText);

    this.overlay.addChild(this.ring, this.nameTag, this.bubble, this.warn);
    this.setAgent(agent);
  }

  place(spot: Spot) {
    this.spot = spot;
    this.x = spot.x;
    this.y = spot.y;
    this.seated = spot.seated;
    this.path = [];
  }

  walk(path: { x: number; y: number }[], spot: Spot) {
    this.spot = spot;
    this.path = path;
    this.seated = false;
  }

  get walking() {
    return this.path.length > 0;
  }

  setAgent(a: Agent) {
    this.agent = a;
    this.nameText.text = a.name;
    const pad = 5;
    this.nameBg.clear();
    this.nameBg
      .roundRect(-this.nameText.width / 2 - pad, 0, this.nameText.width + pad * 2, 17, 3)
      .fill({ color: 0x1b1f2b, alpha: 0.82 });
    this.nameText.position.set(-this.nameText.width / 2, -1);

    // bong bóng
    const text = bubbleText(a);
    const blocked = a.status === 'blocked';
    this.bubble.visible = !!text || a.status === 'idle';
    this.bubbleIcon.clear();
    const icon: Activity | 'idle' = a.status === 'idle' && a.activity !== 'meeting' ? 'idle' : a.activity;
    drawIcon(this.bubbleIcon, icon, 0, 0);
    this.bubbleText.text = text ?? '';
    this.bubbleText.style.fill = blocked ? 0xb42318 : 0x2b2b38;
    const iconW = 16;
    const tw = text ? this.bubbleText.width + 6 : 0;
    const w = 10 + iconW + tw;
    const h = 24;
    this.bubbleBg.clear();
    const fill = blocked ? 0xffe4e4 : 0xffffff;
    const edge = blocked ? 0xd92d20 : 0x2b2b38;
    this.bubbleBg.roundRect(-w / 2, -h, w, h, 6).fill(edge);
    this.bubbleBg.roundRect(-w / 2 + 2, -h + 2, w - 4, h - 4, 5).fill(fill);
    this.bubbleBg.rect(-4, -2, 8, 4).fill(fill);
    this.bubbleBg.rect(-2, 0, 4, 4).fill(edge);
    this.bubbleBg.rect(-6, -2, 2, 2).fill(edge);
    this.bubbleBg.rect(4, -2, 2, 2).fill(edge);
    this.bubbleIcon.position.set(-w / 2 + 5, -h + 4);
    this.bubbleText.position.set(-w / 2 + 5 + iconW + 2, -h + 1);
    this.bubble.alpha = a.status === 'idle' && !text ? 0.75 : 1;

    // biểu tượng cảnh báo
    this.warn.clear();
    if (blocked) {
      this.warn.rect(-9, -22, 18, 22).fill(0x7a1010);
      this.warn.rect(-7, -20, 14, 18).fill(0xef4444);
      this.warn.rect(-2, -17, 4, 9).fill(0xffffff);
      this.warn.rect(-2, -6, 4, 3).fill(0xffffff);
    }
    this.warn.visible = blocked;
  }

  setSelected(v: boolean) {
    this.selected = v;
  }

  private drawSprite(pose: Pose) {
    if (pose === this.pose) return;
    this.pose = pose;
    const g = this.sprite;
    g.clear();
    const rows = spriteRows(pose);
    const ox = -(SPRITE_W * PX) / 2;
    const oy = -rows * PX;
    for (const p of pixels(this.look, pose)) g.rect(ox + p.x * PX, oy + p.y * PX, PX, PX).fill(p.color);
  }

  /** dt tính bằng giây */
  update(dt: number) {
    this.animT += dt;
    // di chuyển
    if (this.path.length) {
      const target = this.path[0];
      const dx = target.x - this.x;
      const dy = target.y - this.y;
      const d = Math.hypot(dx, dy);
      const step = 78 * dt;
      if (d <= step) {
        this.x = target.x;
        this.y = target.y;
        this.path.shift();
        if (!this.path.length) this.seated = !!this.spot?.seated;
      } else {
        this.x += (dx / d) * step;
        this.y += (dy / d) * step;
      }
      this.walkT += dt;
    }

    const a = this.agent;
    let pose: Pose;
    let bob = 0;
    if (this.path.length) pose = Math.floor(this.walkT / 0.16) % 2 ? 'walkA' : 'walkB';
    else if (this.seated) {
      const typing = a.status === 'working' && (a.activity === 'typing' || a.activity === 'drawing');
      pose = typing && Math.floor(this.animT / 0.18) % 2 ? 'sitType' : 'sit';
      if (a.status === 'working' && a.activity === 'thinking') bob = Math.sin(this.animT * 2) > 0.6 ? -PX : 0;
      if (a.status === 'idle') bob = Math.floor(this.animT / 1.2) % 2 ? -1 : 0;
    } else {
      pose = 'stand';
      bob = Math.floor(this.animT / 0.9) % 2 ? -1 : 0;
    }
    this.drawSprite(pose);

    this.body.position.set(Math.round(this.x), Math.round(this.y));
    this.sprite.y = bob;
    this.body.zIndex = this.y + 0.1;

    // bóng & vòng chọn (chỉ khi đứng; khi ngồi bàn che chân)
    this.shadow.clear();
    this.ring.clear();
    if (!this.seated) this.shadow.ellipse(0, 0, 15, 5).fill({ color: 0x000000, alpha: 0.18 });
    const rows = spriteRows(pose);
    const headY = -rows * PX + bob;

    // nhãn tên dưới nhân vật (khi ngồi: dưới mép bàn)
    const tagY = this.seated && this.spot?.seat ? this.spot.seat.deskY + 30 - this.y : 6;
    this.nameTag.position.set(this.x, this.y + tagY);
    this.ring.position.set(this.x, this.y);
    if (this.selected) {
      const w = this.nameText.width + 14;
      this.ring.roundRect(-w / 2, tagY - 2, w, 20, 4).stroke({ color: 0xf59e0b, width: 2 });
      if (!this.seated) this.ring.ellipse(0, 0, 20, 7).stroke({ color: 0xf59e0b, width: 2 });
    }

    // bong bóng và cảnh báo trên đầu
    const float = Math.sin(this.animT * 2.4) * 1.5;
    const blocked = a.status === 'blocked';
    if (blocked) {
      this.warn.position.set(this.x, this.y + headY - 8 + Math.sin(this.animT * 6) * 2);
      this.bubble.position.set(this.x, this.y + headY - 36 + float);
    } else {
      this.bubble.position.set(this.x, this.y + headY - 6 + float);
    }
  }

  /** Vị trí đầu, để đặt hiệu ứng. */
  headPos() {
    return { x: this.x, y: this.y - (this.seated ? 14 : 20) * PX };
  }

  destroy() {
    this.body.destroy({ children: true });
    this.overlay.destroy({ children: true });
  }
}
