# 🦞 LocalClaw R04.0.0

A minimal, hackable agentic framework engineered to run **entirely locally** with [Ollama](https://ollama.com) or [BitNet](https://github.com/microsoft/BitNet).

Inspired by the architecture of OpenClaw, rebuilt from scratch for local-first operation.

**Written by [VTSTech](https://www.vts-tech.org)** · [GitHub](https://github.com/VTSTech/LocalClaw)

[![PyPI version fury.io](https://badge.fury.io/py/localclaw.svg)](https://pypi.python.org/pypi/localclaw/) [![PyPI status](https://img.shields.io/pypi/status/localclaw.svg)](https://pypi.python.org/pypi/localclaw/) [![GitHub commits](https://badgen.net/github/commits/VTSTech/LocalClaw)](https://GitHub.com/VTSTech/LocalClaw/commit/)



[![PyPI download month](https://img.shields.io/pypi/dm/localclaw.svg)](https://pypi.python.org/pypi/localclaw/) [![PyPI download week](https://img.shields.io/pypi/dw/localclaw.svg)](https://pypi.python.org/pypi/localclaw/) [![PyPI download day](https://img.shields.io/pypi/dd/localclaw.svg)](https://pypi.python.org/pypi/localclaw/)


---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [Architecture.md](https://github.com/VTSTech/LocalClaw/blob/main/Architecture.md) | Technical documentation for developers (directory structure, core design, orchestrator modes) |
| [CHANGELOG.md](https://github.com/VTSTech/LocalClaw/blob/main/CHANGELOG.md) | Version history and release notes (R00–R04.0.0) |
| [TESTS.md](https://github.com/VTSTech/LocalClaw/blob/main/TESTS.md) | Benchmark results, model recommendations, and testing guide |

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

### 1. Test Model Tool Support (Recommended First Step)

```bash
# Test all models for native tool support
localclaw models --tool_support

# Results saved to tested_models.json for future reference
```

### 2. Single prompt

```bash
# Simple Q&A
localclaw run "What is the capital of Japan?"

# With streaming output
localclaw run "Tell me a joke." --stream

# Specify a model
localclaw run "Explain quantum computing" -m llama3.2:3b
```

### 3. Interactive chat

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

### 4. Using BitNet backend

```bash
localclaw chat --backend bitnet --force-react
localclaw run "Calculate 17 * 23" --backend bitnet --tools calculator
```

---

## Key Features

- **Zero dependencies** — uses Python stdlib only
- **Ollama + BitNet backends** — switch with `--backend` flag
- **Three-tier tool support** — native, ReAct, or none (auto-detected per model)
- **Agent Skills** — follows [Agent Skills specification](https://agentskills.io/)
- **Small model optimized** — pure reasoning mode for sub-500M models
- **Built-in security** — path validation, command blocklist, SSRF protection

---

## Tool Support Levels

LocalClaw automatically detects each model's tool support level:

| Level | Description | When to Use |
|-------|-------------|-------------|
| `native` | Ollama API tool-calling | Models trained for function calling |
| `react` | Text-based ReAct prompting | Models that accept tools but need format guidance |
| `none` | No tool support | Models that reject tools; use pure reasoning |

### Testing Tool Support

```bash
# Test all models
localclaw models --tool_support

# Example output:
  Model                                      Family       Context    Tool Support
  ──────────────────────────────────────────────────────────────────────────────
  gemma3:270m                                gemma3       32K        ○ none
  granite4:350m                              granite      32K        ✓ native
  qwen2.5-coder:0.5b-instruct-q4_k_m         qwen2        32K        ReAct
  functiongemma:270m                         gemma3       32K        ✓ native
```

### Performance by Tool Support

Recent GSM8K benchmark results (50 math questions):

| Model | Params | Tool Support | Score |
|-------|--------|--------------|-------|
| `gemma3:270m` | 270M | none | **64%** |
| `functiongemma:270m` | 270M | native | 36% |
| `granite4:350m` | 350M | native | ~40% |

**Key insight**: Sub-500M models often perform better with `none` (pure reasoning) than with tools!

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `run "prompt"` | Run single prompt and exit |
| `chat` | Interactive multi-turn conversation |
| `models` | List available Ollama models with tool support info |
| `tools` | List built-in tools |
| `skills` | List available Agent Skills |
| `test [example]` | Run example/test scripts (`--list` to see all) |
| `modelfile [model]` | Show model's Modelfile system prompt |

### Key Flags

| Flag | Description |
|------|-------------|
| `-m`, `--model` | Model name (default: qwen2.5-coder:0.5b) |
| `--tools` | Comma-separated tool list |
| `--skills` | Comma-separated skill list |
| `--backend` | `ollama` or `bitnet` |
| `--stream` | Stream output token-by-token |
| `--fast` | Preset: reduced context for speed |
| `-v`, `--verbose` | Show tool calls and timing |
| `--acp` | Enable ACP (Agent Control Panel) integration |
| `--use-mf-sys` | Use Modelfile system prompt instead of LocalClaw default |
| `--force-react` | Force ReAct mode for all models |
| `--debug` | Show debug info (parsed tool calls, fuzzy matching) |
| `--num-ctx` | Context window size for test commands |
| `--num-predict` | Max tokens to predict for test commands |

### Models Command

```bash
# List models with family, context size, and tool support
localclaw models

# Test each model for native tool support (recommended)
localclaw models --tool_support
```

Output shows:
- **Model** - Model name
- **Family** - Model family from Ollama API
- **Context** - Context window size
- **Tool Support** - `✓ native`, `ReAct`, `○ none`, or `untested`

```
🦞 LocalClaw R04.0.0 Models
  Model                                      Family       Context    Tool Support
  ──────────────────────────────────────────────────────────────────────────────
  gemma3:270m                                gemma3       32K        ○ none
  granite4:350m                              granite      32K        ✓ native
  qwen2.5-coder:0.5b-instruct-q4_k_m         qwen2        32K        ReAct
  functiongemma:270m                         gemma3       32K        untested

  1 model(s) untested. Use --tool_support to detect native support.
```

### Test Command Examples

```bash
# List all available tests
localclaw test --list

# Run a quick test suite
localclaw test quick

# Run GSM8K benchmark (50 math questions)
localclaw test 14 --acp --timeout 6400

# Run with debug output
localclaw test 02 --debug --verbose
```

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
| `save_note` / `get_note` | Save and retrieve notes |

---

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `BITNET_BASE_URL` | BitNet server URL | `http://localhost:8765` |
| `ACP_BASE_URL` | ACP (Agent Control Panel) server URL | `http://localhost:8766` |
| `LOCALCLAW_BACKEND` | Backend: `ollama` or `bitnet` | `ollama` |
| `LOCALCLAW_MODEL` | Default model | `qwen2.5-coder:0.5b-instruct-q4_k_m` |
| `LOCALCLAW_SECURITY_MODE` | Security mode: `strict`, `permissive`, `disabled` | `permissive` |

---

## Setup Ollama

```bash
# Make sure Ollama is running:
ollama serve

# Pull a model:
ollama pull qwen2.5-coder:0.5b-instruct-q4_k_m

# Test tool support:
localclaw models --tool_support
```

---

## About

**🦞 LocalClaw ** is written and maintained by **VTSTech**.

- 🌐 Website: [https://www.vts-tech.org](https://www.vts-tech.org)
- 📦 GitHub: [https://github.com/VTSTech/LocalClaw](https://github.com/VTSTech/LocalClaw)
- 💻 More projects: [https://github.com/VTSTech](https://github.com/VTSTech)

---

For more details, see:
- [Architecture.md](https://github.com/VTSTech/LocalClaw/blob/main/Architecture.md) — Technical architecture and design decisions
- [CHANGELOG.md](https://github.com/VTSTech/LocalClaw/blob/main/CHANGELOG.md) — Version history and release notes
- [TESTS.md](https://github.com/VTSTech/LocalClaw/blob/main/TESTS.md) — Benchmark results and model recommendations
