"""Utilities for reading and updating tool functions/definitions in tools.py."""

from __future__ import annotations

import ast
import pprint
import re
from pathlib import Path
from typing import Any


class ToolRegistryManager:
    """Manage tool function code and OpenAI tool definitions in tools.py."""

    def __init__(self, tools_file: str = "tools.py"):
        self.tools_file = Path(tools_file)

    def list_tools(self) -> list[dict[str, Any]]:
        """Return tools with metadata and source code for each backing function."""
        source = self._read_source()
        module = self._parse_module(source)

        tools_value, _ = self._extract_tools_assignment(module)
        function_nodes = {
            node.name: node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
        }

        result: list[dict[str, Any]] = []
        for tool in tools_value:
            if not isinstance(tool, dict):
                continue
            function_meta = tool.get("function", {})
            name = function_meta.get("name")
            if not name:
                continue

            function_node = function_nodes.get(name)
            function_code = ""
            if function_node is not None:
                function_code = ast.get_source_segment(source, function_node) or ""

            result.append(
                {
                    "name": name,
                    "description": function_meta.get("description", ""),
                    "parameters": function_meta.get("parameters", {}),
                    "code": function_code,
                }
            )

        return result

    def update_tool_code(self, tool_name: str, code: str) -> None:
        """Replace an existing tool function definition with updated code."""
        self._validate_function_code(tool_name, code)

        source = self._read_source()
        module = self._parse_module(source)
        function_node = self._find_function_node(module, tool_name)

        if function_node is None:
            raise ValueError(f"Tool function '{tool_name}' does not exist")

        updated_source = self._replace_line_range(
            source,
            function_node.lineno,
            function_node.end_lineno,
            code.strip() + "\n",
        )

        self._parse_module(updated_source)
        self._write_source(updated_source)

    def add_tool(
        self,
        *,
        name: str,
        description: str,
        parameters: dict[str, Any],
        code: str,
    ) -> None:
        """Add a new tool function, map entry, and OpenAI tool definition."""
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            raise ValueError("Tool name must be a valid Python identifier")

        if not isinstance(parameters, dict):
            raise ValueError("Tool parameters must be a JSON object")

        self._validate_function_code(name, code)

        source = self._read_source()
        module = self._parse_module(source)

        existing_function = self._find_function_node(module, name)
        if existing_function is not None:
            raise ValueError(f"Tool function '{name}' already exists")

        tools_value, _ = self._extract_tools_assignment(module)
        if any(
            isinstance(tool, dict)
            and isinstance(tool.get("function"), dict)
            and tool["function"].get("name") == name
            for tool in tools_value
        ):
            raise ValueError(f"Tool definition '{name}' already exists")

        execute_tool_node = self._find_function_node(module, "execute_tool")
        if execute_tool_node is None:
            raise ValueError("Could not locate execute_tool in tools.py")

        updated_source = self._insert_before_line(
            source,
            execute_tool_node.lineno,
            code.strip() + "\n\n",
        )

        updated_source = self._add_tools_map_entry(updated_source, name)

        updated_module = self._parse_module(updated_source)
        updated_tools_value, updated_tools_assignment = self._extract_tools_assignment(updated_module)

        updated_tools_value.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            }
        )

        tools_block = "TOOLS = " + pprint.pformat(
            updated_tools_value,
            width=100,
            sort_dicts=False,
        )
        updated_source = self._replace_line_range(
            updated_source,
            updated_tools_assignment.lineno,
            updated_tools_assignment.end_lineno,
            tools_block + "\n",
        )

        self._parse_module(updated_source)
        self._write_source(updated_source)

    def _read_source(self) -> str:
        return self.tools_file.read_text(encoding="utf-8")

    def _write_source(self, source: str) -> None:
        if not source.endswith("\n"):
            source += "\n"
        self.tools_file.write_text(source, encoding="utf-8")

    def _parse_module(self, source: str) -> ast.Module:
        return ast.parse(source)

    def _extract_tools_assignment(self, module: ast.Module) -> tuple[list[dict[str, Any]], ast.Assign]:
        for node in module.body:
            if not isinstance(node, ast.Assign):
                continue
            if len(node.targets) != 1:
                continue
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == "TOOLS":
                value = ast.literal_eval(node.value)
                if not isinstance(value, list):
                    raise ValueError("TOOLS must be a list")
                return value, node

        raise ValueError("Could not locate TOOLS assignment")

    def _find_function_node(self, module: ast.Module, function_name: str) -> ast.FunctionDef | None:
        for node in module.body:
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                return node
        return None

    def _validate_function_code(self, expected_name: str, code: str) -> None:
        if not code.strip():
            raise ValueError("Function code cannot be empty")

        parsed = ast.parse(code)
        function_nodes = [node for node in parsed.body if isinstance(node, ast.FunctionDef)]
        if not function_nodes:
            raise ValueError("Code must include a function definition")

        if len(function_nodes) != 1:
            raise ValueError("Code block must include exactly one top-level function")

        if function_nodes[0].name != expected_name:
            raise ValueError(
                f"Function name mismatch. Expected '{expected_name}', got '{function_nodes[0].name}'"
            )

    def _replace_line_range(self, source: str, start_line: int, end_line: int, replacement: str) -> str:
        lines = source.splitlines()
        replacement_lines = replacement.splitlines()
        updated_lines = lines[: start_line - 1] + replacement_lines + lines[end_line:]
        return "\n".join(updated_lines) + "\n"

    def _insert_before_line(self, source: str, line_number: int, text: str) -> str:
        lines = source.splitlines()
        insert_lines = text.splitlines()
        updated_lines = lines[: line_number - 1] + insert_lines + lines[line_number - 1 :]
        return "\n".join(updated_lines) + "\n"

    def _add_tools_map_entry(self, source: str, tool_name: str) -> str:
        module = self._parse_module(source)
        execute_tool = self._find_function_node(module, "execute_tool")
        if execute_tool is None:
            raise ValueError("Could not locate execute_tool function")

        tools_map_node = None
        for statement in execute_tool.body:
            if not isinstance(statement, ast.Assign):
                continue
            if len(statement.targets) != 1:
                continue
            target = statement.targets[0]
            if isinstance(target, ast.Name) and target.id == "tools_map" and isinstance(statement.value, ast.Dict):
                tools_map_node = statement.value
                break

        if tools_map_node is None:
            raise ValueError("Could not locate tools_map dictionary")

        existing_keys = []
        for key in tools_map_node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                existing_keys.append(key.value)

        if tool_name in existing_keys:
            return source

        lines = source.splitlines()
        closing_line_index = tools_map_node.end_lineno - 1
        closing_line = lines[closing_line_index]
        closing_indent = closing_line[: len(closing_line) - len(closing_line.lstrip())]
        entry_indent = closing_indent + "    "
        new_entry = f'{entry_indent}"{tool_name}": {tool_name},'

        lines.insert(closing_line_index, new_entry)
        return "\n".join(lines) + "\n"
