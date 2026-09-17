"""Phase 3 — the four independent review agents. Each takes the current
architecture and returns findings in a common shape; nothing here mutates the
architecture directly, that's the Architect Agent's job (agents.py, revise step).
"""

import json

from agents import STAGE_LABELS
from promptlib import load_prompt
from providers import generate_json
from schemas import COST_SCHEMA, CRITIC_SCHEMA, RELIABILITY_SCHEMA, SECURITY_SCHEMA

SECURITY_SYSTEM_PROMPT = load_prompt("security_review")
COST_SYSTEM_PROMPT = load_prompt("cost_review")
RELIABILITY_SYSTEM_PROMPT = load_prompt("reliability_review")
CRITIC_SYSTEM_PROMPT = load_prompt("critic_review")


def _format_review_prompt(brief: dict, requirements: dict, architecture: dict) -> str:
    lines = [f"Product idea: {brief.get('idea', '').strip()}"]
    stage = (brief.get("stage") or "").strip().lower()
    if stage in STAGE_LABELS:
        lines.append(
            f"User-requested target stage: {STAGE_LABELS[stage]} Judge the design "
            "against this stage specifically - flag both under-building for it and "
            "over-building beyond it."
        )
    if brief.get("budget"):
        lines.append(f"Budget: {brief['budget']}")
    if brief.get("availability"):
        lines.append(f"Availability target: {brief['availability']}")
    if brief.get("traffic"):
        lines.append(f"Expected users/traffic: {brief['traffic']}")
    lines.append("\nRequirements:\n" + json.dumps(requirements, indent=2))
    lines.append("\nProposed architecture:\n" + json.dumps(architecture, indent=2))
    return "\n".join(lines)


def run_security_agent(brief, requirements, architecture, provider) -> dict:
    prompt = _format_review_prompt(brief, requirements, architecture)
    return generate_json(SECURITY_SYSTEM_PROMPT, prompt, SECURITY_SCHEMA, provider)


def run_cost_agent(brief, requirements, architecture, provider) -> dict:
    prompt = _format_review_prompt(brief, requirements, architecture)
    return generate_json(COST_SYSTEM_PROMPT, prompt, COST_SCHEMA, provider)


def run_reliability_agent(brief, requirements, architecture, provider) -> dict:
    prompt = _format_review_prompt(brief, requirements, architecture)
    return generate_json(RELIABILITY_SYSTEM_PROMPT, prompt, RELIABILITY_SCHEMA, provider)


def run_critic_agent(brief, requirements, architecture, provider) -> dict:
    prompt = _format_review_prompt(brief, requirements, architecture)
    return generate_json(CRITIC_SYSTEM_PROMPT, prompt, CRITIC_SCHEMA, provider)
