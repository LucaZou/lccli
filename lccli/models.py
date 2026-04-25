from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass


@dataclass
class Problem:
    question_id: str
    frontend_id: str
    title: str
    title_slug: str
    difficulty: str
    content: str
    content_zh: str
    content_en: str
    sample_test_case: str
    example_testcases: str
    meta_data: str
    code_snippets: list[dict]

    @property
    def dir_name(self) -> str:
        return f"{self.frontend_id.zfill(4)}-{self.title_slug}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Problem":
        content_zh = data.get("content_zh")
        content_en = data.get("content_en")
        legacy_content = data.get("content", "")
        return cls(
            question_id=data["question_id"],
            frontend_id=data["frontend_id"],
            title=data["title"],
            title_slug=data["title_slug"],
            difficulty=data["difficulty"],
            content=content_zh or content_en or legacy_content,
            content_zh=content_zh or legacy_content,
            content_en=content_en or legacy_content,
            sample_test_case=data.get("sample_test_case", ""),
            example_testcases=data.get("example_testcases", ""),
            meta_data=data.get("meta_data", ""),
            code_snippets=data.get("code_snippets", []),
        )
