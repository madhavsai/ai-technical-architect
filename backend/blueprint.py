"""Runs after the review/revision loop, against the final architecture:
Architecture Alternatives (source doc Section 6) and the Blueprint Compiler
(risk register + roadmap - the two things nothing upstream produces).
"""

import json

from agents import STAGE_LABELS
from promptlib import load_prompt
from providers import generate_json
from schemas import ARCHITECTURE_STAGES_SCHEMA, BLUEPRINT_SCHEMA

ALTERNATIVES_SYSTEM_PROMPT = load_prompt("architecture_alternatives")


def run_architecture_alternatives(
    brief: dict, requirements: dict, architecture: dict, cost_review: dict, provider: str
) -> dict:
    stage = (brief.get("stage") or "").strip().lower()
    stage_line = (
        f"The user explicitly requested the {STAGE_LABELS[stage]} stage for the given "
        "architecture - treat it as authoritatively at that stage, don't reinterpret "
        "which stage it's closest to. Describe the other two stages as genuine "
        "alternatives relative to it.\n"
        if stage in STAGE_LABELS
        else ""
    )
    user_prompt = (
        f"Product idea: {brief.get('idea', '').strip()}\n"
        f"Budget: {brief.get('budget', 'not stated')}\n"
        f"Traffic: {brief.get('traffic', 'not stated')}\n"
        f"{stage_line}\n"
        "The Cost Agent's own estimate for the current architecture (use this as your "
        "real cost anchor for transition_trigger cost thresholds, rather than "
        "re-deriving cost intuition from scratch):\n"
        + json.dumps(cost_review, indent=2)
        + "\n\nRequirements:\n" + json.dumps(requirements, indent=2) + "\n\n"
        "Current architecture:\n" + json.dumps(architecture, indent=2)
    )
    return generate_json(ALTERNATIVES_SYSTEM_PROMPT, user_prompt, ARCHITECTURE_STAGES_SCHEMA, provider)


BLUEPRINT_SYSTEM_PROMPT = load_prompt("blueprint_compiler")


def run_blueprint_compiler(
    brief: dict,
    requirements: dict,
    architecture: dict,
    review_history: list,
    alternatives: dict,
    provider: str,
) -> dict:
    user_prompt = (
        f"Product idea: {brief.get('idea', '').strip()}\n\n"
        "Final architecture:\n" + json.dumps(architecture, indent=2) + "\n\n"
        "Staged alternatives already produced for this architecture (your roadmap's "
        "early steps should describe the same starting point as the MVP stage below - "
        "don't silently contradict it):\n"
        + json.dumps(alternatives, indent=2)
        + "\n\nReview history, oldest round first (each round is the four agents' "
        "findings against the architecture as it stood at that point):\n"
        + json.dumps(review_history, indent=2)
    )
    return generate_json(BLUEPRINT_SYSTEM_PROMPT, user_prompt, BLUEPRINT_SCHEMA, provider)
