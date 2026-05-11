"""OpenRouter client and provider abstraction."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from apps.api.config import Settings, get_settings


@dataclass(slots=True)
class ModelUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(slots=True)
class ModelResponse:
    content: str
    raw: dict[str, Any]
    usage: ModelUsage | None = None


class ModelProvider:
    def chat(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = False,
        timeout_seconds: int = 120,
    ) -> ModelResponse:
        raise NotImplementedError


class OpenRouterClient(ModelProvider):
    def __init__(self, settings: Settings | None = None, http_client: httpx.Client | None = None) -> None:
        self.settings = settings or get_settings()
        self.http_client = http_client or httpx.Client(base_url=self.settings.openrouter_base_url)

    def chat(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = False,
        timeout_seconds: int = 120,
    ) -> ModelResponse:
        if not self.settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is not configured")

        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.app_url,
            "X-Title": self.settings.app_name,
        }

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.http_client.post(
                    "/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=timeout_seconds,
                )
                response.raise_for_status()
                raw = response.json()
                choice = raw["choices"][0]["message"]["content"]
                usage = raw.get("usage", {})
                return ModelResponse(
                    content=choice,
                    raw=raw,
                    usage=ModelUsage(
                        prompt_tokens=usage.get("prompt_tokens"),
                        completion_tokens=usage.get("completion_tokens"),
                        total_tokens=usage.get("total_tokens"),
                    ),
                )
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
                last_error = exc
                time.sleep(1 + attempt)
        raise RuntimeError(f"OpenRouter request failed: {last_error}") from last_error

    @staticmethod
    def extract_json(text: str) -> dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if fenced:
                return json.loads(fenced.group(1))
            generic = re.search(r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})", text, re.DOTALL)
            if generic:
                return json.loads(generic.group(1))
        raise ValueError("Model response did not contain valid JSON")

