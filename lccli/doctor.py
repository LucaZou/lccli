from __future__ import annotations

import shutil
from dataclasses import dataclass, asdict


@dataclass
class ToolStatus:
    name: str
    found: bool
    path: str | None


@dataclass
class LanguageStatus:
    lang: str
    local_test_supported: bool
    available: bool
    tools: list[ToolStatus]
    notes: str

    def to_dict(self) -> dict:
        data = asdict(self)
        return data


LANGUAGE_TOOLING: dict[str, dict] = {
    "python3": {
        "tools": [("python3", "python3")],
        "local_test_supported": True,
        "notes": "Current local test implementation is available for python3.",
    },
    "cpp": {
        "tools": [("g++", "g++"), ("clang++", "clang++")],
        "local_test_supported": True,
        "notes": "Current local test supports common LeetCode-style C++ solutions with g++ or clang++.",
    },
    "java": {
        "tools": [("javac", "javac"), ("java", "java")],
        "local_test_supported": False,
        "notes": "Both javac and java are typically required.",
    },
    "golang": {
        "tools": [("go", "go")],
        "local_test_supported": False,
        "notes": "Go local execution would typically rely on the go toolchain.",
    },
    "javascript": {
        "tools": [("node", "node")],
        "local_test_supported": False,
        "notes": "JavaScript local execution would typically rely on node.",
    },
    "typescript": {
        "tools": [("node", "node"), ("tsc", "tsc")],
        "local_test_supported": False,
        "notes": "TypeScript usually needs node plus a compiler such as tsc.",
    },
    "rust": {
        "tools": [("rustc", "rustc"), ("cargo", "cargo")],
        "local_test_supported": False,
        "notes": "Rust local execution would typically rely on rustc or cargo.",
    },
}


def _tool_status(tool_name: str) -> ToolStatus:
    path = shutil.which(tool_name)
    return ToolStatus(name=tool_name, found=path is not None, path=path)


def inspect_language(lang: str) -> LanguageStatus:
    spec = LANGUAGE_TOOLING[lang]
    tool_groups = spec["tools"]
    statuses = [_tool_status(tool_name) for _, tool_name in tool_groups]
    if lang == "cpp":
        available = any(status.found for status in statuses)
    else:
        available = all(status.found for status in statuses)
    return LanguageStatus(
        lang=lang,
        local_test_supported=spec["local_test_supported"],
        available=available,
        tools=statuses,
        notes=spec["notes"],
    )


def inspect_all_languages() -> list[LanguageStatus]:
    return [inspect_language(lang) for lang in LANGUAGE_TOOLING]
