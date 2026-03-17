#!/usr/bin/env python3
"""
🦞 LocalClaw R03 — CLI
Entry point: localclaw <command> [options]

Commands:
  run     Run the agent on a single prompt and exit
  chat    Interactive multi-turn conversation with memory
  models  List models available in Ollama
  tools   List available built-in tools
  skills  List available Agent Skills

Examples:
  localclaw run "What is the capital of France?"
  localclaw run "What is sqrt(144)?" --tools calculator
  localclaw chat --model llama3.1:8b --tools calculator,shell
  localclaw chat --skills skill-creator --tools write_file,shell
  localclaw models
  localclaw tools
  localclaw skills

Written by VTSTech · https://www.vts-tech.org · https://github.com/VTSTech/LocalClaw — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import textwrap
import time
from pathlib import Path

# Allow running as `python cli.py` or as installed entry point
_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
if _root not in sys.path:
    sys.path.insert(0, _root)

from localclaw import Agent, OllamaClient, StepResult
from localclaw.config import OLLAMA_BASE_URL, ACP_BASE_URL, BITNET_BASE_URL  # Add BITNET_BASE_URL here
from localclaw.core.memory import Message
from localclaw.tools.builtins import BUILTIN_REGISTRY
from localclaw.skills import SkillLoader, SkillRegistry
from localclaw.acp_plugin import ACPPlugin
try:
    from localclaw.bitnet_client import BitnetClient, KNOWN_MODELS
    _BITNET_AVAILABLE = True
except ImportError:
    _BITNET_AVAILABLE = False

# Global reference for A2A processing (set in cmd_chat)
_acp_plugin = None
_tools_registry = None


def _execute_a2a_tool(action: str, payload: dict) -> any:
    """Execute an A2A action using the available tools registry."""
    global _tools_registry
    
    if not _tools_registry:
        return {"error": "No tools available"}
    
    # Map A2A actions to tool names
    action_to_tool = {
        "read_file": "read_file",
        "write_file": "write_file",
        "list_directory": "list_directory",
        "shell": "shell",
        "execute_python": "python_repl",
        "execute_code": "python_repl",
        "python_repl": "python_repl",
    }
    
    tool_name = action_to_tool.get(action, action)
    tool = _tools_registry.get(tool_name)
    
    if not tool:
        return {"error": f"Tool not found: {tool_name} (action: {action})"}
    
    try:
        # Execute the tool with the payload as kwargs
        result = tool.fn(**payload)
        return result
    except Exception as e:
        return {"error": str(e)}


def _on_a2a_message_callback(hints: dict):
    """Callback to process A2A messages automatically when notified."""
    global _acp_plugin
    
    pending_count = hints.get("pending_count", 0)
    senders = hints.get("senders", [])
    
    if pending_count > 0 and _acp_plugin:
        print()
        print(cyan(f"  📨 Processing {pending_count} A2A message(s) from {senders}..."))
        
        # Process the inbox
        results = _acp_plugin.a2a_process_inbox(
            tool_executor=_execute_a2a_tool,
            auto_respond=True
        )
        
        for r in results:
            status = green("✓") if r.get("status") == "processed" else yellow("○")
            action = r.get("action", "unknown")
            from_agent = r.get("from_agent", "unknown")
            result_preview = ""
            if r.get("result"):
                result_str = str(r.get("result"))[:60]
                result_preview = f" → {result_str}"
            elif r.get("error"):
                result_preview = f" ✗ {r.get('error')}"
            print(dim(f"    {status} {action} from {from_agent}{result_preview}"))
        print()


# ------------------------------------------------------------------ #
#  Helper functions                                                    #
# ------------------------------------------------------------------ #

def _count_messages(history) -> dict:
    """Count messages by role in history."""
    return {
        'user': sum(1 for m in history if m.role == 'user'),
        'assistant': sum(1 for m in history if m.role == 'assistant'),
        'tool': sum(1 for m in history if m.role == 'tool'),
        'total': len(history),
    }


# ------------------------------------------------------------------ #
#  Colour helpers                                                     #
# ------------------------------------------------------------------ #

_NO_COLOR = not sys.stdout.isatty() or os.environ.get("NO_COLOR")

def _c(code: str, text: str) -> str:
    if _NO_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"

def dim(t):    return _c("2", t)
def bold(t):   return _c("1", t)
def green(t):  return _c("32", t)
def yellow(t): return _c("33", t)
def cyan(t):   return _c("36", t)
def red(t):    return _c("31", t)
def blue(t):   return _c("34", t)
def magenta(t): return _c("35", t)


# ------------------------------------------------------------------ #
#  Step callback for --verbose                                        #
# ------------------------------------------------------------------ #

def _make_step_printer(verbose: bool, debug: bool = False):
    def on_step(step: StepResult):
        if step.type == "tool_call":
            args_str = ", ".join(f"{k}={repr(v)}" for k, v in (step.tool_args or {}).items())
            print(f"  {yellow('⚙')}  {bold(step.tool_name)}({args_str})")
        elif step.type == "tool_result":
            result_preview = step.content[:120] + ("…" if len(step.content) > 120 else "")
            print(f"  {blue('↳')}  {dim(result_preview)}")
        elif step.type == "thought" and verbose:
            wrapped = textwrap.fill(step.content, width=80, initial_indent="     ", subsequent_indent="     ")
            print(f"  {dim('💭')} {dim(wrapped.strip())}")
        if debug and hasattr(step, 'debug_info') and step.debug_info:
            print(f"  {magenta('🔍')} {dim(step.debug_info)}")
    return on_step


# ------------------------------------------------------------------ #
#  Build agent from parsed args                                       #
# ------------------------------------------------------------------ #

def _build_agent(args, client: OllamaClient):
    # Resolve tools
    tools_registry = None
    if args.tools:
        names = [t.strip() for t in args.tools.split(",")]
        unknown = [n for n in names if BUILTIN_REGISTRY.get(n) is None]
        if unknown:
            print(red(f"Unknown tools: {', '.join(unknown)}"))
            print(f"Run {bold('localclaw tools')} to see available tools.")
            sys.exit(1)
        tools_registry = BUILTIN_REGISTRY.subset(names)

    # Resolve skills
    skill_registry = SkillRegistry()
    if args.skills:
        loader = SkillLoader()
        names = [s.strip() for s in args.skills.split(",")]
        for name in names:
            try:
                skill = loader.load(name)
                skill_registry.add(skill)
            except Exception as e:
                print(red(f"Failed to load skill '{name}': {e}"))
                print(f"Run {bold('localclaw skills')} to see available skills.")
                sys.exit(1)

    # Build system prompt — structured for small model reliability
    if getattr(args, "system", None):
        system_prompt = args.system
    else:
        tool_lines = ""
        if tools_registry:
            for t in tools_registry.all():
                params = ", ".join(
                    p.name + ("?" if not p.required else "")
                    for p in t.params
                )
                tool_lines += f"  - {t.name}({params}): {t.description}\n"
        else:
            tool_lines = "  (no tools loaded)\n"
        system_prompt = (
            "You are LocalClaw, a helpful AI assistant that can use tools.\n"
            "\n"
            "TOOLS AVAILABLE:\n"
            + tool_lines +
            "\n"
            "RULES:\n"
            "1. To use a tool, reply with ONLY raw JSON on a single line — "
            "no markdown, no explanation before or after:\n"
            '   {"name": "tool_name", "arguments": {"param": "value"}}\n'
            "2. Wait for the tool result before continuing.\n"
            "3. If you do NOT need a tool, reply normally in plain text.\n"
            "4. Never invent tool names. Only use the tools listed above.\n"
            "5. Never wrap JSON in ```json``` fences.\n"
            "\n"
            "EXAMPLE:\n"
            "User: What files are in the current directory?\n"
            'Assistant: {"name": "list_directory", "arguments": {"path": "."}}\n'
            "Tool result: file1.py  file2.txt  README.md\n"
            "Assistant: The directory contains: file1.py, file2.txt, and README.md.\n"
            "\n"
            "Now help the user with their request."
        )
    
    # Add skill instructions if skills are loaded
    if len(skill_registry) > 0:
        system_prompt += "\n\n" + skill_registry.to_system_prompt_addition()

    # Get temperature
    temperature = getattr(args, "temperature", 0.7)
    
    # Create ACP plugin if requested
    acp_plugin = None
    if getattr(args, "acp", False):
        acp_plugin = ACPPlugin(
            agent_name="LocalClaw",
            model_name=args.model,
            debug=getattr(args, "debug", False),
            on_a2a_message=_on_a2a_message_callback,  # Auto-process A2A messages
        )
        if getattr(args, "verbose", False):
            print(dim(f"  🔗 ACP enabled: {acp_plugin.base_url}"))

    # Build model options for performance tuning
    model_options = {"temperature": temperature} if temperature else {}
    
    # Apply --fast preset if specified
    if getattr(args, "fast", False):
        model_options["num_ctx"] = 2048
        model_options["num_predict"] = 256
        if getattr(args, "verbose", False):
            print(dim("  🚀 Fast mode: num_ctx=2048, num_predict=256"))
    
    # Apply individual options (override --fast if specified)
    if getattr(args, "num_ctx", None):
        model_options["num_ctx"] = args.num_ctx
    if getattr(args, "num_predict", None):
        model_options["num_predict"] = args.num_predict
    
    # Combine step callbacks: verbose printer + ACP plugin
    def combined_on_step(step):
        # Always call printer first (for verbose output)
        _make_step_printer(getattr(args, "verbose", False), getattr(args, "debug", False))(step)
        # Then call ACP plugin if enabled
        if acp_plugin:
            acp_plugin.on_step(step)

    agent = Agent(
        model=args.model,
        tools=tools_registry,
        system_prompt=system_prompt,
        client=client,
        on_step=combined_on_step,
        model_options=model_options,
        force_react=getattr(args, "force_react", False),
        debug=getattr(args, "debug", False),
    )
    
    # Store globals for A2A processing
    global _acp_plugin, _tools_registry
    _acp_plugin = acp_plugin
    _tools_registry = tools_registry
    
    return agent, skill_registry, acp_plugin


# ------------------------------------------------------------------ #
#  Commands                                                           #
# ------------------------------------------------------------------ #

def cmd_models(args):
    backend = getattr(args, "backend", "ollama")
    
    if backend == "bitnet":
        if not _BITNET_AVAILABLE:
            print(red("✗  bitnet_client.py not found. Copy it into localclaw/."))
            sys.exit(1)
            
        print(bold("\n🦞 LocalClaw R03 BitNet Model (Remote)"))
        
        # We use the client logic to see what is actually running at the URL
        try:
            client = _build_client(args)
            models = client.list_models() # BitnetClient should return the loaded .gguf info
            
            if models:
                print(bold(f"  {'Model Name':<50} {'Status'}"))
                print(dim("  " + "─" * 60))
                for m in models:
                    print(f"  {cyan(m):<50} {green('ACTIVE')}")
            else:
                print(yellow("  No active model found at the BitNet endpoint."))
        except Exception as e:
            print(red(f"  ✗ Could not connect to BitNet backend: {e}"))
        print()
        return
    client = OllamaClient()
    if not client.is_running():
        print(red("✗  Ollama is not running. Start it with: ollama serve"))
        sys.exit(1)

    models = client.list_models()
    if not models:
        print(yellow("No models found. Pull one with: ollama pull llama3.2:3b"))
        return

    print(bold("\n🦞 LocalClaw R03 Models") + dim(" · Written by VTSTech · https://www.vts-tech.org · https://github.com/VTSTech/LocalClaw"))
    print(bold(f"{'Model':<40} {'Tool support':>12}"))
    print(dim("─" * 54))
    for m in sorted(models):
        support = green("✓ native") if client.model_supports_tools(m) else dim("  ReAct")
        print(f"  {cyan(m):<49} {support}")
    print()


def cmd_tools(args):
    tools = BUILTIN_REGISTRY.all()
    print(bold("\n🦞 LocalClaw R03 Tools") + dim(" · Written by VTSTech · https://www.vts-tech.org · https://github.com/VTSTech/LocalClaw"))
    print(bold(f"{'Tool':<20} Description"))
    print(dim("─" * 70))
    for t in tools:
        params = ", ".join(
            f"{p.name}: {p.type}" + ("?" if not p.required else "")
            for p in t.params
        )
        print(f"  {cyan(t.name):<26} {t.description}")
        if params:
            print(f"  {'':<26} {dim('Args: ' + params)}")
    print()
    print(dim(f"  Use with: --tools {','.join(t.name for t in tools[:3])},…"))
    print()


def cmd_skills(args):
    loader = SkillLoader()
    skills = loader.list_skills()
    
    print(bold("\n🦞 LocalClaw R03 Skills") + dim(" · Written by VTSTech · https://www.vts-tech.org · https://github.com/VTSTech/LocalClaw"))
    
    if not skills:
        print(yellow("  No skills found."))
        print(dim("  Skills are loaded from localclaw/skills/*/SKILL.md"))
        return
    
    print(bold(f"{'Skill':<20} Description"))
    print(dim("─" * 70))
    
    for name in skills:
        try:
            skill = loader.load(name)
            desc = skill.description[:60] + "..." if len(skill.description) > 60 else skill.description
            print(f"  {magenta(name):<26} {desc}")
            
            # Show resources
            resources = []
            if skill.scripts_dir:
                scripts = list(skill.scripts_dir.glob("*.py"))
                if scripts:
                    resources.append(f"{len(scripts)} scripts")
            if skill.references_dir:
                refs = list(skill.references_dir.glob("*.md"))
                if refs:
                    resources.append(f"{len(refs)} refs")
            if resources:
                print(f"  {'':<26} {dim('Has: ' + ', '.join(resources))}")
        except Exception as e:
            print(f"  {magenta(name):<26} {red(f'Error: {e}')}")
    
    print()
    print(dim(f"  Use with: --skills {','.join(skills[:2])}"))
    print(dim("  Skills provide knowledge/instructions to the agent."))
    print()


def _build_client(args):
    """Return OllamaClient or BitnetClient based on --backend flag."""
    backend = getattr(args, "backend", "ollama")
    if backend == "bitnet":
        from localclaw.bitnet_client import BitnetClient
        # No longer passing a directory here, just the URL from config or args
        return BitnetClient(base_url=BITNET_BASE_URL)
        bitnet_dir = getattr(args, "bitnet_dir", None) or os.environ.get("BITNET_DIR")
        if not bitnet_dir:
            for candidate in ["./BitNet", "./bitnet", os.path.expanduser("~/BitNet"), "/content/BitNet"]:
                if os.path.exists(candidate):
                    bitnet_dir = candidate
                    break
        if not bitnet_dir:
            print(red("✗  BitNet directory not found."))
            print(dim("   Pass --bitnet-dir /path/to/BitNet  or  set BITNET_DIR env var"))
            sys.exit(1)
        model = getattr(args, "model", "bitnet-b1.58-2b-4t")
        if _BITNET_AVAILABLE and model not in KNOWN_MODELS and not model.endswith(".gguf"):
            model = "bitnet-b1.58-2b-4t"
        threads = getattr(args, "bitnet_threads", None) or max(1, (os.cpu_count() or 4))
        gpu_layers = getattr(args, "bitnet_gpu_layers", 0)
        return BitnetClient(
            bitnet_dir=bitnet_dir,
            model=model,
            threads=threads,
            gpu_layers=gpu_layers,
            verbose=getattr(args, "verbose", False),
            auto_start=True,
        )
    return OllamaClient()


def cmd_run(args):
    client = _build_client(args)
    if not client.is_running():
        if getattr(args, "backend", "ollama") == "bitnet":
            print(red("✗  BitNet backend failed to start. Check --bitnet-dir."))
        else:
            print(red("✗  Ollama is not running. Start it with: ollama serve"))
        sys.exit(1)

    agent, skill_registry, acp_plugin = _build_agent(args, client)

    # Bootstrap ACP if enabled
    if acp_plugin:
        bootstrap_result = acp_plugin.bootstrap(claim_primary=False)  # LocalClaw is secondary

    print(bold("🦞 LocalClaw R03") + dim(" · Written by VTSTech · https://www.vts-tech.org · https://github.com/VTSTech/LocalClaw"))
    print(f"Prompt: {args.prompt}")

    # Log user message to ACP
    if acp_plugin:
        acp_plugin.log_user_message(args.prompt)

    # Use streaming if requested
    if getattr(args, "stream", False):
        if getattr(args, "verbose", False):
            print()
        print(bold("Agent: "), end="", flush=True)
        full_response = ""
        for token in agent.stream(args.prompt):
            print(token, end="", flush=True)
            full_response += token
        print()  # newline after streaming
        if getattr(args, "verbose", False):
            print(dim(f"\n  [streaming mode]"))
        # Log assistant response to ACP
        if acp_plugin:
            acp_plugin.log_assistant_message(full_response)
    else:
        run = agent.run(args.prompt)

        if getattr(args, "verbose", False):
            print()

        print(run.final_answer)

        # Log assistant response to ACP
        if acp_plugin:
            acp_plugin.log_assistant_message(run.final_answer)

        if getattr(args, "verbose", False):
            tool_steps = [s for s in run.steps if s.type == "tool_call"]
            print(dim(f"\n  {len(run.steps)} steps · {len(tool_steps)} tool calls · {run.total_ms:.0f}ms"))


def cmd_chat(args):
    client = _build_client(args)
    backend = getattr(args, "backend", "ollama")

    if not client.is_running():
        if backend == "bitnet":
            # Accessing the base_url we just added to the Client
            url = getattr(client, "base_url", "http://localhost:8765")
            print(red(f"✗  BitNet backend not found at {url}"))
            print(dim("   Ensure llama-server.exe is running in a separate terminal."))
        else:
            print(red("✗  Ollama is not running. Start it with: ollama serve"))
        sys.exit(1)

    # Warm up model if requested (useful for remote Ollama with cold starts)
    if getattr(args, "warmup", False):
        print(dim("  🔥 Warming up model..."), end=" ", flush=True)
        t0 = time.perf_counter()
        try:
            # Simple warmup request - just generate 1 token
            warmup_response = client.chat(
                model=args.model,
                messages=[{"role": "user", "content": "Hi"}],
                options={"num_predict": 1}
            )
            elapsed = (time.perf_counter() - t0) * 1000
            print(green(f"✓ {elapsed:.0f}ms"))
        except Exception as e:
            print(yellow(f"(warmup failed: {e})"))
        print()

    agent, skill_registry, acp_plugin = _build_agent(args, client)

    # Bootstrap ACP if enabled
    if acp_plugin:
        bootstrap_result = acp_plugin.bootstrap(claim_primary=False)  # LocalClaw is secondary
        if getattr(args, "verbose", False):
            if bootstrap_result.get("primary_claimed"):
                print(dim(f"  🔗 ACP: Claimed primary agent"))
            else:
                print(dim(f"  🔗 ACP: Connected as secondary agent"))
            if bootstrap_result.get("warnings"):
                for w in bootstrap_result["warnings"]:
                    print(yellow(f"  ⚠ {w}"))

    # Build status line
    parts = [f"[{args.model}"]
    if args.tools:
        parts.append(f"tools: {args.tools}")
    if args.skills:
        parts.append(f"skills: {args.skills}")
    parts.append("]")
    status = " ".join(parts)
    
    print(bold(f"\n🦞 LocalClaw R03 chat") + dim(f"  {status} · Written by VTSTech · https://www.vts-tech.org · https://github.com/VTSTech/LocalClaw"))
    print(dim("  Type 'exit', 'quit', or Ctrl+C to quit."))
    print(dim("  Type '/reset' to clear conversation history."))
    print(dim("  Type '/tools' to list available tools."))
    print(dim("  Type '/skills' to list active skills."))
    print(dim("  Type '/status' to show session status."))
    print(dim("  Type '/context' to show context information."))
    print(dim("  Type '/a2a' to process pending A2A messages."))
    print(dim("  ─────────────────────────────────────"))
    
    # Show loaded skills if verbose
    if getattr(args, "verbose", False) and len(skill_registry) > 0:
        print(cyan("\n  Loaded Skills:"))
        for name in skill_registry.list():
            skill = skill_registry.get(name)
            print(dim(f"    • {name}: {skill.description[:60]}..."))
        print()
    
    print()

    try:
        while True:
            try:
                user_input = input(bold("You: ")).strip()
            except EOFError:
                break

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "/exit", "/quit"):
                print(dim("Goodbye."))
                break

            if user_input == "/reset":
                agent.reset()
                print(dim("  ↺  Conversation history cleared."))
                continue

            if user_input == "/tools":
                if agent.tools.all():
                    names = [t.name for t in agent.tools.all()]
                    print(dim(f"  Active tools: {', '.join(names)}"))
                else:
                    print(dim("  No tools active. Use --tools to add some."))
                continue

            if user_input == "/skills":
                if len(skill_registry) > 0:
                    names = skill_registry.list()
                    for name in names:
                        skill = skill_registry.get(name)
                        desc = skill.description[:50] + "..." if len(skill.description) > 50 else skill.description
                        print(dim(f"  • {name}: {desc}"))
                else:
                    print(dim("  No skills active. Use --skills to add some."))
                continue

            if user_input == "/status":
                # Show current session status
                print()
                print(cyan("  Session Status"))
                print(dim("  ─────────────────────────────────────"))
                print(f"  Model:     {bold(args.model)}")
                # Dynamic Labeling based on backend
                backend_label = "BitNet" if getattr(args, "backend", "ollama") == "bitnet" else "Ollama"
                print(f"  {backend_label}:    {agent.client.base_url}")
                print(f"  Timeout:   {agent.client.timeout}s")
                print(f"  ReAct:     {'forced' if getattr(args, 'force_react', False) else 'auto-detect'}")
                
                # Show performance options
                model_opts = agent.model_options
                if model_opts:
                    perf_opts = []
                    if "num_ctx" in model_opts:
                        perf_opts.append(f"ctx={model_opts['num_ctx']}")
                    if "num_predict" in model_opts:
                        perf_opts.append(f"predict={model_opts['num_predict']}")
                    if "temperature" in model_opts:
                        perf_opts.append(f"temp={model_opts['temperature']}")
                    if perf_opts:
                        print(f"  Perf:      {', '.join(perf_opts)}")
                
                print()
                print(f"  Tools:     {len(agent.tools.all())} active")
                if agent.tools.all():
                    print(dim(f"             {', '.join(t.name for t in agent.tools.all())}"))
                print()
                print(f"  Skills:    {len(skill_registry)} active")
                if len(skill_registry) > 0:
                    print(dim(f"             {', '.join(skill_registry.list())}"))
                print()
                print(f"  Memory:    {len(agent.memory._history)} messages")
                print(f"  Max steps: {agent.max_steps}")
                print()
                if "num_ctx" not in model_opts:
                    print(dim("  💡 Tip: Use --fast for quicker responses, or --num-ctx 2048"))
                print()
                continue

            if user_input == "/context":
                # Show context/memory information
                print()
                print(cyan("  Context Information"))
                print(dim("  ─────────────────────────────────────"))
                
                # System prompt
                sys_prompt = agent.memory.system_prompt or "(none)"
                sys_lines = sys_prompt.split('\n')
                print(f"  System prompt: {len(sys_prompt)} chars, {len(sys_lines)} lines")
                if len(sys_lines) <= 5:
                    print(dim("  ┌─────────────────────────────────────"))
                    for line in sys_lines[:5]:
                        print(dim(f"  │ {line[:50]}{'...' if len(line) > 50 else ''}"))
                    print(dim("  └─────────────────────────────────────"))
                else:
                    print(dim(f"  Preview: {sys_lines[0][:60]}..."))
                
                print()
                
                # Memory history
                history = agent.memory._history
                counts = _count_messages(history)
                print(f"  Conversation history: {counts['total']} messages")
                print(dim(f"    • User messages: {counts['user']}"))
                print(dim(f"    • Assistant messages: {counts['assistant']}"))
                print(dim(f"    • Tool results: {counts['tool']}"))
                
                # Estimate token usage (rough: ~4 chars per token)
                total_chars = sum(len(m.content or '') for m in history)
                total_chars += len(sys_prompt)
                est_tokens = total_chars // 4
                print()
                print(f"  Estimated context: ~{est_tokens:,} tokens ({total_chars:,} chars)")
                
                # Skill context
                if len(skill_registry) > 0:
                    print()
                    print("  Skill context loaded:")
                    for name in skill_registry.list():
                        skill = skill_registry.get(name)
                        instr_len = len(skill.instructions)
                        print(dim(f"    • {name}: {instr_len:,} chars"))
                
                print()
                continue

            if user_input == "/a2a":
                # Process pending A2A messages
                if not acp_plugin:
                    print(yellow("  A2A not enabled. Start with --acp flag."))
                    continue
                
                print()
                print(cyan("  A2A Message Processing"))
                print(dim("  ─────────────────────────────────────"))
                
                # Get pending messages
                messages = acp_plugin.a2a_get_inbox()
                if not messages:
                    print(dim("  No pending A2A messages."))
                    print()
                    continue
                
                print(f"  Processing {len(messages)} message(s)...")
                print()
                
                # Process with tool executor
                results = acp_plugin.a2a_process_inbox(
                    tool_executor=_execute_a2a_tool,
                    auto_respond=True
                )
                
                for r in results:
                    status = green("✓") if r.get("status") == "processed" else yellow("○")
                    action = r.get("action", "unknown")
                    from_agent = r.get("from_agent", "unknown")
                    msg_type = r.get("type", "unknown")
                    
                    print(f"  {status} {bold(action)} from {cyan(from_agent)} ({msg_type})")
                    
                    if r.get("result"):
                        result_str = str(r.get("result"))[:200]
                        print(dim(f"    → {result_str}"))
                    elif r.get("error"):
                        print(red(f"    ✗ {r.get('error')}"))
                
                print()
                continue

            if user_input == "/help":
                print()
                print(cyan("  Available Commands"))
                print(dim("  ─────────────────────────────────────"))
                print("  " + bold("Session Control"))
                print(dim("    exit, quit       End the session"))
                print(dim("    /reset           Clear conversation history"))
                print(dim("    /undo            Remove last exchange"))
                print(dim("    /retry           Retry last request"))
                print()
                print("  " + bold("Information"))
                print(dim("    /status          Show session status"))
                print(dim("    /context         Show context/token info"))
                print(dim("    /tools           List active tools"))
                print(dim("    /skills          List active skills"))
                print(dim("    /stats           Show session statistics"))
                print(dim("    /messages        Show raw message history"))
                print()
                print("  " + bold("A2A Messaging"))
                print(dim("    /a2a             Process pending A2A messages"))
                print()
                print("  " + bold("Export/Save"))
                print(dim("    /export          Export to markdown file"))
                print(dim("    /save <name>     Save conversation"))
                print(dim("    /load <name>     Load conversation"))
                print()
                print("  " + bold("Configuration"))
                print(dim("    /system          View system prompt"))
                print(dim("    /temp <value>    Change temperature"))
                print()
                continue

            if user_input == "/undo":
                # Remove last exchange (user + assistant messages)
                history = agent.memory._history
                if len(history) >= 2:
                    # Remove last assistant and user message
                    removed = []
                    while len(history) > 0 and len(removed) < 2:
                        removed.append(history.pop())
                    print(dim(f"  ↺  Removed {len(removed)} messages from history"))
                elif len(history) == 1:
                    history.pop()
                    print(dim("  ↺  Removed 1 message from history"))
                else:
                    print(dim("  No messages to undo"))
                continue

            if user_input == "/retry":
                # Retry the last user message
                history = agent.memory._history
                last_user_msg = None
                for msg in reversed(history):
                    if msg.role == 'user':
                        last_user_msg = msg.content or ''
                        break
                
                if last_user_msg:
                    # Remove last exchange
                    removed = 0
                    while len(history) > 0:
                        last = history[-1]
                        if last.role == 'user' and removed > 0:
                            break
                        history.pop()
                        removed += 1
                    
                    print(dim(f"  ↻  Retrying: {last_user_msg[:50]}..."))
                    run = agent.run(last_user_msg)
                    print(f"{bold('Agent')}: {run.final_answer}")
                    if getattr(args, "verbose", False) and run.steps:
                        tool_steps = [s for s in run.steps if s.type == "tool_call"]
                        print(dim(f"         [{len(tool_steps)} tool calls · {run.total_ms:.0f}ms]"))
                    print()
                else:
                    print(dim("  No user message to retry"))
                continue

            if user_input == "/stats":
                print()
                print(cyan("  Session Statistics"))
                print(dim("  ─────────────────────────────────────"))
                
                # Message counts
                history = agent.memory._history
                counts = _count_messages(history)
                
                print(f"  Messages: {counts['total']} total")
                print(dim(f"    • User: {counts['user']}"))
                print(dim(f"    • Assistant: {counts['assistant']}"))
                print(dim(f"    • Tool results: {counts['tool']}"))
                print()
                
                # Token estimation
                sys_prompt = agent.memory.system_prompt or ""
                total_chars = sum(len(m.content or '') for m in history)
                total_chars += len(sys_prompt)
                est_tokens = total_chars // 4
                print(f"  Estimated tokens: ~{est_tokens:,}")
                print()
                
                # Model info
                print(f"  Model: {args.model}")
                print(f"  Temperature: {getattr(args, 'temperature', 0.7)}")
                print()
                continue

            if user_input == "/messages":
                print()
                print(cyan("  Message History"))
                print(dim("  ─────────────────────────────────────"))
                
                history = agent.memory._history
                if not history:
                    print(dim("  No messages in history"))
                    print()
                    continue
                
                for i, msg in enumerate(history, 1):
                    role = msg.role
                    content = msg.content or ''
                    
                    # Truncate long content
                    if len(content) > 100:
                        content = content[:100] + "..."
                    
                    role_icon = {"user": "👤", "assistant": "🤖", "tool": "🔧"}.get(role, "❓")
                    print(f"  {role_icon} {bold(role)}:")
                    print(dim(f"    {content[:80]}"))
                    print()
                continue

            if user_input == "/export":
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"conversation_{timestamp}.md"
                filepath = Path(filename)
                
                # Build markdown content
                lines = [
                    f"# LocalClaw Conversation",
                    f"",
                    f"**Model**: {args.model}",
                    f"**Date**: {datetime.datetime.now().isoformat()}",
                    f"",
                    "---",
                    "",
                ]
                
                history = agent.memory._history
                for msg in history:
                    role = msg.role
                    content = msg.content or ''
                    
                    if role == 'user':
                        lines.append(f"## User")
                        lines.append(f"")
                        lines.append(content)
                        lines.append(f"")
                    elif role == 'assistant':
                        lines.append(f"## Assistant")
                        lines.append(f"")
                        lines.append(content)
                        lines.append(f"")
                    elif role == 'tool':
                        lines.append(f"### Tool Result")
                        lines.append(f"")
                        lines.append(f"```")
                        lines.append(content[:500])
                        lines.append(f"```")
                        lines.append(f"")
                
                filepath.write_text("\n".join(lines), encoding='utf-8')
                print(green(f"  ✓ Exported to {filename}"))
                continue

            if user_input.startswith("/temp "):
                try:
                    new_temp = float(user_input.split()[1])
                    args.temperature = new_temp
                    agent.model_options = {"temperature": new_temp}
                    print(dim(f"  Temperature set to {new_temp}"))
                except (ValueError, IndexError):
                    print(dim("  Usage: /temp <value> (e.g., /temp 0.5)"))
                continue

            if user_input == "/system":
                print()
                print(cyan("  System Prompt"))
                print(dim("  ─────────────────────────────────────"))
                sys_prompt = agent.memory.system_prompt or "(none)"
                print(f"  Length: {len(sys_prompt)} chars")
                print()
                # Show first 500 chars
                preview = sys_prompt[:500]
                print(dim(preview))
                if len(sys_prompt) > 500:
                    print(dim(f"\n  ... ({len(sys_prompt) - 500} more chars)"))
                print()
                continue

            if user_input.startswith("/save "):
                name = user_input.split()[1]
                filename = f"{name}.json"
                filepath = Path(filename)
                data = agent.memory.snapshot()
                data["model"] = args.model
                data["temperature"] = getattr(args, 'temperature', 0.7)
                filepath.write_text(json.dumps(data, indent=2), encoding='utf-8')
                print(green(f"  ✓ Saved to {filename}"))
                continue

            if user_input.startswith("/load "):
                name = user_input.split()[1]
                filename = f"{name}.json"
                filepath = Path(filename)
                
                if not filepath.exists():
                    print(red(f"  ✗ File not found: {filename}"))
                    continue
                
                data = json.loads(filepath.read_text(encoding='utf-8'))
                # Properly deserialize Message objects from dicts
                agent.memory._history = [Message.from_dict(m) for m in data.get("history", [])]
                agent.memory.system_prompt = data.get("system_prompt", agent.memory.system_prompt)
                agent.memory._archived_summary = data.get("archived_summary", "")
                print(green(f"  ✓ Loaded from {filename} ({len(agent.memory._history)} messages)"))
                continue

            # Use streaming if requested
            if getattr(args, "stream", False):
                # Log user message to ACP
                if acp_plugin:
                    acp_plugin.log_user_message(user_input)
                print(bold("Agent: "), end="", flush=True)
                full_response = ""
                for token in agent.stream(user_input):
                    print(token, end="", flush=True)
                    full_response += token
                print()  # newline after streaming
                if getattr(args, "verbose", False):
                    print(dim("         [streaming mode]"))
                print()
                # Log assistant response to ACP
                if acp_plugin:
                    acp_plugin.log_assistant_message(full_response)
            else:
                # Log user message to ACP
                if acp_plugin:
                    acp_plugin.log_user_message(user_input)

                run = None  # Initialize variable to prevent UnboundLocalError
                try:
                    run = agent.run(user_input)
                    
                    # Check if run was successful before accessing attributes
                    if run and hasattr(run, 'final_answer'):
                        print(f"{bold('Agent')}: {run.final_answer}")
                        
                        # Log assistant response to ACP
                        if acp_plugin:
                            acp_plugin.log_assistant_message(run.final_answer)
                        
                        if getattr(args, "verbose", False) and run.steps:
                            tool_steps = [s for s in run.steps if s.type == "tool_call"]
                            print(dim(f"         [{len(tool_steps)} tool calls · {run.total_ms:.0f}ms]"))
                except json.JSONDecodeError as e:
                    print(red(f"\n  ✗ BitNet output malformed JSON: {e}"))
                    print(dim("  Tip: Try lowering --temperature to 0.1 for more stable JSON."))
                except Exception as e:
                    print(red(f"\n  ✗ LocalClaw Error: {e}"))
                    print(dim("  Tip: The connection was likely dropped during heavy tool-use prefilling."))
                print()

    except KeyboardInterrupt:
        print(f"\n{dim('Interrupted.')}")


# ------------------------------------------------------------------ #
#  Argument parser                                                    #
# ------------------------------------------------------------------ #

def _default_model(client: OllamaClient) -> str:
    """Pick a sensible default from whatever's available."""
    models = client.list_models()
    preferences = ["llama3.1:8b", "llama3.2:3b", "qwen2.5:7b", "mistral", "qwen3", "qwen35", "qwen2.5-coder", "llama3.2:1b"]
    for pref in preferences:
        for m in models:
            if pref in m.lower():
                return m
    return models[0] if models else "llama3.2:1b"


def build_parser() -> argparse.ArgumentParser:
    client = OllamaClient()
    default_model = _default_model(client) if client.is_running() else "llama3.2:1b"

    parser = argparse.ArgumentParser(
        prog="localclaw",
        description="🦞 LocalClaw R03 — local agentic AI powered by Ollama · Written by VTSTech · https://www.vts-tech.org · https://github.com/VTSTech/LocalClaw",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        options (for 'run' and 'chat' commands):
          -m, --model MODEL      Ollama model to use (default: auto-detect)
          -t, --tools TOOLS      Comma-separated tools: calculator,shell,python_repl,read_file,write_file,http_get
          -k, --skills SKILLS    Comma-separated skills: skill-creator,datetime,web_search
          -s, --system PROMPT    Override system prompt
          -v, --verbose          Show tool calls, timing, and detailed output
          --debug                Show debug info: parsed tool calls, fuzzy matching
          --fast                 Fast mode: num_ctx=2048, num_predict=256
          --stream               Stream output token-by-token (better UX for slow connections)
          --warmup               Warm up model before chat (useful for remote Ollama)
          --num-ctx N            Context window size (smaller = faster)
          --num-predict N        Max tokens to generate (smaller = faster)
          --temperature TEMP     Temperature (default: 0.7)
          --force-react          Force ReAct text-based tool calling
          --acp                  Enable ACP (Agent Control Panel) integration for activity tracking

        examples:
          localclaw run "What is the capital of France?"
          localclaw run "What is sqrt(144)?" --tools calculator
          localclaw run "Tell me a story" --stream --verbose
          localclaw chat --model llama3.1:8b
          localclaw chat --tools calculator,shell,python_repl
          localclaw chat --skills skill-creator --tools write_file,shell
          localclaw chat --fast --stream --verbose
          localclaw chat --acp --tools shell,read_file,write_file
          localclaw models
          localclaw tools
          localclaw skills

        """),
    )

    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = True

    # ── Shared flags ──────────────────────────────────────────────────
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--model", "-m",
        default=default_model,
        metavar="MODEL",
        help=f"Ollama model (default: {default_model})",
    )
    shared.add_argument(
        "--tools", "-t",
        default=None,
        metavar="TOOLS",
        help="Comma-separated tools, e.g. calculator,shell",
    )
    shared.add_argument(
        "--skills", "-k",
        default=None,
        metavar="SKILLS",
        help="Comma-separated skills, e.g. skill-creator",
    )
    shared.add_argument(
        "--system", "-s",
        default=None,
        metavar="PROMPT",
        help="Override system prompt",
    )
    shared.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show tool calls and timing",
    )
    shared.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        metavar="TEMP",
        help="Temperature (default: 0.7)",
    )
    shared.add_argument(
        "--force-react",
        action="store_true",
        help="Force ReAct text-based tool calling (for models without native tool support)",
    )
    # Performance optimization options
    shared.add_argument(
        "--num-ctx",
        type=int,
        default=None,
        metavar="N",
        help="Context window size (default: model default, try 2048 for speed)",
    )
    shared.add_argument(
        "--num-predict",
        type=int,
        default=None,
        metavar="N",
        help="Max tokens to generate (default: -1 for model default, try 128-256 for speed)",
    )
    shared.add_argument(
        "--fast",
        action="store_true",
        help="Fast mode: reduce context (2048) and output (256) for quicker responses",
    )
    shared.add_argument(
        "--warmup",
        action="store_true",
        help="Warm up model with a dummy request before chat (useful for remote Ollama)",
    )
    shared.add_argument(
        "--debug",
        action="store_true",
        help="Show debug info: parsed tool calls, fuzzy matching, etc.",
    )
    shared.add_argument(
        "--stream",
        action="store_true",
        help="Stream output token-by-token (better UX for slow connections)",
    )
    shared.add_argument(
        "--acp",
        action="store_true",
        help="Enable ACP (Agent Control Panel) integration for activity tracking",
    )
    shared.add_argument(
        "--backend",
        default="ollama",
        choices=["ollama", "bitnet"],
        help="Inference backend: ollama (default) or bitnet (bitnet.cpp llama-server)",
    )
    shared.add_argument(
        "--bitnet-dir",
        default=None,
        metavar="DIR",
        dest="bitnet_dir",
        help="Path to BitNet repo (required when --backend bitnet)",
    )
    shared.add_argument(
        "--bitnet-threads",
        type=int,
        default=None,
        metavar="N",
        dest="bitnet_threads",
        help="CPU threads for llama-server (default: all cores)",
    )
    shared.add_argument(
        "--bitnet-gpu-layers",
        type=int,
        default=0,
        metavar="N",
        dest="bitnet_gpu_layers",
        help="GPU layers to offload in llama-server (default: 0)",
    )

    # ── run ─────────────────────────────────────────────────────────
    p_run = sub.add_parser("run", parents=[shared], help="Run a single prompt")
    p_run.add_argument("prompt", help="The prompt to send")
    p_run.set_defaults(func=cmd_run)

    # ── chat ────────────────────────────────────────────────────────
    p_chat = sub.add_parser("chat", parents=[shared], help="Interactive chat")
    p_chat.set_defaults(func=cmd_chat)

    # ── models ──────────────────────────────────────────────────────
    p_models = sub.add_parser("models", parents=[shared], help="List available models")
    p_models.set_defaults(func=cmd_models)

    # ── tools ───────────────────────────────────────────────────────
    p_tools = sub.add_parser("tools", parents=[shared], help="List available tools")
    p_tools.set_defaults(func=cmd_tools)

    # ── skills ──────────────────────────────────────────────────────
    p_skills = sub.add_parser("skills", parents=[shared], help="List available skills")
    p_skills.set_defaults(func=cmd_skills)

    return parser


# ------------------------------------------------------------------ #
#  Entry point                                                       #
# ------------------------------------------------------------------ #

def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()