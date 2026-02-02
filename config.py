import os
from dotenv import load_dotenv

load_dotenv()

# Global Configuration
DEFAULT_MODEL = "qwen2.5:0.5b"  # Change this to "llama3" or others easily
DEBUG_MODE = True               # Toggle verbosity globally if you want

def get_key(key_name):
    return os.getenv(key_name)