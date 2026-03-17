"""
examples/03_orchestrator_acp.py
------------------------------
A three-agent team with a router — with ACP integration.

Demonstrates:
- Multiple agents logging to same ACP session
- Per-agent token tracking
- Agent attribution in activity logs

Run from the project root:   python examples/03_orchestrator_acp.py
Or from the examples folder: python 03_orchestrator_acp.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, Orchestrator, AgentCard, get_default_client, LOCALCLAW_BACKEND
from localclaw.tools.builtins import BUILTIN_REGISTRY
from localclaw.acp_plugin import ACPPlugin
from localclaw.model_discovery import pick_best_model

BACKEND_NAME = LOCALCLAW_BACKEND.upper()

# ── Detect which model to use ──────────────────────────────────────
_client = get_default_client()
_models = _client.list_models()

MAIN_MODEL = pick_best_model(preferred=os.environ.get("LOCALCLAW_MODEL"), client=_client)
ROUTER_MODEL = MAIN_MODEL  # Use same model for router in simple cases

if not MAIN_MODEL:
    print(f"❌ {BACKEND_NAME} is not running or has no models.")
    if LOCALCLAW_BACKEND == "bitnet":
        print("   Start llama-server from bitnet.cpp directory")
    else:
        print("   Start it with: ollama serve")
    sys.exit(1)

print(f"Using model: {MAIN_MODEL}  |  router: {ROUTER_MODEL}\n")

# ── Create shared ACP plugin ───────────────────────────────────────
acp = ACPPlugin(
    agent_name="LocalClaw-Orchestrator",
    model_name=ROUTER_MODEL,
    debug=os.environ.get("ACP_DEBUG", "").lower() in ("1", "true"),
)

bootstrap = acp.bootstrap(claim_primary=False)
print(f"ACP: {'connected' if bootstrap.get('status') else 'unavailable'}")

# Log bootstrap activity
acp.log_chat("system", f"Orchestrator initialized with {MAIN_MODEL}", complete=True)
print()

# ── Build specialist agents with ACP attribution ────────────────────

coder = Agent(
    model=MAIN_MODEL,
    client=_client,
    system_prompt=(
        "You are an expert software engineer. "
        "When asked to write code, respond with clean, working Python code in a code block. "
        "Include type hints and a brief docstring. Do not output JSON or schemas."
    ),
)

analyst = Agent(
    model=MAIN_MODEL,
    client=_client,
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
    client=_client,
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

# ── Run tasks with ACP logging ─────────────────────────────────────

tasks = [
    "Write a Python function that implements binary search with type hints",
    "If I invest $5000 at 7% annual return compounded monthly, how much will I have after 10 years?",
    "Write a short professional email declining a meeting invitation",
]

for task in tasks:
    print(f"Task: {task}")
    
    # Log task to ACP
    acp.log_user_message(task)
    
    result = orch.run(task)
    
    # Log result to ACP
    acp.log_assistant_message(result.final_answer[:500])
    
    print(f"Routed to: [{result.chosen_agent}]")
    print(f"Answer:\n{result.final_answer}")
    print(f"\nTime: {result.total_ms:.0f}ms")
    print("=" * 70 + "\n")

# Show per-agent token breakdown
print("ACP Agent Tokens:")
agent_tokens = acp.get_agent_tokens()
for agent_name, tokens in agent_tokens.items():
    print(f"   {agent_name}: {tokens} tokens")
