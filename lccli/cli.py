from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .client import LeetCodeClient, LeetCodeError, parse_cookie_string, slug_from_input
from .config import CONFIG_FILE, Config
from .files import write_problem_files
from .local_test import (
    evaluate_case,
    load_problem_from_cache,
    load_solution_callable,
    parse_cases,
    parse_problem_meta,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lccli", description="LeetCode CN CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="Store session cookies")
    login.add_argument("--cookie", help="Raw Cookie header string")
    login.add_argument("--cookie-file", help="File containing raw Cookie header string")
    login.add_argument("--base-url", default="https://leetcode.cn")

    sub.add_parser("whoami", help="Show current login status")

    fetch = sub.add_parser("fetch", help="Fetch a problem and create local files")
    fetch.add_argument("slug", help="Problem slug or problem URL")
    fetch.add_argument("--lang", help="Language slug, for example python3")
    fetch.add_argument("--workspace", help="Output directory")

    run = sub.add_parser("run", help="Run code on LeetCode")
    run.add_argument("slug", help="Problem slug or URL")
    run.add_argument("--file", required=True, help="Solution file path")
    run.add_argument("--lang", help="Language slug")
    run.add_argument("--testcase", help="Raw testcase text")
    run.add_argument("--testcase-file", help="Path to testcase file")
    run.add_argument("--timeout", type=float, default=60.0)

    test = sub.add_parser("test", help="Run sample cases locally before remote submit")
    test.add_argument("slug", help="Problem slug or URL")
    test.add_argument("--file", required=True, help="Solution file path")
    test.add_argument("--lang", help="Language slug")
    test.add_argument("--testcase", help="Raw testcase text for local execution")
    test.add_argument("--testcase-file", help="Path to testcase file")
    test.add_argument("--expected", help="Expected output for manual testcase")

    submit = sub.add_parser("submit", help="Submit code to LeetCode")
    submit.add_argument("slug", help="Problem slug or URL")
    submit.add_argument("--file", required=True, help="Solution file path")
    submit.add_argument("--lang", help="Language slug")
    submit.add_argument("--timeout", type=float, default=60.0)

    langs = sub.add_parser("langs", help="List supported remote languages")
    langs.add_argument("--json", action="store_true")

    config = sub.add_parser("config", help="Show config path or current config")
    config.add_argument("--path", action="store_true")

    return parser


def load_cookie_arg(args: argparse.Namespace) -> str:
    if args.cookie:
        return args.cookie
    if args.cookie_file:
        return Path(args.cookie_file).read_text(encoding="utf-8").strip()
    raise SystemExit("login requires --cookie or --cookie-file")


def infer_lang(path: Path, explicit: str | None, default_lang: str) -> str:
    if explicit:
        return explicit
    suffix_map = {
        ".py": "python3",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".java": "java",
        ".go": "golang",
        ".js": "javascript",
        ".ts": "typescript",
        ".rs": "rust",
    }
    return suffix_map.get(path.suffix, default_lang)


def load_testcase(args: argparse.Namespace, sample: str) -> str:
    if args.testcase:
        return args.testcase
    if args.testcase_file:
        return Path(args.testcase_file).read_text(encoding="utf-8")
    return sample


def resolve_problem(config: Config, slug: str, file_path: Path):
    cached = load_problem_from_cache(file_path)
    if cached and cached.title_slug == slug:
        return cached
    client = LeetCodeClient(config)
    return client.question_by_slug(slug)


def cmd_login(args: argparse.Namespace) -> int:
    config = Config.load()
    config.base_url = args.base_url
    config.cookies = parse_cookie_string(load_cookie_arg(args))
    client = LeetCodeClient(config)
    status = client.user_status()
    if not status.get("isSignedIn"):
        raise SystemExit("cookie is not valid or session is not signed in")
    config.save()
    print(f"logged in as {status.get('username')}")
    print(f"config saved to {CONFIG_FILE}")
    return 0


def cmd_whoami(_: argparse.Namespace) -> int:
    config = Config.load()
    client = LeetCodeClient(config)
    status = client.user_status()
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    config = Config.load()
    client = LeetCodeClient(config)
    slug = slug_from_input(args.slug)
    lang = args.lang or config.default_lang
    workspace = Path(args.workspace or config.workspace).resolve()
    problem = client.question_by_slug(slug)
    statement_path, solution_path = write_problem_files(workspace, problem, lang)
    print(statement_path)
    print(solution_path)
    return 0


def print_result(result: dict) -> None:
    interesting = {
        "state": result.get("state"),
        "status_code": result.get("status_code"),
        "status_msg": result.get("status_msg"),
        "run_success": result.get("run_success"),
        "status_runtime": result.get("status_runtime"),
        "memory": result.get("memory"),
        "total_correct": result.get("total_correct"),
        "total_testcases": result.get("total_testcases"),
        "compare_result": result.get("compare_result"),
        "expected_output": result.get("expected_output"),
        "code_output": result.get("code_output"),
        "std_output": result.get("std_output"),
        "last_testcase": result.get("last_testcase"),
        "compile_error": result.get("compile_error"),
        "runtime_error": result.get("runtime_error"),
        "full_compile_error": result.get("full_compile_error"),
    }
    print(json.dumps(interesting, ensure_ascii=False, indent=2))


def cmd_run(args: argparse.Namespace) -> int:
    config = Config.load()
    client = LeetCodeClient(config)
    slug = slug_from_input(args.slug)
    file_path = Path(args.file)
    lang = infer_lang(file_path, args.lang, config.default_lang)
    code = file_path.read_text(encoding="utf-8")
    sample = client.question_by_slug(slug).sample_test_case
    testcase = load_testcase(args, sample)
    run_id = client.run_code(slug, lang, code, testcase)
    result = client.poll_check(run_id, timeout=args.timeout)
    print_result(result.raw)
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    config = Config.load()
    file_path = Path(args.file)
    lang = infer_lang(file_path, args.lang, config.default_lang)
    if lang != "python3":
        raise SystemExit("local test currently supports python3 only")

    slug = slug_from_input(args.slug)
    problem = resolve_problem(config, slug, file_path)
    meta = parse_problem_meta(problem)
    code = file_path.read_text(encoding="utf-8")
    testcase = load_testcase(args, "") if (args.testcase or args.testcase_file) else None
    cases = parse_cases(problem, meta, testcase, args.expected)
    if not cases:
        raise SystemExit("no local testcases available")

    callable_obj = load_solution_callable(code, meta)
    results = [evaluate_case(callable_obj, meta, case) for case in cases]

    failed = False
    for index, result in enumerate(results, start=1):
        status = "PASS" if result.ok is True else "FAIL" if result.ok is False else "DONE"
        print(f"[{status}] case {index} ({result.source})")
        print("inputs:")
        for value in result.inputs:
            print(value)
        print("actual:")
        print(json.dumps(result.actual, ensure_ascii=False))
        if result.expected is not None:
            print("expected:")
            print(json.dumps(result.expected, ensure_ascii=False))
        print()
        failed = failed or result.ok is False
    return 1 if failed else 0


def cmd_submit(args: argparse.Namespace) -> int:
    config = Config.load()
    client = LeetCodeClient(config)
    slug = slug_from_input(args.slug)
    file_path = Path(args.file)
    lang = infer_lang(file_path, args.lang, config.default_lang)
    code = file_path.read_text(encoding="utf-8")
    submission_id = client.submit_code(slug, lang, code)
    result = client.poll_check(submission_id, timeout=args.timeout)
    print_result(result.raw)
    return 0


def cmd_langs(args: argparse.Namespace) -> int:
    config = Config.load()
    client = LeetCodeClient(config)
    languages = client.language_list()
    if args.json:
        print(json.dumps(languages, ensure_ascii=False, indent=2))
        return 0
    for item in languages:
        print(f"{item['name']}\t{item['id']}\t{item.get('verboseName', '')}")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    if args.path:
        print(CONFIG_FILE)
        return 0
    config = Config.load()
    print(json.dumps(config.__dict__, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "login": cmd_login,
        "whoami": cmd_whoami,
        "fetch": cmd_fetch,
        "run": cmd_run,
        "test": cmd_test,
        "submit": cmd_submit,
        "langs": cmd_langs,
        "config": cmd_config,
    }
    try:
        return handlers[args.command](args)
    except LeetCodeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
