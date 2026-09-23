"""Small, dry-run-safe client for Instagram publishing with Instagram Login.

The Graph API version is deliberately required from configuration: callers must
select a version they have verified in their Meta app instead of inheriting a
possibly stale version from this library.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

import requests


class MetaError(RuntimeError):
    """Base class for sanitized Instagram API errors."""


class MetaConfigurationError(MetaError):
    pass


class MetaTransientError(MetaError):
    """Request is known not to have completed successfully; a retry may work."""


class MetaTerminalError(MetaError):
    """Meta rejected the request; fix permissions or request data before retry."""


class MetaAmbiguousPublishError(MetaError):
    """Publish may have succeeded, so callers must check status before retrying."""


@dataclass(frozen=True)
class MetaConfig:
    instagram_user_id: str
    access_token: str
    api_version: str
    dry_run: bool = True
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls, *, dry_run: bool = True) -> "MetaConfig":
        """Read secrets from environment without logging or echoing them."""
        names = {
            "instagram_user_id": "INSTAGRAM_USER_ID",
            "access_token": "INSTAGRAM_ACCESS_TOKEN",
            "api_version": "META_GRAPH_API_VERSION",
        }
        missing = [env for attr, env in names.items() if not os.environ.get(env)]
        if missing:
            raise MetaConfigurationError("Missing Meta configuration: " + ", ".join(missing))
        return cls(**{attr: os.environ[env] for attr, env in names.items()}, dry_run=dry_run)

    def validate(self) -> None:
        if not self.instagram_user_id.strip():
            raise MetaConfigurationError("Instagram user ID must not be empty")
        if not self.access_token.strip():
            raise MetaConfigurationError("Instagram access token must not be empty")
        version = self.api_version.strip()
        if not version or version.startswith("v") or "/" in version:
            raise MetaConfigurationError("Set META_GRAPH_API_VERSION to a verified version number (for example, XX.Y)")
        if self.timeout_seconds <= 0:
            raise MetaConfigurationError("Timeout must be positive")


class InstagramPublisher:
    """Instagram Login publisher; pass a requests-compatible session for tests."""

    BASE_URL = "https://graph.instagram.com"

    def __init__(self, config: MetaConfig, *, session: Any | None = None):
        config.validate()
        self.config = config
        self.session = session if session is not None else requests.Session()
        self.base_url = f"{self.BASE_URL}/v{config.api_version}"

    def create_reel(self, *, video_url: str, caption: str, share_to_feed: bool = True) -> str | None:
        """Create a Reel container and return its ID; dry-run returns None offline."""
        if self.config.dry_run:
            return None
        if not video_url.startswith("https://"):
            raise MetaConfigurationError("Instagram must be able to fetch the Reel from an HTTPS URL")
        data = self._request(
            "POST", f"/{self.config.instagram_user_id}/media",
            data={"media_type": "REELS", "video_url": video_url, "caption": caption,
                  "share_to_feed": "true" if share_to_feed else "false"},
            operation="create",
        )
        container_id = data.get("id")
        if not isinstance(container_id, str) or not container_id:
            raise MetaTerminalError("Meta response did not contain a media container ID")
        return container_id

    def get_container_status(self, container_id: str) -> str:
        """Return Meta's status_code for an existing media container."""
        data = self._request("GET", f"/{container_id}", params={"fields": "status_code"}, operation="status")
        status = data.get("status_code")
        if not isinstance(status, str):
            raise MetaTerminalError("Meta response did not contain a container status")
        if status in {"ERROR", "EXPIRED"}:
            raise MetaTerminalError(f"Instagram media container is {status.lower()}")
        return status

    def publish_reel(self, container_id: str) -> str | None:
        """Publish one ready container; ambiguous results must never be blindly retried."""
        if self.config.dry_run:
            return None
        data = self._request(
            "POST", f"/{self.config.instagram_user_id}/media_publish",
            data={"creation_id": container_id}, operation="publish",
        )
        media_id = data.get("id")
        if not isinstance(media_id, str) or not media_id:
            raise MetaAmbiguousPublishError("Meta accepted publish request but returned no media ID; check container status before retrying")
        return media_id

    def _request(self, method: str, path: str, *, operation: str,
                 params: Mapping[str, str] | None = None,
                 data: Mapping[str, str] | None = None) -> dict[str, Any]:
        request_params = dict(params or {})
        request_data = dict(data or {})
        # Instagram Login accepts the user token as access_token. Never put it in
        # the URL ourselves (which can enter logs); requests encodes it in params.
        request_params["access_token"] = self.config.access_token
        try:
            response = self.session.request(
                method, self.base_url + path, params=request_params,
                data=request_data if method == "POST" else None,
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as exc:
            safe_message = _redact(str(exc), self.config.access_token)
            if operation == "publish":
                raise MetaAmbiguousPublishError(
                    f"Publish outcome is unknown ({type(exc).__name__}); check status before retrying"
                ) from None
            raise MetaTransientError(f"Instagram {operation} request failed ({type(exc).__name__}): {safe_message}") from None

        try:
            body = response.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            body = {}
        if not isinstance(body, dict):
            body = {}
        if not 200 <= response.status_code < 300:
            error = body.get("error") if isinstance(body.get("error"), dict) else {}
            message = _redact(str(error.get("message") or f"HTTP {response.status_code}"), self.config.access_token)
            code = error.get("code")
            details = f" (Meta code {code})" if isinstance(code, (str, int)) else ""
            if operation == "publish" and response.status_code >= 500:
                raise MetaAmbiguousPublishError(f"Publish may have succeeded (HTTP {response.status_code}); check status before retrying")
            if response.status_code == 429 or response.status_code >= 500:
                raise MetaTransientError(f"Instagram {operation} failed (HTTP {response.status_code}){details}: {message}")
            raise MetaTerminalError(f"Instagram {operation} rejected (HTTP {response.status_code}){details}: {message}")
        return body


def _redact(value: str, token: str) -> str:
    return value.replace(token, "[REDACTED]") if token else value
