# 🦞 LocalClaw R03

## GSM8K Benchmark Results (with Calculator Tool)

The following models have been tested on a **50-question GSM8K-style benchmark** using the Agent system with a calculator tool.

### Native Tools (Modelfile Prompts, No Custom/System Prompt)

| Rank | Model | Score | Accuracy | Avg Time | Notes |
|:----:|-------|------:|--------:|--------:|-------|
| 🥇 | **`nchapman/dolphin3.0-qwen2.5:0.5b`** | **34/50** | **68.0%** | 4.7s | Best native tool caller! |
| 🥈 | `qwen2.5:0.5b` | 33/50 | 66.0% | 13.6s | Strong performer |
| 🥉 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | 25/50 | 50.0% | 12.6s | Good but slower |
| 4 | `nchapman/dolphin3.0-llama3:1b` | 21/50 | 42.0% | 5.6s | Fast inference |
| 5 | `granite4:350m` | 20/50 | 40.0% | 22.5s | Struggles with native tools |
| 6 | `gemma3:270m` | 3/50 | 6.0% | 0.8s | Too small for complex tasks |

**Key Insight**: Dolphin fine-tunes show improved native tool calling performance.
- `dolphin3.0-qwen2.5:0.5b` outperforms base `qwen2.5:0.5b` (68% vs 66%) while being ~3x faster
- `dolphin3.0-llama3:1b` (42%) significantly trails the qwen-based dolphin (68%)
- **gemma3:270m** is extremely fast (0.8s) but lacks reasoning capability for GSM8K

### With `--force-react` (Text-based ReAct)

| Rank | Model | Score | Time | Avg/Question | Notes |
|:----:|-------|------:|-----:|-------------:|-------|
| 🥇 | **`driaforall/tiny-agent-a:1.5b`** | **47/50 (94%)** | 1470s | ~29s | **Top performer!** |
| 🥈 | `granite4:350m` | 41/50 (82%) | 960s | ~19s | **Best sub-500M!** |
| 🥉 | `nchapman/dolphin3.0-llama3:1b` | 33/50 (66%) | 847s | ~17s | Good reasoning |
| 4 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | 28/50 (56%) | 671s | ~13s | ⚠️ Timed out |
| 5 | `granite` | 23/50 (46%) | 1312s | ~26s | Slow but stable |
| - | `AgentricAi/AgentricAI_TLM:latest` | 0/50 (0%) | — | — | Needs native tools |

### Key Finding: ReAct Mode Dramatically Improves Small Model Performance

| Model | Native Tools | With `--force-react` | Improvement |
|-------|--------------|---------------------|-------------|
| `driaforall/tiny-agent-a:1.5b` | **70%** (33.8s) | **94%** (1470s) | **+24%** |
| `granite4:350m` | 40% | **82%** | **+42%** |
| `dolphin3.0-llama3:1b` | 42% | **66%** | **+24%** |
| `qwen2.5-coder:0.5b` | 50% | 56% | +6% |
| `qwen2.5:0.5b` | 66% | ? | ? |
| `dolphin3.0-qwen2.5:0.5b` | 68% | ? | ? |
| `granite` | ? | 46% | ? |

**Key Insight**: ReAct mode is NOT universally better - it depends on the model's training.
- Models trained for chat/dialogue (granite4, tiny-agent-a) benefit significantly
- Models fine-tuned for tool calling (qwen2.5-coder) may perform worse with ReAct
- **tiny-agent-a:1.5b** shows dramatic improvement: 70% → 94% with ReAct, though much slower (33.8s vs 1470s)
- **granite4:350m** shows the biggest improvement: 40% → 82% with ReAct (+42%)

---

## Tested Small Models (≤1.5B parameters)

The following models have been tested with a **15-test benchmark** (3 tests per category: Math, Reasoning, Knowledge, Calc Tool, Code).

### Rankings

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

---

## BitNet Benchmark Results

LocalClaw has been tested with **Microsoft BitNet-b1.58-2B-4T** — a 2B parameter model with 1.58-bit ternary weights.

### Test Results Summary

| Test Suite | Score | Time | Notes |
|------------|-------|------|-------|
| **Model Comparison** (15 tests) | **13/15 (87%)** | 394s | 5 categories |
| **Robust Comparison** (22 tests) | **19/22 (86%)** | ~6min | Incremental save |
| **Comprehensive Test** (7 tests) | **6/7 (86%)** | ~90s | Basic + Reasoning + Code |

### Category Breakdown

| Category | Score | Pass Rate |
|----------|-------|-----------|
| **Math** | 3/3 | 100% ✅ |
| **Code** | 3/3 | 100% ✅ |
| **Calc (with tools)** | 3/3 | 100% ✅ |
| **Reasoning** | 2/3 | 67% |
| **Knowledge** | 2/3 | 67% |

### BitNet vs Ollama Small Models

| Rank | Model | Score | Params | Backend |
|:----:|-------|------:|-------:|---------|
| 🥇 | `qwen2.5-coder:0.5b-instruct-q4_k_m` | 14/15 (93%) | 494M | Ollama |
| 🥈 | **`BitNet-b1.58-2B-4T`** | **13/15 (87%)** | **2B** | **BitNet** |
| 🥉 | `granite3.1-moe:1b` | 12/15 (80%) | 1B MoE | Ollama |
| 4 | `llama3.2:1b` | 12/15 (80%) | 1.2B | Ollama |

---

### Recommendations

| Use Case | Recommended Model | Why |
|----------|-------------------|-----|
| **Best overall** | **`tiny-agent-a:1.5b` + `--force-react`** | **94% GSM8K - highest score!** |
| **Best native tools** | `dolphin3.0-qwen2.5:0.5b` | 68% GSM8K with fast 4.7s avg - no ReAct needed |
| **Smallest capable** | `granite4:350m` + `--force-react` | 82% GSM8K - best sub-500M model with ReAct |
| **General use** | `qwen2.5-coder:0.5b-instruct-q4_k_m` | Fast, great native tool calling |
| **Large context** | `llama3.2:1b` | **128k context window** |
| **CPU-only** | `BitNet-b1.58-2B-4T` | Efficient ternary weights, no GPU needed |

---

## Running the Examples

```bash
# Make sure Ollama is serving and you have a model pulled
ollama pull qwen2.5-coder:0.5b-instruct-q4_k_m

# List all available examples
localclaw test --list

# Quick test suite (recommended first run - skips long benchmarks)
localclaw test quick

# Full test suite (all examples)
localclaw test all

# Run a specific example
localclaw test 01          # Basic agent demo
localclaw test 02          # Tool agent demo
localclaw test 04_acp      # Comprehensive test with ACP tracking
```
