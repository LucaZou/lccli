from __future__ import annotations

import ast
import copy
import json
import re
from collections import deque
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Optional

from .client import LeetCodeError
from .models import Problem


class ListNode:
    def __init__(self, val: int = 0, next: Optional["ListNode"] = None):
        self.val = val
        self.next = next


class TreeNode:
    def __init__(
        self,
        val: int = 0,
        left: Optional["TreeNode"] = None,
        right: Optional["TreeNode"] = None,
    ):
        self.val = val
        self.left = left
        self.right = right


@dataclass
class ExampleCase:
    inputs: list[str]
    expected_output: str | None
    source: str


@dataclass
class CaseResult:
    ok: bool | None
    inputs: list[str]
    expected: Any
    actual: Any
    source: str


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "div", "section", "pre", "li", "ul", "ol"}:
            self.parts.append("\n")
        if tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "section", "pre", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    text = unescape(parser.text())
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_type(type_name: str | None) -> str:
    if not type_name:
        return ""
    return type_name.replace(" ", "")


def normalize_literal(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"\bnull\b", "None", raw)
    raw = re.sub(r"\btrue\b", "True", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\bfalse\b", "False", raw, flags=re.IGNORECASE)
    return raw


def parse_literal(raw: str) -> Any:
    try:
        return ast.literal_eval(normalize_literal(raw))
    except (SyntaxError, ValueError) as exc:
        raise LeetCodeError(f"failed to parse literal: {raw}") from exc


def build_list_node(values: list[Any]) -> ListNode | None:
    dummy = ListNode()
    current = dummy
    for value in values:
        current.next = ListNode(value)
        current = current.next
    return dummy.next


def serialize_list_node(node: ListNode | None) -> list[Any]:
    out: list[Any] = []
    while node is not None:
        out.append(node.val)
        node = node.next
    return out


def build_tree(values: list[Any]) -> TreeNode | None:
    if not values:
        return None
    if values[0] is None:
        return None
    root = TreeNode(values[0])
    queue: deque[TreeNode] = deque([root])
    index = 1
    while queue and index < len(values):
        node = queue.popleft()
        if index < len(values) and values[index] is not None:
            node.left = TreeNode(values[index])
            queue.append(node.left)
        index += 1
        if index < len(values) and values[index] is not None:
            node.right = TreeNode(values[index])
            queue.append(node.right)
        index += 1
    return root


def serialize_tree(root: TreeNode | None) -> list[Any]:
    if root is None:
        return []
    out: list[Any] = []
    queue: deque[TreeNode | None] = deque([root])
    while queue:
        node = queue.popleft()
        if node is None:
            out.append(None)
            continue
        out.append(node.val)
        queue.append(node.left)
        queue.append(node.right)
    while out and out[-1] is None:
        out.pop()
    return out


def deserialize_value(raw: str, type_name: str | None) -> Any:
    normalized = normalize_type(type_name)
    lower = normalized.lower()
    if normalized == "ListNode":
        return build_list_node(parse_literal(raw))
    if normalized == "TreeNode":
        return build_tree(parse_literal(raw))
    if lower in {"integer", "int", "long"}:
        return int(parse_literal(raw))
    if lower in {"float", "double"}:
        return float(parse_literal(raw))
    if lower in {"boolean", "bool"}:
        return bool(parse_literal(raw))
    if lower in {"string", "char", "character"}:
        value = raw.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            return parse_literal(value)
        return value
    if normalized.endswith("[]") or normalized.startswith("List[") or "[]" in normalized:
        return parse_literal(raw)
    if not normalized:
        return parse_literal(raw)
    return parse_literal(raw)


def serialize_value(value: Any) -> Any:
    if isinstance(value, ListNode):
        return serialize_list_node(value)
    if isinstance(value, TreeNode):
        return serialize_tree(value)
    if isinstance(value, tuple):
        return [serialize_value(item) for item in value]
    if isinstance(value, list):
        return [serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_value(item) for key, item in value.items()}
    return value


def clone_value(value: Any) -> Any:
    if isinstance(value, ListNode):
        return build_list_node(serialize_list_node(value))
    if isinstance(value, TreeNode):
        return build_tree(serialize_tree(value))
    return copy.deepcopy(value)


def split_top_level(raw: str, delimiter: str = ",") -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    quote: str | None = None
    escaped = False
    for char in raw:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if quote:
            current.append(char)
            if char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            current.append(char)
            continue
        if char in "([{":
            depth += 1
            current.append(char)
            continue
        if char in ")]}":
            depth = max(depth - 1, 0)
            current.append(char)
            continue
        if char == delimiter and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(char)
    part = "".join(current).strip()
    if part:
        parts.append(part)
    return parts


def parse_named_input(raw: str, param_names: list[str]) -> list[str]:
    if len(param_names) == 1 and "=" not in raw:
        return [raw.strip()]
    tokens = split_top_level(raw)
    values_by_name: dict[str, str] = {}
    ordered_values: list[str] = []
    for token in tokens:
        if "=" not in token:
            ordered_values.append(token.strip())
            continue
        name, value = token.split("=", 1)
        values_by_name[name.strip()] = value.strip()
    if values_by_name:
        missing = [name for name in param_names if name not in values_by_name]
        if missing:
            raise LeetCodeError(f"failed to parse sample input, missing params: {', '.join(missing)}")
        return [values_by_name[name] for name in param_names]
    return ordered_values


def parse_raw_testcase(raw: str, param_count: int) -> list[list[str]]:
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return []
    if param_count <= 1:
        return [[line] for line in lines]
    if len(lines) % param_count != 0:
        raise LeetCodeError(f"testcase line count {len(lines)} does not match param count {param_count}")
    return [lines[index : index + param_count] for index in range(0, len(lines), param_count)]


def extract_example_cases(problem: Problem, meta: dict) -> list[ExampleCase]:
    param_names = [param["name"] for param in meta.get("params", [])]
    text = html_to_text(problem.content)
    blocks = re.findall(r"((?:示例|Example)\s*\d+\s*[:：].*?)(?=(?:示例|Example)\s*\d+\s*[:：]|$)", text, flags=re.S)
    cases: list[ExampleCase] = []
    for block in blocks:
        input_match = re.search(r"(?:输入|Input)\s*[:：]\s*(.*?)(?=(?:输出|Output)\s*[:：]|$)", block, flags=re.S)
        output_match = re.search(
            r"(?:输出|Output)\s*[:：]\s*(.*?)(?=(?:解释|Explanation|提示|Constraints|进阶|$))",
            block,
            flags=re.S,
        )
        if not input_match:
            continue
        inputs = parse_named_input(input_match.group(1).strip(), param_names)
        output = output_match.group(1).strip() if output_match else None
        cases.append(ExampleCase(inputs=inputs, expected_output=output, source="example"))
    if cases:
        return cases

    fallback_inputs = parse_raw_testcase(problem.example_testcases or problem.sample_test_case, len(param_names))
    return [ExampleCase(inputs=item, expected_output=None, source="sample") for item in fallback_inputs]


def parse_problem_meta(problem: Problem) -> dict:
    if not problem.meta_data:
        raise LeetCodeError("problem metadata is missing")
    try:
        meta = json.loads(problem.meta_data)
    except json.JSONDecodeError as exc:
        raise LeetCodeError("problem metadata is invalid JSON") from exc
    if "name" not in meta or "params" not in meta:
        raise LeetCodeError("unsupported metadata shape for local test")
    return meta


def make_exec_namespace() -> dict[str, Any]:
    from collections import Counter, defaultdict, deque as typing_deque
    from functools import cache, lru_cache
    from heapq import heapify, heappop, heappush
    from itertools import accumulate, combinations, permutations, product
    from math import ceil, comb, floor, gcd, inf, isqrt, lcm, sqrt
    from typing import Dict, List, Optional, Set, Tuple

    return {
        "__builtins__": __builtins__,
        "Counter": Counter,
        "defaultdict": defaultdict,
        "deque": typing_deque,
        "cache": cache,
        "lru_cache": lru_cache,
        "heapify": heapify,
        "heappop": heappop,
        "heappush": heappush,
        "accumulate": accumulate,
        "combinations": combinations,
        "permutations": permutations,
        "product": product,
        "ceil": ceil,
        "comb": comb,
        "floor": floor,
        "gcd": gcd,
        "inf": inf,
        "isqrt": isqrt,
        "lcm": lcm,
        "sqrt": sqrt,
        "Dict": Dict,
        "List": List,
        "Optional": Optional,
        "Set": Set,
        "Tuple": Tuple,
        "ListNode": ListNode,
        "TreeNode": TreeNode,
    }


def load_solution_callable(code: str, meta: dict) -> Any:
    namespace = make_exec_namespace()
    exec(code, namespace)
    class_name = meta.get("classname") or "Solution"
    method_name = meta.get("name")
    if not method_name:
        raise LeetCodeError("unsupported metadata: missing method name")
    solution_cls = namespace.get(class_name)
    if solution_cls is None:
        raise LeetCodeError(f"solution class not found: {class_name}")
    instance = solution_cls()
    if not hasattr(instance, method_name):
        raise LeetCodeError(f"solution method not found: {class_name}.{method_name}")

    def invoke(*args: Any) -> Any:
        fresh = solution_cls()
        return getattr(fresh, method_name)(*args)

    return invoke


def parse_cases(problem: Problem, meta: dict, raw_testcase: str | None, expected_output: str | None) -> list[ExampleCase]:
    param_count = len(meta.get("params", []))
    if raw_testcase is not None:
        parsed = parse_raw_testcase(raw_testcase, param_count)
        return [
            ExampleCase(inputs=inputs, expected_output=expected_output, source="manual")
            for inputs in parsed
        ]
    return extract_example_cases(problem, meta)


def evaluate_case(callable_obj: Any, meta: dict, case: ExampleCase) -> CaseResult:
    params = meta.get("params", [])
    values = [deserialize_value(raw, param.get("type")) for raw, param in zip(case.inputs, params)]
    invoke_args = [clone_value(value) for value in values]
    result = callable_obj(*invoke_args)

    return_type = normalize_type(meta.get("return", {}).get("type"))
    if return_type.lower() in {"void", "none", "null"}:
        comparable = serialize_value(invoke_args[0]) if invoke_args else None
        expected = (
            deserialize_value(case.expected_output, params[0].get("type"))
            if case.expected_output is not None and params
            else None
        )
    else:
        comparable = serialize_value(result)
        expected = (
            deserialize_value(case.expected_output, meta.get("return", {}).get("type"))
            if case.expected_output is not None
            else None
        )

    actual = serialize_value(comparable)
    expected_serialized = serialize_value(expected) if case.expected_output is not None else None
    ok = None if case.expected_output is None else actual == expected_serialized
    return CaseResult(
        ok=ok,
        inputs=case.inputs,
        expected=expected_serialized,
        actual=actual,
        source=case.source,
    )


def load_problem_from_cache(file_path: Path) -> Problem | None:
    problem_file = file_path.parent / "problem.json"
    if not problem_file.exists():
        return None
    data = json.loads(problem_file.read_text(encoding="utf-8"))
    return Problem.from_dict(data)
