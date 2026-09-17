"""Loads agent system prompts from backend/prompts/*.txt.

Kept as plain text files, not Python string constants, so they're easy to
read, diff, and tighten directly - this matters specifically for the
eval/hillclimb loop in eval/ (see eval/reference_designs.md), where prompts
get edited every round.
"""

import functools
import os

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")


@functools.lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    path = os.path.join(_PROMPTS_DIR, f"{name}.txt")
    with open(path, encoding="utf-8") as f:
        return f.read().strip()
