// AI Technical Architect — Phase 1 frontend, talking to the real Phase 1/2
// backend (FastAPI + Requirements/Architect agents, provider-switchable).

const BACKEND_URL = "http://127.0.0.1:8070";

const EXAMPLE_BRIEF = {
  idea: "A booking platform for small clinics and service businesses (salons, consultants) to manage appointments and take payments online.",
  users: "Small clinics and service businesses in India, and their customers",
  traffic: "100,000 monthly active users",
  budget: "₹25,000/month",
  availability: "99.9%",
  cloud: "",
  stage: "",
  constraints: "Must support UPI payments; mobile-first",
};

const PROVIDER_LABELS = { gemini: "Gemini", ollama: "Ollama (local)" };

let healthInfo = null;
let lastResult = null;

function $(id) {
  return document.getElementById(id);
}

function fillList(id, items) {
  const el = $(id);
  el.innerHTML = "";
  items.forEach((text) => {
    const li = document.createElement("li");
    li.textContent = text;
    el.appendChild(li);
  });
}

function renderApis(id, apis) {
  const el = $(id);
  el.innerHTML = "";
  apis.forEach((api) => {
    const li = document.createElement("li");
    const method = document.createElement("span");
    method.className = "method";
    method.textContent = api.method;
    const rest = document.createElement("span");
    rest.textContent = `${api.path} — ${api.desc}`;
    li.appendChild(method);
    li.appendChild(rest);
    el.appendChild(li);
  });
}

function renderDecisions(id, decisions) {
  const el = $(id);
  el.innerHTML = "";
  decisions.forEach((d) => {
    const wrap = document.createElement("div");
    wrap.className = "adr";
    const decision = document.createElement("span");
    decision.className = "adr-decision";
    const idBadge = document.createElement("span");
    idBadge.className = "id-badge";
    idBadge.textContent = d.id;
    decision.appendChild(idBadge);
    decision.appendChild(document.createTextNode(d.decision));
    wrap.appendChild(decision);
    [
      ["Alternatives considered", d.alternatives_considered],
      ["Trade-offs", d.trade_offs],
      ["Rationale", d.rationale],
    ].forEach(([label, value]) => {
      const field = document.createElement("span");
      field.className = "adr-field";
      const strong = document.createElement("strong");
      strong.textContent = `${label}: `;
      field.appendChild(strong);
      field.appendChild(document.createTextNode(value));
      wrap.appendChild(field);
    });
    el.appendChild(wrap);
  });
}

function renderDataModels(id, models) {
  const el = $(id);
  el.innerHTML = "";
  models.forEach((m) => {
    const wrap = document.createElement("div");
    wrap.className = "adr";
    const name = document.createElement("span");
    name.className = "adr-decision";
    name.textContent = m.entity;
    wrap.appendChild(name);
    const fields = document.createElement("span");
    fields.className = "adr-field";
    fields.textContent = `Fields: ${m.fields.join(", ")}`;
    wrap.appendChild(fields);
    if (m.notes) {
      const notes = document.createElement("span");
      notes.className = "adr-field";
      notes.textContent = m.notes;
      wrap.appendChild(notes);
    }
    el.appendChild(wrap);
  });
}

function renderSpecList(id, entries) {
  const el = $(id);
  el.innerHTML = "";
  entries.forEach(([label, value]) => {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    el.appendChild(dt);
    el.appendChild(dd);
  });
}

const STAGE_MATCH = { mvp: "mvp", growth: "growth", large_scale: "large scale" };

function renderArchStages(stages, requestedStage) {
  const el = $("archStagesBody");
  el.innerHTML = "";
  const wantedText = STAGE_MATCH[requestedStage] || null;
  stages.forEach((s) => {
    const tr = document.createElement("tr");
    if (wantedText && s.stage.toLowerCase().includes(wantedText)) {
      tr.classList.add("stage-current");
    }
    [s.stage, s.characteristics, s.purpose, s.transition_trigger].forEach((text) => {
      const td = document.createElement("td");
      td.textContent = text;
      tr.appendChild(td);
    });
    el.appendChild(tr);
  });
}

function renderValidation(checks) {
  const el = $("validationList");
  el.innerHTML = "";
  checks.forEach((c) => {
    const li = document.createElement("li");
    const cls = c.status === "pass" ? "check-pass" : c.status === "fail" ? "check-fail" : "check-skip";
    li.className = cls;
    li.textContent = `${c.check}: ${c.detail}`;
    el.appendChild(li);
  });
}

function renderBlueprint(blueprint) {
  const risksEl = $("blueprintRisks");
  risksEl.innerHTML = "";
  blueprint.risks.forEach((r) => {
    const li = document.createElement("li");
    const idBadge = document.createElement("span");
    idBadge.className = "id-badge";
    idBadge.textContent = r.id;
    const status = document.createElement("span");
    status.className = `status-badge status-${r.status}`;
    status.textContent = r.status;
    const severity = document.createElement("span");
    severity.className = `finding-status severity-${r.severity}`;
    severity.textContent = r.severity;
    li.appendChild(idBadge);
    li.appendChild(status);
    li.appendChild(severity);
    li.appendChild(document.createTextNode(`${r.risk} (source: ${r.source})`));
    risksEl.appendChild(li);
  });
  if (blueprint.risks.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No risks carried into the final blueprint.";
    risksEl.appendChild(li);
  }

  const roadmapEl = $("blueprintRoadmap");
  roadmapEl.innerHTML = "";
  blueprint.roadmap.forEach((r) => {
    const li = document.createElement("li");
    li.textContent = r.step;
    if (r.addresses_risk_ids && r.addresses_risk_ids.length > 0) {
      const tag = document.createElement("span");
      tag.className = "id-badge";
      tag.textContent = `addresses ${r.addresses_risk_ids.join(", ")}`;
      li.appendChild(document.createTextNode(" "));
      li.appendChild(tag);
    }
    roadmapEl.appendChild(li);
  });
}

function renderChangelog(changelog) {
  const el = $("revisionChangelog");
  el.innerHTML = "";
  if (!changelog || changelog.length === 0) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  changelog.forEach((round) => {
    const heading = document.createElement("h4");
    heading.textContent = `Round ${round.round} changes`;
    el.appendChild(heading);
    const ul = document.createElement("ul");
    round.changes.forEach((c) => {
      const li = document.createElement("li");
      li.textContent = `${c.finding_area}: ${c.mechanism_added} (${c.components_affected.join(", ")})`;
      ul.appendChild(li);
    });
    el.appendChild(ul);
  });
}

// The changelog above is the revise agent's *claim* about what it changed;
// this renders the actual before/after text for the fields that really did
// change between rounds, computed client-side from the architecture snapshot
// the backend now keeps per round (review.architecture_history).
const DIFF_TEXT_FIELDS = [
  ["infrastructure", "Infrastructure"],
  ["security_controls.threat_model_summary", "Threat model"],
  ["security_controls.authentication", "Authentication"],
  ["security_controls.authorization", "Authorization"],
  ["security_controls.iam", "IAM"],
  ["security_controls.network_boundaries", "Network boundaries"],
  ["security_controls.secrets_and_encryption", "Secrets & encryption"],
  ["security_controls.abuse_prevention", "Abuse prevention"],
  ["security_controls.input_validation", "Input validation"],
  ["reliability_design.scaling_strategy", "Scaling strategy"],
  ["reliability_design.reliability", "Reliability"],
  ["reliability_design.disaster_recovery", "Disaster recovery"],
  ["reliability_design.observability", "Observability"],
];

function _getPath(obj, path) {
  return path.split(".").reduce((o, k) => (o ? o[k] : undefined), obj);
}

// Array fields worth a real per-entry diff, not just a count - keyed by a
// stable id/name so an entry that only got its text edited (not added or
// removed) still shows up as a change, matched to its own before/after.
const DIFF_ARRAY_FIELDS = [
  ["components", "name", (c) => c.description, "Component"],
  ["decisions", "id", (d) => `${d.decision}\n\nTrade-offs: ${d.trade_offs}\n\nRationale: ${d.rationale}`, "Decision"],
];

function _diffKeyedArray(beforeArr, afterArr, keyField, textFn) {
  const beforeMap = new Map((beforeArr || []).map((x) => [x[keyField], x]));
  const afterMap = new Map((afterArr || []).map((x) => [x[keyField], x]));
  const keys = new Set([...beforeMap.keys(), ...afterMap.keys()]);
  const entries = [];
  keys.forEach((key) => {
    const b = beforeMap.get(key);
    const a = afterMap.get(key);
    const bText = b ? textFn(b) : null;
    const aText = a ? textFn(a) : null;
    if (bText !== aText) entries.push({ key, before: bText, after: aText });
  });
  return entries;
}

function _appendDiffBlock(el, label, beforeText, afterText) {
  const wrap = document.createElement("div");
  wrap.className = "diff-field";
  const labelEl = document.createElement("div");
  labelEl.className = "diff-field-label";
  labelEl.textContent = label;
  wrap.appendChild(labelEl);

  const grid = document.createElement("div");
  grid.className = "diff-before-after";
  const beforeEl = document.createElement("div");
  beforeEl.className = "diff-before";
  beforeEl.textContent = beforeText || "(not present before this round)";
  const afterEl = document.createElement("div");
  afterEl.className = "diff-after";
  afterEl.textContent = afterText || "(removed this round)";
  grid.appendChild(beforeEl);
  grid.appendChild(afterEl);
  wrap.appendChild(grid);
  el.appendChild(wrap);
}

function renderRevisionDiff(architectureHistory) {
  const el = $("revisionDiff");
  el.innerHTML = "";
  if (!architectureHistory || architectureHistory.length < 2) {
    el.hidden = true;
    return;
  }

  for (let i = 1; i < architectureHistory.length; i++) {
    const before = architectureHistory[i - 1];
    const after = architectureHistory[i];

    const changedFields = DIFF_TEXT_FIELDS.filter(
      ([path]) => _getPath(before, path) !== _getPath(after, path)
    );
    const arrayDiffs = DIFF_ARRAY_FIELDS.map(([key, keyField, textFn, label]) => ({
      label,
      entries: _diffKeyedArray(before[key], after[key], keyField, textFn),
    })).filter((d) => d.entries.length > 0);
    const countOnlyChanges = ["data_models", "apis"]
      .filter((key) => JSON.stringify(before[key] || []) !== JSON.stringify(after[key] || []))
      .map((key) => `${key} (${(before[key] || []).length} → ${(after[key] || []).length} entries)`);

    if (changedFields.length === 0 && arrayDiffs.length === 0 && countOnlyChanges.length === 0) continue;

    const heading = document.createElement("h4");
    heading.textContent = `Round ${i} — before → after`;
    el.appendChild(heading);

    if (countOnlyChanges.length > 0) {
      const note = document.createElement("p");
      note.className = "diff-field-label";
      note.style.marginBottom = "10px";
      note.textContent = `Also changed: ${countOnlyChanges.join(", ")}`;
      el.appendChild(note);
    }

    changedFields.forEach(([path, label]) => {
      _appendDiffBlock(el, label, _getPath(before, path), _getPath(after, path));
    });

    arrayDiffs.forEach(({ label, entries }) => {
      entries.forEach(({ key, before: b, after: a }) => {
        _appendDiffBlock(el, `${label}: ${key}`, b, a);
      });
    });
  }

  el.hidden = !el.hasChildNodes();
}

// Draws a simple left-to-right chain of boxes from a component list — the same
// visual grammar as the hero schematic, applied to whatever came out of the run.
function renderSchematic(svgEl, components) {
  const ns = "http://www.w3.org/2000/svg";
  svgEl.innerHTML = "";
  const n = components.length;
  const boxW = 110;
  const boxH = 56;
  const gap = (760 - n * boxW) / (n + 1);
  const y = 42;

  components.forEach((c, i) => {
    const x = gap + i * (boxW + gap);

    if (i > 0) {
      const prevX = gap + (i - 1) * (boxW + gap) + boxW;
      const line = document.createElementNS(ns, "line");
      line.setAttribute("class", "line");
      line.setAttribute("x1", prevX);
      line.setAttribute("y1", y + boxH / 2);
      line.setAttribute("x2", x);
      line.setAttribute("y2", y + boxH / 2);
      svgEl.appendChild(line);
    }

    const rect = document.createElementNS(ns, "rect");
    rect.setAttribute("class", "box");
    rect.setAttribute("x", x);
    rect.setAttribute("y", y);
    rect.setAttribute("width", boxW);
    rect.setAttribute("height", boxH);
    svgEl.appendChild(rect);

    const label = document.createElementNS(ns, "text");
    label.setAttribute("x", x + boxW / 2);
    label.setAttribute("y", y + boxH / 2 + 4);
    label.setAttribute("text-anchor", "middle");
    label.textContent = c.name.length > 16 ? c.name.slice(0, 14) + "…" : c.name;
    svgEl.appendChild(label);
  });
}

// These are all still-open findings against the final architecture (the pipeline
// already ran one revision attempt against earlier rounds) — badge by severity,
// not resolved/open, since everything shown here is currently unresolved.
function renderFindings(id, findings) {
  const el = $(id);
  el.innerHTML = "";
  findings.forEach((f) => {
    const li = document.createElement("li");
    const status = document.createElement("span");
    status.className = `finding-status severity-${f.severity}`;
    status.textContent = f.severity;
    li.appendChild(status);
    li.appendChild(document.createTextNode(`${f.area}: ${f.issue} — ${f.recommendation}`));
    el.appendChild(li);
  });
  if (findings.length === 0) {
    const li = document.createElement("li");
    li.textContent = "Nothing flagged.";
    el.appendChild(li);
  }
}

function renderReview(review) {
  renderFindings("reviewSecurity", review.security.findings);
  renderFindings("reviewReliability", review.reliability.findings);
  renderFindings("reviewCritic", review.critic.findings);
  renderFindings("reviewCost", review.cost.findings);

  $("costSummary").textContent = review.cost.estimate_summary;
  const tag = $("costBudgetTag");
  tag.textContent = review.cost.within_budget ? "within budget" : "over budget";
  tag.className = review.cost.within_budget ? "within" : "over";

  const total = review.resolved_count + review.open_count;
  $("revisionStatus").textContent =
    total === 0
      ? "No revision needed — the first architecture cleared review with no findings."
      : `${review.revision_rounds} review round${review.revision_rounds > 1 ? "s" : ""} — ` +
        `${review.resolved_count} of ${total} concerns addressed in revision, ` +
        `${review.open_count} remain open and are reported rather than hidden.`;
}

function renderResult(result) {
  const req = result.requirements;
  const arch = result.architecture;

  $("reqProductUnderstanding").textContent = req.product_understanding;
  fillList("reqUseCases", req.users_and_use_cases);
  fillList("reqFunctional", req.functional);
  fillList("reqNonFunctional", req.non_functional);
  fillList("reqAssumptions", req.assumptions);
  fillList("reqOpenQuestions", req.open_questions);

  fillList(
    "archComponents",
    arch.components.map((c) => `${c.name} — ${c.description}`)
  );
  renderApis("archApis", arch.apis);
  renderDataModels("archDataModels", arch.data_models);
  $("archInfra").textContent = arch.infrastructure;
  renderDecisions("archDecisions", arch.decisions);
  renderSchematic($("outputSchematic"), arch.components);

  const sc = arch.security_controls;
  renderSpecList("securityControls", [
    ["Threat model", sc.threat_model_summary],
    ["Authentication", sc.authentication],
    ["Authorization", sc.authorization],
    ["IAM", sc.iam],
    ["Network boundaries", sc.network_boundaries],
    ["Secrets / encryption", sc.secrets_and_encryption],
    ["Abuse prevention", sc.abuse_prevention],
    ["Input validation", sc.input_validation],
  ]);

  const rd = arch.reliability_design;
  renderSpecList("reliabilityDesign", [
    ["Scaling strategy", rd.scaling_strategy],
    ["Reliability", rd.reliability],
    ["Disaster recovery", rd.disaster_recovery],
    ["Observability", rd.observability],
  ]);
  fillList("failureScenarios", rd.failure_scenarios);

  renderArchStages(result.architecture_stages, $("stage").value);
  renderReview(result.review);
  renderChangelog(result.review.changelog);
  renderRevisionDiff(result.review.architecture_history);
  renderBlueprint(result.blueprint);
  renderValidation(result.validation);
  $("refineBtn").disabled = false;
}

function setBanner(text, isError) {
  const banner = $("resultBanner");
  banner.textContent = text;
  banner.classList.toggle("banner-error", !!isError);
}

async function loadHealth() {
  const select = $("providerSelect");
  const status = $("providerStatus");
  try {
    const res = await fetch(`${BACKEND_URL}/api/health`);
    if (!res.ok) throw new Error(`backend returned ${res.status}`);
    healthInfo = await res.json();
  } catch (err) {
    select.innerHTML = "";
    status.textContent = `Backend not reachable at ${BACKEND_URL} — start it with: cd backend && python -m uvicorn main:app --reload --port 8070`;
    status.classList.add("status-bad");
    $("generateBtn").disabled = true;
    $("backendStatus").textContent = "Unreachable";
    return;
  }

  $("backendStatus").textContent = "Live — 10 agents";
  select.innerHTML = "";
  const providers = healthInfo.providers;
  let anyConfigured = false;

  Object.keys(PROVIDER_LABELS).forEach((key) => {
    const info = providers[key];
    const option = document.createElement("option");
    option.value = key;
    option.textContent = info.configured
      ? `${PROVIDER_LABELS[key]} — ${info.model}`
      : `${PROVIDER_LABELS[key]} — not configured`;
    option.disabled = !info.configured;
    if (info.configured) anyConfigured = true;
    select.appendChild(option);
  });

  const defaultProvider = healthInfo.default_provider;
  if (providers[defaultProvider] && providers[defaultProvider].configured) {
    select.value = defaultProvider;
  } else {
    const firstOk = Object.keys(providers).find((k) => providers[k].configured);
    if (firstOk) select.value = firstOk;
  }

  updateProviderStatus();
  $("generateBtn").disabled = !anyConfigured;
  if (!anyConfigured) {
    status.textContent = "Neither provider is configured — set GEMINI_API_KEY or start Ollama. See backend/.env.example.";
    status.classList.add("status-bad");
  }
}

function updateProviderStatus() {
  if (!healthInfo) return;
  const select = $("providerSelect");
  const status = $("providerStatus");
  const info = healthInfo.providers[select.value];
  if (!info) return;
  status.classList.remove("status-bad");
  status.textContent = info.configured
    ? `Ready — ${select.value === "ollama" ? "running locally" : "free tier"}, model ${info.model}.`
    : `${PROVIDER_LABELS[select.value]} isn't configured.`;
  $("generateBtn").disabled = !info.configured;
}

async function runGenerate(brief) {
  const progress = $("progressLine");
  const body = $("outputBody");
  const output = $("output");
  const provider = $("providerSelect").value;

  output.classList.add("is-visible");
  body.hidden = true;
  setBanner("");
  progress.hidden = false;
  progress.textContent = `Requirements agent — reading the brief (${PROVIDER_LABELS[provider]})…`;
  output.scrollIntoView({ behavior: "smooth", block: "start" });

  const stages = [
    [4, "Architect agent — designing components, APIs and data models…"],
    [22, "Security Architect — designing auth, IAM and network boundaries…"],
    [38, "Reliability Architect — designing scaling, DR and observability…"],
    [55, "Security, Cost, Reliability and Critic agents — reviewing the full design…"],
    [90, "Architect agent — revising based on findings…"],
    [110, "Reviewing the revised architecture…"],
    [145, "Sketching MVP / Growth / Large-scale alternatives…"],
    [160, "Compiling the risk register and implementation roadmap…"],
    [180, "Still running — this pipeline does several review + revision rounds, a few minutes is normal on a local model…"],
  ];
  const timers = stages.map(([seconds, text]) =>
    setTimeout(() => { progress.textContent = text; }, seconds * 1000)
  );

  try {
    const res = await fetch(`${BACKEND_URL}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...brief, provider }),
    });

    const payload = await res.json().catch(() => null);

    if (!res.ok) {
      const detail = payload && payload.detail ? payload.detail : `HTTP ${res.status}`;
      throw new Error(detail);
    }

    timers.forEach(clearTimeout);
    progress.hidden = true;
    body.hidden = false;
    setBanner(`Generated live via ${PROVIDER_LABELS[provider]} — project ${payload.id.slice(0, 8)}.`);
    lastResult = payload;
    $("downloadJson").disabled = false;
    $("downloadBlueprint").disabled = false;
    renderResult(payload);
    loadProjects();
  } catch (err) {
    timers.forEach(clearTimeout);
    progress.hidden = true;
    body.hidden = true;
    setBanner(`Generation failed: ${err.message}`, true);
  }
}

function formatDate(isoString) {
  const d = new Date(isoString);
  return isNaN(d) ? isoString : d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

async function loadProjects() {
  const body = $("projectsBody");
  const empty = $("projectsEmpty");
  try {
    const res = await fetch(`${BACKEND_URL}/api/projects`);
    if (!res.ok) throw new Error(`backend returned ${res.status}`);
    const { projects } = await res.json();

    body.innerHTML = "";
    empty.hidden = projects.length > 0;

    projects.forEach((p) => {
      const tr = document.createElement("tr");

      const ideaTd = document.createElement("td");
      ideaTd.textContent = p.idea.length > 70 ? p.idea.slice(0, 68) + "…" : p.idea;
      if (p.refined_from) {
        const tag = document.createElement("span");
        tag.className = "id-badge";
        tag.style.marginLeft = "8px";
        tag.textContent = "refined";
        ideaTd.appendChild(tag);
      }
      tr.appendChild(ideaTd);

      const providerTd = document.createElement("td");
      providerTd.textContent = PROVIDER_LABELS[p.provider] || p.provider;
      tr.appendChild(providerTd);

      const dateTd = document.createElement("td");
      dateTd.textContent = formatDate(p.created_at);
      tr.appendChild(dateTd);

      const actionTd = document.createElement("td");
      const viewBtn = document.createElement("button");
      viewBtn.type = "button";
      viewBtn.className = "btn btn-ghost";
      viewBtn.textContent = "View";
      viewBtn.addEventListener("click", () => viewProject(p.id));
      actionTd.appendChild(viewBtn);
      tr.appendChild(actionTd);

      body.appendChild(tr);
    });
  } catch (err) {
    empty.hidden = false;
    empty.textContent = `Couldn't load saved projects: ${err.message}`;
  }
}

async function viewProject(projectId) {
  setBanner("");
  try {
    const res = await fetch(`${BACKEND_URL}/api/projects/${projectId}`);
    if (!res.ok) throw new Error(`backend returned ${res.status}`);
    const payload = await res.json();

    lastResult = payload;
    $("downloadJson").disabled = false;
    $("downloadBlueprint").disabled = false;
    $("output").classList.add("is-visible");
    $("progressLine").hidden = true;
    $("outputBody").hidden = false;
    setBanner(`Viewing saved project ${payload.id.slice(0, 8)} (${PROVIDER_LABELS[payload.provider] || payload.provider}).`);
    renderResult(payload);
    $("output").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    setBanner(`Couldn't load that project: ${err.message}`, true);
  }
}

async function refineProject() {
  if (!lastResult || !lastResult.id) return;
  const notes = $("refineNotes").value.trim();
  const errorEl = $("refineError");
  const btn = $("refineBtn");
  errorEl.hidden = true;

  if (!notes) {
    errorEl.textContent = "Add a note describing what should change.";
    errorEl.hidden = false;
    return;
  }

  const provider = $("providerSelect").value;
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Refining… (re-runs review + compile, similar time to a generation)";

  try {
    const res = await fetch(`${BACKEND_URL}/api/projects/${lastResult.id}/refine`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes, provider }),
    });
    const payload = await res.json().catch(() => null);
    if (!res.ok) {
      const detail = payload && payload.detail ? payload.detail : `HTTP ${res.status}`;
      throw new Error(detail);
    }

    lastResult = payload;
    $("downloadJson").disabled = false;
    $("downloadBlueprint").disabled = false;
    setBanner(`Refined into project ${payload.id.slice(0, 8)} based on your notes.`);
    renderResult(payload);
    $("refineNotes").value = "";
    loadProjects();
    $("output").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    errorEl.textContent = `Refine failed: ${err.message}`;
    errorEl.hidden = false;
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
}

function validateForm() {
  const idea = $("idea");
  const errorEl = $("formError");
  idea.classList.remove("field-error");
  errorEl.hidden = true;

  if (!idea.value.trim()) {
    idea.classList.add("field-error");
    errorEl.textContent = "Add a product idea — everything downstream starts from this.";
    errorEl.hidden = false;
    idea.focus();
    return false;
  }
  return true;
}

function readBrief() {
  const f = $("briefForm");
  return {
    idea: f.idea.value.trim(),
    users: f.users.value.trim(),
    traffic: f.traffic.value.trim(),
    budget: f.budget.value.trim(),
    availability: f.availability.value.trim(),
    cloud: f.cloud.value,
    stage: f.stage.value,
    constraints: f.constraints.value.trim(),
  };
}

function init() {
  $("revDate").textContent = new Date().toISOString().slice(0, 10);

  $("loadExample").addEventListener("click", () => {
    const f = $("briefForm");
    f.idea.value = EXAMPLE_BRIEF.idea;
    f.users.value = EXAMPLE_BRIEF.users;
    f.traffic.value = EXAMPLE_BRIEF.traffic;
    f.budget.value = EXAMPLE_BRIEF.budget;
    f.availability.value = EXAMPLE_BRIEF.availability;
    f.cloud.value = EXAMPLE_BRIEF.cloud;
    f.stage.value = EXAMPLE_BRIEF.stage;
    f.constraints.value = EXAMPLE_BRIEF.constraints;
  });

  $("providerSelect").addEventListener("change", updateProviderStatus);

  function downloadJson(data, filename) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  $("downloadJson").addEventListener("click", () => {
    if (!lastResult) return;
    downloadJson(lastResult, `architecture-${lastResult.id.slice(0, 8)}.json`);
  });

  $("downloadBlueprint").addEventListener("click", () => {
    if (!lastResult) return;
    downloadJson(lastResult.blueprint, `blueprint-${lastResult.id.slice(0, 8)}.json`);
  });

  $("briefForm").addEventListener("submit", (e) => {
    e.preventDefault();
    if (!validateForm()) return;
    runGenerate(readBrief());
  });

  $("refineBtn").addEventListener("click", refineProject);

  loadHealth();
  loadProjects();
}

document.addEventListener("DOMContentLoaded", init);
