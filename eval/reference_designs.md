# Reference designs — hillclimb eval set

5 hard system-design scenarios, written by hand (no app involved) as the comparison
target for tightening the pipeline's prompts. Each covers the core architecture, the
non-obvious hard parts a junior design misses, and what a review agent *should* catch
if the app's design is weak there. Briefs given to the app are in `runs/*/brief.json`;
results and per-round notes in `runs/*/notes.md`.

---

## 1. Real-time multiplayer game backend

**Brief given to the app:** "A backend for a real-time multiplayer battle-royale game.
100 players per match, authoritative server simulation, must feel responsive worldwide."
Users: players (mobile + PC), game studio ops. Traffic: 50,000 concurrent matches at
peak. Budget: $80,000/month. Availability: 99.95%. Constraints: server-authoritative
(no client trust), sub-100ms perceived input latency.

**The hard parts a strong design must get right:**
- **Authoritative simulation, not just message relay.** Each match needs a dedicated
  game-server process (not a shared stateless service) running a fixed-tick simulation
  loop (e.g. 20-30Hz), validating every client input server-side before applying it -
  the client is never trusted for hit detection or position.
- **Regional matchmaking + server placement.** Players get matched *and* placed onto a
  game-server instance in their region *before* the match starts - matchmaking and
  server allocation are two different concerns that a naive design conflates. A queue
  service picks players; an orchestrator (like Agones/a custom fleet manager) allocates
  a warm game-server process per match, not a cold container spin-up (which blows the
  latency budget).
- **State sync is delta + client-side prediction, not full-state broadcast.** 100 players
  x full state every tick is bandwidth-infeasible. Real answer: interest management
  (only sync entities near the player), delta compression, client-side prediction with
  server reconciliation (rollback) to hide latency.
- **A match is a stateful, ephemeral, single-writer process** - this breaks the reflex
  to put everything behind a horizontally-scaled stateless API + shared DB. The match
  data model lives in the game-server's memory for the match duration; only the *result*
  (final stats, rankings) is persisted afterward.
- **Anti-cheat is a server-side validation concern**, not a bolt-on - speed/teleport
  checks, rate limits on actions, replay-based post-match anomaly detection.
- **Failure mode that matters most:** a game-server process crashing mid-match. Needs
  state checkpointing (periodic snapshot to a fast store) so a match can migrate to a
  fresh process, not just "the match dies and 100 players get nothing."

**What a weak design typically does wrong:** treats it like a normal CRUD API (stateless
services + Postgres for live match state), broadcasts full world state every tick,
matches players without considering server region/placement, trusts client-reported
positions, has no answer for a mid-match server crash.

---

## 2. Ride-hailing dispatch system

**Brief given to the app:** "A ride-hailing dispatch platform - riders request a ride,
available drivers get matched by proximity, trip runs with live location tracking,
pricing adjusts with demand." Users: riders, drivers, ops/support. Traffic: 2M rides/day,
150K concurrent active trips at peak in a city. Budget: $120,000/month. Availability:
99.95%. Constraints: driver locations update every 3-5s, matching decision must complete
in under 2 seconds.

**The hard parts a strong design must get right:**
- **Geospatial indexing at speed, not a naive lat/lng table scan.** Needs a real
  geospatial index (H3/S2 cells, or Redis GEO / a geo-index in the primary store) so
  "nearest available drivers" is a fast lookup, not `WHERE distance < X` over the whole
  drivers table. Driver location updates are extremely high write volume (every driver,
  every few seconds) - this has to be a write-optimized path (in-memory / geo-indexed
  cache), not hitting the primary transactional DB per ping.
- **Matching is a claim/lock problem, not a simple assignment.** Two riders can't be
  matched to the same driver - the match step needs an atomic claim (optimistic lock,
  or a single-writer matching service per geo-cell) to avoid a race where two dispatch
  workers assign the same driver simultaneously.
- **Trip state machine with strong consistency where money is involved**, eventual
  consistency elsewhere. Trip status transitions (requested -> matched -> in-progress ->
  completed -> paid) need a real state machine with idempotent transitions (a driver's
  spotty connection retrying an update shouldn't double-charge or double-complete a trip).
  Live location trail during the trip can be eventually consistent / best-effort.
- **Surge pricing needs its own computation path** - a demand/supply ratio per geo-cell,
  computed on a short interval, cached and read by both the rider-facing quote and the
  matching service, not recomputed per-request from raw data.
- **Failure mode that matters most:** the matching service or a geo-shard going down
  mid-region. Design needs to say what happens to in-flight match attempts and how
  driver-location freshness is protected from a single point of failure (partition the
  geo-index by region/shard, not one global instance).

**What a weak design typically does wrong:** stores driver location in the primary
Postgres table and queries it directly for "nearby," has no explicit claim/lock step for
matching (silently assumes it "just works"), treats trip-state updates and payment with
the same consistency model, computes surge synchronously per request.

---

## 3. Distributed rate limiter for a multi-tenant API platform

**Brief given to the app:** "A rate-limiting layer for a multi-tenant API platform -
every tenant gets a configurable requests-per-minute quota, enforced consistently across
many stateless API gateway nodes, with per-endpoint override limits." Users: platform
tenants (API consumers), platform ops. Traffic: 500,000 requests/sec across all tenants,
thousands of tenants. Budget: $15,000/month. Availability: 99.99% (it's in the hot path
of every request). Constraints: a rate-limit decision must add under 5ms p99 latency;
must not become the single point of failure for the whole platform.

**The hard parts a strong design must get right:**
- **The core problem is a distributed counter, and the algorithm choice is the whole
  design.** Fixed windows are simple but allow 2x burst at window boundaries. Sliding
  window log is accurate but memory-expensive per key. The real answer for this scale
  is a **sliding window counter (weighted average of current + previous fixed window)**
  or a **token bucket held in a fast shared store (Redis)** with an atomic
  check-and-decrement (a Lua script or Redis `CL.THROTTLE`/similar, not
  read-then-write from the gateway, which races).
- **500K req/s of counter increments cannot hit a single Redis instance.** Needs
  sharding (consistent hashing by tenant+endpoint key across a Redis cluster) and the
  gateway nodes need a local fast-path: an in-memory approximate counter with periodic
  sync to the shared store, trading a little accuracy for avoiding a network round-trip
  on every single request (the 5ms budget effectively forces this).
- **Fail-open vs fail-closed is an explicit decision, not an afterthought** - if the
  shared rate-limit store is unreachable, does traffic get rejected (fail-closed,
  protects backends but takes the platform down with the rate limiter) or allowed
  through (fail-open, protects availability but a tenant could burst past their quota
  during the outage)? A strong design states this explicitly and default to fail-open
  with a tighter *local* fallback limit, given the stated 99.99% availability target.
- **Per-endpoint override on top of per-tenant quota is two dimensions of keying**, not
  one - the design needs to say how override configs propagate to gateway nodes without
  a lookup on every request (pushed/cached config, not a DB read per request).
- **Failure mode that matters most:** the rate-limit store itself becomes a bottleneck
  or SPOF for 500K req/s of traffic it's supposed to be protecting other services from.

**What a weak design typically does wrong:** does a synchronous read-then-write against
a single Redis instance per request (races, and a single point of failure at 500K
req/s), uses a naive fixed-window counter without addressing the boundary-burst problem,
never states fail-open vs fail-closed, ignores the "under 5ms" constraint entirely when
picking the algorithm.

---

## 4. Global video streaming platform (live + VOD)

**Brief given to the app:** "A video platform - creators upload video (VOD) or go live,
viewers watch on any device/network quality worldwide, video must adapt to the viewer's
bandwidth." Users: creators, viewers, platform ops. Traffic: 5,000 concurrent live
streams at peak, 2M concurrent VOD viewers, global audience. Budget: $200,000/month.
Availability: 99.9% for VOD, 99.95% for live (an outage during a live stream is worse).
Constraints: adaptive bitrate required, live latency target under 10 seconds glass-to-glass.

**The hard parts a strong design must get right:**
- **VOD and live are different pipelines that happen to share storage/CDN**, not one
  pipeline - a design that tries to force both through the same ingest/transcode path
  will get the latency budget wrong for live. VOD: upload -> async transcode into
  multiple renditions (ABR ladder) -> store as HLS/DASH segments -> CDN. Live: ingest
  (RTMP/SRT) -> **real-time** transcode into the same ABR ladder with segments short
  enough for the latency target (e.g. 2s HLS segments, or LL-HLS/WebRTC if sub-3s is
  ever needed) -> origin -> CDN, continuously as the stream runs, not after it ends.
- **Adaptive bitrate is a client-side decision fed by a server-prepared ladder** - the
  design needs to specify multiple renditions (resolution/bitrate pairs) actually get
  produced (a transcoding fleet, likely GPU-accelerated at this concurrency, with a job
  queue - not "the server converts the video" as a black box), and that the player uses
  a manifest (HLS/DASH) to switch renditions based on measured bandwidth.
- **CDN + origin shield is not optional at this scale** - 2M concurrent VOD viewers
  cannot be served from an origin directly; needs a CDN with an origin-shield layer so
  the transcode/storage tier only serves cache misses, not 2M simultaneous origin
  requests.
- **Live-specific reliability:** an availability target of 99.95% *for live* implies the
  transcode pipeline for an in-progress stream needs redundancy (a failed transcoder
  mid-stream can't mean the stream drops for viewers) - this is a genuinely different
  reliability problem than VOD, where a transient failure just means a retry before
  anyone's watching.
- **Failure mode that matters most:** a transcoding node failing mid-live-stream, or a
  regional CDN edge failing during a popular live event (thundering herd onto the next
  edge/origin-shield).

**What a weak design typically does wrong:** treats live and VOD as the same pipeline
with "process the video" as a black box, doesn't mention a CDN/origin-shield layer at
all for 2M concurrent viewers, states "adaptive bitrate" without describing where the
multiple renditions actually come from, has no specific answer for live-stream transcoder
failure mid-broadcast.

---

## 5. Collaborative real-time document editor

**Brief given to the app:** "A collaborative document editor - many users edit the same
document simultaneously and see each other's changes live, must work with brief network
drops (edits queue and reconcile on reconnect)." Users: teams co-editing documents.
Traffic: 500,000 documents with active concurrent editors, up to 50 simultaneous editors
per document. Budget: $40,000/month. Availability: 99.9%. Constraints: edits must
converge to the same final document for everyone regardless of order/network timing; no
data loss on a brief disconnect.

**The hard parts a strong design must get right:**
- **This is fundamentally a conflict-resolution algorithm problem, not a sync-protocol
  problem** - the core decision is **CRDTs (e.g. a sequence CRDT like RGA/Yjs's
  algorithm) or Operational Transformation (OT)**, and the design needs to actually pick
  one and justify it (CRDTs are generally easier to reason about for peer-to-peer/offline
  merge and don't need a central transform server; OT is what Google Docs historically
  used and needs a central server to transform concurrent ops against each other in the
  right order). "Edits get merged" without naming the algorithm is not a real answer to
  this brief.
- **A per-document single sequencer, not a shared stateless API + shared DB for live
  edits.** Similar to the game-server insight in scenario 1 - each actively-edited
  document needs a process/actor that holds the authoritative current CRDT/OT state in
  memory and broadcasts ops to connected editors (WebSocket), with periodic persistence
  (snapshot + op log) to the durable store - not every keystroke round-tripping through
  a stateless API to a relational DB.
- **Reconnection/offline needs an explicit op-log + vector-clock (or CRDT-native)
  reconciliation story** - client buffers local ops while offline, and on reconnect
  either replays them against a CRDT (which merges automatically by construction) or
  needs an OT-specific rebase-against-server-history step. A design that just says
  "syncs on reconnect" hasn't actually solved the stated constraint.
- **Presence (cursors, who's editing what) is a separate, lossy, ephemeral channel** -
  it must not go through the same durable-persistence path as document content; it's
  fine to lose a cursor position on a hiccup, it is not fine to lose an edit.
- **Failure mode that matters most:** the per-document sequencer process crashing with
  edits still in memory not yet persisted - needs a short persistence interval (or
  persist-on-every-op to a fast log) so the durability window is small and bounded.

**What a weak design typically does wrong:** says "real-time sync via WebSockets" without
naming a conflict-resolution algorithm at all, routes every edit through a stateless API
to a relational DB per keystroke, has no specific mechanism for offline-queued edits
beyond "it syncs when back online," conflates presence data with document content in the
same persistence/consistency model.
