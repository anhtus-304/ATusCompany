/** Màu cảnh 3D theo theme (bố cục giữ nguyên). */
import type { ThemeId } from '../scene/palette';

export interface Palette3D {
  bg: string;
  skyTop: string;
  skyBottom: string;
  building: string;
  windowLit: string[];
  night: boolean;
  floor: string;
  slab: string;
  pad: Record<'code' | 'creative' | 'lead' | 'lounge', string>;
  edge: Record<'code' | 'creative' | 'lead' | 'lounge', string>;
  wall: string;
  glass: string;
  glassOpacity: number;
  frame: string;
  desk: string;
  deskLeg: string;
  chair: string;
  robot: string;
  hemiSky: string;
  hemiGround: string;
  hemi: number;
  sun: number;
  sunColor: string;
  accent: string;
}

const dark: Palette3D = {
  bg: '#070b14',
  skyTop: '#05070f',
  skyBottom: '#1a2340',
  building: '#0c1222',
  windowLit: ['#ffd27a', '#ffe7ad', '#9fd4fb', '#ffb86b'],
  night: true,
  floor: '#232b3d',
  slab: '#0d121e',
  pad: { code: '#26365a', creative: '#21402f', lead: '#3a3226', lounge: '#2a2f3c' },
  edge: { code: '#3b82f6', creative: '#22c55e', lead: '#f59e0b', lounge: '#64748b' },
  wall: '#2a3247',
  glass: '#6d9be0',
  glassOpacity: 0.2,
  frame: '#4a5675',
  desk: '#e9edf3',
  deskLeg: '#9aa3b2',
  chair: '#2b3245',
  robot: '#f3f5f8',
  hemiSky: '#8fb2ff',
  hemiGround: '#1a1f2e',
  hemi: 1.25,
  sun: 1.9,
  sunColor: '#cfdcff',
  accent: '#60a5fa',
};

const sky: Palette3D = {
  ...dark,
  bg: '#dfeefa',
  skyTop: '#9fcff6',
  skyBottom: '#f3f8fd',
  building: '#b7c8dc',
  windowLit: ['#e9f3fc', '#d6e6f5', '#ffffff'],
  night: false,
  floor: '#e7edf4',
  slab: '#c4d0dd',
  pad: { code: '#d6e6fb', creative: '#d8f1de', lead: '#f6ecd8', lounge: '#eceff3' },
  edge: { code: '#3b82f6', creative: '#16a34a', lead: '#d97706', lounge: '#94a3b8' },
  wall: '#f4f1ea',
  glass: '#8ec5f2',
  glassOpacity: 0.22,
  frame: '#c3ccd8',
  desk: '#ffffff',
  deskLeg: '#a7b0bd',
  chair: '#5b6b8c',
  hemiSky: '#ffffff',
  hemiGround: '#b9c3cf',
  hemi: 1.15,
  sun: 1.6,
  sunColor: '#fff6e8',
  accent: '#3b82f6',
};

const chibiBlue: Palette3D = {
  ...sky,
  bg: '#d6f1f4',
  skyTop: '#8fdde6',
  skyBottom: '#effcfc',
  building: '#a6d3d6',
  floor: '#e3f4f3',
  pad: { code: '#c7eaf7', creative: '#cdf3e3', lead: '#fdf3cf', lounge: '#e7f2f1' },
  edge: { code: '#0ea5c4', creative: '#10b981', lead: '#e0a800', lounge: '#7fb3b6' },
  wall: '#f2fbfa',
  accent: '#14a3b0',
};

const chibiPink: Palette3D = {
  ...sky,
  bg: '#fde8f0',
  skyTop: '#f7b6cf',
  skyBottom: '#fff4f8',
  building: '#e6c3d2',
  floor: '#fbeef2',
  pad: { code: '#e5dbfb', creative: '#fcd9e5', lead: '#fff1d6', lounge: '#f6eef1' },
  edge: { code: '#8b5cf6', creative: '#ec4899', lead: '#f59e0b', lounge: '#c9a3b4' },
  wall: '#fff7f9',
  glass: '#f3a6c4',
  accent: '#ec4899',
};

export const PALETTES_3D: Record<ThemeId, Palette3D> = { dark, sky, 'chibi-blue': chibiBlue, 'chibi-pink': chibiPink };
