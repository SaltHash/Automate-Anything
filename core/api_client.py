"""
API Client - multi-provider integration for macro generation
"""
import json
import re
import urllib.request
import urllib.error
from typing import Callable, Optional

from core.storage import Macro, MacroAction


PROVIDER_CONFIG = {
    "groq": {
        "label": "Groq",
        "chat_url": "https://api.groq.com/openai/v1/chat/completions",
        "models_url": "https://api.groq.com/openai/v1/models",
        "models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "gemma2-9b-it",
            "mixtral-8x7b-32768",
        ],
        "model_input": "dropdown",
    },
    "openai": {
        "label": "OpenAI",
        "chat_url": "https://api.openai.com/v1/chat/completions",
        "models_url": "https://api.openai.com/v1/models",
        "models": ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1"],
        "model_input": "dropdown",
    },
    "anthropic": {
        "label": "Anthropic",
        "chat_url": "https://api.anthropic.com/v1/messages",
        "models_url": "https://api.anthropic.com/v1/models",
        "models": ["claude-3-5-haiku-latest", "claude-3-7-sonnet-latest"],
        "model_input": "dropdown",
    },
    "gemini": {
        "label": "Google Gemini",
        "chat_url": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "models_url": "https://generativelanguage.googleapis.com/v1beta/models",
        "models": ["gemini-2.0-flash", "gemini-1.5-pro"],
        "model_input": "dropdown",
    },
    "openrouter": {
        "label": "OpenRouter",
        "chat_url": "https://openrouter.ai/api/v1/chat/completions",
        "models_url": "https://openrouter.ai/api/v1/models",
        "models": ["openai/gpt-4o-mini"],
        "model_input": "text",
    },
}

DEFAULT_PROVIDER = "groq"
DEFAULT_MODELS = {k: v["models"][0] for k, v in PROVIDER_CONFIG.items()}

SYSTEM_PROMPT = """You are an automation expert. When given a task description, generate a structured desktop automation macro.

Respond ONLY with valid JSON matching this exact schema:
{
  "name": "Short descriptive name",
  "summary": "One sentence describing what this macro does",
  "actions": [
    // Each action is one of:
    {
      "type": "click_image",
      "params": {
        "description": "What UI element to click (human readable)",
        "confidence": 0.8,
        "retry_count": 3,
        "retry_delay": 1.0,
        "fallback_coords": null
      }
    },
    {
      "type": "type_text",
      "params": {
        "text": "text to type",
        "delay_between_keys": 0.05
      }
    },
    {
      "type": "wait",
      "params": {
        "seconds": 1.5,
        "description": "Waiting for page to load"
      }
    },
    {
      "type": "scroll",
      "params": {
        "direction": "down",
        "amount": 3,
        "description": "Scroll down to see more content"
      }
    },
    {
      "type": "key_press",
      "params": {
        "keys": ["ctrl", "c"],
        "description": "Copy selected text"
      }
    },
    {
      "type": "screenshot_capture",
      "params": {
        "description": "Take a screenshot for verification"
      }
    }
  ]
}

Guidelines:
- Prefer click_image over coordinates for reliability
- Add wait steps after actions that trigger loading/animations
- Use key_press for keyboard shortcuts
- Keep actions granular and clear
- For click_image, describe the element clearly so a user can capture it
- Set confidence between 0.7-0.95 based on how distinct the element is
- NEVER include markdown, explanations, or anything outside the JSON object"""


class APIError(Exception):
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class AIClient:
    def __init__(self, provider: str, model: str, api_keys: dict[str, str]):
        self.provider = provider if provider in PROVIDER_CONFIG else DEFAULT_PROVIDER
        self.model = model or DEFAULT_MODELS[self.provider]
        self.api_keys = {k: self._normalize_api_key(v) for k, v in (api_keys or {}).items()}

    @staticmethod
    def _normalize_api_key(api_key: str) -> str:
        key = (api_key or "").strip()
        if key.lower().startswith("bearer "):
            key = key[7:].strip()
        if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
            key = key[1:-1].strip()
        return key

    @property
    def provider_label(self) -> str:
        return PROVIDER_CONFIG[self.provider]["label"]

    @property
    def active_key(self) -> str:
        return self.api_keys.get(self.provider, "")

    def _headers(self, is_json: bool = True) -> dict:
        key = self.active_key
        if not key:
            return {}

        headers = {}
        if self.provider == "anthropic":
            headers["x-api-key"] = key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = f"Bearer {key}"

        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://automate-anything.local"
            headers["X-Title"] = "Automate Anything"

        if is_json:
            headers["Content-Type"] = "application/json"
        return headers

    def validate_key(self) -> tuple[bool, str]:
        try:
            req = urllib.request.Request(
                self._models_url(),
                headers=self._headers(is_json=False),
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200, ""
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return False, "Invalid API key. Please check and try again."
            if e.code == 403:
                return False, f"Access denied by {self.provider_label} (HTTP 403)."
            return False, f"Validation failed (HTTP {e.code})."
        except urllib.error.URLError as e:
            return False, f"Network error during validation: {e.reason}"
        except Exception as e:
            return False, f"Validation error: {e}"

    def _models_url(self) -> str:
        cfg = PROVIDER_CONFIG[self.provider]
        if self.provider == "gemini":
            return f"{cfg['models_url']}?key={self.active_key}"
        return cfg["models_url"]

    def generate_macro(self, prompt: str, progress_callback: Optional[Callable[[str], None]] = None) -> Macro:
        if not self.active_key:
            raise APIError(f"No API key set for {self.provider_label}. Open Settings to add it.")

        if progress_callback:
            progress_callback(f"Sending request to {self.provider_label} API...")

        req = self._build_chat_request(prompt)
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 401:
                raise APIError(f"Invalid API key for {self.provider_label}.", 401)
            if e.code == 429:
                raise APIError("Rate limit exceeded. Please wait and try again.", 429)
            raise APIError(f"API error {e.code}: {body}", e.code)
        except urllib.error.URLError as e:
            raise APIError(f"Network error: {e.reason}")

        if progress_callback:
            progress_callback("Parsing macro from response...")

        raw_text = self._extract_text(data)
        return self._parse_macro(raw_text, prompt)

    def _build_chat_request(self, prompt: str) -> urllib.request.Request:
        cfg = PROVIDER_CONFIG[self.provider]

        if self.provider == "anthropic":
            payload = {
                "model": self.model,
                "max_tokens": 2048,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": f"Create a macro for: {prompt}"}],
            }
            return urllib.request.Request(
                cfg["chat_url"],
                data=json.dumps(payload).encode("utf-8"),
                headers=self._headers(),
                method="POST",
            )

        if self.provider == "gemini":
            payload = {
                "contents": [{"parts": [{"text": f"{SYSTEM_PROMPT}\n\nCreate a macro for: {prompt}"}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
            }
            url = cfg["chat_url"].format(model=self.model) + f"?key={self.active_key}"
            return urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Create a macro for: {prompt}"},
            ],
            "temperature": 0.3,
            "max_tokens": 2048,
        }
        return urllib.request.Request(
            cfg["chat_url"],
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )

    def _extract_text(self, data: dict) -> str:
        if self.provider == "anthropic":
            content = data.get("content", [])
            for block in content:
                if block.get("type") == "text":
                    return block.get("text", "")
            raise APIError("Anthropic response missing text.")

        if self.provider == "gemini":
            candidates = data.get("candidates", [])
            if not candidates:
                raise APIError("Gemini response missing candidates.")
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "\n".join(part.get("text", "") for part in parts if part.get("text"))
            if not text:
                raise APIError("Gemini response missing text.")
            return text

        try:
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise APIError(f"Unexpected API response format: {e}")

    def _parse_macro(self, raw: str, original_prompt: str) -> Macro:
        text = raw.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise APIError("Model response did not contain valid JSON.")

        try:
            data = json.loads(text[start:end])
        except json.JSONDecodeError as e:
            raise APIError(f"Failed to parse macro JSON: {e}")

        actions = []
        for action in data.get("actions", []):
            action_type = action.get("type", "")
            params = action.get("params", {})
            if action_type:
                actions.append(MacroAction(type=action_type, params=params))

        return Macro(
            id=None,
            name=data.get("name", "Unnamed Macro"),
            prompt=original_prompt,
            summary=data.get("summary", ""),
            actions=actions,
        )
