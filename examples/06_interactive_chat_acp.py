"""
examples/06_interactive_chat_acp.py
---------------------------------
Interactive chat with tool support and ACP integration.

Demonstrates:
- Real-time activity logging
- Shell command logging
- Session token tracking
- Multi-agent visibility

Run from the project root:   python examples/06_interactive_chat_acp.py
Or from the examples folder: python 06_interactive_chat_acp.py

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, get_default_client, LOCALCLAW_BACKEND, StepResult
from localclaw.tools.builtins import make_builtin_registry
from localclaw.acp_plugin import ACPPlugin
from localclaw.model_discovery import pick_best_model, get_available_models

BACKEND_NAME = LOCALCLAW_BACKEND.upper()


# Model to test (discovered dynamically or set via environment)
preferred = os.environ.get("LOCALCLAW_MODEL")
MODEL = None  # Will be set in main()
TOOLS = ["calculator", "shell", "python_repl", "read_file", "write_file"]


def main():
    global MODEL
    client = get_default_client()
    
    if not client.is_running():
        print(f"❌ {BACKEND_NAME} is not running.")
        if LOCALCLAW_BACKEND == "bitnet":
            print("   Start llama-server from bitnet.cpp directory")
        else:
            print("   Start it with: ollama serve")
        return
    
    # Pick best model dynamically
    MODEL = pick_best_model(preferred=preferred, client=client)
    if not MODEL:
        models = get_available_models(client)
        MODEL = models[0] if models else None
    
    if not MODEL:
        print(f"❌ No models available in {BACKEND_NAME}.")
        return
    
    # ── Create and bootstrap ACP ─────────────────────────────────
    acp = ACPPlugin(
        agent_name="LocalClaw-Interactive",
        model_name=MODEL,
        debug=os.environ.get("ACP_DEBUG", "").lower() in ("1", "true"),
        on_hint=lambda h: print(f"\n   💡 Hint: {h}"),
        on_nudge=lambda n: print(f"\n   📢 Nudge: {n.get('message', '')}"),
    )
    
    bootstrap = acp.bootstrap(claim_primary=False)
    acp_connected = bootstrap.get("status") is not None
    
    if bootstrap.get("stop_flag"):
        print(f"⚠️ ACP STOP flag is set: {bootstrap.get('stop_reason')}")
        return
    
    tools = make_builtin_registry().subset(TOOLS)
    
    # Combined step callback: print + log to ACP
    def print_step(step: StepResult):
        acp.on_step(step)  # Log to ACP
        if step.type == "tool_call":
            args = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
            print(f"\n  \033[33m🔧 {step.tool_name}({args})\033[0m")
        elif step.type == "tool_result":
            preview = step.content[:100].replace("\n", " ")
            if len(step.content) > 100:
                preview += "..."
            print(f"  \033[34m📦 → {preview}\033[0m")
    
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
            "temperature": 0.3,
            "num_ctx": 2048,
            "num_predict": 512,
        },
    )
    
    print(f"\n{'='*60}")
    print(f"💬 LocalClaw Interactive Chat (ACP Enabled)")
    print(f"   Backend: {BACKEND_NAME}")
    print(f"   Model: {MODEL}")
    print(f"   Tools: {', '.join(TOOLS)}")
    print(f"   ACP: {'connected' if acp_connected else 'unavailable'}")
    print(f"{'='*60}")
    print("   Commands: /reset, /tools, /status, /tokens, /quit")
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
            # Log session end
            if acp_connected:
                status = acp.get_status()
                acp.add_note("context", f"Session ended. Tokens: {status.get('session_tokens', 0)}")
            print("👋 Goodbye!")
            break
        
        if user_input == "/reset":
            agent.reset()
            print("🔄 Conversation reset.\n")
            continue
        
        if user_input == "/tools":
            print(f"🔧 Available tools: {', '.join(t.name for t in tools.all())}\n")
            continue
        
        if user_input == "/status":
            if acp_connected:
                status = acp.get_status()
                print(f"\n📊 ACP Status:")
                print(f"   Stop flag: {status.get('stop_flag', False)}")
                print(f"   Primary agent: {status.get('primary_agent', 'none')}")
                print(f"   Running activities: {status.get('running_count', 0)}")
            else:
                print("ACP not connected\n")
            continue
        
        if user_input == "/tokens":
            if acp_connected:
                status = acp.get_status()
                agent_tokens = acp.get_agent_tokens()
                print(f"\n📊 Token Usage:")
                print(f"   Session tokens: {status.get('session_tokens', 0)}")
                print(f"   Context window: {status.get('context_window', 200000)}")
                print(f"   Remaining: {status.get('tokens_remaining', 0)}")
                print(f"   Agent breakdown: {agent_tokens}")
            else:
                print("ACP not connected\n")
            continue
        
        # Log user message to ACP
        acp.log_user_message(user_input)
        
        # Run agent
        print()
        try:
            run = agent.run(user_input)
            print(f"\n\033[32m🤖 Agent:\033[0m {run.final_answer}")
            
            # Log assistant message to ACP
            acp.log_assistant_message(run.final_answer)
            
            tool_calls = len([s for s in run.steps if s.type == "tool_call"])
            if tool_calls > 0 or run.total_ms > 5000:
                print(f"\n   \033[90m({tool_calls} tools, {run.total_ms/1000:.1f}s)\033[0m")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            acp.log_assistant_message(f"[ERROR] {str(e)[:200]}")


if __name__ == "__main__":
    main()
