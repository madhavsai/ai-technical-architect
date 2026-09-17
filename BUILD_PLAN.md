# AI Technical Architect — Build Plan

Source of truth for vision/positioning: [`AI_Product_Factory_Vision_and_Build_Plan.html`](AI_Product_Factory_Vision_and_Build_Plan.html),
Section 12 ("Development Roadmap"). This plan covers **V1 only — Phases 1 through 6**.
The long-term "AI Product Factory" vision in the source doc's Sections 14-15 (PM agents,
engineering agents, infra agents, AI SRE, a full "AI company platform") is **explicitly
out of scope** and not tracked here.

Positioning (source doc Section 11): *"An AI engineering review board for your product
before you write the code."*

**All agent prompts live in `backend/prompts/*.txt`** (loaded via `backend/promptlib.py`),
not inline in Python — makes them easy to read/diff/tighten directly, which matters for
the eval/hillclimb loop in `eval/`. Restart the backend after editing a prompt file —
`promptlib.load_prompt` caches per-process.

**A "Target stage" selector was added to the brief form, 2026-09-16** — an 8th field
(Auto / MVP / Growth / Large scale). When set, it's a hard override threaded through
`agents.py`'s shared `STAGE_LABELS`/`_format_brief` into every design agent (Architect,
Security Architect, Reliability Architect), every review agent, and the Architecture
Alternatives agent — explicitly told to take priority over what the raw traffic/budget
numbers alone would imply. Verified with a real run: the same 150K-concurrent-trips
ride-hailing brief that normally produces sharding/multi-region design instead came back
"Single-region deployment... auto-scaling disabled for MVP stage" when `stage=mvp` was
forced, and the Architecture Alternatives table correctly anchored MVP to match. The
matching stage row is highlighted in the UI (`.stage-current`) when a stage was requested.

**A 3-agent independent audit + fix pass ran 2026-09-16** — the prompt set was
audited by 3 separate AI sessions (Claude, ChatGPT, Gemini) using
`eval/prompt_verification_request.md`; findings were cross-checked against the
running code, deduplicated, and triaged. Fixed: decision/risk IDs with a
roadmap that now cross-references risks, a `critical` severity tier, two new
Security Architect fields (`abuse_prevention`, `input_validation` - the
Security Agent was already scoped to check for these, nothing upstream
designed them; caught independently by all 3 reviewers), a structured
revision changelog (the revise step now has to name what it actually
changed, not just promise it), the Alternatives↔Compiler↔Cost data-flow gaps,
a `within_budget` grading contradiction, and an RTO-parsing direction bug.
Full detail in `eval/audit_fixes.md`. Verified end-to-end on a real run,
through the real UI.

**A real hillclimb pass ran 2026-09-16** — 5 hand-written hard system designs
(`eval/reference_designs.md`) run through the actual pipeline and compared against
reference; 7 generalizable fixes applied to the Architect/Critic prompts (REST-vs-
real-time API matching, an auth-boundary violation, missing concurrency-safety
mechanisms, verbatim/rambling repetition, hedging between two algorithms instead of
picking one). Full findings, what got verified-fixed vs. applied-but-unverified, and
honest residual gaps (fail-open/closed still doesn't land) in `eval/hillclimb_report.md`.

---

## Total agent calls in the pipeline: 10 distinct roles (up to ~20 calls per run)

**Revised 2026-09-16** from the original 6-agent count: once the source doc's full
Section 5 blueprint (Security/Operations as real designed content, not review-only) and
Section 6 (architecture alternatives) were brought in for real, "review-only" agents
weren't enough — something has to actually *design* security and reliability posture
before anyone can review it. Decomposed into focused, single-concern calls deliberately
(a specialist reasoning about one thing produces more depth than one generalist call
splitting attention across ten) — explicit product direction was to prioritize quality
over call count or generation time.

| # | Agent | Phase | Role |
|---|---|---|---|
| 1 | Requirements Agent | 2 | Product understanding, users/use cases, functional/non-functional requirements, assumptions, open questions. |
| 2 | Architect Agent | 2 | Core design: components, data models, APIs, infrastructure, ADR-shaped decisions. |
| 3 | Security Architect | 2 | **Designs** (not reviews) the security posture: threat model, authN, authZ, IAM, network boundaries, secrets/encryption — for the specific components already designed. |
| 4 | Reliability Architect | 2 | **Designs** the reliability posture: scaling strategy, reliability approach, disaster recovery, observability, concrete failure scenarios. |
| 5 | Security Agent | 3 | Reviews the full design (core + security + reliability) for security gaps. |
| 6 | Cost Agent | 3 | Estimates cost against the stated budget; flags risk. |
| 7 | Reliability Agent | 3 | Reviews SPOFs, availability, backups, RTO/RPO against the stated target. |
| 8 | Architecture Critic | 3 | Adversarial pass across everything - bottlenecks, overengineering, bad assumptions. |
| 9 | Architecture Alternatives | 4 (§6) | Given the final design, sketches MVP / Growth / Large-scale versions of *this specific system* with concrete transition triggers - not a generic table. |
| 10 | Blueprint Compiler | 4 | The two things nothing upstream produces: a deduplicated risk register (traced to source agent/round) and a real implementation roadmap. |

Revision loop (Phase 3, agents 5-8) is bounded by `MAX_REVISION_ROUNDS` (env, default
**2**, matching the source doc's own suggestion now that latency isn't the constraint).
Unresolved concerns after the last round are reported as `open`, not hidden.

**Real run, 2026-09-16** (appointment-booking example, local Ollama `qwen3-coder-16k`):
3 revision rounds, 48 findings resolved across revisions, 24 still open in the final
round: 8 decisions/ADRs, 6 data model entities, 9 concrete failure scenarios, 3 real
staged alternatives, 12-46 risks in the compiled register (varies run to run), a
genuine multi-phase roadmap referencing the system's actual specifics (UPI transaction
IDs, KMS encryption, circuit breakers). Total time: ~2-4 minutes depending on how much
the revision loop has to do. Verified end-to-end through the real UI (not mocked) —
zero console errors, every field populated correctly.

---

## The Architecture Specification (shared schema, source doc Section 7)

This is the canonical object every phase's output gets compiled into — Phase 4's
Blueprint Compiler assembles it from what every upstream agent already produced, using
these exact field names. It's returned as `blueprint` in the API response and is what
"Download blueprint JSON" exports.

```
blueprint
├── product                (Requirements Agent — product_understanding)
├── requirements           (Requirements Agent — functional + non_functional)
├── constraints            (from the user's brief, passed through)
├── assumptions            (Requirements Agent)
├── components             (Architect Agent)
├── data_models            (Architect Agent — real entities + fields, not table names)
├── APIs                   (Architect Agent)
├── security_controls      (Security Architect — the positive design)
├── threats                (Security Agent's findings, final round)
├── infrastructure         (Architect Agent)
├── scaling_strategy       (Reliability Architect)
├── reliability             (Reliability Architect)
├── observability           (Reliability Architect)
├── cost                   (Cost Agent, final round)
├── decisions / ADRs       (Architect Agent — decision, alternatives_considered, trade_offs, rationale)
├── risks                  (Blueprint Compiler — deduplicated, traced to source agent/round, status: open/mitigated/accepted)
├── review_findings        (full history — every round, every agent)
├── architecture_stages    (Architecture Alternatives — not in the original tree, added for source doc §6)
└── roadmap                (Blueprint Compiler — not in the original tree, added for source doc §5's "Implementation roadmap")
```

Two fields (`architecture_stages`, `roadmap`) aren't in the doc's original Section 7
list but were explicitly requested (§5's roadmap, §6's alternatives) — added as
siblings rather than force-fit into an existing branch.

---

## Phase 1 — Foundation *(built)*

No agents. Pure infrastructure.

- FastAPI backend, `backend/main.py`
- A `projects` table — one row per generation. **Built with SQLite, not Supabase** as
  originally sketched here — zero external setup, so it's testable immediately. Migrate
  to Postgres/Supabase in Phase 6, when multi-user auth actually needs it.
- The Architecture Specification JSON schema (`backend/schemas.py`), trimmed for now to
  the Requirements + Architecture branches Phase 2 actually fills
- A provider-abstraction "model interface" (`backend/providers.py`) — Gemini free tier
  and local Ollama, switchable **per request** from the frontend (not just via `.env`).
  Carries over the two real environment fixes already found and documented in
  `ideas/ui project/Live Visual Tutor/prototype/backend/llm.py`: this machine's broken
  `SSL_CERT_FILE` (patched to `certifi.where()`) and the global `OLLAMA_HOST=0.0.0.0`
  being a bind address, not a client target (always connect to `127.0.0.1:11434`
  explicitly instead of trusting the env var).
- **Simple web UI — plain HTML/CSS/JS, no framework, no build step** (`public/`)

**Run it** (two terminals):

```powershell
# Terminal 1 — backend
cd "C:\Users\user\Desktop\Master folder for work\AI System architect\backend"
copy .env.example .env   # then edit: set GEMINI_API_KEY and/or make sure Ollama is running
python -m uvicorn main:app --reload --port 8070

# Terminal 2 — frontend
cd "C:\Users\user\Desktop\Master folder for work\AI System architect\public"
python -m http.server 8060 --bind 127.0.0.1
```
Then open <http://127.0.0.1:8060/>. Check `http://127.0.0.1:8070/api/health` first if
generation isn't working — it reports which provider(s) are actually configured.

Note: `qwen3-coder:30b` isn't pulled under that literal tag on this machine — only a
16k-context variant built from it is (`qwen3-coder-16k:latest`, same convention as this
machine's `gemma4-8k`/`gemma4-16k` variants). `backend/.env.example` defaults to the
real tag; run `ollama list` to confirm yours if this changes.

**Status:** done and verified — real end-to-end generation confirmed via the local
Ollama provider (qwen3-coder-16k, ~35s for both agents). Gemini path is wired the same
way but untested here since no `GEMINI_API_KEY` is set in this environment yet.

---

## Phase 2 — Architect *(built, expanded 2026-09-16)*

Agents: **Requirements Agent**, **Architect Agent**, **Security Architect**,
**Reliability Architect** (4). Code in `backend/agents.py`.

Input: the 7 fields from the source doc's Section 2 ("Product inputs") — product idea,
target users, expected users/traffic, budget, availability target, cloud preference,
special constraints.

Flow: raw brief → Requirements Agent (product understanding, users/use cases,
functional/non-functional requirements, assumptions, open questions) → Architect Agent
(core: components, data models as real entities+fields, APIs, infrastructure, ADR-shaped
decisions) → Security Architect (designs, not reviews: threat model, authN, authZ, IAM,
network boundaries, secrets/encryption — for the specific components already designed) →
Reliability Architect (designs: scaling strategy, reliability approach, disaster
recovery, observability, concrete failure scenarios). Every call is schema-constrained
JSON (`backend/schemas.py`) on both providers — Gemini via `response_schema`, Ollama via
grammar-constrained `format`.

**Why four separate calls instead of one bigger schema:** originally planned as one
Architect Agent call with an expanded schema. Revised deliberately once cost/latency
stopped being the constraint — a real security architect and a real reliability
architect are different specialist roles in practice, and a focused call produces more
depth than one generalist call splitting attention across ten concerns in one schema.

Output rendered to the user: Requirements, Architecture (components/APIs/data
models/decisions), a generated schematic diagram, plus a live "Security & reliability
design" card.

---

## Phase 3 — Multi-agent review *(built)*

Agents: **Security Agent**, **Cost Agent**, **Reliability Agent**, **Architecture
Critic** (4). Code in `backend/review_agents.py`; revision handled by
`run_architect_revise` in `backend/agents.py`, now working against the *merged*
architecture (core + security_controls + reliability_design) so a fix in one lane stays
consistent with the others; the whole loop orchestrated in `backend/pipeline.py`.

Each reviews the full design independently against its own lane (threat model / budget
vs. estimate / SPOFs & RTO-RPO / adversarial "assume it's wrong") and returns findings
in one shared shape (`area`, `issue`, `severity`, `recommendation`). Cost also returns a
concrete estimate + a `within_budget` check.

Revision loop (source doc Section 4): `MAX_REVISION_ROUNDS` (env, default **2**, the
source doc's own suggestion — raised from an earlier default of 1 once the product
direction was explicitly "don't optimize for call count or time, optimize for quality").
If a round has zero findings, no further revision runs. Otherwise: revise, review again,
repeat up to the round cap; whatever the final round still flags is reported as open —
resolution is tracked at the round level (a round's findings count as addressed once a
revision was attempted against them), not per-finding matching.

**Status: done, verified end-to-end via Ollama**, findings badged by severity, a cost
summary + budget-fit tag, and the revision summary line rendered live.

---

## Phase 4 — Blueprint *(built, 2026-09-16)*

Two new agents (not "compilation only" as originally planned — see below): **Architecture
Alternatives**, **Blueprint Compiler** (bringing the pipeline total to 10 distinct
agent roles). Code in `backend/blueprint.py`, orchestrated at the end of
`backend/pipeline.py` after the review/revision loop settles.

**Why this needed real generation, not just formatting:** the original plan ("no new
agents — this is compilation, not generation") assumed everything Section 5 asks for
already existed somewhere upstream. It didn't — nothing produced the MVP/Growth/
Large-scale alternatives (source doc §6), and nothing produced a deduplicated risk
register or an implementation roadmap. Those two gaps are exactly what Phase 4 fills:

- **Architecture Alternatives** — given the *final* (post-revision) architecture, sketches
  how it would genuinely look at three points in its life, with a concrete
  `transition_trigger` per stage (a real signal, not "when the company grows").
- **Blueprint Compiler** — reads the *entire* review history (every round, every agent,
  not just the final one) and produces a deduplicated risk register (each entry traced
  to its source agent/round, status `open`/`mitigated`/`accepted`) and a real,
  system-specific implementation roadmap. ADRs are not regenerated here — the Architect
  Agent already produced those in Phase 2.
- The Compiler then assembles the canonical `blueprint` object matching source doc
  Section 7's exact field names (see the schema section above) — this is what "Download
  blueprint JSON" exports.

**Status: done, verified end-to-end through the real UI** (not mocked) — a full run
produced 8 ADRs, 6 data model entities, 9 concrete failure scenarios, 3 real staged
alternatives, a 12-46-item risk register, and a genuine multi-phase roadmap. Zero
console errors. Total pipeline time (Phases 2-4 in one request): **~2-4 minutes** on
local Ollama, depending on how much the revision loop has to do.

---

## Phase 5 — Knowledge + verification *(deterministic half built, 2026-09-16; knowledge
retrieval parked)*

No agents for the deterministic half — pure Python, zero LLM calls, in
`backend/validation.py`, run at the end of `pipeline.py` against the compiled
`blueprint`. Source doc Section 8: *"AI agents reason about risks, while deterministic
tools and policy systems enforce hard constraints."*

Five checks, each `pass` / `fail` / `skipped` (skipped when the brief didn't give enough
to check against):

1. **Availability vs. disaster recovery** — computes the actual downtime budget a stated
   availability target allows (e.g. 99.9% → ~8.8h/year) and checks it against an RTO
   parsed out of the disaster-recovery text. A real bug was caught and fixed building
   this: the first version fell back to scanning the *whole* paragraph for any duration
   when the word "RTO" wasn't found, and grabbed an unrelated number (a backup-retention
   period) - fixed to report "no RTO stated" honestly instead of a fabricated figure.
2. **Cost estimate vs. stated budget** — parses real numbers from both and does the
   comparison itself, rather than trusting the Cost Agent's own `within_budget`
   self-assessment. Also flags it directly when the two disagree - confirmed working
   against a synthetic case where the model was simply wrong about its own math.
3. **Hedge-language scan** — flags "TBD" / "not yet defined" / "not specified" etc.
   appearing in place of a real answer anywhere in the compiled blueprint.
4. **Cloud preference consistency** — if the brief named a cloud provider, checks the
   generated infrastructure text actually references it and not a different one.
5. **Completeness** — every required field (product, infra, scaling, reliability,
   observability, all 6 security_controls fields, and every list field) has real,
   non-trivial content.

**Status: done, verified end-to-end through the real UI.** A real run correctly flagged
the availability/RTO check (the Reliability Architect states backup/RPO detail but
doesn't consistently name an explicit RTO number - a genuine, real gap this check exists
to catch) while passing cost, hedge-language, and completeness.

**Parked for later, per explicit direction:** the knowledge-retrieval/RAG half (a
curated knowledge base with retrieval - architecture patterns, security best practices,
cloud pricing references - to ground the design/review agents; same pgvector + Ollama
embedding stack already proven in `The crawler/Content ingetion`). Source doc Section 13
still applies whenever this resumes: validation only, never autonomous Terraform/
Kubernetes execution.

---

## Phase 6 — SaaS

No new agents — product engineering.

Auth, project history, architecture spec versioning, usage limits, billing,
collaboration/sharing. `Gen ai applied/ai-advisor-back-end` already has working JWT auth
and Razorpay payment code — this phase adapts that rather than building it from zero.

---

## Build order

- [x] `BUILD_PLAN.md` — this document
- [x] Phase 1 frontend (`public/index.html`, `style.css`, `app.js`)
- [x] Frontend review / approval gate — approved
- [x] Phase 1 backend (FastAPI, schema, provider abstraction, SQLite)
- [x] Phase 2 (Requirements Agent + Architect Agent) — **live, verified end-to-end via
      Ollama**, real generation not mock data
- [x] Phases 3–6 **UI preview** — static, illustrative sections added below the real
      Phase 2 output (`.pipeline-preview` in `public/index.html`), all using the
      appointment-booking example from this doc, clearly labeled "Preview." Approved
      design system (blueprint motif) reused throughout, no new tokens introduced.
- [x] Phase 3 backend — **live now**, moved out of the preview section into the real
      output area (see Phase 3 above); the pipeline preview below covers Phases 4–6 only.
- [x] Phase 4/5 preview expanded to match the source doc's full Section 5/6/8 detail
      (superseded below — Phase 4 is now real, Phase 5's preview content still stands)
- [x] **Phase 2 expanded + Phase 4 built for real, 2026-09-16** — per explicit direction
      to build the full Section 5/6/7 blueprint completely rather than half: Security
      Architect + Reliability Architect added to Phase 2 (positive design, not just
      review); Architecture Alternatives (§6) and Blueprint Compiler added as Phase 4's
      two new agents; the canonical `blueprint` object (§7's exact field names) is now
      real and downloadable. Pipeline is 10 agent roles, ~2-4 min per run on local Ollama.
      Verified end-to-end through the real UI — zero console errors, every new field
      (use cases, data models, decisions, security controls, reliability design, failure
      scenarios, architecture stages, risk register, roadmap) confirmed populated with
      real generated content, not mocked.
- [x] **Phase 5 — deterministic validation, 2026-09-16** — 5 real checks (availability
      vs. RTO, cost vs. budget, hedge-language scan, cloud consistency, completeness),
      `backend/validation.py`, zero LLM calls. One real parsing bug found in testing and
      fixed (see Phase 5 above). Verified end-to-end through the real UI.
- [ ] Phase 5 — knowledge retrieval / RAG half ← **parked, explicit direction**
- [x] **Phase 6 — project history slice, 2026-09-16** — every generation was already
      being saved to SQLite (`db.save_project`, since Phase 1); this adds the read side:
      `db.list_projects()`/`db.get_project()`, `GET /api/projects` + `GET /api/projects/{id}`,
      and a "Your projects" section at the bottom of the page (replaced the old static
      Phase 6 preview card) listing every past run with a click-to-view row that reloads
      that run's full result through the same `renderResult()` used for a fresh generation.
      Auth/billing/collaboration are still not built — this is shared local history, not
      per-account. Verified against the live backend (27 real saved runs listed correctly)
      and by running the actual shipped `app.js` in a sandboxed DOM against the live
      server (no browser-automation tool was available this session) — `loadProjects()`
      and `viewProject()` both execute cleanly end-to-end with zero errors.
- [x] **Human-facing refine action + revision diff view, 2026-09-17** — per an external
      product-management review's top recommendation (close the "no reaction to output"
      core-loop gap before anything else): `POST /api/projects/{id}/refine` takes a saved
      project + free-text human notes, reuses `run_architect_revise` unchanged (the notes
      are framed as a single `human_reviewer` finding in the same shape the automated
      agents already produce), then re-runs the same tail a fresh generation gets
      (review, alternatives, blueprint compile, validation) so a refined result is exactly
      as complete as a new one - saved as a new, linked project (`refined_from` in the
      brief), not an in-place overwrite. `backend/pipeline.py` refactored to share this
      tail (`_assemble_result`) between `run_pipeline` and `run_refine` rather than
      duplicating the ~40-line blueprint-assembly block.
      Paired with a real before/after diff view (`review.architecture_history`, a
      snapshot per revision round, not just the changelog's claims about what changed) -
      renders per-field and per-component/per-decision text diffs client-side.
      **Real bug caught by this on its first live test**: refining the multi-tenant
      voice-agent project with "add replay-attack protection to the API key auth" produced
      a changelog claiming the fix landed in `security_controls.authentication`, but the
      diff view showed every `security_controls` field byte-identical before/after - the
      mechanism actually landed as an appended sentence in `components["Gateway
      Service"].description` instead, a real violation of the architect_revise prompt's
      own scope rule ("keep auth/IAM/secrets inside security_controls... rather than
      leaking into the core fields"). Confirms exactly the kind of gap this feature exists
      to surface — not a plumbing bug in this new code, a real, live instance of the
      changelog-not-verified issue flagged during the earlier adversarial-findings prompt
      audit. Verified end-to-end: real refine call against the live backend + Ollama
      (HTTP 200, correct lineage, correct changelog), plus the actual shipped `app.js` run
      in a sandboxed DOM against the live server confirming `renderRevisionDiff()` and
      `refineProject()` both execute cleanly with the right rendered output.
- [ ] Reliability arithmetic self-contradiction fix, 2026-09-17 — `reliability_architect.txt`
      and `reliability_review.txt` no longer ask the LLM to freehand RTO-vs-availability-
      budget arithmetic; that comparison is deferred to Phase 5's deterministic check
      (which already computes it correctly). Root cause: on a real saved run, the final
      review flagged a 5-minute RTO as `critical` ("consumes 6.25% of the annual budget"),
      while the deterministic check on the same run correctly passed it - and round 2's
      revise had already moved the RTO 2min→5min specifically to satisfy an *earlier*
      round's version of the same wrong finding. Both prompts now only judge what a
      numeric check can't: DR-tier-vs-RTO consistency and whether the recovery sequence
      actually plausibly achieves the stated number. **Not yet re-verified against a live
      run** - the fix is in prompt files, restart-tested for import errors only.
- [ ] Phase 6 remainder — auth, billing, collaboration ← **next, if resumed**
- [ ] Optional, discussed but not scheduled: live research step (self-hosted SearXNG +
      an Ollama tool-calling loop, zero API keys) feeding grounded current-info context
      into Phase 2's agents — related to but separate from the Phase 5 knowledge base
