"""
examples/02_tool_agent.py
--------------------------
An agent with custom + built-in tools.
Demonstrates the decorator-based tool registry.
Uses dynamic model discovery.

Run from the project root:   python examples/02_tool_agent.py
Or from the examples folder: python 02_tool_agent.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, ToolRegistry, StepResult, OllamaClient
from localclaw.tools.builtins import BUILTIN_REGISTRY
from localclaw.model_discovery import pick_best_model

# ── 1. Verify Ollama and pick model ──────────────────────────────────
client = OllamaClient()
if not client.is_running():
    print("❌  Ollama is not running. Start it with: ollama serve")
    sys.exit(1)

preferred = os.environ.get("LOCALCLAW_MODEL")
MODEL = pick_best_model(preferred=preferred, client=client)
if not MODEL:
    print("❌  No models available. Pull one with: ollama pull qwen2.5-coder:0.5b")
    sys.exit(1)

print(f"✓  Using model: {MODEL}\n")

# ── 2. Define custom tools ─────────────────────────────────────────
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
    description="Convert currency amounts. Supports USD, EUR, GBP, JPY, CAD.",
    param_descriptions={
        "amount": "The numeric amount to convert",
        "from_currency": "Source currency code: USD, EUR, GBP, JPY, or CAD",
        "to_currency": "Target currency code: USD, EUR, GBP, JPY, or CAD",
    },
)
def convert_currency(amount, from_currency: str = "USD", to_currency: str = "EUR") -> str:
    """Approximate currency conversion."""
    import re
    
    rates_to_usd = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "JPY": 0.0067, "CAD": 0.74}
    
    # Fuzzy handling for amount
    if isinstance(amount, str):
        match = re.match(r'(\d+(?:\.\d+)?)\s*([A-Z]{3})?', amount.upper())
        if match:
            amount = float(match.group(1))
            if match.group(2) and from_currency == "USD":
                from_currency = match.group(2)
        else:
            try:
                amount = float(amount)
            except ValueError:
                return f"Error: Could not parse amount '{amount}'."
    
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return f"Error: Amount must be a number, got '{amount}'"
    
    fc, tc = from_currency.upper(), to_currency.upper()
    
    unknown = []
    if fc not in rates_to_usd:
        unknown.append(fc)
    if tc not in rates_to_usd:
        unknown.append(tc)
    if unknown:
        return f"Unknown currency: {', '.join(unknown)}. Supported: USD, EUR, GBP, JPY, CAD"
    
    usd = amount * rates_to_usd[fc]
    result = usd / rates_to_usd[tc]
    return f"{amount} {fc} ≈ {result:.2f} {tc}"


# ── 3. Also include the built-in calculator ─────────────────────────
for t in BUILTIN_REGISTRY.subset(["calculator"]).all():
    registry.register(t)

# ── 4. Live step hook for a nice trace ─────────────────────────────
def print_step(step: StepResult):
    icons = {"thought": "💭", "tool_call": "🔧", "tool_result": "📦", "final": "✅"}
    icon = icons.get(step.type, "•")
    if step.type == "tool_call":
        print(f"  {icon} Calling {step.tool_name}({step.tool_args})")
    elif step.type == "tool_result":
        print(f"  {icon} Result: {step.content}")
    elif step.type == "thought":
        print(f"  {icon} {step.content[:120]}")


# ── 5. Build the agent ─────────────────────────────────────────────
agent = Agent(
    model=MODEL,
    tools=registry,
    system_prompt=(
        "You are a helpful assistant with access to tools. "
        "Call tools when needed. Give brief final answers after getting results."
    ),
    on_step=print_step,
    model_options={
        "temperature": 0.0,
        "num_ctx": 1024,
        "num_predict": 256,
    },
)

print(f"=== Multi-tool agent demo ({agent.model}) ===\n")

queries = [
    "Convert 500 JPY to EUR",
    "What is 17 to the power of 4?",
]

for q in queries:
    agent.reset()
    print(f"User: {q}")
    run = agent.run(q)
    print(f"\nFinal: {run.final_answer}")
    print(f"Took {run.total_ms:.0f}ms | {len(run.steps)} steps\n")
    print("-" * 60 + "\n")
