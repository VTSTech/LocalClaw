"""
🦞 LocalClaw R02 — Extended Tools

Additional practical tools for LocalClaw agents:
  • json_extract - Extract values from JSON
  • text_process - Text manipulation utilities
  • diff_compare - Compare two texts
  • template_fill - Simple string templating
  • data_transform - Data format conversions
  • regex_tool - Regular expression operations

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import json
import re
import difflib
from typing import Any

from ..core.tools import ToolRegistry


def make_extended_tools() -> ToolRegistry:
    """
    Create a registry with extended utility tools.
    Can be combined with builtin tools via registry merge.
    """
    registry = ToolRegistry()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # JSON TOOLS
    # ═══════════════════════════════════════════════════════════════════════════
    
    @registry.tool(
        description="Extract a value from JSON using a dot-notation path. Returns 'null' if not found.",
        param_descriptions={
            "json_str": "JSON string to parse",
            "path": "Dot-notation path (e.g., 'data.users.0.name')"
        }
    )
    def json_extract(json_str: str, path: str) -> str:
        """Extract value from JSON using dot notation."""
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return f"[JSON parse error] {e}"
        
        # Navigate path
        parts = path.split(".")
        current = data
        
        for part in parts:
            if current is None:
                return "null"
            
            # Handle array indices
            if part.isdigit():
                idx = int(part)
                if isinstance(current, list) and 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return f"[Index {idx} out of bounds]"
            elif isinstance(current, dict):
                if part in current:
                    current = current[part]
                else:
                    return f"[Key '{part}' not found]"
            else:
                return f"[Cannot access '{part}' on {type(current).__name__}]"
        
        return json.dumps(current) if isinstance(current, (dict, list)) else str(current)
    
    @registry.tool(
        description="Parse JSON and return a list of all keys or values at a given depth.",
        param_descriptions={
            "json_str": "JSON string to parse",
            "extract": "What to extract: 'keys' or 'values' (default: 'keys')"
        }
    )
    def json_list(json_str: str, extract: str = "keys") -> str:
        """List keys or values from a JSON object."""
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return f"[JSON parse error] {e}"
        
        if isinstance(data, dict):
            items = list(data.keys() if extract == "keys" else data.values())
            return "\n".join(str(i) for i in items[:20])  # Limit output
        elif isinstance(data, list):
            return f"List with {len(data)} items: {str(data[:5])[:200]}..."
        else:
            return str(data)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TEXT TOOLS
    # ═══════════════════════════════════════════════════════════════════════════
    
    @registry.tool(
        description="Process text: truncate, lowercase, uppercase, strip, or count.",
        param_descriptions={
            "text": "Input text",
            "operation": "Operation: 'truncate:N', 'lower', 'upper', 'strip', 'count', 'lines', 'words'"
        }
    )
    def text_process(text: str, operation: str) -> str:
        """Apply text transformation."""
        op = operation.lower().strip()
        
        if op == "lower":
            return text.lower()
        elif op == "upper":
            return text.upper()
        elif op == "strip":
            return text.strip()
        elif op == "count":
            return f"Characters: {len(text)}"
        elif op == "lines":
            return f"Lines: {len(text.splitlines())}"
        elif op == "words":
            return f"Words: {len(text.split())}"
        elif op.startswith("truncate:"):
            try:
                n = int(op.split(":")[1])
                return text[:n] + ("..." if len(text) > n else "")
            except (IndexError, ValueError):
                return text[:100]
        elif op == "head":
            return "\n".join(text.splitlines()[:10])
        elif op == "tail":
            return "\n".join(text.splitlines()[-10:])
        else:
            return f"[Unknown operation: {operation}]"
    
    @registry.tool(
        description="Search text using a regular expression pattern.",
        param_descriptions={
            "text": "Text to search",
            "pattern": "Regular expression pattern",
            "flags": "Regex flags: 'i' for case-insensitive (default: '')"
        }
    )
    def regex_search(text: str, pattern: str, flags: str = "") -> str:
        """Search text with regex and return matches."""
        try:
            re_flags = 0
            if "i" in flags:
                re_flags |= re.IGNORECASE
            if "m" in flags:
                re_flags |= re.MULTILINE
            if "d" in flags:
                re_flags |= re.DOTALL
            
            matches = re.findall(pattern, text, re_flags)
            
            if not matches:
                return "[No matches found]"
            
            # Limit output
            unique = list(set(matches))[:20]
            return "\n".join(str(m) for m in unique)
        except re.error as e:
            return f"[Regex error] {e}"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DIFF TOOL
    # ═══════════════════════════════════════════════════════════════════════════
    
    @registry.tool(
        description="Compare two texts and show the differences line by line.",
        param_descriptions={
            "text1": "First text (original)",
            "text2": "Second text (modified)"
        }
    )
    def diff_compare(text1: str, text2: str) -> str:
        """Compare two texts and show differences."""
        lines1 = text1.splitlines(keepends=True)
        lines2 = text2.splitlines(keepends=True)
        
        diff = list(difflib.unified_diff(lines1, lines2, fromfile="original", tofile="modified", lineterm=""))
        
        if not diff:
            return "[No differences found - texts are identical]"
        
        return "".join(diff[:50])  # Limit output
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TEMPLATE TOOL
    # ═════════════════════════════════════════════════════════VTSTech════════════
    
    @registry.tool(
        description="Fill a template string by replacing {{key}} placeholders with values.",
        param_descriptions={
            "template": "Template string with {{key}} placeholders",
            "values_json": "JSON object with key-value pairs"
        }
    )
    def template_fill(template: str, values_json: str) -> str:
        """Fill template placeholders with values."""
        try:
            values = json.loads(values_json)
        except json.JSONDecodeError:
            return "[Invalid JSON for values]"
        
        result = template
        for key, value in values.items():
            placeholder = "{{" + key + "}}"
            result = result.replace(placeholder, str(value))
        
        return result
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DATA TRANSFORM
    # ═══════════════════════════════════════════════════════════════════════════
    
    @registry.tool(
        description="Convert between data formats: json-to-yaml, yaml-to-json, csv-to-json.",
        param_descriptions={
            "data": "Input data string",
            "transform": "Transformation: 'json2yaml', 'yaml2json', 'csv2json'"
        }
    )
    def data_transform(data: str, transform: str) -> str:
        """Transform data between formats."""
        t = transform.lower().strip()
        
        if t == "json2yaml":
            try:
                obj = json.loads(data)
                # Simple YAML output (no external deps)
                def to_yaml(obj, indent=0):
                    if isinstance(obj, dict):
                        lines = []
                        for k, v in obj.items():
                            if isinstance(v, (dict, list)):
                                lines.append("  " * indent + f"{k}:")
                                lines.append(to_yaml(v, indent + 1))
                            else:
                                lines.append("  " * indent + f"{k}: {v}")
                        return "\n".join(lines)
                    elif isinstance(obj, list):
                        lines = []
                        for item in obj:
                            if isinstance(item, dict):
                                lines.append("  " * indent + "-")
                                for k, v in item.items():
                                    lines.append("  " * (indent + 1) + f"{k}: {v}")
                            else:
                                lines.append("  " * indent + f"- {item}")
                        return "\n".join(lines)
                    else:
                        return str(obj)
                return to_yaml(obj)
            except json.JSONDecodeError as e:
                return f"[JSON error] {e}"
        
        elif t == "csv2json":
            try:
                lines = data.strip().split("\n")
                if len(lines) < 2:
                    return "[Need at least header + 1 data row]"
                headers = [h.strip() for h in lines[0].split(",")]
                rows = []
                for line in lines[1:]:
                    values = [v.strip() for v in line.split(",")]
                    row = dict(zip(headers, values))
                    rows.append(row)
                return json.dumps(rows, indent=2)
            except Exception as e:
                return f"[CSV error] {e}"
        
        elif t == "yaml2json":
            # Very basic YAML parser (no external deps)
            try:
                # This is a simplified parser - real YAML is complex
                lines = data.split("\n")
                result = {}
                current_key = None
                for line in lines:
                    if ":" in line and not line.startswith(" "):
                        key, value = line.split(":", 1)
                        current_key = key.strip()
                        if value.strip():
                            result[current_key] = value.strip()
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"[YAML error] {e}"
        
        else:
            return f"[Unknown transform: {transform}]"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STRING GENERATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    @registry.tool(
        description="Generate a random string of specified length.",
        param_descriptions={
            "length": "Length of string to generate (default 16)",
            "charset": "Characters to use: 'alphanumeric', 'alpha', 'numeric', 'hex' (default: alphanumeric)"
        }
    )
    def random_string(length: int = 16, charset: str = "alphanumeric") -> str:
        """Generate a random string."""
        import random
        import string
        
        length = max(1, min(128, length))  # Clamp to 1-128
        
        if charset == "alpha":
            chars = string.ascii_letters
        elif charset == "numeric":
            chars = string.digits
        elif charset == "hex":
            chars = "0123456789abcdef"
        else:  # alphanumeric
            chars = string.ascii_letters + string.digits
        
        return "".join(random.choice(chars) for _ in range(length))
    
    return registry


# Convenience: pre-made registry
EXTENDED_TOOLS = make_extended_tools()
