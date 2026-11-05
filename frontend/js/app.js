// =============================================================================
// File Path: frontend/js/app.js
// Main Application Bootstrapper, WebSocket Client & REST Fallback Poller
// =============================================================================

function switchMainTab(tabId) {
  STATE.activeTab = tabId;
  ["rtl", "dv", "synth"].forEach((id) => {
    const btn = document.getElementById(`tab-btn-${id}`);
    const pane = document.getElementById(`pane-${id}`);
    if (btn) btn.classList.toggle("active", id === tabId);
    if (pane) pane.classList.toggle("hidden", id !== tabId);
  });
  if (tabId === "dv") {
    if (STATE.bundle) renderWaveDromDiagramOnly(STATE.bundle);
    if (STATE.waveViewMode === "coi_graph") {
      requestAnimationFrame(() => fitSchematicToViewport("coi"));
    }
  } else if (tabId === "rtl") {
    requestAnimationFrame(() => fitSchematicToViewport("rtl"));
  } else if (tabId === "synth") {
    requestAnimationFrame(() => fitSchematicToViewport("gates"));
  }
}

function toggleTheme() {
  const isLight = document.documentElement.classList.toggle("light-theme");
  localStorage.setItem("silicon_studio_theme", isLight ? "light" : "dark");
}

function toggleHelpModal(forceState) {
  const modal = document.getElementById("help-modal");
  if (!modal) return;
  const isHidden = modal.classList.contains("hidden");
  const shouldOpen = typeof forceState === "boolean" ? forceState : isHidden;
  modal.classList.toggle("hidden", !shouldOpen);
  modal.classList.toggle("flex", shouldOpen);
}

function computeBundleSignature(b) {
  if (!b) return "";
  const s = b.session_state || {};
  const h = b.hierarchy || {};
  const histLen = (s.tool_history || []).length;
  const lastTs = histLen > 0 ? s.tool_history[histLen - 1].timestamp : "";
  const staleStr = (s.stale_stages || []).join(",");
  const compStr = (s.completed_stages || []).join(",");
  const failStr = (s.failed_stages || []).join(",");
  const tLen = (b.tickets_history || []).length;
  const svgCount = Object.keys(b.svg_schematics || {}).length;
  const projCount = (b.available_projects || []).length;
  return `${s.active_project}|${h.top_module}|${s.rtl_sha256}|${s.is_executing}|${s.last_action}|${histLen}|${lastTs}|${staleStr}|${compStr}|${failStr}|${tLen}|${svgCount}|${projCount}`;
}

function applyWorkspaceBundle(rawBundle, forceRender = false) {
  if (!rawBundle) return;
  const sess = rawBundle.session_state || {};
  const incomingProj = sess.active_project || sess.project_name || null;

  if (incomingProj && STATE.activeProjectName && incomingProj !== STATE.activeProjectName) {
    STATE.selectedRtlSchematicKey = null;
    STATE.selectedGatesSchematicKey = null;
    STATE.renderedRtlSvgHash = null;
    STATE.renderedGatesSvgHash = null;
    STATE.selectedTicketIndex = 0;
    STATE.waveTimeScale = 1.0;
    STATE.topology.lastEventKey = null;
    if (STATE.topology.decayTimer) {
      clearTimeout(STATE.topology.decayTimer);
      STATE.topology.decayTimer = null;
    }
    forceRender = true;
  }
  if (incomingProj) {
    STATE.activeProjectName = incomingProj;
  }

  const sig = computeBundleSignature(rawBundle);
  if (!forceRender && sig === STATE.lastBundleSignature) {
    return;
  }
  STATE.lastBundleSignature = sig;
  STATE.bundle = rawBundle;

  renderHeaderAndNavbar(rawBundle);
  updateEventDrivenTopology(rawBundle);
  renderTelemetryLog(rawBundle);
  renderRtlStudioTab(rawBundle);
  renderDvStudioTab(rawBundle);
  renderSynthStudioTab(rawBundle);
  renderTicketDrawer(rawBundle);
}

async function fetchInitialRestBundle() {
  try {
    const res = await fetch("/api/bundle");
    if (res.ok) {
      const data = await res.json();
      if (data && data.type === "WORKSPACE_UPDATE") {
        applyWorkspaceBundle(data, true);
      }
    }
  } catch (_) {}
}

function connectWebSocketTelemetry() {
  const wsDot = document.getElementById("ws-dot");
  const wsLabel = document.getElementById("ws-label");
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host || "127.0.0.1:8080";
  const wsUrl = `${proto}//${host}/ws`;

  try {
    const ws = new WebSocket(wsUrl);
    STATE.wsSocket = ws;
    ws.onopen = () => {
      STATE.wsConnected = true;
      if (wsDot) wsDot.className = "w-2 h-2 rounded-full bg-emerald-400 animate-pulse";
      if (wsLabel) wsLabel.textContent = "WS LIVE (:8080)";
    };
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data && data.type === "WORKSPACE_UPDATE") {
          applyWorkspaceBundle(data);
        }
      } catch (_) {}
    };
    ws.onclose = () => {
      STATE.wsConnected = false;
      if (wsDot) wsDot.className = "w-2 h-2 rounded-full bg-amber-400";
      if (wsLabel) wsLabel.textContent = "RECONNECTING...";
      setTimeout(connectWebSocketTelemetry, 2000);
    };
  } catch (_) {}
}

function startRestFallbackPolling() {
  setInterval(async () => {
    if (STATE.wsConnected) return;
    await fetchInitialRestBundle();
  }, 1800);
}

window.addEventListener("DOMContentLoaded", () => {
  if (localStorage.getItem("silicon_studio_theme") === "light") {
    document.documentElement.classList.add("light-theme");
  }
  mountTopologySvgIfNeeded();
  bindInteractivePanZoom("rtl-schematic-viewport", "rtl");
  bindInteractivePanZoom("gates-schematic-viewport", "gates");
  bindInteractivePanZoom("wave-schematic-viewport", "wave");

  const newProjInp = document.getElementById("new-project-input");
  if (newProjInp) {
    newProjInp.addEventListener("keydown", (e) => {
      if (e.key === "Enter") submitNewProjectModal();
      if (e.key === "Escape") toggleNewProjectModal(false);
    });
  }

  window.addEventListener("resize", () => {
    if (STATE.activeTab === "rtl") fitSchematicToViewport("rtl");
    else if (STATE.activeTab === "synth") fitSchematicToViewport("gates");
    else if (STATE.activeTab === "dv") {
      applyWaveformHorizontalScale();
      if (STATE.waveViewMode === "coi_graph") fitSchematicToViewport("coi");
    }
  });

  fetchInitialRestBundle();
  connectWebSocketTelemetry();
  startRestFallbackPolling();
});
