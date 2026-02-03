import os
from colorama import Fore, Style
from core.agent import LocalClawAgent
from config import LOCALCLAW_BUILD, LOCALCLAW_BUILD_DATE

def start_cli(model_override):
    
    if model_override:
        agent = LocalClawAgent(model=model_override)
        print(f"Using model override: {model_override}\n")
    else:
        agent = LocalClawAgent()
    
    # 1. Proactive Bootstrap Check
    bootstrap_path = os.path.join(agent.memory.base_path, "BOOTSTRAP.md")
    
    build_str = f"{LOCALCLAW_BUILD} {LOCALCLAW_BUILD_DATE}"
    
    if os.path.exists(bootstrap_path):
        print(f"{Fore.CYAN}LocalClaw {build_str} is waking up...{Style.RESET_ALL}")
        # Send a silent trigger to force the bootstrap ritual
        response = agent.chat("INIT_BOOTSTRAP", verbose=True)
        print(f"\n{Fore.GREEN}Claw:{Style.RESET_ALL} {response}")

    # 2. Main Loop
    try:
        while True:
            user_input = input(f"\n{Fore.BLUE}You:{Style.RESET_ALL} ")
            
            if user_input.lower() in ['exit', 'quit']:
                print("Goodbye!")
                break
                
            response = agent.chat(user_input, verbose=True)
            print(f"\n{Fore.GREEN}Claw:{Style.RESET_ALL} {response}")
            
    except KeyboardInterrupt:
        print("\nSession ended by user.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")