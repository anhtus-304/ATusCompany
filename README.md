# Virtual Tech Dept

Phòng công nghệ ảo chạy bằng AI. Sếp nhắn yêu cầu của khách, các agent tự tiếp nhận, viết spec, code, kiểm thử và gửi báo cáo kèm bản demo để sếp duyệt.

**Trạng thái: Giai đoạn 4** — có bộ nhớ khách hàng, quyết định đã chốt và bảng điểm từng agent. Luồng làm việc:

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
        → Báo cáo viên ⏸ Sếp duyệt gửi khách
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
| `backend/` | FastAPI + SQLite: dự án, task board, artifact, nhật ký, chi phí, hai điểm duyệt (chọn phương án, duyệt gửi khách), WebSocket `/ws/events` cho dashboard |
| `ai/` | `agents.py` (các agent), `prompts/` (prompt từng vai), `artifacts.py` (schema giao tiếp), `team.py` (Designer, Backend Dev, QA chạy test, Reviewer), `templates/` (mẫu backend offline), `orchestrator.py` (luồng điều phối), `llm.py` (gọi model + trần ngân sách), `workspace.py` (quyền theo vai) |
| `workspace/` | Mỗi dự án là một git repo riêng trong `workspace/projects/<id>/` |
| `infra/` | Dockerfile, docker-compose, script chạy dev |

## Nguyên tắc đã áp dụng

- **Giao tiếp bằng artifact có cấu trúc.** Mỗi agent nhận và trả về một model Pydantic (`Brief`, `Spec`, `CodeArtifact`, `QAReport`, `FinalReport`). Với model thật, output được ép đúng schema bằng structured outputs.
- **Quyền tối thiểu.** Chỉ vai `frontend_dev` được ghi file; QA và Báo cáo viên chỉ đọc. Không agent nào deploy. Đường dẫn bị khóa trong thư mục dự án.
- **QA chạy kiểm tra thật** trên file: DOCTYPE, lang, meta, title, đủ section theo spec, đúng một h1, ảnh có alt, liên kết nội bộ, không tài nguyên ngoài, tài nguyên nội bộ tồn tại, nút CTA, dung lượng.
- **Lỗi trả về dev, không đẩy cho sếp.** Quá `VTD_MAX_FIX_ROUNDS` vòng thì dự án chuyển sang "Cần sếp xử lý".
- **Trần ngân sách mỗi dự án.** Theo dõi token và chi phí theo từng agent; chạm trần thì dừng và báo.
- **Điểm dừng cho con người.** Kết thúc luôn ở trạng thái "Chờ sếp duyệt" trước khi gửi khách hay deploy.
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

## Lộ trình

- [x] Giai đoạn 1: nhắn → spec → code → test → báo cáo cho landing page tĩnh
- [x] Giai đoạn 2: tạo 2–3 phương án (nhanh/rẻ, cân bằng, cao cấp) và cơ chế chọn
- [x] Giai đoạn 3: tách frontend/backend, thêm QA chạy test thật, Reviewer bảo mật, UI/UX Designer, WebSocket cho dashboard
- [x] Giai đoạn 4: bộ nhớ khách hàng và quyết định đã chốt, bảng điểm từng agent, gói giao khách
- [ ] Tiếp theo: chạy thử với model thật và chỉnh prompt, đẩy thẳng lên GitHub của khách (cần token), dashboard pixel (luồng riêng)
