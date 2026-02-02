import json
import os
import chromadb
from datetime import datetime

class Memory:
    def __init__(self, persistence_dir="./memory_store"):
        self.facts_file = os.path.join(persistence_dir, "soul_facts.json")
        os.makedirs(persistence_dir, exist_ok=True)
        
        # Load Long-term Facts (The Soul)
        if not os.path.exists(self.facts_file):
            with open(self.facts_file, 'w') as f:
                json.dump({"agent_name": "LocalClaw", "user_name": "User", "facts": []}, f)
        
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