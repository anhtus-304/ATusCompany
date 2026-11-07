# Dashboard “Văn phòng”

Giao diện cho sếp theo dõi đội AI agent của Virtual Tech Dept, vẽ như một văn phòng thật:
phòng Ban lãnh đạo, Xưởng code, Studio sáng tạo, góc nghỉ, bàn ghế, màn hình đang chạy mã, cây cảnh,
và các agent đang làm việc. Có hai kiểu văn phòng, chuyển bằng nút **3D / Pixel** ở góc trên phải:

- **3D** (mặc định, Three.js): sàn văn phòng nhìn từ trên xuống, robot agent đứng ở bàn hai màn hình,
  phòng kính Ban lãnh đạo, thành phố đêm phía sau. Kéo để xoay, chuột phải hoặc Shift+kéo để di chuyển,
  cuộn để phóng to; nút ⟲ ⟳ + − ⌂ ở góc dưới phải. Nút “Tìm trong văn phòng” ở tab Chi tiết đưa camera tới agent.
- **Pixel** (PixiJS): bản pixel-art 2D, nhẹ hơn, hợp máy yếu.

Dashboard **chỉ hiển thị**, không chứa logic điều phối: mọi thay đổi đến từ server qua WebSocket.

- React 19 + TypeScript + Vite
- Three.js vẽ văn phòng 3D, PixiJS 8 vẽ bản pixel (đồ họa dựng hoàn toàn bằng code, không cần file ảnh hay model);
  mỗi bản chỉ được tải khi được chọn
- Thanh bên, nhật ký, thống kê dùng HTML/CSS thường
- Font: Be Vietnam Pro cho nội dung, VT323 (có dấu tiếng Việt) cho tiêu đề và nhãn nhỏ, đóng gói sẵn qua `@fontsource` nên chạy được offline

## Chạy thử

```bash
cd dashboard
npm install
npm run dev          # mở http://localhost:5173
```

Không cần backend: khi chưa đặt `VITE_WS_URL`, dashboard dùng **server giả lập** trong `src/mock/`
với 7 agent (Leader Nghèo, Senior Coder, Junior Coder, Intern Coder, Reviewer, Designer, Tester)
và các task TD-36 … TD-45. Server giả lập liên tục sinh sự kiện: agent xong việc (pháo giấy),
bị chặn hoặc lỗi (dấu ! đỏ), Leader gọi agent lên bàn họp để giao việc rồi agent đi về bàn.
Ô “Giao việc” ở dưới cũng chạy được với mock.

Các lệnh khác:

```bash
npm run typecheck    # kiểm tra kiểu
npm run build        # build ra dist/
npm run preview      # xem bản build
```

## Nối WebSocket thật

1. Tạo file `.env.local` trong `dashboard/`:

   ```bash
   VITE_WS_URL=ws://localhost:8000/ws/events
   ```

2. Chạy lại `npm run dev`. Góc phải header sẽ hết chữ “mock”, trạng thái kết nối lấy từ socket thật.
   Mất kết nối thì dashboard tự kết nối lại (chờ tăng dần tới 15 giây).

Không cần sửa code nào khác: `src/hooks/useOffice.ts` tự chọn mock hay WebSocket theo biến này.

### Hợp đồng WebSocket

Kiểu đầy đủ nằm trong [`src/types.ts`](src/types.ts). Server gửi JSON:

| Tin nhắn | Khi nào | Nội dung |
|---|---|---|
| `{type:"snapshot", company?, agents, tasks, log}` | ngay khi kết nối | toàn bộ trạng thái hiện tại |
| `{type:"agent", agent}` | agent đổi trạng thái | `agent` có `id` và các trường thay đổi (gộp vào bản cũ) |
| `{type:"task", task}` | task tạo mới / đổi trạng thái | task đầy đủ (thay bản cũ) |
| `{type:"log", entry}` | có sự kiện mới | `{id, ts, agentId, taskId?, kind, text}` |

Dashboard gửi lên: `{type:"assign", to: "<agent id>", text: "<nội dung>"}` khi sếp bấm Giao việc.

Các trường chính:

- `Agent.status`: `idle` | `working` | `blocked` → chấm xanh / cam / đỏ
- `Agent.activity`: `typing` | `reading` | `thinking` | `reviewing` | `testing` | `drawing` | `meeting` | `idle` → biểu tượng trong bong bóng
- `Agent.location`: `desk` | `meeting` → nhân vật đi bộ về bàn hoặc ra bàn họp Ban lãnh đạo
- `Agent.group`: `lead` | `code` | `creative` → phòng và nhóm ở cột trái
- `Agent.bubble` (tuỳ chọn): ghi đè chữ trong bong bóng, mặc định là `"<taskId> <đang làm gì>"`, ví dụ “TD-43 đang kiểm thử”
- `Agent.metrics` (tuỳ chọn): `{tasksDone, firstPassRate, avgSeconds, costUsd}`, hiện ở tab Chi tiết
- `Task.status`: `todo` | `doing` | `review` | `blocked` | `error` | `done` → 6 ô thống kê trên header
- `LogEntry.kind`: `start` | `done` | `error` | `blocked` | `review` | `assign` | `info` → màu dòng nhật ký

Hiệu ứng tự suy ra từ dữ liệu, server không cần gửi lệnh riêng:
task chuyển sang `done` thì nổ pháo giấy quanh người nhận; agent `blocked` thì có dấu ! đỏ trên đầu
và màn hình đỏ; đổi `location` thì nhân vật đi bộ theo lối đi chung, không nhảy.

`src/hooks/normalize.ts` cũng chấp nhận dạng snake_case (`task_id`, `task_text`, `agent_id`,
`at`, `level`) và agent `status: "error"` (hiển thị như bị chặn), để backend gửi dữ liệu thô vẫn chạy.

## Cấu trúc

```
src/
  types.ts            hợp đồng dữ liệu + nhãn tiếng Việt
  App.tsx             bố cục 3 cột + header + thanh giao việc, thu gọn cột, ngăn kéo trên màn hình hẹp
  components/         Header (thống kê, chuyển chế độ, theme, kết nối), PixelAvatar, Icons
  scene3d/            Three.js: Office3D (cảnh, camera, robot đi lại, nhãn, pháo giấy), robot (robot dựng từ khối),
                      props3d (sàn, khu, vách kính, thành phố, bàn, đồ đạc), screens3d (màn hình chạy mã),
                      layout3d (mặt bằng, bàn, đường đi), palette3d (màu theo theme)
  scene/              PixiJS: OfficeRenderer (cảnh), Character (nhân vật, đi bộ, bong bóng),
                      furniture (sàn, tường, đồ đạc), screens (màn hình chạy mã), effects (pháo giấy),
                      layout (vị trí phòng, bàn, đường đi), sprites (nhân vật pixel), palette (màu theo theme)
  panels/             TeamPanel (Đội ngũ), RightPanel (Nhật ký/Chi tiết), LogPanel, DetailPanel,
                      AssignBar (Giao việc), TaskBoard (chế độ Bảng việc)
  hooks/              useOffice (trạng thái + WebSocket/mock), normalize, useAutoScroll, useMediaQuery
  mock/               dữ liệu mẫu và server giả lập
  styles/             theme.css (token màu 4 theme), app.css
```

## Thêm agent hoặc đổi ngoại hình

- Agent mới chỉ cần có trong `snapshot`; dashboard tự xếp vào bàn trống của nhóm
  (Xưởng code 4 bàn, Studio 2 bàn, Ban lãnh đạo 1 ghế), hết bàn thì đứng ở góc nghỉ (3D) hoặc chỗ dự phòng (pixel).
  Thêm bàn: sửa `DESKS` trong `src/scene3d/layout3d.ts` và `SEATS` trong `src/scene/layout.ts`.
- Ngoại hình theo `id` nằm trong `LOOKS` ở `src/scene/sprites.ts` (dùng chung cho nhân vật pixel và màu robot 3D);
  id lạ được sinh ngoại hình ổn định từ id.
- Theme: thêm bảng màu trong `src/scene/palette.ts`, `src/scene3d/palette3d.ts` và một khối `:root[data-theme=...]`
  trong `src/styles/theme.css`.

Tab **Chi tiết** của một task hiện luồng công việc Tiếp nhận → Lên kế hoạch → Thực hiện → Kiểm thử → Review → Hoàn thành,
suy ra từ `Task.status` (và `activity: "testing"` của người nhận để biết đang ở bước Kiểm thử).
