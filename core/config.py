"""
Config - Secure local configuration management
"""
import os
import json
import base64
from pathlib import Path

from core.api_client import PROVIDER_CONFIG, DEFAULT_PROVIDER, DEFAULT_MODELS


CONFIG_DIR = Path.home() / ".automate_anything"
CONFIG_FILE = CONFIG_DIR / "config.json"


class Config:
    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self._data, f, indent=2)
        try:
            os.chmod(CONFIG_FILE, 0o600)
        except Exception:
            pass

    def _encode(self, value: str) -> str:
        return base64.b64encode(value.encode()).decode()

    def _decode(self, value: str) -> str:
        try:
            return base64.b64decode(value.encode()).decode()
        except Exception:
            return value

    def get_api_key(self) -> str:
        raw = self._data.get("api_key", "")
        return self._decode(raw) if raw else ""

    def set_api_key(self, key: str):
        self.set_provider_key("groq", key)

    def get_openrouter_api_key(self) -> str:
        return self.get_provider_key("openrouter")

    def set_openrouter_api_key(self, key: str):
        self.set_provider_key("openrouter", key)

    def get_provider_key(self, provider: str) -> str:
        raw = self._data.get("api_keys", {}).get(provider, "")
        if not raw and provider == "groq":
            raw = self._data.get("api_key", "")
        if not raw and provider == "openrouter":
            raw = self._data.get("openrouter_api_key", "")
        return self._decode(raw) if raw else ""

    def set_provider_key(self, provider: str, key: str):
        key = (key or "").strip()
        api_keys = self._data.setdefault("api_keys", {})
        if key:
            api_keys[provider] = self._encode(key)
        else:
            api_keys.pop(provider, None)

        if provider == "groq":
            if key:
                self._data["api_key"] = self._encode(key)
            else:
                self._data.pop("api_key", None)
        if provider == "openrouter":
            if key:
                self._data["openrouter_api_key"] = self._encode(key)
            else:
                self._data.pop("openrouter_api_key", None)

        self._save()

    def get_all_provider_keys(self) -> dict[str, str]:
        return {provider: self.get_provider_key(provider) for provider in PROVIDER_CONFIG}

    def get_provider(self) -> str:
        provider = self._data.get("provider", DEFAULT_PROVIDER)
        return provider if provider in PROVIDER_CONFIG else DEFAULT_PROVIDER

    def set_provider(self, provider: str):
        if provider in PROVIDER_CONFIG:
            self._data["provider"] = provider
            self._save()

    def get_model(self) -> str:
        provider = self.get_provider()
        models_by_provider = self._data.get("models_by_provider", {})
        return models_by_provider.get(provider, self._data.get("model", DEFAULT_MODELS[provider]))

    def set_model(self, model: str):
        provider = self.get_provider()
        models_by_provider = self._data.setdefault("models_by_provider", {})
        models_by_provider[provider] = model
        self._data["model"] = model
        self._save()

    def get_model_for_provider(self, provider: str) -> str:
        models_by_provider = self._data.get("models_by_provider", {})
        return models_by_provider.get(provider, DEFAULT_MODELS.get(provider, ""))

    def set_model_for_provider(self, provider: str, model: str):
        models_by_provider = self._data.setdefault("models_by_provider", {})
        models_by_provider[provider] = model
        if provider == self.get_provider():
            self._data["model"] = model
        self._save()

    def has_api_key(self) -> bool:
        return any(self.get_provider_key(provider) for provider in PROVIDER_CONFIG)

    def has_api_key_for_provider(self, provider: str) -> bool:
        return bool(self.get_provider_key(provider))

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self._save()
