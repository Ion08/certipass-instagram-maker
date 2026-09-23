from __future__ import annotations

import requests
import pytest

from certipass_instagram.meta import (
    InstagramPublisher,
    MetaAmbiguousPublishError,
    MetaConfig,
    MetaConfigurationError,
    MetaTerminalError,
    MetaTransientError,
)


FAKE_TOKEN = "synthetic-not-a-valid-token"


class Response:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body or {}

    def json(self):
        return self._body


class Session:
    def __init__(self, responses=(), exception=None):
        self.responses = list(responses)
        self.exception = exception
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if self.exception:
            raise self.exception
        return self.responses.pop(0)


def client(*, dry_run=False, session=None):
    return InstagramPublisher(
        MetaConfig("17841400000000000", FAKE_TOKEN, "XX.Y", dry_run=dry_run),
        session=session,
    )


def test_dry_run_create_and_publish_make_no_network_calls():
    session = Session()
    publisher = client(dry_run=True, session=session)

    assert publisher.create_post(image_urls=["https://cdn.example/card.png"], caption="caption") is None
    assert publisher.publish_post("container-1") is None
    assert session.calls == []


def test_create_single_image_post_uses_image_url():
    session = Session([Response(body={"id": "container-123"})])
    result = client(session=session).create_post(image_urls=["https://cdn.example/card.png"], caption="Hello")

    assert result == "container-123"
    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert url.endswith("/vXX.Y/17841400000000000/media")
    assert kwargs["data"] == {"image_url": "https://cdn.example/card.png", "caption": "Hello"}
    assert kwargs["params"]["access_token"] == FAKE_TOKEN


def test_status_returns_processing_state_and_rejects_terminal_state():
    processing = Session([Response(body={"status_code": "IN_PROGRESS"})])
    assert client(session=processing).get_container_status("container-123") == "IN_PROGRESS"
    failed = Session([Response(body={"status_code": "ERROR"})])
    with pytest.raises(MetaTerminalError, match="container is error"):
        client(session=failed).get_container_status("container-123")


def test_create_carousel_slides_then_parent_container():
    session = Session([
        Response(body={"id": "slide-1"}), Response(body={"id": "slide-2"}),
        Response(body={"id": "container-123"}),
    ])
    result = client(session=session).create_post(
        image_urls=["https://cdn.example/1.png", "https://cdn.example/2.png"], caption="Hello",
    )
    assert result == "container-123"
    assert [call[2]["data"] for call in session.calls] == [
        {"image_url": "https://cdn.example/1.png", "is_carousel_item": "true"},
        {"image_url": "https://cdn.example/2.png", "is_carousel_item": "true"},
        {"media_type": "CAROUSEL", "children": "slide-1,slide-2", "caption": "Hello"},
    ]


def test_publish_uses_creation_id_and_returns_published_media_id():
    session = Session([Response(body={"id": "media-456"})])
    result = client(session=session).publish_post("container-123")
    assert result == "media-456"
    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert url.endswith("/vXX.Y/17841400000000000/media_publish")
    assert kwargs["data"] == {"creation_id": "container-123"}


def test_timeout_and_publish_server_error_are_ambiguous():
    timeout = Session(exception=requests.Timeout(f"secret {FAKE_TOKEN}"))
    with pytest.raises(MetaAmbiguousPublishError) as exc:
        client(session=timeout).publish_post("container-123")
    assert FAKE_TOKEN not in str(exc.value)

    server = Session([Response(503, {"error": {"message": "temporary"}})])
    with pytest.raises(MetaAmbiguousPublishError, match="may have succeeded"):
        client(session=server).publish_post("container-123")


def test_transient_and_terminal_http_failures_are_distinct_and_redacted():
    transient = Session([Response(429, {"error": {"message": f"rate limit {FAKE_TOKEN}", "code": 4}})])
    with pytest.raises(MetaTransientError) as exc:
        client(session=transient).create_post(image_urls=["https://cdn.example/a.png"], caption="a")
    assert FAKE_TOKEN not in str(exc.value)

    terminal = Session([Response(400, {"error": {"message": "invalid permission", "code": 10}})])
    with pytest.raises(MetaTerminalError, match="Meta code 10"):
        client(session=terminal).create_post(image_urls=["https://cdn.example/a.png"], caption="a")


def test_configuration_requires_explicit_api_version_and_https_media():
    with pytest.raises(MetaConfigurationError):
        InstagramPublisher(MetaConfig("id", FAKE_TOKEN, "vXX.Y"), session=Session())
    with pytest.raises(MetaConfigurationError):
        client(session=Session()).create_post(image_urls=["http://example.com/a.png"], caption="a")


def test_missing_environment_configuration_does_not_echo_secret(monkeypatch):
    for name in ("INSTAGRAM_USER_ID", "INSTAGRAM_ACCESS_TOKEN", "META_GRAPH_API_VERSION"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", FAKE_TOKEN)
    with pytest.raises(MetaConfigurationError) as exc:
        MetaConfig.from_env()
    assert FAKE_TOKEN not in str(exc.value)
