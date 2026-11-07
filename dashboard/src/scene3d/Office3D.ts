/**
 * Văn phòng 3D bằng Three.js. Giống OfficeRenderer bản pixel: chỉ nhận agent/task qua update()
 * rồi vẽ cho khớp (robot đi lại, màn hình chạy mã, bong bóng, pháo giấy, cảnh báo).
 */
import {
  ACESFilmicToneMapping,
  CanvasTexture,
  Clock,
  Color,
  DirectionalLight,
  Fog,
  HemisphereLight,
  Mesh,
  MeshBasicMaterial,
  PCFSoftShadowMap,
  PerspectiveCamera,
  PlaneGeometry,
  PointLight,
  Raycaster,
  Scene,
  SRGBColorSpace,
  Vector2,
  Vector3,
  WebGLRenderer,
  DoubleSide,
  type Object3D,
} from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { Agent, Task } from '../types';
import { bubbleText } from '../types';
import type { ThemeId } from '../scene/palette';
import { homeSpots, meetingSpot, route3d, type Desk3D, type Spot3D } from './layout3d';
import { PALETTES_3D, type Palette3D } from './palette3d';
import { buildStatic, type StaticScene } from './props3d';
import { buildRobot, type RobotParts } from './robot';
import type { ScreenMode } from './screens3d';

export interface Scene3DHandlers {
  onHover: (agentId: string | null, pos: { x: number; y: number } | null) => void;
  onSelect: (agentId: string) => void;
}

interface Bot {
  id: string;
  parts: RobotParts;
  agent: Agent;
  x: number;
  z: number;
  heading: number;
  spot: Spot3D;
  path: { x: number; z: number }[];
  walkT: number;
  animT: number;
  tag: HTMLDivElement;
  bubble: HTMLDivElement;
  name: HTMLDivElement;
}

interface Particle {
  mesh: Mesh;
  vx: number;
  vy: number;
  vz: number;
  life: number;
  max: number;
  spin: Vector3;
}

const HOME_DIR = new Vector3(0.3, 0.78, 0.82).normalize();
const HOME_TARGET = new Vector3(0.2, 0, 1.0);
const CONFETTI = ['#ef4444', '#f59e0b', '#22c55e', '#3b82f6', '#a855f7', '#ec4899', '#facc15'];

export class Office3D {
  private renderer!: WebGLRenderer;
  private scene = new Scene();
  private camera = new PerspectiveCamera(36, 1, 0.1, 400);
  private controls!: OrbitControls;
  private clock = new Clock();
  private host: HTMLElement | null = null;
  private overlay = document.createElement('div');
  private resizeObs: ResizeObserver | null = null;
  private raf = 0;
  private theme: ThemeId = 'dark';
  private pal: Palette3D = PALETTES_3D.dark;
  private stat: StaticScene | null = null;
  private hemi = new HemisphereLight();
  private sun = new DirectionalLight();
  private glow = new PointLight('#60a5fa', 0, 30);
  private lamps: PointLight[] = [];
  private bots = new Map<string, Bot>();
  private homeDesk = new Map<string, Desk3D | undefined>();
  private taskStatus = new Map<string, Task['status']>();
  private firstUpdate = true;
  private selected: string | null = null;
  private handlers: Scene3DHandlers = { onHover: () => {}, onSelect: () => {} };
  private ray = new Raycaster();
  private ptr = new Vector2();
  private hoverId: string | null = null;
  private down: { x: number; y: number } | null = null;
  private particles: Particle[] = [];
  private camTween: { from: Vector3; to: Vector3; tFrom: Vector3; tTo: Vector3; t: number } | null = null;
  private destroyed = false;

  init(host: HTMLElement, theme: ThemeId) {
    this.host = host;
    this.renderer = new WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.outputColorSpace = SRGBColorSpace;
    this.renderer.toneMapping = ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = PCFSoftShadowMap;
    host.appendChild(this.renderer.domElement);
    this.renderer.domElement.style.display = 'block';
    this.renderer.domElement.style.touchAction = 'none';
    this.overlay.className = 'r3-overlay';
    host.appendChild(this.overlay);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.target.copy(HOME_TARGET);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.minDistance = 6;
    this.controls.maxDistance = 48;
    this.controls.maxPolarAngle = 1.32;
    this.controls.screenSpacePanning = false;

    this.sun.position.set(-10, 22, 12);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    const sc = this.sun.shadow.camera;
    sc.left = -17;
    sc.right = 17;
    sc.top = 13;
    sc.bottom = -13;
    sc.near = 1;
    sc.far = 60;
    this.sun.shadow.bias = -0.0005;
    this.sun.shadow.radius = 4;
    this.glow.position.set(0, 6, 0);
    this.scene.add(this.hemi, this.sun, this.glow);
    for (const [x, z, c] of [[-7, -3, '#9ec5ff'], [5, -3.5, '#b9f5c9'], [8, 5.6, '#ffd59a'], [-6, 5.5, '#ffe2b8']] as const) {
      const l = new PointLight(c, 0, 14, 1.6);
      l.position.set(x, 4.2, z);
      this.lamps.push(l);
      this.scene.add(l);
    }

    this.applyTheme(theme);
    this.bindPointer();
    this.resizeObs = new ResizeObserver(() => this.resize());
    this.resizeObs.observe(host);
    this.resize();
    this.camera.position.copy(this.homePos());
    this.loop();
  }

  setHandlers(h: Scene3DHandlers) {
    this.handlers = h;
  }

  setTheme(theme: ThemeId) {
    if (theme !== this.theme) this.applyTheme(theme);
  }

  private applyTheme(theme: ThemeId) {
    this.theme = theme;
    this.pal = PALETTES_3D[theme];
    const p = this.pal;
    this.scene.background = new Color(p.bg);
    this.scene.fog = new Fog(p.bg, 55, 90);
    this.hemi.color.set(p.hemiSky);
    this.hemi.groundColor.set(p.hemiGround);
    this.hemi.intensity = p.hemi;
    this.sun.color.set(p.sunColor);
    this.sun.intensity = p.sun;
    this.glow.intensity = p.night ? 30 : 0;
    for (const l of this.lamps) l.intensity = p.night ? 22 : 0;
    if (this.renderer) this.renderer.toneMappingExposure = p.night ? 1.3 : 1.05;
    if (this.stat) {
      this.scene.remove(this.stat.group);
      disposeTree(this.stat.group);
    }
    this.stat = buildStatic(p);
    this.scene.add(this.stat.group);
    this.overlay.dataset.night = p.night ? '1' : '0';
    // dựng lại robot để đổi màu thân
    const agents = [...this.bots.values()].map((b) => b.agent);
    if (agents.length) {
      const keep = new Map([...this.bots].map(([id, b]) => [id, { x: b.x, z: b.z, spot: b.spot, heading: b.heading }]));
      for (const b of this.bots.values()) this.removeBot(b);
      this.bots.clear();
      for (const a of agents) {
        const k = keep.get(a.id)!;
        const b = this.addBot(a, k.spot);
        b.x = k.x;
        b.z = k.z;
        b.heading = k.heading;
      }
      this.setSelected(this.selected);
    }
  }

  setSelected(id: string | null) {
    this.selected = id;
    for (const b of this.bots.values()) {
      b.parts.ring.visible = b.id === id;
      b.tag.classList.toggle('selected', b.id === id);
    }
  }

  /** Đưa camera tới một agent. */
  focus(id: string) {
    const b = this.bots.get(id);
    if (!b) return;
    const tTo = new Vector3(b.x, 0.8, b.z);
    const dir = this.camera.position.clone().sub(this.controls.target).normalize();
    const to = tTo.clone().add(dir.multiplyScalar(11));
    this.camTween = { from: this.camera.position.clone(), to, tFrom: this.controls.target.clone(), tTo, t: 0 };
  }

  /** Khoảng cách camera sao cho cả sàn vừa khung hình. */
  private homePos() {
    const v = (this.camera.fov * Math.PI) / 360;
    const h = 2 * Math.atan(Math.tan(v) * this.camera.aspect) / 2;
    const byW = (28 * 0.5) / Math.tan(h);
    const byH = (18 * 0.62) / Math.tan(v);
    const dist = Math.min(this.controls.maxDistance, Math.max(byW, byH) * (this.camera.aspect < 1 ? 1.2 : 1.08));
    return HOME_TARGET.clone().add(HOME_DIR.clone().multiplyScalar(dist));
  }

  resetView() {
    this.camTween = { from: this.camera.position.clone(), to: this.homePos(), tFrom: this.controls.target.clone(), tTo: HOME_TARGET.clone(), t: 0 };
  }

  rotate(dir: 1 | -1) {
    const off = this.camera.position.clone().sub(this.controls.target);
    off.applyAxisAngle(new Vector3(0, 1, 0), dir * (Math.PI / 6));
    this.camTween = { from: this.camera.position.clone(), to: this.controls.target.clone().add(off), tFrom: this.controls.target.clone(), tTo: this.controls.target.clone(), t: 0 };
  }

  zoom(f: number) {
    const off = this.camera.position.clone().sub(this.controls.target);
    const len = Math.min(this.controls.maxDistance, Math.max(this.controls.minDistance, off.length() * f));
    off.setLength(len);
    this.camTween = { from: this.camera.position.clone(), to: this.controls.target.clone().add(off), tFrom: this.controls.target.clone(), tTo: this.controls.target.clone(), t: 0 };
  }

  update(agents: Agent[], tasks: Task[]) {
    if (this.destroyed) return;
    const homes = homeSpots(agents);
    this.homeDesk = new Map([...homes].map(([id, sp]) => [id, sp.desk]));
    const meeting = agents.filter((a) => a.location === 'meeting');

    for (const [id, b] of this.bots) {
      if (!agents.find((a) => a.id === id)) {
        this.removeBot(b);
        this.bots.delete(id);
      }
    }

    for (const a of agents) {
      const home = homes.get(a.id)!;
      const mi = meeting.indexOf(a);
      const target = mi >= 0 ? meetingSpot(mi) : home;
      let b = this.bots.get(a.id);
      if (!b) {
        b = this.addBot(a, target);
        continue;
      }
      b.agent = a;
      const cur = b.spot;
      if (Math.abs(cur.x - target.x) > 0.01 || Math.abs(cur.z - target.z) > 0.01) {
        // đang đi dở thì coi như xuất phát từ khu của điểm đến cũ
        b.path = route3d({ x: b.x, z: b.z }, cur, target);
        b.spot = target;
      }
      this.refreshTag(b);
    }

    for (const t of tasks) {
      const prev = this.taskStatus.get(t.id);
      if (!this.firstUpdate && t.status === 'done' && prev !== 'done') {
        const b = this.bots.get(t.assignee);
        if (b) this.celebrate(b.x, 1.6, b.z);
      }
      this.taskStatus.set(t.id, t.status);
    }
    this.firstUpdate = false;
  }

  private addBot(a: Agent, spot: Spot3D): Bot {
    const parts = buildRobot(a.id, this.pal.robot);
    parts.root.position.set(spot.x, 0, spot.z);
    parts.root.rotation.y = spot.face;
    this.scene.add(parts.root);
    const tag = document.createElement('div');
    tag.className = 'r3-tag';
    const bubble = document.createElement('div');
    bubble.className = 'r3-bubble';
    const name = document.createElement('div');
    name.className = 'r3-name';
    tag.append(bubble, name);
    this.overlay.appendChild(tag);
    const b: Bot = { id: a.id, parts, agent: a, x: spot.x, z: spot.z, heading: spot.face, spot, path: [], walkT: 0, animT: Math.random() * 10, tag, bubble, name };
    this.bots.set(a.id, b);
    this.refreshTag(b);
    b.parts.ring.visible = a.id === this.selected;
    return b;
  }

  private removeBot(b: Bot) {
    this.scene.remove(b.parts.root);
    disposeTree(b.parts.root);
    b.tag.remove();
  }

  private refreshTag(b: Bot) {
    const a = b.agent;
    const text = bubbleText(a);
    b.tag.className = `r3-tag s-${a.status}${b.id === this.selected ? ' selected' : ''}`;
    b.name.innerHTML = '';
    const dot = document.createElement('span');
    dot.className = 'dot';
    b.name.append(dot, document.createTextNode(a.name));
    b.bubble.textContent = text ?? '';
    b.bubble.style.display = text ? '' : 'none';
    b.bubble.dataset.activity = a.status === 'blocked' ? 'blocked' : a.activity;
    b.parts.warnRing.visible = a.status === 'blocked';
    b.parts.eyes.emissive.set(a.status === 'blocked' ? '#ef4444' : a.status === 'idle' ? '#64748b' : '#38bdf8');
    b.parts.eyes.color.set(a.status === 'blocked' ? '#fca5a5' : a.status === 'idle' ? '#94a3b8' : '#7dd3fc');
  }

  private celebrate(x: number, y: number, z: number) {
    const geo = new PlaneGeometry(0.08, 0.13);
    for (let i = 0; i < 46; i++) {
      const mat = new MeshBasicMaterial({ color: CONFETTI[i % CONFETTI.length], side: DoubleSide, transparent: true });
      const m = new Mesh(geo, mat);
      m.position.set(x, y, z);
      const a = Math.random() * Math.PI * 2;
      const sp = 1.2 + Math.random() * 1.8;
      this.scene.add(m);
      this.particles.push({
        mesh: m,
        vx: Math.cos(a) * sp * 0.6,
        vy: 3 + Math.random() * 2.5,
        vz: Math.sin(a) * sp * 0.6,
        life: 0,
        max: 1.6 + Math.random() * 0.6,
        spin: new Vector3(Math.random() * 10, Math.random() * 10, Math.random() * 10),
      });
    }
    // sao lấp lánh: một vòng sáng ngắn
    const star = new Mesh(new PlaneGeometry(1.4, 1.4), new MeshBasicMaterial({ map: starTexture(), transparent: true, depthWrite: false, toneMapped: false }));
    star.position.set(x, y + 0.2, z);
    this.scene.add(star);
    this.particles.push({ mesh: star, vx: 0, vy: 0.3, vz: 0, life: 0, max: 1.0, spin: new Vector3(0, 0, 0) });
  }

  private bindPointer() {
    const el = this.renderer.domElement;
    el.addEventListener('pointermove', (e) => {
      const r = el.getBoundingClientRect();
      this.ptr.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      const id = this.pick();
      if (id !== this.hoverId) {
        this.hoverId = id;
        el.style.cursor = id ? 'pointer' : '';
        if (!id) this.handlers.onHover(null, null);
      }
    });
    el.addEventListener('pointerleave', () => {
      this.hoverId = null;
      this.handlers.onHover(null, null);
    });
    el.addEventListener('pointerdown', (e) => (this.down = { x: e.clientX, y: e.clientY }));
    el.addEventListener('pointerup', (e) => {
      if (!this.down) return;
      const moved = Math.hypot(e.clientX - this.down.x, e.clientY - this.down.y);
      this.down = null;
      if (moved > 5) return;
      const r = el.getBoundingClientRect();
      this.ptr.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      const id = this.pick();
      if (id) this.handlers.onSelect(id);
    });
    el.addEventListener('pointerdown', () => (this.camTween = null));
    el.addEventListener('wheel', () => (this.camTween = null), { passive: true });
  }

  private pick(): string | null {
    this.ray.setFromCamera(this.ptr, this.camera);
    const objs: Object3D[] = [];
    for (const b of this.bots.values()) objs.push(...b.parts.hit);
    const hit = this.ray.intersectObjects(objs, false)[0];
    return (hit?.object.userData.agentId as string) ?? null;
  }

  private resize() {
    if (!this.host) return;
    const w = Math.max(1, this.host.clientWidth);
    const h = Math.max(1, this.host.clientHeight);
    this.renderer.setSize(w, h);
    this.camera.aspect = w / h;
    // màn hình dọc: lùi camera để thấy đủ sàn
    this.camera.fov = w / h < 1 ? 52 : 36;
    this.camera.updateProjectionMatrix();
  }

  private loop = () => {
    if (this.destroyed) return;
    this.raf = requestAnimationFrame(this.loop);
    const dt = Math.min(this.clock.getDelta(), 0.05);
    this.step(dt);
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
    this.placeTags();
  };

  private step(dt: number) {
    if (this.camTween) {
      const tw = this.camTween;
      tw.t = Math.min(1, tw.t + dt / 0.8);
      const k = 1 - Math.pow(1 - tw.t, 3);
      this.camera.position.lerpVectors(tw.from, tw.to, k);
      this.controls.target.lerpVectors(tw.tFrom, tw.tTo, k);
      if (tw.t >= 1) this.camTween = null;
    }

    const deskMode = new Map<Desk3D, ScreenMode>();
    for (const b of this.bots.values()) {
      this.stepBot(b, dt);
      const d = this.homeDesk.get(b.id);
      if (d) {
        const atDesk = !b.path.length && b.spot.desk === d;
        const a = b.agent;
        deskMode.set(d, a.status === 'blocked' ? 'alert' : a.status === 'working' && atDesk ? 'work' : 'idle');
      }
    }
    if (this.stat) {
      for (const [d, screens] of this.stat.screensByDesk) {
        const mode = deskMode.get(d) ?? 'off';
        for (const s of screens) s.update(mode, dt);
      }
    }

    for (const p of this.particles) {
      p.life += dt;
      const m = p.mesh;
      if (p.spin.lengthSq() === 0) {
        const k = p.life / p.max;
        m.scale.setScalar(0.4 + Math.sin(Math.min(k, 1) * Math.PI) * 1.2);
        m.quaternion.copy(this.camera.quaternion);
        (m.material as MeshBasicMaterial).opacity = 1 - k;
        m.position.y += p.vy * dt;
        continue;
      }
      p.vy -= 7 * dt;
      m.position.x += p.vx * dt;
      m.position.y = Math.max(0.02, m.position.y + p.vy * dt);
      m.position.z += p.vz * dt;
      m.rotation.x += p.spin.x * dt;
      m.rotation.y += p.spin.y * dt;
      m.rotation.z += p.spin.z * dt;
      (m.material as MeshBasicMaterial).opacity = Math.max(0, 1 - Math.max(0, p.life / p.max - 0.6) / 0.4);
    }
    const dead = this.particles.filter((p) => p.life >= p.max);
    for (const p of dead) {
      this.scene.remove(p.mesh);
      (p.mesh.material as MeshBasicMaterial).map?.dispose();
      (p.mesh.material as MeshBasicMaterial).dispose();
    }
    if (dead.length) this.particles = this.particles.filter((p) => p.life < p.max);
  }

  private stepBot(b: Bot, dt: number) {
    b.animT += dt;
    const P = b.parts;
    let walking = false;
    if (b.path.length) {
      walking = true;
      const t = b.path[0];
      const dx = t.x - b.x;
      const dz = t.z - b.z;
      const d = Math.hypot(dx, dz);
      const stepLen = 1.9 * dt;
      if (d <= stepLen) {
        b.x = t.x;
        b.z = t.z;
        b.path.shift();
      } else {
        b.x += (dx / d) * stepLen;
        b.z += (dz / d) * stepLen;
      }
      if (d > 0.001) b.heading = turn(b.heading, Math.atan2(dx, dz), dt * 10);
      b.walkT += dt;
    } else {
      b.heading = turn(b.heading, b.spot.face, dt * 6);
    }
    P.root.position.set(b.x, 0, b.z);
    P.root.rotation.y = b.heading;

    const a = b.agent;
    const t = b.animT;
    // tư thế mặc định
    let legSwing = 0;
    let armL = 0;
    let armR = 0;
    let bob = Math.sin(t * 2) * 0.012;
    let headTilt = 0;
    let headTurn = 0;
    if (walking) {
      legSwing = Math.sin(b.walkT * 9) * 0.5;
      armL = -legSwing * 0.8;
      armR = legSwing * 0.8;
      bob = Math.abs(Math.sin(b.walkT * 9)) * 0.05;
    } else if (a.status === 'working') {
      switch (a.activity) {
        case 'typing':
        case 'drawing':
          armL = -0.9 + Math.sin(t * 16) * 0.12;
          armR = -0.9 + Math.sin(t * 16 + 1.7) * 0.12;
          headTilt = 0.12;
          break;
        case 'reading':
        case 'reviewing':
          armL = -0.5;
          armR = -0.5;
          headTilt = 0.18 + Math.sin(t * 0.8) * 0.04;
          headTurn = Math.sin(t * 0.6) * 0.25;
          break;
        case 'testing':
          armR = -1.0 + Math.sin(t * 6) * 0.2;
          headTurn = Math.sin(t * 1.4) * 0.3;
          break;
        case 'thinking':
          armR = -1.6;
          headTilt = -0.15;
          headTurn = Math.sin(t * 0.7) * 0.2;
          break;
        case 'meeting':
          armL = Math.sin(t * 3) * 0.3 - 0.2;
          armR = -Math.sin(t * 3) * 0.3 - 0.2;
          headTurn = Math.sin(t * 1.1) * 0.3;
          break;
      }
    } else if (a.status === 'blocked') {
      headTilt = 0.35;
      armL = 0.15;
      armR = 0.15;
      headTurn = Math.sin(t * 1.5) * 0.15;
    } else {
      headTurn = Math.sin(t * 0.4) * 0.35;
    }
    P.legL.rotation.x = legSwing;
    P.legR.rotation.x = -legSwing;
    P.armL.rotation.x = damp(P.armL.rotation.x, armL, dt * 12);
    P.armR.rotation.x = damp(P.armR.rotation.x, armR, dt * 12);
    P.head.rotation.x = damp(P.head.rotation.x, headTilt, dt * 6);
    P.head.rotation.y = damp(P.head.rotation.y, headTurn, dt * 6);
    P.body.position.y = bob;
    if (P.warnRing.visible) {
      const s = 1 + Math.sin(t * 5) * 0.12;
      P.warnRing.scale.set(s, s, s);
    }
    if (P.ring.visible) P.ring.rotation.z += dt * 0.8;
  }

  private placeTags() {
    if (!this.host) return;
    const w = this.host.clientWidth;
    const h = this.host.clientHeight;
    const v = new Vector3();
    for (const b of this.bots.values()) {
      v.set(b.x, 1.72, b.z).project(this.camera);
      const visible = v.z < 1 && v.x > -1.2 && v.x < 1.2 && v.y > -1.2 && v.y < 1.2;
      b.tag.style.display = visible ? '' : 'none';
      if (!visible) continue;
      const sx = (v.x * 0.5 + 0.5) * w;
      const sy = (-v.y * 0.5 + 0.5) * h;
      b.tag.style.transform = `translate(${sx.toFixed(1)}px, ${sy.toFixed(1)}px) translate(-50%, -100%)`;
      b.tag.style.zIndex = String(Math.round((1 - v.z) * 10000));
      if (b.id === this.hoverId) {
        const r = this.renderer.domElement.getBoundingClientRect();
        this.handlers.onHover(b.id, { x: r.left + sx, y: r.top + sy - 40 });
      }
    }
  }

  destroy() {
    this.destroyed = true;
    cancelAnimationFrame(this.raf);
    this.resizeObs?.disconnect();
    this.controls?.dispose();
    if (this.stat) disposeTree(this.stat.group);
    for (const b of this.bots.values()) this.removeBot(b);
    this.renderer?.dispose();
    this.renderer?.domElement.remove();
    this.overlay.remove();
  }
}

function turn(cur: number, target: number, k: number) {
  let d = target - cur;
  while (d > Math.PI) d -= Math.PI * 2;
  while (d < -Math.PI) d += Math.PI * 2;
  return cur + d * Math.min(1, k);
}

function damp(cur: number, target: number, k: number) {
  return cur + (target - cur) * Math.min(1, k);
}

let starTex: CanvasTexture | null = null;
function starTexture() {
  if (starTex) return starTex.clone();
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d')!;
  const grd = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grd.addColorStop(0, 'rgba(255,250,210,1)');
  grd.addColorStop(0.25, 'rgba(255,220,120,0.6)');
  grd.addColorStop(1, 'rgba(255,200,80,0)');
  g.fillStyle = grd;
  g.fillRect(0, 0, 128, 128);
  g.fillStyle = 'rgba(255,255,255,0.95)';
  g.fillRect(60, 6, 8, 116);
  g.fillRect(6, 60, 116, 8);
  starTex = new CanvasTexture(c);
  return starTex.clone();
}

function disposeTree(o: Object3D) {
  o.traverse((n) => {
    const m = n as Mesh;
    if (m.isMesh) {
      m.geometry?.dispose();
      const mats = Array.isArray(m.material) ? m.material : [m.material];
      for (const mat of mats) {
        (mat as MeshBasicMaterial).map?.dispose();
        mat.dispose();
      }
    }
  });
}
