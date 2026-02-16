# -*- coding: utf-8 -*-
"""
VTSBot - Unified Entry Point

VTSBot R6: Multi-Agent System with Agent Skills Integration

Usage:
    python main.py                           # Run integrated agent (default)
    python main.py --legacy                  # Run original R4 agent
    python main.py --skills ./my_skills      # Load custom skills
    python main.py --test                    # Run test prompts
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="VTSBot - Multi-Agent Orchestration System with Skills",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                           Run integrated agent (R6)
  python main.py --legacy                  Run original multi-agent (R4)
  python main.py --skills ./my_skills      Load custom skill directories
  python main.py --test                    Run test prompts
  python main.py --validate ./skill-dir    Validate a skill

Architecture (R6):
  User Input ? Dispatcher ? [SKILL:xxx] ? DevOps ? Auditor ? Worker
                       ? [CHAT/LOCAL/DIRECT/SCRIPT]
        """,
    )
    
    # Model selection
    parser.add_argument(
        "--refiner",
        default="qwen2.5:1.5b-instruct-q4_k_m",
        help="Refiner/Dispatcher model"
    )
    parser.add_argument(
        "--coordinator",
        default="qwen2.5:1.5b-instruct-q4_k_m",
        help="Coordinator model (legacy)"
    )
    parser.add_argument(
        "--worker",
        default="qwen2.5-coder:0.5b-instruct-q4_k_m",
        help="Worker model"
    )
    
    # Mode selection
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Use legacy R4 multi-agent system"
    )
    
    # Skill configuration
    parser.add_argument(
        "--skills",
        nargs="*",
        default=[],
        help="Directories to load Agent Skills from"
    )
    
    # Test mode
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run test prompts"
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
    
    # Run appropriate agent
    if args.legacy:
        # Legacy R4 agent
        print("[VTSBot R4] Running legacy multi-agent system...")
        from agent import run_agent
        run_agent(args.refiner, args.coordinator, args.worker, test_queue=test_queue)
    else:
        # Integrated R6 agent with skills
        print("[VTSBot R6] Running integrated multi-agent with skills...")
        from agent_integrated import run_integrated_agent
        run_integrated_agent(
            refiner_model=args.refiner,
            worker_model=args.worker,
            skills_dirs=args.skills if args.skills else None,
            test_queue=test_queue,
        )


if __name__ == "__main__":
    main()