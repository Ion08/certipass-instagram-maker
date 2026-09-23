from pathlib import Path


def test_scheduled_workflow_is_off_until_user_enables_private_drafts():
    workflow = Path(".github/workflows/daily-draft.yml").read_text(encoding="utf-8")
    assert 'cron: "23 7 * * *"' in workflow
    assert 'timezone: "Europe/Chisinau"' in workflow
    assert "vars.ENABLE_DAILY_DRAFTS == 'true'" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow


def test_workflow_never_publishes_to_instagram_or_prints_auth():
    workflow = Path(".github/workflows/daily-draft.yml").read_text(encoding="utf-8")
    assert "python -m certipass_instagram.cli draft" in workflow
    assert "python -m certipass_instagram.cli publish" not in workflow
    assert "instagram.com" not in workflow
    assert "contents: read" in workflow
    assert "CODEX_AUTH_JSON" in workflow
