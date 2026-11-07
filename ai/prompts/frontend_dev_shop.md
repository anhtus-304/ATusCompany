Dự án này là web bán hàng (`kind` = `shop`). Ngoài các quy tắc trên, viết thêm và chỉ dùng JavaScript thuần, không thư viện ngoài:

- `index.html`: mục `#products` liệt kê mọi sản phẩm trong `products`, mỗi sản phẩm là phần tử có `data-id` đúng `id`, hiện tên, giá VND và `<button type="button" class="add" data-id="...">`. Header có liên kết `checkout.html` kèm số lượng trong giỏ (`#cart-count`). Nút CTA trỏ tới `#products`.
- `checkout.html`: giỏ hàng (sửa số lượng, xóa), tạm tính, form `#checkout` có các ô đúng tên trong contract `/api/orders` (name, phone, address, note) với `required`/`maxlength`, radio `payment` đúng các giá trị `choices`. Gửi JSON tới `api/orders` (đường dẫn tương đối) gồm `items: [{id, qty}]`; không gửi giá. Thành công thì chuyển tới `order.html?code=...`.
- `order.html`: hiện đơn vừa đặt; nếu có `bank_transfer` hiện thông tin chuyển khoản giữ chỗ và nội dung chuyển khoản là mã đơn; nếu có `order_lookup` có form tra cứu gửi tới `api/orders/lookup`.
- `admin.html` nếu có `admin_orders`: nhập mã truy cập, gọi `api/admin/orders` với header `Authorization: Bearer <mã>`, đổi trạng thái qua `api/admin/orders/status`. Mã chỉ lưu trong `sessionStorage`. Có `<meta name="robots" content="noindex">`.
- `cart.js` dùng chung cho mọi trang, giỏ hàng lưu trong `localStorage`. Mọi trang nạp `styles.css` và `cart.js`, có DOCTYPE, lang, viewport, title, đúng một h1.
- Bảo mật: không dùng `innerHTML`/`document.write`/`eval` với dữ liệu; tạo phần tử bằng `createElement` và `textContent`. Không dùng thuộc tính sự kiện nội tuyến (`onclick`...).
