# Audit fixes — 2026-09-16

Three independent agents (a fresh Claude session, ChatGPT, Gemini) audited
`eval/prompt_verification_request.md`. Findings were cross-checked against the
running code (not taken at face value), deduplicated, and triaged. This is
what got fixed, in the approved scope: **Tier 1 (7 verified bugs) + the
security-scope mismatch (all 3 reviewers caught this independently) + IDs +
a structured revision resolution-proof.**

## What changed

**Schemas (`schemas.py`)**
- `ADR_ITEM_SCHEMA` and `RISK_ITEM_SCHEMA` each gained an `id` field.
- `BLUEPRINT_SCHEMA.roadmap` changed from `array of string` to
  `array of {step, addresses_risk_ids}` - a roadmap step can now name which
  risk(s) it resolves.
- `FINDING_ITEM_SCHEMA` and `RISK_ITEM_SCHEMA` severity gained a `critical`
  tier (was capped at `high`, so a launch-blocker and a shippable-but-
  imperfect issue shared a bucket).
- `SECURITY_CONTROLS_SCHEMA` gained `abuse_prevention` and `input_validation`
  - fields the Security Agent was already scoped to review (STRIDE's DoS and
  tampering/injection categories) but nothing upstream ever designed.
- New `REVISE_SCHEMA` = the merged architecture + a required `changelog`
  (`finding_area`, `mechanism_added`, `components_affected` per entry) - the
  revise step now has to structurally account for what it changed, not just
  promise it in prose.

**Data flow (`pipeline.py`, `blueprint.py`, `agents.py`)**
- `run_blueprint_compiler` now receives the Architecture Alternatives output
  (previously generated blind to it - the roadmap and the MVP-stage
  description could describe two different systems with nothing checking).
- `run_architecture_alternatives` now receives the final round's Cost Agent
  finding, so `transition_trigger` cost thresholds are anchored to a real
  number instead of re-derived from scratch.
- `run_architect_revise` now receives the round number and whether it's the
  final round, and returns (and pipeline.py accumulates) the changelog
  per round.

**Prompts** - `cost_review.txt` (within_budget graded against the upper bound
of the stated range, matching what the deterministic validator already
checks - closes a real contradiction where an honest "mostly within budget"
answer got overruled), `security_architect.txt` (two new sections for the two
new fields), `security_review.txt` / `reliability_review.txt` /
`critic_review.txt` (a `critical` vs. `high` severity rule each, and the
reliability RTO/availability arithmetic reworded to be precise about
per-incident vs. annual-aggregate), `critic_review.txt` (loosened the
"don't repeat other reviewers" instruction - the Critic runs blind to the
other three agents within a round and can't actually know what they'll find,
so the instruction risked real findings being self-censored for no reason;
duplicates cost nothing since the Compiler already merges them downstream
with full visibility), `architect_agent.txt` / `blueprint_compiler.txt`
(id-assignment instructions), `architect_revise.txt` (round-awareness +
the changelog requirement - and removed the old line telling it *not* to
produce a changelog).

**Deterministic validation (`validation.py`)**
- `_duration_minutes_near` now searches both directions from the "RTO"
  keyword, not just forward - "a 4-hour recovery time (RTO)" was silently
  missed before.
- `HEDGE_PHRASES` expanded modestly, with an honest docstring caveat added:
  it's a literal-substring net, not a vagueness detector, and can't catch an
  agent that pads around a gap with confident-sounding prose instead of an
  honest placeholder.

**Frontend** - decision/risk ID badges, the two new security fields render,
`.severity-critical` styling, structured roadmap rendering (step + which
risk IDs it addresses), and a new changelog section on the review card
showing each revision round's actual changes.

## Verified, real run (not mocked)

Full pipeline run via Ollama: 8 real decision IDs (D1-D8), 10 risks with IDs
and a real mix of `critical`/`high` severity, a roadmap that correctly
cross-references those same risk IDs, a 2-round changelog with real
mechanism-level entries ("Added Customer Authentication Service component
with OAuth2...", listing the exact components touched), `abuse_prevention`
and `input_validation` populated with concrete content (rate limits with
real numbers, parameterized queries), `within_budget: true` consistent with
an estimate whose upper bound (22,000) fit the budget (25,000), and
Architecture Alternatives' transition triggers anchored to real INR figures
matching the actual cost estimate. Confirmed rendering correctly through the
real UI (not just the API response) - zero console errors.

## Known residual (documented, not silently dropped)

- One roadmap step's text had a stray leading colon (a one-off LLM
  formatting slip, not a schema/logic issue).
- Items intentionally left out of this pass, per the approved scope:
  Tier 3 (depends_on field, external-dependency list, requirement priority,
  API versioning, migration mechanics) and Tier 4 (requirement provenance,
  an explicit capacity/workload model, a new Architecture Contract stage,
  extending Phase 5's validator with coverage/orphan-detection, a
  verification/acceptance-criteria layer, the AI-systems extension, and
  Gemini's `_scratchpad` reasoning-space idea) - all real, all discussed,
  none in scope for this pass.
