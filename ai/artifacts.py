"""Structured artifacts that agents hand to each other.

Agents never talk in free-form chat. Each stage reads the previous stage's
artifact and produces its own, validated by these Pydantic models.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PastProject(BaseModel):
    project_id: str
    title: str
    status: str
    date: str
    budget: str = "chưa rõ"
    chosen_tier: str | None = None
    chosen_name: str | None = None
    price_vnd: int | None = None
    features: list[str] = Field(default_factory=list)


class PastDecision(BaseModel):
    kind: str  # choice | revision | approved | changes_requested | note | budget | stopped | deployed | sent | pushed
    text: str
    date: str


class ClientMemory(BaseModel):
    """What the office remembers about a client: earlier projects and decisions already made."""

    client_name: str
    contact: str = ""
    projects: list[PastProject] = Field(default_factory=list)
    decisions: list[PastDecision] = Field(default_factory=list)

    @property
    def is_returning(self) -> bool:
        return bool(self.projects)

    def last_budget(self) -> str | None:
        for p in reversed(self.projects):
            if p.budget and p.budget != "chưa rõ":
                return p.budget
        return None

    def preferred_tier(self) -> str | None:
        tiers = [p.chosen_tier for p in self.projects if p.chosen_tier]
        return max(set(tiers), key=tiers.count) if tiers else None

    def notes(self) -> list[str]:
        return [d.text for d in self.decisions if d.kind in ("note", "revision", "changes_requested")]

    def as_prompt(self) -> str:
        if not self.projects and not self.decisions:
            return f"Khách mới: {self.client_name}. Chưa có lịch sử."
        lines = [f"Khách quen: {self.client_name}" + (f" ({self.contact})" if self.contact else "")]
        for p in self.projects[-5:]:
            chosen = f", chọn {p.chosen_name} ({p.price_vnd:,} VND)" if p.chosen_name and p.price_vnd else ""
            lines.append(f"- {p.date}: {p.title} | ngân sách {p.budget}{chosen} | trạng thái {p.status}")
        for d in self.decisions[-10:]:
            lines.append(f"- Quyết định {d.date} [{d.kind}]: {d.text}")
        return "\n".join(lines)


class Brief(BaseModel):
    """Intake (Lễ tân) output: the client's request, cleaned up."""

    project_name: str = Field(description="Tên ngắn của dự án / thương hiệu")
    business_type: str = Field(description="Loại hình kinh doanh, ví dụ quán cà phê")
    goal: str = Field(description="Mục tiêu chính của landing page")
    target_audience: str
    tone: str = Field(description="Giọng điệu, ví dụ ấm áp, chuyên nghiệp")
    language: str = Field(description="Mã ngôn ngữ nội dung trang, ví dụ vi")
    budget: str = Field(description="Ngân sách nếu khách nêu, nếu không ghi 'chưa rõ'")
    deadline: str = Field(description="Thời hạn nếu khách nêu, nếu không ghi 'chưa rõ'")
    assumptions: list[str] = Field(description="Giả định đã tự đặt khi thiếu thông tin")
    open_questions: list[str] = Field(description="Câu hỏi cần sếp/khách trả lời sau")


class Section(BaseModel):
    id: str = Field(description="id HTML dạng kebab-case, ví dụ hero, menu, contact")
    heading: str
    purpose: str
    content: list[str] = Field(description="Các ý nội dung cụ thể sẽ xuất hiện trong mục")


class ApiField(BaseModel):
    name: str
    type: Literal["string", "email", "phone", "text"]
    required: bool
    max_length: int = 500


class ApiEndpoint(BaseModel):
    """Contract the Architect fixes so Frontend and Backend can work in parallel."""

    method: Literal["GET", "POST"]
    path: str = Field(description="Đường dẫn, ví dụ /api/contact")
    purpose: str
    fields: list[ApiField] = Field(default_factory=list)
    success_status: int = 201


class Spec(BaseModel):
    """Business Analyst + Architect output."""

    project_name: str
    page_title: str = Field(description="Nội dung thẻ <title>")
    goal: str
    audience: str
    language: str
    sections: list[Section]
    cta_text: str = Field(description="Chữ trên nút kêu gọi hành động chính")
    palette: list[str] = Field(description="3-5 mã màu hex")
    tech: str = Field(description="Công nghệ, giai đoạn 1 luôn là HTML + CSS tĩnh")
    acceptance_criteria: list[str]
    features: list[str] = Field(default_factory=list,
                                description="Mã tính năng, được điền sau khi sếp chọn phương án")
    meta_description: str = Field(default="", description="Mô tả ngắn cho SEO, 1 câu")
    api: list[ApiEndpoint] = Field(default_factory=list, description="API backend, rỗng nếu trang tĩnh")


Layout = Literal["hero", "grid", "list", "split", "faq", "form"]


class SectionDesign(BaseModel):
    id: str
    layout: Layout
    note: str = ""


class DesignSpec(BaseModel):
    """UI/UX Designer output, consumed by the Frontend Dev."""

    colors: dict[str, str] = Field(description="Token màu: brand, accent, surface, ink, muted (hex)")
    dark_colors: dict[str, str] = Field(default_factory=dict, description="Token màu cho giao diện tối")
    font_stack: str
    radius_px: int
    max_width_px: int
    sections: list[SectionDesign]
    notes: list[str] = Field(description="Ghi chú thiết kế cho Frontend Dev")


Tier = Literal["fast", "balanced", "premium"]

# Design features the Frontend Dev knows how to build and QA knows how to check.
FEATURES = {
    "responsive": "Responsive tới 360px",
    "sticky_nav": "Thanh điều hướng dính trên cùng",
    "dark_mode": "Tự đổi giao diện tối theo máy người xem",
    "animations": "Hiệu ứng xuất hiện nhẹ khi cuộn (CSS)",
    "faq_accordion": "Mục hỏi đáp dạng mở/đóng",
    "contact_form": "Form liên hệ lưu vào hệ thống (có backend API)",
    "seo_meta": "Meta description và Open Graph cho chia sẻ mạng xã hội",
}


class Option(BaseModel):
    """One way to deliver the project, for the boss to compare."""

    id: str = Field(description="Mã ngắn: A, B hoặc C")
    tier: Tier
    name: str = Field(description="Tên phương án, ví dụ Nhanh & rẻ")
    summary: str
    sections: list[Section] = Field(description="Các mục của trang theo phương án này, mục đầu là hero, có contact")
    features: list[str] = Field(description="Mã tính năng chọn từ danh sách cho phép")
    est_days: float = Field(description="Số ngày làm việc ước tính để bàn giao cho khách")
    est_price_vnd: int = Field(description="Giá đề xuất báo khách, VND")
    pros: list[str]
    cons: list[str]


class Proposal(BaseModel):
    """Solution Architect output: 2-3 options and a recommendation."""

    options: list[Option]
    recommended: str = Field(description="id của phương án khuyên chọn")
    reasoning: str = Field(description="Vì sao khuyên phương án đó, 1-2 câu")

    def get(self, option_id: str) -> Option | None:
        return next((o for o in self.options if o.id == option_id), None)


class FileOut(BaseModel):
    path: str = Field(description="Đường dẫn tương đối, ví dụ index.html")
    content: str


class CodeArtifact(BaseModel):
    """Frontend Dev output."""

    files: list[FileOut]
    notes: str = Field(description="Ghi chú ngắn cho QA / trưởng phòng")


Owner = Literal["frontend_dev", "backend_dev"]


class Check(BaseModel):
    name: str
    passed: bool
    detail: str = ""
    owner: Owner = "frontend_dev"


class QAReport(BaseModel):
    passed: bool
    checks: list[Check]

    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]


class Finding(BaseModel):
    severity: Literal["blocker", "major", "minor"]
    owner: Owner
    file: str
    rule: str
    message: str


class ReviewReport(BaseModel):
    """Reviewer output. Blockers and majors go back to the owning dev."""

    findings: list[Finding]

    @property
    def passed(self) -> bool:
        return not any(f.severity in ("blocker", "major") for f in self.findings)

    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.severity in ("blocker", "major")]


class FinalReport(BaseModel):
    """Báo cáo viên output, sent to the boss."""

    summary: str
    done: list[str]
    remaining: list[str]
    risks: list[str]
    decisions_needed: list[str]


class ClientMessage(BaseModel):
    """Báo cáo viên's message to the client. The boss edits and approves it before it is sent."""

    subject: str = Field(description="Tiêu đề email, dưới 120 ký tự")
    body: str = Field(description="Nội dung email gửi khách, văn bản thuần")


TaskStatus = Literal["pending", "running", "done", "failed", "blocked"]
