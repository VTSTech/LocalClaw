# -*- coding: utf-8 -*-
"""
Ollama API Client with Function Calling and JSON Mode Support

Supports:
- Native tool/function calling
- JSON mode for structured output
- Streaming and non-streaming responses
"""

import requests
import json
import time
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass

# Ollama Connection Constants
CHAT_URL = "http://127.0.0.1:11434/api/chat"


# =============================================================================
# DEFAULT PARAMETERS
# =============================================================================

# For deterministic tool calling
TOOL_CALL_PARAMS = {
    "temperature": 0.0,
    "num_predict": 512,
    "top_k": 10,
    "repeat_penalty": 1.1,
}

# For chat responses
CHAT_PARAMS = {
    "temperature": 0.3,
    "num_predict": 1024,
    "top_k": 40,
    "repeat_penalty": 1.1,
}


# =============================================================================
# TOOL CALLING TYPES
# =============================================================================

@dataclass
class ToolCall:
    """Represents a tool/function call from the model"""
    name: str
    arguments: Dict[str, Any]
    id: Optional[str] = None
    
    @classmethod
    def from_ollama(cls, tool_call: Dict) -> "ToolCall":
        """Parse from Ollama response format"""
        function = tool_call.get("function", {})
        name = function.get("name", "")
        args_str = function.get("arguments", "{}")
        
        # Parse arguments (may be string or dict)
        if isinstance(args_str, str):
            try:
                arguments = json.loads(args_str)
            except json.JSONDecodeError:
                arguments = {"raw": args_str}
        else:
            arguments = args_str
        
        return cls(
            name=name,
            arguments=arguments,
            id=tool_call.get("id")
        )


# =============================================================================
# API FUNCTIONS
# =============================================================================

def chat_api(
    model: str,
    messages: List[Dict],
    tools: List[Dict] = None,
    tool_choice: str = "auto",
    json_mode: bool = False,
    params: Dict = None,
    retries: int = 3,
) -> Dict:
    """
    Chat API with function calling support.
    
    Args:
        model: Model name (e.g., "qwen2.5:3b")
        messages: List of message dicts
        tools: List of tool definitions in OpenAI format
        tool_choice: "auto", "none", or "required"
        json_mode: Force JSON output format
        params: Generation parameters
        retries: Number of retries on failure
    
    Returns:
        Response dict with message and optional tool_calls
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": params or TOOL_CALL_PARAMS,
    }
    
    # Add tools if provided
    if tools:
        payload["tools"] = tools
    
    # Tool choice
    if tool_choice != "auto":
        if tool_choice == "none":
            pass  # Don't include tools
        elif tool_choice == "required":
            payload["tool_choice"] = {"type": "function"}
    
    # JSON mode
    if json_mode:
        payload["format"] = "json"
    
    for attempt in range(retries + 1):
        try:
            response = requests.post(CHAT_URL, json=payload, timeout=120)
            response.raise_for_status()
            
            data = response.json()
            
            # Validate response
            if not data.get("message"):
                raise RuntimeError("Empty response from model")
            
            return data
            
        except requests.exceptions.RequestException as e:
            if attempt < retries:
                wait_time = 2 ** attempt
                time.sleep(wait_time)
                continue
            return {
                "message": {
                    "role": "assistant",
                    "content": f"[ERROR] Connection failed: {str(e)}"
                }
            }
        except Exception as e:
            return {
                "message": {
                    "role": "assistant", 
                    "content": f"[ERROR] {str(e)}"
                }
            }


def chat_json(
    model: str,
    messages: List[Dict],
    schema: Dict = None,
    params: Dict = None,
) -> Dict:
    """
    Chat with forced JSON output.
    
    Args:
        model: Model name
        messages: Conversation history
        schema: Optional JSON schema (for models that support it)
        params: Generation parameters
    
    Returns:
        Parsed JSON dict or error
    """
    params = params or {**TOOL_CALL_PARAMS, "num_predict": 2048}
    
    response = chat_api(
        model=model,
        messages=messages,
        json_mode=True,
        params=params,
    )
    
    content = response.get("message", {}).get("content", "")
    
    # Parse JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass
        
        return {
            "error": "Failed to parse JSON response",
            "raw": content
        }


# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================

def get_model_info(model: str, detail: str = "template") -> str:
    """Get model information"""
    try:
        r = requests.post(
            "http://127.0.0.1:11434/api/show",
            json={"name": model}
        )
        r.raise_for_status()
        return r.json().get(detail, "No info available")
    except:
        return f"Error retrieving info for {model}"