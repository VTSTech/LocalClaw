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

from localclaw import Agent, Orchestrator, AgentCard
from localclaw.tools.builtins import BUILTIN_REGISTRY

# ── Build specialist agents ────────────────────────────────────────

coder = Agent(
    model="llama3.1:8b",
    tools=BUILTIN_REGISTRY.subset(["python_repl", "shell", "read_file", "write_file"]),
    system_prompt=(
        "You are an expert software engineer. Write clean, well-commented code. "
        "Use the python_repl tool to verify your solutions when helpful."
    ),
)

analyst = Agent(
    model="llama3.1:8b",
    tools=BUILTIN_REGISTRY.subset(["calculator", "python_repl"]),
    system_prompt=(
        "You are a data analyst and mathematician. Break down problems step-by-step. "
        "Show your work. Use the calculator or python_repl for computations."
    ),
)

writer = Agent(
    model="llama3.1:8b",
    system_prompt=(
        "You are a skilled writer. Produce clear, well-structured prose. "
        "Adapt tone to context: professional for business, friendly for casual."
    ),
)

# ── Build the orchestrator ─────────────────────────────────────────

orch = Orchestrator(
    agents=[
        AgentCard("coder",   coder,   "Writing, debugging, and explaining code"),
        AgentCard("analyst", analyst, "Math problems, data analysis, statistics"),
        AgentCard("writer",  writer,  "Writing emails, summaries, creative content"),
    ],
    router_model="llama3.2:3b",  # fast small model for routing
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
    print(f"Answer: {result.final_answer[:400]}...")
    print(f"Time: {result.total_ms:.0f}ms\n")
    print("=" * 70 + "\n")