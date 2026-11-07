"""Structured artifacts that agents hand to each other.

Agents never talk in free-form chat. Each stage reads the previous stage's
artifact and produces its own, validated by these Pydantic models.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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


Tier = Literal["fast", "balanced", "premium"]

# Design features the Frontend Dev knows how to build and QA knows how to check.
FEATURES = {
    "responsive": "Responsive tới 360px",
    "sticky_nav": "Thanh điều hướng dính trên cùng",
    "dark_mode": "Tự đổi giao diện tối theo máy người xem",
    "animations": "Hiệu ứng xuất hiện nhẹ khi cuộn (CSS)",
    "faq_accordion": "Mục hỏi đáp dạng mở/đóng",
    "contact_form": "Form liên hệ gửi qua email (mailto)",
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


class Check(BaseModel):
    name: str
    passed: bool
    detail: str = ""


class QAReport(BaseModel):
    passed: bool
    checks: list[Check]

    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]


class FinalReport(BaseModel):
    """Báo cáo viên output, sent to the boss."""

    summary: str
    done: list[str]
    remaining: list[str]
    risks: list[str]
    decisions_needed: list[str]


TaskStatus = Literal["pending", "running", "done", "failed", "blocked"]
