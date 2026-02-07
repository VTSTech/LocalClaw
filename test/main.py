import argparse
from agent import run_agent

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--coordinator",
        default="qwen2.5:1.5b-instruct-q4_k_m", # Slightly smarter planner
        help="Ollama model for planning"
    )
    parser.add_argument(
        "--worker",
        default="qwen2.5:0.5b-instruct-q4_k_m", # Fast executor
        help="Ollama model for tool usage"
    )
    
    args = parser.parse_args()
    run_agent(args.coordinator, args.worker)