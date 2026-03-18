# 🦞 LocalClaw R03

A minimal, hackable agentic framework engineered to run **entirely locally** with [Ollama](https://ollama.com) or [BitNet](https://github.com/microsoft/BitNet).

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
│   ├── skill-creator/     # OpenClaw skill-creator for generating new skills
│   ├── acp/               # ACP (Agent Control Panel) skill
│   ├── datetime/          # Datetime utilities skill
│   └── web_search/        # Web search skill
├── tools/
│   └── builtins.py        # Ready-to-use tools: calculator, shell, file I/O, HTTP, REPL
├── bitnet_client.py       # R03: BitNet backend client (Microsoft 1.58-bit quantization)
├── bitnet_setup.py        # R03: BitNet setup/compilation helper
├── acp_plugin.py          # ACP integration for activity tracking and A2A messaging
├── model_discovery.py     # R03: Dynamic model discovery for both backends
└── examples/
    ├── 01_basic_agent.py           # Simple Q&A demo
    ├── 02_tool_agent.py            # Tool calling demo
    ├── 03_orchestrator.py          # Multi-agent routing demo
    ├── 04_comprehensive_test.py    # Full test suite (supports BitNet)
    ├── 04_comprehensive_test_acp.py # ACP-tracked version
    ├── 05_tool_tests.py            # Tool-specific tests
    ├── 06_interactive_chat.py      # Interactive CLI chat
    ├── 07_model_comparison.py      # Compare models on 15 tests (3 per category)
    ├── 07_model_comparison_acp.py  # ACP-tracked version with model logging
    ├── 08_robust_comparison.py     # Progress-saving comparison for unstable connections
    ├── 08_robust_comparison_acp.py # ACP-tracked version with resumability
    ├── 09_expanded_benchmark.py    # 25 tests across 8 categories
    ├── 10_skills_demo.py           # Agent Skills system demo
    └── 11_skill_creator_test.py    # Skill creation benchmark across models
```

### Test Scripts

```
test.sh          # Bash: Run all 11 examples (Linux/macOS/Colab)
test-quick.sh    # Bash: Run 7 quick tests (skips benchmarks)
run.sh           # Bash: Interactive menu for single example
test-bitnet.sh   # Bash: Run BitNet benchmark tests
test.cmd         # Batch: Run all 11 examples (Windows)
test-quick.cmd   # Batch: Run 7 quick tests (Windows)
run.cmd          # Batch: Interactive menu for single example (Windows)
test-bitnet.cmd  # Batch: Run BitNet benchmark tests (Windows)
```

### Core design decisions

| Concern | Approach |
|---|---|
| **HTTP Client** | Zero external dependencies — uses Python stdlib `urllib` only |
| **Backends** | Ollama (default) or BitNet (R03) — switch via `--backend` flag |
| **Tool calling** | Native Ollama tool-call protocol when supported; automatic ReAct text-parsing fallback for other models |
| **Memory** | Sliding window — older turns are archived and optionally compressed via LLM summarization |
| **Tools** | Decorator-based, auto-generates JSON schemas from Python type hints |
| **Orchestration** | Router (LLM picks agent), Pipeline (chain), or Parallel (concurrent + merge) |
| **Streaming** | First-class via generator interface |
| **Error handling** | Automatic retry with exponential backoff for transient network/server errors |
| **Security** | Path validation, command blocklist, SSRF protection (R03) |

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

### BitNet Backend (R03)

LocalClaw supports Microsoft's BitNet for 1.58-bit ternary weight models — highly efficient CPU inference.

#### Supported Models

| Model | Size | HuggingFace Repo |
|-------|------|------------------|
| **BitNet-b1.58-2B-4T** | ~0.4 GB | `microsoft/BitNet-b1.58-2B-4T` |
| **Falcon3-1B-Instruct** | ~1 GB | `tiiuae/Falcon3-1B-Instruct-1.58bit` |
| **Falcon3-3B-Instruct** | ~3 GB | `tiiuae/Falcon3-3B-Instruct-1.58bit` |
| **Falcon3-7B-Instruct** | ~7 GB | `tiiuae/Falcon3-7B-Instruct-1.58bit` |
| **Falcon3-10B-Instruct** | ~10 GB | `tiiuae/Falcon3-10B-Instruct-1.58bit` |

#### Setup (One Command)

BitNet's `setup_env.py` handles everything: download, convert to GGUF, quantize, and compile kernels.

```bash
# Clone BitNet
git clone --recursive https://github.com/microsoft/BitNet.git
cd BitNet
pip install -r requirements.txt

# Download, convert, and prepare a model (choose one):
python setup_env.py --hf-repo microsoft/BitNet-b1.58-2B-4T -q i2_s      # Recommended
python setup_env.py --hf-repo tiiuae/Falcon3-1B-Instruct-1.58bit -q i2_s  # Smallest Falcon
python setup_env.py --hf-repo tiiuae/Falcon3-3B-Instruct-1.58bit -q i2_s  # Best balance
python setup_env.py --hf-repo tiiuae/Falcon3-7B-Instruct-1.58bit -q i2_s  # Most capable
```

This automatically:
1. Downloads the model from HuggingFace (safetensors format)
2. Converts to GGUF format
3. Quantizes to `i2_s` (1.58-bit ternary)
4. Compiles optimized CPU kernels

#### Start the Server

```bash
# Start BitNet server (separate terminal)
./build/bin/llama-server -m models/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf

# Or for Falcon models:
./build/bin/llama-server -m models/Falcon3-1B-Instruct-1.58bit/ggml-model-i2_s.gguf
```

#### Use with LocalClaw

```bash
# Set BitNet URL (default: http://localhost:8080)
export BITNET_BASE_URL=http://localhost:8080

# Chat with BitNet backend
python cli.py chat --backend bitnet --force-react

# With tools
python cli.py chat --backend bitnet --force-react --tools calculator,shell
```

> **Note**: BitNet models require `--force-react` as they don't support native tool calling.

#### Colab Quick Start

```bash
# Cell 1: Setup BitNet with Falcon3-1B (fastest option)
!git clone --recursive https://github.com/microsoft/BitNet.git
%cd BitNet
!pip install -r requirements.txt
!python setup_env.py --hf-repo tiiuae/Falcon3-1B-Instruct-1.58bit -q i2_s

# Cell 2: Start server in background
import subprocess, time
server = subprocess.Popen(
    ['./build/bin/llama-server', '-m', 'models/Falcon3-1B-Instruct-1.58bit/ggml-model-i2_s.gguf', '--port', '8080'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
time.sleep(5)  # Wait for server startup

# Cell 3: Clone and run LocalClaw
%cd /content
!git clone https://github.com/VTSTech/LocalClaw.git
%cd LocalClaw
!python cli.py chat --backend bitnet --force-react
```

#### Model Comparison

| Model | Speed | Quality | Best For |
|-------|-------|---------|----------|
| BitNet-b1.58-2B-4T | ⚡⚡⚡ | Good | Quick tasks, testing |
| Falcon3-1B-Instruct | ⚡⚡⚡ | Good | Fastest inference |
| Falcon3-3B-Instruct | ⚡⚡ | Better | Balanced performance |
| Falcon3-7B-Instruct | ⚡ | Best | Complex reasoning |

> **BitNet Benchmark Results**: BitNet-b1.58-2B-4T achieved **87%** on the LocalClaw benchmark — see **BitNet Benchmark Results** section below.

---

## Quick start

### 1. Single prompt

```bash
# Simple Q&A
python cli.py run "What is the capital of Japan?"

# With streaming output
python cli.py run "Tell me a joke." --stream

# Specify a model
python cli.py run "Explain quantum computing" -m llama3.2:3b
```

### 2. Interactive chat

```bash
# Start interactive session
python cli.py chat -m qwen2.5-coder:0.5b

# With tools enabled
python cli.py chat -m llama3.1:8b --tools calculator,shell,read_file,write_file

# With skills loaded
python cli.py chat -m llama3.2:3b --skills skill-creator --tools write_file,shell

# Fast mode (reduced context for speed)
python cli.py chat -m qwen2.5-coder:0.5b --fast --verbose
```

### 3. Using BitNet backend

```bash
# BitNet requires --force-react for tool support
python cli.py chat --backend bitnet --force-react

# Run single prompt with BitNet
python cli.py run "Calculate 17 * 23" --backend bitnet --tools calculator
```

### 4. With ACP tracking

```bash
# Enable ACP for activity monitoring
python cli.py chat -m qwen2.5-coder:0.5b --acp --tools shell,read_file,write_file

# Single prompt with ACP
python cli.py run "What is 2+2?" --acp
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `run "prompt"` | Run single prompt and exit |
| `chat` | Interactive multi-turn conversation |
| `models` | List available Ollama models |
| `tools` | List built-in tools |
| `skills` | List available Agent Skills |

### CLI Flags

| Flag | Description |
|------|-------------|
| `-m`, `--model` | Model name (default: qwen2.5-coder:0.5b) |
| `--tools` | Comma-separated tool list |
| `--skills` | Comma-separated skill list |
| `--backend` | `ollama` or `bitnet` |
| `--force-react` | Force ReAct text parsing |
| `--acp` | Enable ACP integration |
| `-v`, `--verbose` | Show tool calls and timing |
| `--debug` | Show detailed debug info |
| `--fast` | Preset: reduced context for speed |
| `--warmup` | Pre-load model before chat |
| `--stream` | Stream output token-by-token |
| `--temperature` | Sampling temperature (0.0-2.0) |
| `--num-ctx` | Context window size |
| `--num-predict` | Max output tokens |

### Interactive Commands (in chat)

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/status` | Show session status |
| `/tools` | List active tools |
| `/skills` | List active skills |
| `/reset` | Clear conversation history |
| `/undo` | Remove last exchange |
| `/retry` | Retry last message |
| `/a2a` | Process pending A2A messages |
| `/export` | Export to markdown |
| `exit` | End session |

---

## Built-in Tools

| Tool | Description |
|------|-------------|
| `calculator` | Evaluate math expressions |
| `python_repl` | Execute Python code |
| `shell` | Run shell commands |
| `read_file` | Read file contents |
| `write_file` | Write content to file |
| `list_directory` | List directory contents |
| `http_get` | HTTP GET request |
| `save_note` | Save a note to memory |
| `get_note` | Retrieve saved notes |

```bash
# List all tools
python cli.py tools

# Use specific tools
python cli.py chat --tools calculator,python_repl,shell
```

---

## Built-in Skills

| Skill | Description |
|-------|-------------|
| `skill-creator` | Generate new Agent Skills from requests |
| `datetime` | Date/time formatting and calculations |
| `web_search` | Web search capabilities |

```bash
# List all skills
python cli.py skills

# Use skills in chat
python cli.py chat --skills skill-creator --tools write_file
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
| 🥈 | **`BitNet-b1.58-2B-4T`** (BitNet) | **13/15 (87%)** | ~394s | **3/3** | 2/3 | 2/3 | **3/3** | **3/3** |
| 🥉 | `granite3.1-moe:1b` | **12/15 (80%)** | ~60s | **3/3** | 2/3 | **3/3** | 1/3 | **3/3** |
| 4 | `llama3.2:1b` | **12/15 (80%)** | ~600s | **3/3** | 1/3 | 2/3 | **3/3** | **3/3** |
| 5 | `gemma3:270m` | 10/15 (67%) | ~75s | **3/3** | 1/3 | 1/3 | 2/3 | **3/3** |
| 6 | `qwen3:0.6b` | ~9/12 | ~130s | 2/3 | **3/3** | **3/3** | 0/3 | — |
| 7 | `granite4:350m` | 8/15 (53%) | ~97s | 2/3 | 1/3 | 2/3 | 0/3 | **3/3** |
| 8 | `qwen2.5:0.5b` | 10/15 (67%) | ~107s | 1/3 | **3/3** | **3/3** | 0/3 | **3/3** |
| 9 | `qwen2-math:1.5b` | 12/15 (80%) | ~611s | **3/3** | **3/3** | **3/3** | ❌ | **3/3** |
| 10 | `tinyllama:latest` | 9/15 (60%) | ~587s | 2/3 | 2/3 | **3/3** | 0/3 | 2/3 |
| 11 | `smollm:135m` | 7/15 (47%) | ~285s | 0/3 | 2/3 | 2/3 | 0/3 | **3/3** |
| 12 | `functiongemma:270m` | 1/15 (7%) | ~90s | 0/3 | 0/3 | 0/3 | 0/3 | 1/3 |

> **Note**: Scores vary between runs due to model non-determinism. The `qwen2.5-coder:0.5b` achieved 100% in some runs.

### Model Details

| Model | Params | Size | Speed | Tool Support | Notes |
|-------|--------|------|-------|--------------|-------|
| `qwen2.5-coder:0.5b` | 494M | ~400MB | ⚡ Fast | ✅ Native | **🏆 Best overall!** Excellent tool usage |
| **`BitNet-b1.58-2B-4T`** | **2B** | **~1.3GB** | **⚡ Medium** | **⚠️ ReAct** | **🥈 2nd place!** CPU-efficient ternary weights |
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
| **Math** | `qwen2.5-coder:0.5b`, `granite3.1-moe:1b`, `BitNet-b1.58-2B` | 3/3 | Also gemma3:270m |
| **Reasoning** | `qwen2.5:0.5b`, `qwen3:0.6b`, `qwen2-math` | 3/3 | Multiple tied |
| **Knowledge** | `granite3.1-moe:1b`, `qwen2-math` | 3/3 | Multiple tied at 3/3 |
| **Calc** | `qwen2.5-coder:0.5b`, `llama3.2:1b`, `BitNet-b1.58-2B` | 3/3 | 100% tool usage with ReAct |
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

🦞 LocalClaw R03 supports the **[Agent Skills](https://agentskills.io/)** specification for reusable instruction bundles.

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

```bash
# Load skills via CLI
python cli.py chat --skills skill-creator --tools write_file,shell

# Multiple skills
python cli.py chat --skills datetime,web_search --tools calculator
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
| `datetime` | Date and time utilities for formatting, parsing, and calculations. |
| `web_search` | Web search capabilities for retrieving information from the internet. |

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

# Quick test suite (recommended first run)
bash test-quick.sh      # Linux/macOS/Colab
test-quick.cmd          # Windows

# Full test suite (all 11 examples)
bash test.sh            # Linux/macOS/Colab
test.cmd                # Windows

# Interactive menu
bash run.sh             # Linux/macOS/Colab
run.cmd                 # Windows

# Run individual examples
python examples/01_basic_agent.py
python examples/02_tool_agent.py
python examples/03_orchestrator.py
python examples/04_comprehensive_test.py
python examples/05_tool_tests.py
python examples/06_interactive_chat.py
python examples/07_model_comparison.py
python examples/08_robust_comparison.py
python examples/09_expanded_benchmark.py
python examples/10_skills_demo.py
python examples/11_skill_creator_test.py
```

---

## ACP Integration (Agent Control Panel)

🦞 LocalClaw R03 supports **[ACP (Agent Control Panel)](https://github.com/VTSTech/ACP-Agent-Control-Panel)** for centralized activity tracking, token monitoring, and multi-agent coordination.

### What is ACP?

ACP is a monitoring and observability protocol for AI agents. Unlike communication protocols (MCP, A2A), ACP sits alongside your agents and provides:

- **Activity Tracking**: Real-time monitoring of all agent actions
- **Token Management**: Context window usage estimation per agent
- **Multi-Agent Coordination**: Track multiple agents in one session
- **STOP/Resume Control**: Emergency stop capability
- **Session Persistence**: State preserved across restarts

### Enable ACP

```bash
# Run with ACP tracking
python cli.py chat --acp --tools shell,read_file,write_file -m qwen2.5-coder:0.5b

# Run single prompt with ACP
python cli.py run --acp "What is 2+2?"
```

### Configuration

Set your ACP server URL via environment variables:

```bash
# Local ACP
export ACP_URL="http://localhost:8766"

# Remote ACP (cloudflare tunnel)
export ACP_URL="https://your-tunnel.trycloudflare.com"

# Credentials
export ACP_USER="admin"
export ACP_PASS="secret"
```

Or edit `localclaw/config.py` for persistent settings.

### What Gets Logged

| Activity | Description |
|----------|-------------|
| **Bootstrap** | Session start, identity establishment |
| **User messages** | All prompts sent to the model |
| **Assistant messages** | All model responses |
| **Tool calls** | Shell commands, file operations, etc. |
| **Tool results** | Outcomes from tool execution |

### Per-Agent Token Tracking

When multiple agents connect to the same ACP session:

```json
{
  "primary_agent": "Super Z",
  "agent_tokens": {
    "Super Z": 42000,
    "LocalClaw": 500
  },
  "other_agents_tokens": 500
}
```

- First agent to connect becomes **primary** (owns main context window)
- Other agents tracked separately in `agent_tokens`
- Prevents context pollution between agents

### ACP Server

To run your own ACP server, see the [ACP Specification](https://github.com/VTSTech/ACP-Agent-Control-Panel):

```bash
# ACP is a single Python file
python VTSTech-GLMACP.py

# With cloudflare tunnel
GLMACP_TUNNEL=auto python VTSTech-GLMACP.py
```

---

## Remote Ollama Configuration

To use a remote Ollama instance (e.g., via Cloudflare tunnel), set the environment variable:

```bash
# Local Ollama (default)
export OLLAMA_URL="http://localhost:11434"

# Remote Ollama (cloudflare tunnel)
export OLLAMA_URL="https://your-tunnel.trycloudflare.com"
```

Or edit `localclaw/config.py` for persistent settings.

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

Control model behavior via CLI flags:

```bash
# Lower temperature = more deterministic
python cli.py chat -m qwen2.5-coder:0.5b --temperature 0.1

# Smaller context = faster
python cli.py chat -m qwen2.5-coder:0.5b --num-ctx 2048 --num-predict 128

# Combined for optimal speed
python cli.py chat -m qwen2.5-coder:0.5b --fast --temperature 0.3
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

## Recent Improvements

### R03: BitNet Backend

🦞 LocalClaw R03 adds **BitNet backend support** for running Microsoft's 1.58-bit quantized models:

- **New backend**: Switch between Ollama and BitNet via `--backend` flag
- **Zero-cost inference**: BitNet models run efficiently on CPU
- **Setup helper**: `bitnet_setup.py` handles cloning and compilation
- **Note**: BitNet requires ReAct fallback (no native tool support)

### R03: Enhanced Security

Built-in tools now have comprehensive security:

- **Path validation**: Restrict file access to allowed directories
- **Command blocklist**: Block dangerous commands (`rm`, `sudo`, `chmod`, etc.)
- **Pattern detection**: Detect dangerous shell patterns (pipes to bash, command substitution)
- **SSRF protection**: Block private IPs and cloud metadata endpoints in `http_get`
- **Configurable modes**: `strict`, `permissive`, or `disabled`

```bash
# Set security mode
export LOCALCLAW_SECURITY_MODE=strict
export LOCALCLAW_ALLOWED_PATHS=/home/user/projects:/tmp
export LOCALCLAW_BLOCKED_COMMANDS=rm,sudo,dd
```

### Zero Dependencies

🦞 LocalClaw R03 continues to use **only Python stdlib** — no pip install required! The HTTP client uses `urllib` instead of `httpx`.

### Automatic Error Recovery

- **HTTP 524/502/503/504/500 retry**: Transient server errors are automatically retried with exponential backoff
- **Timeout retry**: Socket timeouts are retried automatically
- **Configurable via environment variables**: `OLLAMA_TIMEOUT`, `OLLAMA_MAX_RETRIES`, `OLLAMA_RETRY_DELAY`

### Small Model Support

🦞 LocalClaw R03 handles quirks of small models (≤1.5B parameters):

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
| `11_skill_creator_test.py` | Benchmark skill creation across multiple small models |

### Test Categories (15 tests)

| Category | Tests | Description |
|----------|-------|-------------|
| Math | Multiply, Add, Divide | Basic arithmetic (no tools) |
| Reasoning | Apples, Sequence, Logic | Multi-step reasoning |
| Knowledge | Japan, France, Brazil | World knowledge |
| Calc | Multiply, Divide, Power | Calculator tool usage |
| Code | is_even, reverse, max_num | Python code generation |

---

## BitNet Benchmark Results

LocalClaw R03 has been tested with **Microsoft BitNet-b1.58-2B-4T** — a 2B parameter model with 1.58-bit ternary weights, designed for efficient CPU inference.

### Test Results Summary

| Test Suite | Score | Time | Notes |
|------------|-------|------|-------|
| **Model Comparison** (15 tests) | **13/15 (87%)** | 394s | 5 categories |
| **Robust Comparison** (22 tests) | **19/22 (86%)** | ~6min | Incremental save |
| **Comprehensive Test** (7 tests) | **6/7 (86%)** | ~90s | Basic + Reasoning + Code |

### Category Breakdown (Model Comparison - 15 tests)

| Category | Score | Pass Rate |
|----------|-------|-----------|
| **Math** | 3/3 | 100% ✅ |
| **Code** | 3/3 | 100% ✅ |
| **Calc (with tools)** | 3/3 | 100% ✅ |
| **Reasoning** | 2/3 | 67% |
| **Knowledge** | 2/3 | 67% |
| **Total** | **13/15** | **87%** |

### Failed Tests

| Test | Expected | Got | Category |
|------|----------|-----|----------|
| Apples (reasoning) | 5 | 7 | Reasoning |
| Brazil capital | Brasília | São Paulo | Knowledge |

### Performance Notes

| Metric | Value |
|--------|-------|
| **Avg response time** | 5-10s (simple), 100s+ (tool use) |
| **Tool calling** | ReAct fallback (no native support) |
| **Context window** | Default (model dependent) |
| **Inference** | CPU-efficient ternary weights |

### BitNet vs Ollama Small Models

| Rank | Model | Score | Params | Backend |
|:----:|-------|------:|-------:|---------|
| 🥇 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | 14/15 (93%) | 494M | Ollama |
| 🥈 | **`BitNet-b1.58-2B-4T`** | **13/15 (87%)** | **2B** | **BitNet** |
| 🥉 | `granite3.1-moe:1b` | 12/15 (80%) | 1B MoE | Ollama |
| 4 | `llama3.2:1b` | 12/15 (80%) | 1.2B | Ollama |

> **Note**: BitNet uses 1.58-bit ternary weights, making it highly efficient for CPU inference despite having 2B parameters.

### BitNet Setup for Benchmarking

```bash
# 1. Clone and compile BitNet
python localclaw/bitnet_setup.py

# 2. Start the BitNet server
./build/bin/llama-server -m models/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf

# 3. Run benchmark
export LOCALCLAW_BACKEND=bitnet
python examples/07_model_comparison.py

# 4. Run with ACP tracking
export LOCALCLAW_BACKEND=bitnet
python examples/07_model_comparison_acp.py
```

### Observations

1. **Excellent for CPU-only systems** — ternary weights enable fast inference without GPU
2. **Solid tool usage** — ReAct fallback handles calculator tools reliably
3. **Code generation strong** — 100% pass rate on function writing tasks
4. **Multi-step reasoning challenges** — the "apples" test requires tracking state
5. **Knowledge gaps** — São Paulo is commonly mistaken for Brazil's capital

---

## About

**🦞 LocalClaw R03** is written and maintained by **VTSTech**.

- 🌐 Website: [https://www.vts-tech.org](https://www.vts-tech.org)
- 📦 GitHub: [https://github.com/VTSTech/LocalClaw](https://github.com/VTSTech/LocalClaw)
- 💻 More projects: [https://github.com/VTSTech](https://github.com/VTSTech)

---

> **Testing Status**: LocalClaw has been tested with both **Ollama** (11 small models) and **BitNet** (BitNet-b1.58-2B-4T) backends. BitNet achieved **87%** on the benchmark, making it the 2nd best performer overall. See **Tested Small Models** and **BitNet Benchmark Results** sections for details.
