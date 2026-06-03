"""
One-liner .env loader for the collector package.

Usage:
  from lib.env_loader import load_env; load_env()
  # or simply:
  import lib.env_loader  # auto-loads on import

Will silently skip if no .env file exists next to this module.
Will NOT override already-set environment variables.
"""

import os
from pathlib import Path

_COLLECTOR_DIR = Path(__file__).resolve().parent.parent
_DOTENV_PATH = _COLLECTOR_DIR / ".env"

_LOADED = False


def load_env():
    """Load .env from collector/ directory into os.environ (once)."""
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    if not _DOTENV_PATH.exists():
        return
    with open(_DOTENV_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if value and not os.environ.get(key):
                os.environ[key] = value


# Auto-load on import
load_env()
