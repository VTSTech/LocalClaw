#!/usr/bin/env python3
"""
🦞 LocalClaw R03 — Command Line Interface

Entry point for: python -m localclaw [command] [options]

Commands:
  run     Run the agent on a single prompt and exit
  chat    Interactive multi-turn conversation with memory
  models  List models available in Ollama
  tools   List available built-in tools
  skills  List available Agent Skills

Examples:
  python -m localclaw run "What is the capital of France?"
  python -m localclaw chat --model llama3.1:8b --tools calculator,shell
  python -m localclaw models
  python -m localclaw tools
  python -m localclaw skills

Written by VTSTech · https://www.vts-tech.org · https://github.com/VTSTech/LocalClaw
"""

from localclaw.cli import main

if __name__ == "__main__":
    main()
