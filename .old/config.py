import os
from dotenv import load_dotenv

load_dotenv()

def get_key(key_name):
    # You can add logic here to decrypt keys if you store them encrypted
    return os.getenv(key_name)