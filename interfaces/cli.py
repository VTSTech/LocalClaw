from core.agent import LocalClawAgent
import colorama
from colorama import Fore, Style

colorama.init(autoreset=True)

def start_cli():
    print(Fore.CYAN + "Starting LocalClaw CLI... (Type 'exit' to quit)")
    
    # No model passed, so it uses DEFAULT_MODEL from config.py
    agent = LocalClawAgent() 

    while True:
        try:
            user_input = input(Fore.GREEN + "\nYou: " + Style.RESET_ALL)
            if user_input.lower() in ["exit", "quit"]:
                break
            
            # You can also move verbose=True to a config variable if you like
            response = agent.chat(user_input, verbose=True)
            
            print(Fore.MAGENTA + "Claw: " + Style.RESET_ALL + response)
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break