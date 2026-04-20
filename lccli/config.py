from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_BASE_URL = "https://leetcode.cn"
CONFIG_DIR = Path.home() / ".config" / "lccli"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Config:
    base_url: str = DEFAULT_BASE_URL
    cookies: dict[str, str] = field(default_factory=dict)
    default_lang: str = "python3"
    workspace: str = "."

    @classmethod
    def load(cls) -> "Config":
        if not CONFIG_FILE.exists():
            return cls()
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return cls(
            base_url=data.get("base_url", DEFAULT_BASE_URL),
            cookies=data.get("cookies", {}),
            default_lang=data.get("default_lang", "python3"),
            workspace=data.get("workspace", "."),
        )

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "base_url": self.base_url,
            "cookies": self.cookies,
            "default_lang": self.default_lang,
            "workspace": self.workspace,
        }
        CONFIG_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

