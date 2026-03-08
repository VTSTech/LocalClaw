from __future__ import annotations
"""
LocalClaw — CLI
Entry point: localclaw <command> [options]

Commands:
  run     Run the agent on a single prompt and exit
  chat    Interactive multi-turn conversation with memory
  models  List models available in Ollama
  tools   List available built-in tools

Examples:
  localclaw run "What is the capital of France?"
  localclaw run "What is sqrt(144)?" --tools calculator
  localclaw run "Write a haiku" --model qwen2.5:7b --stream
  localclaw chat --model llama3.1:8b --tools calculator,shell
  localclaw models
  localclaw tools

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

import argparse
import os
import sys
import textwrap

# Allow running as `python localclaw/cli.py` or as installed entry point
_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
if _root not in sys.path:
    sys.path.insert(0, _root)

from localclaw import Agent, OllamaClient, StepResult
from localclaw.tools.builtins import BUILTIN_REGISTRY


# ------------------------------------------------------------------ #
#  Colour helpers (graceful fallback if terminal doesn't support it)  #
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


# ------------------------------------------------------------------ #
#  Step callback for --verbose                                         #
# ------------------------------------------------------------------ #

def _make_step_printer(verbose: bool):
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
    return on_step


# ------------------------------------------------------------------ #
#  Build agent from parsed args                                        #
# ------------------------------------------------------------------ #

def _build_agent(args, client: OllamaClient) -> Agent:
    # Resolve tools
    registry = None
    if args.tools:
        names = [t.strip() for t in args.tools.split(",")]
        unknown = [n for n in names if BUILTIN_REGISTRY.get(n) is None]
        if unknown:
            print(red(f"Unknown tools: {', '.join(unknown)}"))
            print(f"Run {bold('localclaw tools')} to see available tools.")
            sys.exit(1)
        registry = BUILTIN_REGISTRY.subset(names)

    system_prompt = args.system if hasattr(args, "system") and args.system else (
        "You are a helpful assistant. Answer concisely and directly."
    )

    return Agent(
        model=args.model,
        tools=registry,
        system_prompt=system_prompt,
        client=client,
        force_react=getattr(args, "react", False),
        on_step=_make_step_printer(getattr(args, "verbose", False)),
        model_options={"temperature": args.temperature} if hasattr(args, "temperature") else {},
    )


# ------------------------------------------------------------------ #
#  Commands                                                            #
# ------------------------------------------------------------------ #

def cmd_models(args):
    client = OllamaClient()
    if not client.is_running():
        print(red("✗  Ollama is not running. Start it with: ollama serve"))
        sys.exit(1)

    models = client.list_models()
    if not models:
        print(yellow("No models found. Pull one with: ollama pull llama3.2:3b"))
        return

    print(bold(f"\n{'Model':<40} {'Tool support':>12}"))
    print(dim("─" * 54))
    for m in sorted(models):
        support = green("✓ native") if client.model_supports_tools(m) else dim("  ReAct")
        print(f"  {cyan(m):<49} {support}")
    print()


def cmd_tools(args):
    tools = BUILTIN_REGISTRY.all()
    print(bold(f"\n{'Tool':<20} Description"))
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


def cmd_run(args):
    client = OllamaClient()
    if not client.is_running():
        print(red("✗  Ollama is not running. Start it with: ollama serve"))
        sys.exit(1)

    agent = _build_agent(args, client)
    print(f"Prompt: {args.prompt}")
    if args.stream and not agent.tools.all():
        # Streaming mode — only available without tools
        print(f"{bold('Agent')}: ", end="", flush=True)
        for token in agent.stream(args.prompt):
            print(token, end="", flush=True)
        print()
    else:
        if args.stream and agent.tools.all():
            print(dim("(streaming disabled when tools are active)"))

        run = agent.run(args.prompt)

        if getattr(args, "verbose", False):
            print()

        print(run.final_answer)

        if getattr(args, "verbose", False):
            tool_steps = [s for s in run.steps if s.type == "tool_call"]
            print(dim(f"\n  {len(run.steps)} steps · {len(tool_steps)} tool calls · {run.total_ms:.0f}ms"))


def cmd_chat(args):
    client = OllamaClient()
    if not client.is_running():
        print(red("✗  Ollama is not running. Start it with: ollama serve"))
        sys.exit(1)

    agent = _build_agent(args, client)
    tools_label = f" + tools: {args.tools}" if args.tools else ""
    print(bold(f"\n🦞 LocalClaw chat") + dim(f"  [{args.model}{tools_label}]"))
    print(dim("  Type 'exit', 'quit', or Ctrl+C to quit."))
    print(dim("  Type '/reset' to clear conversation history."))
    print(dim("  Type '/tools' to list available tools."))
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
                    print(dim("  No tools active. Restart with --tools to add some."))
                continue

            if args.stream and not agent.tools.all():
                print(f"{bold('Agent')}: ", end="", flush=True)
                for token in agent.stream(user_input):
                    print(token, end="", flush=True)
                print()
            else:
                run = agent.run(user_input)
                print(f"{bold('Agent')}: {run.final_answer}")
                if getattr(args, "verbose", False) and run.steps:
                    tool_steps = [s for s in run.steps if s.type == "tool_call"]
                    print(dim(f"         [{len(tool_steps)} tool calls · {run.total_ms:.0f}ms]"))
            print()

    except KeyboardInterrupt:
        print(f"\n{dim('Interrupted.')}")


# ------------------------------------------------------------------ #
#  Argument parser                                                     #
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
        description="🦞 LocalClaw — local agentic AI powered by Ollama",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        examples:
          localclaw run "What is the capital of France?"
          localclaw run "What is sqrt(144)?" --tools calculator
          localclaw run "List files in /tmp" --tools shell --verbose
          localclaw chat --model llama3.1:8b
          localclaw chat --tools calculator,shell,python_repl
          localclaw models
          localclaw tools
        """),
    )

    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = True

    # ── Shared flags for run + chat ──────────────────────────────────
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--model", "-m",
        default=default_model,
        metavar="MODEL",
        help=f"Ollama model to use (default: {default_model})",
    )
    shared.add_argument(
        "--tools", "-t",
        default=None,
        metavar="TOOLS",
        help="Comma-separated built-in tools to enable, e.g. calculator,shell",
    )
    shared.add_argument(
        "--system", "-s",
        default=None,
        metavar="PROMPT",
        help="Override the system prompt",
    )
    shared.add_argument(
        "--stream",
        action="store_true",
        help="Stream tokens as they are generated (no-tool mode only)",
    )
    shared.add_argument(
        "--react",
        action="store_true",
        help="Force text-based ReAct mode even for native tool-call models",
    )
    shared.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show tool calls, results, and timing",
    )
    shared.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        metavar="TEMP",
        help="Sampling temperature (default: 0.7)",
    )

    # ── run ─────────────────────────────────────────────────────────
    p_run = sub.add_parser(
        "run",
        parents=[shared],
        help="Run a single prompt and exit",
        description="Run the agent on a single prompt and print the answer.",
    )
    p_run.add_argument("prompt", help="The prompt to send to the agent")
    p_run.set_defaults(func=cmd_run)

    # ── chat ─────────────────────────────────────────────────────────
    p_chat = sub.add_parser(
        "chat",
        parents=[shared],
        help="Interactive multi-turn conversation",
        description="Start an interactive chat session. Memory is retained across turns.",
    )
    p_chat.set_defaults(func=cmd_chat)

    # ── models ───────────────────────────────────────────────────────
    p_models = sub.add_parser(
        "models",
        help="List available Ollama models",
    )
    p_models.set_defaults(func=cmd_models)

    # ── tools ────────────────────────────────────────────────────────
    p_tools = sub.add_parser(
        "tools",
        help="List available built-in tools",
    )
    p_tools.set_defaults(func=cmd_tools)

    return parser


# ------------------------------------------------------------------ #
#  Entry point                                                         #
# ------------------------------------------------------------------ #

def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()