import sys
import argparse
from interfaces.cli import start_cli
# Import web lazily inside function to avoid Streamlit CLI issues if not needed

def main():
    parser = argparse.ArgumentParser(description="LocalClaw Agent Runner")
    parser.add_argument('--mode', choices=['cli', 'web'], default='cli', help="Interface mode")
    args = parser.parse_args()

    if args.mode == 'cli':
        start_cli()
    elif args.mode == 'web':
        # Streamlit needs to be run via `streamlit run`, so we use subprocess if called via python
        import os
        os.system("streamlit run interfaces/web.py")

if __name__ == "__main__":
    main()