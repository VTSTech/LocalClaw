from core.agent import LocalClawAgent
import colorama
from colorama import Fore, Style

colorama.init(autoreset=True)

def start_cli():
    agent = LocalClawAgent()
    
    # Check if this is the first run
    if os.path.exists("memory_store/BOOTSTRAP.md"):
        # We trigger a "silent" first turn to let the agent speak first
        print(f"{Fore.CYAN}LocalClaw is waking up...{Style.RESET_ALL}")
        response = agent.chat("INIT_BOOTSTRAP", verbose=False)
        print(f"\n{Fore.GREEN}Claw:{Style.RESET_ALL} {response}")

    while True:
        user_input = input(f"\n{Fore.BLUE}You:{Style.RESET_ALL} ")
        if user_input.lower() in ['exit', 'quit']:
            break
            
            # You can also move verbose=True to a config variable if you like
            response = agent.chat(user_input, verbose=True)
            
            print(Fore.MAGENTA + "Claw: " + Style.RESET_ALL + response)
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break