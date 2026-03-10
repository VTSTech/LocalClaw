# 🦞 LocalClaw R01

A minimal, hackable agentic framework engineered to run **entirely locally** with [Ollama](https://ollama.com).

Inspired by the architecture of OpenClaw, rebuilt from scratch for local-first operation.

**Written by [VTSTech](https://www.vts-tech.org)** · [GitHub](https://github.com/VTSTech/LocalClaw)

---

## Architecture

```
localclaw/
├── core/
│   ├── ollama_client.py   # Zero-dependency HTTP wrapper (stdlib urllib only)
│   ├── tools.py           # Decorator-based tool registry + JSON schema generation
│   ├── memory.py          # Sliding-window conversation memory with summarization
│   ├── agent.py           # ReAct loop — native tool-call + text-fallback modes
│   └── orchestrator.py    # Multi-agent routing (router / pipeline / parallel)
├── skills/
│   ├── loader.py          # Agent Skills specification loader (progressive disclosure)
│   └── skill-creator/     # OpenClaw skill-creator for generating new skills
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
    ├── 08_robust_comparison.py # Progress-saving comparison for unstable connections
    ├── 09_expanded_benchmark.py # 25 tests across 8 categories
    └── 10_skills_demo.py      # Agent Skills system demo
```

### Core design decisions

| Concern | Approach |
|---|---|
| **HTTP Client** | Zero external dependencies — uses Python stdlib `urllib` only |
| **Tool calling** | Native Ollama tool-call protocol when supported; automatic ReAct text-parsing fallback for other models |
| **Memory** | Sliding window — older turns are archived and optionally compressed via LLM summarization |
| **Tools** | Decorator-based, auto-generates JSON schemas from Python type hints |
| **Orchestration** | Router (LLM picks agent), Pipeline (chain), or Parallel (concurrent + merge) |
| **Streaming** | First-class via generator interface |
| **Error handling** | Automatic retry with exponential backoff for transient network/server errors |

---

## Installation

```bash
# Clone / copy the localclaw directory into your project
# No pip install required — uses only Python stdlib!

# Make sure Ollama is running:
ollama serve

# Pull a model:
ollama pull qwen2.5-coder:0.5b-instruct-q4_k_m
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

**Meta Llama**: `llama3`, `llama3.1`, `llama3.2`, `llama3.3`, `llama3-groq-tool-use`

**Mistral AI**: `mistral`, `mixtral`, `mistral-nemo`, `mistral-small`, `mistral-large`, `codestral`, `ministral`

**Alibaba Qwen**: `qwen2`, `qwen2.5`, `qwen3`, `qwen35`, `qwen2.5-coder`, `qwen2-math`

**Cohere**: `command-r`, `command-r7b`

**DeepSeek**: `deepseek`, `deepseek-coder`, `deepseek-v2`, `deepseek-v3`

**Microsoft Phi**: `phi-3`, `phi3`, `phi-4`

**Google Gemma**: `functiongemma` (designed for function calling)

**Others**: `yi-`, `yi1.5`, `internlm2`, `internlm2.5`, `solar`, `glm4`, `chatglm`, `firefunction`, `hermes`, `nemotron`, `cogito`, `athene`

All other models fall back to **ReAct text-parsing** automatically.

---

## Tested Small Models (≤1.5B parameters)

The following models have been tested with a **15-test benchmark** (3 tests per category: Math, Reasoning, Knowledge, Calc Tool, Code). Prompts are optimized for small model comprehension.

### Rankings (Updated)

| Rank | Model | Score | Time | Math | Reason | Know | Calc | Code |
|:----:|-------|------:|-----:|:----:|:------:|:----:|:----:|:----:|
| 🥇 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | **14/15 (93%)** | ~80s | **3/3** | 2/3 | 2/3 | **3/3** | **3/3** |
| 🥈 | `granite3.1-moe:1b` | **12/15 (80%)** | ~60s | **3/3** | 2/3 | **3/3** | 1/3 | **3/3** |
| 🥉 | `llama3.2:1b` | **12/15 (80%)** | ~600s | **3/3** | 1/3 | 2/3 | **3/3** | **3/3** |
| 4 | `gemma3:270m` | 10/15 (67%) | ~75s | **3/3** | 1/3 | 1/3 | 2/3 | **3/3** |
| 5 | `qwen3:0.6b` | ~9/12 | ~130s | 2/3 | **3/3** | **3/3** | 0/3 | — |
| 6 | `granite4:350m` | 8/15 (53%) | ~97s | 2/3 | 1/3 | 2/3 | 0/3 | **3/3** |
| 7 | `qwen2.5:0.5b` | 10/15 (67%) | ~107s | 1/3 | **3/3** | **3/3** | 0/3 | **3/3** |
| 8 | `qwen2-math:1.5b` | 12/15 (80%) | ~611s | **3/3** | **3/3** | **3/3** | ❌ | **3/3** |
| 9 | `tinyllama:latest` | 9/15 (60%) | ~587s | 2/3 | 2/3 | **3/3** | 0/3 | 2/3 |
| 10 | `smollm:135m` | 7/15 (47%) | ~285s | 0/3 | 2/3 | 2/3 | 0/3 | **3/3** |
| 11 | `functiongemma:270m` | 1/15 (7%) | ~90s | 0/3 | 0/3 | 0/3 | 0/3 | 1/3 |

> **Note**: Scores vary between runs due to model non-determinism. The `qwen2.5-coder:0.5b` achieved 100% in some runs.

### Model Details

| Model | Params | Size | Speed | Tool Support | Notes |
|-------|--------|------|-------|--------------|-------|
| `qwen2.5-coder:0.5b` | 494M | ~400MB | ⚡ Fast | ✅ Native | **🏆 Best overall!** Excellent tool usage |
| `granite3.1-moe:1b` | 1B MoE | ~1.4GB | ⚡ Medium | ✅ Native | Strong knowledge, HTTP 500 on long context |
| `llama3.2:1b` | 1.2B | ~1.3GB | 🐢 Slow | ✅ Native | **128k context!** Thorough but slow |
| `gemma3:270m` | 270M | ~292MB | ⚡⚡ Fastest | ⚠️ ReAct JSON | Uses JSON ReAct format, Math & Code champion |
| `qwen3:0.6b` | 600M | ~523MB | ⚡ Medium | ⚠️ Text | Perfect reasoning but Calc returns empty |
| `granite4:350m` | 350M | ~708MB | ⚡ Fast | ❌ Refused | **Refuses calculator** - safety filter |
| `qwen2.5:0.5b` | 494M | ~398MB | ⚡ Fast | ⚠️ Text | **Reasoning & Knowledge champ**, Calc fails |
| `qwen2-math:1.5b` | 1.5B | ~935MB | 🐢 Slow | ❌ No tools | **4 perfect categories!** No tool support |
| `tinyllama:latest` | 1.1B | ~638MB | 🐢 Slow | ⚠️ Text | Older model, verbose, unstable |
| `smollm:135m` | 135M | ~92MB | ⚡ Fast | ❌ None | **Smallest** - hallucinates math (7×8=42!) |
| `functiongemma:270m` | 270M | ~301MB | ⚡ Fast | ❌ Broken | **Worst performer** - returns empty |

### Category Champions

| Category | Champion | Score | Notes |
|----------|----------|-------|-------|
| **Math** | `qwen2.5-coder:0.5b`, `granite3.1-moe:1b` | 3/3 | Also gemma3:270m |
| **Reasoning** | `qwen2.5:0.5b`, `qwen3:0.6b`, `qwen2-math` | 3/3 | Multiple tied |
| **Knowledge** | `granite3.1-moe:1b`, `qwen2-math` | 3/3 | Multiple tied at 3/3 |
| **Calc** | `qwen2.5-coder:0.5b`, `llama3.2:1b` | 3/3 | Only models with 100% tool usage |
| **Code** | Many models | 3/3 | Code generation is easy for small models! |

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
| **General use** | `qwen2.5-coder:0.5b-instruct-q4_k_m` | Best all-around, fast, great tool usage |
| **Large context** | `llama3.2:1b` | **128k context window** - handles long conversations |
| **Math tasks** | `qwen2.5-coder:0.5b` or `qwen2-math:1.5b` | Perfect math scores |
| **Reasoning tasks** | `qwen2.5:0.5b` or `qwen3:0.6b` | Perfect reasoning |
| **Tool usage** | `qwen2.5-coder:0.5b` | Most reliable tool calling |
| **Fastest inference** | `gemma3:270m` | 270M params, fastest responses |
| **No tools needed** | `qwen2-math:1.5b` | 4/5 categories perfect (no Calc) |
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
   - `granite3.1-moe:1b`: HTTP 500 crashes (server EOF)
   - `tinyllama`, `qwen3:0.6b`: HTTP 524 timeouts
6. **Empty responses**: `functiongemma:270m` returns empty strings on most tests

---

## Skills (Agent Skills Specification)

🦞 LocalClaw R01 supports the **[Agent Skills](https://agentskills.io/)** specification for reusable instruction bundles.

### Skill Structure

```
skills/
└── my-skill/
    ├── SKILL.md          # Required: name, description, instructions
    ├── scripts/          # Optional: executable scripts
    ├── references/       # Optional: additional docs
    └── assets/           # Optional: templates, images
```

### SKILL.md Format

```yaml
---
name: calculator
description: Perform mathematical calculations. Use when the user needs to compute expressions.
---

# Calculator Skill

Instructions for the model on how to use this skill...
```

### Using Skills

```python
from localclaw import Agent, SkillLoader, SkillRegistry
from localclaw.tools.builtins import make_builtin_registry

# Load skills
loader = SkillLoader()
registry = SkillRegistry()

for skill_name in loader.list_skills():
    skill = loader.load(skill_name)
    registry.add(skill)

# Create agent with skills
tools = make_builtin_registry().subset(["calculator"])
skill_prompt = registry.to_system_prompt_addition()

agent = Agent(
    model="qwen2.5-coder:0.5b-instruct-q4_k_m",
    tools=tools,
    system_prompt="You are a helpful assistant." + skill_prompt,
)

response = agent.chat("What is 25 times 17?")
```

### Progressive Disclosure

Skills follow a three-level loading system:

1. **Metadata** (~100 tokens): `name` + `description` loaded at startup
2. **Instructions** (<500 lines): Full `SKILL.md` body loaded when skill triggers
3. **Resources** (as needed): Files in `scripts/`, `references/`, `assets/` loaded on demand

### Built-in Skills

| Skill | Description |
|-------|-------------|
| `skill-creator` | OpenClaw's platform-agnostic skill generator. Creates new skills from user requests. |

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

---

## Remote Ollama Configuration

To use a remote Ollama instance (e.g., via Cloudflare tunnel), edit `localclaw/core/ollama_client.py`:

```python
# LOCAL OLLAMA (default):
DEFAULT_BASE_URL = "http://localhost:11434"

# REMOTE OLLAMA (cloudflare tunnel):
# DEFAULT_BASE_URL = "https://your-tunnel.trycloudflare.com"
```

### Timeout Configuration

Configure via environment variables:

```bash
# Request timeout in seconds (default: 90s for Cloudflare tunnel compatibility)
export OLLAMA_TIMEOUT=90

# Max retry attempts for transient errors (default: 3)
export OLLAMA_MAX_RETRIES=3

# Initial retry delay in seconds (default: 5s, doubles each retry)
export OLLAMA_RETRY_DELAY=5
```

### Automatic Retry

LocalClaw automatically retries on transient errors with exponential backoff:

| Error Code | Description | Retry Behavior |
|------------|-------------|----------------|
| HTTP 524 | Cloudflare tunnel timeout | Retries up to 3 times |
| HTTP 502/503/504 | Server temporarily unavailable | Retries up to 3 times |
| HTTP 500 | Server error (model loading, memory pressure) | Retries up to 3 times |
| Timeout | Socket or connection timeout | Retries up to 3 times |

---

## Performance Optimization

### CLI Options for Speed

```bash
# Fast mode - reduces context and output for quicker responses
python cli.py chat -m qwen2.5-coder:0.5b --fast --verbose

# Fine-tuned control
python cli.py chat -m qwen2.5-coder:0.5b --num-ctx 2048 --num-predict 128

# Warm up model before chat (useful for remote Ollama with cold starts)
python cli.py chat -m qwen2.5-coder:0.5b --warmup --fast
```

| Option | Description | Speed Impact |
|--------|-------------|--------------|
| `--fast` | Preset: `num_ctx=2048`, `num_predict=256` | 🚀 Significant |
| `--num-ctx N` | Reduce context window (default varies by model) | 🚀 Significant |
| `--num-predict N` | Limit max output tokens | ⚡ Moderate |
| `--warmup` | Pre-load model before first chat | ⚡ Faster first response |

### Ollama Model Options

You can pass any Ollama option via `model_options`:

```python
agent = Agent(
    model="qwen2.5-coder:0.5b",
    model_options={
        "temperature": 0.1,      # Lower = more deterministic
        "num_ctx": 2048,         # Smaller context = faster
        "num_predict": 128,      # Limit output length
        "top_p": 0.9,            # Nucleus sampling
        "top_k": 40,             # Top-k sampling
        "repeat_penalty": 1.1,   # Reduce repetition
    },
)
```

### Remote Ollama Tips

When using a **remote Ollama via Cloudflare tunnel**:

1. **Use `--fast` flag** - Reduces inference time significantly
2. **Use smaller models** - `qwen2.5-coder:0.5b` is fastest
3. **Warm up the model** - First request is slowest due to model loading
4. **Increase timeout if needed**: `export OLLAMA_TIMEOUT=120`

```bash
# Recommended for remote Ollama
python cli.py chat -m qwen2.5-coder:0.5b-instruct-q4_k_m \
    --fast --warmup --verbose \
    --tools python_repl
```

### Why Inference is Slow

| Factor | Impact | Solution |
|--------|--------|----------|
| **Model size** | Larger models = slower | Use smaller quantized models |
| **Context window** | More context = slower | Use `--num-ctx 2048` or smaller |
| **Output length** | More tokens = slower | Use `--num-predict 128` |
| **Remote connection** | Network latency | Use local Ollama if possible |
| **Cold start** | First load is slowest | Use `--warmup` flag |
| **GPU unavailable** | CPU inference is slow | Ensure GPU is configured |

---

## CLI Commands (Interactive Chat)

When using `examples/06_interactive_chat.py`, the following commands are available:

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/status` | Show agent status (model, tools, memory) |
| `/context` | Show current conversation context |
| `/stats` | Show session statistics |
| `/messages` | Show message count |
| `/undo` | Undo last exchange |
| `/retry` | Retry last message |
| `/export` | Export conversation to file |
| `/save <file>` | Save conversation to file |
| `/load <file>` | Load conversation from file |
| `/system <prompt>` | Change system prompt |
| `/temp <value>` | Change temperature |
| `/quit` or `exit` | Exit the chat |

### CLI Flags

```bash
python cli.py chat --model llama3.2:1b --verbose

# Use --force-react for models without native tool support
python cli.py chat --model phi3.5:3.8b --force-react

# Performance optimization
python cli.py chat --model qwen2.5-coder:0.5b --fast --warmup

# Fine-tune context and output limits
python cli.py chat --model llama3.2:1b --num-ctx 4096 --num-predict 512
```

---

## Recent Improvements

### Zero Dependencies

🦞 LocalClaw R01 now uses **only Python stdlib** — no pip install required! The HTTP client uses `urllib` instead of `httpx`.

### Automatic Error Recovery

- **HTTP 524/502/503/504/500 retry**: Transient server errors are automatically retried with exponential backoff
- **Timeout retry**: Socket timeouts are retried automatically
- **Configurable via environment variables**: `OLLAMA_TIMEOUT`, `OLLAMA_MAX_RETRIES`, `OLLAMA_RETRY_DELAY`

### Small Model Support

🦞 LocalClaw R01 handles quirks of small models (≤1.5B parameters):

- **Fuzzy tool name matching**: Hallucinated tool names like `calculate_expression` are automatically mapped to `calculator`
- **Argument auto-fixing**: Common wrong argument patterns are corrected (e.g., `{"base": 2, "exponent": 10}` → `{"expression": "2 ** 10"}`)
- **JSON response cleaning**: When models output tool schemas instead of text answers, LocalClaw falls back to tool results
- **Unicode normalization**: Accented characters are normalized for comparison (e.g., "Brasília" matches "brasilia")
- **ReAct text parsing**: Models without native tool support automatically fall back to text-based ReAct format

### Optimized Test Prompts

Key insights for small model prompt engineering:

1. **State the fact first**: "The capital of Japan is Tokyo. What is the capital of Japan?"
2. **Show the answer format**: "Answer: Tokyo" at the end
3. **Give calculation steps**: "10 minus 3 equals 7. Then 7 minus 2 equals 5."
4. **Be explicit with tools**: "Use calculator tool. Expression: 2 ** 10. Result: 1024"
5. **Guide code output**: "Start with: def is_even(n):"

### New Examples

| Example | Description |
|---------|-------------|
| `07_model_comparison.py` | Benchmark 15 tests across models with category breakdown |
| `08_robust_comparison.py` | Progress-saving comparison for unstable connections |
| `09_expanded_benchmark.py` | 25 tests across 8 categories including tool chaining |
| `10_skills_demo.py` | Demonstrate Agent Skills system with skill-creator |

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

**🦞 LocalClaw R01** is written and maintained by **VTSTech**.

- 🌐 Website: [https://www.vts-tech.org](https://www.vts-tech.org)
- 📦 GitHub: [https://github.com/VTSTech/LocalClaw](https://github.com/VTSTech/LocalClaw)
- 💻 More projects: [https://github.com/VTSTech](https://github.com/VTSTech)
