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


def _revise_loop(brief, requirements, architecture, review_round, provider, max_rounds):
    """Shared by run_pipeline (revising against automated review findings) and
    run_refine (revising against a human's notes, framed as a single-round
    finding) - runs the revise -> re-review loop and returns everything a
    caller needs to assemble a final result: the final architecture, the full
    review_history, the changelog per round, and a before/after architecture
    snapshot per round (the diff view needs the actual snapshots, not just
    the changelog's claims about what changed)."""
    review_history = [review_round]
    architecture_history = [architecture]
    resolved_count = 0
    rounds_run = 1
    changelog_history = []

    for round_idx in range(max_rounds):
        if _finding_count(review_round) == 0:
            break
        resolved_count += _finding_count(review_round)
        is_final_round = round_idx == max_rounds - 1
        revised = run_architect_revise(
            brief, requirements, architecture, review_round, round_idx + 1, is_final_round, provider
        )
        changelog_history.append({"round": round_idx + 1, "changes": revised.pop("changelog")})
        architecture = revised
        architecture_history.append(architecture)
        review_round = _run_review_round(brief, requirements, architecture, provider)
        review_history.append(review_round)
        rounds_run += 1

    return {
        "architecture": architecture,
        "architecture_history": architecture_history,
        "review_round": review_round,
        "review_history": review_history,
        "changelog_history": changelog_history,
        "resolved_count": resolved_count,
        "rounds_run": rounds_run,
    }


def _assemble_result(brief, requirements, loop_result, provider) -> dict:
    """The tail every full or refined run shares: alternatives, blueprint
    compilation, and deterministic validation, assembled into the same
    response shape either way."""
    architecture = loop_result["architecture"]
    review_round = loop_result["review_round"]
    review_history = loop_result["review_history"]

    alternatives = run_architecture_alternatives(brief, requirements, architecture, review_round["cost"], provider)
    compiled = run_blueprint_compiler(brief, requirements, architecture, review_history, alternatives, provider)

    review = {
        **review_round,
        "revision_rounds": loop_result["rounds_run"],
        "resolved_count": loop_result["resolved_count"],
        "open_count": _finding_count(review_round),
        "changelog": loop_result["changelog_history"],
        "architecture_history": loop_result["architecture_history"],
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


def run_pipeline(brief: dict, provider: str) -> dict:
    requirements = run_requirements_agent(brief, provider)

    core = run_architect_agent(brief, requirements, provider)
    security_controls = run_security_architect(brief, requirements, core, provider)
    reliability_design = run_reliability_architect(brief, requirements, core, provider)
    architecture = _merge_architecture(core, security_controls, reliability_design)

    review_round = _run_review_round(brief, requirements, architecture, provider)
    loop_result = _revise_loop(brief, requirements, architecture, review_round, provider, MAX_REVISION_ROUNDS)

    return _assemble_result(brief, requirements, loop_result, provider)


def run_refine(
    brief: dict, requirements: dict, architecture: dict, review_round: dict, notes: str, provider: str
) -> dict:
    """Human-facing counterpart to the automated revise loop - takes an
    existing (already fully-reviewed) architecture, the review it was last
    reviewed against (the caller passes in the saved project's own final
    review - re-running that review here would just be 4 wasted LLM calls
    for a result already on disk), plus a human's free-text notes, and runs
    exactly one revision pass against the notes. Reuses run_architect_revise
    unchanged: the notes are framed as a single named finding (the prompt
    already expects "independent review findings from Security, Cost,
    Reliability, and Architecture Critic agents" in this shape, and handles a
    human's plainer language the same way it handles any other reviewer's).
    Then re-runs the same tail every full run gets (fresh review,
    alternatives, blueprint compile, validation) so a refined result is
    exactly as complete as a fresh generation, not a partial patch.
    """
    findings_by_agent = {
        "human_reviewer": {
            "findings": [
                {
                    "area": "Human feedback",
                    "issue": notes,
                    "severity": "high",
                    "recommendation": "Address this note directly in the revised architecture.",
                }
            ]
        }
    }
    # The human's notes are the thing being addressed this round, not the
    # architecture's pre-existing review findings - revise against the notes
    # alone as a single, final round (there's no bounded multi-round loop for
    # a human-steered refine; one considered pass, same as an original design).
    revised = run_architect_revise(
        brief, requirements, architecture, findings_by_agent, 1, True, provider
    )
    changelog_history = [{"round": 1, "changes": revised.pop("changelog")}]
    new_architecture = revised
    new_review_round = _run_review_round(brief, requirements, new_architecture, provider)

    loop_result = {
        "architecture": new_architecture,
        "architecture_history": [architecture, new_architecture],
        "review_round": new_review_round,
        "review_history": [review_round, new_review_round],
        "changelog_history": changelog_history,
        "resolved_count": _finding_count(review_round),
        "rounds_run": 1,
    }

    return _assemble_result(brief, requirements, loop_result, provider)
