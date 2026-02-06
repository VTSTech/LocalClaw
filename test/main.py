import argparse
from agent import run_agent

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        default="qwen2.5:0.5b-instruct-q4_k_m",
        help="Ollama model name"
    )
    run_agent(parser.parse_args().model)
