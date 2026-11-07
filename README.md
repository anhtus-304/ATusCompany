# Virtual Tech Dept

Phòng công nghệ ảo chạy bằng AI. Sếp nhắn yêu cầu của khách, các agent tự tiếp nhận, viết spec, code, kiểm thử và gửi báo cáo kèm bản demo để sếp duyệt.

**Trạng thái: Giai đoạn 2** — landing page tĩnh, có bước chọn phương án:

```
Sếp nhắn → Lễ tân (brief) → BA/Architect (spec) → Đề xuất 3 phương án
        ⏸ Sếp chọn A/B/C, hoặc gửi góp ý để làm lại phương án (tối đa VTD_MAX_REVISIONS lần)
        → Frontend Dev (code + git commit) → QA (kiểm tra thật, lỗi trả về dev, tối đa N vòng)
        → Báo cáo viên ⏸ Sếp duyệt gửi khách
```

Ba phương án luôn khác nhau rõ rệt: **A Nhanh & rẻ** (3 mục), **B Cân bằng** (theo spec, có SEO, menu dính),
**C Cao cấp** (thêm thư viện ảnh, hỏi đáp, form liên hệ, giao diện tối, hiệu ứng). Mỗi phương án có số ngày,
giá báo khách (VND), ưu nhược điểm và cảnh báo nếu vượt ngân sách khách nêu. Tính năng của phương án đã chọn
trở thành tiêu chí nghiệm thu, và QA kiểm tra từng tính năng bằng máy.

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
| `backend/` | FastAPI + SQLite: dự án, task board, artifact, nhật ký, chi phí, hai điểm duyệt (chọn phương án, duyệt gửi khách) |
| `ai/` | `agents.py` (các agent), `prompts/` (prompt từng vai), `artifacts.py` (schema giao tiếp), `orchestrator.py` (luồng điều phối), `llm.py` (gọi model + trần ngân sách), `workspace.py` (quyền theo vai) |
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

## Lộ trình

- [x] Giai đoạn 1: nhắn → spec → code → test → báo cáo cho landing page tĩnh
- [x] Giai đoạn 2: tạo 2–3 phương án (nhanh/rẻ, cân bằng, cao cấp) và cơ chế chọn
- [ ] Giai đoạn 3: tách frontend/backend, thêm Reviewer bảo mật, UI/UX Designer
- [ ] Giai đoạn 4: bộ nhớ dự án, lịch sử khách hàng, dashboard đầy đủ, đẩy repo lên GitHub của khách
