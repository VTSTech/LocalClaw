import os
import keyring
from dotenv import load_dotenv

load_dotenv()

LOCALCLAW_BUILD = "R0"
LOCALCLAW_BUILD_DATE = "02.03.2026 11:40:21AM"

# Global Configuration
DEFAULT_MODEL = "cogito:3b"  # Change this to "llama3" or others easily
DEBUG_MODE = True               # Toggle verbosity globally if you want
BOOTSTRAP_VERBOSITY = True

def get_key(key_name):
    return os.getenv(key_name)

# Usage: save_api_key("OpenWeather", "your_api_key_here")
def save_api_key(service_name, key_value):
    keyring.set_password("LocalClaw", service_name, key_value)

def get_api_key(service_name):
    return keyring.get_password("LocalClaw", service_name)

def store_secret(service, value):
    # This stores the key in the OS-level secure vault
    keyring.set_password("LocalClaw", service, value)
    return f"Secret for {service} stored securely."

def get_secret(service):
    return keyring.get_password("LocalClaw", service)    