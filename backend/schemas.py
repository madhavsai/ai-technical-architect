"""JSON schemas for every agent's structured output. Same dict is handed to
both providers: Gemini's `response_schema` (Google's subset of OpenAPI 3.0)
and Ollama's `format` (grammar-constrained JSON) both accept this shape
directly - see providers.py. One shared schema per concept means the two
providers can never silently drift apart on output shape.

Field names follow the source doc's Section 7 Architecture Specification
tree wherever a concept maps onto it 1:1 (security_controls, threats,
scaling_strategy, reliability, observability, decisions, risks,
review_findings); Phase 4's blueprint.py assembles the final object using
those exact keys.

Revised 2026-09-16 after an independent 3-agent audit of the prompt set
(eval/prompt_verification_request.md) - see eval/audit_fixes.md for the
full list of what changed and why. Key additions: `id` on decisions and
risks (so a roadmap step or a later finding can reference one), a
"critical" severity tier (a launch-blocking gap and a shippable-but-
imperfect one used to share the same "high" bucket), two new
security_controls fields the review agents were already scoped to check
for but nothing designed (abuse_prevention, input_validation), a
structured roadmap (was a flat string list, couldn't reference which
risks a step addresses), and a dedicated REVISE_SCHEMA that forces a
changelog proving what actually changed instead of trusting prose.
"""

# ---------------------------------------------------------------------------
# Phase 2 - Requirements Agent
# ---------------------------------------------------------------------------

REQUIREMENTS_SCHEMA = {
    "type": "object",
    "properties": {
        "product_understanding": {"type": "string"},
        "users_and_use_cases": {"type": "array", "items": {"type": "string"}},
        "functional": {"type": "array", "items": {"type": "string"}},
        "non_functional": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "product_understanding",
        "users_and_use_cases",
        "functional",
        "non_functional",
        "assumptions",
        "open_questions",
    ],
}

# ---------------------------------------------------------------------------
# Phase 2 - Architect Agent (core design) + revise
# ---------------------------------------------------------------------------

ADR_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "decision": {"type": "string"},
        "alternatives_considered": {"type": "string"},
        "trade_offs": {"type": "string"},
        "rationale": {"type": "string"},
    },
    "required": ["id", "decision", "alternatives_considered", "trade_offs", "rationale"],
}

DATA_MODEL_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "entity": {"type": "string"},
        "fields": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
    },
    "required": ["entity", "fields", "notes"],
}

CORE_ARCHITECTURE_SCHEMA = {
    "type": "object",
    "properties": {
        "components": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["name", "description"],
            },
        },
        "data_models": {"type": "array", "items": DATA_MODEL_ITEM_SCHEMA},
        "apis": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "method": {"type": "string"},
                    "path": {"type": "string"},
                    "desc": {"type": "string"},
                },
                "required": ["method", "path", "desc"],
            },
        },
        "infrastructure": {"type": "string"},
        "decisions": {"type": "array", "items": ADR_ITEM_SCHEMA},
    },
    "required": ["components", "data_models", "apis", "infrastructure", "decisions"],
}

# ---------------------------------------------------------------------------
# Phase 2 - Security Architect (positive design, not review)
# ---------------------------------------------------------------------------

SECURITY_CONTROLS_SCHEMA = {
    "type": "object",
    "properties": {
        "threat_model_summary": {"type": "string"},
        "authentication": {"type": "string"},
        "authorization": {"type": "string"},
        "iam": {"type": "string"},
        "network_boundaries": {"type": "string"},
        "secrets_and_encryption": {"type": "string"},
        "abuse_prevention": {"type": "string"},
        "input_validation": {"type": "string"},
    },
    "required": [
        "threat_model_summary",
        "authentication",
        "authorization",
        "iam",
        "network_boundaries",
        "secrets_and_encryption",
        "abuse_prevention",
        "input_validation",
    ],
}

# ---------------------------------------------------------------------------
# Phase 2 - Reliability Architect (positive design, not review)
# ---------------------------------------------------------------------------

RELIABILITY_DESIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "scaling_strategy": {"type": "string"},
        "reliability": {"type": "string"},
        "disaster_recovery": {"type": "string"},
        "observability": {"type": "string"},
        "failure_scenarios": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "scaling_strategy",
        "reliability",
        "disaster_recovery",
        "observability",
        "failure_scenarios",
    ],
}

# ---------------------------------------------------------------------------
# The merged architecture (core + security_controls + reliability_design) -
# used by the review agents, which need to see all three at once.
# ---------------------------------------------------------------------------

FULL_ARCHITECTURE_SCHEMA = {
    "type": "object",
    "properties": {
        "components": CORE_ARCHITECTURE_SCHEMA["properties"]["components"],
        "data_models": CORE_ARCHITECTURE_SCHEMA["properties"]["data_models"],
        "apis": CORE_ARCHITECTURE_SCHEMA["properties"]["apis"],
        "infrastructure": CORE_ARCHITECTURE_SCHEMA["properties"]["infrastructure"],
        "decisions": CORE_ARCHITECTURE_SCHEMA["properties"]["decisions"],
        "security_controls": SECURITY_CONTROLS_SCHEMA,
        "reliability_design": RELIABILITY_DESIGN_SCHEMA,
    },
    "required": [
        "components",
        "data_models",
        "apis",
        "infrastructure",
        "decisions",
        "security_controls",
        "reliability_design",
    ],
}

# ---------------------------------------------------------------------------
# The revise step's own schema - the merged architecture plus a required
# changelog. Without this, "revise" was graded purely on prose promising a
# fix was real; the changelog forces a structural claim (which finding, what
# mechanism, which components) that a downstream reader - or a future
# automated check - can actually verify against the architecture fields.
# ---------------------------------------------------------------------------

CHANGELOG_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "finding_area": {"type": "string"},
        "mechanism_added": {"type": "string"},
        "components_affected": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["finding_area", "mechanism_added", "components_affected"],
}

REVISE_SCHEMA = {
    "type": "object",
    "properties": {
        **FULL_ARCHITECTURE_SCHEMA["properties"],
        "changelog": {"type": "array", "items": CHANGELOG_ITEM_SCHEMA},
    },
    "required": [*FULL_ARCHITECTURE_SCHEMA["required"], "changelog"],
}

# ---------------------------------------------------------------------------
# Phase 3 - the four review agents (unchanged shape - critique, not design)
# ---------------------------------------------------------------------------

FINDING_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "area": {"type": "string"},
        "issue": {"type": "string"},
        "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "recommendation": {"type": "string"},
    },
    "required": ["area", "issue", "severity", "recommendation"],
}

SECURITY_SCHEMA = {
    "type": "object",
    "properties": {"findings": {"type": "array", "items": FINDING_ITEM_SCHEMA}},
    "required": ["findings"],
}

COST_SCHEMA = {
    "type": "object",
    "properties": {
        "estimate_summary": {"type": "string"},
        "within_budget": {"type": "boolean"},
        "findings": {"type": "array", "items": FINDING_ITEM_SCHEMA},
    },
    "required": ["estimate_summary", "within_budget", "findings"],
}

RELIABILITY_SCHEMA = {
    "type": "object",
    "properties": {"findings": {"type": "array", "items": FINDING_ITEM_SCHEMA}},
    "required": ["findings"],
}

CRITIC_SCHEMA = {
    "type": "object",
    "properties": {"findings": {"type": "array", "items": FINDING_ITEM_SCHEMA}},
    "required": ["findings"],
}

# ---------------------------------------------------------------------------
# Architecture Alternatives (source doc Section 6)
# ---------------------------------------------------------------------------

ARCHITECTURE_STAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "stage": {"type": "string"},
        "characteristics": {"type": "string"},
        "purpose": {"type": "string"},
        "transition_trigger": {"type": "string"},
    },
    "required": ["stage", "characteristics", "purpose", "transition_trigger"],
}

ARCHITECTURE_STAGES_SCHEMA = {
    "type": "object",
    "properties": {"stages": {"type": "array", "items": ARCHITECTURE_STAGE_SCHEMA}},
    "required": ["stages"],
}

# ---------------------------------------------------------------------------
# Phase 4 - Blueprint Compiler
# ---------------------------------------------------------------------------

RISK_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "risk": {"type": "string"},
        "source": {"type": "string"},
        "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "status": {"type": "string", "enum": ["open", "accepted", "mitigated"]},
    },
    "required": ["id", "risk", "source", "severity", "status"],
}

ROADMAP_STEP_SCHEMA = {
    "type": "object",
    "properties": {
        "step": {"type": "string"},
        "addresses_risk_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["step", "addresses_risk_ids"],
}

BLUEPRINT_SCHEMA = {
    "type": "object",
    "properties": {
        "risks": {"type": "array", "items": RISK_ITEM_SCHEMA},
        "roadmap": {"type": "array", "items": ROADMAP_STEP_SCHEMA},
    },
    "required": ["risks", "roadmap"],
}
