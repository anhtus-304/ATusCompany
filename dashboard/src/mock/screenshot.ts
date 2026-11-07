/** Ảnh chụp màn hình giả (SVG data URL) để khung Chi tiết có ảnh khi chạy mock. */
export function mockScreenshot(title: string, color: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="320" height="200" viewBox="0 0 320 200">
<rect width="320" height="200" fill="#fdf8f2"/>
<rect width="320" height="22" fill="${color}"/>
<circle cx="12" cy="11" r="4" fill="#fff" opacity=".7"/><rect x="230" y="8" width="80" height="6" rx="3" fill="#fff" opacity=".6"/>
<text x="20" y="62" font-family="sans-serif" font-size="20" font-weight="700" fill="#2b2235">${title}</text>
<rect x="20" y="74" width="160" height="8" rx="4" fill="#c9bfb4"/><rect x="20" y="88" width="120" height="8" rx="4" fill="#c9bfb4"/>
<rect x="20" y="108" width="72" height="22" rx="11" fill="#f08c3a"/>
<rect x="196" y="40" width="104" height="90" rx="8" fill="${color}" opacity=".35"/>
<rect x="20" y="146" width="84" height="40" rx="6" fill="#efe6da"/><rect x="118" y="146" width="84" height="40" rx="6" fill="#efe6da"/><rect x="216" y="146" width="84" height="40" rx="6" fill="#efe6da"/>
</svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}
