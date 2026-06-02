"""Shared fixtures. Tests run on stdlib + pytest only (no optional deps)."""

import pytest

from applykit.config import parse_config
from applykit.db import connect


@pytest.fixture
def config():
    """A small, valid config built from a dict (no YAML/file IO needed)."""
    return parse_config(
        {
            "profile": {"name": "Test User", "remote_preference": "remote"},
            "scoring": {
                "dimensions": [
                    {"key": "role_fit", "label": "Role Fit", "weight": 60},
                    {"key": "technical_match", "label": "Technical Match", "weight": 40},
                ]
            },
            "companies": [
                {"name": "Dream Co", "careers_url": "https://dream.example/careers",
                 "tier": "dream", "craft_threshold": "B"},
                {"name": "Target Co", "careers_url": "https://target.example/careers",
                 "tier": "target"},
            ],
            "pipeline": {"score_cap": 10, "craft_threshold": "B+", "craft_cap": 2},
        }
    )


@pytest.fixture
def default_config():
    """A config using the ten default dimensions."""
    return parse_config({})


@pytest.fixture
def conn():
    """An in-memory database with the schema initialised."""
    c = connect(":memory:")
    try:
        yield c
    finally:
        c.close()
