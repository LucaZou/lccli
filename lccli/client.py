from __future__ import annotations

import json
import time
from dataclasses import dataclass
from urllib import error, parse, request

from .config import Config
from .models import Problem


USER_AGENT = "lccli/0.1 (+https://leetcode.cn)"


class LeetCodeError(RuntimeError):
    pass


@dataclass
class RunResult:
    state: str
    status_msg: str
    status_code: int | None
    run_success: bool | None
    raw: dict


class LeetCodeClient:
    def __init__(self, config: Config):
        self.config = config

    @property
    def base_url(self) -> str:
        return self.config.base_url.rstrip("/")

    def _cookie_header(self) -> str:
        return "; ".join(f"{key}={value}" for key, value in self.config.cookies.items())

    def _headers(self, referer: str | None = None, json_body: bool = True) -> dict[str, str]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Origin": self.base_url,
        }
        if json_body:
            headers["Content-Type"] = "application/json"
        if referer:
            headers["Referer"] = referer
        if self.config.cookies:
            headers["Cookie"] = self._cookie_header()
        csrf = self.config.cookies.get("csrftoken")
        if csrf:
            headers["x-csrftoken"] = csrf
            headers["X-CSRFToken"] = csrf
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict | None = None,
        referer: str | None = None,
        json_body: bool = True,
    ) -> dict:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=url,
            data=data,
            method=method,
            headers=self._headers(referer=referer, json_body=json_body),
        )
        try:
            with request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise LeetCodeError(f"HTTP {exc.code} for {url}: {raw}") from exc
        except error.URLError as exc:
            raise LeetCodeError(f"Request failed for {url}: {exc}") from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LeetCodeError(f"Invalid JSON from {url}: {raw[:300]}") from exc

    def graphql(self, query: str, variables: dict | None = None) -> dict:
        data = self._request(
            "POST",
            "/graphql/",
            payload={"query": query, "variables": variables or {}},
            referer=f"{self.base_url}/",
        )
        if data.get("errors"):
            raise LeetCodeError(f"GraphQL error: {data['errors']}")
        return data["data"]

    def user_status(self) -> dict:
        query = """
        query userStatus {
          userStatus {
            isSignedIn
            username
            realName
          }
        }
        """
        return self.graphql(query)["userStatus"]

    def question_by_slug(self, title_slug: str) -> Problem:
        query = """
        query questionData($titleSlug: String!) {
          question(titleSlug: $titleSlug) {
            questionId
            questionFrontendId
            title
            titleSlug
            difficulty
            translatedContent
            content
            sampleTestCase
            exampleTestcases
            metaData
            codeSnippets {
              lang
              langSlug
              code
            }
          }
        }
        """
        question = self.graphql(query, {"titleSlug": title_slug})["question"]
        if not question:
            raise LeetCodeError(f"Question not found: {title_slug}")
        return Problem(
            question_id=question["questionId"],
            frontend_id=question["questionFrontendId"],
            title=question["title"],
            title_slug=question["titleSlug"],
            difficulty=question["difficulty"],
            content=question.get("translatedContent") or question.get("content") or "",
            content_zh=question.get("translatedContent") or "",
            content_en=question.get("content") or "",
            sample_test_case=question.get("sampleTestCase") or "",
            example_testcases=question.get("exampleTestcases") or "",
            meta_data=question.get("metaData") or "",
            code_snippets=question.get("codeSnippets") or [],
        )

    def language_list(self) -> list[dict]:
        query = """
        query languageList {
          languageList {
            id
            name
            verboseName
          }
        }
        """
        return self.graphql(query)["languageList"]

    def _post_problem_action(self, title_slug: str, action: str, payload: dict) -> dict:
        referer = f"{self.base_url}/problems/{title_slug}/description/"
        return self._request(
            "POST",
            f"/problems/{title_slug}/{action}/",
            payload=payload,
            referer=referer,
        )

    def run_code(self, title_slug: str, lang: str, code: str, testcase: str) -> str:
        data = self._post_problem_action(
            title_slug,
            "interpret_solution",
            {
                "lang": lang,
                "question_id": self.question_by_slug(title_slug).question_id,
                "typed_code": code,
                "data_input": testcase,
            },
        )
        interpretation_id = data.get("interpret_id") or data.get("interpretId")
        if not interpretation_id:
            raise LeetCodeError(f"Unexpected run response: {data}")
        return str(interpretation_id)

    def submit_code(self, title_slug: str, lang: str, code: str) -> int:
        data = self._post_problem_action(
            title_slug,
            "submit",
            {
                "lang": lang,
                "question_id": self.question_by_slug(title_slug).question_id,
                "typed_code": code,
            },
        )
        submission_id = data.get("submission_id")
        if not submission_id:
            raise LeetCodeError(f"Unexpected submit response: {data}")
        return int(submission_id)

    def poll_check(self, submission_id: int | str, *, interval: float = 1.0, timeout: float = 60.0) -> RunResult:
        deadline = time.time() + timeout
        last = {}
        while time.time() < deadline:
            data = self._request(
                "GET",
                f"/submissions/detail/{submission_id}/check/",
                referer=f"{self.base_url}/",
                json_body=False,
            )
            last = data
            state = data.get("state")
            if state == "SUCCESS":
                return RunResult(
                    state=state,
                    status_msg=data.get("status_msg", ""),
                    status_code=data.get("status_code"),
                    run_success=data.get("run_success"),
                    raw=data,
                )
            if state not in (None, "PENDING", "STARTED"):
                return RunResult(
                    state=state,
                    status_msg=data.get("status_msg", ""),
                    status_code=data.get("status_code"),
                    run_success=data.get("run_success"),
                    raw=data,
                )
            time.sleep(interval)
        raise LeetCodeError(f"Timed out waiting for result: {last}")


def parse_cookie_string(raw: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for chunk in raw.split(";"):
        part = chunk.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        cookies[key.strip()] = value.strip()
    return cookies


def slug_from_input(value: str) -> str:
    value = value.strip()
    if "/problems/" in value:
        parsed = parse.urlparse(value)
        parts = [part for part in parsed.path.split("/") if part]
        if "problems" in parts:
            idx = parts.index("problems")
            if idx + 1 < len(parts):
                return parts[idx + 1]
    return value
