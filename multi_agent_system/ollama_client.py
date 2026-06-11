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
    "1) Установите Ollama с https://ollama.com/download.\n"
    "2) Запустите Ollama: кнопкой в приложении «Запустить Ollama» или командой `ollama serve`.\n"
    "3) Загрузите модель в терминале: `ollama pull llama3.1` или другую модель.\n"
    "4) В этом приложении откройте «Меню → Настройки Ollama»: проверьте API `http://127.0.0.1:11434`, "
    "при необходимости укажите API ключ и путь к исполняемому файлу Ollama.\n"
    "5) Нажмите «Проверить» или «Модели»."
)


@dataclass
class OllamaStatus:
    available: bool
    message: str
    models: List[str]


class OllamaClient:
    """Check, list, and call local Ollama models."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, timeout: float = 60.0, api_key: str = "") -> None:
        self.base_url = ""
        self.api_key = ""
        self.timeout = timeout
        self.configure(base_url, api_key)

    def configure(self, base_url: str, api_key: str = "") -> None:
        self.set_base_url(base_url)
        self.set_api_key(api_key)

    def set_base_url(self, base_url: str) -> None:
        self.base_url = (base_url or OLLAMA_BASE_URL).strip().rstrip("/")

    def set_api_key(self, api_key: str) -> None:
        self.api_key = api_key.strip()

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

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
            return OllamaStatus(True, f"Ollama доступна: {self.base_url}", models)
        except Exception as exc:
            return OllamaStatus(False, f"Ollama недоступна ({self.base_url}): {exc}", [])

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
