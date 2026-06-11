"""Small Ollama HTTP client that uses only Python's standard library."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_INSTALL_URL = "https://ollama.com/download"
OLLAMA_INSTALL_INSTRUCTIONS = (

)


@dataclass
class OllamaStatus:
    available: bool
    message: str
    models: List[str]


class OllamaClient:
    """Check, list, and call local Ollama models."""



    def _request_json(self, path: str, payload: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> Dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=self._headers(),
            method="GET" if payload is None else "POST",
        )
        with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def status(self) -> OllamaStatus:
        try:
            models = self.list_models()


    def list_models(self) -> List[str]:
        data = self._request_json("/api/tags", timeout=5.0)
        return sorted(model.get("name", "") for model in data.get("models", []) if model.get("name"))

    def generate(self, model: str, prompt: str) -> str:
        data = self._request_json(
            "/api/generate",
            {"model": model, "prompt": prompt, "stream": False, "format": "json"},
        )
        return data.get("response", "")

    @staticmethod
    def install_instructions() -> str:
        return OLLAMA_INSTALL_INSTRUCTIONS

    @staticmethod
    def open_install_page() -> None:
        webbrowser.open(OLLAMA_INSTALL_URL)
