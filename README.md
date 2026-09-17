# AI Technical Architect

A multi-agent AI system that turns a plain-language product brief into a full
production-grade technical architecture blueprint — the kind of design doc a real
architecture review board would sign off on, not a single-shot LLM sketch.

Give it a product idea, expected users/traffic, a budget, an availability target, a
cloud preference, and any special constraints. It runs the brief through a pipeline of
**10 specialist agents** — design agents, independent adversarial reviewers, and a
compiler — and returns components, data models, APIs, a named security posture, a named
reliability posture, a deduplicated risk register, MVP/Growth/Large-scale architecture
alternatives, and an implementation roadmap. Every generation is saved and browsable
from the same page.

No frameworks, no build step: a FastAPI + SQLite backend and a plain HTML/CSS/JS
frontend.

## Why this exists

Most "AI system design" tools produce a single confident-sounding pass. This project's
premise is that a good architecture survives *adversarial* review, not just generation —
so every design gets attacked by four independent reviewers before it's considered
final, and the fixes have to be real mechanisms, not reworded prose.

## The pipeline

```
Brief
  │
  ▼
Requirements Agent ─── product understanding, users/use cases, functional +
  │                     non-functional requirements, assumptions, open questions
  ▼
Architect Agent ─────── components (C4-style), data models, APIs, infrastructure,
  │                     ADR-format engineering decisions
  ▼
Security Architect ──── threat model (STRIDE), authN/authZ, IAM, network boundaries,
  │                     secrets & encryption, abuse prevention, input validation
  ▼
Reliability Architect ─ scaling strategy, DR strategy (backup/pilot-light/warm-standby/
  │                     active-active), RTO/RPO, observability, failure scenarios
  ▼
┌─────────────────────────────────────────────────────────────┐
│  4 independent adversarial reviewers, run blind to each      │
│  other each round:                                            │
│    Security Agent · Cost Agent · Reliability Agent ·          │
│    Architecture Critic (pre-mortem / red-team pass)            │
└─────────────────────────────────────────────────────────────┘
  │
  ▼ (bounded revision loop — revise, re-review, repeat until
  │  clean or the round cap is hit)
  ▼
Architecture Alternatives ── the same design at 3 real points in its life
  │                          (MVP / Growth / Large-scale), each with a concrete
  │                          transition_trigger
  ▼
Blueprint Compiler ───────── deduplicated risk register (traced to source agent/round,
                             status open/mitigated/accepted) + a system-specific
                             implementation roadmap + the canonical blueprint object
```

Every agent call is **schema-constrained JSON** — Gemini via `response_schema`, local
Ollama via grammar-constrained `format` — so the pipeline never depends on an LLM
"remembering" to return valid JSON.

## What makes the review loop real

- **Reviewers run blind to each other within a round.** A finding isn't suppressed just
  because it might overlap with another lane's — duplicates get merged later, but a real
  finding talked out of existing doesn't get a second chance.
- **Revisions must prove themselves.** Each revision round returns a `changelog` — the
  actual mechanism added per finding, not a restatement of the finding — because a
  cosmetic fix (reworded prose, same underlying gap) reads identically to a real one in
  free text.
- **A deterministic layer enforces what shouldn't be left to an LLM's judgment.**
  Availability-vs-RTO math, cost-vs-budget arithmetic, hedge-language scanning
  ("TBD", "not yet defined"), cloud-preference consistency, and field completeness are
  all checked in plain Python against the compiled blueprint — *"AI agents reason about
  risk, deterministic tools enforce hard constraints."*
- **A target-stage override** (MVP / Growth / Large-scale) lets you force the design's
  complexity level regardless of what the raw traffic/budget numbers would otherwise
  imply — genuinely changes generation behavior, not a cosmetic label.

## Quick start

Requires Python 3.11+, and either a free [Gemini API key](https://aistudio.google.com/apikey)
or a locally running [Ollama](https://ollama.com/) with a model pulled.

```bash
# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env        # then set GEMINI_API_KEY and/or confirm your Ollama model
python -m uvicorn main:app --reload --port 8070

# Frontend (separate terminal)
cd public
python -m http.server 8060 --bind 127.0.0.1
```

Open `http://127.0.0.1:8060`. If generation isn't working, check
`http://127.0.0.1:8070/api/health` first — it reports which provider(s) are actually
configured and reachable.

## Project layout

```
backend/
  main.py            FastAPI app — /api/generate, /api/projects, /api/health
  pipeline.py         Orchestrates the full 10-agent run + revision loop
  agents.py           Requirements / Architect / Security Architect / Reliability Architect
  review_agents.py    Security / Cost / Reliability / Critic reviewers
  blueprint.py        Architecture Alternatives + Blueprint Compiler
  validation.py       Deterministic (non-LLM) checks against the compiled blueprint
  schemas.py          JSON schemas shared by both providers (Gemini + Ollama)
  providers.py        Gemini / Ollama provider abstraction, retry-on-parse-failure
  promptlib.py        Loads prompts from prompts/*.txt
  prompts/            One .txt file per agent — the actual prompt engineering
  db.py               SQLite persistence — every generation is saved automatically
public/
  index.html / app.js / style.css   Plain HTML/CSS/JS frontend, no build step
eval/
  Hand-authored reference designs, hillclimb notes, and real pipeline runs used to
  iteratively tighten the prompts against real (not hypothetical) failure modes
BUILD_PLAN.md          Living build log — phase-by-phase status, decisions, and why
```

## Design principles this project holds itself to

- **Every prompt is grounded in a named industry framework** — C4 component modeling,
  Nygard-format ADRs, STRIDE threat modeling, OWASP API Security, Zero Trust, RBAC/ABAC,
  SRE error-budget math, the standard DR-tier taxonomy (backup-restore → pilot-light →
  warm-standby → multi-site active-active), FinOps unit economics — not generic
  "best practices" language.
- **Prompts are tightened against real evidence, not intuition.** `eval/` holds hand-authored
  reference designs and real pipeline runs compared against them; prompt changes are only
  made once a gap is confirmed in real generated output, then re-verified that the fix
  generalizes rather than just patching one scenario.
- **No mocked output.** Every phase was verified end-to-end against a real running
  backend and a real browser session before being marked done in `BUILD_PLAN.md`.

## Status

Phases 1–4 (design pipeline, adversarial review, blueprint compilation) and the
deterministic half of Phase 5 (verification checks) are complete and verified.
Phase 5's knowledge-retrieval/RAG half is parked. Phase 6's project-history browsing is
live; auth, billing, and collaboration are not built. See `BUILD_PLAN.md` for the full
phase-by-phase build log.
