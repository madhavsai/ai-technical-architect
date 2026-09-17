"""Orchestrates the full run:

Requirements -> Architect (core) -> Security Architect -> Reliability
Architect -> [Security, Cost, Reliability, Critic review] -> revise if
there's anything to fix -> review again -> Architecture Alternatives ->
Blueprint Compiler (risk register + roadmap) -> assemble the canonical
Section 7 `blueprint` object.

Bounded revision rounds (source doc Section 4); whatever the last review
round still flags is reported as open, not hidden.
"""

import os

from agents import (
    run_architect_agent,
    run_architect_revise,
    run_reliability_architect,
    run_requirements_agent,
    run_security_architect,
)
from blueprint import run_architecture_alternatives, run_blueprint_compiler
from review_agents import (
    run_cost_agent,
    run_critic_agent,
    run_reliability_agent,
    run_security_agent,
)
from validation import run_validation

# Quality over call count, per explicit product direction - this can run long.
MAX_REVISION_ROUNDS = int(os.environ.get("MAX_REVISION_ROUNDS", "2"))


def _merge_architecture(core: dict, security_controls: dict, reliability_design: dict) -> dict:
    return {**core, "security_controls": security_controls, "reliability_design": reliability_design}


def _run_review_round(brief, requirements, architecture, provider) -> dict:
    return {
        "security": run_security_agent(brief, requirements, architecture, provider),
        "cost": run_cost_agent(brief, requirements, architecture, provider),
        "reliability": run_reliability_agent(brief, requirements, architecture, provider),
        "critic": run_critic_agent(brief, requirements, architecture, provider),
    }


def _finding_count(review_round: dict) -> int:
    return sum(len(review_round[agent]["findings"]) for agent in review_round)


def run_pipeline(brief: dict, provider: str) -> dict:
    requirements = run_requirements_agent(brief, provider)

    core = run_architect_agent(brief, requirements, provider)
    security_controls = run_security_architect(brief, requirements, core, provider)
    reliability_design = run_reliability_architect(brief, requirements, core, provider)
    architecture = _merge_architecture(core, security_controls, reliability_design)

    review_round = _run_review_round(brief, requirements, architecture, provider)
    review_history = [review_round]
    resolved_count = 0
    rounds_run = 1
    changelog_history = []

    for round_idx in range(MAX_REVISION_ROUNDS):
        if _finding_count(review_round) == 0:
            break
        resolved_count += _finding_count(review_round)
        is_final_round = round_idx == MAX_REVISION_ROUNDS - 1
        revised = run_architect_revise(
            brief, requirements, architecture, review_round, round_idx + 1, is_final_round, provider
        )
        changelog_history.append({"round": round_idx + 1, "changes": revised.pop("changelog")})
        architecture = revised
        review_round = _run_review_round(brief, requirements, architecture, provider)
        review_history.append(review_round)
        rounds_run += 1

    alternatives = run_architecture_alternatives(brief, requirements, architecture, review_round["cost"], provider)
    compiled = run_blueprint_compiler(brief, requirements, architecture, review_history, alternatives, provider)

    review = {
        **review_round,
        "revision_rounds": rounds_run,
        "resolved_count": resolved_count,
        "open_count": _finding_count(review_round),
        "changelog": changelog_history,
    }

    blueprint = {
        "product": requirements["product_understanding"],
        "requirements": {
            "functional": requirements["functional"],
            "non_functional": requirements["non_functional"],
        },
        "constraints": brief.get("constraints", ""),
        "assumptions": requirements["assumptions"],
        "components": architecture["components"],
        "data_models": architecture["data_models"],
        "APIs": architecture["apis"],
        "security_controls": architecture["security_controls"],
        "threats": review_round["security"]["findings"],
        "infrastructure": architecture["infrastructure"],
        "scaling_strategy": architecture["reliability_design"]["scaling_strategy"],
        "reliability": architecture["reliability_design"]["reliability"],
        "disaster_recovery": architecture["reliability_design"]["disaster_recovery"],
        "observability": architecture["reliability_design"]["observability"],
        "failure_scenarios": architecture["reliability_design"]["failure_scenarios"],
        "cost": {
            "estimate_summary": review_round["cost"]["estimate_summary"],
            "within_budget": review_round["cost"]["within_budget"],
        },
        "decisions": architecture["decisions"],
        "risks": compiled["risks"],
        "review_findings": review_history,
        "architecture_stages": alternatives["stages"],
        "roadmap": compiled["roadmap"],
    }

    validation = run_validation(brief, architecture, blueprint)

    return {
        "requirements": requirements,
        "architecture": architecture,
        "review": review,
        "architecture_stages": alternatives["stages"],
        "blueprint": blueprint,
        "validation": validation,
    }
