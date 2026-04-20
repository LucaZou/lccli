from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Problem:
    question_id: str
    frontend_id: str
    title: str
    title_slug: str
    difficulty: str
    content: str
    sample_test_case: str
    example_testcases: str
    meta_data: str
    code_snippets: list[dict]

    @property
    def dir_name(self) -> str:
        return f"{self.frontend_id.zfill(4)}-{self.title_slug}"

