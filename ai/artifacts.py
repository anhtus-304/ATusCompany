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
