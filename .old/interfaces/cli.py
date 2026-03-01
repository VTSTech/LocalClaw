from core.agent import LocalClawAgent
import colorama
from colorama import Fore, Style

colorama.init(autoreset=True)

def start_cli():
    print(Fore.CYAN + "Starting LocalClaw CLI... (Type 'exit' to quit)")
    agent = LocalClawAgent()

    while True:
        try:
            user_input = input(Fore.GREEN + "You: " + Style.RESET_ALL)
            if user_input.lower() in ["exit", "quit"]:
                break
            
            response = agent.chat(user_input)
            print(Fore.MAGENTA + "Claw: " + Style.RESET_ALL + response)
            
        except KeyboardInterrupt:
            break