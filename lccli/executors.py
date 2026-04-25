from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .client import LeetCodeError
from .local_test import (
    CaseResult,
    ExampleCase,
    ListNode,
    TreeNode,
    build_case_result,
    clone_value,
    deserialize_case_inputs,
    evaluate_case,
    load_solution_callable,
    serialize_list_node,
    serialize_tree,
)


class LocalExecutor(Protocol):
    lang: str

    def run_cases(self, code: str, meta: dict, cases: list[ExampleCase]) -> list[CaseResult]:
        ...


@dataclass
class PythonExecutor:
    lang: str = "python3"

    def run_cases(self, code: str, meta: dict, cases: list[ExampleCase]) -> list[CaseResult]:
        callable_obj = load_solution_callable(code, meta)
        return [evaluate_case(callable_obj, meta, case) for case in cases]


@dataclass
class CppExecutor:
    lang: str = "cpp"

    def run_cases(self, code: str, meta: dict, cases: list[ExampleCase]) -> list[CaseResult]:
        compiler = shutil.which("g++") or shutil.which("clang++")
        if not compiler:
            raise LeetCodeError("missing local runtime: g++ or clang++")

        source = self._render_source(code, meta, cases)
        with tempfile.TemporaryDirectory(prefix="lccli-cpp-") as tmp:
            tmp_path = Path(tmp)
            source_path = tmp_path / "runner.cpp"
            binary_path = tmp_path / "runner"
            source_path.write_text(source, encoding="utf-8")

            compile_proc = subprocess.run(
                [compiler, "-std=c++17", "-O2", str(source_path), "-o", str(binary_path)],
                capture_output=True,
                text=True,
            )
            if compile_proc.returncode != 0:
                details = compile_proc.stderr.strip() or compile_proc.stdout.strip()
                raise LeetCodeError(f"cpp compile failed:\n{details}")

            run_proc = subprocess.run(
                [str(binary_path)],
                capture_output=True,
                text=True,
            )
            if run_proc.returncode != 0:
                details = run_proc.stderr.strip() or run_proc.stdout.strip()
                raise LeetCodeError(f"cpp execution failed:\n{details}")

        lines = [line for line in run_proc.stdout.splitlines() if line.strip()]
        if len(lines) != len(cases):
            raise LeetCodeError(
                f"cpp executor produced {len(lines)} result lines for {len(cases)} cases"
            )

        actual_values = [self._parse_output_line(line) for line in lines]
        return [build_case_result(meta, case, actual) for case, actual in zip(cases, actual_values)]

    def _parse_output_line(self, raw: str) -> Any:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LeetCodeError(f"failed to parse cpp output: {raw}") from exc

    def _render_source(self, code: str, meta: dict, cases: list[ExampleCase]) -> str:
        method_name = meta.get("name")
        class_name = meta.get("classname") or "Solution"
        if not method_name:
            raise LeetCodeError("unsupported metadata: missing method name")
        params = meta.get("params", [])
        return_type = (meta.get("return") or {}).get("type")
        support_code = self._support_code(include_list=self._needs_list_node(meta), include_tree=self._needs_tree_node(meta))
        cases_code = "\n".join(
            self._render_case_block(case, params, return_type, class_name, method_name)
            for case in cases
        )
        return (
            "#include <bits/stdc++.h>\n"
            "using namespace std;\n\n"
            f"{support_code}\n"
            f"{code}\n\n"
            "int main() {\n"
            f"{cases_code}\n"
            "    return 0;\n"
            "}\n"
        )

    def _support_code(self, *, include_list: bool, include_tree: bool) -> str:
        parts: list[str] = [
            "static string lccli_escape_json(const string& value) {",
            '    string out = "\\"";',
            "    for (char ch : value) {",
            "        switch (ch) {",
            "            case '\\\\': out += \"\\\\\\\\\"; break;",
            "            case '\"': out += \"\\\\\\\"\"; break;",
            "            case '\\n': out += \"\\\\n\"; break;",
            "            case '\\r': out += \"\\\\r\"; break;",
            "            case '\\t': out += \"\\\\t\"; break;",
            "            default: out += ch; break;",
            "        }",
            "    }",
            '    out += "\\"";',
            "    return out;",
            "}",
            "",
            "static string lccli_to_json(const string& value) { return lccli_escape_json(value); }",
            "static string lccli_to_json(const char* value) { return lccli_escape_json(string(value)); }",
            "static string lccli_to_json(char value) { return lccli_escape_json(string(1, value)); }",
            "static string lccli_to_json(bool value) { return value ? \"true\" : \"false\"; }",
            "",
            "template <typename T>",
            "static typename enable_if<is_integral<T>::value && !is_same<T, bool>::value, string>::type",
            "lccli_to_json(T value) {",
            "    return to_string(value);",
            "}",
            "",
            "template <typename T>",
            "static typename enable_if<is_floating_point<T>::value, string>::type",
            "lccli_to_json(T value) {",
            "    ostringstream out;",
            "    out << value;",
            "    return out.str();",
            "}",
            "",
            "template <typename T>",
            "static string lccli_to_json(const vector<T>& values) {",
            '    string out = "[";',
            "    for (size_t i = 0; i < values.size(); ++i) {",
            '        if (i) out += ",";',
            "        out += lccli_to_json(values[i]);",
            "    }",
            '    out += "]";',
            "    return out;",
            "}",
            "",
        ]
        if include_list:
            parts.extend(
                [
                    "struct ListNode {",
                    "    int val;",
                    "    ListNode* next;",
                    "    ListNode() : val(0), next(nullptr) {}",
                    "    ListNode(int x) : val(x), next(nullptr) {}",
                    "    ListNode(int x, ListNode* next_node) : val(x), next(next_node) {}",
                    "};",
                    "",
                    "static ListNode* lccli_build_list_node(const vector<int>& values) {",
                    "    ListNode dummy;",
                    "    ListNode* current = &dummy;",
                    "    for (int value : values) {",
                    "        current->next = new ListNode(value);",
                    "        current = current->next;",
                    "    }",
                    "    return dummy.next;",
                    "}",
                    "",
                    "static vector<int> lccli_serialize_list_node(ListNode* node) {",
                    "    vector<int> out;",
                    "    while (node != nullptr) {",
                    "        out.push_back(node->val);",
                    "        node = node->next;",
                    "    }",
                    "    return out;",
                    "}",
                    "",
                    "static void lccli_free_list_node(ListNode* node) {",
                    "    while (node != nullptr) {",
                    "        ListNode* next_node = node->next;",
                    "        delete node;",
                    "        node = next_node;",
                    "    }",
                    "}",
                    "",
                    "static string lccli_to_json(ListNode* node) {",
                    "    return lccli_to_json(lccli_serialize_list_node(node));",
                    "}",
                    "",
                ]
            )
        if include_tree:
            parts.extend(
                [
                    "struct TreeNode {",
                    "    int val;",
                    "    TreeNode* left;",
                    "    TreeNode* right;",
                    "    TreeNode() : val(0), left(nullptr), right(nullptr) {}",
                    "    TreeNode(int x) : val(x), left(nullptr), right(nullptr) {}",
                    "    TreeNode(int x, TreeNode* left_node, TreeNode* right_node) : val(x), left(left_node), right(right_node) {}",
                    "};",
                    "",
                    "static TreeNode* lccli_build_tree(const vector<optional<int>>& values) {",
                    "    if (values.empty() || !values[0].has_value()) return nullptr;",
                    "    TreeNode* root = new TreeNode(*values[0]);",
                    "    queue<TreeNode*> nodes;",
                    "    nodes.push(root);",
                    "    size_t index = 1;",
                    "    while (!nodes.empty() && index < values.size()) {",
                    "        TreeNode* node = nodes.front();",
                    "        nodes.pop();",
                    "        if (index < values.size() && values[index].has_value()) {",
                    "            node->left = new TreeNode(*values[index]);",
                    "            nodes.push(node->left);",
                    "        }",
                    "        ++index;",
                    "        if (index < values.size() && values[index].has_value()) {",
                    "            node->right = new TreeNode(*values[index]);",
                    "            nodes.push(node->right);",
                    "        }",
                    "        ++index;",
                    "    }",
                    "    return root;",
                    "}",
                    "",
                    "static vector<optional<int>> lccli_serialize_tree(TreeNode* root) {",
                    "    if (root == nullptr) return {};",
                    "    vector<optional<int>> out;",
                    "    queue<TreeNode*> nodes;",
                    "    nodes.push(root);",
                    "    while (!nodes.empty()) {",
                    "        TreeNode* node = nodes.front();",
                    "        nodes.pop();",
                    "        if (node == nullptr) {",
                    "            out.push_back(nullopt);",
                    "            continue;",
                    "        }",
                    "        out.push_back(node->val);",
                    "        nodes.push(node->left);",
                    "        nodes.push(node->right);",
                    "    }",
                    "    while (!out.empty() && !out.back().has_value()) {",
                    "        out.pop_back();",
                    "    }",
                    "    return out;",
                    "}",
                    "",
                    "static void lccli_free_tree(TreeNode* root) {",
                    "    if (root == nullptr) return;",
                    "    lccli_free_tree(root->left);",
                    "    lccli_free_tree(root->right);",
                    "    delete root;",
                    "}",
                    "",
                    "static string lccli_to_json(const optional<int>& value) {",
                    "    return value.has_value() ? lccli_to_json(*value) : string(\"null\");",
                    "}",
                    "",
                    "static string lccli_to_json(TreeNode* root) {",
                    "    return lccli_to_json(lccli_serialize_tree(root));",
                    "}",
                    "",
                ]
            )
        return "\n".join(parts)

    def _render_case_block(
        self,
        case: ExampleCase,
        params: list[dict],
        return_type: str | None,
        class_name: str,
        method_name: str,
    ) -> str:
        values = deserialize_case_inputs(case, params)
        lines = ["    {"]
        cleanup_vars: list[tuple[str, str]] = []
        call_args: list[str] = []
        for index, (value, param) in enumerate(zip(values, params)):
            expr, cleanup = self._cpp_value(value, param.get("type"))
            var_name = f"arg{index}"
            cpp_type = self._cpp_type(param.get("type"))
            lines.append(f"        {cpp_type} {var_name} = {expr};")
            call_args.append(var_name)
            cleanup_vars.extend((kind, var_name) for kind in cleanup)
        lines.append(f"        {class_name} solver;")

        normalized_return = re.sub(r"\s+", "", return_type or "").lower()
        if normalized_return in {"void", "none", "null"}:
            lines.append(f"        solver.{method_name}({', '.join(call_args)});")
            result_var = call_args[0] if call_args else "nullptr"
        else:
            lines.append(f"        auto lccli_result = solver.{method_name}({', '.join(call_args)});")
            result_var = "lccli_result"

        lines.append(f'        cout << lccli_to_json({result_var}) << "\\n";')
        for kind, var_name in reversed(cleanup_vars):
            if kind == "list":
                lines.append(f"        lccli_free_list_node({var_name});")
            elif kind == "tree":
                lines.append(f"        lccli_free_tree({var_name});")
        lines.append("    }")
        return "\n".join(lines)

    def _cpp_value(self, value: Any, type_name: str | None) -> tuple[str, list[str]]:
        normalized = self._normalize_type(type_name)
        lower = normalized.lower()
        if normalized == "ListNode":
            data = serialize_list_node(value)
            items = ", ".join(self._cpp_scalar(item, "integer") for item in data)
            return f"lccli_build_list_node(vector<int>{{{items}}})", ["list"]
        if normalized == "TreeNode":
            data = serialize_tree(value)
            items = ", ".join("nullopt" if item is None else f"optional<int>{{{int(item)}}}" for item in data)
            return f"lccli_build_tree(vector<optional<int>>{{{items}}})", ["tree"]
        if self._is_vector_type(normalized):
            inner = self._vector_inner_type(normalized)
            items = ", ".join(self._cpp_value(item, inner)[0] for item in value)
            return f"{self._cpp_type(normalized)}{{{items}}}", []
        return self._cpp_scalar(value, normalized), []

    def _cpp_scalar(self, value: Any, type_name: str | None) -> str:
        normalized = self._normalize_type(type_name)
        lower = normalized.lower()
        if lower in {"integer", "int"}:
            return str(int(value))
        if lower == "long":
            return f"{int(value)}LL"
        if lower in {"float", "double"}:
            return repr(float(value))
        if lower in {"boolean", "bool"}:
            return "true" if value else "false"
        if lower in {"string"}:
            return f"string({json.dumps(value)})"
        if lower in {"char", "character"}:
            if isinstance(value, str) and len(value) == 1:
                return f"static_cast<char>({ord(value)})"
            return str(int(value))
        if value is None:
            return "nullptr"
        return json.dumps(value)

    def _cpp_type(self, type_name: str | None) -> str:
        normalized = self._normalize_type(type_name)
        lower = normalized.lower()
        if self._is_vector_type(normalized):
            inner = self._vector_inner_type(normalized)
            return f"vector<{self._cpp_type(inner)}>"
        if normalized == "ListNode":
            return "ListNode*"
        if normalized == "TreeNode":
            return "TreeNode*"
        if lower in {"integer", "int"}:
            return "int"
        if lower == "long":
            return "long long"
        if lower in {"float", "double"}:
            return "double"
        if lower in {"boolean", "bool"}:
            return "bool"
        if lower == "string":
            return "string"
        if lower in {"char", "character"}:
            return "char"
        raise LeetCodeError(f"unsupported cpp type: {type_name}")

    def _normalize_type(self, type_name: str | None) -> str:
        return re.sub(r"\s+", "", type_name or "")

    def _is_vector_type(self, normalized: str) -> bool:
        return normalized.endswith("[]") or (
            normalized.startswith("List<") and normalized.endswith(">")
        )

    def _vector_inner_type(self, normalized: str) -> str:
        if normalized.endswith("[]"):
            return normalized[:-2]
        if normalized.startswith("List<") and normalized.endswith(">"):
            return normalized[5:-1]
        raise LeetCodeError(f"unsupported vector type: {normalized}")

    def _needs_list_node(self, meta: dict) -> bool:
        return self._meta_contains_type(meta, "ListNode")

    def _needs_tree_node(self, meta: dict) -> bool:
        return self._meta_contains_type(meta, "TreeNode")

    def _meta_contains_type(self, meta: dict, needle: str) -> bool:
        if needle == (meta.get("return") or {}).get("type"):
            return True
        return any(param.get("type") == needle for param in meta.get("params", []))


EXECUTORS: dict[str, LocalExecutor] = {
    "python3": PythonExecutor(),
    "cpp": CppExecutor(),
}


def get_local_executor(lang: str) -> LocalExecutor | None:
    return EXECUTORS.get(lang)


def supported_local_languages() -> set[str]:
    return set(EXECUTORS)
