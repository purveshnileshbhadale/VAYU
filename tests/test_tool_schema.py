"""Tests for tool-schema conversion, and a guard on the real declarations.

The bug these exist to prevent is silent: a tool list that comes back empty or
malformed makes the model look disobedient rather than misconfigured.

Run with:  python -m unittest discover -s tests -v
"""

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.tool_schema import groq_tool_schema, normalize_schema  # noqa: E402


def real_declarations() -> list[dict]:
    """Pull TOOL_DECLARATIONS out of main.py without importing it.

    main.py pulls in the whole desktop stack at import time, so it is parsed
    rather than imported.
    """
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "TOOL_DECLARATIONS":
            return ast.literal_eval(node.value)
    raise AssertionError("TOOL_DECLARATIONS not found in main.py")


class NormalizeSchemaTest(unittest.TestCase):
    def test_lowercases_types(self):
        got = normalize_schema({"type": "OBJECT", "properties": {"x": {"type": "STRING"}}})
        self.assertEqual(got["type"], "object")
        self.assertEqual(got["properties"]["x"]["type"], "string")

    def test_recurses_into_arrays(self):
        got = normalize_schema({"type": "ARRAY", "items": {"type": "NUMBER"}})
        self.assertEqual(got["items"]["type"], "number")

    def test_leaves_unknown_type_values_alone(self):
        got = normalize_schema({"type": "SomethingCustom"})
        self.assertEqual(got["type"], "SomethingCustom")

    def test_drops_gemini_only_keys(self):
        self.assertNotIn("nullable", normalize_schema({"type": "STRING", "nullable": True}))

    def test_preserves_descriptions_and_required(self):
        got = normalize_schema({
            "type": "OBJECT",
            "properties": {"a": {"type": "STRING", "description": "keep me"}},
            "required": ["a"],
        })
        self.assertEqual(got["properties"]["a"]["description"], "keep me")
        self.assertEqual(got["required"], ["a"])


class GroqToolSchemaTest(unittest.TestCase):
    def test_wraps_flat_declarations(self):
        tools = groq_tool_schema([
            {"name": "do_thing", "description": "does it",
             "parameters": {"type": "OBJECT", "properties": {}}},
        ])
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["type"], "function")
        self.assertEqual(tools[0]["function"]["name"], "do_thing")
        self.assertEqual(tools[0]["function"]["parameters"]["type"], "object")

    def test_accepts_the_gemini_wrapper_form(self):
        tools = groq_tool_schema([{"function_declarations": [
            {"name": "nested", "description": "", "parameters": {"type": "OBJECT"}},
        ]}])
        self.assertEqual([t["function"]["name"] for t in tools], ["nested"])

    def test_skips_entries_without_a_name(self):
        self.assertEqual(groq_tool_schema([{"description": "anonymous"}]), [])

    def test_supplies_parameters_when_missing(self):
        tools = groq_tool_schema([{"name": "bare"}])
        self.assertEqual(tools[0]["function"]["parameters"], {"type": "object", "properties": {}})

    def test_empty_input_is_empty_output(self):
        self.assertEqual(groq_tool_schema([]), [])
        self.assertEqual(groq_tool_schema(None), [])


class RealDeclarationsTest(unittest.TestCase):
    """Guards the regression that shipped: Groq mode advertising zero tools."""

    def setUp(self):
        self.decls = real_declarations()
        self.tools = groq_tool_schema(self.decls)

    def test_every_declaration_converts(self):
        self.assertEqual(len(self.tools), len(self.decls))
        self.assertGreater(len(self.tools), 30)

    def test_no_uppercase_types_survive(self):
        def walk(node):
            if isinstance(node, dict):
                t = node.get("type")
                if isinstance(t, str) and t.isupper():
                    self.fail(f"uppercase type survived conversion: {t}")
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(self.tools)

    def test_the_new_tools_are_present(self):
        names = {t["function"]["name"] for t in self.tools}
        self.assertIn("gesture_control", names)
        self.assertIn("screen_process", names)

    def test_names_are_unique(self):
        names = [t["function"]["name"] for t in self.tools]
        self.assertEqual(len(names), len(set(names)), "duplicate tool names would confuse the model")


if __name__ == "__main__":
    unittest.main()
