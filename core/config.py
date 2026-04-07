"""
Config - Secure local configuration management
"""
import os
import json
import base64
from pathlib import Path


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
        # Restrict permissions on Unix
        try:
            os.chmod(CONFIG_FILE, 0o600)
        except Exception:
            pass

    def _encode(self, value: str) -> str:
        """Simple obfuscation (not encryption, but better than plaintext)."""
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
        self._data["api_key"] = self._encode(key)
        self._save()

    def get_model(self) -> str:
        return self._data.get("model", "llama-3.3-70b-versatile")

    def set_model(self, model: str):
        self._data["model"] = model
        self._save()

    def has_api_key(self) -> bool:
        return bool(self.get_api_key() or self.get_openrouter_api_key())

    def get_openrouter_api_key(self) -> str:
        raw = self._data.get("openrouter_api_key", "")
        return self._decode(raw) if raw else ""

    def set_openrouter_api_key(self, key: str):
        key = (key or "").strip()
        if key:
            self._data["openrouter_api_key"] = self._encode(key)
        else:
            self._data.pop("openrouter_api_key", None)
        self._save()

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self._save()
