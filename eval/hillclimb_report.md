# Hillclimb report — tightening the pipeline's prompts against 5 hard designs

Methodology: 5 complicated system-design scenarios written by hand
(`reference_designs.md`), each with a list of "hard parts" a strong design must get
right and what a weak design typically gets wrong. Each scenario was run through the
real app (local Ollama `qwen3-coder-16k`), compared against the reference, and any
generalizable gap found was fixed in the shared prompts (`backend/prompts/*.txt`) -
not per-scenario hacks, since all scenarios share the same Architect/Security/
Reliability/review prompts. Later scenarios were run against the already-improved
prompts, so fixes compound. Raw runs are in `runs/<scenario>/round*/result.json`.

## What got fixed, in the order it was found

1. **REST-endpoint-for-real-time-input anti-pattern** (found in scenario 1, multiplayer
   game). The Architect designed `POST /matches/{id}/input` for 100-player, 20-30Hz
   input - a protocol mismatch none of the four review agents caught either. Fixed by
   telling the Architect to match API transport to the actual frequency/latency the
   brief implies (WebSocket/gRPC/UDP when many updates/sec are implied, not a default
   REST verb), and telling the Critic to specifically check for this pattern.
   **Verified fixed** in the round-2 regeneration (a dedicated WebSocket component
   appeared) and **confirmed generalizing** in every later scenario - ride-hailing's
   `WS /ws/trip/{trip_id}` + `GRPC /drivers/location-stream`, the rate limiter's
   correctly-REST config APIs (this scenario has no real-time channel, and none was
   invented), and the collaborative editor's 4-for-4 `WS` endpoints.

2. **Auth-boundary violation** (scenario 1). The Architect built a "Token Refresh
   Service" component and duplicate `/auth/refresh` + `/auth/token/refresh` endpoints
   despite being told not to design auth. Fixed by strengthening the instruction to
   forbid even lightweight auth/session/token fields or endpoints anywhere in the
   Architect's output. **Verified fixed** in round 2 - no auth component, no auth
   endpoints, appeared correctly instead in the Security Architect's output where it
   belongs.

3. **Missing concurrency-safety mechanism for race-prone resource claims** (scenario 2,
   ride-hailing). The Driver Matcher described "optimized matching" but never said what
   stops two riders claiming the same driver simultaneously. Fixed by requiring the
   Architect to name the actual mechanism (atomic claim / optimistic lock / single-
   writer-per-shard) whenever concurrent actors compete for a limited resource.
   **Verified fixed** in round 2 ("sharded assignment queue... eliminates distributed
   locking contention") and **confirmed generalizing** to scenario 4's transcoding-slot
   allocation ("atomic claims... optimistic lock with retry") and scenario 5's document
   writes ("only one [component] that can modify document state directly... atomic
   operations").

4. **Verbatim repetition of the same scale/budget/availability sentence across
   different components** (scenario 2). Fixed by telling the Architect to state a given
   numeric constraint once, at the component where it's the deciding factor.
   **Verified fixed** - zero verbatim hits in the round-2 regeneration, vs. the same
   sentence appearing in 2+ component descriptions before.

5. **Within-component rambling** - not verbatim repetition, but the same 4-5 ideas
   restated in different words across many sentences, producing 2,000+ character
   descriptions that were mostly padding (scenario 3, rate limiter - one description
   alone ran to ~2,500 characters). Fixed by telling the Architect to stop once it
   notices it's rephrasing something already said. **Verified fixed dramatically** in
   scenario 3's regeneration - the same component dropped from ~2,500 to 681 characters
   while gaining real content (see #6). **Partially held** in scenario 4 (~1,100-1,300
   chars, moderate) and **regressed** in scenario 5, where the Document Engine
   description hit 2,094 characters and contained the *exact same sentence twice*
   verbatim ("This component is the only one that can modify document state directly,
   ensuring consistency through atomic operations.") - a variant of the repetition
   problem the existing instruction didn't fully cover. A follow-up fix (#7) was applied
   but not re-verified before this report was written - see Residual gaps.

6. **No named low-level mechanism for the actual bottleneck** (scenario 3). The first
   rate-limiter draft described desirable outcomes ("handles 500K req/s", "low
   latency") without naming how - no sliding-window-vs-token-bucket decision, no
   sharding scheme, no atomicity mechanism for the counter itself. This was addressed
   as a side effect of fix #5 (forcing density over restatement) - the round-2 version
   named "consistent hashing with virtual nodes to prevent hotspots" (sharding) and
   "lock-free atomic operations (compare-and-swap)" (the exact mechanism my reference
   asked for) unprompted.

7. **Hedging between two named approaches instead of committing to one** (scenario 5).
   The Document Engine said "hybrid approach of OT for simple edits and CRDT for
   complex structural changes" without a precise rule for which case gets which - my
   reference specifically warns that "edits get merged" without naming one real
   algorithm and justifying it isn't a real answer, and a vague hybrid is the same
   failure in a more sophisticated-sounding wrapper. Fixed by telling the Architect
   that when two established approaches could both work, pick one and justify it - a
   "hybrid" is only legitimate with a precise dividing rule. **Applied, not yet
   re-verified** - see Residual gaps.

## Fail-open / fail-closed - tried, did not land

Scenario 3's brief (`must not become the single point of failure`) is exactly the kind
of decision the source doc's Section 8 principle is about, and my reference explicitly
wants a named fail-open/fail-closed choice. Added an instruction ("name which failure
behavior was chosen... don't describe only the desirable outcome"); the round-2
regeneration still never said the words "fail-open" or "fail-closed" anywhere, despite
picking up every other fix from the same edit. Left in the prompt since it's a correct
instruction and may generalize on scenarios where the trade-off is more forced, but
it's a confirmed miss on this specific scenario worth knowing about rather than a
quiet success.

## Per-scenario summary

| # | Scenario | Round-1 findings | Real gaps found | Fixed & verified |
|---|---|---|---|---|
| 1 | Multiplayer game | 21 | REST-vs-realtime API; auth-boundary violation | Both, round 2 |
| 2 | Ride-hailing | 18 | No concurrency-safety mechanism; verbatim repetition | Both, round 2 |
| 3 | Rate limiter | 18 → 20 (2nd attempt) | Extreme within-component rambling; no fail-open/closed decision | Rambling fixed (round 2); fail-open/closed not fixed |
| 4 | Video streaming | 21 | VOD/live forced into one generic component (same class of bug as #1, different domain) | Fix applied, not re-verified (time budget) |
| 5 | Collaborative editor | 20 | Verbatim self-repetition within one description; hedged OT/CRDT choice | Fixes applied, not re-verified (time budget) |

Review-agent finding counts stayed roughly flat (18-22) across every scenario and
round, including after fixes. That's expected, not a failure of the fixes: these are
genuinely hard systems with real depth to find fault with, and the review agents
verifiably catch real things throughout (e.g. scenario 1's Reliability Agent correctly
caught an RTO/RPO inconsistency against the stated availability target - the same class
of thing Phase 5's deterministic check independently verifies). The count was never a
reliable proxy for "is the design good" on its own; the qualitative fixes above (a
severe protocol mismatch, a scope violation, a missing concurrency mechanism, a hedge
instead of a decision) are the real signal, and all five were things a senior reviewer
would flag as more serious than typical review noise.

## Addendum, 2026-09-16: prompts rewritten to be extensive + industry-standard-grounded

Per explicit direction, all 11 prompts were rewritten from short rule-lists into fuller
playbooks grounded in real frameworks each agent's role actually corresponds to in
production practice — C4-style component thinking and Nygard-format ADRs for the
Architect, STRIDE + OWASP-style threat framing for Security, SRE error-budget math +
the standard DR-tier taxonomy (backup-restore / pilot-light / warm-standby /
multi-site-active-active) for Reliability, FinOps unit-economics framing for Cost,
pre-mortem/red-team framing for the Critic. Every fix from the sections above was kept
and folded into the new prompts, not lost in the rewrite.

Re-verified on the rate-limiter scenario (round 3, the scenario with the most known
residual issues) rather than re-running all five, given time already spent:
**components dropped to 335-546 characters each (7 components, tightest yet)**, and the
DR-tier vocabulary produced a real, correct answer unprompted - "Multi-site
active-active strategy... RTO reduced... aligning with the 99.99% availability target"
with consistent RPO math from the stated backup frequency. Security controls came back
with named real mechanisms (mTLS with short-lived certs via a managed PKI, OAuth2
client-credentials with a tenant-ID claim binding, RBAC with named roles plus
ownership-based checks) - the deepest, most concrete output yet across the whole
exercise. One small residual: two adjacent sentences in the `authorization` field
restated the same ownership-check idea - a minor instance of the repetition problem,
much reduced but not fully eliminated. **Fail-open/fail-closed still isn't named
explicitly**, even after moving that instruction to the Reliability Architect
specifically (a more natural home for it) - confirmed still open, not fixed by
relocation alone.

## Residual gaps (honest, not swept under the rug)

- **Fail-open/fail-closed** still doesn't get named explicitly even when the brief
  practically demands it (scenario 3).
- **Scenario 4 and 5's fixes (#5-cont'd, #7) were applied but not re-verified** with a
  regeneration before this report - time budget for this exercise ran out after 5
  scenarios × up to 2 rounds each (each round is a real ~2-4 minute, up to ~20-call
  pipeline run). Recommended next step if this continues: regenerate scenarios 4 and 5
  once more to confirm.
- **Within-component exact-sentence duplication** (found once, in scenario 5) may be a
  narrower case of the broader rambling problem, or may need its own explicit rule if
  it recurs - worth watching on the next run rather than assuming #7's fix fully covers
  it.
- This was one model (`qwen3-coder-16k`, local) at `MAX_REVISION_ROUNDS=2`. Whether
  these same prompts hold up on Gemini, or need retuning per-provider, hasn't been
  tested - no `GEMINI_API_KEY` was configured in this environment.
