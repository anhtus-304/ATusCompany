/** Màu của cảnh văn phòng theo theme. Theme chỉ đổi màu, không đổi bố cục. */

export type ThemeId = 'sky' | 'chibi-blue' | 'chibi-pink' | 'dark';

export interface ScenePalette {
  bg: number;
  wall: number;
  wallShade: number;
  wallTrim: number;
  floorA: number;
  floorB: number;
  floorLine: number;
  codeCarpet: number;
  codeCarpetEdge: number;
  studioCarpet: number;
  studioCarpetEdge: number;
  leadRug: number;
  leadRugEdge: number;
  wood: number;
  woodDark: number;
  deskTop: number;
  deskFront: number;
  window: number;
  windowSky: number;
  accent: number;
  partition: number;
  partitionTop: number;
  screenOff: number;
  label: number;
  labelText: number;
}

const sky: ScenePalette = {
  bg: 0xdfeefa,
  wall: 0xf6ead2,
  wallShade: 0xe6d6b8,
  wallTrim: 0xb99a6e,
  floorA: 0xd8b48a,
  floorB: 0xcfa87d,
  floorLine: 0xb98f63,
  codeCarpet: 0xa9cdf0,
  codeCarpetEdge: 0x7fb0e0,
  studioCarpet: 0xb5e2b8,
  studioCarpetEdge: 0x86c98d,
  leadRug: 0xe9d9b7,
  leadRugEdge: 0xc8a978,
  wood: 0xb07a4a,
  woodDark: 0x80552f,
  deskTop: 0xe8c79a,
  deskFront: 0xb98a58,
  window: 0xffffff,
  windowSky: 0x9fd4fb,
  accent: 0x3b82f6,
  partition: 0xeadbbd,
  partitionTop: 0xfff6e4,
  screenOff: 0x2a3446,
  label: 0x2f3e66,
  labelText: 0xffffff,
};

const chibiBlue: ScenePalette = {
  ...sky,
  bg: 0xd6f1f4,
  wall: 0xeefaf8,
  wallShade: 0xd3ece9,
  wallTrim: 0x86b9c0,
  floorA: 0xc8e4ec,
  floorB: 0xbddce6,
  floorLine: 0xa3c9d6,
  codeCarpet: 0x9ed8f5,
  codeCarpetEdge: 0x63bce8,
  studioCarpet: 0xb7ecd5,
  studioCarpetEdge: 0x7fd6b1,
  leadRug: 0xfdf2c6,
  leadRugEdge: 0xe8cf7c,
  deskTop: 0xffffff,
  deskFront: 0xc9dde6,
  accent: 0x14b8c4,
  partition: 0xdcefee,
  partitionTop: 0xffffff,
  label: 0x1d7f8c,
};

const chibiPink: ScenePalette = {
  ...sky,
  bg: 0xfde8f0,
  wall: 0xfff1f4,
  wallShade: 0xf6d9e1,
  wallTrim: 0xd99aae,
  floorA: 0xf6d9cf,
  floorB: 0xf0cfc4,
  floorLine: 0xe0b3a6,
  codeCarpet: 0xd9c8f6,
  codeCarpetEdge: 0xb69ff0,
  studioCarpet: 0xfbc8d8,
  studioCarpetEdge: 0xf39ab8,
  leadRug: 0xfff3d6,
  leadRugEdge: 0xf0c98a,
  deskTop: 0xfff8f2,
  deskFront: 0xe8c3c0,
  accent: 0xec4899,
  partition: 0xf9e1e8,
  partitionTop: 0xffffff,
  label: 0xbe3f78,
};

const dark: ScenePalette = {
  ...sky,
  bg: 0x0f1522,
  wall: 0x2a3247,
  wallShade: 0x222a3c,
  wallTrim: 0x4a5675,
  floorA: 0x3a3340,
  floorB: 0x342e3a,
  floorLine: 0x2a2530,
  codeCarpet: 0x24406a,
  codeCarpetEdge: 0x305a92,
  studioCarpet: 0x1f4d3c,
  studioCarpetEdge: 0x2b6b52,
  leadRug: 0x4a3f33,
  leadRugEdge: 0x6b5a45,
  wood: 0x6b4a33,
  woodDark: 0x4a3222,
  deskTop: 0x5a4a3e,
  deskFront: 0x3f342c,
  window: 0x3a4560,
  windowSky: 0x1b2a4a,
  accent: 0x60a5fa,
  partition: 0x323b52,
  partitionTop: 0x414c68,
  screenOff: 0x161c28,
  label: 0x60a5fa,
  labelText: 0x0f1522,
};

export const SCENE_PALETTES: Record<ThemeId, ScenePalette> = {
  sky,
  'chibi-blue': chibiBlue,
  'chibi-pink': chibiPink,
  dark,
};

export const THEMES: { id: ThemeId; label: string }[] = [
  { id: 'sky', label: 'Xanh nhạt' },
  { id: 'chibi-blue', label: 'Chibi Xanh' },
  { id: 'chibi-pink', label: 'Chibi Hồng' },
  { id: 'dark', label: 'Tối' },
];
