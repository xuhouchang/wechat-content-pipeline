#!/usr/bin/env python3
"""
Centralized model configuration for the collector pipeline.

All scripts should import `get_model()` from here instead of defining
their own defaults or referencing environment variables directly.

Usage:
    from lib.models import get_model
    model = get_model("writing")

Environment variable overrides:
    MODEL_WRITING      — 公众号写作 (default: openai/gpt-5.4)
    MODEL_POLISH       — 润色       (default: openai/gpt-5.4)
    MODEL_CASE         — 案例拆解   (default: deepseek/deepseek-chat)
    MODEL_FILTER       — 素材过滤   (default: deepseek/deepseek-chat)
    MODEL_SYNTHESIS    — 周度整合   (default: openai/gpt-5.4)
    MODEL_FRAMEWORK    — 框架文章   (default: openai/gpt-5.4)

Legacy:
    WRITING_MODEL env var is still respected as a blanket fallback.
    DEFAULT_WRITING_MODEL in lib/llm.py remains for backward compat
    but new code should prefer get_model().
"""

import os
from typing import Optional

_MODELS = {
    "writing":    os.environ.get("MODEL_WRITING",    "openai/gpt-5.4"),
    "polish":     os.environ.get("MODEL_POLISH",     "openai/gpt-5.4"),
    "case":       os.environ.get("MODEL_CASE",       "deepseek/deepseek-chat"),
    "filter":     os.environ.get("MODEL_FILTER",     "deepseek/deepseek-chat"),
    "synthesis":  os.environ.get("MODEL_SYNTHESIS",  "openai/gpt-5.4"),
    "framework":  os.environ.get("MODEL_FRAMEWORK",  "openai/gpt-5.4"),
}


def get_model(purpose: str) -> str:
    """Get the configured model for a given purpose.

    Args:
        purpose: One of "writing", "polish", "case", "filter",
                 "synthesis", "framework".

    Returns:
        Full model identifier string (e.g., "openai/gpt-5.4").
    """
    return _MODELS.get(purpose, os.environ.get("WRITING_MODEL", "openai/gpt-5.4"))


def _get_all_purposes():
    """Return all model configs as dict (for debugging)."""
    return dict(_MODELS)
