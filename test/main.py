import argparse
from agent import run_agent

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refiner", default="qwen2.5:1.5b-instruct-q4_k_m")
    parser.add_argument("--coordinator", default="qwen2.5:1.5b-instruct-q4_k_m")
    parser.add_argument("--worker", default="qwen2.5:0.5b-instruct-q4_k_m")
    
    args = parser.parse_args()
    run_agent(args.refiner, args.coordinator, args.worker)