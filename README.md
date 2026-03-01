# LocalClaw 🦞

A minimal, hackable agentic framework engineered to run **entirely locally** with [Ollama](https://ollama.com).

Inspired by the architecture of OpenClaw, rebuilt from scratch for local-first operation.

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
    ├── 01_basic_agent.py
    ├── 02_tool_agent.py
    └── 03_orchestrator.py
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
- `qwen2`, `qwen2.5`
- `command-r`
- `hermes` (function calling variants)
- `nemotron`

All other models fall back to **ReAct text-parsing** automatically.

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
ollama pull llama3.1:8b

python examples/01_basic_agent.py
python examples/02_tool_agent.py
python examples/03_orchestrator.py
```
