import os, json, httpx
from typing import Any

DEFAULT_URL = os.getenv("LLM_GATEWAY_V2_URL", "http://localhost:8100")
DEFAULT_MODEL = os.getenv("LLM_MODEL", None)
DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", None)

class LLM:
    def __init__(self, base_url=DEFAULT_URL, timeout=600):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def chat(self, prompt=None, *, system=None, provider=None,
             model=None, max_tokens=2048, temperature=0.7):
        body = {"prompt": prompt, "system": system, "provider": provider,
                "model": model, "max_tokens": max_tokens,
                "temperature": temperature, "stream": False}
        body = {k: v for k, v in body.items() if v is not None}
        r = httpx.post(f"{self.base_url}/v1/chat", json=body, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

def call_llm(system_prompt: str, user_message: str) -> str:
    result = LLM().chat(
        prompt=user_message,
        system=system_prompt,
        model=DEFAULT_MODEL,
        provider=DEFAULT_PROVIDER,
    )
    return result["text"]
