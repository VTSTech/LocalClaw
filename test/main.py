# -*- coding: utf-8 -*-
"""
VTSBot - Unified Entry Point

VTSBot R7: Function Calling + Agent Skills
- Native function calling (no text parsing)
- SKILL.md skills (agentskills.io spec)
- JSON mode for structured output
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="VTSBot - Multi-Agent Orchestration System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                           Run R7 (function calling, recommended)
  python main.py --model qwen2.5:7b        Use larger model
  python main.py --skills ./my_skills      Load custom skill directories
  python main.py --test                    Run test prompts
  python main.py --test-skills             Test all skills directly
  python main.py --validate ./skill-dir    Validate a skill directory

Architecture (R7 - Function Calling):
  User Input ? LLM with Tools ? Function Call ? Execute ? Result
  
  No text parsing! Uses native function calling for:
  - Skill selection
  - Command execution
  - File operations
  - Chat responses
        """,
    )
    
    # Model selection
    parser.add_argument(
        "--model",
        default="qwen2.5:3b",
        help="LLM model (default: qwen2.5:3b - larger models work better)"
    )
    
    # Skill configuration
    parser.add_argument(
        "--skills",
        nargs="*",
        default=[],
        help="Directories to load Agent Skills from"
    )
    
    # Test modes
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run test prompts"
    )
    parser.add_argument(
        "--test-skills",
        action="store_true",
        help="Test all skills directly without prompting"
    )
    
    # Validation
    parser.add_argument(
        "--validate",
        metavar="PATH",
        help="Validate a skill directory"
    )
    
    args = parser.parse_args()
    
    # Validation mode
    if args.validate:
        from agent_skills.core.skill import validate_skill
        errors = validate_skill(Path(args.validate))
        if errors:
            print(f"\n? Validation FAILED for: {args.validate}\n")
            for e in errors:
                print(f"  - {e}")
            sys.exit(1)
        else:
            print(f"\n? Validation PASSED for: {args.validate}")
            sys.exit(0)
    
    # Prepare test queue
    test_queue = None
    if args.test:
        from prompts import TEST_PROMPTS
        test_queue = [p.strip() for p in TEST_PROMPTS.strip().split('\n') if p.strip()]
    
    # Run R7 function-calling agent
    print("[VTSBot R7] Running function-calling agent with skills...")
    from agent_fc import FunctionCallingAgent
    agent = FunctionCallingAgent(
        model=args.model,
        skills_dirs=args.skills if args.skills else None,
        verbose=True
    )
    
    if args.test_skills:
        # Test skills directly
        results = agent.test_skills()
        sys.exit(0)
    
    # Run normal agent loop
    from agent_fc import run_agent as run_fc_agent, banner
    banner(args.model, len(agent.registry))
    
    if test_queue:
        print(f"  [TEST MODE] {len(test_queue)} tests queued\n")
    
    run_fc_agent(
        model=args.model,
        skills_dirs=args.skills if args.skills else None,
        test_queue=test_queue,
    )


if __name__ == "__main__":
    main()