// =============================================================================
// File Path: frontend/js/components/ticket_drawer.js
// Slide-Over Inter-Agent Handoff Blackboard Inspector (with Timestamp Display)
// =============================================================================

function renderTicketDrawer(bundle) {
  const sess = bundle.session_state || {};
  const activeProj = sess.active_project || sess.project_name || "";
  const tickets = filterLiveProjectTickets(bundle);

  const tsEl = document.getElementById("drawer-ticket-timestamp");
  const shaEl = document.getElementById("drawer-ticket-sha");

  if (tickets.length === 0) {
    document.getElementById("drawer-ticket-tabs").innerHTML =
      `<span class="text-xs text-zinc-500">No active tickets for ${activeProj || "this project"} (pipeline in progress or clean).</span>`;
    document.getElementById("drawer-ticket-status").textContent = "NONE";
    document.getElementById("drawer-from-agent").textContent = "None";
    document.getElementById("drawer-to-agent").textContent = "None";
    document.getElementById("drawer-kb-rule").textContent = "None";
    if (tsEl) tsEl.textContent = "N/A";
    if (shaEl) shaEl.textContent = (sess.rtl_sha256 || "--------").slice(0, 10);
    document.getElementById("drawer-anchor-t0").textContent = "N/A";
    document.getElementById("drawer-rtl-loc").textContent = "N/A";
    document.getElementById("drawer-coi-signals").textContent = "None";
    document.getElementById("drawer-summary").textContent =
      "No active inter-agent tickets in the current pipeline run.";
    document.getElementById("drawer-evidence").textContent =
      "When @dv-debugger isolates a bug or @synth-qor completes Stage 4 synthesis sign-off, a timestamped ticket will appear here.";
    return;
  }

  if (STATE.selectedTicketIndex >= tickets.length) {
    STATE.selectedTicketIndex = tickets.length - 1;
  }
  const activeTicket = tickets[STATE.selectedTicketIndex] || tickets[tickets.length - 1];

  document.getElementById("drawer-ticket-tabs").innerHTML = tickets
    .map((t, idx) => {
      const isSel = idx === STATE.selectedTicketIndex;
      const displayId = `TICKET-${String(idx + 1).padStart(3, "0")}`;
      const shortTime = formatTicketShortTime(t);
      const timeSuffix = shortTime ? ` • ${shortTime}` : "";
      return `<button onclick="selectTicketInDrawer(${idx})" class="px-3 py-1 rounded-md font-mono-code text-xs transition ${
        isSel
          ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-semibold"
          : "bg-zinc-900 text-zinc-400 border border-zinc-800"
      }">${displayId} • ${t.status}${timeSuffix}</button>`;
    })
    .join("");

  document.getElementById("drawer-ticket-status").textContent = activeTicket.status || "OPEN";
  document.getElementById("drawer-from-agent").textContent =
    activeTicket.from_agent || "@dv-debugger";
  document.getElementById("drawer-to-agent").textContent =
    activeTicket.to_agent || "@rtl-architect";
  document.getElementById("drawer-kb-rule").textContent = activeTicket.kb_rule_id || "None";
  if (tsEl) tsEl.textContent = formatTicketTimestamp(activeTicket.timestamp);
  if (shaEl) shaEl.textContent = (activeTicket.rtl_sha256 || sess.rtl_sha256 || "--------").slice(0, 10);
  document.getElementById("drawer-anchor-t0").textContent = cleanMathText(
    activeTicket.anchor_time_ns || "N/A"
  );
  document.getElementById("drawer-rtl-loc").textContent =
    activeTicket.suspect_rtl_location || "src/*.sv";
  document.getElementById("drawer-coi-signals").textContent =
    activeTicket.coi_signals || "None";
  document.getElementById("drawer-summary").textContent = cleanMathText(
    activeTicket.summary || ""
  );
  document.getElementById("drawer-evidence").textContent = cleanMathText(
    activeTicket.evidence_and_action || ""
  );
}

function selectTicketInDrawer(idx) {
  STATE.selectedTicketIndex = idx;
  if (STATE.bundle) renderTicketDrawer(STATE.bundle);
}

function toggleTicketDrawer(forceState) {
  const drawer = document.getElementById("ticket-drawer");
  const backdrop = document.getElementById("ticket-drawer-backdrop");
  if (!drawer || !backdrop) return;
  const isHidden = drawer.classList.contains("translate-x-full");
  const shouldOpen = typeof forceState === "boolean" ? forceState : isHidden;
  drawer.classList.toggle("translate-x-full", !shouldOpen);
  backdrop.classList.toggle("hidden", !shouldOpen);
}

function inspectAgent() {
  toggleTicketDrawer(true);
}
