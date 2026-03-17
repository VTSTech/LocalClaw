import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, OllamaClient
from localclaw.acp_plugin import ACPPlugin

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# List extracted from your comments for iteration
MODELS_TO_TEST = [
    #"gemma3:270m",
    #"granite4:350m",
    #"qwen2.5:0.5b",
    "qwen2.5-coder:0.5b-instruct-q4_k_m",
    #"nchapman/dolphin3.0-qwen2.5:0.5b",
    #"nchapman/dolphin3.0-llama3:1b",
    #"driaforall/tiny-agent-a:1.5b",
    "deepseek-coder:1.3b",
    "AgentricAi/AgentricAI_TLM:latest",
]

TESTS = {
    "basic": [
        {
            "name": "Simple Addition",
            "prompt": "What is 2 + 2? Answer with just the number.",
            "check": lambda r: "4" in r,
        },
        {
            "name": "Multiplication",
            "prompt": "What is 7 times 8? Answer with just the number.",
            "check": lambda r: "56" in r,
        },
        {
            "name": "Capital City",
            "prompt": "What is the capital of Japan? Answer in one word.",
            "check": lambda r: "tokyo" in r.lower(),
        },
    ],
    "reasoning": [
        {
            "name": "Simple Reasoning",
            "prompt": "I have 10 apples. I eat 3 and give 2 to a friend. How many do I have left? Just the number.",
            "check": lambda r: "5" in r,
        },
        {
            "name": "Age Problem",
            "prompt": "Tom is 5 years older than Mary. Mary is 12. How old is Tom? Just the number.",
            "check": lambda r: "17" in r,
        },
    ],
    "code": [
        {
            "name": "Even Function",
            "prompt": "Write a Python function called is_even that takes a number and returns True if it's even.",
            "check": lambda r: "def is_even" in r and "return" in r,
        },
        {
            "name": "Add Function",
            "prompt": "Write a Python function called add that takes two numbers and returns their sum.",
            "check": lambda r: "def add" in r and "return" in r,
        },
    ],
}

def run_tests(model_name, client):
    """Run all test categories for a specific model with ACP tracking."""
    
    available_models = client.list_models()
    if model_name not in available_models:
        print(f"\n⚠️  Skipping '{model_name}': Not found in Ollama.")
        return

    # Create ACP plugin
    acp = ACPPlugin(
        agent_name="LocalClaw",
        model_name=model_name,
        debug=os.environ.get("ACP_DEBUG", "").lower() in ("1", "true"),
    )
    
    bootstrap = acp.bootstrap(claim_primary=False)
    acp_connected = bootstrap.get("status") is not None
    
    print(f"\n{'='*60}")
    print(f"🧪 Testing Model: {model_name}")
    print(f"   ACP: {'connected' if acp_connected else 'unavailable'}")
    print(f"{'='*60}")
    
    if acp_connected:
        acp.log_chat("system", f"Test suite started for {model_name}", complete=True)
    
    total_passed = 0
    total_tests = 0
    total_time = 0
    
    for category, tests in TESTS.items():
        print(f"\n📋 {category.upper()} TESTS")
        
        agent = Agent(
            model=model_name,
            client=client,
            system_prompt="You are a helpful assistant. Be concise and accurate.",
            max_steps=6,
            model_options={
                "temperature": 0.0,
                "num_ctx": 1024,
                "num_predict": 128,
            },
        )
        
        for test in tests:
            total_tests += 1
            t0 = time.time()
            try:
                response = agent.chat(test["prompt"])
                elapsed = time.time() - t0
                total_time += elapsed
                
                passed = test["check"](response)
                total_passed += int(passed)
                
                status = "✅ PASS" if passed else "❌ FAIL"
                preview = response[:50].replace("\n", " ")
                print(f"  {status} ({elapsed:.1f}s): {preview}...")
                
                if acp_connected:
                    acp.log_user_message(f"[TEST] {test['name']}")
                    acp.log_assistant_message(f"[{'PASS' if passed else 'FAIL'}] {response[:100]}")
            
            except Exception as e:
                print(f"  ❌ ERROR: {e}")

    # Summary for this model
    pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    print(f"\n📊 {model_name} Results: {total_passed}/{total_tests} ({pass_rate:.0f}%)")
    
    if acp_connected:
        acp.add_note("context", f"Completed {model_name}: {pass_rate:.0f}% pass rate.")

if __name__ == "__main__":
    ollama_client = OllamaClient()
    
    if not ollama_client.is_running():
        print("❌ Ollama is not running. Please start Ollama and try again.")
        sys.exit(1)

    print(f"🚀 Starting comprehensive benchmark for {len(MODELS_TO_TEST)} models...")
    
    for model in MODELS_TO_TEST:
        run_tests(model, ollama_client)
        
    print("\n✅ All scheduled model tests complete.")