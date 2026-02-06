import argparse
from agent import run_agent

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3:0.6b")
    args = parser.parse_args()

    run_agent(args.model)
