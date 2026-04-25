from __future__ import annotations

import html
import json
import re
from pathlib import Path

from .models import Problem


def sanitize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip()


def problem_dir(workspace: Path, problem: Problem) -> Path:
    return workspace / problem.dir_name


def starter_code(problem: Problem, lang_slug: str) -> str:
    for snippet in problem.code_snippets:
        if snippet.get("langSlug") == lang_slug:
            return snippet.get("code", "")
    available = ", ".join(snippet.get("langSlug", "?") for snippet in problem.code_snippets)
    raise ValueError(f"Language not available. Requested={lang_slug}, available={available}")


def write_problem_files(workspace: Path, problem: Problem, lang_slug: str) -> tuple[Path, Path]:
    target_dir = problem_dir(workspace, problem)
    target_dir.mkdir(parents=True, exist_ok=True)

    statement_path = target_dir / "README.md"
    metadata_path = target_dir / "problem.json"
    solution_name = default_solution_name(lang_slug)
    solution_path = target_dir / solution_name

    statement = render_problem_markdown(problem)
    statement_path.write_text(statement, encoding="utf-8")
    metadata_path.write_text(
        json.dumps(problem.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if not solution_path.exists():
        solution_path.write_text(starter_code(problem, lang_slug), encoding="utf-8")
    return statement_path, solution_path


def render_problem_markdown(problem: Problem) -> str:
    meta_block = ""
    if problem.meta_data:
        try:
            parsed = json.loads(problem.meta_data)
            meta_block = "```json\n" + json.dumps(parsed, ensure_ascii=False, indent=2) + "\n```\n\n"
        except json.JSONDecodeError:
            meta_block = "```json\n" + problem.meta_data + "\n```\n\n"

    return (
        f"# {problem.frontend_id}. {sanitize_title(problem.title)}\n\n"
        f"- 标题 Slug: `{problem.title_slug}`\n"
        f"- 难度: `{problem.difficulty}`\n"
        f"- 链接: https://leetcode.cn/problems/{problem.title_slug}/description/\n\n"
        "## 题面\n\n"
        f"{html.unescape(problem.content)}\n\n"
        "## 示例测试用例\n\n"
        "```text\n"
        f"{problem.example_testcases or problem.sample_test_case}\n"
        "```\n\n"
        "## 默认测试用例\n\n"
        "```text\n"
        f"{problem.sample_test_case}\n"
        "```\n\n"
        "## 元数据\n\n"
        f"{meta_block}"
    )


def default_solution_name(lang_slug: str) -> str:
    mapping = {
        "python3": "solution.py",
        "python": "solution.py",
        "cpp": "solution.cpp",
        "java": "Solution.java",
        "golang": "solution.go",
        "javascript": "solution.js",
        "typescript": "solution.ts",
        "rust": "solution.rs",
    }
    return mapping.get(lang_slug, f"solution.{lang_slug}")
