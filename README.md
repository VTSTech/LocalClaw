# 🦞 LocalClaw R03

A minimal, hackable agentic framework engineered to run **entirely locally** with [Ollama](https://ollama.com) or [BitNet](https://github.com/microsoft/BitNet).

Inspired by the architecture of OpenClaw, rebuilt from scratch for local-first operation.

**Written by [VTSTech](https://www.vts-tech.org)** · [GitHub](https://github.com/VTSTech/LocalClaw)

---

## Installation

### From PyPI (Recommended)

```bash
pip install localclaw

# Or install from GitHub for the latest development version:
pip install git+https://github.com/VTSTech/LocalClaw.git
```

### From Source

```bash
git clone https://github.com/VTSTech/LocalClaw.git
cd LocalClaw
pip install -e .
```

### No Installation Required

LocalClaw uses only Python stdlib — no dependencies! You can also just copy the `localclaw` directory into your project:

```bash
cp -r localclaw /path/to/your/project/
```

---

## Quick Start

### 1. Single prompt

```bash
# Simple Q&A
localclaw run "What is the capital of Japan?"

# With streaming output
localclaw run "Tell me a joke." --stream

# Specify a model
localclaw run "Explain quantum computing" -m llama3.2:3b
```

### 2. Interactive chat

```bash
# Start interactive session
localclaw chat -m qwen2.5-coder:0.5b

# With tools enabled
localclaw chat -m llama3.1:8b --tools calculator,shell,read_file,write_file

# With skills loaded
localclaw chat -m llama3.2:3b --skills skill-creator --tools write_file,shell

# Fast mode (reduced context for speed)
localclaw chat -m qwen2.5-coder:0.5b --fast --verbose
```

### 3. Using BitNet backend

```bash
localclaw chat --backend bitnet --force-react
localclaw run "Calculate 17 * 23" --backend bitnet --tools calculator
```

### 4. With ACP tracking

```bash
localclaw chat -m qwen2.5-coder:0.5b --acp --tools shell,read_file,write_file
localclaw run "What is 2+2?" --acp
```

---

## Skills System

LocalClaw supports the **[Agent Skills](https://agentskills.io/)** specification for reusable instruction bundles.

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

### Progressive Disclosure

Skills follow a three-level loading system:

1. **Metadata** (~100 tokens): `name` + `description` loaded at startup
2. **Instructions** (<500 lines): Full `SKILL.md` body loaded when skill triggers
3. **Resources** (as needed): Files in `scripts/`, `references/`, `assets/` loaded on demand

---

## Security Features (R03)

Built-in tools have comprehensive security:

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

---

## Small Model Support (≤1.5B parameters)

LocalClaw handles quirks of small models:

- **Fuzzy tool name matching**: Hallucinated tool names like `calculate_expression` are automatically mapped to `calculator`
- **Argument auto-fixing**: Common wrong argument patterns are corrected (e.g., `{"base": 2, "exponent": 10}` → `{"expression": "2 ** 10"}`)
- **JSON response cleaning**: When models output tool schemas instead of text answers, LocalClaw falls back to tool results
- **Unicode normalization**: Accented characters are normalized for comparison (e.g., "Brasília" matches "brasilia")
- **ReAct text parsing**: Models without native tool support automatically fall back to text-based ReAct format

---

## Prompt Engineering for Small Models

Key insights for small model prompt engineering:

1. **State the fact first**: "The capital of Japan is Tokyo. What is the capital of Japan?"
2. **Show the answer format**: "Answer: Tokyo" at the end
3. **Give calculation steps**: "10 minus 3 equals 7. Then 7 minus 2 equals 5."
4. **Be explicit with tools**: "Use calculator tool. Expression: 2 ** 10. Result: 1024"
5. **Guide code output**: "Start with: def is_even(n):"

---

## Configuration

Environment variables for runtime configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `BITNET_BASE_URL` | BitNet server URL | `http://localhost:8765` |
| `ACP_BASE_URL` | ACP server URL | `http://localhost:8766` |
| `ACP_USER` | ACP username | `admin` |
| `ACP_PASS` | ACP password | `secret` |
| `LOCALCLAW_BACKEND` | Backend: `ollama` or `bitnet` | `ollama` |
| `LOCALCLAW_MODEL` | Default model | `qwen2.5-coder:0.5b-instruct-q4_k_m` |
| `OLLAMA_TIMEOUT` | Request timeout (seconds) | `90` |
| `OLLAMA_MAX_RETRIES` | Max retry attempts | `3` |
| `OLLAMA_RETRY_DELAY` | Initial retry delay (seconds) | `5` |

---

## Setup Ollama

```bash
# Make sure Ollama is running:
ollama serve

# Pull a model:
ollama pull qwen2.5-coder:0.5b-instruct-q4_k_m
```

---

## BitNet Backend (R03)

LocalClaw supports Microsoft's BitNet for 1.58-bit ternary weight models — highly efficient CPU inference.

### Supported Models

| Model | Size | HuggingFace Repo |
|-------|------|------------------|
| **BitNet-b1.58-2B-4T** | ~0.4 GB | `microsoft/BitNet-b1.58-2B-4T` |
| **Falcon3-1B-Instruct** | ~1 GB | `tiiuae/Falcon3-1B-Instruct-1.58bit` |
| **Falcon3-3B-Instruct** | ~3 GB | `tiiuae/Falcon3-3B-Instruct-1.58bit` |
| **Falcon3-7B-Instruct** | ~7 GB | `tiiuae/Falcon3-7B-Instruct-1.58bit` |

### Setup

```bash
# Clone BitNet
git clone --recursive https://github.com/microsoft/BitNet.git
cd BitNet
pip install -r requirements.txt

# Download, convert, and prepare a model:
python setup_env.py --hf-repo microsoft/BitNet-b1.58-2B-4T -q i2_s

# Start the server
./build/bin/llama-server -m models/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf
```

### Use with LocalClaw

```bash
# BitNet requires --force-react for tool support
localclaw chat --backend bitnet --force-react

# With tools
localclaw chat --backend bitnet --force-react --tools calculator,shell
```

> **Note**: BitNet models require `--force-react` as they don't support native tool calling.

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `run "prompt"` | Run single prompt and exit |
| `chat` | Interactive multi-turn conversation |
| `models` | List available Ollama models |
| `tools` | List built-in tools |
| `skills` | List available Agent Skills |
| `test [example]` | Run example/test scripts (`--list` to see all) |

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
localclaw tools
localclaw chat --tools calculator,python_repl,shell
```

---

## Built-in Skills

| Skill | Description |
|-------|-------------|
| `skill-creator` | Generate new Agent Skills from requests |
| `datetime` | Date/time formatting and calculations |
| `web_search` | Web search capabilities |

```bash
localclaw skills
localclaw chat --skills skill-creator --tools write_file
```

---

## Supported Models (Tool-calling)

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

## ACP Integration (Agent Control Panel)

LocalClaw supports **[ACP (Agent Control Panel)](https://github.com/VTSTech/ACP-Agent-Control-Panel)** for centralized activity tracking, token monitoring, and multi-agent coordination.

### Enable ACP

```bash
localclaw chat --acp --tools shell,read_file,write_file -m qwen2.5-coder:0.5b
localclaw run --acp "What is 2+2?"
```

### Configuration

```bash
# Local ACP
export ACP_BASE_URL="http://localhost:8766"

# Remote ACP (cloudflare tunnel)
export ACP_BASE_URL="https://your-tunnel.trycloudflare.com"

# Credentials
export ACP_USER="admin"
export ACP_PASS="secret"
```

---

## Remote Ollama Configuration

```bash
# Local Ollama (default)
export OLLAMA_BASE_URL="http://localhost:11434"

# Remote Ollama (cloudflare tunnel)
export OLLAMA_BASE_URL="https://your-tunnel.trycloudflare.com"
```

### Timeout Configuration

```bash
export OLLAMA_TIMEOUT=90
export OLLAMA_MAX_RETRIES=3
export OLLAMA_RETRY_DELAY=5
```

---

## Performance Optimization

```bash
# Fast mode - reduces context and output for quicker responses
localclaw chat -m qwen2.5-coder:0.5b --fast --verbose

# Fine-tuned control
localclaw chat -m qwen2.5-coder:0.5b --num-ctx 2048 --num-predict 128

# Warm up model before chat (useful for remote Ollama with cold starts)
localclaw chat -m qwen2.5-coder:0.5b --warmup --fast
```

| Option | Description | Speed Impact |
|--------|-------------|--------------|
| `--fast` | Preset: `num_ctx=2048`, `num_predict=256` | 🚀 Significant |
| `--num-ctx N` | Reduce context window | 🚀 Significant |
| `--num-predict N` | Limit max output tokens | ⚡ Moderate |
| `--warmup` | Pre-load model before first chat | ⚡ Faster first response |

## About

**🦞 LocalClaw R03** is written and maintained by **VTSTech**.

- 🌐 Website: [https://www.vts-tech.org](https://www.vts-tech.org)
- 📦 GitHub: [https://github.com/VTSTech/LocalClaw](https://github.com/VTSTech/LocalClaw)
- 💻 More projects: [https://github.com/VTSTech](https://github.com/VTSTech)

For technical architecture details, see [Architecture.md](Architecture.md).