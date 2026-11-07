"""Phase 6: online shops (catalog, cart, checkout, orders).

Everything specific to `kind == "shop"` lives here so the landing-page flow stays as it was:
detection and a placeholder catalog for Intake/Analyst, the three shop options, the API
contract, the offline templates for Frontend and Backend Dev, and the QA checks.

Payment: cash on delivery and bank transfer (the order code is the transfer reference). Online
gateways (VNPay, MoMo...) need the client's merchant account, so they are listed as a risk
for the boss, not built.
"""
from __future__ import annotations

import html
import json
import pprint
import re
import urllib.error
import urllib.request
from pathlib import Path

from .artifacts import ApiEndpoint, ApiField, FileOut, Option, Product, Section, Spec

TEMPLATES = Path(__file__).parent / "templates"
SHOP_RE = re.compile(r"giỏ hàng|bán hàng|bán online|đặt hàng|thanh toán|web bán|cửa hàng online|shop online|"
                     r"e-?commerce|online shop|\bcart\b|checkout", re.I)
PAYMENT_LABELS = {"cod": "Thanh toán khi nhận hàng (COD)", "bank_transfer": "Chuyển khoản ngân hàng"}
STATUS_LABELS = {"new": "Mới", "confirmed": "Đã xác nhận", "paid": "Đã thanh toán", "shipping": "Đang giao",
                 "done": "Hoàn tất", "cancelled": "Đã hủy"}
GATEWAY_RISK = ("Chưa có cổng thanh toán online (VNPay, MoMo): cần tài khoản doanh nghiệp của khách, "
                "làm sau khi khách đăng ký")


def is_shop(message: str) -> bool:
    return bool(SHOP_RE.search(message))


# --------------------------------------------------------------------------- catalog

_CATALOGS = [
    (r"cà phê|cafe|coffee", [
        ("Cà phê Arabica rang xay 250g", 145_000), ("Cà phê Robusta rang mộc 250g", 95_000),
        ("Cà phê phin giấy (hộp 10 gói)", 85_000), ("Cold brew đóng chai 1L", 150_000),
        ("Bộ phin nhôm và ly sứ", 120_000), ("Hộp quà cà phê đặc sản", 390_000)]),
    (r"bánh|bakery", [
        ("Bánh mì bơ tỏi", 35_000), ("Bánh bông lan trứng muối", 65_000), ("Bánh su kem (hộp 6)", 60_000),
        ("Bánh kem sinh nhật 16cm", 280_000), ("Cookie bơ (hộp 250g)", 90_000), ("Bánh croissant", 30_000)]),
    (r"thời trang|quần áo|fashion", [
        ("Áo thun cotton", 189_000), ("Áo sơ mi linen", 359_000), ("Quần jean ống suông", 459_000),
        ("Váy midi hoa nhí", 429_000), ("Túi tote canvas", 149_000), ("Mũ bucket", 129_000)]),
    (r"mỹ phẩm|skincare|làm đẹp", [
        ("Sữa rửa mặt dịu nhẹ", 189_000), ("Toner hoa cúc", 229_000), ("Serum vitamin C", 389_000),
        ("Kem dưỡng ẩm ban đêm", 349_000), ("Kem chống nắng SPF50", 299_000), ("Mặt nạ đất sét", 199_000)]),
]


def sample_catalog(business_type: str, message: str = "") -> list[Product]:
    """Placeholder catalog until the client sends the real one. Prices are marked as temporary in the brief."""
    text = f"{business_type} {message}".lower()
    items = next((c for rx, c in _CATALOGS if re.search(rx, text)), None) or [
        (f"Sản phẩm {i}", p) for i, p in enumerate((99_000, 149_000, 199_000, 249_000, 299_000, 399_000), 1)]
    from .agents import _slug
    return [Product(id=_slug(name)[:40], name=name, price_vnd=price, description="[Mô tả ngắn sản phẩm]", stock=20)
            for name, price in items]


def normalize_products(products: list[Product]) -> list[Product]:
    from .agents import _slug
    seen: set[str] = set()
    out = []
    for p in products[:60]:
        pid = _slug(p.id or p.name)[:40]
        while pid in seen:
            pid = (pid[:37] + "-2")
        seen.add(pid)
        out.append(p.model_copy(update={"id": pid, "price_vnd": max(0, int(p.price_vnd)), "stock": max(0, int(p.stock))}))
    return out


def sections(brief) -> list[Section]:
    n = brief.project_name
    return [
        Section(id="hero", heading=n, purpose="Giới thiệu cửa hàng và mời mua",
                content=[f"{n}: {brief.business_type.lower()}, đặt online giao tận nơi", "Ưu đãi nổi bật [..]"]),
        Section(id="products", heading="Sản phẩm", purpose="Danh mục để khách chọn và thêm vào giỏ",
                content=["Danh mục sản phẩm, giá và nút thêm vào giỏ"]),
        Section(id="features", heading="Vì sao mua ở đây", purpose="Lợi ích khi mua",
                content=["Hàng chính hãng, rõ nguồn gốc", "Giao nhanh trong ngày [khu vực]", "Đổi trả trong 7 ngày"]),
        Section(id="about", heading="Về chúng tôi", purpose="Tạo niềm tin", content=[f"Câu chuyện của {n}"]),
        Section(id="contact", heading="Liên hệ", purpose="Hỗ trợ trước và sau khi mua",
                content=["[Địa chỉ]", "[Số điện thoại / Zalo]", "[Giờ làm việc]"]),
    ]


# --------------------------------------------------------------------------- options

def options(spec: Spec, over) -> list[Option]:
    by_id = {s.id: s for s in spec.sections}
    hero, products, contact = by_id["hero"], by_id["products"], by_id["contact"]
    middle = [s for s in spec.sections if s.id not in ("hero", "products", "contact")]
    faq = Section(id="faq", heading="Câu hỏi thường gặp", purpose="Giải đáp trước khi đặt hàng",
                  content=["Phí giao hàng thế nào?", "Bao lâu thì nhận được hàng?", "Đổi trả ra sao?"])
    a, b, c = 8_000_000, 15_000_000, 28_000_000
    return [
        Option(id="A", tier="fast", name="Shop cơ bản",
               summary="Danh mục, giỏ hàng, đặt hàng trả tiền khi nhận, chủ shop xem đơn ở trang quản lý.",
               sections=[hero, products, contact], features=["responsive", "cart", "cod", "admin_orders"],
               est_days=5, est_price_vnd=a,
               pros=["Bán được ngay với chi phí thấp", "Chủ shop xem và cập nhật đơn trên điện thoại"],
               cons=["Chỉ nhận COD", "Không tra cứu đơn, không quản lý tồn kho", GATEWAY_RISK] + over(a)),
        Option(id="B", tier="balanced", name="Shop chuẩn",
               summary="Thêm chuyển khoản theo mã đơn, khách tự tra cứu đơn, quản lý tồn kho, SEO và menu dính.",
               sections=[hero, products, *middle, contact],
               features=["responsive", "sticky_nav", "seo_meta", "cart", "cod", "bank_transfer", "order_lookup",
                         "admin_orders", "stock"],
               est_days=10, est_price_vnd=b,
               pros=["Nhận cả COD và chuyển khoản, đối soát bằng mã đơn", "Không bán quá số hàng còn trong kho"],
               cons=["Cần khách gửi danh mục, giá và tồn kho thật", GATEWAY_RISK] + over(b)),
        Option(id="C", tier="premium", name="Shop cao cấp",
               summary="Như Shop chuẩn, thêm hỏi đáp, giao diện tối và hiệu ứng.",
               sections=[hero, products, *middle, faq, contact],
               features=["responsive", "sticky_nav", "seo_meta", "dark_mode", "animations", "faq_accordion",
                         "cart", "cod", "bank_transfer", "order_lookup", "admin_orders", "stock"],
               est_days=18, est_price_vnd=c,
               pros=["Trải nghiệm mua sắm chuyên nghiệp", "Giảm câu hỏi lặp lại nhờ mục hỏi đáp"],
               cons=["Lâu và tốn kém hơn", "Cần ảnh sản phẩm chất lượng cao", GATEWAY_RISK] + over(c)),
    ]


def normalize_option(o: Option) -> None:
    """Every shop has a product list and a cart; a cart without a payment method can't take orders."""
    if not any(s.id == "products" for s in o.sections):
        o.sections.insert(1, Section(id="products", heading="Sản phẩm", purpose="Danh mục",
                                     content=["Danh mục sản phẩm"]))
    for must in ("cart",):
        if must not in o.features:
            o.features.append(must)
    if not {"cod", "bank_transfer"} & set(o.features):
        o.features.append("cod")


# --------------------------------------------------------------------------- contract

def payments(features: list[str]) -> list[str]:
    return [p for p in ("cod", "bank_transfer") if p in features] or ["cod"]


def endpoints(features: list[str]) -> list[ApiEndpoint]:
    eps = [
        ApiEndpoint(method="GET", path="/api/products", purpose="Danh mục, giá" + (" và tồn kho" if "stock" in features else ""),
                    success_status=200),
        ApiEndpoint(method="POST", path="/api/orders", purpose="Tạo đơn. Tổng tiền tính ở server theo danh mục, "
                    "không tin giá gửi từ trình duyệt. Trả mã đơn DHxxxxxx", fields=[
                        ApiField(name="name", type="string", required=True, max_length=100),
                        ApiField(name="phone", type="phone", required=True, max_length=20),
                        ApiField(name="address", type="text", required=True, max_length=300),
                        ApiField(name="note", type="text", required=False, max_length=500),
                        ApiField(name="payment", type="choice", required=True, max_length=20,
                                 choices=payments(features)),
                        ApiField(name="items", type="items", required=True, max_length=30)]),
    ]
    if "order_lookup" in features:
        eps.append(ApiEndpoint(method="POST", path="/api/orders/lookup", success_status=200,
                               purpose="Tra cứu đơn bằng mã đơn + số điện thoại; sai một trong hai đều trả 404",
                               fields=[ApiField(name="code", type="string", required=True, max_length=8),
                                       ApiField(name="phone", type="phone", required=True, max_length=20)]))
    if "admin_orders" in features:
        eps += [
            ApiEndpoint(method="GET", path="/api/admin/orders", success_status=200,
                        purpose="Danh sách đơn cho chủ shop. Header Authorization: Bearer $SHOP_ADMIN_TOKEN, sai trả 401"),
            ApiEndpoint(method="POST", path="/api/admin/orders/status", success_status=200,
                        purpose="Đổi trạng thái đơn, cùng token",
                        fields=[ApiField(name="code", type="string", required=True, max_length=8),
                                ApiField(name="status", type="choice", required=True, max_length=20,
                                         choices=list(STATUS_LABELS))]),
        ]
    return eps


def criteria(features: list[str]) -> list[str]:
    out = ["Có checkout.html và order.html, mọi trang dùng chung cart.js và styles.css",
           "Mỗi sản phẩm trong danh mục có thẻ data-id và nút thêm vào giỏ",
           "Tổng tiền tính ở server; giá sửa ở trình duyệt không có tác dụng",
           "Sản phẩm không tồn tại hoặc số lượng sai bị từ chối (400)"]
    if "stock" in features:
        out.append("Đặt quá tồn kho bị từ chối (409)")
    if "order_lookup" in features:
        out.append("Tra cứu đơn cần đúng cả mã đơn và số điện thoại")
    if "admin_orders" in features:
        out.append("Trang quản lý đơn chỉ hoạt động với mã truy cập đúng (401 nếu sai)")
    return out


# --------------------------------------------------------------------------- Backend Dev (offline template)

def flags(features: list[str]) -> dict:
    return {"payments": payments(features), "lookup": "order_lookup" in features,
            "admin": "admin_orders" in features, "stock": "stock" in features}


def backend_files(spec: Spec) -> list[FileOut]:
    server = (TEMPLATES / "api_shop_server.py.tmpl").read_text(encoding="utf-8").replace(
        "__FEATURES__", pprint.pformat(flags(spec.features), sort_dicts=False))
    tests = (TEMPLATES / "api_shop_test.py.tmpl").read_text(encoding="utf-8")
    catalog = json.dumps([p.model_dump() for p in spec.products], ensure_ascii=False, indent=2)
    return [FileOut(path="api/server.py", content=server), FileOut(path="api/test_server.py", content=tests),
            FileOut(path="api/products.json", content=catalog + "\n")]


# --------------------------------------------------------------------------- Frontend Dev (offline template)

def money(n: int) -> str:
    return f"{n:,}".replace(",", ".") + " ₫"


def products_section(spec: Spec, sec: Section, cls: str) -> str:
    e = html.escape
    cards = "".join(
        f'\n      <li class="product" data-id="{e(p.id)}">'
        f'<div class="ph" role="img" aria-label="Ảnh {e(p.name)}"></div>'
        f"<h3>{e(p.name)}</h3><p>{e(p.description)}</p>"
        f'<p class="price">{money(p.price_vnd)}</p>'
        f'<button type="button" class="add" data-id="{e(p.id)}">Thêm vào giỏ</button></li>'
        for p in spec.products)
    return (f'<section id="{sec.id}"{cls}>\n  <div class="wrap">\n    <h2>{e(sec.heading)}</h2>\n'
            f'    <ul class="products">{cards}\n    </ul>\n'
            f'    <p id="cart-msg" class="cart-msg" role="status" aria-live="polite"></p>\n  </div>\n</section>')


def header_extra() -> str:
    return '<a class="cart-link" href="checkout.html">Giỏ hàng (<span id="cart-count">0</span>)</a>'


def _page(spec: Spec, title: str, body: str, robots: bool = False) -> str:
    e = html.escape
    return f"""<!DOCTYPE html>
<html lang="{e(spec.language)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">{chr(10) + '<meta name="robots" content="noindex">' if robots else ''}
<title>{e(title)} | {e(spec.project_name)}</title>
<link rel="stylesheet" href="styles.css">
<script src="cart.js" defer></script>
</head>
<body>
<header class="top"><div class="wrap"><a class="brand" href="index.html">{e(spec.project_name)}</a><nav><a href="index.html#products">Sản phẩm</a>{header_extra()}</nav></div></header>
<main>
{body}
</main>
<footer><div class="wrap">© {e(spec.project_name)}</div></footer>
</body>
</html>
"""


def pages(spec: Spec) -> list[FileOut]:
    f = set(spec.features)
    pay = "".join(
        f'<label class="opt"><input type="radio" name="payment" value="{m}" required{" checked" if i == 0 else ""}> '
        f"{PAYMENT_LABELS[m]}</label>" for i, m in enumerate(payments(spec.features)))
    checkout = _page(spec, "Giỏ hàng", f"""<section id="cart"><div class="wrap">
  <h1>Giỏ hàng</h1>
  <div id="cart-items" aria-live="polite"><p class="muted">Đang tải giỏ hàng…</p></div>
  <p class="total">Tạm tính: <strong id="cart-total">0 ₫</strong></p>
  <form id="checkout" class="form">
    <label>Họ tên<input name="name" maxlength="100" required autocomplete="name"></label>
    <label>Số điện thoại<input name="phone" type="tel" maxlength="20" required autocomplete="tel"></label>
    <label>Địa chỉ nhận hàng<textarea name="address" rows="2" maxlength="300" required autocomplete="street-address"></textarea></label>
    <label>Ghi chú<textarea name="note" rows="2" maxlength="500"></textarea></label>
    <fieldset class="pay"><legend>Thanh toán</legend>{pay}</fieldset>
    <button type="submit">Đặt hàng</button>
    <p id="checkout-error" class="error" role="alert"></p>
  </form>
</div></section>""")
    bank = ("""
  <div id="bank" class="bank" hidden>
    <h2>Thông tin chuyển khoản</h2>
    <p>Ngân hàng: [Tên ngân hàng]<br>Số tài khoản: [Số tài khoản]<br>Chủ tài khoản: [Tên chủ tài khoản]</p>
    <p>Nội dung chuyển khoản: <strong id="bank-ref"></strong></p>
  </div>""" if "bank_transfer" in f else "")
    lookup = ("""
  <form id="lookup" class="form">
    <h2>Tra cứu đơn hàng</h2>
    <label>Mã đơn<input name="code" maxlength="8" required placeholder="DH…" autocapitalize="characters"></label>
    <label>Số điện thoại đặt hàng<input name="phone" type="tel" maxlength="20" required></label>
    <button type="submit">Tra cứu</button>
    <p id="lookup-error" class="error" role="alert"></p>
  </form>""" if "order_lookup" in f else "")
    order = _page(spec, "Đơn hàng", f"""<section id="order"><div class="wrap">
  <h1>Đơn hàng</h1>
  <div id="order-result" aria-live="polite"><p class="muted">{"Nhập mã đơn và số điện thoại để xem trạng thái." if lookup else "Cảm ơn bạn đã đặt hàng."}</p></div>{bank}{lookup}
</div></section>""")
    files = [FileOut(path="checkout.html", content=checkout), FileOut(path="order.html", content=order)]
    if "admin_orders" in f:
        files.append(FileOut(path="admin.html", content=_page(spec, "Quản lý đơn hàng", """<section id="admin"><div class="wrap">
  <h1>Quản lý đơn hàng</h1>
  <form id="admin-login" class="form">
    <label>Mã truy cập<input name="token" type="password" maxlength="200" required autocomplete="current-password"></label>
    <button type="submit">Xem đơn</button>
    <p id="admin-error" class="error" role="alert"></p>
  </form>
  <div id="admin-orders" class="table-wrap" aria-live="polite"></div>
</div></section>""", robots=True)))
    files.append(FileOut(path="cart.js", content=CART_JS.replace("__STATUS__", json.dumps(STATUS_LABELS, ensure_ascii=False))
                         .replace("__PAYMENTS__", json.dumps(PAYMENT_LABELS, ensure_ascii=False))))
    return files


CSS = """
.top .brand { color: var(--on-brand); font-weight: 700; text-decoration: none; }
.cart-link { font-weight: 700; }
.products { list-style: none; padding: 0; display: grid; gap: 16px; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); }
.product { background: var(--surface); border-radius: var(--radius); padding: 16px; display: flex; flex-direction: column; gap: 6px; }
.product h3 { margin: 4px 0 0; font-size: 1.05rem; }
.product p { margin: 0; }
.product .ph { aspect-ratio: 4 / 3; border-radius: var(--radius); background: linear-gradient(135deg, var(--accent), var(--brand)); opacity: .85; }
.price { font-weight: 700; font-size: 1.1rem; color: var(--ink); }
.add, .qty button, .line .rm { font: inherit; cursor: pointer; border-radius: var(--radius); }
.add { margin-top: auto; background: var(--accent); color: #fff; border: 0; padding: 10px 14px; font-weight: 600; }
.cart-msg { min-height: 1.5em; font-weight: 600; color: var(--accent); }
.line { display: grid; grid-template-columns: 1fr auto auto auto; gap: 12px; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--muted); }
.qty { display: inline-flex; align-items: center; gap: 6px; }
.qty button { width: 32px; height: 32px; border: 1px solid var(--muted); background: var(--card); color: var(--ink); }
.line .rm { border: 0; background: none; color: var(--muted); text-decoration: underline; }
.total { font-size: 1.2rem; }
.pay { border: 1px solid var(--muted); border-radius: var(--radius); display: grid; gap: 6px; }
.form .opt { font-weight: 400; display: flex; gap: 8px; align-items: center; }
.error { color: #b42318; font-weight: 600; min-height: 1.2em; }
.muted { color: var(--muted); }
.bank, .receipt { background: var(--card); border-radius: var(--radius); padding: 16px; margin: 16px 0; }
.table-wrap { overflow-x: auto; }
.orders { width: 100%; border-collapse: collapse; }
.orders th, .orders td { text-align: left; padding: 8px; border-bottom: 1px solid var(--muted); vertical-align: top; }
.orders td:nth-child(5) { white-space: nowrap; }
@media (max-width: 600px) { .line { grid-template-columns: 1fr auto; } }
"""


CART_JS = r"""/* Cart, checkout, order lookup and the order admin page. No libraries, no innerHTML with data. */
(function () {
  "use strict";
  var STATUS = __STATUS__;
  var PAYMENTS = __PAYMENTS__;
  var KEY = "cart:" + location.pathname.replace(/[^\/]*$/, "");
  var money = function (n) { return Number(n).toLocaleString("vi-VN") + " ₫"; };
  var $ = function (id) { return document.getElementById(id); };

  function load() {
    try { var c = JSON.parse(localStorage.getItem(KEY) || "{}"); return c && typeof c === "object" ? c : {}; }
    catch (e) { return {}; }
  }
  function save(c) {
    try { localStorage.setItem(KEY, JSON.stringify(c)); } catch (e) { /* private mode: cart lives for this page only */ }
    count(c);
  }
  function count(c) {
    var el = $("cart-count"); if (!el) return;
    c = c || load(); var n = 0; Object.keys(c).forEach(function (k) { n += c[k]; }); el.textContent = String(n);
  }
  function el(tag, text, cls) {
    var e = document.createElement(tag);
    if (text !== undefined && text !== null) e.textContent = String(text);
    if (cls) e.className = cls;
    return e;
  }
  function api(path, opts) {
    return fetch(path, opts).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) {
        if (!r.ok) { var err = new Error(d.message || (d.details && d.details.join("; ")) || ("Lỗi " + r.status)); err.status = r.status; throw err; }
        return d;
      });
    });
  }
  function post(path, data, token) {
    var h = { "Content-Type": "application/json" };
    if (token) h.Authorization = "Bearer " + token;
    return api(path, { method: "POST", headers: h, body: JSON.stringify(data) });
  }

  // Product list: add to cart.
  Array.prototype.forEach.call(document.querySelectorAll("button.add[data-id]"), function (b) {
    b.addEventListener("click", function () {
      var c = load(), id = b.getAttribute("data-id");
      c[id] = Math.min(99, (c[id] || 0) + 1); save(c);
      var m = $("cart-msg"); if (m) m.textContent = "Đã thêm vào giỏ: " + (b.parentNode.querySelector("h3") || {}).textContent;
    });
  });
  count();

  // Checkout: prices shown come from the server catalog; the server computes the real total again.
  var list = $("cart-items"), form = $("checkout");
  if (list && form) {
    var catalog = {};
    var render = function () {
      var c = load(), total = 0, ids = Object.keys(c).filter(function (id) { return catalog[id]; });
      list.textContent = "";
      if (!ids.length) { list.appendChild(el("p", "Giỏ hàng đang trống.", "muted")); }
      ids.forEach(function (id) {
        var p = catalog[id], row = el("div", null, "line"), qty = el("span", null, "qty");
        var minus = el("button", "−"), plus = el("button", "+"), rm = el("button", "Xóa", "rm");
        minus.type = plus.type = rm.type = "button";
        minus.setAttribute("aria-label", "Bớt " + p.name); plus.setAttribute("aria-label", "Thêm " + p.name);
        minus.addEventListener("click", function () { var d = load(); d[id] = Math.max(1, (d[id] || 1) - 1); save(d); render(); });
        plus.addEventListener("click", function () { var d = load(); d[id] = Math.min(99, (d[id] || 0) + 1); save(d); render(); });
        rm.addEventListener("click", function () { var d = load(); delete d[id]; save(d); render(); });
        qty.appendChild(minus); qty.appendChild(el("span", c[id])); qty.appendChild(plus);
        row.appendChild(el("span", p.name)); row.appendChild(qty);
        row.appendChild(el("strong", money(p.price_vnd * c[id]))); row.appendChild(rm);
        if (p.in_stock !== undefined && c[id] > p.in_stock) row.appendChild(el("span", "Chỉ còn " + p.in_stock, "error"));
        list.appendChild(row);
        total += p.price_vnd * c[id];
      });
      $("cart-total").textContent = money(total);
    };
    api("api/products").then(function (d) {
      (d.products || []).forEach(function (p) { catalog[p.id] = p; });
      render();
    }).catch(function () { list.textContent = "Không tải được danh mục, vui lòng thử lại."; });

    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var c = load(), err = $("checkout-error");
      var items = Object.keys(c).filter(function (id) { return catalog[id]; }).map(function (id) { return { id: id, qty: c[id] }; });
      if (!items.length) { err.textContent = "Giỏ hàng đang trống."; return; }
      var fd = new FormData(form), btn = form.querySelector("button[type=submit]");
      var data = { name: fd.get("name"), phone: fd.get("phone"), address: fd.get("address"), note: fd.get("note") || "",
                   payment: fd.get("payment"), items: items };
      btn.disabled = true; err.textContent = "";
      post("api/orders", data).then(function (o) {
        try { sessionStorage.setItem("lastOrder", JSON.stringify(o)); } catch (e) { /* ignore */ }
        save({});
        location.href = "order.html?code=" + encodeURIComponent(o.code);
      }).catch(function (e) { err.textContent = e.message; btn.disabled = false; });
    });
  }

  // Order page: the order just placed, or a lookup by code + phone.
  var result = $("order-result");
  function showOrder(o, fresh) {
    result.textContent = "";
    var box = el("div", null, "receipt");
    box.appendChild(el("h2", fresh ? "Đặt hàng thành công" : "Đơn " + o.code));
    box.appendChild(el("p", "Mã đơn: " + o.code + " · Trạng thái: " + (STATUS[o.status] || o.status)));
    var ul = el("ul");
    (o.items || []).forEach(function (it) { ul.appendChild(el("li", it.name + " × " + it.qty + ": " + money(it.price_vnd * it.qty))); });
    box.appendChild(ul);
    box.appendChild(el("p", "Tổng cộng: " + money(o.total_vnd) + " · " + (PAYMENTS[o.payment] || o.payment), "total"));
    if (fresh) box.appendChild(el("p", "Hãy lưu lại mã đơn để tra cứu khi cần.", "muted"));
    result.appendChild(box);
    var bank = $("bank");
    if (bank) { bank.hidden = o.payment !== "bank_transfer" || o.status !== "new"; $("bank-ref").textContent = o.code; }
  }
  if (result) {
    var code = new URLSearchParams(location.search).get("code"), last = null;
    try { last = JSON.parse(sessionStorage.getItem("lastOrder") || "null"); } catch (e) { last = null; }
    if (code && last && last.code === code) showOrder(last, true);
    var lk = $("lookup");
    if (lk) {
      if (code) lk.elements.code.value = code;
      lk.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var fd = new FormData(lk), err = $("lookup-error"); err.textContent = "";
        post("api/orders/lookup", { code: String(fd.get("code")).trim().toUpperCase(), phone: fd.get("phone") })
          .then(function (o) { showOrder(o, false); }).catch(function (e) { err.textContent = e.message; });
      });
    }
  }

  // Admin page: the access code stays in this tab only.
  var login = $("admin-login"), box = $("admin-orders");
  if (login && box) {
    var token = "";
    try { token = sessionStorage.getItem("adminToken") || ""; } catch (e) { token = ""; }
    var showOrders = function () {
      var err = $("admin-error"); err.textContent = "";
      api("api/admin/orders", { headers: { Authorization: "Bearer " + token } }).then(function (d) {
        box.textContent = "";
        if (!d.orders.length) { box.appendChild(el("p", "Chưa có đơn hàng.", "muted")); return; }
        var t = el("table", null, "orders"), head = el("tr");
        ["Mã", "Thời gian", "Khách", "Sản phẩm", "Tổng", "Thanh toán", "Trạng thái"].forEach(function (h) { head.appendChild(el("th", h)); });
        t.appendChild(head);
        d.orders.forEach(function (o) {
          var tr = el("tr");
          tr.appendChild(el("td", o.code)); tr.appendChild(el("td", o.at.replace("T", " ")));
          tr.appendChild(el("td", o.name + " · " + o.phone + " · " + o.address + (o.note ? " · " + o.note : "")));
          tr.appendChild(el("td", o.items.map(function (i) { return i.name + " × " + i.qty; }).join(", ")));
          tr.appendChild(el("td", money(o.total_vnd))); tr.appendChild(el("td", PAYMENTS[o.payment] || o.payment));
          var td = el("td"), sel = el("select");
          sel.setAttribute("aria-label", "Trạng thái đơn " + o.code);
          Object.keys(STATUS).forEach(function (s) { var op = el("option", STATUS[s]); op.value = s; op.selected = s === o.status; sel.appendChild(op); });
          sel.addEventListener("change", function () {
            post("api/admin/orders/status", { code: o.code, status: sel.value }, token)
              .catch(function (e) { err.textContent = e.message; sel.value = o.status; });
          });
          td.appendChild(sel); tr.appendChild(td); t.appendChild(tr);
        });
        box.appendChild(t);
      }).catch(function (e) { err.textContent = e.status === 401 ? "Sai mã truy cập" : e.message; });
    };
    login.addEventListener("submit", function (ev) {
      ev.preventDefault();
      token = String(new FormData(login).get("token") || "");
      try { sessionStorage.setItem("adminToken", token); } catch (e) { /* ignore */ }
      showOrders();
    });
    if (token) showOrders();
  }
})();
"""


# --------------------------------------------------------------------------- QA

def qa_checks(spec: Spec, ws, collector):
    """Static checks on the shop pages. Yields (name, ok, detail)."""
    f = set(spec.features)
    need = ["checkout.html", "order.html", "cart.js"] + (["admin.html"] if "admin_orders" in f else [])
    missing = [p for p in need if not ws.exists(p)]
    yield "Shop đủ trang (giỏ hàng, đơn hàng, cart.js)", not missing, f"Thiếu: {', '.join(missing)}"
    if missing:
        return
    index = ws.read("index.html")
    ids_on_page = set(re.findall(r'data-id="([^"]+)"', index))
    lost = [p.id for p in spec.products if p.id not in ids_on_page]
    yield "Mọi sản phẩm trong danh mục có nút thêm vào giỏ", not lost, f"Thiếu data-id: {', '.join(lost[:10])}"
    pages = ["index.html"] + [p for p in need if p.endswith(".html")]
    no_js = [p for p in pages if not re.search(r'<script[^>]+src="cart\.js"', ws.read(p))]
    yield "Mọi trang nạp cart.js", not no_js, f"Không nạp cart.js: {', '.join(no_js)}"
    for page in pages[1:]:
        c = collector()
        c.feed(ws.read(page))
        bad = []
        if not c.doctype:
            bad.append("DOCTYPE")
        if not any(t == "html" and a.get("lang") for t, a in c.tags):
            bad.append("lang")
        if not any(t == "meta" and a.get("name", "").lower() == "viewport" for t, a in c.tags):
            bad.append("viewport")
        if sum(1 for t, _ in c.tags if t == "h1") != 1:
            bad.append("một h1")
        if not c.title.strip():
            bad.append("title")
        yield f"{page} đúng chuẩn trang", not bad, f"Thiếu: {', '.join(bad)}"
    c = collector()
    c.feed(ws.read("checkout.html"))
    controls = {a.get("name"): a for t, a in c.tags if t in ("input", "textarea", "select") and a.get("name")}
    orders = next(ep for ep in spec.api if ep.path == "/api/orders")
    form_fields = [fl for fl in orders.fields if fl.type != "items"]
    missing = [fl.name for fl in form_fields if fl.name not in controls]
    not_req = [fl.name for fl in form_fields if fl.required and fl.name in controls and "required" not in controls[fl.name]]
    pay = next(fl for fl in orders.fields if fl.name == "payment")
    offered = {a.get("value") for t, a in c.tags if t == "input" and a.get("name") == "payment"}
    yield ("Form đặt hàng khớp API contract", not missing and not not_req and offered == set(pay.choices),
           f"Thiếu ô: {missing}; chưa required: {not_req}; thanh toán {sorted(offered)} khác {pay.choices}")
    js = ws.read("cart.js")
    yield ("cart.js gọi đúng API", "api/orders" in js and "api/products" in js
           and ("order_lookup" not in f or "api/orders/lookup" in js)
           and ("admin_orders" not in f or "api/admin/orders" in js), "cart.js không gọi đủ endpoint trong contract")


def _call(base: str, method: str, path: str, data=None, token: str | None = None) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base + path, method=method, headers=headers,
                                 data=json.dumps(data).encode() if data is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, ValueError, ConnectionError):
        return 0, {}


def runtime_checks(spec: Spec, base: str, data_dir: Path, token: str, add) -> None:
    """Black-box tests against the running shop server, the way a malicious or careless shopper would use it."""
    f = set(spec.features)
    st, cat = _call(base, "GET", "/api/products")
    items = cat.get("products") or []
    add("GET /api/products trả danh mục", st == 200 and len(items) == len(spec.products),
        f"Trả {st}, {len(items)} sản phẩm (spec có {len(spec.products)})")
    if not spec.products:
        return
    p = max(spec.products, key=lambda x: x.price_vnd)
    order = {"name": "Khách thử", "phone": "0901 234 567", "address": "1 Lê Lợi", "payment": payments(spec.features)[0],
             "items": [{"id": p.id, "qty": 1, "price_vnd": 1}], "total_vnd": 1}
    st, o = _call(base, "POST", "/api/orders", order)
    add("Đặt hàng hợp lệ trả 201 kèm mã đơn", st == 201 and str(o.get("code", "")).startswith("DH"), f"Trả {st}: {o}")
    add("Tổng tiền tính ở server, bỏ qua giá gửi từ trình duyệt", o.get("total_vnd") == p.price_vnd,
        f"Tổng {o.get('total_vnd')}, đúng phải là {p.price_vnd}")
    saved = list(data_dir.rglob("*.json")) if data_dir.is_dir() else []
    add("Đơn được lưu vào thư mục --data", any(o.get("code", "?") in x.read_text(encoding="utf-8") for x in saved),
        f"Không thấy đơn trong {data_dir}")
    for name, bad in [("sản phẩm không tồn tại", {"items": [{"id": "khong-ton-tai", "qty": 1}]}),
                      ("số lượng 0", {"items": [{"id": p.id, "qty": 0}]}),
                      ("số lượng âm", {"items": [{"id": p.id, "qty": -3}]}),
                      ("thiếu số điện thoại", {"phone": ""}),
                      ("hình thức thanh toán lạ", {"payment": "bitcoin"})]:
        st, _ = _call(base, "POST", "/api/orders", {**order, **bad})
        add(f"Từ chối đơn có {name}", st == 400, f"Trả {st}, cần 400")
    if "stock" in f:
        small = min(spec.products, key=lambda x: x.stock)
        if small.stock < 99:
            st, _ = _call(base, "POST", "/api/orders", {**order, "items": [{"id": small.id, "qty": small.stock + 1}]})
            add("Không cho đặt quá tồn kho", st == 409, f"Trả {st}, cần 409")
    if "order_lookup" in f and o.get("code"):
        st, _ = _call(base, "POST", "/api/orders/lookup", {"code": o["code"], "phone": "0999999999"})
        add("Tra cứu sai số điện thoại bị từ chối", st == 404, f"Trả {st}, cần 404")
        st, found = _call(base, "POST", "/api/orders/lookup", {"code": o["code"], "phone": "0901234567"})
        add("Tra cứu đúng mã và số điện thoại", st == 200 and found.get("code") == o["code"], f"Trả {st}")
        add("Tra cứu không trả địa chỉ khách", "address" not in found, "Kết quả tra cứu lộ địa chỉ")
    if "admin_orders" in f:
        st, _ = _call(base, "GET", "/api/admin/orders")
        add("Trang quản lý từ chối khi thiếu mã truy cập", st == 401, f"Trả {st}, cần 401")
        st, _ = _call(base, "GET", "/api/admin/orders", token="sai-ma-truy-cap-123456")
        add("Trang quản lý từ chối mã sai", st == 401, f"Trả {st}, cần 401")
        st, listing = _call(base, "GET", "/api/admin/orders", token=token)
        add("Trang quản lý xem được đơn với mã đúng", st == 200 and bool(listing.get("orders")), f"Trả {st}")
        if o.get("code"):
            st, _ = _call(base, "POST", "/api/admin/orders/status", {"code": o["code"], "status": "paid"})
            add("Đổi trạng thái đơn cần mã truy cập", st == 401, f"Trả {st}, cần 401")
    for path in ("/api/server.py", "/api/products.json", "/api/data/orders.json"):
        st, _ = _call(base, "GET", path)
        add(f"Không lộ {path} qua HTTP", st == 404, f"Trả {st}")
