"""Phase 5 — deterministic validation only (the knowledge-retrieval/RAG half
of Phase 5 is parked for later). Pure Python, no LLM calls: source doc
Section 8's whole point is that an LLM shouldn't be the final authority on
whether its own numbers add up. Every check here is arithmetic, a lookup, or
a pattern match against what the pipeline already generated.
"""

import re

# A literal-substring net, not a vagueness detector - it catches an agent that
# writes an honest placeholder, not one that pads around the gap with
# confident-sounding prose ("secured appropriately", "as needed"). That kind
# of semantic vagueness needs a reader (the review agents, or a human) - a
# fixed phrase list can't reliably catch it without becoming an LLM call
# itself, which would defeat Phase 5's whole point (deterministic, no LLM).
# Keep expanding this list when a real run turns up a new hedge phrase, but
# don't mistake a clean scan for proof the text is actually concrete.
HEDGE_PHRASES = [
    "not yet defined",
    "to be determined",
    "tbd",
    "not specified",
    "not itemized",
    "open item",
    "not defined",
    "to be decided",
    "not applicable",
    "secured appropriately",
    "handled appropriately",
    "will be determined",
    "unspecified",
]

CLOUD_KEYWORDS = {
    "aws": ["aws", "amazon web services", "ec2", "s3", "rds", "lambda", "dynamodb", "cloudfront"],
    "azure": ["azure", "aks", "cosmos db", "azure sql"],
    "gcp": ["gcp", "google cloud", "gke", "bigquery", "firestore", "cloud run"],
}


def _numbers(text: str) -> list[float]:
    return [float(n.replace(",", "")) for n in re.findall(r"[\d,]+(?:\.\d+)?", text or "")]


def _percentage(text: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text or "")
    return float(m.group(1)) if m else None


def _duration_minutes_near(text: str, keyword: str) -> float | None:
    if not text:
        return None
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        # Keyword genuinely absent - don't fall back to scanning the whole
        # paragraph for *any* number, that grabs an unrelated figure (e.g. a
        # backup-retention period) and reports it as if it were the RTO.
        return None
    # Search both directions from the keyword - "RTO: 4 hours" and "a 4-hour
    # recovery time (RTO)" are both real phrasings, and only scanning forward
    # missed the second one entirely (silently, not even a "no RTO found").
    duration_re = re.compile(r"(\d+(?:\.\d+)?)\s*(day|hour|hr|minute|min)s?\b", re.IGNORECASE)
    after = text[idx : idx + 120]
    before_start = max(0, idx - 60)
    before = text[before_start:idx]
    m = duration_re.search(after)
    if not m:
        matches = list(duration_re.finditer(before))
        m = matches[-1] if matches else None  # closest match to the keyword
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2).lower()
    if unit.startswith("day"):
        return value * 24 * 60
    if unit.startswith("h"):
        return value * 60
    return value


def check_availability_vs_rto(brief: dict, architecture: dict) -> dict:
    name = "Availability target vs. disaster recovery"
    pct = _percentage(brief.get("availability", ""))
    if pct is None:
        return {"check": name, "status": "skipped", "detail": "No numeric availability target stated - nothing to check."}

    allowed_min = (1 - pct / 100) * 365.25 * 24 * 60
    dr_text = architecture.get("reliability_design", {}).get("disaster_recovery", "")
    rto_min = _duration_minutes_near(dr_text, "RTO")

    if rto_min is None:
        return {
            "check": name,
            "status": "fail",
            "detail": f"{pct}% availability allows ~{allowed_min / 60:.1f}h of downtime/year, but no explicit "
            "RTO duration was found in the disaster recovery plan to check it against.",
        }
    if rto_min > allowed_min:
        return {
            "check": name,
            "status": "fail",
            "detail": f"{pct}% availability allows ~{allowed_min / 60:.1f}h/year of downtime, but the stated "
            f"RTO is ~{rto_min / 60:.1f}h - a single incident could exceed the whole annual budget.",
        }
    return {
        "check": name,
        "status": "pass",
        "detail": f"RTO (~{rto_min / 60:.1f}h) fits within the {pct}% target's ~{allowed_min / 60:.1f}h/year downtime budget.",
    }


def check_budget(brief: dict, blueprint: dict) -> dict:
    name = "Cost estimate vs. stated budget"
    budget_nums = _numbers(brief.get("budget", ""))
    if not budget_nums:
        return {"check": name, "status": "skipped", "detail": "No parseable budget number stated - nothing to check."}
    budget_value = max(budget_nums)

    estimate_text = blueprint.get("cost", {}).get("estimate_summary", "")
    estimate_nums = _numbers(estimate_text)
    if not estimate_nums:
        return {"check": name, "status": "skipped", "detail": "Could not parse a number from the cost estimate."}
    estimate_value = max(estimate_nums)

    llm_says_within = blueprint.get("cost", {}).get("within_budget")
    computed_within = estimate_value <= budget_value

    if llm_says_within is not None and computed_within != llm_says_within:
        return {
            "check": name,
            "status": "fail",
            "detail": f"The Cost Agent said within_budget={llm_says_within}, but the parsed numbers disagree: "
            f"estimate up to {estimate_value:,.0f} vs. budget {budget_value:,.0f}.",
        }
    if not computed_within:
        return {
            "check": name,
            "status": "fail",
            "detail": f"Estimate (up to {estimate_value:,.0f}) exceeds the stated budget ({budget_value:,.0f}).",
        }
    return {
        "check": name,
        "status": "pass",
        "detail": f"Estimate (up to {estimate_value:,.0f}) fits within the stated budget ({budget_value:,.0f}).",
    }


def check_vague_language(blueprint: dict) -> dict:
    name = "Hedge-language scan"
    fields = {
        "infrastructure": blueprint.get("infrastructure", ""),
        "scaling_strategy": blueprint.get("scaling_strategy", ""),
        "reliability": blueprint.get("reliability", ""),
        "observability": blueprint.get("observability", ""),
        "cost.estimate_summary": blueprint.get("cost", {}).get("estimate_summary", ""),
    }
    for key, value in blueprint.get("security_controls", {}).items():
        fields[f"security_controls.{key}"] = value

    hits = []
    for field_name, text in fields.items():
        lower = (text or "").lower()
        for phrase in HEDGE_PHRASES:
            if phrase in lower:
                hits.append(f'{field_name}: contains "{phrase}"')

    if hits:
        return {"check": name, "status": "fail", "detail": "Unresolved/vague language found instead of a real answer: " + "; ".join(hits)}
    return {"check": name, "status": "pass", "detail": 'No hedge phrases ("TBD", "not yet defined", ...) found in the compiled blueprint.'}


def check_cloud_consistency(brief: dict, blueprint: dict) -> dict:
    name = "Cloud preference consistency"
    chosen = (brief.get("cloud") or "").strip().lower()
    if chosen not in CLOUD_KEYWORDS:
        return {"check": name, "status": "skipped", "detail": "No specific cloud preference stated - nothing to check."}

    infra_text = (blueprint.get("infrastructure", "") or "").lower()
    chosen_hits = sum(infra_text.count(kw) for kw in CLOUD_KEYWORDS[chosen])
    other_hits = {p: sum(infra_text.count(kw) for kw in kws) for p, kws in CLOUD_KEYWORDS.items() if p != chosen}
    best_other = max(other_hits, key=other_hits.get) if other_hits else None

    if chosen_hits == 0 and best_other and other_hits[best_other] > 0:
        return {
            "check": name,
            "status": "fail",
            "detail": f"Brief specified {chosen.upper()}, but the infrastructure design references "
            f"{best_other.upper()} instead and never mentions {chosen.upper()}.",
        }
    return {"check": name, "status": "pass", "detail": f"Infrastructure design is consistent with the stated {chosen.upper()} preference."}


def check_completeness(blueprint: dict) -> dict:
    name = "Completeness"
    missing = []
    for field in ["product", "infrastructure", "scaling_strategy", "reliability", "observability"]:
        value = blueprint.get(field, "")
        if not value or len(value.strip()) < 15:
            missing.append(field)
    for key, value in blueprint.get("security_controls", {}).items():
        if not value or len(value.strip()) < 15:
            missing.append(f"security_controls.{key}")
    for field in ["components", "data_models", "APIs", "decisions", "risks"]:
        if not blueprint.get(field):
            missing.append(field)

    if missing:
        return {"check": name, "status": "fail", "detail": "Missing or too short: " + ", ".join(missing)}
    return {"check": name, "status": "pass", "detail": "Every required blueprint field has real content."}


def run_validation(brief: dict, architecture: dict, blueprint: dict) -> list[dict]:
    return [
        check_availability_vs_rto(brief, architecture),
        check_budget(brief, blueprint),
        check_vague_language(blueprint),
        check_cloud_consistency(brief, blueprint),
        check_completeness(blueprint),
    ]
