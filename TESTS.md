# 🦞 LocalClaw R03

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
| **General use** | `qwen2.5-coder:0.5b-instruct-q4_k_m` | Best all-around, fast, great tool usage |
| **Large context** | `llama3.2:1b` | **128k context window** - handles long conversations |
| **Math tasks** | `qwen2.5-coder:0.5b` or `qwen2-math:1.5b` | Perfect math scores |
| **Reasoning tasks** | `qwen2.5:0.5b` or `qwen3:0.6b` | Perfect reasoning |
| **Tool usage** | `qwen2.5-coder:0.5b` | Most reliable tool calling |
| **Fastest inference** | `gemma3:270m` | 270M params, fastest responses |
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
