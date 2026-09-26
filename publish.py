"""Publish the next certiPass carousel and its first slide as an Instagram Story."""

import json
import os
import sys
import time
import base64
import hashlib
from datetime import date, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from cryptography.fernet import Fernet, InvalidToken


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "data" / "posts.json"
STATE = ROOT / "data" / "state.json"
TOKEN_FILE = ROOT / "data" / "token.enc"
TZ = ZoneInfo("Europe/Chisinau")
GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v26.0")
GRAPH = f"https://graph.instagram.com/{GRAPH_VERSION}"
TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
IG_USER_ID = os.environ.get("IG_USER_ID", "")
MEDIA_BASE_URL = os.environ.get("MEDIA_BASE_URL", "").rstrip("/")


def announce(message):
    print(message, flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write(message + "\n\n")


def cipher():
    key = base64.urlsafe_b64encode(hashlib.sha256(TOKEN.encode("utf-8")).digest())
    return Fernet(key)


def load_current_token():
    if not TOKEN_FILE.exists():
        return TOKEN
    try:
        return cipher().decrypt(TOKEN_FILE.read_bytes().strip()).decode("utf-8")
    except (InvalidToken, UnicodeError) as exc:
        raise RuntimeError("Saved token cannot be decrypted; check META_ACCESS_TOKEN") from exc


def refresh_token(current_token):
    url = "https://graph.instagram.com/refresh_access_token?" + urlencode({
        "grant_type": "ig_refresh_token",
        "access_token": current_token,
    })
    try:
        with urlopen(Request(url, headers={"User-Agent": "certiPass-instagram-publisher/1.0"}), timeout=35) as response:
            result = json.load(response)
            if not result.get("access_token"):
                raise RuntimeError("Meta returned no refreshed token")
            return result["access_token"]
    except HTTPError as exc:
        raise RuntimeError(f"Meta token refresh failed (HTTP {exc.code}); reauthorize before it expires") from exc


def request(path, params=None, method="GET"):
    url = f"{GRAPH}/{path.lstrip('/')}"
    body = None
    if method == "POST":
        body = urlencode(params or {}).encode("utf-8")
    elif params:
        url += "?" + urlencode(params)
    req = Request(url, data=body, method=method,
                  headers={"Authorization": f"Bearer {TOKEN}",
                           "User-Agent": "certiPass-instagram-publisher/1.0"})
    try:
        with urlopen(req, timeout=35) as response:
            return json.load(response)
    except HTTPError as exc:
        try:
            error = json.loads(exc.read()).get("error", {})
            detail = f"{error.get('message', 'Meta request failed')} (code {error.get('code', exc.code)})"
        except (ValueError, UnicodeError):
            detail = f"HTTP {exc.code}"
        raise RuntimeError(detail) from exc
    except URLError as exc:
        raise RuntimeError(f"Meta connection failed: {exc.reason}") from exc


def image_url(day, number):
    return f"{MEDIA_BASE_URL}/day-{day:03}-{number:02}.jpg"


def check_public_image(url):
    req = Request(url, headers={"User-Agent": "certiPass-instagram-publisher/1.0"})
    try:
        with urlopen(req, timeout=35) as response:
            content_type = response.headers.get("Content-Type", "").split(";")[0]
            if content_type not in ("image/jpeg", "image/jpg"):
                raise RuntimeError(f"Image URL returned {content_type or 'no content type'}: {url}")
            if not response.read(16).startswith(b"\xff\xd8\xff"):
                raise RuntimeError(f"Image URL did not return a JPEG: {url}")
    except HTTPError as exc:
        raise RuntimeError(f"Image URL returned HTTP {exc.code}: {url}") from exc


def recent_captions():
    # Fail closed if the read fails; publishing without this check could duplicate a post.
    result = request(f"{IG_USER_ID}/media", {"fields": "id,caption", "limit": 100})
    return {item.get("caption", "") for item in result.get("data", [])}


def wait_until_ready(container_id):
    for attempt in range(18):
        result = request(container_id, {"fields": "status_code,status"})
        status = result.get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Meta media container status: {status}")
        time.sleep(5 if attempt < 5 else 10)
    raise RuntimeError("Meta media container was not ready in time")


def publish_carousel(day, caption):
    urls = [image_url(day, number) for number in (1, 2)]
    for url in urls:
        check_public_image(url)
    children = []
    for url in urls:
        result = request(f"{IG_USER_ID}/media", {
            "image_url": url,
            "is_carousel_item": "true",
        }, method="POST")
        children.append(result["id"])
    parent = request(f"{IG_USER_ID}/media", {
        "media_type": "CAROUSEL",
        "children": ",".join(children),
        "caption": caption,
    }, method="POST")
    wait_until_ready(parent["id"])
    try:
        result = request(f"{IG_USER_ID}/media_publish", {
            "creation_id": parent["id"]
        }, method="POST")
    except RuntimeError as exc:
        # An interrupted response may follow a successful publish. Never retry blindly.
        raise RuntimeError(f"Publish result uncertain; check Instagram before retrying. {exc}") from exc
    return result["id"]


def save_state(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def publish_story(day, entry, state):
    if entry.get("story_id"):
        announce(f"Story for day {day:02} is already published: {entry['story_id']}")
        return
    if entry.get("story_status") == "uncertain":
        raise RuntimeError(f"Story for day {day:02} may already be live; check Instagram before retrying")
    url = image_url(day, 1)
    check_public_image(url)
    container = request(f"{IG_USER_ID}/media", {
        "media_type": "STORIES",
        "image_url": url,
    }, method="POST")
    wait_until_ready(container["id"])
    # Persist before publishing: an interrupted response must never cause an automatic duplicate.
    entry["story_status"] = "uncertain"
    save_state(state)
    try:
        result = request(f"{IG_USER_ID}/media_publish", {
            "creation_id": container["id"]
        }, method="POST")
    except RuntimeError as exc:
        raise RuntimeError(f"Story result uncertain; check Instagram before retrying. {exc}") from exc
    entry["story_id"] = result["id"]
    entry["story_status"] = "published"
    save_state(state)
    announce(f"Published Story for day {day:02}: media ID {result['id']}")


def main():
    global TOKEN
    if not TOKEN or not IG_USER_ID or not MEDIA_BASE_URL:
        raise RuntimeError("Set META_ACCESS_TOKEN, IG_USER_ID and MEDIA_BASE_URL in GitHub settings")
    posts = json.loads(MANIFEST.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8"))
    today = datetime.now(TZ).date().isoformat()
    original_token = TOKEN
    TOKEN = load_current_token()
    if state.get("token_refreshed_at"):
        token_age = (date.fromisoformat(today) - date.fromisoformat(state["token_refreshed_at"])).days
        if token_age >= 30:
            TOKEN = refresh_token(TOKEN)
            TOKEN_FILE.write_bytes(Fernet(base64.urlsafe_b64encode(
                hashlib.sha256(original_token.encode("utf-8")).digest()
            )).encrypt(TOKEN.encode("utf-8")) + b"\n")
            state["token_refreshed_at"] = today
            save_state(state)
            announce("Instagram access token refreshed securely.")
    else:
        state["token_refreshed_at"] = today
        save_state(state)
    if state.get("last_published_date") == today:
        entry = state["history"][-1]
        if entry["date"] != today:
            raise RuntimeError("Publishing history does not match today's date")
        if entry.get("story_id"):
            announce(f"Carousel and Story already posted on {today} (Chișinău). Nothing to do.")
            return
        publish_story(int(entry["day"]), entry, state)
        return
    day = int(state["next_day"])
    if day > len(posts):
        announce("All 90 carousels have been posted. Nothing to do.")
        return
    post = posts[day - 1]
    if post["day"] != day:
        raise RuntimeError("Post manifest is out of order")
    caption = post["caption"]
    if caption in recent_captions():
        announce(f"Day {day:02} is already visible on Instagram; recording it without reposting.")
        media_id = "already-present"
    else:
        media_id = publish_carousel(day, caption)
        announce(f"Published day {day:02} on Instagram: media ID {media_id}")
    state["next_day"] = day + 1
    state["last_published_date"] = today
    entry = {"day": day, "date": today, "media_id": media_id}
    state.setdefault("history", []).append(entry)
    save_state(state)
    publish_story(day, entry, state)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, KeyError, ValueError) as exc:
        announce(f"Publishing stopped: {exc}")
        sys.exit(1)
