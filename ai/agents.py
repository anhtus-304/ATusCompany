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
    FEATURES, Brief, Check, ClientMemory, ClientMessage, CodeArtifact, DesignSpec, FileOut, FinalReport, Option, Proposal, QAReport,
    Section, Spec,
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


def extract_client_name(message: str) -> str | None:
    """Brand/client name the boss quoted in the request, e.g. 'Mộc Coffee'."""
    quoted = re.search(r"[\"“']([^\"”']{2,40})[\"”']", message)
    return quoted.group(1).strip() if quoted else None


def intake(llm: LLM, message: str, memory: ClientMemory | None = None) -> Brief:
    user = f"Yêu cầu của khách:\n\n{message}"
    if memory:
        user += f"\n\nBộ nhớ về khách hàng (đừng hỏi lại điều đã biết):\n{memory.as_prompt()}"
    out = llm.structured("intake", prompt("intake"), user, Brief)
    if out is not None:
        return out

    lower = message.lower()
    business, audience = "Doanh nghiệp", "Khách hàng tiềm năng của doanh nghiệp"
    for pattern, b, a in _BUSINESS_HINTS:
        if re.search(pattern, lower):
            business, audience = b, a
            break
    name = extract_client_name(message) or (memory.client_name if memory and memory.is_returning else business)
    budget = re.search(r"(\d[\d.,]*\s*(?:triệu|tr|k|đ|vnd|usd|\$))", lower)
    deadline = re.search(r"(\d+\s*(?:ngày|tuần|tháng|days?|weeks?))", lower)
    assumptions = [f"Đối tượng: {audience}", "Giọng điệu thân thiện, đáng tin cậy",
                   "Sản phẩm là landing page một trang"]
    questions = []
    budget_text = budget.group(1) if budget else None
    if memory and memory.is_returning:
        last = memory.projects[-1]
        assumptions.insert(0, f"Khách quen: đã làm {len(memory.projects)} dự án, gần nhất {last.date} ({last.title[:50]})")
        if not budget_text and memory.last_budget():
            budget_text = memory.last_budget()
            assumptions.append(f"Lấy ngân sách theo lần trước: {budget_text}")
        if memory.preferred_tier():
            tier_name = {"fast": "Nhanh & rẻ", "balanced": "Cân bằng", "premium": "Cao cấp"}.get(
                memory.preferred_tier(), memory.preferred_tier())
            assumptions.append(f"Khách thường chọn phương án {tier_name}")
        for n in memory.notes()[-3:]:
            assumptions.append(f"Lưu ý đã chốt trước đây: {n}")
    if not budget_text:
        questions.append("Ngân sách dự kiến cho dự án là bao nhiêu?")
    if not deadline:
        questions.append("Khách cần bàn giao khi nào?")
    if not (memory and memory.is_returning):
        questions.append("Khách có logo, ảnh thật, địa chỉ và số điện thoại để thay chỗ giữ chỗ không?")
    return Brief(
        project_name=name, business_type=business, goal=message.strip(),
        target_audience=audience, tone="Thân thiện, đáng tin cậy",
        language=_guess_language(message),
        budget=budget_text or "chưa rõ",
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


# --------------------------------------------------------------------------- Proposer (Architect)

def _budget_vnd(text: str) -> int | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(triệu|tr\b|k\b|nghìn)", text.lower())
    if not m:
        return None
    n = float(m.group(1).replace(",", "."))
    return int(n * (1_000_000 if m.group(2).startswith("tr") else 1_000))


def proposer(llm: LLM, brief: Brief, spec: Spec, note: str = "",
             previous: Proposal | None = None, memory: ClientMemory | None = None) -> Proposal:
    user = (f"Bộ nhớ khách hàng:\n{memory.as_prompt()}\n\n" if memory else "") + (f"Brief:\n{brief.model_dump_json(indent=2)}\n\nSpec gốc:\n{spec.model_dump_json(indent=2)}"
            f"\n\nTính năng cho phép:\n" + "\n".join(f"- {k}: {v}" for k, v in FEATURES.items()))
    if note:
        user += f"\n\nGóp ý của Sếp về các phương án lần trước:\n{note}"
        if previous:
            user += f"\n\nPhương án lần trước:\n{previous.model_dump_json(indent=2)}"
    out = llm.structured("proposer", prompt("proposer"), user, Proposal)
    if out is None:
        out = _mock_proposal(brief, spec, note, memory)
    return _normalize_proposal(out)


def _mock_proposal(brief: Brief, spec: Spec, note: str, memory: ClientMemory | None = None) -> Proposal:
    hero = spec.sections[0]
    contact = next(s for s in spec.sections if s.id == "contact")
    middle = [s for s in spec.sections if s.id not in ("hero", "contact")]
    gallery = Section(id="gallery", heading="Hình ảnh", purpose="Cho khách thấy không gian và sản phẩm",
                      content=["[Ảnh không gian]", "[Ảnh sản phẩm nổi bật]", "[Ảnh đội ngũ]"])
    faq = Section(id="faq", heading="Câu hỏi thường gặp", purpose="Giải đáp thắc mắc trước khi liên hệ",
                  content=["Giờ mở cửa thế nào?", "Có giao hàng không?", "Có chỗ đỗ xe không?"])
    budget = _budget_vnd(brief.budget)

    def over(price: int) -> list[str]:
        return [f"Vượt ngân sách khách nêu ({brief.budget})"] if budget and price > budget else []

    a_price, b_price, c_price = 2_500_000, 5_000_000, 12_000_000
    options = [
        Option(id="A", tier="fast", name="Nhanh & rẻ",
               summary="Trang ngắn 3 mục, đủ để khách biết và liên hệ.",
               sections=[hero, *middle[:1], contact], features=["responsive"],
               est_days=2, est_price_vnd=a_price,
               pros=["Bàn giao nhanh nhất", "Chi phí thấp, dễ chốt"],
               cons=["Ít nội dung tạo niềm tin", "Không có SEO cho chia sẻ mạng xã hội"] + over(a_price)),
        Option(id="B", tier="balanced", name="Cân bằng",
               summary="Đầy đủ các mục theo spec, có SEO cơ bản và menu dính.",
               sections=list(spec.sections), features=["responsive", "sticky_nav", "seo_meta"],
               est_days=5, est_price_vnd=b_price,
               pros=["Đủ nội dung để chuyển đổi khách", "Chia sẻ lên Facebook/Zalo hiển thị đẹp"],
               cons=["Cần khách cung cấp nội dung thật cho nhiều mục"] + over(b_price)),
        Option(id="C", tier="premium", name="Cao cấp",
               summary="Thêm thư viện ảnh, hỏi đáp, form liên hệ, giao diện tối và hiệu ứng.",
               sections=[hero, *middle, gallery, faq, contact], features=list(FEATURES),
               est_days=10, est_price_vnd=c_price,
               pros=["Trải nghiệm chuyên nghiệp, nổi bật", "Form liên hệ giảm bước cho khách"],
               cons=["Lâu và tốn kém hơn", "Cần ảnh chất lượng cao từ khách"] + over(c_price)),
    ]
    fitting = [o for o in options if not budget or o.est_price_vnd <= budget]
    rec = "B" if any(o.id == "B" for o in fitting) else (fitting[-1].id if fitting else "A")
    reasoning = (f"Phương án {rec} vừa ngân sách {brief.budget} và đủ để đạt mục tiêu."
                 if budget else f"Chưa rõ ngân sách nên khuyên phương án {rec} để cân bằng chi phí và hiệu quả.")
    tier = memory.preferred_tier() if memory else None
    liked = next((o for o in fitting if o.tier == tier), None)
    if liked and liked.id != rec:
        rec = liked.id
        reasoning = f"Khách quen thường chọn {liked.name} và phương án {rec} vẫn vừa ngân sách {brief.budget}."
    elif tier and memory:
        reasoning += f" Lần trước khách chọn {next(p.chosen_name for p in reversed(memory.projects) if p.chosen_name)}."
    if memory and memory.notes():
        reasoning += " Lưu ý đã chốt: " + "; ".join(memory.notes()[-2:]) + "."
    if note:
        reasoning += f" Đã ghi nhận góp ý của Sếp: {note}"
    return Proposal(options=options, recommended=rec, reasoning=reasoning)


def _normalize_proposal(p: Proposal) -> Proposal:
    for o in p.options:
        o.features = [f for f in o.features if f in FEATURES]
        tmp = Spec(project_name="", page_title="", goal="", audience="", language="", sections=o.sections,
                   cta_text="", palette=[], tech="", acceptance_criteria=[])
        o.sections = _normalize_spec(tmp).sections
        if "faq_accordion" in o.features and not any(s.id == "faq" for s in o.sections):
            o.features.remove("faq_accordion")
    if not p.get(p.recommended):
        p.recommended = p.options[0].id
    return p


def apply_option(spec: Spec, option: Option) -> Spec:
    """Final spec for the build: the analyst's spec narrowed/extended by the chosen option."""
    final = spec.model_copy(deep=True)
    final.sections = [s.model_copy() for s in option.sections]
    final.features = list(option.features)
    if not final.meta_description:
        final.meta_description = spec.goal[:155]
    if "contact_form" in final.features and not any(ep.path == "/api/contact" for ep in final.api):
        from .team import contact_endpoint
        final.api.append(contact_endpoint())
    final.acceptance_criteria = default_criteria() + [
        f"Tính năng: {FEATURES[f]}" for f in option.features]
    if final.api:
        final.acceptance_criteria += [
            "Backend có test tự động và tất cả đều đạt",
            *(f"{ep.method} {ep.path} đúng contract: dữ liệu hợp lệ trả {ep.success_status}, thiếu trường bắt buộc trả 400"
              for ep in final.api),
            "Reviewer không còn lỗi mức blocker/major",
        ]
    return final

# --------------------------------------------------------------------------- Frontend Dev

def frontend_dev(llm: LLM, spec: Spec, ws: RoleView, qa_failures: list[Check] | None = None,
                 previous: CodeArtifact | None = None, design: DesignSpec | None = None) -> CodeArtifact:
    user = f"Spec:\n{spec.model_dump_json(indent=2)}"
    if design:
        user += f"\n\nDesign spec:\n{design.model_dump_json(indent=2)}"
    if qa_failures:
        user += "\n\nLỗi cần sửa:\n" + "\n".join(f"- {c.name}: {c.detail}" for c in qa_failures)
        if previous:
            user += "\n\nCode lần trước:\n" + "\n\n".join(
                f"=== {f.path} ===\n{f.content}" for f in previous.files)
    out = llm.structured("frontend_dev", prompt("frontend_dev"), user, CodeArtifact)
    if out is None:
        out = _render_template(spec, design)
    for f in out.files:
        ws.write(f.path, f.content)
    return out


def _render_template(spec: Spec, design: DesignSpec | None = None) -> CodeArtifact:
    e = html.escape
    f = set(spec.features)
    pal = spec.palette + ["#3b2a20", "#a8652f", "#f6efe7", "#1f1a17"]
    c = (design.colors if design else
         {"brand": pal[0], "accent": pal[1], "surface": pal[2], "ink": pal[3], "muted": "#5c5047"})
    dark = (design.dark_colors if design and design.dark_colors else
            {"brand": "#e9d8c4", "accent": "#d9a26b", "surface": "#171310", "ink": "#efe6dc", "muted": "#b9ab9c"})
    font = design.font_stack if design else 'system-ui, -apple-system, "Segoe UI", sans-serif'
    radius = design.radius_px if design else 10
    width = design.max_width_px if design else 1040
    layout = {d.id: d.layout for d in design.sections} if design else {}
    api = {ep.path: ep for ep in spec.api}

    def form_html() -> str:
        ep = api.get("/api/contact")
        if not ep:
            return ""
        labels = {"name": "Họ tên", "phone": "Số điện thoại", "email": "Email", "message": "Lời nhắn"}
        types = {"phone": "tel", "email": "email", "string": "text"}
        rows = []
        for fld in ep.fields:
            req = " required" if fld.required else ""
            label = labels.get(fld.name, fld.name)
            if fld.type == "text":
                ctl = f'<textarea name="{fld.name}" rows="3" maxlength="{fld.max_length}"{req}></textarea>'
            else:
                ctl = f'<input name="{fld.name}" type="{types[fld.type]}" maxlength="{fld.max_length}"{req}>'
            rows.append(f"<label>{e(label)}{ctl}</label>")
        return ('\n    <form class="form" action="api/contact" method="post">' + "".join(rows)
                + '<button type="submit">Gửi</button></form>'
                  '\n    <p id="sent" class="sent" role="status">Đã nhận lời nhắn, chúng tôi sẽ liên hệ sớm.</p>')

    blocks = []
    for i, sec in enumerate(spec.sections):
        items = "".join(f"<li>{e(x)}</li>" for x in sec.content)
        cls = " reveal" if "animations" in f else ""
        lay = layout.get(sec.id, "grid")
        if i == 0:
            blocks.append(
                f'<section id="{sec.id}" class="hero">\n  <div class="wrap">\n'
                f"    <h1>{e(sec.heading)}</h1>\n    <p class=\"lead\">{e(sec.content[0] if sec.content else sec.purpose)}</p>\n"
                f'    <a class="cta" href="#contact">{e(spec.cta_text)}</a>\n  </div>\n</section>')
        elif sec.id == "faq" and "faq_accordion" in f:
            qs = "".join(f"<details><summary>{e(x)}</summary><p>[Câu trả lời]</p></details>" for x in sec.content)
            blocks.append(f'<section id="{sec.id}" class="{cls.strip()}">\n  <div class="wrap">\n    <h2>{e(sec.heading)}</h2>\n'
                          f"    {qs}\n  </div>\n</section>")
        elif sec.id == "contact":
            blocks.append(
                f'<section id="{sec.id}" class="{cls.strip()}">\n  <div class="wrap">\n    <h2>{e(sec.heading)}</h2>\n'
                f"    <ul>{items}</ul>{form_html() if 'contact_form' in f else ''}\n"
                f'    <a class="cta" href="#contact">{e(spec.cta_text)}</a>\n  </div>\n</section>')
        else:
            ul = {"grid": "grid", "split": "split", "list": "plain"}.get(lay, "grid")
            blocks.append(
                f'<section id="{sec.id}" class="{cls.strip()}">\n  <div class="wrap">\n    <h2>{e(sec.heading)}</h2>\n'
                f'    <ul class="{ul}">{items}</ul>\n  </div>\n</section>')
    blocks = [b.replace(' class=""', "") for b in blocks]
    nav = "".join(f'<a href="#{s.id}">{e(s.heading)}</a>' for s in spec.sections[1:])
    seo = ""
    if "seo_meta" in f:
        desc = e(spec.meta_description or spec.goal[:155])
        seo = (f'\n<meta name="description" content="{desc}">'
               f'\n<meta property="og:title" content="{e(spec.page_title)}">'
               f'\n<meta property="og:description" content="{desc}">')
    page = f"""<!DOCTYPE html>
<html lang="{e(spec.language)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">{seo}
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
    on_brand = "#f6efe7"
    css = f""":root {{ --brand: {c['brand']}; --accent: {c['accent']}; --surface: {c['surface']}; --ink: {c['ink']}; --muted: {c['muted']}; --card: #ffffff; --on-brand: {on_brand}; --radius: {radius}px; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: {font}; font-size: 16px; color: var(--ink); background: var(--surface); line-height: 1.6; }}
.wrap {{ max-width: {width}px; margin: 0 auto; padding: 0 16px; }}
.top {{ {"position: sticky; top: 0; z-index: 1; " if "sticky_nav" in f else ""}background: var(--brand); color: var(--on-brand); padding: 12px 0; }}
.top .wrap {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }}
.top nav a {{ color: var(--on-brand); margin-left: 16px; text-decoration: none; font-size: 14px; }}
section {{ padding: 64px 0; }}
section:nth-child(even) {{ background: var(--card); }}
.hero {{ background: var(--brand); color: var(--on-brand); padding: 96px 0; text-align: center; }}
.hero h1 {{ font-size: clamp(2rem, 6vw, 3.5rem); margin: 0 0 16px; }}
.lead {{ font-size: 1.2rem; max-width: 640px; margin: 0 auto 32px; }}
h2 {{ font-size: 1.8rem; margin-top: 0; }}
ul {{ padding-left: 20px; }}
.grid, .split {{ list-style: none; padding: 0; display: grid; gap: 16px; }}
.grid {{ grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
.split {{ grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }}
.grid li, .split li {{ background: var(--surface); border-left: 4px solid var(--accent); padding: 16px; border-radius: var(--radius); }}
.plain li {{ margin-bottom: 6px; }}
.cta {{ display: inline-block; background: var(--accent); color: #fff; padding: 14px 28px; border-radius: 999px; text-decoration: none; font-weight: 600; }}
.cta:hover {{ filter: brightness(1.1); }}
a:focus-visible, button:focus-visible, input:focus-visible, textarea:focus-visible, summary:focus-visible {{ outline: 3px solid var(--accent); outline-offset: 2px; }}
details {{ background: var(--surface); border-radius: var(--radius); padding: 12px 16px; margin-bottom: 8px; }}
summary {{ font-weight: 600; cursor: pointer; }}
.form {{ display: grid; gap: 12px; max-width: 480px; margin: 16px 0 24px; }}
.form label {{ display: grid; gap: 4px; font-weight: 600; }}
.form input, .form textarea {{ font: inherit; padding: 10px; border: 1px solid var(--muted); border-radius: var(--radius); background: var(--card); color: var(--ink); }}
.form button {{ justify-self: start; background: var(--ink); color: var(--surface); border: 0; padding: 10px 20px; border-radius: var(--radius); font: inherit; cursor: pointer; }}
.sent {{ display: none; color: var(--accent); font-weight: 600; }}
.sent:target {{ display: block; }}
footer {{ background: var(--ink); color: var(--surface); padding: 24px 0; font-size: 14px; }}
"""
    if "responsive" in f:
        css += "@media (max-width: 600px) { .top nav { display: none; } section { padding: 48px 0; } }\n"
    if "dark_mode" in f:
        css += ("@media (prefers-color-scheme: dark) {\n"
                f"  :root {{ --surface: {dark['surface']}; --ink: {dark['ink']}; --muted: {dark['muted']}; --card: #211b16; }}\n"
                "  footer { background: #0d0b09; color: var(--ink); }\n}\n")
    if "animations" in f:
        css += ("@keyframes rise { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: none; } }\n"
                ".reveal { animation: rise .7s ease-out both; }\n"
                "@media (prefers-reduced-motion: reduce) { .reveal { animation: none; } }\n")
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


def _feature_checks(spec: Spec, ws: RoleView, src: str, tags: list[tuple[str, dict]]):
    """Checks for the design features of the chosen option."""
    css = src + "\n".join(ws.read(f) for f in ws.list_files() if f.endswith(".css"))
    css_flat = re.sub(r"\s+", "", css.lower())
    meta = lambda key, val: any(t == "meta" and a.get(key, "").lower() == val for t, a in tags)  # noqa: E731
    rules = {
        "responsive": ("@media" in css_flat, "CSS không có @media"),
        "sticky_nav": ("position:sticky" in css_flat, "Không có position: sticky"),
        "dark_mode": ("prefers-color-scheme:dark" in css_flat, "Không có @media (prefers-color-scheme: dark)"),
        "animations": ("@keyframes" in css_flat and "prefers-reduced-motion" in css_flat,
                       "Thiếu @keyframes hoặc chưa tôn trọng prefers-reduced-motion"),
        "faq_accordion": (bool(re.search(r'<section[^>]*id="faq".*?<details', src, re.S)),
                          "Mục #faq không dùng <details>"),
        "contact_form": (bool(re.search(r'<section[^>]*id="contact".*?<form[^>]*action="/?api/contact"[^>]*method="post"', src, re.S | re.I)),
                         "Mục #contact không có <form action=\"api/contact\" method=\"post\">"),
        "seo_meta": (meta("name", "description") and meta("property", "og:title"),
                     "Thiếu meta description hoặc og:title"),
    }
    for feat in spec.features:
        if feat in rules:
            ok, detail = rules[feat]
            yield f"Tính năng: {FEATURES[feat]}", ok, detail


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

    for name, ok, detail in _feature_checks(spec, ws, src, tags):
        add(name, ok, detail)

    for ep in spec.api:
        if ep.method != "POST" or ep.path != "/api/contact" or "contact_form" not in spec.features:
            continue
        controls = {a.get("name"): a for t, a in tags if t in ("input", "textarea", "select") and a.get("name")}
        missing = [fl.name for fl in ep.fields if fl.name not in controls]
        not_req = [fl.name for fl in ep.fields if fl.required and fl.name in controls
                   and "required" not in controls[fl.name]]
        add("Form khớp API contract", not missing and not not_req,
            f"Thiếu ô: {missing}; ô bắt buộc chưa có required: {not_req}")

    size = sum(len(ws.read(f).encode()) for f in ws.list_files())
    add("Tổng dung lượng < 300KB", size < 300_000, f"Tổng {size} byte")

    return QAReport(passed=all(c.passed for c in checks), checks=checks)


# --------------------------------------------------------------------------- Reporter

def reporter(llm: LLM, brief: Brief, spec: Spec, qa_report: QAReport, fix_rounds: int,
             cost: dict, escalated: bool, option: Option | None = None,
             review: "ReviewReport | None" = None, memory: ClientMemory | None = None) -> FinalReport:
    chosen = (f"Phương án sếp chọn: {option.id} - {option.name}, {option.est_days} ngày, "
              f"{option.est_price_vnd:,} VND, tính năng: {', '.join(option.features)}\n\n") if option else ""
    user = (f"Brief:\n{brief.model_dump_json(indent=2)}\n\n{chosen}Spec (rút gọn): {spec.project_name}, "
            f"{len(spec.sections)} mục: {', '.join(s.id for s in spec.sections)}\n\n"
            f"QA:\n{qa_report.model_dump_json(indent=2)}\n\nSố vòng sửa lỗi: {fix_rounds}\n"
            f"Đã vượt ngưỡng sửa lỗi tự động: {escalated}\nChi phí: {cost}"
            + (f"\n\nReview:\n{review.model_dump_json(indent=2)}" if review else "")
            + (f"\n\nBộ nhớ khách hàng:\n{memory.as_prompt()}" if memory else ""))
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
    if review:
        blocking = review.blocking()
        minors = [f for f in review.findings if f.severity == "minor"]
        if blocking:
            risks.insert(0, "Reviewer còn lỗi chưa sửa: " + "; ".join(f"{f.file}: {f.message}" for f in blocking))
        if minors:
            remaining.append("Gợi ý từ Reviewer: " + "; ".join(f"{f.file}: {f.message}" for f in minors))
    if spec.api:
        risks.append("Backend lưu dữ liệu khách vào file trên máy chủ, cần chọn hosting có backup trước khi chạy thật")
    if escalated:
        risks.insert(0, "Đã hết số lần sửa lỗi tự động, cần người xử lý")
    return FinalReport(
        summary=(f"Đã làm xong landing page tĩnh cho {spec.project_name} theo phương án "
                 f"{option.id + ' (' + option.name + ')' if option else 'mặc định'}, {len(spec.sections)} mục. "
                 f"QA chạy {total} kiểm tra, {status} sau {fix_rounds} vòng sửa."
                 + (f" Đây là dự án thứ {len(memory.projects) + 1} của khách {memory.client_name}."
                    if memory and memory.is_returning else "")),
        done=["Tiếp nhận và chuẩn hóa yêu cầu", "Viết spec và tiêu chí nghiệm thu",
              *([f"Sếp chọn phương án {option.id}: {option.est_days:g} ngày, báo khách {option.est_price_vnd:,} VND"]
                if option else []),
              "UI/UX Designer lập design spec (màu, font, bố cục từng mục)",
              *(["Backend Dev viết API " + ", ".join(ep.path for ep in spec.api) + " kèm test"] if spec.api else []),
              "Frontend Dev code index.html + styles.css, commit vào repo dự án",
              f"QA {passed}/{total} kiểm tra đạt",
              *([f"Reviewer: {len(review.blocking())} lỗi chặn, {len(review.findings)} ghi chú"] if review else [])],
        remaining=remaining,
        risks=risks,
        decisions_needed=["Duyệt gửi bản demo cho khách", "Duyệt deploy lên hosting"]
        + (["Chọn nơi lưu dữ liệu khách (file hiện tại, Google Sheet, hay CRM)"] if spec.api else [])
        + brief.open_questions,
    )


# How each feature is described to a client: what it does for them, not how it is built.
CLIENT_FEATURES = {
    "responsive": "hiển thị đẹp trên điện thoại",
    "sticky_nav": "menu luôn hiện khi cuộn trang",
    "dark_mode": "tự đổi giao diện tối theo máy người xem",
    "animations": "hiệu ứng nhẹ khi cuộn",
    "faq_accordion": "mục hỏi đáp",
    "contact_form": "form liên hệ, thông tin khách để lại được lưu lại cho anh/chị",
    "seo_meta": "tối ưu cho Google và khi chia sẻ lên mạng xã hội",
}


def client_message(llm: LLM, brief: Brief, spec: Spec, option: Option | None, report: FinalReport,
                   links: dict[str, str], client_name: str) -> ClientMessage:
    """Draft the hand-over email. Gets only what the client may see: no cost, QA or review internals."""
    link_lines = "\n".join(f"- {k}: {v}" for k, v in links.items()) or "- (chưa có link)"
    chosen = (f"Phương án đã chốt: {option.name}, {option.est_days:g} ngày, {option.est_price_vnd:,} VND, "
              f"tính năng: {', '.join(CLIENT_FEATURES.get(f, f) for f in option.features)}\n") if option else ""
    user = (f"Khách: {client_name}\nNgôn ngữ trang: {brief.language}\nMục tiêu: {brief.goal}\n{chosen}"
            f"Các mục của trang: {', '.join(s.heading for s in spec.sections)}\n"
            f"Câu hỏi còn mở với khách: {'; '.join(brief.open_questions) or 'không'}\n"
            f"Link:\n{link_lines}")
    out = llm.structured("reporter", prompt("client_message"), user, ClientMessage)
    if out is not None:
        return out

    link = links.get("Bản chạy thật") or links.get("Bản demo") or ""
    todo = ["Gửi ảnh thật và logo để thay ảnh minh họa",
            "Xem lại các nội dung trong ngoặc vuông [..] và gửi thông tin chính xác (địa chỉ, số điện thoại, giờ mở cửa)"]
    todo += [q for q in brief.open_questions if not re.search(r"logo|ảnh|địa chỉ|điện thoại", q, re.I)][:3]
    lines = [f"Chào anh/chị {client_name},", "",
             f"Bên em đã hoàn thành bản demo landing page {spec.project_name}"
             + (f" theo phương án {option.name}" if option else "") + ".",
             "Trang gồm các mục: " + ", ".join(s.heading for s in spec.sections) + "."]
    if option and option.features:
        lines.append("Trang có " + ", ".join(CLIENT_FEATURES.get(f, FEATURES.get(f, f)) for f in option.features) + ".")
    if link:
        lines += ["", f"Anh/chị xem trang tại: {link}"]
    lines += ["", "Để hoàn thiện, anh/chị giúp bên em:", *[f"- {t}" for t in todo], "",
              "Anh/chị xem và phản hồi giúp em, bên em sẽ chỉnh theo góp ý.", "", "Trân trọng."]
    return ClientMessage(subject=f"Bàn giao bản demo landing page {spec.project_name}", body="\n".join(lines))

