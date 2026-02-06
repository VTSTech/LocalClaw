import requests

CHAT_URL = "http://127.0.0.1:11434/api/chat"
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
            r = requests.post(CHAT_URL, json=payload, timeout=120)
            r.raise_for_status()
            data = r.json()
            if not data.get("message"):
                raise RuntimeError("Model returned no message")
            return data
        except Exception as e:
            if attempt >= retries:
                raise
            print("[WARN] retrying model call...")

def get_model_info(model: str, field: str):
    try:
        r = requests.post(SHOW_URL, json={"name": model}, timeout=60)
        return r.json().get(field, "N/A") if r.ok else f"Error {r.status_code}"
    except Exception as e:
        return str(e)
