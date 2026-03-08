"""
LocalClaw — Agent
Core ReAct agent that drives the think → act → observe loop.

Supports:
  • Native Ollama tool-calling (for models that expose it)
  • Text-based ReAct fallback (for models without native tool support)
  • Streaming output
  • Hooks for custom logging / UI

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Literal

from .ollama_client import OllamaClient
from .memory import Memory
from .tools import ToolRegistry


# ------------------------------------------------------------------ #
#  Argument key normalizer                                             #
# ------------------------------------------------------------------ #

def _normalize_args(args: dict, tool) -> dict:
    """
    Small models sometimes hallucinate argument keys, e.g. merging
    the param name with its description: 'amount from_currency' instead
    of 'amount'. This attempts to match each incoming key to a real
    parameter name via exact → prefix → substring matching.

    Also coerces string values to the correct type when the schema
    declares integer or number (e.g. '500' → 500.0).
    """
    if tool is None:
        return args

    real_params = [p for p in tool.params]
    if not real_params:
        return args

    param_map = {p.name: p for p in real_params}

    normalized = {}
    for key, val in args.items():
        # Resolve key → real param name
        if key in param_map:
            target_param = param_map[key]
        else:
            target_param = None
            for p in real_params:
                if p.name in key or key.startswith(p.name):
                    target_param = p
                    break

        pname = target_param.name if target_param else key

        # Coerce string numbers to the declared type
        if target_param and isinstance(val, str):
            if target_param.type in ("number", "float"):
                try:
                    val = float(val)
                except ValueError:
                    pass
            elif target_param.type == "integer":
                try:
                    val = int(val)
                except ValueError:
                    pass

        if pname not in normalized:
            normalized[pname] = val
        else:
            normalized[key] = val  # collision — pass through

    return normalized


def _fix_calculator_args(t_name: str, t_args: dict, user_input: str, prior_results: list[str]) -> dict:
    """
    Detect when a model passes a plain number as a calculator expression
    (e.g. expression='83521') when the question implies a further operation
    like sqrt. Rewrites the expression to the correct form.
    """
    if t_name != "calculator":
        return t_args
    expr = t_args.get("expression", "")
    # Check if expression is just a plain number matching a prior result
    try:
        float(expr)
    except (ValueError, TypeError):
        return t_args  # already a real expression, leave it alone

    q = user_input.lower()
    if "sqrt" in q or "square root" in q:
        t_args = dict(t_args)
        t_args["expression"] = f"sqrt({expr})"
    return t_args


def _looks_like_tool_schema(text: str) -> bool:
    """
    Returns True if the text looks like the model outputting a JSON
    function-call schema rather than a real answer. Catches patterns like:
      {"name": "...", "parameters": {...}}
      {"name": "...", "arguments": {...}}
    even when no tools were defined.
    """
    stripped = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1:
        return False
    try:
        obj = json.loads(stripped[start:end + 1])
        return (
            isinstance(obj, dict)
            and "name" in obj
            and any(k in obj for k in ("parameters", "arguments", "args"))
        )
    except json.JSONDecodeError:
        return False


# ------------------------------------------------------------------ #
#  Agent result                                                         #
# ------------------------------------------------------------------ #

@dataclass
class StepResult:
    type: Literal["thought", "tool_call", "tool_result", "final"]
    content: str
    tool_name: str | None = None
    tool_args: dict | None = None
    elapsed_ms: float = 0.0

    def __str__(self):
        if self.type == "tool_call":
            return f"[CALL] {self.tool_name}({self.tool_args})"
        if self.type == "tool_result":
            return f"[RESULT] {self.tool_name} → {self.content}"
        if self.type == "thought":
            return f"[THOUGHT] {self.content}"
        return f"[FINAL] {self.content}"


@dataclass
class AgentRun:
    steps: list[StepResult] = field(default_factory=list)
    final_answer: str = ""
    total_ms: float = 0.0
    success: bool = True
    error: str = ""

    def print_trace(self):
        for step in self.steps:
            print(step)
        print(f"\n✓ Done in {self.total_ms:.0f}ms")


# ------------------------------------------------------------------ #
#  ReAct text parser                                                   #
# ------------------------------------------------------------------ #

_THOUGHT_RE = re.compile(r"Thought:\s*(.*?)(?=Action:|Final Answer:|$)", re.DOTALL | re.IGNORECASE)
_ACTION_RE  = re.compile(r"Action:\s*(\w+)\s*\nAction Input:\s*(.*?)(?=Observation:|Thought:|Final Answer:|$)", re.DOTALL | re.IGNORECASE)
_FINAL_RE   = re.compile(r"Final Answer:\s*(.*?)$", re.DOTALL | re.IGNORECASE)

REACT_SYSTEM_SUFFIX = """
You have access to tools. Use the following format EXACTLY:

Thought: <your reasoning about what to do next>
Action: <tool_name>
Action Input: <JSON object with tool arguments>
Observation: <the result will appear here>
... (repeat Thought/Action/Action Input/Observation as needed)
Thought: I now have enough information.
Final Answer: <your final response to the user>

IMPORTANT: Action Input must be valid JSON. Only use tools listed below.
"""


def _parse_json_tool_call(text: str) -> tuple[str | None, dict | None]:
    """
    Fallback for models that output tool calls as JSON text instead of
    using the native tool_calls API field. Handles patterns like:

        ```json
        {"name": "calculator", "arguments": {"expression": "2+2"}}
        ```

    Returns (tool_name, tool_args) or (None, None) if not found.
    """
    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()

    # Find the outermost JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        return None, None

    try:
        obj = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None, None

    # Support {"name": ..., "arguments": ...} and {"name": ..., "parameters": ...}
    name = obj.get("name") or obj.get("function")
    args = obj.get("arguments") or obj.get("parameters") or obj.get("args") or {}

    if not name or not isinstance(args, dict):
        return None, None

    return name, args


def _parse_react(text: str) -> tuple[str | None, str | None, dict | None, str | None]:
    """
    Returns (thought, tool_name, tool_args, final_answer).
    Any field may be None if not present.
    """
    thought = None
    tool_name = None
    tool_args = None
    final_answer = None

    m = _THOUGHT_RE.search(text)
    if m:
        thought = m.group(1).strip()

    m = _ACTION_RE.search(text)
    if m:
        tool_name = m.group(1).strip()
        raw_args = m.group(2).strip()
        try:
            tool_args = json.loads(raw_args)
        except json.JSONDecodeError:
            # Try to salvage key=value style
            tool_args = {"input": raw_args}

    m = _FINAL_RE.search(text)
    if m:
        final_answer = m.group(1).strip()

    return thought, tool_name, tool_args, final_answer


# ------------------------------------------------------------------ #
#  Agent                                                               #
# ------------------------------------------------------------------ #

class Agent:
    """
    A single autonomous agent backed by a local Ollama model.

    Parameters
    ----------
    model : str
        Ollama model tag, e.g. "llama3.1:8b" or "qwen2.5:14b".
    tools : ToolRegistry | None
        Tools this agent may call.
    system_prompt : str
        Base instructions for the agent.
    max_steps : int
        Safety ceiling on tool-call iterations per run.
    client : OllamaClient | None
        Shared client (creates one if not provided).
    force_react : bool
        If True, always use text-based ReAct even if the model supports native tools.
    on_step : Callable[[StepResult], None] | None
        Called after each step — useful for live UI updates.
    model_options : dict | None
        Passed through to Ollama (temperature, num_ctx, etc.).
    """

    def __init__(
        self,
        model: str,
        tools: ToolRegistry | None = None,
        system_prompt: str = "You are a helpful assistant.",
        max_steps: int = 10,
        client: OllamaClient | None = None,
        force_react: bool = False,
        on_step: Callable[[StepResult], None] | None = None,
        model_options: dict | None = None,
        memory_max_turns: int = 20,
    ):
        self.model = model
        self.tools = tools or ToolRegistry()
        self.max_steps = max_steps
        self.client = client or OllamaClient()
        self.force_react = force_react
        self.on_step = on_step
        self.model_options = model_options or {}

        self._native_tools = (
            not force_react and self.client.model_supports_tools(model)
        )

        # Build system prompt
        base_sys = system_prompt
        if not self._native_tools and self.tools.all():
            tool_descriptions = "\n".join(
                f"- {t.name}: {t.description}" for t in self.tools.all()
            )
            base_sys = base_sys + f"\n\nAvailable tools:\n{tool_descriptions}" + REACT_SYSTEM_SUFFIX

        self.memory = Memory(
            system_prompt=base_sys,
            max_turns=memory_max_turns,
        )

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def run(self, user_input: str) -> AgentRun:
        """
        Run the agent on a user message and return a complete AgentRun.
        """
        run = AgentRun()
        t0 = time.perf_counter()
        self.memory.add_user(user_input)

        # Loop guards
        _tool_call_counts: dict[str, int] = {}  # per-tool call counter
        _successful_results: list[str] = []      # accumulate good results for synthesis
        _successful_tools: set[str] = set()      # track which tools have returned good results
        _max_calls_per_tool = 2
        _max_total_tool_calls = 4               # hard ceiling across all tools

        for _ in range(self.max_steps):
            step_t0 = time.perf_counter()

            response = self.client.chat(
                model=self.model,
                messages=self.memory.to_messages(),
                tools=self.tools.schemas() if self._native_tools else None,
                options=self.model_options,
            )

            elapsed = (time.perf_counter() - step_t0) * 1000
            msg = response.get("message", {})
            content = msg.get("content", "")
            tool_calls_raw = msg.get("tool_calls", [])

            # ---- Native tool calling --------------------------------- #
            if self._native_tools and tool_calls_raw:
                self.memory.add_assistant(content or "", tool_calls=tool_calls_raw)

                for tc in tool_calls_raw:
                    fn = tc.get("function", {})
                    t_name = fn.get("name", "")
                    t_args = fn.get("arguments", {})
                    if isinstance(t_args, str):
                        try:
                            t_args = json.loads(t_args)
                        except json.JSONDecodeError:
                            t_args = {}

                    t_args = _normalize_args(t_args, self.tools.get(t_name))
                    t_args = _fix_calculator_args(t_name, t_args, user_input, _successful_results)
                    _tool_call_counts[t_name] = _tool_call_counts.get(t_name, 0) + 1

                    call_step = StepResult(
                        type="tool_call",
                        content=f"{t_name}({t_args})",
                        tool_name=t_name,
                        tool_args=t_args,
                        elapsed_ms=elapsed,
                    )
                    run.steps.append(call_step)
                    self._emit(call_step)

                    result = self.tools.invoke(t_name, t_args)
                    result_str = str(result)

                    result_step = StepResult(type="tool_result", content=result_str, tool_name=t_name)
                    run.steps.append(result_step)
                    self._emit(result_step)
                    self.memory.add_tool_result(t_name, result_str)

                    if not result_str.startswith("[Tool error]"):
                        _successful_results.append(f"{t_name} → {result_str}")

                continue

            # ---- JSON-in-text fallback (small models that ignore tool API) -- #
            # Some models (e.g. llama3.2:1b) output JSON in the message body
            # instead of using the tool_calls field.
            if self._native_tools and not tool_calls_raw and self.tools.all() and content:
                t_name, t_args = _parse_json_tool_call(content)
                if t_name and t_args is not None and self.tools.get(t_name):
                    t_args = _normalize_args(t_args, self.tools.get(t_name))

                    # Intercept repeat calls only when args are identical — the model is
                    # truly stuck. Different args = legitimate chained call (e.g. sqrt after **).
                    if not hasattr(run, '_last_tool_args'):
                        run._last_tool_args = {}
                    already_succeeded = t_name in _successful_tools
                    same_args = run._last_tool_args.get(t_name) == t_args
                    if already_succeeded and same_args:
                        pending = [
                            t.name for t in self.tools.all()
                            if t.name not in _successful_tools
                        ]
                        if pending:
                            self.memory.add_user(
                                f"You already have the result for {t_name} with those arguments. "
                                f"Please call {pending[0]} next to complete the answer."
                            )
                        else:
                            # All tools done — synthesize now
                            final_answer = self._synthesize(user_input, _successful_results)
                            final_step = StepResult(type="final", content=final_answer, elapsed_ms=elapsed)
                            run.steps.append(final_step)
                            self._emit(final_step)
                            run.final_answer = final_answer
                            break
                        continue

                    run._last_tool_args[t_name] = t_args

                    t_args = _fix_calculator_args(t_name, t_args, user_input, _successful_results)
                    _tool_call_counts[t_name] = _tool_call_counts.get(t_name, 0) + 1

                    # Hard ceiling — synthesize from what we already have
                    total_calls = sum(_tool_call_counts.values())
                    if _tool_call_counts[t_name] > _max_calls_per_tool or total_calls > _max_total_tool_calls:
                        final_answer = self._synthesize(user_input, _successful_results)
                        final_step = StepResult(type="final", content=final_answer, elapsed_ms=elapsed)
                        run.steps.append(final_step)
                        self._emit(final_step)
                        run.final_answer = final_answer
                        break

                    self.memory.add_assistant(content)

                    call_step = StepResult(
                        type="tool_call",
                        content=f"{t_name}({t_args})",
                        tool_name=t_name,
                        tool_args=t_args,
                        elapsed_ms=elapsed,
                    )
                    run.steps.append(call_step)
                    self._emit(call_step)

                    result = self.tools.invoke(t_name, t_args)
                    result_str = str(result)

                    result_step = StepResult(type="tool_result", content=result_str, tool_name=t_name)
                    run.steps.append(result_step)
                    self._emit(result_step)

                    if result_str.startswith("[Tool error]"):
                        # Feed rich error back so the model can self-correct
                        tool_obj = self.tools.get(t_name)
                        param_hint = ", ".join(
                            f"{p.name}: {p.type}" for p in tool_obj.params
                        )
                        self.memory.add_tool_result(
                            t_name,
                            f"Error: {result_str}\nExpected arguments: {param_hint}",
                        )
                    else:
                        _successful_results.append(f"{t_name} → {result_str}")
                        _successful_tools.add(t_name)
                        self.memory.add_tool_result(t_name, result_str)

                    # Nudge the model to answer once 2+ distinct tools have succeeded.
                    # Don't fire on repeats — those are intercepted above.
                    if not result_str.startswith("[Tool error]") and len(_successful_tools) >= 2:
                        results_so_far = "\n".join(f"- {r}" for r in _successful_results)
                        self.memory.add_user(
                            f"You have already gathered the following information:\n{results_so_far}\n\n"
                            f"Please now answer the original question in plain text using these results.\n"
                            f"Original question: {user_input}\n"
                            "Do NOT call any more tools."
                        )
                        nudge_response = self.client.chat(
                            model=self.model,
                            messages=self.memory.to_messages(),
                            options=self.model_options,
                        )
                        nudge_content = nudge_response.get("message", {}).get("content", "").strip()
                        # Only accept it if it doesn't look like another tool call
                        _, check_args = _parse_json_tool_call(nudge_content)
                        if nudge_content and check_args is None:
                            final_step = StepResult(type="final", content=nudge_content, elapsed_ms=elapsed)
                            run.steps.append(final_step)
                            self._emit(final_step)
                            run.final_answer = nudge_content
                            self.memory.add_assistant(nudge_content)
                            break
                        else:
                            # Model still wants to use tools — remove nudge from memory and let it
                            self.memory._history.pop()
                    continue

            # ---- ReAct text parsing ---------------------------------- #
            if not self._native_tools and self.tools.all():
                thought, t_name, t_args, final_answer = _parse_react(content)

                if thought:
                    step = StepResult(type="thought", content=thought, elapsed_ms=elapsed)
                    run.steps.append(step)
                    self._emit(step)

                if t_name and t_args is not None:
                    t_args = _normalize_args(t_args, self.tools.get(t_name))
                    _tool_call_counts[t_name] = _tool_call_counts.get(t_name, 0) + 1

                    call_step = StepResult(
                        type="tool_call",
                        content=content,
                        tool_name=t_name,
                        tool_args=t_args,
                        elapsed_ms=elapsed,
                    )
                    run.steps.append(call_step)
                    self._emit(call_step)

                    result = self.tools.invoke(t_name, t_args)
                    result_str = str(result)

                    result_step = StepResult(type="tool_result", content=result_str, tool_name=t_name)
                    run.steps.append(result_step)
                    self._emit(result_step)

                    if not result_str.startswith("[Tool error]"):
                        _successful_results.append(f"{t_name} → {result_str}")

                    observation = content + f"\nObservation: {result_str}\n"
                    self.memory.add_assistant(observation)
                    continue

                if final_answer:
                    final_step = StepResult(type="final", content=final_answer, elapsed_ms=elapsed)
                    run.steps.append(final_step)
                    self._emit(final_step)
                    run.final_answer = final_answer
                    self.memory.add_assistant(content)
                    break

            # ---- Plain response (no tools or tool loop ended) -------- #
            # Native tool model answered in plain text after only 1 tool call.
            # If the original question likely needs more steps, nudge it to
            # call the next tool rather than guessing from memory.
            total_calls = sum(_tool_call_counts.values())
            if (
                self._native_tools
                and self.tools.all()
                and _successful_results
                and total_calls == 1
                and not tool_calls_raw
            ):
                results_so_far = "\n".join(f"- {r}" for r in _successful_results)
                self.memory.add_assistant(content)
                self.memory.add_user(
                    f"You have gathered so far:\n{results_so_far}\n\n"
                    f"The original question was: {user_input}\n\n"
                    "If the question requires further calculation, call the tool with the "
                    "correct next expression using the result above as input (do NOT pass "
                    "the raw result as the expression — compute something new with it). "
                    "Otherwise give your final answer in plain text."
                )
                continue

            # Detect: model output looks like a JSON tool schema even though
            # no tools are defined. Re-prompt once asking for plain text.
            if _looks_like_tool_schema(content) and not self.tools.all():
                self.memory.add_assistant(content)
                self.memory.add_user(
                    "Please answer in plain text only. "
                    "Do not output JSON or function call syntax."
                )
                retry = self.client.chat(
                    model=self.model,
                    messages=self.memory.to_messages(),
                    options=self.model_options,
                )
                content = retry.get("message", {}).get("content", "").strip() or content
                self.memory._history.pop()   # remove the nudge from memory
                self.memory._history.pop()   # remove the bad assistant turn

            final_step = StepResult(type="final", content=content, elapsed_ms=elapsed)
            run.steps.append(final_step)
            self._emit(final_step)
            run.final_answer = content
            self.memory.add_assistant(content)
            break

        else:
            # max_steps hit — try to salvage with synthesis
            run.success = False
            run.error = f"Exceeded max_steps ({self.max_steps})"
            if _successful_results:
                run.final_answer = self._synthesize(user_input, _successful_results)

        run.total_ms = (time.perf_counter() - t0) * 1000
        return run

    def _synthesize(self, user_input: str, results: list[str]) -> str:
        """
        Called when the model is stuck in a tool loop but we have good results.
        Makes one clean LLM call asking it to summarize what was found.
        """
        if not results:
            return "I was unable to complete this task with the available tools."

        results_text = "\n".join(f"- {r}" for r in results)
        synthesis_messages = self.memory.to_messages() + [{
            "role": "user",
            "content": (
                f"You have already gathered the following information using your tools:\n"
                f"{results_text}\n\n"
                f"Please now answer the original question directly using these results. "
                f"Do not call any more tools. Original question: {user_input}"
            ),
        }]
        try:
            response = self.client.chat(
                model=self.model,
                messages=synthesis_messages,
                options=self.model_options,
            )
            return response.get("message", {}).get("content", "").strip() or results_text
        except Exception:
            return results_text

    def chat(self, user_input: str) -> str:
        """Convenience wrapper — returns just the final answer string."""
        return self.run(user_input).final_answer

    def reset(self):
        """Clear conversation history (preserves system prompt)."""
        self.memory.clear()

    # ------------------------------------------------------------------ #
    #  Streaming                                                           #
    # ------------------------------------------------------------------ #

    def stream(self, user_input: str) -> Iterator[str]:
        """
        Yield text tokens as they arrive (no tool use in streaming mode).
        Suitable for simple Q&A agents where you want live output.
        """
        self.memory.add_user(user_input)
        chunks = self.client.chat(
            model=self.model,
            messages=self.memory.to_messages(),
            stream=True,
            options=self.model_options,
        )
        full = ""
        for chunk in chunks:
            token = chunk.get("message", {}).get("content", "")
            full += token
            yield token
        self.memory.add_assistant(full)

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _emit(self, step: StepResult):
        if self.on_step:
            self.on_step(step)