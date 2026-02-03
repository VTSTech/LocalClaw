import os
from colorama import Fore, Style
from core.agent import LocalClawAgent
from config import LOCALCLAW_BUILD, LOCALCLAW_BUILD_DATE, BOOTSTRAP_DONE

def start_cli(model_override):
    if model_override:
        agent = LocalClawAgent(model=model_override)
        print(f"Using model override: {model_override}\n")
    else:
        agent = LocalClawAgent()
    
    bootstrap_path = os.path.join(agent.memory.base_path, "BOOTSTRAP.md")
    build_str = f"{LOCALCLAW_BUILD} {LOCALCLAW_BUILD_DATE}"

    def force_bootstrap():
        print(f"{Fore.MAGENTA}[ADMIN] Forcing Manual Bootstrap...{Style.RESET_ALL}")
        id_content = "AI_NAME: VTSBot\nVibe: Adventurous & Curious\n"
        user_content = "HUMAN_NAME: VTSTech\nStatus: System Architect"
        agent.tools.execute("write_file", f"IDENTITY.md|{id_content}")
        agent.tools.execute("write_file", f"USER.md|{user_content}")
        if os.path.exists(bootstrap_path):
            os.remove(bootstrap_path)
        print(f"{Fore.GREEN}[SUCCESS] Resident files created. BOOTSTRAP.md removed.{Style.RESET_ALL}")

    if os.path.exists(bootstrap_path):
        print(f"{Fore.CYAN}LocalClaw {build_str} is waking up (New Install)...{Style.RESET_ALL}")
        force_bootstrap()
        response = agent.chat("INIT_BOOTSTRAP", verbose=True)
        print(f"\n{Fore.GREEN}Claw:{Style.RESET_ALL} {response}")
    else:
        print(f"{Fore.CYAN}LocalClaw {build_str} is resuming...{Style.RESET_ALL}")

    try:
        while True:
            user_input = input(f"\n{Fore.BLUE}You:{Style.RESET_ALL} ")
            
            if user_input.startswith("/bootstrap"):
                force_bootstrap()
                continue 
                       
            if user_input.lower() in ['exit', 'quit']:
                print("Goodbye!")
                break
                
            response = agent.chat(user_input, verbose=True)
            print(f"\n{Fore.GREEN}Claw:{Style.RESET_ALL} {response}")
            
    except KeyboardInterrupt:
        print("\nSession ended by user.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")