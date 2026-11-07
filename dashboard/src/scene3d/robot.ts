/** Robot agent dựng từ khối cơ bản: thân, đầu có kính mặt phát sáng, tay chân chuyển động. */
import {
  CapsuleGeometry,
  Color,
  CylinderGeometry,
  Group,
  Mesh,
  MeshStandardMaterial,
  RingGeometry,
  TorusGeometry,
  type Object3D,
} from 'three';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { lookFor } from '../scene/sprites';

const hex = (n: number) => new Color(n);

export interface RobotParts {
  root: Group;
  body: Group;
  head: Group;
  armL: Group;
  armR: Group;
  legL: Group;
  legR: Group;
  eyes: MeshStandardMaterial;
  ring: Mesh;
  warnRing: Mesh;
  hit: Object3D[];
}

export function buildRobot(id: string, bodyColor: string): RobotParts {
  const look = lookFor(id);
  const accent = hex(look.shirt);
  const capColor = hex(look.hair);

  const white = new MeshStandardMaterial({ color: bodyColor, roughness: 0.45, metalness: 0.05 });
  const joint = new MeshStandardMaterial({ color: '#2a3142', roughness: 0.6 });
  const accentMat = new MeshStandardMaterial({ color: accent, roughness: 0.5 });
  const visor = new MeshStandardMaterial({ color: '#0d1220', roughness: 0.25, metalness: 0.3 });
  const eyes = new MeshStandardMaterial({ color: '#7dd3fc', emissive: '#38bdf8', emissiveIntensity: 1.6 });

  const root = new Group();
  const body = new Group();
  root.add(body);

  // chân
  const leg = () => {
    const g = new Group();
    const m = new Mesh(new CapsuleGeometry(0.075, 0.26, 4, 10), joint);
    m.position.y = -0.2;
    const foot = new Mesh(new RoundedBoxGeometry(0.17, 0.09, 0.24, 2, 0.04), white);
    foot.position.set(0, -0.42, 0.03);
    g.add(m, foot);
    g.position.y = 0.46;
    return g;
  };
  const legL = leg();
  const legR = leg();
  legL.position.x = -0.12;
  legR.position.x = 0.12;
  body.add(legL, legR);

  // thân
  const torso = new Mesh(new RoundedBoxGeometry(0.5, 0.5, 0.34, 4, 0.12), white);
  torso.position.y = 0.72;
  const chest = new Mesh(new RoundedBoxGeometry(0.3, 0.14, 0.04, 2, 0.02), accentMat);
  chest.position.set(0, 0.76, 0.17);
  const back = new Mesh(new RoundedBoxGeometry(0.34, 0.32, 0.06, 2, 0.03), accentMat);
  back.position.set(0, 0.74, -0.18);
  const belt = new Mesh(new CylinderGeometry(0.24, 0.24, 0.06, 18), joint);
  belt.position.y = 0.5;
  body.add(torso, chest, back, belt);

  // tay
  const arm = (side: number) => {
    const g = new Group();
    const m = new Mesh(new CapsuleGeometry(0.06, 0.26, 4, 10), white);
    m.position.y = -0.17;
    const hand = new Mesh(new RoundedBoxGeometry(0.11, 0.1, 0.11, 2, 0.04), joint);
    hand.position.y = -0.36;
    g.add(m, hand);
    g.position.set(side * 0.32, 0.92, 0);
    return g;
  };
  const armL = arm(-1);
  const armR = arm(1);
  body.add(armL, armR);

  // đầu
  const head = new Group();
  head.position.y = 1.2;
  const skull = new Mesh(new RoundedBoxGeometry(0.52, 0.42, 0.42, 5, 0.15), white);
  const face = new Mesh(new RoundedBoxGeometry(0.42, 0.24, 0.05, 3, 0.05), visor);
  face.position.set(0, -0.01, 0.2);
  const eyeGeo = new RoundedBoxGeometry(0.07, 0.06, 0.02, 2, 0.02);
  const eL = new Mesh(eyeGeo, eyes);
  const eR = new Mesh(eyeGeo, eyes);
  eL.position.set(-0.09, 0.0, 0.23);
  eR.position.set(0.09, 0.0, 0.23);
  const cap = new Mesh(new RoundedBoxGeometry(0.46, 0.08, 0.36, 2, 0.04), new MeshStandardMaterial({ color: capColor, roughness: 0.5 }));
  cap.position.y = 0.21;
  const neck = new Mesh(new CylinderGeometry(0.07, 0.07, 0.1, 10), joint);
  neck.position.y = -0.24;
  head.add(skull, face, eL, eR, cap, neck);

  const extraMat = new MeshStandardMaterial({ color: look.extraColor ?? 0xe0483e, roughness: 0.5 });
  switch (look.extra) {
    case 'headphones': {
      const band = new Mesh(new TorusGeometry(0.29, 0.03, 8, 24, Math.PI), joint);
      band.position.y = 0.04;
      const cupL = new Mesh(new CylinderGeometry(0.09, 0.09, 0.06, 14), extraMat);
      cupL.rotation.z = Math.PI / 2;
      cupL.position.set(-0.28, 0.0, 0);
      const cupR = cupL.clone();
      cupR.position.x = 0.28;
      head.add(band, cupL, cupR);
      break;
    }
    case 'tie': {
      const tie = new Mesh(new RoundedBoxGeometry(0.08, 0.2, 0.03, 2, 0.01), extraMat);
      tie.position.set(0, 0.62, 0.18);
      body.add(tie);
      const ant = new Mesh(new CylinderGeometry(0.015, 0.015, 0.16, 6), joint);
      ant.position.y = 0.32;
      const bulb = new Mesh(new RoundedBoxGeometry(0.07, 0.07, 0.07, 2, 0.03), new MeshStandardMaterial({ color: '#fbbf24', emissive: '#f59e0b', emissiveIntensity: 1.2 }));
      bulb.position.y = 0.42;
      head.add(ant, bulb);
      break;
    }
    case 'beret': {
      const b = new Mesh(new CylinderGeometry(0.24, 0.27, 0.07, 18), extraMat);
      b.position.set(0.04, 0.26, 0);
      b.rotation.z = -0.15;
      head.add(b);
      break;
    }
    case 'glasses': {
      const bar = new Mesh(new RoundedBoxGeometry(0.4, 0.03, 0.02, 1, 0.01), new MeshStandardMaterial({ color: '#e5e7eb', emissive: '#94a3b8', emissiveIntensity: 0.4 }));
      bar.position.set(0, 0.05, 0.235);
      head.add(bar);
      break;
    }
  }
  if (look.hairStyle === 'cap') {
    const brim = new Mesh(new RoundedBoxGeometry(0.4, 0.03, 0.18, 1, 0.01), new MeshStandardMaterial({ color: look.extraColor ?? 0xe9b949 }));
    brim.position.set(0, 0.2, 0.24);
    head.add(brim);
  }
  body.add(head);

  // vòng chọn & vòng cảnh báo dưới chân
  const ring = new Mesh(new RingGeometry(0.42, 0.52, 40), new MeshStandardMaterial({ color: '#f59e0b', emissive: '#f97316', emissiveIntensity: 1.2, transparent: true, opacity: 0.95 }));
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.012;
  ring.visible = false;
  const warnRing = new Mesh(new RingGeometry(0.34, 0.6, 40), new MeshStandardMaterial({ color: '#ef4444', emissive: '#ef4444', emissiveIntensity: 1.4, transparent: true, opacity: 0.5 }));
  warnRing.rotation.x = -Math.PI / 2;
  warnRing.position.y = 0.01;
  warnRing.visible = false;
  root.add(ring, warnRing);

  const hit: Object3D[] = [];
  root.traverse((o) => {
    if ((o as Mesh).isMesh && o !== ring && o !== warnRing) {
      o.castShadow = true;
      o.userData.agentId = id;
      hit.push(o);
    }
  });

  return { root, body, head, armL, armR, legL, legR, eyes, ring, warnRing, hit };
}
