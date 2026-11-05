// =============================================================================
// File Path: frontend/js/components/telemetry_log.js
// 250-Event Monotonic Agent & Tool Execution Log Table
// =============================================================================

function formatToolAndAgentRow(item, index) {
  const rawAct = String(item.action || "Tool execution");
  const low = rawAct.toLowerCase();

  let agent = item.agent || "@eda-lead";
  if (!item.agent) {
    if (low.includes("hierarchy") || low.includes("lint")) agent = "@rtl-architect";
    else if (low.includes("simulation") || low.includes("coi") || low.includes("waveform"))
      agent = "@dv-debugger";
    else if (low.includes("synthesis") || low.includes("views") || low.includes("schematic"))
      agent = "@synth-qor";
    else if (low.includes("query_kb") || low.includes("knowledge")) {
      agent = low.includes(":sdc:") || low.includes(":ppa:") ? "@synth-qor" : "@rtl-architect";
    }
  }

  let toolCallHtml = `<span class="text-zinc-100 font-semibold">${rawAct}</span>`;
  let status = item.status || "PASS";

  if (low.startsWith("[running]")) {
    toolCallHtml = `<span class="text-amber-300 font-semibold">⚡ Executing: ${rawAct.replace(/^\[running\]\s*/i, "")}</span>`;
    status = "RUNNING";
  } else if (low.startsWith("query_kb:") || low.includes("query_design_knowledge")) {
    const parts = rawAct.split(":");
    const dom = parts[1] ? parts[1].toUpperCase() : "KB";
    const ruleId = parts[2] || "RULE";
    toolCallHtml = `<span class="text-cyan-300 font-semibold">query_design_knowledge(${dom})</span> <span class="text-zinc-400">→ Pulled</span> <span class="text-amber-300 font-semibold">${ruleId}</span>`;
    status = "KB HIT";
  } else if (low.startsWith("run_yosys_synthesis:")) {
    const target = rawAct.split(":")[1] || "cmos";
    toolCallHtml = `<span class="text-emerald-300 font-semibold">run_yosys_synthesis</span><span class="text-zinc-400">(target="${target}")</span>`;
  } else if (low.startsWith("post_handoff:")) {
    const tId = rawAct.split(":")[1] || "TICKET";
    toolCallHtml = `<span class="text-purple-300 font-semibold">post_agent_handoff</span> <span class="text-zinc-400">→ ${tId}</span>`;
  }

  let agentPillClass = "agent-pill-lead";
  if (agent.includes("rtl")) agentPillClass = "agent-pill-rtl";
  else if (agent.includes("dv")) agentPillClass = "agent-pill-dv";
  else if (agent.includes("synth")) agentPillClass = "agent-pill-synth";

  let ts = item.timestamp || "12:00:00";
  if (ts.length === 8) ts = `${ts}.${String((850 + index * 3) % 999).padStart(3, "0")}`;

  return { ts, agent, agentPillClass, toolCallHtml, rawAct, status };
}

function renderTelemetryLog(bundle) {
  const sess = bundle.session_state || {};
  const projKey = sess.active_project || sess.project_name || "default";
  const incomingHistory = Array.isArray(sess.tool_history) ? sess.tool_history : [];

  // Strictly bind to the current project's incoming history (filtered by project_name)
  const projectOnlyHistory = incomingHistory.filter(
    (item) => item && typeof item === "object" && (!item.project_name || item.project_name === projKey)
  );
  STATE.projectLogCache[projKey] = projectOnlyHistory.slice(-250);

  const entries = STATE.projectLogCache[projKey].map((item, idx) =>
    formatToolAndAgentRow(item, idx)
  );

  if (sess.is_executing && sess.last_action) {
    entries.push(
      formatToolAndAgentRow(
        {
          timestamp: new Date().toTimeString().slice(0, 8),
          agent: sess.active_agent || "@eda-lead",
          action: `[RUNNING] ${sess.last_action}`,
          status: "RUNNING"
        },
        entries.length
      )
    );
  }

  const passCnt = entries.filter((e) => e.status === "PASS" || e.status === "KB HIT").length;
  const failCnt = entries.filter((e) => e.status === "FAIL").length;
  const staleCnt = entries.filter((e) => e.status === "STALE").length;

  document.getElementById("count-pass").textContent = passCnt;
  document.getElementById("count-fail").textContent = failCnt;
  document.getElementById("count-stale").textContent = staleCnt;
  document.getElementById("telemetry-count-badge").textContent = `(${entries.length} events)`;

  const filtered =
    STATE.logFilter === "ALL"
      ? entries
      : entries.filter((e) =>
          STATE.logFilter === "PASS"
            ? e.status === "PASS" || e.status === "KB HIT"
            : e.status === STATE.logFilter
        );

  const container = document.getElementById("telemetry-log-container");
  if (!container) return;

  if (filtered.length === 0) {
    container.innerHTML = `<div class="py-12 text-center text-zinc-500 text-xs">No tool executions recorded for ${
      sess.active_project || "active project"
    } yet.</div>`;
    return;
  }

  container.innerHTML = filtered
    .map((e) => {
      let badgeClass = "badge-pass";
      if (e.status === "FAIL") badgeClass = "badge-fail";
      else if (e.status === "STALE") badgeClass = "badge-stale";
      else if (e.status === "KB HIT" || e.status === "RUNNING") badgeClass = "badge-kb";

      return `<div class="grid grid-cols-12 items-center py-1 px-2 rounded hover:bg-zinc-800/60 transition cursor-pointer" onclick="handleLogRowClick('${e.rawAct.replace(/'/g, "")}')">
      <div class="col-span-2 text-zinc-500 text-[11px]">${e.ts}</div>
      <div class="col-span-2 pr-1">
        <span class="px-2 py-0.5 rounded text-[10.5px] font-semibold ${e.agentPillClass}">${e.agent}</span>
      </div>
      <div class="col-span-6 pr-2 break-all sm:break-normal truncate" title="${e.rawAct}">${e.toolCallHtml}</div>
      <div class="col-span-2 text-right">
        <span class="px-2 py-0.5 rounded text-[10px] font-semibold ${badgeClass}">${e.status}</span>
      </div>
    </div>`;
    })
    .join("");

  container.scrollTop = container.scrollHeight;
}

function setLogFilter(filter) {
  STATE.logFilter = STATE.logFilter === filter ? "ALL" : filter;
  const clearBtn = document.getElementById("filter-btn-clear");
  if (clearBtn) clearBtn.classList.toggle("hidden", STATE.logFilter === "ALL");
  if (STATE.bundle) renderTelemetryLog(STATE.bundle);
}

function handleLogRowClick(actionStr) {
  const low = actionStr.toLowerCase();
  if (low.includes("sim") || low.includes("wave") || low.includes("coi")) switchMainTab("dv");
  else if (low.includes("synth") || low.includes("ppa") || low.includes("views"))
    switchMainTab("synth");
  else if (low.includes("handoff") || low.includes("query_kb")) toggleTicketDrawer(true);
  else switchMainTab("rtl");
}
