"""
examples/03_orchestrator.py
----------------------------
A three-agent team with a router that dispatches tasks.
Backend-agnostic (works with Ollama or BitNet).

Run from the project root:   python examples/03_orchestrator.py
Or from the examples folder: python 03_orchestrator.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import (
    Agent,
    Orchestrator,
    AgentCard,
    get_default_client,
    get_available_models,
    DEFAULT_MODEL,
    LOCALCLAW_BACKEND,
)
from localclaw.tools.builtins import BUILTIN_REGISTRY

BACKEND_NAME = LOCALCLAW_BACKEND.upper()

# ── Verify backend is running ──────────────────────────────────────
client = get_default_client()
if not client.is_running():
    print(f"❌  {BACKEND_NAME} is not running.")
    if LOCALCLAW_BACKEND == "bitnet":
        print("   Start llama-server from bitnet.cpp directory")
    else:
        print("   Start it with: ollama serve")
    sys.exit(1)

models = get_available_models(client)
if not models:
    print(f"❌  No models available.")
    sys.exit(1)

# ── Pick models ────────────────────────────────────────────────────
def _pick(preferences):
    """Pick the best available model from a preference list."""
    for p in preferences:
        for m in models:
            if p in m.lower():
                return m
    return models[0]

# For BitNet, just use whatever model is available
if LOCALCLAW_BACKEND == "bitnet":
    MAIN_MODEL = models[0]
    ROUTER_MODEL = models[0]
else:
    MAIN_MODEL   = _pick(["qwen2.5-coder", "llama3.1:8b", "llama3.2:3b", "qwen2.5:7b", "mistral", "qwen3.5:0.8b"])
    ROUTER_MODEL = _pick(["qwen2.5-coder", "llama3.2:3b", "qwen3.5:0.8b", "qwen2.5", MAIN_MODEL])

print(f"Using model: {MAIN_MODEL}  |  router: {ROUTER_MODEL}\n")

# ── Build specialist agents ────────────────────────────────────────
# NOTE: Small models (1b/3b) work best WITHOUT tools for generative tasks.
# They tend to output JSON schemas instead of code when tool schemas are present.
# Only give tools to agents that genuinely need to compute something.

coder = Agent(
    model=MAIN_MODEL,
    client=client,
    system_prompt=(
        "You are an expert software engineer. "
        "When asked to write code, respond with clean, working Python code in a code block. "
        "Include type hints and a brief docstring. Do not output JSON or schemas."
    ),
)

analyst = Agent(
    model=MAIN_MODEL,
    client=client,
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
    client=client,
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
