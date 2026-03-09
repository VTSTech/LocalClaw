#!/usr/bin/env python3
"""
🦞 LocalClaw R01 — CLI
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

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap

# Allow running as `python cli.py` or as installed entry point
_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
if _root not in sys.path:
    sys.path.insert(0, _root)

from localclaw import Agent, OllamaClient, StepResult
from localclaw.tools.builtins import BUILTIN_REGISTRY
from localclaw.skills import SkillLoader, SkillRegistry


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
def mag(t):    return _c("35", t)


# ------------------------------------------------------------------ #
#  Step callback for --verbose                                        #
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

    # Build system prompt
    system_prompt = getattr(args, "system", None) or "You are a helpful assistant. Answer concisely and directly."
    
    # Add skill instructions if skills are loaded
    if len(skill_registry) > 0:
        system_prompt += "\n\n" + skill_registry.to_system_prompt_addition()

    # Get temperature
    temperature = getattr(args, "temperature", 0.7)
    
    agent = Agent(
        model=args.model,
        tools=tools_registry,
        system_prompt=system_prompt,
        client=client,
        on_step=_make_step_printer(getattr(args, "verbose", False)),
        model_options={"temperature": temperature} if temperature else {},
        force_react=getattr(args, "force_react", False),
    )
    
    return agent, skill_registry


# ------------------------------------------------------------------ #
#  Commands                                                           #
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

    print(bold("\n🦞 LocalClaw R01 Models") + dim(" · VTSTech"))
    print(bold(f"{'Model':<40} {'Tool support':>12}"))
    print(dim("─" * 54))
    for m in sorted(models):
        support = green("✓ native") if client.model_supports_tools(m) else dim("  ReAct")
        print(f"  {cyan(m):<49} {support}")
    print()


def cmd_tools(args):
    tools = BUILTIN_REGISTRY.all()
    print(bold("\n🦞 LocalClaw R01 Tools") + dim(" · VTSTech"))
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
    
    print(bold("\n🦞 LocalClaw R01 Skills") + dim(" · VTSTech"))
    
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
            print(f"  {mag(name):<26} {desc}")
            
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
            print(f"  {mag(name):<26} {red(f'Error: {e}')}")
    
    print()
    print(dim(f"  Use with: --skills {','.join(skills[:2])}"))
    print(dim("  Skills provide knowledge/instructions to the agent."))
    print()


def cmd_run(args):
    client = OllamaClient()
    if not client.is_running():
        print(red("✗  Ollama is not running. Start it with: ollama serve"))
        sys.exit(1)

    agent, skill_registry = _build_agent(args, client)
    
    print(bold("🦞 LocalClaw R01") + dim(" · VTSTech"))
    print(f"Prompt: {args.prompt}")
    
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

    agent, skill_registry = _build_agent(args, client)
    
    # Build status line
    parts = [f"[{args.model}"]
    if args.tools:
        parts.append(f"tools: {args.tools}")
    if args.skills:
        parts.append(f"skills: {args.skills}")
    parts.append("]")
    status = " ".join(parts)
    
    print(bold(f"\n🦞 LocalClaw R01 chat") + dim(f"  {status} · VTSTech"))
    print(dim("  Type 'exit', 'quit', or Ctrl+C to quit."))
    print(dim("  Type '/reset' to clear conversation history."))
    print(dim("  Type '/tools' to list available tools."))
    print(dim("  Type '/skills' to list active skills."))
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

            run = agent.run(user_input)
            print(f"{bold('Agent')}: {run.final_answer}")
            if getattr(args, "verbose", False) and run.steps:
                tool_steps = [s for s in run.steps if s.type == "tool_call"]
                print(dim(f"         [{len(tool_steps)} tool calls · {run.total_ms:.0f}ms]"))
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
        description="🦞 LocalClaw R01 — local agentic AI powered by Ollama · VTSTech",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        examples:
          localclaw run "What is the capital of France?"
          localclaw run "What is sqrt(144)?" --tools calculator
          localclaw chat --model llama3.1:8b
          localclaw chat --tools calculator,shell,python_repl
          localclaw chat --skills skill-creator --tools write_file,shell
          localclaw models
          localclaw tools
          localclaw skills

        Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
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

    # ── run ─────────────────────────────────────────────────────────
    p_run = sub.add_parser("run", parents=[shared], help="Run a single prompt")
    p_run.add_argument("prompt", help="The prompt to send")
    p_run.set_defaults(func=cmd_run)

    # ── chat ────────────────────────────────────────────────────────
    p_chat = sub.add_parser("chat", parents=[shared], help="Interactive chat")
    p_chat.set_defaults(func=cmd_chat)

    # ── models ──────────────────────────────────────────────────────
    p_models = sub.add_parser("models", help="List available models")
    p_models.set_defaults(func=cmd_models)

    # ── tools ───────────────────────────────────────────────────────
    p_tools = sub.add_parser("tools", help="List available tools")
    p_tools.set_defaults(func=cmd_tools)

    # ── skills ──────────────────────────────────────────────────────
    p_skills = sub.add_parser("skills", help="List available skills")
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
