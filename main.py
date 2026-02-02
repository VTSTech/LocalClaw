import sys
import argparse
from interfaces.cli import start_cli
# Import web lazily inside function to avoid Streamlit CLI issues if not needed

def main():
    parser = argparse.ArgumentParser(description="LocalClaw Agent Runner")
    parser.add_argument('--mode', choices=['cli', 'web'], default='cli', help="Interface mode")
    # Add the model argument here
    parser.add_argument('--model', type=str, default='llama3.2:1b', help="Override the default Ollama model")
    
    args = parser.parse_args()

    if args.mode == 'cli':
        # Pass the model argument to the CLI start function
        start_cli(model_override=args.model)
    elif args.mode == 'web':
        import os
        os.system("streamlit run interfaces/web.py")

if __name__ == "__main__":
    main()