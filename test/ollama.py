import requests
import time

# Ollama Connection Constants
CHAT_URL = "http://127.0.0.1:11434/api/chat"

# Strict parameters for deterministic agent behavior
# temperature 0.0 is non-negotiable for tool/tag accuracy
params = {
    "temperature": 0.0,      
    "num_predict": 512,      # Increased slightly to allow for [SCRIPT] blocks
    "top_k": 20,             
    "repeat_penalty": 1.1,   
    "stop": ["```", "<|im_end|>", "<|im_start|>", "User>", "\nUser>"]
}

def chat_api(model: str, messages: list, tools: list, retries=5):
    """
    Communicates with local Ollama instance with exponential backoff.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": params,
    }
    
    # R2 architecture uses raw strings/tags, but we keep the structure for compatibility
    if tools:
        payload["tools"] = tools

    for attempt in range(retries + 1):
        try:
            response = requests.post(CHAT_URL, json=payload, timeout=120)
            response.raise_for_status()
            
            data = response.json()
            if not data.get("message") or not data["message"].get("content"):
                raise RuntimeError("Empty response from model")
                
            return data

        except (requests.exceptions.RequestException, RuntimeError) as e:
            if attempt < retries:
                # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                wait_time = 2 ** attempt
                time.sleep(wait_time)
                continue
            else:
                # Final failure notification
                return {
                    "message": {
                        "role": "assistant",
                        "content": f"[CHAT] I'm sorry, but I encountered a persistent error connecting to the model: {str(e)}"
                    }
                }

def get_model_info(model: str, detail: str = "template"):
    """
    Utility to check model metadata/templates via /api/show
    """
    try:
        r = requests.post("http://127.0.0.1:11434/api/show", json={"name": model})
        r.raise_for_status()
        return r.json().get(detail, "No info available")
    except:
        return f"Error retrieving info for {model}"