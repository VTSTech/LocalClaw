"""
examples/02_tool_agent_acp.py
-----------------------------
An agent with custom + built-in tools — with ACP integration.

Demonstrates:
- ACP plugin attached to on_step callback
- Tool calls logged automatically to ACP
- Hints and nudge handling

Run from the project root:   python examples/02_tool_agent_acp.py
Or from the examples folder: python 02_tool_agent_acp.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, ToolRegistry, StepResult
from localclaw.tools.builtins import BUILTIN_REGISTRY
from localclaw.acp_plugin import ACPPlugin

# ── 1. Create ACP plugin and bootstrap ─────────────────────────────
acp = ACPPlugin(
    agent_name="LocalClaw-ToolAgent",
    model_name=os.environ.get("LOCALCLAW_MODEL", "qwen2.5-coder:0.5b"),
    debug=os.environ.get("ACP_DEBUG", "").lower() in ("1", "true"),
    on_hint=lambda h: print(f"   💡 Hint: {h}"),
    on_nudge=lambda n: print(f"   📢 Nudge: {n.get('message', '')}"),
)

bootstrap = acp.bootstrap(claim_primary=False)
print(f"ACP: {'connected' if bootstrap.get('status') else 'unavailable'}\n")

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
    description="Convert currency amounts. Use format: convert 500 JPY to EUR. Supports USD, EUR, GBP, JPY, CAD.",
    param_descriptions={
        "amount": "REQUIRED: The numeric amount to convert (e.g., 500, not '500 JPY')",
        "from_currency": "Source currency code: USD, EUR, GBP, JPY, or CAD",
        "to_currency": "Target currency code: USD, EUR, GBP, JPY, or CAD",
    },
)
def convert_currency(amount, from_currency: str = "USD", to_currency: str = "EUR") -> str:
    """
    Approximate currency conversion with fuzzy argument handling.
    
    Handles common mistakes from small models:
    - String amounts like "500" or "500 JPY"
    - Missing currency parameters
    """
    import re
    
    rates_to_usd = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "JPY": 0.0067, "CAD": 0.74}
    
    # ── Fuzzy handling for amount ─────────────────────────────────
    if isinstance(amount, str):
        # Try to extract number from "500 JPY" pattern
        match = re.match(r'(\d+(?:\.\d+)?)\s*([A-Z]{3})?', amount.upper())
        if match:
            amount = float(match.group(1))
            if match.group(2) and from_currency == "USD":
                from_currency = match.group(2)
        else:
            try:
                amount = float(amount)
            except ValueError:
                return f"Error: Could not parse amount '{amount}'. Please provide a number."
    
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return f"Error: Amount must be a number, got '{amount}'"
    
    # ── Validate currencies ───────────────────────────────────────
    fc, tc = from_currency.upper(), to_currency.upper()
    unknown = []
    if fc not in rates_to_usd:
        unknown.append(fc)
    if tc not in rates_to_usd:
        unknown.append(tc)
    if unknown:
        return f"Unknown currency: {', '.join(unknown)}. Supported: USD, EUR, GBP, JPY, CAD"
    
    # ── Perform conversion ────────────────────────────────────────
    usd = amount * rates_to_usd[fc]
    result = usd / rates_to_usd[tc]
    return f"{amount} {fc} ≈ {result:.2f} {tc}"


# Include the built-in calculator
for t in BUILTIN_REGISTRY.subset(["calculator"]).all():
    registry.register(t)


# ── 3. Combined step hook: ACP + local printing ────────────────────
def print_step(step: StepResult):
    """Print step info AND log to ACP."""
    # Log to ACP
    acp.on_step(step)
    
    # Print locally
    icons = {"thought": "💭", "tool_call": "🔧", "tool_result": "📦", "final": "✅"}
    icon = icons.get(step.type, "•")
    if step.type == "tool_call":
        print(f"  {icon} Calling {step.tool_name}({step.tool_args})")
    elif step.type == "tool_result":
        print(f"  {icon} Result: {step.content}")
    elif step.type == "thought":
        print(f"  {icon} {step.content[:120]}")


# ── 4. Build the agent with ACP integration ────────────────────────
MODEL = os.environ.get("LOCALCLAW_MODEL", "qwen2.5-coder:0.5b-instruct-q4_k_m")

agent = Agent(
    model=MODEL,
    tools=registry,
    system_prompt=(
        "You are a helpful assistant with access to tools. "
        "Call tools when needed. Give brief final answers after getting results."
    ),
    on_step=print_step,  # Combined callback
    model_options={
        "temperature": 0.0,
        "num_ctx": 1024,
        "num_predict": 256,
    },
)

print(f"=== Multi-tool agent demo with ACP ({agent.model}) ===\n")

# Use simpler, single-tool prompts for small models (≤1B parameters)
# Complex multi-part prompts can confuse small models
queries = [
    # Simple single-tool prompts work best with small models
    "Convert 500 JPY to EUR",
    "What is 17 to the power of 4?",
    # Multi-tool prompts work better with larger models (>3B)
    # "What's the weather in Tokyo, and how much is 500 JPY in EUR?",  # May fail on 0.5B
]

for q in queries:
    agent.reset()
    print(f"User: {q}")
    
    # Log user message to ACP
    acp.log_user_message(q)
    
    run = agent.run(q)
    
    # Log assistant message to ACP
    acp.log_assistant_message(run.final_answer)
    
    print(f"\nFinal: {run.final_answer}")
    print(f"Took {run.total_ms:.0f}ms | {len(run.steps)} steps\n")
    print("-" * 60 + "\n")

# Show ACP stats
status = acp.get_status()
print(f"ACP Session tokens: {status.get('session_tokens', 0)}")
print(f"Agent tokens: {acp.get_agent_tokens()}")
