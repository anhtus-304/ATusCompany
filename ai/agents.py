"""The phase-1 agents: Intake, Analyst/Architect, Frontend Dev, QA, Reporter.

Each agent takes structured artifacts in and returns one structured artifact.
When the LLM is the offline mock, agents use deterministic fallbacks so the
whole pipeline still runs end to end (tests, demos, no API key).
"""
from __future__ import annotations

import html
import re
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

from .artifacts import (
    Brief, Check, CodeArtifact, FileOut, FinalReport, QAReport, Section, Spec,
)
from .llm import LLM
from .workspace import RoleView

PROMPTS = Path(__file__).parent / "prompts"


def prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- Intake

_BUSINESS_HINTS = [
    (r"cà phê|cafe|coffee", "Quán cà phê", "Người yêu cà phê 20-40 tuổi trong khu vực"),
    (r"spa|làm đẹp|beauty", "Spa & làm đẹp", "Phụ nữ 25-45 tuổi quan tâm chăm sóc bản thân"),
    (r"nha khoa|dental", "Phòng khám nha khoa", "Gia đình và người đi làm cần chăm sóc răng"),
    (r"nhà hàng|quán ăn|restaurant", "Nhà hàng", "Thực khách địa phương và khách du lịch"),
    (r"gym|thể hình|fitness", "Phòng tập thể hình", "Người 18-40 tuổi muốn rèn luyện sức khỏe"),
    (r"khóa học|course|đào tạo", "Khóa học", "Người đi làm muốn nâng cao kỹ năng"),
    (r"app|ứng dụng|saas|phần mềm", "Sản phẩm phần mềm", "Doanh nghiệp nhỏ và người dùng cá nhân"),
]


def _guess_language(text: str) -> str:
    vi = re.search(r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]", text.lower())
    return "vi" if vi else "en"


def intake(llm: LLM, message: str) -> Brief:
    out = llm.structured("intake", prompt("intake"), f"Yêu cầu của khách:\n\n{message}", Brief)
    if out is not None:
        return out

    lower = message.lower()
    business, audience = "Doanh nghiệp", "Khách hàng tiềm năng của doanh nghiệp"
    for pattern, b, a in _BUSINESS_HINTS:
        if re.search(pattern, lower):
            business, audience = b, a
            break
    quoted = re.search(r"[\"“']([^\"”']{2,40})[\"”']", message)
    name = quoted.group(1).strip() if quoted else business
    budget = re.search(r"(\d[\d.,]*\s*(?:triệu|tr|k|đ|vnd|usd|\$))", lower)
    deadline = re.search(r"(\d+\s*(?:ngày|tuần|tháng|days?|weeks?))", lower)
    assumptions = [f"Đối tượng: {audience}", "Giọng điệu thân thiện, đáng tin cậy",
                   "Giai đoạn 1 chỉ làm landing page tĩnh một trang"]
    questions = []
    if not budget:
        questions.append("Ngân sách dự kiến cho dự án là bao nhiêu?")
    if not deadline:
        questions.append("Khách cần bàn giao khi nào?")
    questions.append("Khách có logo, ảnh thật, địa chỉ và số điện thoại để thay chỗ giữ chỗ không?")
    return Brief(
        project_name=name, business_type=business, goal=message.strip(),
        target_audience=audience, tone="Thân thiện, đáng tin cậy",
        language=_guess_language(message),
        budget=budget.group(1) if budget else "chưa rõ",
        deadline=deadline.group(1) if deadline else "chưa rõ",
        assumptions=assumptions, open_questions=questions,
    )


# --------------------------------------------------------------------------- Analyst

def analyst(llm: LLM, brief: Brief) -> Spec:
    out = llm.structured("analyst", prompt("analyst"),
                         f"Brief:\n{brief.model_dump_json(indent=2)}", Spec)
    if out is not None:
        return _normalize_spec(out)

    n = brief.project_name
    sections = [
        Section(id="hero", heading=n, purpose="Gây ấn tượng và nêu giá trị chính",
                content=[f"{n}: {brief.business_type.lower()} dành cho {brief.target_audience.lower()}",
                         "Một câu khẳng định giá trị nổi bật"]),
        Section(id="features", heading="Vì sao chọn chúng tôi", purpose="Lợi ích chính",
                content=["Chất lượng ổn định", "Phục vụ tận tâm", "Giá hợp lý"]),
        Section(id="about", heading="Về chúng tôi", purpose="Tạo niềm tin",
                content=[f"Câu chuyện của {n}", "[Năm thành lập, con số nổi bật]"]),
        Section(id="testimonials", heading="Khách hàng nói gì", purpose="Bằng chứng xã hội",
                content=["[Nhận xét khách hàng 1]", "[Nhận xét khách hàng 2]"]),
        Section(id="contact", heading="Liên hệ", purpose="Chuyển đổi",
                content=["[Địa chỉ]", "[Số điện thoại]", "[Giờ mở cửa]"]),
    ]
    return Spec(
        project_name=n, page_title=f"{n} | {brief.business_type}", goal=brief.goal,
        audience=brief.target_audience, language=brief.language, sections=sections,
        cta_text="Liên hệ ngay" if brief.language == "vi" else "Contact us",
        palette=["#3b2a20", "#c8956d", "#f6efe7", "#1f1f1f"],
        tech="HTML5 + CSS tĩnh, không phụ thuộc bên ngoài",
        acceptance_criteria=default_criteria(),
    )


def default_criteria() -> list[str]:
    return [
        "Có index.html với DOCTYPE, lang, meta charset, meta viewport và title đúng spec",
        "Mỗi mục trong spec có section với id tương ứng",
        "Có đúng một thẻ h1",
        "Mọi ảnh có thuộc tính alt",
        "Liên kết nội bộ #id không gãy, tài nguyên nội bộ tồn tại",
        "Không tải script hay tài nguyên từ bên ngoài",
        "Có nút CTA với đúng chữ trong spec",
    ]


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.replace("đ", "d").replace("Đ", "D"))
    s = s.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "section"


def _normalize_spec(spec: Spec) -> Spec:
    seen: set[str] = set()
    for sec in spec.sections:
        sid = _slug(sec.id)
        while sid in seen:
            sid += "-2"
        seen.add(sid)
        sec.id = sid
    if "contact" not in seen:
        spec.sections.append(Section(id="contact", heading="Liên hệ", purpose="Chuyển đổi",
                                     content=["[Thông tin liên hệ]"]))
    return spec


# --------------------------------------------------------------------------- Frontend Dev

def frontend_dev(llm: LLM, spec: Spec, ws: RoleView, qa_failures: list[Check] | None = None,
                 previous: CodeArtifact | None = None) -> CodeArtifact:
    user = f"Spec:\n{spec.model_dump_json(indent=2)}"
    if qa_failures:
        user += "\n\nLỗi QA cần sửa:\n" + "\n".join(f"- {c.name}: {c.detail}" for c in qa_failures)
        if previous:
            user += "\n\nCode lần trước:\n" + "\n\n".join(
                f"=== {f.path} ===\n{f.content}" for f in previous.files)
    out = llm.structured("frontend_dev", prompt("frontend_dev"), user, CodeArtifact)
    if out is None:
        out = _render_template(spec)
    for f in out.files:
        ws.write(f.path, f.content)
    return out


def _render_template(spec: Spec) -> CodeArtifact:
    e = html.escape
    bg, accent, light, dark = (spec.palette + ["#333", "#c80", "#fafafa", "#111"])[:4]
    blocks = []
    for i, sec in enumerate(spec.sections):
        items = "".join(f"<li>{e(c)}</li>" for c in sec.content)
        if i == 0:
            blocks.append(
                f'<section id="{sec.id}" class="hero">\n  <div class="wrap">\n'
                f"    <h1>{e(sec.heading)}</h1>\n    <p class=\"lead\">{e(sec.content[0] if sec.content else sec.purpose)}</p>\n"
                f'    <a class="cta" href="#contact">{e(spec.cta_text)}</a>\n  </div>\n</section>')
        elif sec.id == "contact":
            blocks.append(
                f'<section id="{sec.id}">\n  <div class="wrap">\n    <h2>{e(sec.heading)}</h2>\n'
                f"    <ul>{items}</ul>\n"
                f'    <a class="cta" href="#contact">{e(spec.cta_text)}</a>\n  </div>\n</section>')
        else:
            blocks.append(
                f'<section id="{sec.id}">\n  <div class="wrap">\n    <h2>{e(sec.heading)}</h2>\n'
                f"    <ul class=\"grid\">{items}</ul>\n  </div>\n</section>")
    nav = "".join(f'<a href="#{s.id}">{e(s.heading)}</a>' for s in spec.sections[1:])
    page = f"""<!DOCTYPE html>
<html lang="{e(spec.language)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(spec.page_title)}</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>
<header class="top"><div class="wrap"><strong>{e(spec.project_name)}</strong><nav>{nav}</nav></div></header>
<main>
{chr(10).join(blocks)}
</main>
<footer><div class="wrap">© {e(spec.project_name)}</div></footer>
</body>
</html>
"""
    css = f""":root {{ --bg: {bg}; --accent: {accent}; --light: {light}; --dark: {dark}; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: var(--dark); background: var(--light); line-height: 1.6; }}
.wrap {{ max-width: 1040px; margin: 0 auto; padding: 0 16px; }}
.top {{ position: sticky; top: 0; background: var(--bg); color: var(--light); padding: 12px 0; z-index: 1; }}
.top .wrap {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }}
.top nav a {{ color: var(--light); margin-left: 16px; text-decoration: none; font-size: 14px; }}
section {{ padding: 64px 0; }}
section:nth-child(even) {{ background: #fff; }}
.hero {{ background: var(--bg); color: var(--light); padding: 96px 0; text-align: center; }}
.hero h1 {{ font-size: clamp(2rem, 6vw, 3.5rem); margin: 0 0 16px; }}
.lead {{ font-size: 1.2rem; max-width: 640px; margin: 0 auto 32px; }}
h2 {{ font-size: 1.8rem; margin-top: 0; }}
ul {{ padding-left: 20px; }}
.grid {{ list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }}
.grid li {{ background: var(--light); border-left: 4px solid var(--accent); padding: 16px; border-radius: 8px; }}
.cta {{ display: inline-block; background: var(--accent); color: #fff; padding: 14px 28px; border-radius: 999px; text-decoration: none; font-weight: 600; }}
.cta:hover {{ filter: brightness(1.1); }}
footer {{ background: var(--dark); color: var(--light); padding: 24px 0; font-size: 14px; }}
@media (max-width: 600px) {{ .top nav {{ display: none; }} section {{ padding: 48px 0; }} }}
"""
    return CodeArtifact(files=[FileOut(path="index.html", content=page),
                               FileOut(path="styles.css", content=css)],
                        notes="Sinh từ template offline (chế độ mock).")


# --------------------------------------------------------------------------- QA

class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.doctype = False
        self.tags: list[tuple[str, dict]] = []
        self.title = ""
        self._in_title = False
        self._anchor: dict | None = None
        self.anchors: list[tuple[dict, str]] = []

    def handle_decl(self, decl):
        if decl.lower().startswith("doctype html"):
            self.doctype = True

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        self.tags.append((tag, a))
        if tag == "title":
            self._in_title = True
        if tag == "a":
            self._anchor = {**a, "_text": ""}

    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, {k: (v or "") for k, v in attrs}))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._anchor is not None:
            self.anchors.append((self._anchor, self._anchor["_text"].strip()))
            self._anchor = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._anchor is not None:
            self._anchor["_text"] += data


def _external(url: str) -> bool:
    return bool(re.match(r"^(https?:)?//", url.strip(), re.I))


def qa(spec: Spec, ws: RoleView) -> QAReport:
    """Runs real checks on the files. Read-only: QA never edits code."""
    checks: list[Check] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append(Check(name=name, passed=bool(ok), detail="" if ok else detail))

    if not ws.exists("index.html"):
        add("index.html tồn tại", False, "Không tìm thấy index.html")
        return QAReport(passed=False, checks=checks)

    src = ws.read("index.html")
    p = _Collector()
    p.feed(src)
    tags = p.tags
    ids = {a.get("id") for _, a in tags if a.get("id")}

    add("index.html tồn tại", True)
    add("Có <!DOCTYPE html>", p.doctype, "Thiếu khai báo DOCTYPE html")
    html_tag = next((a for t, a in tags if t == "html"), {})
    add("Thẻ html có lang", bool(html_tag.get("lang")), "Thiếu thuộc tính lang trên <html>")
    add("Có meta charset", any(t == "meta" and "charset" in a for t, a in tags), "Thiếu <meta charset>")
    add("Có meta viewport",
        any(t == "meta" and a.get("name", "").lower() == "viewport" for t, a in tags),
        "Thiếu <meta name=viewport>")
    add("Title đúng spec", p.title.strip() == spec.page_title.strip(),
        f"Title là '{p.title.strip()}', spec yêu cầu '{spec.page_title}'")

    missing = [s.id for s in spec.sections if s.id not in ids]
    add("Đủ các section theo spec", not missing, f"Thiếu id: {', '.join(missing)}")

    h1 = sum(1 for t, _ in tags if t == "h1")
    add("Đúng một thẻ h1", h1 == 1, f"Có {h1} thẻ h1")

    no_alt = [a.get("src", "?") for t, a in tags if t == "img" and not a.get("alt", "").strip()]
    add("Ảnh có alt", not no_alt, f"Ảnh thiếu alt: {', '.join(no_alt)}")

    broken = sorted({a["href"] for a, _ in p.anchors
                     if a.get("href", "").startswith("#") and len(a["href"]) > 1 and a["href"][1:] not in ids})
    add("Liên kết nội bộ không gãy", not broken, f"Trỏ tới id không tồn tại: {', '.join(broken)}")

    refs = [a.get("src") or a.get("href") for t, a in tags
            if t in ("script", "img", "link", "source") and (a.get("src") or a.get("href"))]
    external = [r for r in refs if _external(r)]
    add("Không phụ thuộc tài nguyên ngoài", not external, f"Tài nguyên ngoài: {', '.join(external)}")
    local_missing = [r for r in refs if not _external(r) and not r.startswith("data:")
                     and not ws.exists(r.split("#")[0].split("?")[0])]
    add("Tài nguyên nội bộ tồn tại", not local_missing, f"Không tìm thấy: {', '.join(local_missing)}")

    cta_ok = any(text == spec.cta_text.strip() for _, text in p.anchors) or bool(
        re.search(r"<button[^>]*>\s*" + re.escape(html.escape(spec.cta_text.strip(), quote=False)) + r"\s*</button>", src))
    add("Có nút CTA đúng chữ", cta_ok, f"Không có liên kết/nút với chữ '{spec.cta_text}'")

    size = sum(len(ws.read(f).encode()) for f in ws.list_files())
    add("Tổng dung lượng < 300KB", size < 300_000, f"Tổng {size} byte")

    return QAReport(passed=all(c.passed for c in checks), checks=checks)


# --------------------------------------------------------------------------- Reporter

def reporter(llm: LLM, brief: Brief, spec: Spec, qa_report: QAReport, fix_rounds: int,
             cost: dict, escalated: bool) -> FinalReport:
    user = (f"Brief:\n{brief.model_dump_json(indent=2)}\n\nSpec (rút gọn): {spec.project_name}, "
            f"{len(spec.sections)} mục: {', '.join(s.id for s in spec.sections)}\n\n"
            f"QA:\n{qa_report.model_dump_json(indent=2)}\n\nSố vòng sửa lỗi: {fix_rounds}\n"
            f"Đã vượt ngưỡng sửa lỗi tự động: {escalated}\nChi phí: {cost}")
    out = llm.structured("reporter", prompt("reporter"), user, FinalReport)
    if out is not None:
        return out

    passed = sum(c.passed for c in qa_report.checks)
    total = len(qa_report.checks)
    status = "đạt toàn bộ" if qa_report.passed else f"còn {total - passed} lỗi"
    remaining = ["Thay nội dung giữ chỗ [..] bằng thông tin thật của khách"]
    if not qa_report.passed:
        remaining.insert(0, "Sửa các lỗi QA còn lại: " + "; ".join(c.name for c in qa_report.failures()))
    risks = ["Nội dung do AI viết, cần người kiểm tra trước khi gửi khách"]
    if escalated:
        risks.insert(0, "Đã hết số lần sửa lỗi tự động, cần người xử lý")
    return FinalReport(
        summary=(f"Đã làm xong landing page tĩnh cho {spec.project_name} với {len(spec.sections)} mục. "
                 f"QA chạy {total} kiểm tra, {status} sau {fix_rounds} vòng sửa."),
        done=["Tiếp nhận và chuẩn hóa yêu cầu", "Viết spec và tiêu chí nghiệm thu",
              "Code index.html + styles.css, commit vào repo dự án", f"QA {passed}/{total} kiểm tra đạt"],
        remaining=remaining,
        risks=risks,
        decisions_needed=["Duyệt gửi bản demo cho khách", "Duyệt deploy lên hosting"]
        + brief.open_questions,
    )
