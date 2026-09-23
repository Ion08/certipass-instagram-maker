import requests

from certipass_instagram.research import SOURCES, fetch_snapshot


class Response:
    status_code = 200
    content = b"unused"
    text = "<html><script>ignore this</script><p>Current reference text</p></html>"
    def raise_for_status(self): pass


def test_research_only_fetches_allowlisted_sources_and_omits_failed_pages():
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        if url.endswith("/about"):
            raise requests.ConnectionError("temporary failure")
        return Response()
    pages = fetch_snapshot(get=get)
    assert calls == [url for _, url in SOURCES]
    assert all("ignore this" not in page.text for page in pages)
    assert all("Current reference text" in page.text for page in pages)
