import os
import keyring
from dotenv import load_dotenv

load_dotenv()

# Global Configuration
DEFAULT_MODEL = "qwen2.5:0.5b"  # Change this to "llama3" or others easily
DEBUG_MODE = True               # Toggle verbosity globally if you want

def get_key(key_name):
    return os.getenv(key_name)

# Usage: save_api_key("OpenWeather", "your_api_key_here")
def save_api_key(service_name, key_value):
    keyring.set_password("LocalClaw", service_name, key_value)

def get_api_key(service_name):
    return keyring.get_password("LocalClaw", service_name)