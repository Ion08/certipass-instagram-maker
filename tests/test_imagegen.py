import base64

import pytest

from certipass_instagram.imagegen import (
    ImageGenerationError,
    OpenRouterConfig,
    OpenRouterImageGenerator,
)


class Response:
    status_code = 200

    def json(self):
        return {"data": [{"b64_json": base64.b64encode(b"synthetic-png").decode(),
                          "media_type": "image/png"}],
                "usage": {"cost": 0.13}}


class Session:
    def __init__(self, response=None):
        self.response = response or Response()
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_openrouter_image_generation_uses_dedicated_images_endpoint():
    session = Session()
    generator = OpenRouterImageGenerator(
        OpenRouterConfig(api_key="secret-token"), session=session,
    )
    assert generator.generate("A polished educational illustration") == b"synthetic-png"
    url, request = session.calls[0]
    assert url == "https://openrouter.ai/api/v1/images"
    assert request["headers"]["Authorization"] == "Bearer secret-token"
    assert request["json"] == {
        "model": "openai/gpt-image-2",
        "prompt": "A polished educational illustration",
        "size": "1024x1280",
        "quality": "high",
        "output_format": "png",
        "n": 1,
    }


@pytest.mark.parametrize("status", [402, 429])
def test_credit_or_rate_limit_failure_is_clear_and_sanitized(status):
    class Failure:
        status_code = status
    with pytest.raises(ImageGenerationError, match="credits and rate limits"):
        OpenRouterImageGenerator(OpenRouterConfig(api_key="secret"),
                                 session=Session(Failure())).generate("illustration")


def test_missing_openrouter_key_is_not_echoed(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ImageGenerationError) as exc:
        OpenRouterConfig.from_env()
    assert "private-token" not in str(exc.value)
