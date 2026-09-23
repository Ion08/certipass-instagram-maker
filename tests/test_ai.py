from datetime import date
import json
from pathlib import Path

import pytest

from certipass_instagram.ai import CodexConfig, CodexGenerator, GenerationError, _draft_from_json, _validate_draft


def valid_payload(url="https://docs.python.org/3/tutorial/floatingpoint.html"):
    return {
        "pillar": "useful_it", "language": "ro", "topic": "Punctul flotant",
        "hook": "De ce 0.1 + 0.2 nu este exact 0.3?", "caption": "Calculul are o explicație.",
        "visual_family": "editorial", "facts": ["Unele fracții zecimale nu au reprezentare binară exactă."],
        "sources": [{"title": "Python docs", "url": url, "accessed_at": "2026-09-23T00:00:00+00:00",
                     "supports": "binary floating point representation"}],
        "slides": [{"headline": f"Cadru {i}", "body": f"Explicația numărul {i}.",
                    "image_prompt": "Bright editorial illustration about binary number systems.",
                    "alt_text": f"Ilustrație educațională {i}"} for i in range(1, 5)],
    }


def test_draft_parser_and_validator_enforce_facts_sources_and_static_slides():
    payload = valid_payload()
    draft = _draft_from_json(payload, date(2026, 9, 23))
    _validate_draft(draft, [{"url": payload["sources"][0]["url"]}])
    assert draft.id == "post-2026-09-23"
    assert draft.post_type == "CAROUSEL"
    payload["sources"][0]["url"] = "https://made-up.example/claim"
    with pytest.raises(ValueError, match="not supplied"):
        _validate_draft(_draft_from_json(payload, draft.publish_date), [{"url": "https://docs.python.org/3/tutorial/floatingpoint.html"}])


def test_facts_without_sources_are_rejected():
    payload = valid_payload()
    payload["sources"] = []
    with pytest.raises(ValueError, match="need sources"):
        _validate_draft(_draft_from_json(payload, date(2026, 9, 23)), [])


def test_single_slide_is_a_static_image_post():
    payload = valid_payload()
    payload["slides"] = payload["slides"][:1]
    draft = _draft_from_json(payload, date(2026, 9, 23))
    _validate_draft(draft, [{"url": payload["sources"][0]["url"]}])
    assert draft.post_type == "IMAGE"


def test_bac_claim_requires_current_official_ance_reference():
    payload = valid_payload()
    payload["topic"] = "Nota la Bacalaureat"
    draft = _draft_from_json(payload, date(2026, 9, 23))
    with pytest.raises(ValueError, match="ANCE"):
        _validate_draft(draft, [{"url": payload["sources"][0]["url"]}])


def test_generator_removes_platform_api_keys_and_reports_no_raw_stderr(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "do-not-forward")
    evidence = [{"url": "https://docs.python.org/3/tutorial/floatingpoint.html", "title": "Python docs",
                 "accessed_at": "now", "text": "Binary floating-point arithmetic."}]

    def runner(command, **kwargs):
        assert "do-not-forward" not in kwargs["env"].get("OPENAI_API_KEY", "")
        assert "--ephemeral" not in command and "--sandbox" in command and "read-only" in command
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps(valid_payload(), ensure_ascii=False), encoding="utf-8")
        class Result:
            returncode = 0
            stderr = ""
            stdout = ""
        return Result()

    result = CodexGenerator(CodexConfig(executable="codex"), runner=runner).generate(
        day=date(2026, 9, 23), evidence=evidence)
    assert result.language == "ro"


def test_generator_sanitizes_failure_output():
    def runner(*args, **kwargs):
        class Result:
            returncode = 1
            stderr = "private token diagnostic"
            stdout = ""
        return Result()
    with pytest.raises(GenerationError) as exc:
        CodexGenerator(runner=runner).generate(day=date(2026, 9, 23), evidence=[])
    assert "private token diagnostic" not in str(exc.value)
