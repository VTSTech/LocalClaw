"""
examples/02_tool_agent.py
--------------------------
An agent with custom + built-in tools.
Demonstrates the decorator-based tool registry.

Run from the project root:   python examples/02_tool_agent.py
Or from the examples folder: python 02_tool_agent.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, ToolRegistry, StepResult
from localclaw.tools.builtins import BUILTIN_REGISTRY

# ── 1. Define custom tools ─────────────────────────────────────────
registry = ToolRegistry()

@registry.tool(
    description="Get the current weather for a city (mock data for this example)",
    param_descriptions={
        "city": "City name",
        "unit": "Temperature unit: 'celsius' or 'fahrenheit'",
    },
)
def get_weather(city: str, unit: str = "celsius") -> str:
    """Return mock weather data."""
    mock = {
        "london":   {"temp": 12, "condition": "cloudy"},
        "new york": {"temp": 22, "condition": "sunny"},
        "tokyo":    {"temp": 28, "condition": "humid"},
    }
    data = mock.get(city.lower(), {"temp": 20, "condition": "unknown"})
    temp = data["temp"]
    if unit == "fahrenheit":
        temp = temp * 9 / 5 + 32
    return f"{city}: {temp}°{'C' if unit == 'celsius' else 'F'}, {data['condition']}"


@registry.tool(
    description="Convert currency amounts using approximate exchange rates",
    param_descriptions={
        "amount": "Amount to convert",
        "from_currency": "Source currency code (USD, EUR, GBP, JPY)",
        "to_currency": "Target currency code",
    },
)
def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Approximate currency conversion."""
    rates_to_usd = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "JPY": 0.0067, "CAD": 0.74}
    fc, tc = from_currency.upper(), to_currency.upper()
    if fc not in rates_to_usd or tc not in rates_to_usd:
        return f"Unknown currency: {fc} or {tc}"
    usd = amount * rates_to_usd[fc]
    result = usd / rates_to_usd[tc]
    return f"{amount} {fc} ≈ {result:.2f} {tc}"


# ── 2. Also include the built-in calculator ─────────────────────────
for t in BUILTIN_REGISTRY.subset(["calculator"]).all():
    registry.register(t)

# ── 3. Live step hook for a nice trace ─────────────────────────────
def print_step(step: StepResult):
    icons = {"thought": "💭", "tool_call": "🔧", "tool_result": "📦", "final": "✅"}
    icon = icons.get(step.type, "•")
    if step.type == "tool_call":
        print(f"  {icon} Calling {step.tool_name}({step.tool_args})")
    elif step.type == "tool_result":
        print(f"  {icon} Result: {step.content}")
    elif step.type == "thought":
        print(f"  {icon} {step.content[:120]}")


# ── 4. Build the agent ─────────────────────────────────────────────
agent = Agent(
    model="qwen2.5-coder:0.5b-instruct-q4_k_m",       # or qwen2.5:7b, mistral:7b, etc.
    tools=registry,
    system_prompt=(
        "You are a helpful assistant with access to tools. "
        "Use the appropriate tool ONCE to answer each part of the question, "
        "then give your final answer in plain text. "
        "Do not repeat tool calls or verify results with additional tools."
    ),
    on_step=print_step,
    model_options={"temperature": 0.2},
)

print("=== Multi-tool agent demo ===\n")

queries = [
    "What's the weather in Tokyo, and how much is 500 JPY in EUR?",
    "What is 17 ** 4, and what's the square root of that?",
]

for q in queries:
    print(f"User: {q}")
    run = agent.run(q)
    print(f"\nFinal: {run.final_answer}")
    print(f"Took {run.total_ms:.0f}ms | {len(run.steps)} steps\n")
    print("-" * 60 + "\n")