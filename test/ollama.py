import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
SHOW_URL = "http://127.0.0.1:11434/api/show"

def chat_api(model: str, messages: list, tools: list, retries=2):
    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "stream": False,
    }

    for attempt in range(retries + 1):
        try:
            r = requests.post(OLLAMA_URL, json=payload, timeout=45)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.ReadTimeout:
            if attempt >= retries:
                raise
            print("[WARN] Model timeout, retrying...")

def get_model_info(model: str, field: str) -> str:
    try:
        r = requests.post(SHOW_URL, json={"name": model}, timeout=10)
        if r.status_code == 200:
            return r.json().get(field, "Field not found.")
        return f"Error: {r.status_code}"
    except Exception as e:
        return str(e)
