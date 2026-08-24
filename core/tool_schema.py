"""Convert VAYU's tool declarations into the schema Groq/OpenAI expects.

The declarations in main.py are written in Gemini's dialect: a flat list of
``{name, description, parameters}`` with uppercase JSON-Schema types
(``"OBJECT"``, ``"STRING"``). Gemini gets them wrapped as
``[{"function_declarations": [...]}]``; Groq needs each one wrapped
individually as ``{"type": "function", "function": {...}}`` with lowercase
types.

Getting this wrong is quiet rather than loud: an empty or malformed tool list
means the model simply never calls a tool, and the assistant looks like it is
ignoring instructions rather than like it is misconfigured.
"""

from __future__ import annotations

from typing import Any

# JSON Schema types, as Groq/OpenAI expect to see them.
_TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}


def normalize_schema(node: Any) -> Any:
    """Recursively lowercase ``type`` values and drop Gemini-only keys."""
    if isinstance(node, list):
        return [normalize_schema(v) for v in node]
    if not isinstance(node, dict):
        return node

    out: dict[str, Any] = {}
    for key, value in node.items():
        if key == "type" and isinstance(value, str):
            lowered = value.lower()
            out[key] = lowered if lowered in _TYPES else value
        elif key in ("properties", "items", "$defs", "definitions"):
            out[key] = normalize_schema(value)
        elif key == "nullable":
            continue  # Gemini-only; Groq rejects unknown keywords on some models
        else:
            out[key] = normalize_schema(value)
    return out


def groq_tool_schema(declarations: list[dict]) -> list[dict]:
    """Wrap flat tool declarations for the Groq chat-completions API.

    Accepts either the flat form used throughout VAYU or the Gemini wrapper
    form (``{"function_declarations": [...]}``), so plugin declarations in
    either shape are handled.
    """
    tools: list[dict] = []

    for decl in declarations or []:
        if not isinstance(decl, dict):
            continue
        nested = decl.get("function_declarations")
        group = nested if isinstance(nested, list) else [decl]

        for fn in group:
            if not isinstance(fn, dict):
                continue
            name = fn.get("name")
            if not name:
                continue
            params = fn.get("parameters") or {"type": "object", "properties": {}}
            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": fn.get("description", ""),
                    "parameters": normalize_schema(params),
                },
            })

    return tools
