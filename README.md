# Virtual Tech Dept

Phòng công nghệ ảo chạy bằng AI. Sếp nhắn yêu cầu của khách, các agent tự tiếp nhận, viết spec, code, kiểm thử và gửi báo cáo kèm bản demo để sếp duyệt.

**Trạng thái: Giai đoạn 6** — ngoài landing page, đội làm được web bán hàng có giỏ hàng và đặt hàng. Giao hàng có
kiểm soát: staging, deploy production, email cho khách, đẩy code lên GitHub của khách, duyệt chi thêm ngân sách.
Luồng làm việc:

```
Sếp nhắn → Lễ tân (brief) → BA/Architect (spec) → Đề xuất 3 phương án
        ⏸ Sếp chọn A/B/C, hoặc gửi góp ý để làm lại phương án
        → Architect chốt spec + API contract
        → UI/UX Designer  ┐ song song (không phụ thuộc nhau)
        → Backend Dev     ┘
        → Frontend Dev (theo design spec + API contract)
        → QA            ┐ song song (cả hai chỉ đọc)
        → Reviewer      ┘
        → lỗi được trả đúng dev phụ trách file, tối đa VTD_MAX_FIX_ROUNDS vòng
        → Báo cáo viên → tự deploy staging ⏸ Sếp duyệt bàn giao
        → ⏸ Deploy production   ⏸ Gửi email cho khách   ⏸ Đẩy code lên GitHub của khách
Chạm trần ngân sách ở bất kỳ bước nào ⏸ Sếp duyệt chi thêm (làm tiếp từ bước đó) hoặc dừng dự án
```

**Ba phương án:** A Nhanh & rẻ (3 mục), B Cân bằng (theo spec, SEO, menu dính), C Cao cấp (thư viện ảnh, hỏi đáp,
form liên hệ có backend, giao diện tối, hiệu ứng). Mỗi phương án có số ngày, giá báo khách, ưu nhược điểm.

**Phân vai và quyền ghi** (bị chặn ở tầng code, không chỉ trong prompt):

| Vai | Được ghi | Ghi chú |
|---|---|---|
| UI/UX Designer | `design/` | Màu bị ép đạt tương phản WCAG AA |
| Frontend Dev | `*.html`, `*.css`, ảnh ở thư mục gốc | Không đụng `api/`, `design/` |
| Backend Dev | `api/` (trừ `api/data/`) | Chỉ thư viện chuẩn Python |
| QA, Reviewer, Báo cáo viên | không | Chỉ đọc |

**QA** kiểm tra HTML (cấu trúc, liên kết, CTA, từng tính năng đã chọn, form khớp API contract), rồi với dự án có
backend thì chạy test của Backend Dev (`python -m unittest`) và khởi động server thật để thử API: dữ liệu hợp lệ,
thiếu trường, không lộ mã nguồn. Code do agent viết chạy trong tiến trình riêng, có timeout và không thấy biến môi
trường bí mật. Khi dùng cho khách thật nên chạy trong container (`infra/`).

**Reviewer** dò khóa bí mật trong code, eval/exec/shell, SQL ghép chuỗi, trả lỗi lộ stack trace, thiếu giới hạn đầu
vào, `javascript:` và sự kiện nội tuyến trong HTML; khi có model thật thì model review thêm. Lỗi mức blocker/major
quay lại dev phụ trách; gợi ý minor vào báo cáo.

**Bộ nhớ khách hàng (giai đoạn 4).** Mỗi dự án gắn với một khách (ô "Khách hàng" khi giao việc, hoặc tên
trong ngoặc kép như `'Mộc Coffee'`). Hệ thống tự ghi nhớ các quyết định của sếp: phương án đã chọn, góp ý làm lại,
duyệt hoặc yêu cầu sửa, cùng ghi chú tay ở trang Khách hàng. Dự án sau của cùng khách:
- Lễ tân không hỏi lại điều đã biết (ví dụ lấy ngân sách lần trước) và ghi các lưu ý đã chốt vào giả định.
- Kiến trúc sư ưu tiên phương án khách hay chọn nếu vẫn vừa ngân sách, và nêu lý do.
- Báo cáo viên biết đây là dự án thứ mấy của khách.

**Bảng điểm đội ngũ** (`GET /api/agents/scorecard`, tab Đội ngũ): việc xong, bị chặn, thời gian trung bình,
tỷ lệ đạt ngay lần đầu và số vòng sửa của từng dev, chi phí model theo agent, số ghi chú của Reviewer, số kiểm
tra của QA, tỷ lệ sếp duyệt. Số liệu này cũng gửi qua WebSocket trong trường `metrics` của từng agent.

**Giao khách.** Sau khi sếp duyệt, `GET /api/projects/{id}/export` tải gói zip của dự án, kèm lịch sử git
riêng để đẩy lên GitHub của khách. Dữ liệu khách để lại qua form (`api/data/`) không bao giờ nằm trong gói
và không xem được qua trang demo.

**Giao hàng (giai đoạn 5).** Mọi bước ra bên ngoài đều cần sếp bấm và xác nhận; agent không có quyền deploy hay gửi.
- *Staging*: build xong tự đăng bản chụp của commit vừa qua QA ở `/staging/<id>/`. Đây là link nội bộ để sếp xem.
- *Production*: sau khi sếp duyệt, nút "Deploy production" đăng đúng commit sếp đã xem trên staging lên
  `/live/<id>/`, kể cả khi repo dự án có commit mới hơn. Bản cũ được thay một lần, không có lúc trang trống.
- Chỉ trang tĩnh được đăng: `api/`, `design/`, `.git` và dữ liệu khách không có trên staging hay production. Form
  liên hệ trên trang đã đăng vẫn chạy: dữ liệu được kiểm theo API contract và lưu ngoài thư mục được phục vụ.
- *Email cho khách*: duyệt xong, Báo cáo viên soạn email bàn giao (không có chi phí, QA, Reviewer hay chi tiết
  nội bộ), lấy địa chỉ email từ thông tin liên hệ của khách. Sếp sửa, lưu, rồi bấm gửi. Có SMTP thì gửi thật;
  chưa cấu hình thì lưu file `.eml` vào `workspace/outbox/` và giao diện ghi rõ là chưa gửi.
- *GitHub của khách*: nhập `chủ-repo/tên-repo` và nhánh, hệ thống đẩy commit đã duyệt (không force-push).
  Token lấy từ `VTD_GITHUB_TOKEN`, truyền qua biến môi trường của git, không nằm trong URL, lệnh hay nhật ký.
- *Ngân sách*: dùng 80% trần thì nhật ký cảnh báo. Chạm trần thì dự án dừng ở trạng thái "Chạm trần ngân sách";
  sếp nhập số USD cấp thêm để làm tiếp từ bước đang dừng (bước đã xong không chạy lại) hoặc dừng hẳn dự án.
- Các quyết định này (chi thêm, dừng, deploy, gửi, giao code) được ghi vào bộ nhớ khách hàng.

**Web bán hàng (giai đoạn 6).** Lễ tân nhận ra yêu cầu bán hàng (giỏ hàng, đặt hàng, thanh toán...) và đánh dấu
dự án là `shop`. BA viết danh mục sản phẩm (tạm, nếu khách chưa gửi). Kiến trúc sư đưa 3 phương án: Shop cơ bản
(giỏ hàng, COD, trang quản lý đơn), Shop chuẩn (thêm chuyển khoản theo mã đơn, tra cứu đơn, tồn kho, SEO), Shop
cao cấp (thêm hỏi đáp, giao diện tối, hiệu ứng). Sản phẩm gồm `index.html` (danh mục), `checkout.html`,
`order.html`, `admin.html`, `cart.js` dùng chung và backend Python `api/server.py` + `api/products.json`.
- Tổng tiền luôn tính lại ở server theo danh mục; giá sửa trong trình duyệt không có tác dụng.
- Tra cứu đơn cần đúng cả mã đơn và số điện thoại, không trả địa chỉ. Trang quản lý cần mã truy cập
  (`SHOP_ADMIN_TOKEN`), mỗi dự án một mã riêng nằm trên máy chủ, không nằm trong repo; sếp xem mã ở mục Giao hàng.
- QA thử như một người mua cố tình phá: gửi giá giả, sản phẩm không tồn tại, số lượng 0 hoặc âm, đặt quá tồn
  kho, tra cứu sai số điện thoại, vào trang quản lý không có mã. Reviewer dò thêm `innerHTML`, `eval`,
  `document.write` và lưu mã truy cập trong `localStorage` ở file `.js`.
- Trên staging/production, các lời gọi `api/...` chạy bằng chính backend của commit đã deploy (tiến trình riêng,
  cổng nội bộ, không thấy biến môi trường bí mật), dữ liệu lưu ngoài thư mục được phục vụ. Staging và production
  có đơn riêng. Sếp xem đơn production ngay trong mục Giao hàng.
- Chưa có cổng thanh toán online (VNPay, MoMo): cần tài khoản doanh nghiệp của khách, được ghi rõ trong mỗi
  phương án và trong báo cáo.

**Dashboard văn phòng pixel** (`dashboard/`, làm riêng) đọc luồng sự kiện realtime ở `ws://<host>/ws/events`
theo hợp đồng trong `dashboard/src/types.ts`: `snapshot`, `agent`, `task`, `log`; gửi `{type: "assign", to, text}`
để giao việc (tạo dự án mới). Server ở `backend/office.py`.

## Chạy thử

```bash
pip install -r requirements.txt
cp .env.example .env          # điền ANTHROPIC_API_KEY để dùng model thật
./infra/dev.sh                # mở http://localhost:8000
```

Không có khóa API thì hệ thống chạy ở chế độ **mock**: các agent dùng logic mẫu offline, đủ để chạy hết luồng, xem giao diện và chạy test mà không tốn tiền.

Chạy từ terminal, không cần giao diện:

```bash
python -m ai.cli "Làm landing page cho quán cà phê 'Mộc Coffee' ở Đà Lạt, ngân sách 5 triệu"
# thêm --choose B (hoặc recommended) để không phải gõ khi được hỏi
```

Docker: `docker compose -f infra/docker-compose.yml up --build`

Test: `python -m pytest -q`

## Cấu trúc

| Thư mục | Nội dung |
|---|---|
| `frontend/` | Giao diện cho sếp: giao việc, task board theo agent, brief, spec, kết quả QA, báo cáo, xem demo, nút duyệt |
| `backend/` | FastAPI + SQLite: dự án, task board, artifact, nhật ký, chi phí, các điểm duyệt, `delivery.py` (staging/production, email, GitHub), WebSocket `/ws/events` cho dashboard |
| `ai/` | `agents.py` (các agent), `prompts/` (prompt từng vai), `artifacts.py` (schema giao tiếp), `team.py` (Designer, Backend Dev, QA chạy test, Reviewer), `templates/` (mẫu backend offline), `orchestrator.py` (luồng điều phối), `llm.py` (gọi model + trần ngân sách), `workspace.py` (quyền theo vai) |
| `workspace/` | Mỗi dự án là một git repo riêng trong `workspace/projects/<id>/` |
| `infra/` | Dockerfile, docker-compose, script chạy dev |

## Nguyên tắc đã áp dụng

- **Giao tiếp bằng artifact có cấu trúc.** Mỗi agent nhận và trả về một model Pydantic (`Brief`, `Spec`, `CodeArtifact`, `QAReport`, `FinalReport`). Với model thật, output được ép đúng schema bằng structured outputs.
- **Quyền tối thiểu.** Mỗi dev chỉ ghi được thư mục của mình; QA, Reviewer và Báo cáo viên chỉ đọc. Không agent nào deploy hay gửi gì ra ngoài (`backend/delivery.py` chỉ chạy từ nút của sếp). Đường dẫn bị khóa trong thư mục dự án.
- **QA chạy kiểm tra thật** trên file: DOCTYPE, lang, meta, title, đủ section theo spec, đúng một h1, ảnh có alt, liên kết nội bộ, không tài nguyên ngoài, tài nguyên nội bộ tồn tại, nút CTA, dung lượng.
- **Lỗi trả về dev, không đẩy cho sếp.** Quá `VTD_MAX_FIX_ROUNDS` vòng thì dự án chuyển sang "Cần sếp xử lý".
- **Trần ngân sách mỗi dự án.** Theo dõi token và chi phí theo từng agent; chạm trần thì dừng, chờ sếp duyệt chi thêm.
- **Điểm dừng cho con người.** Chọn phương án, chi thêm tiền, duyệt bàn giao, deploy production, gửi khách, đẩy code: mỗi bước cần sếp bấm.
- **Khóa API chỉ nằm trong biến môi trường.**

## Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `ANTHROPIC_API_KEY` | | Khóa API |
| `VTD_LLM` | `auto` | `auto`, `mock` hoặc `anthropic` |
| `VTD_MODEL` | `claude-opus-5-5` | Model dùng cho các agent |
| `VTD_EFFORT` | `medium` | Mức suy nghĩ của model |
| `VTD_DEFAULT_BUDGET_USD` | `2.0` | Trần chi phí mặc định mỗi dự án |
| `VTD_MAX_FIX_ROUNDS` | `2` | Số vòng sửa lỗi tự động tối đa |
| `VTD_MAX_REVISIONS` | `3` | Số lần sếp được yêu cầu làm lại phương án |
| `VTD_TEST_TIMEOUT` | `60` | Giới hạn giây khi QA chạy test backend |
| `VTD_COMPANY` | `AtusCompany` | Tên công ty hiện trên dashboard |
| `VTD_PUBLIC_URL` | `http://localhost:8000` | Địa chỉ công khai của máy chủ, dùng cho link staging/production |
| `VTD_DEPLOYS` | `workspace/deploys` | Nơi lưu bản staging, production và dữ liệu form của trang đã đăng |
| `VTD_GITHUB_TOKEN` | | Token GitHub (quyền ghi repo của khách) để đẩy code |
| `VTD_SMTP_HOST`, `VTD_SMTP_PORT`, `VTD_SMTP_USER`, `VTD_SMTP_PASSWORD`, `VTD_SMTP_FROM` | | Máy chủ gửi email cho khách; bỏ trống thì email nằm trong hộp thư đi |
| `VTD_OUTBOX` | `workspace/outbox` | Hộp thư đi khi chưa có SMTP |

## Lộ trình

- [x] Giai đoạn 1: nhắn → spec → code → test → báo cáo cho landing page tĩnh
- [x] Giai đoạn 2: tạo 2–3 phương án (nhanh/rẻ, cân bằng, cao cấp) và cơ chế chọn
- [x] Giai đoạn 3: tách frontend/backend, thêm QA chạy test thật, Reviewer bảo mật, UI/UX Designer, WebSocket cho dashboard
- [x] Giai đoạn 4: bộ nhớ khách hàng và quyết định đã chốt, bảng điểm từng agent, gói giao khách
- [x] Giai đoạn 5: staging, deploy production, email bàn giao, đẩy code lên GitHub của khách, duyệt chi thêm ngân sách
- [x] Giai đoạn 6: web bán hàng: danh mục, giỏ hàng, đặt hàng COD/chuyển khoản, tra cứu đơn, quản lý đơn, tồn kho
- [ ] Tiếp theo: chạy thử với model thật và chỉnh prompt, cổng thanh toán online (cần tài khoản của khách), hosting ngoài (VPS)
