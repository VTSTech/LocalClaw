# LocalClaw 🦞

A minimal, hackable agentic framework engineered to run **entirely locally** with [Ollama](https://ollama.com).

Inspired by the architecture of OpenClaw, rebuilt from scratch for local-first operation.

**Written by [VTSTech](https://www.vts-tech.org)** · [GitHub](https://github.com/VTSTech/LocalClaw)

---

## Architecture

```
localclaw/
├── core/
│   ├── ollama_client.py   # Thin HTTP wrapper around the Ollama API
│   ├── tools.py           # Decorator-based tool registry + JSON schema generation
│   ├── memory.py          # Sliding-window conversation memory with summarization
│   ├── agent.py           # ReAct loop — native tool-call + text-fallback modes
│   └── orchestrator.py    # Multi-agent routing (router / pipeline / parallel)
├── tools/
│   └── builtins.py        # Ready-to-use tools: calculator, shell, file I/O, HTTP, REPL
└── examples/
    ├── 01_basic_agent.py      # Simple Q&A demo
    ├── 02_tool_agent.py       # Tool calling demo
    ├── 03_orchestrator.py     # Multi-agent routing demo
    ├── 04_comprehensive_test.py  # Full test suite
    ├── 05_tool_tests.py       # Tool-specific tests
    ├── 06_interactive_chat.py # Interactive CLI chat
    ├── 07_model_comparison.py # Compare models on 15 tests (3 per category)
    └── 08_robust_comparison.py # Progress-saving comparison for unstable connections
```

### Core design decisions

| Concern | Approach |
|---|---|
| **Tool calling** | Native Ollama tool-call protocol when supported; automatic ReAct text-parsing fallback for other models |
| **Memory** | Sliding window — older turns are archived and optionally compressed via LLM summarization |
| **Tools** | Decorator-based, auto-generates JSON schemas from Python type hints |
| **Orchestration** | Router (LLM picks agent), Pipeline (chain), or Parallel (concurrent + merge) |
| **Streaming** | First-class via generator interface |

---

## Installation

```bash
# Clone / copy the localclaw directory into your project, then:
pip install httpx

# Make sure Ollama is running:
ollama serve

# Pull a model:
ollama pull llama3.1:8b
```

---

## Quick start

### 1. Simple chat agent

```python
from localclaw import Agent

agent = Agent(
    model="llama3.1:8b",
    system_prompt="You are a helpful assistant.",
)

print(agent.chat("What is the capital of Japan?"))

# Streaming
for token in agent.stream("Tell me a joke."):
    print(token, end="", flush=True)
```

### 2. Agent with tools

```python
from localclaw import Agent, ToolRegistry

registry = ToolRegistry()

@registry.tool(description="Get the price of a stock ticker")
def get_stock_price(ticker: str) -> str:
    # your real implementation here
    return f"{ticker}: $142.50"

agent = Agent(
    model="llama3.1:8b",
    tools=registry,
    system_prompt="You are a financial assistant.",
)

run = agent.run("What's the price of AAPL?")
print(run.final_answer)
run.print_trace()   # shows all steps
```

### 3. Built-in tools

```python
from localclaw import Agent
from localclaw.tools.builtins import BUILTIN_REGISTRY

# All built-ins: calculator, python_repl, shell, read_file,
#                write_file, list_directory, http_get, save_note, get_note

agent = Agent(
    model="llama3.1:8b",
    tools=BUILTIN_REGISTRY,
)

agent.run("Write a Python script to fibonacci.py that prints the first 20 Fibonacci numbers, then run it")
```

### 4. Multi-agent orchestration

```python
from localclaw import Agent, Orchestrator, AgentCard

coder  = Agent(model="llama3.1:8b", system_prompt="You write code.")
writer = Agent(model="llama3.1:8b", system_prompt="You write prose.")

orch = Orchestrator(
    agents=[
        AgentCard("coder",  coder,  "Writing and explaining code"),
        AgentCard("writer", writer, "Writing documents and emails"),
    ],
    router_model="llama3.2:3b",
)

result = orch.run("Write a Python function that reverses a string")
print(result.chosen_agent, result.final_answer)
```

---

## Tool registry

Tools are plain Python functions decorated with `@registry.tool()`.

```python
from localclaw import ToolRegistry

reg = ToolRegistry()

@reg.tool(
    description="Search a local SQLite database",
    param_descriptions={
        "query": "SQL SELECT query to run",
        "db_path": "Path to the .db file",
    },
)
def sqlite_query(query: str, db_path: str = "data.db") -> str:
    import sqlite3
    conn = sqlite3.connect(db_path)
    rows = conn.execute(query).fetchall()
    return str(rows)
```

The registry auto-generates the JSON schema from type hints. Optional parameters (those with defaults) are marked `required: false` in the schema.

Use `registry.subset(["tool_a", "tool_b"])` to give different agents different tool subsets.

---

## Memory

```python
from localclaw import Memory

mem = Memory(
    system_prompt="You are a helpful assistant.",
    max_turns=20,                       # sliding window size
    summary_model_fn=my_summarizer,     # optional: LLM-based compression
)
```

When the window fills, older turns are archived. If `summary_model_fn` is provided, it is called with the archived text and the summary is injected back into the system prompt.

---

## Agent options

```python
agent = Agent(
    model="qwen2.5:14b",
    tools=registry,
    system_prompt="...",
    max_steps=15,                    # max tool-call iterations
    force_react=False,               # force text-based ReAct even for capable models
    on_step=my_callback,             # called after each step (for UIs / logging)
    model_options={                  # passed directly to Ollama
        "temperature": 0.1,
        "num_ctx": 8192,
        "top_p": 0.9,
    },
    memory_max_turns=30,
)
```

---

## Supported models (tool-calling)

The following model families support native tool calling in Ollama and are auto-detected:

- `llama3.1`, `llama3.2`, `llama3-groq-tool-use`
- `mistral`, `mixtral`, `mistral-nemo`
- `qwen2`, `qwen2.5`, `qwen2.5-coder`
- `command-r`
- `hermes` (function calling variants)
- `nemotron`

All other models fall back to **ReAct text-parsing** automatically.

---

## Tested Small Models (≤1.5B parameters)

The following models have been tested with a **15-test benchmark** (3 tests per category: Math, Reasoning, Knowledge, Calc Tool, Code):

### Rankings

| Rank | Model | Score | Time | Math | Reason | Know | Calc | Code |
|:----:|-------|------:|-----:|:----:|:------:|:----:|:----:|:----:|
| 🥇 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | **12/15 (80%)** | 210s | **3/3** | 1/3 | **3/3** | **3/3** | 2/3 |
| 🥈 | `llama3.2:1b` | **12/15 (80%)** | 331s | **3/3** | 1/3 | 2/3 | **3/3** | **3/3** |
| 🥉 | `qwen2-math:1.5b` | **12/15 (80%)** | 611s | **3/3** | **3/3** | **3/3** | ❌ | **3/3** |
| 4 | `gemma3:270m` | 10/15 (67%) | 73s | **3/3** | 0/3 | 2/3 | 2/3 | **3/3** |
| 5 | `qwen2.5:0.5b` | 10/15 (67%) | 107s | 1/3 | **3/3** | **3/3** | 0/3 | **3/3** |
| 6 | `tinyllama:latest` | 9/15 (60%) | 587s | 2/3 | 2/3 | **3/3** | 0/3 | 2/3 |
| 7 | `qwen3:0.6b` | 9/15 (60%) | 595s | 2/3 | **3/3** | 2/3 | 0/3 | 2/3 |
| 8 | `granite4:350m` | 8/15 (53%) | 83s | 2/3 | 1/3 | 2/3 | 0/3 | **3/3** |
| 9 | `granite3.1-moe:1b` | 8/15 (53%) | 435s | 2/3 | 1/3 | **3/3** | 0/3 | 2/3 |
| 10 | `smollm:135m` | 7/15 (47%) | 285s | 0/3 | 2/3 | 2/3 | 0/3 | **3/3** |
| 11 | `functiongemma:270m` | 1/15 (7%) | 90s | 0/3 | 0/3 | 0/3 | 0/3 | 1/3 |

> **Note**: `qwen2-math:1.5b` Calc tests failed with HTTP 400 (model doesn't support native tool calling)

### Model Details

| Model | Params | Size | Speed | Tool Support | Notes |
|-------|--------|------|-------|--------------|-------|
| `qwen2.5-coder:0.5b` | 494M | ~400MB | ⚡ Fast | ✅ Native | **Best overall** - fastest winner, great tools |
| `llama3.2:1b` | 1.2B | ~1.3GB | 🐢 Medium | ✅ Native | Strong all-rounder, perfect Code |
| `qwen2-math:1.5b` | 1.5B | ~935MB | 🐢 Slow | ❌ No tools | **4 perfect categories!** No tool support |
| `gemma3:270m` | 270M | ~292MB | ⚡⚡ Fastest | ⚠️ Text | **Math & Code champion** - tiny but capable |
| `qwen2.5:0.5b` | 494M | ~398MB | ⚡ Fast | ⚠️ Text | **Reasoning & Knowledge champ**, Calc fails |
| `tinyllama:latest` | 1.1B | ~638MB | 🐢 Slow | ⚠️ Text | Older model, verbose, unstable |
| `qwen3:0.6b` | 600M | ~523MB | 🐢 Slow | ⚠️ Text | Perfect reasoning but Calc returns empty |
| `granite4:350m` | 350M | ~708MB | ⚡ Fast | ❌ Refused | **Refuses calculator** - safety filter |
| `granite3.1-moe:1b` | 1B MoE | ~1.4GB | 🐢 Slow | ✅ Native | HTTP 500 errors, unstable |
| `smollm:135m` | 135M | ~92MB | ⚡ Fast | ❌ None | **Smallest** - hallucinates math (7×8=42!) |
| `functiongemma:270m` | 270M | ~301MB | ⚡ Fast | ❌ Broken | **Worst performer** - refuses most tasks |

### Category Champions

| Category | Champion | Score | Notes |
|----------|----------|-------|-------|
| **Math** | `gemma3:270m` 🏆 | 3/3 | 270M params - impressive! |
| **Reasoning** | `qwen2.5:0.5b`, `qwen3:0.6b`, `qwen2-math` 🏆 | 3/3 | Qwen family excels |
| **Knowledge** | `qwen2.5:0.5b`, `qwen2-math` 🏆 | 3/3 | Multiple perfect scores |
| **Calc** | `qwen2.5-coder`, `llama3.2` 🏆 | 3/3 | Only models with 100% tool usage |
| **Code** | `gemma3:270m` 🏆 | 3/3 | Tiny but generates valid Python |

### Test Categories

| Category | Tests | What it measures |
|----------|-------|------------------|
| **Math** | Multiply, Add, Divide | Basic arithmetic without tools |
| **Reasoning** | Apples, Sequence, Logic | Multi-step reasoning and deduction |
| **Knowledge** | Japan, France, Brazil capitals | World knowledge recall |
| **Calc** | Multiply, Divide, Power | Tool usage with calculator |
| **Code** | is_even, reverse, max_num | Python function generation |

### Recommendations

| Use Case | Recommended Model | Why |
|----------|-------------------|-----|
| **General use** | `qwen2.5-coder:0.5b-instruct-q4_k_m` | Best overall, fastest winner, great tools |
| **Math tasks** | `gemma3:270m` or `qwen2-math:1.5b` | Perfect score, gemma fastest |
| **Reasoning tasks** | `qwen2.5:0.5b` or `qwen2-math:1.5b` | Perfect reasoning, qwen2.5 faster |
| **Quality over speed** | `llama3.2:1b` or `qwen2-math:1.5b` | Ties for best, more capable |
| **Tool usage** | `qwen2.5-coder:0.5b` or `llama3.2:1b` | Only models with 100% Calc |
| **Fastest inference** | `gemma3:270m` | 270M params, ~73s total |
| **No tools needed** | `qwen2-math:1.5b` | 4/5 categories perfect |
| **Smallest footprint** | `smollm:135m` | 92MB - but expect hallucinations |

### ⚠️ Models to Avoid

| Model | Issue |
|-------|-------|
| `functiongemma:270m` | Despite the name, terrible at function calling - returns empty or refuses |
| `smollm:135m` | Hallucinates wrong math (7×8=42), only 7/15 score |
| `granite4:350m` | Refuses calculator tools (safety filter) |

### Known Issues with Small Models

1. **Tool calling variations**:
   - `granite4:350m`: Refuses calculator ("I'm sorry, but I can't assist with that")
   - `functiongemma:270m`: Asks for clarification instead of using tools
   - `qwen2.5:0.5b`, `qwen3:0.6b`: Returns empty responses on Calc tests
   - `qwen2-math:1.5b`: HTTP 400 - doesn't support tool calling at all
2. **Math hallucinations**: `smollm:135m` says "7×8=42", `tinyllama` says "7×8=45"
3. **Power operator confusion**: `gemma3:270m` reads `2**10` as `2*10=20`
4. **Reasoning failures**: Some models answer "8" for sequence "2,4,6,8,?" (repeat last)
5. **Stability issues**:
   - `granite3.1-moe:1b`: HTTP 500 crashes
   - `tinyllama`, `qwen3:0.6b`: HTTP 524 timeouts
6. **Empty responses**: `functiongemma:270m` returns empty strings on most tests

---

## Orchestrator modes

| Mode | Behaviour |
|---|---|
| `router` | A small routing LLM picks the best agent for each request |
| `pipeline` | Agents run sequentially — each receives the previous agent's output |
| `parallel` | All agents run concurrently; results are merged with attribution |

---

## Running the examples

```bash
# Make sure Ollama is serving and you have a model pulled
ollama pull qwen2.5-coder:0.5b-instruct-q4_k_m

# Or use a remote Ollama instance by editing localclaw/core/ollama_client.py

# Run examples
python examples/01_basic_agent.py
python examples/02_tool_agent.py
python examples/03_orchestrator.py

# Test suite
python examples/04_comprehensive_test.py
python examples/05_tool_tests.py

# Interactive chat
python examples/06_interactive_chat.py

# Model comparison (15 tests per model)
python examples/07_model_comparison.py

# Robust comparison (saves progress, good for unstable connections)
python examples/08_robust_comparison.py
```

### Remote Ollama Configuration

To use a remote Ollama instance, edit `localclaw/core/ollama_client.py`:

```python
# LOCAL OLLAMA (default):
# DEFAULT_BASE_URL = "http://localhost:11434"
#
# REMOTE OLLAMA (cloudflare tunnel):
DEFAULT_BASE_URL = "https://your-tunnel.trycloudflare.com"

# Timeout for remote connections (30 minutes recommended)
DEFAULT_TIMEOUT = 1800.0
```

---

## Recent Improvements

### Small Model Support

LocalClaw now handles quirks of small models (≤1B parameters):

- **Fuzzy tool name matching**: Hallucinated tool names like `calculate_expression` are automatically mapped to `calculator`
- **Argument auto-fixing**: Common wrong argument patterns are corrected (e.g., `{"base": 2, "exponent": 10}` → `{"expression": "2 ** 10"}`)
- **JSON response cleaning**: When models output tool schemas instead of text answers, LocalClaw falls back to tool results
- **Unicode normalization**: Accented characters are normalized for comparison (e.g., "Brasília" matches "brasilia")

### New Examples

| Example | Description |
|---------|-------------|
| `07_model_comparison.py` | Benchmark 15 tests across models with category breakdown |
| `08_robust_comparison.py` | Progress-saving comparison for unstable connections |

### Test Categories (15 tests)

| Category | Tests | Description |
|----------|-------|-------------|
| Math | Multiply, Add, Divide | Basic arithmetic (no tools) |
| Reasoning | Apples, Sequence, Logic | Multi-step reasoning |
| Knowledge | Japan, France, Brazil | World knowledge |
| Calc | Multiply, Divide, Power | Calculator tool usage |
| Code | is_even, reverse, max_num | Python code generation |

---

## About

**LocalClaw** is written and maintained by **VTSTech**.

- 🌐 Website: [https://www.vts-tech.org](https://www.vts-tech.org)
- 📦 GitHub: [https://github.com/VTSTech/LocalClaw](https://github.com/VTSTech/LocalClaw)
- 💻 More projects: [https://github.com/VTSTech](https://github.com/VTSTech)
