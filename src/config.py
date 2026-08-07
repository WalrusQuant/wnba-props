"""Loads config.yaml once, so every module reads tunables the same way."""

from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

_config: dict | None = None


def load_config() -> dict:
    global _config
    if _config is None:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            _config = yaml.safe_load(f)
    return _config
