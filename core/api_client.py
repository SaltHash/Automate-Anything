"""
API Client - Groq/OpenRouter integration for macro generation
"""
import json
import re
import urllib.request
import urllib.error
from typing import List, Callable, Optional

from core.storage import Macro, MacroAction


GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_DEFAULT_MODEL = "openai/gpt-4o-mini"

AVAILABLE_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
    OPENROUTER_DEFAULT_MODEL,
]

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


class GroqClient:
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile", openrouter_api_key: str = ""):
        self.api_key = self._normalize_api_key(api_key)
        self.openrouter_api_key = self._normalize_api_key(openrouter_api_key)
        self.model = model

    @staticmethod
    def _normalize_api_key(api_key: str) -> str:
        key = (api_key or "").strip()
        if key.lower().startswith("bearer "):
            key = key[7:].strip()
        if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
            key = key[1:-1].strip()
        return key

    @property
    def _use_openrouter(self) -> bool:
        return bool(self.openrouter_api_key)

    @property
    def _active_key(self) -> str:
        return self.openrouter_api_key if self._use_openrouter else self.api_key

    @property
    def _chat_url(self) -> str:
        return OPENROUTER_API_URL if self._use_openrouter else GROQ_API_URL

    @property
    def _models_url(self) -> str:
        return OPENROUTER_MODELS_URL if self._use_openrouter else GROQ_MODELS_URL

    @property
    def _resolved_model(self) -> str:
        if not self._use_openrouter:
            return self.model
        if self.model in AVAILABLE_MODELS[:4]:
            return OPENROUTER_DEFAULT_MODEL
        return self.model or OPENROUTER_DEFAULT_MODEL

    def _headers(self) -> dict:
        headers = {
            "Authorization": f"Bearer {self._active_key}",
            "Content-Type": "application/json",
        }
        if self._use_openrouter:
            headers["HTTP-Referer"] = "https://automate-anything.local"
            headers["X-Title"] = "Automate Anything"
        return headers

    def validate_key(self) -> tuple[bool, str]:
        """Quick validation by listing models."""
        try:
            req = urllib.request.Request(
                self._models_url,
                headers=self._headers(),
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200, ""
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return False, "Invalid API key. Please check and try again."
            if e.code == 403:
                provider = "OpenRouter" if self._use_openrouter else "Groq"
                return False, f"Access denied by {provider} (HTTP 403). Check key permissions and account status."
            return False, f"Validation failed (HTTP {e.code}). Please try again."
        except urllib.error.URLError as e:
            return False, f"Network error during validation: {e.reason}"
        except Exception as e:
            return False, f"Validation error: {e}"

    def generate_macro(
        self,
        prompt: str,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Macro:
        """Call Groq API and parse response into a Macro."""

        if progress_callback:
            provider = "OpenRouter" if self._use_openrouter else "Groq"
            progress_callback(f"Sending request to {provider} API...")

        payload = json.dumps({
            "model": self._resolved_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Create a macro for: {prompt}"},
            ],
            "temperature": 0.3,
            "max_tokens": 2048,
        }).encode("utf-8")

        req = urllib.request.Request(self._chat_url, data=payload, headers=self._headers(), method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 401:
                provider = "OpenRouter" if self._use_openrouter else "Groq"
                raise APIError(f"Invalid API key. Please check your {provider} API key.", 401)
            elif e.code == 429:
                raise APIError("Rate limit exceeded. Please wait and try again.", 429)
            else:
                raise APIError(f"API error {e.code}: {body}", e.code)
        except urllib.error.URLError as e:
            raise APIError(f"Network error: {e.reason}")

        if progress_callback:
            progress_callback("Parsing macro from response...")

        raw_text = data["choices"][0]["message"]["content"]
        return self._parse_macro(raw_text, prompt)

    def _parse_macro(self, raw: str, original_prompt: str) -> Macro:
        """Extract and parse JSON from the model response."""
        # Strip markdown fences if present
        text = raw.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

        # Find JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise APIError("Model response did not contain valid JSON.")

        try:
            data = json.loads(text[start:end])
        except json.JSONDecodeError as e:
            raise APIError(f"Failed to parse macro JSON: {e}")

        actions = []
        for a in data.get("actions", []):
            action_type = a.get("type", "")
            params = a.get("params", {})
            if action_type:
                actions.append(MacroAction(type=action_type, params=params))

        return Macro(
            id=None,
            name=data.get("name", "Unnamed Macro"),
            prompt=original_prompt,
            summary=data.get("summary", ""),
            actions=actions,
        )
