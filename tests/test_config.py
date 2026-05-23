"""Tests for Pydantic config validation."""

import pytest
import yaml

from content_agent.config import AppConfig, load_config


def test_config_loads_from_dict():
    raw = {
        "obsidian": {"vault_path": "/tmp/vault"},
        "state_dir": "/tmp/data",
    }
    cfg = AppConfig(**raw)
    assert cfg.obsidian.vault_path == "/tmp/vault"
    assert cfg.llm.writer_model == "claude-sonnet-4-6"
    assert cfg.llm.max_tokens == 4096
    assert cfg.schedule.timezone == "Europe/London"
    assert cfg.images.brand_colors.primary == "#1a1a2e"


def test_config_defaults():
    raw = {"obsidian": {"vault_path": "~/vault"}}
    cfg = AppConfig(**raw)
    assert cfg.state_dir == "data"
    assert cfg.day_counter_start == 1
    assert cfg.about_me == "AboutMe.md"
    assert cfg.seo.default_hashtags["twitter"] == ["cybersecurity", "infosec", "AI"]
    assert cfg.video.width == 1080
    assert cfg.video.height == 1920


def test_config_posting_time_validation():
    raw = {
        "obsidian": {"vault_path": "~/vault"},
        "seo": {"posting_times": {"twitter": "9am"}},
    }
    with pytest.raises(ValueError, match="Invalid time format"):
        AppConfig(**raw)


def test_config_schedule_time_validation():
    raw = {
        "obsidian": {"vault_path": "~/vault"},
        "schedule": {"daily_time": "7:00"},
    }
    with pytest.raises(ValueError, match="Invalid time format"):
        AppConfig(**raw)


def test_config_valid_posting_times():
    raw = {
        "obsidian": {"vault_path": "~/vault"},
        "seo": {"posting_times": {"twitter": "09:00", "linkedin": "08:30"}},
        "schedule": {"daily_time": "06:30"},
    }
    cfg = AppConfig(**raw)
    assert cfg.seo.posting_times["twitter"] == "09:00"
    assert cfg.schedule.daily_time == "06:30"


def test_config_file_not_found():
    with pytest.raises(FileNotFoundError, match="not found"):
        load_config("/nonexistent/config.yaml")


def test_config_from_yaml(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump({
        "obsidian": {"vault_path": "/tmp/vault", "notes_glob": "daily/*.md"},
        "llm": {"max_tokens": 8192},
        "state_dir": str(tmp_path / "data"),
    }))
    cfg = load_config(cfg_file)
    assert cfg.obsidian.vault_path == "/tmp/vault"
    assert cfg.obsidian.notes_glob == "daily/*.md"
    assert cfg.llm.max_tokens == 8192


def test_config_brand_colors():
    raw = {
        "obsidian": {"vault_path": "~/vault"},
        "images": {
            "brand_colors": {
                "primary": "#000000",
                "highlight": "#ff0000",
            },
        },
    }
    cfg = AppConfig(**raw)
    assert cfg.images.brand_colors.primary == "#000000"
    assert cfg.images.brand_colors.highlight == "#ff0000"
    assert cfg.images.brand_colors.secondary == "#16213e"  # default
