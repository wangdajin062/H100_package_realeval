"""Tests for config/schema.py and config loader."""
from __future__ import annotations

import pytest

from config import load_config
from config.schema import CONFIG_SCHEMA, ensure_valid_config, validate_config


def _leaf_keys(d: dict, prefix: str = "") -> set[str]:
    """Return dotted leaf keys (non-dict values) present in a nested dict."""
    keys = set()
    for k, v in d.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.update(_leaf_keys(v, path))
        else:
            keys.add(path)
    return keys


def test_default_config_loads_and_validates():
    cfg = load_config()
    ensure_valid_config(cfg)


def test_h100_config_loads_and_validates():
    cfg = load_config("config/h100.yaml")
    ensure_valid_config(cfg)
    assert cfg["hardware"].get("precision") == "bf16"


def test_all_yaml_keys_have_schema():
    """Every leaf key in config/experiments.yaml must be declared in CONFIG_SCHEMA."""
    cfg = load_config()
    yaml_keys = _leaf_keys(cfg)
    # `students` is a dynamic table of checkpoint paths; do not require every variant.
    yaml_keys = {k for k in yaml_keys if not k.startswith("students.")}
    schema_keys = set(CONFIG_SCHEMA)
    missing = yaml_keys - schema_keys
    # Internal runtime keys are not part of YAML and should not be required.
    missing = {k for k in missing if not k.startswith("_")}
    assert not missing, f"YAML keys missing from CONFIG_SCHEMA: {sorted(missing)}"


def test_invalid_quantize_rejected():
    cfg = load_config()
    cfg["training"]["quantize"] = "int5"
    issues = validate_config(cfg)
    assert any("quantize" in i for i in issues)


def test_invalid_data_source_rejected():
    cfg = load_config()
    cfg["data"]["source"] = "unknown"
    issues = validate_config(cfg)
    assert any("data.source" in i for i in issues)
