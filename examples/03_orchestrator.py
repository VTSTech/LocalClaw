"""
examples/03_orchestrator.py
----------------------------
A three-agent team with a router that dispatches tasks.

Run from the project root:   python examples/03_orchestrator.py
Or from the examples folder: python 03_orchestrator.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, Orchestrator, AgentCard, OllamaClient
from localclaw.tools.builtins import BUILTIN_REGISTRY

# ── Detect which model to use ──────────────────────────────────────
_client = OllamaClient()
_models = _client.list_models()

def _pick(preferences):
    """Pick the best available model from a preference list."""
    for p in preferences:
        for m in _models:
            if p in m.lower():
                return m
    return _models[0] if _models else "qwen2.5-coder:0.5b-instruct-q4_k_m"

MAIN_MODEL   = _pick(["llama3.1:8b", "llama3.2:3b", "qwen2.5:7b", "mistral", "qwen3.5:0.8b"])
ROUTER_MODEL = _pick(["llama3.2:3b", "qwen3.5:0.8b", "qwen2.5", MAIN_MODEL])

print(f"Using model: {MAIN_MODEL}  |  router: {ROUTER_MODEL}\n")

# ── Build specialist agents ────────────────────────────────────────
# NOTE: Small models (1b/3b) work best WITHOUT tools for generative tasks.
# They tend to output JSON schemas instead of code when tool schemas are present.
# Only give tools to agents that genuinely need to compute something.

coder = Agent(
    model=MAIN_MODEL,
    system_prompt=(
        "You are an expert software engineer. "
        "When asked to write code, respond with clean, working Python code in a code block. "
        "Include type hints and a brief docstring. Do not output JSON or schemas."
    ),
)

analyst = Agent(
    model=MAIN_MODEL,
    tools=BUILTIN_REGISTRY.subset(["calculator"]),
    system_prompt=(
        "You are a data analyst and mathematician. "
        "Break down problems step-by-step and show your reasoning. "
        "Use the calculator tool for arithmetic. "
        "After getting a result, state your final answer in plain text."
    ),
)

writer = Agent(
    model=MAIN_MODEL,
    system_prompt=(
        "You are a skilled writer. Produce clear, well-structured prose. "
        "Adapt tone to context: professional for business, friendly for casual. "
        "Respond in plain text only."
    ),
)

# ── Build the orchestrator ─────────────────────────────────────────

orch = Orchestrator(
    agents=[
        AgentCard("coder",   coder,   "Writing, debugging, and explaining code and programming tasks"),
        AgentCard("analyst", analyst, "Math, arithmetic, financial calculations, statistics, numbers"),
        AgentCard("writer",  writer,  "Writing emails, essays, summaries, and creative or professional prose"),
    ],
    router_model=ROUTER_MODEL,
    mode="router",
)

# ── Run some tasks ─────────────────────────────────────────────────

tasks = [
    "Write a Python function that implements binary search with type hints",
    "If I invest $5000 at 7% annual return compounded monthly, how much will I have after 10 years?",
    "Write a short professional email declining a meeting invitation",
]

for task in tasks:
    print(f"Task: {task}")
    result = orch.run(task)
    print(f"Routed to: [{result.chosen_agent}]")
    print(f"Answer:\n{result.final_answer}")
    print(f"\nTime: {result.total_ms:.0f}ms")
    print("=" * 70 + "\n")