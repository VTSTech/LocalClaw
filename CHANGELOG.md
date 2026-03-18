# Changelog

All notable changes to LocalClaw will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [R03.0.4] - 2026-03-18

### Fixed
- **Argparse help display in Google Colab** - Disabled all ANSI color codes by default
  - Set `_NO_COLOR = True` unconditionally to eliminate any ANSI escape sequence issues
  - Colors were causing terminal output truncation in Colab's `TERM=screen` environment
  
### Fixed
- **Argparse help display in Google Colab** - Final fix: removed emoji from argparse description entirely
  - Emojis in argparse description cause terminal width calculation issues in Colab's `TERM=screen` environment
  - Removed custom `WideHelpFormatter` class - standard `RawDescriptionHelpFormatter` works fine
  - Help now displays correctly: description, positional arguments, options, examples

### Fixed
- **Argparse help display in Google Colab** - Removed emoji from description (emojis break argparse's width calculation in Colab's terminal)
- Help now displays correctly with positional arguments section visible

### Fixed
- **Argparse help display in Google Colab** - Shortened description and moved URLs to epilog to prevent truncation in environments with non-standard terminals
- Added `WideHelpFormatter` with forced width of 200 characters for better compatibility
- URLs now display correctly in the help epilog section

---

## [R03.0.3] - 2026-03-18

### Fixed
- **Argparse help display in Google Colab** - Added `WideHelpFormatter` with minimum width of 120 characters to fix truncation issues in environments with non-standard terminals (Google Colab, some Docker containers)
- Removed unnecessary Colab color detection - ANSI colors work fine in Colab, the issue was argparse width calculation

---

## [R03.0.2] - 2026-03-18

### Changed
- **Documentation restructure** - README.md split into modular documentation files
  - `README.md` now serves as concise entry point (~180 lines, down from ~420)
  - `Architecture.md` - Technical documentation for developers (directory structure, design decisions, orchestrator modes)
  - `CHANGELOG.md` - Version history and release notes
  - `TESTS.md` - Benchmark results, model recommendations, and testing guide
  - Added Documentation table in README with clear links to all supporting files
- **Fixed version mismatch** - `__init__.py` now correctly shows 0.3.0.2 (was behind at 0.3.0)

---

## [R03] - 2026-03-17

### Added
- **BitNet Backend Support** - Alternative inference backend using Microsoft's BitNet b1.58 2-bit quantization
  - New `BitnetClient` class in `localclaw/bitnet_client.py` (simplified from 667 to 149 lines)
  - Setup helper in `localclaw/bitnet_setup.py` for cloning and compiling BitNet
  - CLI flag `--backend bitnet` to switch from Ollama to BitNet
  - Supported models: `BitNet-b1.58-2B-4T`, `Falcon3-1B-Instruct-1.58bit`, `Falcon3-3B-Instruct-1.58bit`, `Falcon3-7B-Instruct-1.58bit`
  - Model download via `huggingface-cli` or `wget` with automatic safetensors→GGUF conversion
- **Enhanced Security in Built-in Tools**
  - Path validation with configurable allowed directories (`LOCALCLAW_ALLOWED_PATHS`)
  - Command blocklist with dangerous commands blocked (`LOCALCLAW_BLOCKED_COMMANDS`)
  - Dangerous pattern detection (piping to bash, command substitution, device writes)
  - SSRF protection in `http_get` with private IP blocking and DNS rebinding prevention
  - Three security modes: `strict`, `permissive`, `disabled` (`LOCALCLAW_SECURITY_MODE`)
- **ACP Plugin Enhancements**
  - Merged `acp_streaming.py` into `acp_plugin.py` for unified ACP support
  - Added `CostTracker` and `SessionHealth` classes for monitoring
  - JSON-RPC 2.0 support for A2A compliance
  - Agent Card discovery via `/.well-known/agent-card.json`
  - Auto-generated AgentSkills from tool mapping
- **Agent Improvements**
  - Pre-call argument synthesis for missing required arguments
  - Redundant calculator call detection to avoid unnecessary tool invocations
  - Enhanced few-shot prompting for small models
  - Improved date/time query handling with automatic Python code synthesis
- **Test Scripts for BitNet**
  - `test-bitnet.sh` / `test-bitnet.cmd` - Run benchmark tests with BitNet backend

### Changed
- Version tags updated from R02 to R03 across all files
- CLI now supports `--backend ollama|bitnet` flag for backend selection
- Tool system now has comprehensive security validation layer
- ACP streaming functionality consolidated into main plugin
- README.md rewritten with CLI command examples instead of Python code
- README.md added comprehensive BitNet section with model download instructions
- ACP benchmark tests (`07_model_comparison_acp.py`, `08_robust_comparison_acp.py`) now display proper model names for path-style BitNet models

### Fixed
- **ACP model name display** - Path-style model names (e.g., `Falcon3-1B-Instruct-1.58bit/ggml-model-i2_s.gguf`) now show directory name instead of GGUF filename in activity log

### Removed
- `localclaw/acp_streaming.py` - merged into `acp_plugin.py`

### Tested
- BitNet backend with `Falcon3-1B-Instruct-1.58bit` model - ✅ Working
- Model conversion from safetensors to GGUF via `setup_env.py` - ✅ Working
- ACP benchmark tests with BitNet models - ✅ Working

### Known Issues
- BitNet models require `--force-react` as they don't support native tool calling
- BitNet backend requires separate `llama-server` process running
- Intermediate conversion files (~8GB) should be deleted after model setup: `model.safetensors`, `ggml-model-f32.gguf`

---

## [R02] - 2026-03-10

### Added
- **`--stream` flag** for CLI - enables token-by-token streaming output for better UX on slow connections
  - Works in both `run` and `chat` commands
  - Shows output as it's generated instead of waiting for complete response
- **Comprehensive CLI help** - main `-h` now shows all available options for run/chat commands

### Changed
- Version tags updated from R01 to R02 across all files
- **Test output verbosity** - no more truncation, shows full content for debugging

### Fixed
- **Small model tool calling** - Identified working models and optimal settings:
  - `functiongemma:270m` (270M params) - ✅ Works, ~5s response
  - `qwen2.5:0.5b` (494M params) - ✅ Works, ~7s response
  - `granite4:350m` (352M params) - ✅ Works, ~10s response
- **Test integrity issues** - Fixed examples that were providing answers in prompts:
  - `05_tool_tests.py` - Now asks questions without providing expressions/code
  - `10_skills_demo.py` - Agent generates skill content autonomously
  - `11_skill_creator_test.py` - Tests actual skill creation, not copying

### Known Issues
- `smollm:135m` and `gemma3:270m` don't support tools (HTTP 400)
- `qwen2.5-coder:0.5b` and `qwen3:0.6b` output tool calls as text instead of executing

---

## [R01] - 2026-03-09 to 2026-03-10

### Added
- **Fuzzy argument name matching** for tool invocation - handles small model hallucinations of argument names (e.g., `filepath` → `path`, `data` → `content`)
- **Nested tool_args extraction** - handles when models output `{"tool": "name", "tool_args": {...}}` format
- **Test scripts for all platforms**:
  - `test.sh` / `test.cmd` - Run all 11 examples
  - `test-quick.sh` / `test-quick.cmd` - Run 7 quick tests (skips benchmarks)
  - `run.sh` / `run.cmd` - Interactive menu for single example selection
- **Environment variables for test configuration**:
  - `LOCALCLAW_VERBOSE=1` - Show detailed tool calls
  - `LOCALCLAW_TIMEOUT=120` - Timeout per test in seconds
  - `LOCALCLAW_MODEL=<model>` - Override default model
- **Proper exit codes** for all test scripts (0=success, 1=failure)
- **Tool verification** in tests - detects when models hallucinate answers without calling tools
- **YAML validation** for skill files with partial credit for incomplete skills
- **datetime skill** - Date and time utilities
- **web_search skill** - Web search capabilities
- **Example 11**: `11_skill_creator_test.py` - Benchmark skill creation across models

### Changed
- **Trimmed skill-creator SKILL.md** from 373 lines to 111 lines (70% reduction) - made framework-agnostic
- **Improved test verbosity** with detailed step output showing tool calls and results
- **Fixed 08_robust_comparison.py** - no longer deletes results file on startup (proper resumability)
- **Rewrote 05_tool_tests.py** with tool verification and proper expected values for all tests
- **Rewrote 11_skill_creator_test.py** with YAML validation, timeout handling, and detailed error reporting

### Fixed
- **Tool invocation failures** when small models pass wrong argument names
- **False positive test results** when models hallucinate without using tools
- **Resumability bug** in 08_robust_comparison.py that deleted progress on restart

### Technical Details
- Added `_fuzzy_match_args()` method in `localclaw/core/tools.py` with alias dictionary for common argument variants
- Added nested argument extraction in `_normalize_args()` in `localclaw/core/agent.py`
- Argument aliases: `filepath→path`, `data→content`, `expr→expression`, `search→query`, `cmd→command`, `uri→url`

---

## [R00] - 2026-03-09

### Added
- **Skills system** following Agent Skills specification
- **skill-creator skill** - OpenClaw's platform-agnostic skill generator
- **Progressive disclosure** - three-level loading (metadata, instructions, resources)
- **SkillLoader** and **SkillRegistry** for skill management
- **Example 10**: `10_skills_demo.py` - Skills system demonstration
- **CLI improvements** with `/save` and `/load` commands for conversation persistence
- **Remote Ollama support** via environment variables:
  - `OLLAMA_TIMEOUT` - Request timeout
  - `OLLAMA_MAX_RETRIES` - Max retry attempts
  - `OLLAMA_RETRY_DELAY` - Initial retry delay

### Changed
- Renamed from earlier development versions to R00 as first tagged release
- Improved error messages and validation

---

## [R0] - 2026-02-06 to 2026-03-09

### Added
- **Core framework** with zero external dependencies (stdlib only)
- **Agent class** with ReAct loop supporting:
  - Native Ollama tool-calling protocol
  - Text-based ReAct fallback for non-tool models
  - Streaming responses via generator interface
  - Multi-step reasoning with configurable max steps
- **OllamaClient** - Zero-dependency HTTP wrapper using urllib
- **ToolRegistry** - Decorator-based tool registration with:
  - Auto-generated JSON schemas from Python type hints
  - Tool subset selection for different agents
  - Fuzzy tool name matching for small model hallucinations
- **Memory system** - Sliding-window conversation memory with:
  - Optional LLM-based summarization
  - Turn archiving when window fills
- **Orchestrator** - Multi-agent routing with:
  - Router mode (LLM picks best agent)
  - Pipeline mode (sequential chain)
  - Parallel mode (concurrent execution with merge)
- **Built-in tools**:
  - `calculator` - Safe math expression evaluator
  - `shell` - Shell command execution with timeout
  - `read_file` / `write_file` - File I/O
  - `list_directory` - Directory listing
  - `http_get` - HTTP GET requests
  - `web_search` - DuckDuckGo search (no API key)
  - `python_repl` - Python code execution
  - `save_note` / `get_note` / `list_notes` - Note storage
- **Small model support** (≤1.5B parameters):
  - Fuzzy tool name matching
  - Argument auto-fixing
  - JSON response cleaning
  - Unicode normalization
  - ReAct text parsing fallback
- **Examples**:
  - `01_basic_agent.py` - Simple Q&A demo
  - `02_tool_agent.py` - Tool calling demo
  - `03_orchestrator.py` - Multi-agent routing demo
  - `04_comprehensive_test.py` - Full test suite
  - `05_tool_tests.py` - Tool-specific tests
  - `06_interactive_chat.py` - Interactive CLI chat
  - `07_model_comparison.py` - Model benchmark (15 tests)
  - `08_robust_comparison.py` - Progress-saving comparison
  - `09_expanded_benchmark.py` - Expanded benchmark (25 tests)
- **CLI interface** (`cli.py`) with:
  - Chat mode with tool support
  - Model listing
  - Tool listing
  - Skill listing
  - Debug and verbose modes
  - Fast mode for quicker responses

### Supported Models (Tool-calling)
- Meta Llama: llama3, llama3.1, llama3.2, llama3.3
- Mistral AI: mistral, mixtral, mistral-nemo, codestral
- Alibaba Qwen: qwen2, qwen2.5, qwen3, qwen2.5-coder
- Cohere: command-r, command-r7b
- DeepSeek: deepseek, deepseek-coder, deepseek-v2/v3
- Microsoft Phi: phi-3, phi-4
- Google Gemma: functiongemma
- Others: yi, internlm2, solar, glm4, hermes, nemotron

### Tested Small Models (≤1.5B)
| Rank | Model | Score | Notes |
|------|-------|-------|-------|
| 🥇 | qwen2.5-coder:0.5b | 93% | Best overall |
| 🥈 | granite3.1-moe:1b | 80% | Strong knowledge |
| 🥉 | llama3.2:1b | 80% | 128k context |

---

## [R1-R7] - 2026-02-08 to 2026-02-17

Early development iterations building the core framework.

### R7 (2026-02-16 to 2026-02-17)
- 11 commits
- Further refinements and testing

### R6 (2026-02-16)
- 1 commit
- Minor update

### R4 (2026-02-09)
- 8 commits
- Bug fixes and improvements

### R3 (2026-02-09)
- 4 commits
- Feature additions

### R2 (2026-02-08 to 2026-02-09)
- 6 commits
- Core functionality expansion

### R1 (2026-02-08)
- 4 commits
- Initial agent implementation

---

## Version Naming Convention

- **R0, R1, R2...** - Development iterations
- **R00, R01, R02...** - Tagged releases
- Each tagged release includes all changes from development iterations since the previous release

---

## Small Model Tool Calling Guide

### Models that WORK (≤600M params)
| Model | Size | Tool Support | Speed |
|-------|------|--------------|-------|
| `functiongemma:270m` | 270M | ✅ Native | ~5s |
| `qwen2.5:0.5b` | 494M | ✅ Native | ~7s |
| `granite4:350m` | 352M | ✅ Native | ~10s |

### Optimal Settings for Small Models
```python
model_options={
    "temperature": 0.0,    # Deterministic
    "num_ctx": 1024,       # Smaller context
    "num_predict": 512,    # Limit output
}
```

### Models that DON'T work
- `smollm:135m` - No tool support (HTTP 400)
- `gemma3:270m` - No tool support (HTTP 400)
- `qwen2.5-coder:0.5b` - Outputs tool calls as text
- `qwen3:0.6b` - Outputs tool calls as text

---

## Links

- **Repository**: https://github.com/VTSTech/LocalClaw
- **Author**: [VTSTech](https://www.vts-tech.org)
- **Inspiration**: OpenClaw

---

*This changelog is maintained by VTSTech. For the full commit history, see [GitHub Commits](https://github.com/VTSTech/LocalClaw/commits/main/).*
