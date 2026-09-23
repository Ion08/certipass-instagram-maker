from datetime import date
import json
from pathlib import Path

import pytest

from certipass_instagram.ai import (CodexConfig, CodexGenerator, GenerationError, _daily_set_prompt,
                                    _draft_from_json, _validate_daily_set, _validate_draft)


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


def test_daily_set_requires_each_type_unique_topic_character_and_motif():
    evidence = [
        {"url": "https://docs.python.org/3/tutorial/floatingpoint.html", "title": "Python docs", "accessed_at": "today"},
        {"url": "https://www.certipass.md/", "title": "certiPass", "accessed_at": "today"},
    ]
    base = valid_payload()
    base["facts"] = []
    base["sources"] = []
    base["slides"] = base["slides"][:1]
    posts = []
    for content_type, topic in (("meme", "Python operator joke"),
                                ("educational", "Python exponents"),
                                ("informative", "How to study with practice")):
        item = {**base, "content_type": content_type, "topic": topic,
                "visual_family": "pastel-editorial", "character": f"student {content_type}",
                "visual_motif": f"motif {content_type}"}
        item["hook"] = f"Distinct hook for {content_type}"
        item["caption"] = f"Distinct caption for {content_type}"
        item["slides"] = [{**base["slides"][0], "headline": f"{content_type} post"}]
        posts.append(_draft_from_json(item, date(2026, 9, 23)))
    _validate_daily_set(posts, evidence)
    assert {draft.id for draft in posts} == {
        "post-2026-09-23-meme", "post-2026-09-23-educational", "post-2026-09-23-informative"
    }
    posts[2] = _draft_from_json({**base, "content_type": "educational", "character": "another",
                                 "visual_motif": "another", "slides": base["slides"][:1]}, date(2026, 9, 23))
    with pytest.raises(ValueError, match="one meme"):
        _validate_daily_set(posts, evidence)


def test_daily_prompt_carries_brand_style_and_rotation_history():
    prompt = _daily_set_prompt(date(2026, 9, 23), [], [{"topic": "past topic", "character": "past student"}])
    assert "meme, educational, informative" in prompt
    assert "lavender" in prompt and "past student" in prompt
    assert "vary topics, hooks" in prompt
