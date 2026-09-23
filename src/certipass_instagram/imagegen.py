"""OpenRouter image generation client for GPT Image 2."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Any

import requests


class ImageGenerationError(RuntimeError):
    """Image generation failed or is not configured."""


@dataclass(frozen=True)
class OpenRouterConfig:
    api_key: str
    model: str = "openai/gpt-image-2"
    size: str = "1024x1280"
    quality: str = "high"
    timeout_seconds: float = 360

    @classmethod
    def from_env(cls) -> "OpenRouterConfig":
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise ImageGenerationError("Set OPENROUTER_API_KEY as a GitHub Actions secret.")
        return cls(api_key=api_key)


class OpenRouterImageGenerator:
    """Generate image bytes using OpenRouter's dedicated image endpoint."""

    ENDPOINT = "https://openrouter.ai/api/v1/images"

    def __init__(self, config: OpenRouterConfig, *, session: Any | None = None):
        if config.model != "openai/gpt-image-2":
            raise ImageGenerationError("This build is configured for openai/gpt-image-2.")
        if config.size != "1024x1280":
            raise ImageGenerationError("Instagram image dimensions must remain 1024x1280 (4:5).")
        if config.quality not in {"low", "medium", "high", "auto"} or config.timeout_seconds <= 0:
            raise ImageGenerationError("Invalid image generation settings.")
        self.config = config
        self.session = session if session is not None else requests.Session()

    def generate(self, prompt: str) -> bytes:
        if not prompt.strip() or len(prompt) > 32000:
            raise ImageGenerationError("Each image prompt must contain 1 to 32000 characters.")
        try:
            response = self.session.post(
                self.ENDPOINT,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.model,
                    "prompt": prompt,
                    "size": self.config.size,
                    "quality": self.config.quality,
                    "output_format": "png",
                    "n": 1,
                },
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise ImageGenerationError(
                f"OpenRouter image request failed ({type(exc).__name__}); check connectivity and account status."
            ) from None
        if response.status_code in {402, 429}:
            raise ImageGenerationError(
                f"OpenRouter rejected image generation (HTTP {response.status_code}); check credits and rate limits."
            )
        if not 200 <= response.status_code < 300:
            raise ImageGenerationError(f"OpenRouter rejected image generation (HTTP {response.status_code}).")
        try:
            payload = response.json()
            encoded = payload["data"][0]["b64_json"]
            image_bytes = base64.b64decode(encoded, validate=True)
        except (ValueError, KeyError, TypeError, base64.binascii.Error):
            raise ImageGenerationError("OpenRouter returned an invalid image response.") from None
        if not image_bytes:
            raise ImageGenerationError("OpenRouter returned an empty image.")
        return image_bytes
