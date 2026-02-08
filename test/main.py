import argparse
from agent import run_agent

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refiner", default="qwen2.5:1.5b-instruct-q4_k_m")
    parser.add_argument("--coordinator", default="qwen2.5:1.5b-instruct-q4_k_m")
    parser.add_argument("--worker", default="qwen2.5:0.5b-instruct-q4_k_m")
    parser.add_argument("--test", action="store_true", help="Run predefined TEST_PROMPTS")
    
    args = parser.parse_args()
    if args.test:
        from prompts import TEST_PROMPTS
		        test_list = [p.strip() for p in TEST_PROMPTS.strip().split('\n') if p.strip()]
		        # Pass the test list to run_agent
		        run_agent(args.refiner, args.coordinator, args.worker, test_queue=test_list)
		    else:
		        run_agent(args.refiner, args.coordinator, args.worker)