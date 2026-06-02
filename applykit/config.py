"""Single-file YAML config loader with section validation.

Per ADR-001 Tension 6, all configuration lives in one ``config.yml`` with four
sections: ``profile``, ``scoring``, ``companies``, and ``pipeline``. This module
loads it, applies defaults, and validates the important invariants (e.g. that
scoring dimensions are well-formed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .models import CompanyTier, Dimension


class ConfigError(Exception):
    """Raised when a config file is missing, malformed, or fails validation."""


# Default scoring dimensions (PRD section 4, Step 2). Weights are percentages
# and sum to 100. Users override these in their own config.yml.
DEFAULT_DIMENSIONS: list[Dimension] = [
    Dimension("role_fit", "Role Fit", 20.0,
              "Title, scope, seniority, responsibility alignment"),
    Dimension("technical_match", "Technical Match", 15.0,
              "Stack overlap, required vs nice-to-have skills"),
    Dimension("leadership_match", "Leadership Match", 15.0,
              "Team size, org scope, management expectations"),
    Dimension("mission_alignment", "Mission Alignment", 10.0,
              "Company mission vs user's values"),
    Dimension("growth_potential", "Growth Potential", 10.0,
              "Career trajectory, learning, promotion signals"),
    Dimension("compensation_signal", "Compensation Signal", 10.0,
              "Salary range or inferred level vs target"),
    Dimension("location_remote", "Location/Remote", 5.0,
              "Remote/hybrid/onsite fit"),
    Dimension("security_domain", "Security Domain", 5.0,
              "Cybersecurity, AI safety, trust & safety relevance"),
    Dimension("government_adjacency", "Government Adjacency", 5.0,
              "Public sector, clearance, defense connection"),
    Dimension("culture_signal", "Culture Signal", 5.0,
              "Tone, values, work-life signals, red flags"),
]

DEFAULT_PIPELINE = {
    "score_cap": 25,        # max JDs evaluated per run
    "craft_threshold": "B+",  # min grade for automatic material generation
    "craft_cap": 5,         # max materials generated per run
    "schedule": "daily",    # informational; the scheduler lives in Cowork
    "calibration_examples": 5,  # disagreements injected into the eval prompt
    "calibration_min_sample": 5,  # disagreements before suggesting a reweight
}


@dataclass
class Company:
    name: str
    careers_url: str
    tier: CompanyTier = CompanyTier.TARGET
    check_frequency: str = "daily"
    craft_threshold: Optional[str] = None  # per-company override


@dataclass
class Config:
    """Parsed, validated configuration."""

    profile: dict[str, Any] = field(default_factory=dict)
    dimensions: list[Dimension] = field(default_factory=list)
    companies: list[Company] = field(default_factory=list)
    pipeline: dict[str, Any] = field(default_factory=dict)
    path: Optional[Path] = None

    def dimension_weight_total(self) -> float:
        return sum(d.weight for d in self.dimensions)

    def company_craft_threshold(self, company_name: str) -> str:
        """Resolve the craft threshold for a company, honouring per-company override."""
        for c in self.companies:
            if c.name.lower() == company_name.lower() and c.craft_threshold:
                return c.craft_threshold
        return self.pipeline.get("craft_threshold", DEFAULT_PIPELINE["craft_threshold"])


def _require_yaml():
    try:
        import yaml  # noqa: F401
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ConfigError(
            "PyYAML is required to load config files. Install with `pip install pyyaml`."
        ) from exc
    return yaml


def parse_config(data: dict[str, Any], path: Optional[Path] = None) -> Config:
    """Validate and normalise a raw config dict into a Config.

    Kept separate from file IO so it is trivially unit-testable.
    """
    if not isinstance(data, dict):
        raise ConfigError("Config root must be a mapping with named sections.")

    # ---- scoring ----
    scoring = data.get("scoring") or {}
    raw_dims = scoring.get("dimensions")
    if raw_dims:
        dimensions = []
        for i, d in enumerate(raw_dims):
            if "key" not in d or "weight" not in d:
                raise ConfigError(
                    f"scoring.dimensions[{i}] requires 'key' and 'weight'."
                )
            dimensions.append(
                Dimension(
                    key=str(d["key"]),
                    label=str(d.get("label", d["key"])),
                    weight=float(d["weight"]),
                    description=str(d.get("description", "")),
                )
            )
    else:
        dimensions = list(DEFAULT_DIMENSIONS)

    if not dimensions:
        raise ConfigError("At least one scoring dimension is required.")
    if any(d.weight < 0 for d in dimensions):
        raise ConfigError("Dimension weights must be non-negative.")
    if sum(d.weight for d in dimensions) <= 0:
        raise ConfigError("Dimension weights must sum to a positive number.")

    keys = [d.key for d in dimensions]
    if len(keys) != len(set(keys)):
        raise ConfigError("Duplicate dimension keys are not allowed.")

    # ---- companies ----
    companies = []
    for i, c in enumerate(data.get("companies") or []):
        if "name" not in c or "careers_url" not in c:
            raise ConfigError(
                f"companies[{i}] requires 'name' and 'careers_url'."
            )
        tier_raw = str(c.get("tier", "target")).lower()
        try:
            tier = CompanyTier(tier_raw)
        except ValueError:
            raise ConfigError(
                f"companies[{i}].tier '{tier_raw}' must be one of "
                f"{[t.value for t in CompanyTier]}."
            )
        companies.append(
            Company(
                name=str(c["name"]),
                careers_url=str(c["careers_url"]),
                tier=tier,
                check_frequency=str(c.get("check_frequency", "daily")),
                craft_threshold=c.get("craft_threshold"),
            )
        )

    # ---- pipeline ----
    pipeline = dict(DEFAULT_PIPELINE)
    pipeline.update(data.get("pipeline") or {})
    if int(pipeline["score_cap"]) <= 0:
        raise ConfigError("pipeline.score_cap must be a positive integer.")
    if int(pipeline["craft_cap"]) < 0:
        raise ConfigError("pipeline.craft_cap must be >= 0.")

    return Config(
        profile=dict(data.get("profile") or {}),
        dimensions=dimensions,
        companies=companies,
        pipeline=pipeline,
        path=path,
    )


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*. Lists replace, not append."""
    merged = dict(base)
    for key, val in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = _deep_merge(merged[key], val)
        else:
            merged[key] = val
    return merged


def load_config(path: str | Path) -> Config:
    """Load and validate config, merging defaults.yml into config.yml.

    If config/defaults.yml exists alongside the given path, it is loaded
    first as the base layer. The personal config.yml is then deep-merged on
    top so its values win. This lets structural settings (scoring dimensions,
    pipeline caps) live in a tracked file while personal data stays gitignored.
    """
    yaml = _require_yaml()
    p = Path(path)
    if not p.exists():
        raise ConfigError(
            f"Config not found at {p}. Copy config/config.yml.example to "
            f"config/config.yml and fill it in."
        )

    # Load tracked defaults if present
    defaults_path = p.parent / "defaults.yml"
    base: dict = {}
    if defaults_path.exists():
        with defaults_path.open("r", encoding="utf-8") as fh:
            base = yaml.safe_load(fh) or {}

    # Load personal config
    with p.open("r", encoding="utf-8") as fh:
        personal = yaml.safe_load(fh) or {}

    data = _deep_merge(base, personal) if base else personal
    return parse_config(data, path=p)
