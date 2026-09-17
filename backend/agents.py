"""Phase 2 — the design agents, run in sequence: Requirements -> Architect
(core) -> Security Architect -> Reliability Architect. Each is a focused,
narrow-scope call by design - a specialist reasoning hard about one concern
produces better depth than one generalist call splitting attention across
everything. Revision (after Phase 3's review) is the one place that works
against the *merged* architecture, since a fix in one lane often needs to
stay consistent with the other two.
"""

import json

from promptlib import load_prompt
from providers import generate_json
from schemas import (
    CORE_ARCHITECTURE_SCHEMA,
    RELIABILITY_DESIGN_SCHEMA,
    REQUIREMENTS_SCHEMA,
    REVISE_SCHEMA,
    SECURITY_CONTROLS_SCHEMA,
)


STAGE_LABELS = {
    "mvp": "MVP - simple architecture, low cost, low operational overhead. Goal: validate the product quickly. Do not design for scale or traffic beyond what's needed to prove the product works.",
    "growth": "Growth - horizontal scaling, caching, queues, and replicas where justified. Goal: handle increasing traffic reliably, without the cost/complexity of large-scale specialized infrastructure.",
    "large_scale": "Large scale - specialized services, partitioning/regional strategies where justified. Goal: support substantially larger workloads than a Growth-stage design could.",
}


def _format_brief(brief: dict) -> str:
    lines = [f"Product idea: {brief.get('idea', '').strip()}"]
    stage = (brief.get("stage") or "").strip().lower()
    if stage in STAGE_LABELS:
        lines.append(
            f"REQUIRED target stage: {STAGE_LABELS[stage]} Design specifically for "
            "this stage - it is not something to infer from traffic/budget, it is a "
            "direct instruction from the user that overrides your own judgment about "
            "which stage best fits the numbers."
        )
    labels = {
        "users": "Target users",
        "traffic": "Expected users/traffic",
        "budget": "Budget",
        "availability": "Availability target",
        "cloud": "Cloud preference",
        "constraints": "Special constraints",
    }
    for key, label in labels.items():
        value = (brief.get(key) or "").strip()
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Requirements Agent
# ---------------------------------------------------------------------------

REQUIREMENTS_SYSTEM_PROMPT = load_prompt("requirements_agent")


def run_requirements_agent(brief: dict, provider: str) -> dict:
    user_prompt = _format_brief(brief)
    return generate_json(REQUIREMENTS_SYSTEM_PROMPT, user_prompt, REQUIREMENTS_SCHEMA, provider)


# ---------------------------------------------------------------------------
# Architect Agent - core design
# ---------------------------------------------------------------------------

ARCHITECT_SYSTEM_PROMPT = load_prompt("architect_agent")


def run_architect_agent(brief: dict, requirements: dict, provider: str) -> dict:
    user_prompt = (
        _format_brief(brief)
        + "\n\nStructured requirements:\n"
        + json.dumps(requirements, indent=2)
    )
    return generate_json(ARCHITECT_SYSTEM_PROMPT, user_prompt, CORE_ARCHITECTURE_SCHEMA, provider)


# ---------------------------------------------------------------------------
# Security Architect - positive design, not review
# ---------------------------------------------------------------------------

SECURITY_ARCHITECT_SYSTEM_PROMPT = load_prompt("security_architect")


def run_security_architect(brief: dict, requirements: dict, core_architecture: dict, provider: str) -> dict:
    user_prompt = (
        _format_brief(brief)
        + "\n\nStructured requirements:\n"
        + json.dumps(requirements, indent=2)
        + "\n\nCore architecture (components, data models, APIs, infrastructure):\n"
        + json.dumps(core_architecture, indent=2)
    )
    return generate_json(SECURITY_ARCHITECT_SYSTEM_PROMPT, user_prompt, SECURITY_CONTROLS_SCHEMA, provider)


# ---------------------------------------------------------------------------
# Reliability Architect - positive design, not review
# ---------------------------------------------------------------------------

RELIABILITY_ARCHITECT_SYSTEM_PROMPT = load_prompt("reliability_architect")


def run_reliability_architect(brief: dict, requirements: dict, core_architecture: dict, provider: str) -> dict:
    user_prompt = (
        _format_brief(brief)
        + "\n\nStructured requirements:\n"
        + json.dumps(requirements, indent=2)
        + "\n\nCore architecture (components, data models, APIs, infrastructure):\n"
        + json.dumps(core_architecture, indent=2)
    )
    return generate_json(
        RELIABILITY_ARCHITECT_SYSTEM_PROMPT, user_prompt, RELIABILITY_DESIGN_SCHEMA, provider
    )


# ---------------------------------------------------------------------------
# Architect Agent - revise (works against the merged architecture)
# ---------------------------------------------------------------------------

ARCHITECT_REVISE_SYSTEM_PROMPT = load_prompt("architect_revise")


def run_architect_revise(
    brief: dict,
    requirements: dict,
    architecture: dict,
    findings_by_agent: dict,
    round_number: int,
    is_final_round: bool,
    provider: str,
) -> dict:
    round_line = (
        f"\n\nThis is revision round {round_number}"
        + (
            " - this is the LAST round available (MAX_REVISION_ROUNDS reached). "
            "Whatever is still open after this pass gets reported to the user as an "
            "unresolved risk, not silently retried - prioritize the highest-severity "
            "findings if you can't address everything with equal depth."
            if is_final_round
            else ". Further rounds are available if needed - don't rush a shallow fix "
            "just because there's another chance later; a bad fix here becomes a new "
            "finding for the next round to deal with."
        )
    )
    user_prompt = (
        _format_brief(brief)
        + round_line
        + "\n\nStructured requirements:\n"
        + json.dumps(requirements, indent=2)
        + "\n\nCurrent architecture (core + security + reliability):\n"
        + json.dumps(architecture, indent=2)
        + "\n\nReview findings to address:\n"
        + json.dumps(findings_by_agent, indent=2)
    )
    return generate_json(ARCHITECT_REVISE_SYSTEM_PROMPT, user_prompt, REVISE_SCHEMA, provider)
