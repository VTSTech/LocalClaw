import json
import os
from datetime import datetime

class Memory:
    def __init__(self, base_path="memory_store"):
        self.base_path = base_path
        self.memory_dir = os.path.join(base_path, "memory")
        # Ensure the soul file exists for legacy 'save_fact' calls
        self.facts_file = os.path.join(base_path, "soul_facts.json")
        
        os.makedirs(self.memory_dir, exist_ok=True)
        if not os.path.exists(self.facts_file):
            with open(self.facts_file, 'w') as f:
                json.dump({"agent_name": "LocalClaw", "user_name": "User", "facts": []}, f)

    def read_soul(self):
        """Reads SOUL.md, USER.md, MEMORY.md, and BOOTSTRAP.md to build context."""
        context = ""
        # Added BOOTSTRAP.md to the reading list
        files_to_read = ['BOOTSTRAP.md', 'SOUL.md', 'USER.md', 'MEMORY.md', 'AGENTS.md']
        
        for filename in files_to_read:
            path = os.path.join(self.base_path, filename)
            if os.path.exists(path):
                with open(path, 'r') as f:
                    context += f"\n--- {filename} ---\n{f.read()}\n"
        return context

    def add_log(self, role, content):
        """Standardizes logging to the daily Markdown files."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = os.path.join(self.memory_dir, f"{date_str}.md")
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        with open(file_path, "a") as f:
            f.write(f"### {timestamp} - {role.upper()}\n{content}\n\n")

    def get_soul(self):
        with open(self.facts_file, 'r') as f:
            return json.load(f)

    def save_fact(self, fact):
        data = self.get_soul()
        clean_fact = fact.replace("The user's name is", "").strip()
        
        if len(clean_fact.split()) <= 2:
            data["user_name"] = clean_fact
            
        data["facts"].append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {fact}")
        with open(self.facts_file, 'w') as f:
            json.dump(data, f, indent=4)