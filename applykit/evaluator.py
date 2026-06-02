"""Scoring engine: build the evaluation prompt, parse the response, optionally call the API.

The prompt builder and response parser are pure and fully unit-testable. The
API caller is optional — in Cowork mode the SKILL.md prompt does the scoring and
writes results directly; in CLI mode this module calls the Anthropic API.
"""

from __future__ import annotations

import json
import re
from typing import Optional, Sequence

from .config import Config
from .models import Dimension, DimensionScore, Evaluation


class EvaluationError(Exception):
    """Raised when an evaluator response cannot be parsed into scores."""


def build_prompt(
    jd_text: str,
    config: Config,
    *,
    profile_narrative: str = "",
    calibration_examples: Optional[Sequence[str]] = None,
) -> str:
    """Construct the scoring prompt for a single JD.

    Includes the user's profile, the configured dimensions with weights, the JD,
    and any recent disagreement examples used as few-shot calibration (ADR-001
    Tension 5: prompt calibration is in the MVP).
    """
    dims = config.dimensions
    dim_lines = "\n".join(
        f"- {d.key} ({d.label}, weight {d.weight:g}%): {d.description}".rstrip()
        for d in dims
    )

    profile_blob = json.dumps(config.profile, indent=2) if config.profile else "{}"

    calibration_block = ""
    if calibration_examples:
        joined = "\n".join(f"- {ex}" for ex in calibration_examples)
        calibration_block = (
            "\nPAST CALIBRATION (cases where the user disagreed with a prior "
            "score — learn from these):\n" + joined + "\n"
        )

    keys = [d.key for d in dims]
    schema_hint = ", ".join(f'"{k}": {{"score": <0-100>, "explanation": "<why>"}}' for k in keys)

    return f"""You are ApplyKit's scoring engine. Evaluate one job description against the
user's profile across the configured dimensions. Be calibrated and specific.

USER PROFILE (structured):
{profile_blob}

USER PROFILE (narrative):
{profile_narrative or "(none provided)"}

SCORING DIMENSIONS (score each 0-100):
{dim_lines}
{calibration_block}
JOB DESCRIPTION:
\"\"\"
{jd_text}
\"\"\"

Return ONLY a JSON object, no prose, in exactly this shape:
{{
  "company": "<company name or 'Unknown'>",
  "role": "<role title or 'Unknown'>",
  "dimensions": {{ {schema_hint} }}
}}
Every dimension key listed above must be present. Scores are integers 0-100."""


def parse_response(
    raw: str,
    config: Config,
    *,
    source: str = "",
    raw_jd: str = "",
) -> Evaluation:
    """Parse a model JSON response into an :class:`Evaluation`.

    Tolerant of surrounding prose and ```json fences. Computes the weighted
    overall score and grade from the per-dimension scores and configured weights.
    """
    data = _extract_json(raw)
    dim_map = data.get("dimensions")
    if not isinstance(dim_map, dict):
        raise EvaluationError("Response is missing a 'dimensions' object.")

    by_key = {d.key: d for d in config.dimensions}
    scores: list[DimensionScore] = []
    missing: list[str] = []
    for key, dim in by_key.items():
        entry = dim_map.get(key)
        if entry is None:
            missing.append(key)
            continue
        scores.append(_dimension_score(dim, entry))

    if missing:
        raise EvaluationError(f"Response missing dimensions: {', '.join(missing)}")

    return Evaluation.from_dimension_scores(
        company=str(data.get("company", "Unknown")) or "Unknown",
        role=str(data.get("role", "Unknown")) or "Unknown",
        dimension_scores=scores,
        source=source,
        raw_jd=raw_jd,
    )


def _dimension_score(dim: Dimension, entry) -> DimensionScore:
    if isinstance(entry, dict):
        raw_score = entry.get("score", 0)
        explanation = str(entry.get("explanation", ""))
    else:  # allow a bare number
        raw_score = entry
        explanation = ""
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        raise EvaluationError(f"Dimension '{dim.key}' has a non-numeric score: {raw_score!r}")
    score = max(0.0, min(100.0, score))
    return DimensionScore(
        key=dim.key,
        label=dim.label,
        score=score,
        weight=dim.weight,
        explanation=explanation,
    )


def _extract_json(raw: str) -> dict:
    """Pull the first JSON object out of a model response, tolerating fences/prose."""
    if not raw or not raw.strip():
        raise EvaluationError("Empty evaluator response.")
    text = raw.strip()

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        candidate = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise EvaluationError("No JSON object found in evaluator response.")
        candidate = text[start : end + 1]

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise EvaluationError(f"Invalid JSON in evaluator response: {exc}") from exc


def evaluate(
    jd_text: str,
    config: Config,
    *,
    profile_narrative: str = "",
    calibration_examples: Optional[Sequence[str]] = None,
    source: str = "",
    model: str = "claude-sonnet-4-5",
    api_key: Optional[str] = None,
) -> Evaluation:
    """Score a JD by calling the Anthropic API (CLI mode).

    Requires the ``anthropic`` SDK (the ``[standalone]`` extra). In Cowork mode
    you do not call this — the skill prompt scores directly.
    """
    try:
        import anthropic
    except ImportError as exc:
        raise EvaluationError(
            "CLI scoring requires the anthropic SDK. Install with "
            "`pip install applykit[standalone]`, or run scoring in Cowork mode."
        ) from exc

    prompt = build_prompt(
        jd_text,
        config,
        profile_narrative=profile_narrative,
        calibration_examples=calibration_examples,
    )
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
    return parse_response(raw, config, source=source, raw_jd=jd_text)
