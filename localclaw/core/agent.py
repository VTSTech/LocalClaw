"""
LocalClaw — Agent
Core ReAct agent that drives the think → act → observe loop.

Supports:
  • Native Ollama tool-calling (for models that expose it)
  • Text-based ReAct fallback (for models without native tool support)
  • Streaming output
  • Hooks for custom logging / UI
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

                    result_step = StepResult(
                        type="tool_result",
                        content=result_str,
                        tool_name=t_name,
                    )
                    run.steps.append(result_step)
                    self._emit(result_step)

                    self.memory.add_tool_result(t_name, result_str)

                continue  # loop back to get the next assistant message

            # ---- ReAct text parsing ---------------------------------- #
            if not self._native_tools and self.tools.all():
                thought, t_name, t_args, final_answer = _parse_react(content)

                if thought:
                    step = StepResult(type="thought", content=thought, elapsed_ms=elapsed)
                    run.steps.append(step)
                    self._emit(step)

                if t_name and t_args is not None:
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

                    # Feed observation back
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
            final_step = StepResult(type="final", content=content, elapsed_ms=elapsed)
            run.steps.append(final_step)
            self._emit(final_step)
            run.final_answer = content
            self.memory.add_assistant(content)
            break

        else:
            run.success = False
            run.error = f"Exceeded max_steps ({self.max_steps})"

        run.total_ms = (time.perf_counter() - t0) * 1000
        return run

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
