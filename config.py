import os
import keyring
from dotenv import load_dotenv

load_dotenv()

LOCALCLAW_BUILD = "R0"
LOCALCLAW_BUILD_DATE = "02.02.2026"
LOCALCLAW_BUILD_TIME = "2026-02-02 6:27:54PM"
	
# Global Configuration
DEFAULT_MODEL = "llama3.2:1b"  # Change this to "llama3" or others easily
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