"""
examples/06_interactive_chat.py
-------------------------------
Interactive chat with tool support. Good for manual testing.

Run from the project root:   python examples/06_interactive_chat.py
Or from the examples folder: python 06_interactive_chat.py

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, OllamaClient, StepResult
from localclaw.tools.builtins import make_builtin_registry


MODEL = os.environ.get("LOCALCLAW_MODEL", "qwen2.5-coder:0.5b-instruct-q4_k_m")
TOOLS = ["calculator", "shell", "python_repl", "read_file", "write_file"]


def print_step(step: StepResult):
    """Print step info with colors."""
    if step.type == "tool_call":
        args = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
        print(f"\n  \033[33m🔧 {step.tool_name}({args})\033[0m")
    elif step.type == "tool_result":
        preview = step.content[:100].replace("\n", " ")
        if len(step.content) > 100:
            preview += "..."
        print(f"  \033[34m📦 → {preview}\033[0m")


def main():
    client = OllamaClient()
    
    if not client.is_running():
        print("❌ Ollama is not running.")
        return
    
    tools = make_builtin_registry().subset(TOOLS)
    
    agent = Agent(
        model=MODEL,
        client=client,
        tools=tools,
        system_prompt=(
            "You are a helpful assistant with access to tools. "
            "Use them when needed. Be concise but informative."
        ),
        max_steps=8,
        on_step=print_step,
        model_options={
            "temperature": 0.3,     # Some creativity for chat
            "num_ctx": 2048,        # Larger context for conversation
            "num_predict": 512,     # Longer responses for chat
        },
    )
    
    print(f"\n{'='*60}")
    print(f"💬 LocalClaw Interactive Chat")
    print(f"   Model: {MODEL}")
    print(f"   Tools: {', '.join(TOOLS)}")
    print(f"{'='*60}")
    print("   Commands: /reset, /tools, /quit")
    print(f"{'='*60}\n")
    
    while True:
        try:
            user_input = input("\033[1mYou:\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break
        
        if not user_input:
            continue
        
        if user_input in ("/quit", "/exit"):
            print("👋 Goodbye!")
            break
        
        if user_input == "/reset":
            agent.reset()
            print("🔄 Conversation reset.\n")
            continue
        
        if user_input == "/tools":
            print(f"🔧 Available tools: {', '.join(t.name for t in tools.all())}\n")
            continue
        
        # Run agent
        print()
        try:
            run = agent.run(user_input)
            print(f"\n\033[32m🤖 Agent:\033[0m {run.final_answer}")
            
            tool_calls = len([s for s in run.steps if s.type == "tool_call"])
            if tool_calls > 0 or run.total_ms > 5000:
                print(f"\n   \033[90m({tool_calls} tools, {run.total_ms/1000:.1f}s)\033[0m")
        except Exception as e:
            print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
