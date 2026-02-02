import json
import os
import chromadb
from datetime import datetime

class Memory:
    def __init__(self, base_path="memory_store"):
        self.base_path = base_path
        self.memory_dir = os.path.join(base_path, "memory")
        os.makedirs(self.memory_dir, exist_ok=True)

    def read_soul(self):
        """Reads SOUL.md, USER.md, and MEMORY.md to build context."""
        context = ""
        files_to_read = ['SOUL.md', 'USER.md', 'MEMORY.md', 'AGENTS.md']
        
        for filename in files_to_read:
            path = os.path.join(self.base_path, filename)
            if os.path.exists(path):
                with open(path, 'r') as f:
                    context += f"\n--- {filename} ---\n{f.read()}\n"
        return context

    def log_daily(self, role, content):
        """Writes to memory/YYYY-MM-DD.md as per OpenClaw spec."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = os.path.join(self.memory_dir, f"{date_str}.md")
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        with open(file_path, "a") as f:
            f.write(f"**{timestamp} - {role.upper()}**: {content}\n\n")
        
        self.chroma_client = chromadb.Client() # In-memory for now, can be persistent
        self.collection = self.chroma_client.create_collection(name="conversation")

    def get_soul(self):
        with open(self.facts_file, 'r') as f:
            data = json.load(f)
        return data

    def save_fact(self, fact):
        data = self.get_soul()
        
        # If the model just sends the name (like 'VTSTech'), 
        # or a sentence, let's try to capture it.
        clean_fact = fact.replace("The user's name is", "").strip()
        
        # Simple heuristic: if it's 1-2 words, it's probably the name update
        if len(clean_fact.split()) <= 2:
            data["user_name"] = clean_fact
            
        data["facts"].append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {fact}")
        with open(self.facts_file, 'w') as f:
            json.dump(data, f, indent=4)

    def add_log(self, role, content):
        # Store vector embedding of conversation for retrieval
        self.collection.add(
            documents=[content],
            metadatas=[{"role": role, "timestamp": str(datetime.now())}],
            ids=[str(datetime.now().timestamp())]
        )