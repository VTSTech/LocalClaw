import sys
import os
import time
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, ToolRegistry, StepResult, get_default_client, LOCALCLAW_BACKEND
from localclaw.tools.builtins import BUILTIN_REGISTRY
from localclaw.acp_plugin import ACPPlugin

BACKEND_NAME = LOCALCLAW_BACKEND.upper()

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & MODELS
# ═══════════════════════════════════════════════════════════════════════════════

# Models discovered dynamically at runtime
MODELS_TO_TEST = []  # Will be populated from available models

QUERIES = [
    "Convert 500 JPY to EUR",
    "What is 17 to the power of 4?",
    "What is the weather in Tokyo?",
]

# ── Tool Definitions ─────────────────────────────────────────────
registry = ToolRegistry()

@registry.tool(
    description="Get the current weather for a city",
    param_descriptions={
        "city": "City name",
        "unit": "Temperature unit: 'celsius' or 'fahrenheit'",
    },
)
def get_weather(city: str, unit: str = "celsius") -> str:
    mock = {
        "london":    {"temp": 12, "condition": "cloudy"},
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
        "amount": "Numeric amount (e.g. 500)",
        "from_currency": "Source currency code (3 letters)",
        "to_currency": "Target currency code (3 letters)",
    },
)
def convert_currency(amount, from_currency: str = "USD", to_currency: str = "EUR") -> str:
    rates_to_usd = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "JPY": 0.0067, "CAD": 0.74}
    
    # Handle string amounts from tiny models
    if isinstance(amount, str):
        match = re.search(r'(\d+(?:\.\d+)?)', amount)
        amount = float(match.group(1)) if match else 0.0

    fc, tc = from_currency.upper(), to_currency.upper()
    if fc not in rates_to_usd or tc not in rates_to_usd:
        return f"Unknown currency. Supported: {list(rates_to_usd.keys())}"
    
    usd = float(amount) * rates_to_usd[fc]
    result = usd / rates_to_usd[tc]
    return f"{amount} {fc} ≈ {result:.2f} {tc}"

# Register built-in calculator
for t in BUILTIN_REGISTRY.subset(["calculator"]).all():
    registry.register(t)

# ═══════════════════════════════════════════════════════════════════════════════
# BENCHMARK RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def run_tool_benchmark(model_name, client):
    available = client.list_models()
    if model_name not in available:
        print(f"⏩ Skipping {model_name} (not found)")
        return

    # Initialize ACP specifically for this model iteration
    acp = ACPPlugin(
        agent_name="LocalClaw",
        model_name=model_name,
        debug=False,
    )
    acp.bootstrap(claim_primary=False)

    def print_step(step: StepResult):
        acp.on_step(step)
        icons = {"thought": "💭", "tool_call": "🔧", "tool_result": "📦", "final": "✅"}
        icon = icons.get(step.type, "•")
        if step.type == "tool_call":
            print(f"    {icon} Tool: {step.tool_name}")
        elif step.type == "final":
            print(f"    {icon} {step.content[:70]}...")

    print(f"\n{'='*60}")
    print(f"🛠️  TOOL TEST: {model_name}")
    print(f"{'='*60}")

    agent = Agent(
        model=model_name,
        client=client,
        tools=registry,
        system_prompt="You have tools. Use them to answer. Be concise.",
        on_step=print_step,
        model_options={"temperature": 0.0, "num_ctx": 2048},
    )

    for q in QUERIES:
        print(f"\nUser: {q}")
        acp.log_user_message(q)
        try:
            run = agent.run(q)
            acp.log_assistant_message(run.final_answer)
        except Exception as e:
            print(f"    ❌ Execution Error: {e}")

if __name__ == "__main__":
    client = get_default_client()
    if not client.is_running():
        print(f"❌ {BACKEND_NAME} is not running.")
        if LOCALCLAW_BACKEND == "bitnet":
            print("   Start llama-server from bitnet.cpp directory")
        else:
            print("   Start it with: ollama serve")
        sys.exit(1)

    # Get available models dynamically
    from localclaw.model_discovery import get_available_models
    available_models = get_available_models(client)
    MODELS_TO_TEST = available_models[:10] if available_models else []
    
    if not MODELS_TO_TEST:
        print(f"❌ No models available in {BACKEND_NAME}.")
        sys.exit(1)
    
    print(f"Testing {len(MODELS_TO_TEST)} models: {MODELS_TO_TEST}")

    for model in MODELS_TO_TEST:
        run_tool_benchmark(model, client)