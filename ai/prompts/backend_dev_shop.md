Dự án này là web bán hàng. Viết thêm `api/products.json` (danh mục được đưa kèm, giữ nguyên `id`, `price_vnd`, `stock`) và theo đúng contract:

- `GET /api/products` trả `{"products": [...], "payments": [...]}`; nếu có quản lý tồn kho thì mỗi sản phẩm có `in_stock` còn lại.
- `POST /api/orders` nhận JSON `name, phone, address, note, payment, items: [{id, qty}]`. Kiểm từng trường, `payment` trong danh sách cho phép, `id` có trong danh mục, `qty` là số nguyên 1-99, tối đa 30 dòng. **Tổng tiền tính lại từ danh mục**, bỏ qua mọi giá gửi lên. Có tồn kho thì đặt quá trả 409. Trả 201 với `code` dạng `DH` + 6 ký tự, `status`, `payment`, `total_vnd`, `items`. Mã đơn sinh bằng `secrets`.
- `POST /api/orders/lookup` (nếu có): cần đúng cả `code` và `phone`, sai một trong hai trả 404 giống nhau; không trả địa chỉ hay tên.
- `GET /api/admin/orders`, `POST /api/admin/orders/status` (nếu có): header `Authorization: Bearer <SHOP_ADMIN_TOKEN>` lấy từ biến môi trường, so sánh bằng `hmac.compare_digest`; sai hoặc thiếu trả 401, chưa cấu hình token trả 503.
- Lưu đơn trong thư mục `--data` (file JSON, ghi qua file tạm rồi đổi tên, có khóa luồng). Không phục vụ `api/`, `design/`, `.git` qua HTTP.
- `api/test_server.py` kiểm tra các trường hợp trên, trong đó có trường hợp gửi giá giả.
