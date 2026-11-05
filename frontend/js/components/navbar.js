// =============================================================================
// File Path: frontend/js/components/navbar.js
// Top Header Bar, Bi-Directional Project Selector & Pipeline Stage Pills
// =============================================================================

function populateProjectSelectorDropdown(bundle) {
  const selectEl = document.getElementById("hdr-project-select");
  if (!selectEl) return;

  const sess = (bundle && bundle.session_state) || {};
  const activeProj =
    sess.active_project ||
    sess.project_name ||
    (bundle && bundle.workspace_context && bundle.workspace_context.active_project) ||
    "polar_scl_decoder";

  const projectsList = Array.isArray(bundle && bundle.available_projects)
    ? bundle.available_projects
    : STATE.availableProjects || [];

  if (projectsList.length > 0) {
    STATE.availableProjects = projectsList;
  }

  const names = new Set(STATE.availableProjects.map((p) => p.project_name || p));
  if (activeProj) names.add(activeProj);

  const sortedNames = Array.from(names).sort();
  selectEl.innerHTML = sortedNames
    .map(
      (name) =>
        `<option value="${name}" ${name === activeProj ? "selected" : ""}>${name}</option>`
    )
    .join("");
}

async function onProjectSelectorChange(projectName, createIfMissing = false) {
  if (!projectName || !String(projectName).trim()) return;
  const cleanName = String(projectName).trim();

  try {
    const res = await fetch("/api/workspace/select-project", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_name: cleanName,
        create_if_missing: Boolean(createIfMissing)
      })
    });
    if (res.ok) {
      const data = await res.json();
      if (data && data.bundle) {
        applyWorkspaceBundle(data.bundle, true);
        return;
      }
    }
  } catch (_) {}

  // Fallback over WebSocket if REST call was offline
  if (STATE.wsSocket && STATE.wsSocket.readyState === WebSocket.OPEN) {
    STATE.wsSocket.send(
      JSON.stringify({
        type: "SELECT_PROJECT",
        project_name: cleanName
      })
    );
  }
}

function toggleNewProjectModal(forceState) {
  const modal = document.getElementById("new-project-modal");
  if (!modal) return;
  const isHidden = modal.classList.contains("hidden");
  const shouldOpen = typeof forceState === "boolean" ? forceState : isHidden;
  modal.classList.toggle("hidden", !shouldOpen);
  modal.classList.toggle("flex", shouldOpen);
  if (shouldOpen) {
    const inp = document.getElementById("new-project-input");
    if (inp) {
      inp.value = "";
      setTimeout(() => inp.focus(), 50);
    }
  }
}

function submitNewProjectModal() {
  const inp = document.getElementById("new-project-input");
  if (!inp) return;
  const slug = inp.value
    .trim()
    .replace(/[^a-zA-Z0-9_-]+/g, "_")
    .replace(/^_+|_+$/g, "");
  if (!slug) return;
  toggleNewProjectModal(false);
  onProjectSelectorChange(slug, true);
}

function renderPipelineStageTracker(bundle) {
  const sess = bundle.session_state || {};
  const incomingCompleted = new Set(Array.isArray(sess.completed_stages) ? sess.completed_stages : []);
  const stale = new Set(sess.stale_stages || []);
  const failed = new Set(sess.failed_stages || []);

  const isExecuting = Boolean(sess.is_executing);
  const lastAct = String(sess.last_action || "").toLowerCase();

  // Strict 4-Stage Pipeline Sequence: 1.Hier -> 2.Lint -> 3.Sim -> 4.Synth
  const stageKeys = ["hierarchy", "lint", "simulation", "synthesis"];
  const stageMap = {
    hierarchy: { elId: "stage-pill-hierarchy", label: "1.Hier" },
    lint: { elId: "stage-pill-lint", label: "2.Lint" },
    simulation: { elId: "stage-pill-simulation", label: "3.Sim" },
    synthesis: { elId: "stage-pill-synthesis", label: "4.Synth" }
  };

  stageKeys.forEach((k) => {
    const el = document.getElementById(stageMap[k].elId);
    if (!el) return;

    let st = "pending";
    if (stale.has(k)) {
      st = "stale";
    } else if (failed.has(k)) {
      st = "fail";
    } else if (incomingCompleted.has(k)) {
      st = "pass";
    }

    if (isExecuting) {
      if (k === "hierarchy" && lastAct.includes("hierarchy")) st = "running";
      else if (k === "lint" && lastAct.includes("lint")) st = "running";
      else if (k === "simulation" && lastAct.includes("simulation")) st = "running";
      else if (
        k === "synthesis" &&
        (lastAct.includes("synthesis") || lastAct.includes("schematic") || lastAct.includes("views"))
      )
        st = "running";
    }

    el.className = `px-2 py-0.5 rounded stage-pill-${st}`;
    if (st === "running") el.textContent = `● ${stageMap[k].label}`;
    else if (st === "stale") el.textContent = `${stageMap[k].label} (STALE)`;
    else if (st === "fail") el.textContent = `${stageMap[k].label} (FAIL)`;
    else el.textContent = stageMap[k].label;
  });

  // Optional COI Diagnostic Pill (only shown when COI debug slice is used)
  const coiEl = document.getElementById("stage-pill-coi");
  if (coiEl) {
    const coiActive =
      incomingCompleted.has("coi") ||
      (isExecuting && (lastAct.includes("coi") || lastAct.includes("waveform")));
    coiEl.classList.toggle("hidden", !coiActive);
    if (coiActive) {
      coiEl.textContent = isExecuting && lastAct.includes("coi") ? "● 🔍 COI" : "🔍 COI";
    }
  }
}

function renderHeaderAndNavbar(bundle) {
  const sess = bundle.session_state || {};
  populateProjectSelectorDropdown(bundle);
  const shaEl = document.getElementById("hdr-sha-badge");
  if (shaEl) {
    shaEl.textContent = `SHA: ${(sess.rtl_sha256 || "--------").slice(0, 10)}`;
  }
  renderPipelineStageTracker(bundle);
}
