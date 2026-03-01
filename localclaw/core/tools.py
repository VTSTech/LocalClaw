"""
LocalClaw — Tool System
Decorator-based tool registry that auto-generates Ollama-compatible JSON schemas
from Python type hints and docstrings.
"""

import inspect
import json
from typing import Any, Callable, get_type_hints
from dataclasses import dataclass, field


# ------------------------------------------------------------------ #
#  Type → JSON Schema mapping                                          #
# ------------------------------------------------------------------ #

_PY_TO_JSON = {
    int: "integer",
    float: "number",
    str: "string",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _py_type_to_json(t) -> str:
    origin = getattr(t, "__origin__", None)
    if origin is list:
        return "array"
    if origin is dict:
        return "object"
    return _PY_TO_JSON.get(t, "string")


# ------------------------------------------------------------------ #
#  Tool descriptor                                                     #
# ------------------------------------------------------------------ #

@dataclass
class ToolParam:
    name: str
    type: str
    description: str
    required: bool = True
    enum: list | None = None


@dataclass
class Tool:
    name: str
    description: str
    fn: Callable
    params: list[ToolParam] = field(default_factory=list)

    def to_ollama_schema(self) -> dict:
        """Return the tool definition dict Ollama expects."""
        properties = {}
        required = []
        for p in self.params:
            prop: dict[str, Any] = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
            if p.required:
                required.append(p.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def __call__(self, **kwargs) -> Any:
        return self.fn(**kwargs)


# ------------------------------------------------------------------ #
#  Registry                                                            #
# ------------------------------------------------------------------ #

class ToolRegistry:
    """
    Central store for all tools.  Agents receive a view into this registry.

    Usage:
        registry = ToolRegistry()

        @registry.tool(description="Add two numbers")
        def add(a: int, b: int) -> int:
            '''Add a and b together.'''
            return a + b
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    # ---- registration ------------------------------------------------ #

    def tool(
        self,
        description: str | None = None,
        name: str | None = None,
        param_descriptions: dict[str, str] | None = None,
    ):
        """Decorator to register a function as a tool."""

        def decorator(fn: Callable) -> Callable:
            tool_name = name or fn.__name__
            tool_desc = description or (inspect.getdoc(fn) or "").split("\n")[0]
            param_descs = param_descriptions or {}

            hints = get_type_hints(fn)
            sig = inspect.signature(fn)

            params = []
            for pname, param in sig.parameters.items():
                if pname == "return":
                    continue
                py_type = hints.get(pname, str)
                json_type = _py_type_to_json(py_type)
                has_default = param.default is not inspect.Parameter.empty
                params.append(
                    ToolParam(
                        name=pname,
                        type=json_type,
                        description=param_descs.get(pname, pname.replace("_", " ")),
                        required=not has_default,
                    )
                )

            t = Tool(name=tool_name, description=tool_desc, fn=fn, params=params)
            self._tools[tool_name] = t
            return fn

        return decorator

    def register(self, tool: Tool):
        """Manually register a pre-built Tool object."""
        self._tools[tool.name] = tool

    # ---- access ------------------------------------------------------ #

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def schemas(self) -> list[dict]:
        return [t.to_ollama_schema() for t in self._tools.values()]

    def invoke(self, name: str, args: dict) -> Any:
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' not found in registry.")
        try:
            return tool(**args)
        except Exception as e:
            return f"[Tool error] {type(e).__name__}: {e}"

    def subset(self, names: list[str]) -> "ToolRegistry":
        """Return a new registry containing only the named tools."""
        sub = ToolRegistry()
        for name in names:
            if name in self._tools:
                sub._tools[name] = self._tools[name]
        return sub

    def __repr__(self):
        return f"ToolRegistry({list(self._tools.keys())})"


# ------------------------------------------------------------------ #
#  Module-level default registry (optional convenience)               #
# ------------------------------------------------------------------ #

default_registry = ToolRegistry()
tool = default_registry.tool   # shorthand decorator
