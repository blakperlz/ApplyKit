import pytest

from applykit.evaluator import (
    EvaluationError,
    build_prompt,
    parse_response,
)


def test_build_prompt_includes_dimensions_and_jd(config):
    prompt = build_prompt("Lead the security team", config,
                          profile_narrative="I lead teams.")
    assert "role_fit" in prompt
    assert "technical_match" in prompt
    assert "Lead the security team" in prompt
    assert "I lead teams." in prompt


def test_build_prompt_includes_calibration_examples(config):
    prompt = build_prompt("JD", config,
                          calibration_examples=["Acme: user disagreed — too junior"])
    assert "CALIBRATION" in prompt
    assert "too junior" in prompt


def test_parse_response_plain_json(config):
    raw = """{"company": "Acme", "role": "Director",
        "dimensions": {
            "role_fit": {"score": 90, "explanation": "great"},
            "technical_match": {"score": 70, "explanation": "ok"}}}"""
    ev = parse_response(raw, config)
    assert ev.company == "Acme"
    assert ev.role == "Director"
    # (90*60 + 70*40)/100 = 82
    assert ev.overall_score == 82.0
    assert ev.grade == "B"
    assert ev.dimension_scores[0].explanation == "great"


def test_parse_response_tolerates_fences_and_prose(config):
    raw = "Here you go:\n```json\n" \
          '{"company":"X","role":"Y","dimensions":' \
          '{"role_fit":{"score":100},"technical_match":{"score":100}}}\n```\nDone.'
    ev = parse_response(raw, config)
    assert ev.overall_score == 100.0
    assert ev.grade == "A"


def test_parse_response_clamps_out_of_range(config):
    raw = '{"company":"X","role":"Y","dimensions":' \
          '{"role_fit":{"score":150},"technical_match":{"score":-20}}}'
    ev = parse_response(raw, config)
    scores = {d.key: d.score for d in ev.dimension_scores}
    assert scores["role_fit"] == 100.0
    assert scores["technical_match"] == 0.0


def test_parse_response_missing_dimension_raises(config):
    raw = '{"company":"X","role":"Y","dimensions":{"role_fit":{"score":90}}}'
    with pytest.raises(EvaluationError):
        parse_response(raw, config)


def test_parse_response_no_json_raises(config):
    with pytest.raises(EvaluationError):
        parse_response("no json here", config)


def test_parse_response_accepts_bare_numbers(config):
    raw = '{"company":"X","role":"Y","dimensions":{"role_fit":80,"technical_match":80}}'
    ev = parse_response(raw, config)
    assert ev.overall_score == 80.0
