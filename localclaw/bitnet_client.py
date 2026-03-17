import json
import urllib.request
from .config import BITNET_BASE_URL

class BitnetClient:
    def __init__(self, base_url=None, timeout=120):
        # Prioritize passed URL, fallback to config
        self.base_url = base_url or BITNET_BASE_URL
        self.timeout = timeout

    def is_running(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base_url}/health", timeout=2) as resp:
                return resp.getcode() == 200
        except:
            return False

    def list_models(self):
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=5)
            if response.status_code == 200:
                data = response.json()
                # Return the ID of the model(s) from the data you verified
                return [m['id'] for m in data.get('data', [])]
        except:
            return []
    def chat(
        self,
        model: str,
        messages: list[dict],
        options: dict | None = None,
        stream: bool = False,
        tools: list | None = None, # Signature fix for agent.py
        **kwargs,                  # Catch-all for extra agent args
    ) -> dict:
        url = f"{self.base_url}/v1/chat/completions"
        
        data = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "temperature": (options or {}).get("temperature", 0.7),
        }

        req = urllib.request.Request(
            url, 
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            # Normalize OpenAI completion to Ollama format for the Agent
            return {
                "model": model,
                "message": {
                    "role": "assistant",
                    "content": result["choices"][0]["message"]["content"]
                },
                "done": True
            }

    def model_supports_tools(self, model: str) -> bool:
        return False # BitNet models require ReAct fallback in Agent.py