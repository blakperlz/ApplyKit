import pytest

from applykit.config import ConfigError, parse_config


def test_defaults_when_empty():
    cfg = parse_config({})
    assert len(cfg.dimensions) == 10  # ten PRD defaults
    assert cfg.pipeline["score_cap"] == 25
    assert cfg.pipeline["craft_threshold"] == "B+"
    assert cfg.dimension_weight_total() == 100.0


def test_custom_dimensions(config):
    keys = [d.key for d in config.dimensions]
    assert keys == ["role_fit", "technical_match"]


def test_company_craft_threshold_override(config):
    assert config.company_craft_threshold("Dream Co") == "B"      # per-company
    assert config.company_craft_threshold("Target Co") == "B+"    # falls back
    assert config.company_craft_threshold("Unknown") == "B+"


def test_rejects_dimension_without_weight():
    with pytest.raises(ConfigError):
        parse_config({"scoring": {"dimensions": [{"key": "x"}]}})


def test_rejects_duplicate_dimension_keys():
    with pytest.raises(ConfigError):
        parse_config({"scoring": {"dimensions": [
            {"key": "x", "weight": 1}, {"key": "x", "weight": 1}]}})


def test_rejects_bad_company_tier():
    with pytest.raises(ConfigError):
        parse_config({"companies": [
            {"name": "X", "careers_url": "http://x", "tier": "nonsense"}]})


def test_rejects_company_without_url():
    with pytest.raises(ConfigError):
        parse_config({"companies": [{"name": "X"}]})


def test_rejects_nonpositive_score_cap():
    with pytest.raises(ConfigError):
        parse_config({"pipeline": {"score_cap": 0}})
