// =============================================================================
// File Path: frontend/js/components/topology_graph.js
// 4-Agent SVG Topology Graph, Central Ticket Hub & Deterministic Glow Decay
// =============================================================================

const AGENT_META = {
  "@eda-lead": {
    x: 230,
    y: 44,
    haloId: "halo-eda-lead",
    groupId: "node-group-eda-lead",
    subId: "sub-eda-lead",
    defaultRole: "Orchestrator"
  },
  "@dv-debugger": {
    x: 78,
    y: 125,
    haloId: "halo-dv-debugger",
    groupId: "node-group-dv-debugger",
    subId: "sub-dv-debugger",
    defaultRole: "Verif / COI"
  },
  "@rtl-architect": {
    x: 382,
    y: 125,
    haloId: "halo-rtl-architect",
    groupId: "node-group-rtl-architect",
    subId: "sub-rtl-architect",
    defaultRole: "RTL / Lint"
  },
  "@synth-qor": {
    x: 230,
    y: 206,
    haloId: "halo-synth-qor",
    groupId: "node-group-synth-qor",
    subId: "sub-synth-qor",
    defaultRole: "ASIC / PPA"
  }
};

function mountTopologySvgIfNeeded() {
  if (STATE.topology.mounted) return;
  const mount = document.getElementById("topology-svg-mount");
  if (!mount) return;

  mount.innerHTML = `
    <svg id="agent-topology-svg" viewBox="0 0 460 250" class="w-full h-full">
      <defs>
        <filter id="glow-cyan" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="9" result="blur1" />
          <feMerge><feMergeNode in="blur1" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <filter id="glow-amber" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="9" result="blur1" />
          <feMerge><feMergeNode in="blur1" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <filter id="glow-purple" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="8" result="blur1" />
          <feMerge><feMergeNode in="blur1" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <filter id="glow-emerald" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="8" result="blur1" />
          <feMerge><feMergeNode in="blur1" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <linearGradient id="beam-grad-cyan-amber" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#06b6d4" />
          <stop offset="50%" stop-color="#34d399" />
          <stop offset="100%" stop-color="#f59e0b" />
        </linearGradient>
        <linearGradient id="ticket-holo-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.95" />
          <stop offset="50%" stop-color="#818cf8" stop-opacity="0.9" />
          <stop offset="100%" stop-color="#c084fc" stop-opacity="0.95" />
        </linearGradient>
        <marker id="arrow-cyan" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="4" markerHeight="4" orient="auto">
          <path d="M 0 1 L 10 5 L 0 9 z" fill="#22d3ee" />
        </marker>
        <marker id="arrow-amber" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="4" markerHeight="4" orient="auto">
          <path d="M 0 1 L 10 5 L 0 9 z" fill="#fbbf24" />
        </marker>
      </defs>

      <!-- Background Mesh Curves Between All 4 Agents -->
      <g stroke="#27272a" stroke-width="1.1" fill="none" opacity="0.65">
        <path d="M 78 125 C 115 62, 165 44, 230 44" />
        <path d="M 230 44 C 295 44, 345 62, 382 125" />
        <path d="M 78 125 C 115 188, 165 206, 230 206" />
        <path d="M 230 206 C 295 206, 345 188, 382 125" />
        <path d="M 230 62 L 230 100" stroke-dasharray="3 3" />
        <path d="M 230 150 L 230 188" stroke-dasharray="3 3" />
        <path d="M 96 125 L 202 125" stroke-dasharray="3 3" />
        <path d="M 258 125 L 364 125" stroke-dasharray="3 3" />
      </g>

      <!-- Event-Driven Active Handoff Energy Paths -->
      <g id="active-handoff-paths" class="handoff-beam-group">
        <path id="beam-to-ticket" d="M 96 125 L 206 125" fill="none" stroke="#22d3ee" stroke-width="1.8" stroke-dasharray="4 4" class="beam-animated" marker-end="url(#arrow-cyan)" />
        <path id="beam-wave-glow" d="M 78 125 Q 230 180, 382 125" fill="none" stroke="url(#beam-grad-cyan-amber)" stroke-width="4.5" opacity="0.32" filter="url(#glow-cyan)" />
        <path id="beam-wave-core" d="M 78 125 Q 230 180, 382 125" fill="none" stroke="url(#beam-grad-cyan-amber)" stroke-width="2" marker-end="url(#arrow-amber)" />
        <path id="beam-wave-particles" d="M 78 125 Q 230 180, 382 125" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-dasharray="1 16" class="beam-animated" opacity="0.9" />
      </g>

      <g id="sparkle-particles" class="handoff-beam-group">
        <circle cx="145" cy="144" r="1.5" fill="#67e8f9" />
        <circle cx="185" cy="151" r="1.3" fill="#a7f3d0" />
        <circle cx="230" cy="154" r="1.8" fill="#34d399" />
        <circle cx="275" cy="151" r="1.3" fill="#fde68a" />
        <circle cx="315" cy="144" r="1.7" fill="#fbbf24" />
      </g>

      <!-- Compact Non-Overlapping Central Ticket Hub -->
      <g id="central-ticket-hub" class="ticket-hub-float" onclick="toggleTicketDrawer(true)">
        <circle id="ticket-hub-glow" cx="230" cy="125" r="26" fill="rgba(56, 189, 248, 0.12)" filter="url(#glow-cyan)" />
        <rect x="219" y="104" width="26" height="32" rx="4" fill="#181824" stroke="#6366f1" stroke-width="1" opacity="0.65" />
        <rect x="216" y="107" width="26" height="32" rx="4" fill="#181824" stroke="#38bdf8" stroke-width="1.1" opacity="0.82" />
        <rect x="213" y="110" width="26" height="32" rx="4" fill="#131824" stroke="url(#ticket-holo-grad)" stroke-width="1.4" />
        <path d="M 231 110 L 239 118 L 231 118 Z" fill="#38bdf8" opacity="0.6" />
        <line x1="218" y1="120" x2="231" y2="120" stroke="#bae6fd" stroke-width="1.4" stroke-linecap="round" />
        <line x1="218" y1="126" x2="234" y2="126" stroke="#93c5fd" stroke-width="1.4" stroke-linecap="round" />
        <line x1="218" y1="132" x2="228" y2="132" stroke="#c4b5fd" stroke-width="1.4" stroke-linecap="round" />
        <circle cx="242" cy="106" r="6.5" fill="#27272a" stroke="#52525b" stroke-width="1" />
        <text id="svg-ticket-count" x="242" y="109" text-anchor="middle" fill="#f4f4f5" font-size="8" font-weight="700" font-family="JetBrains Mono, monospace">0</text>
        <text id="svg-ticket-id" x="230" y="152" text-anchor="middle" fill="#d4d4d8" font-size="8.5" font-weight="600" font-family="JetBrains Mono, monospace">NO TICKET</text>
      </g>

      <!-- Node 1: @eda-lead (TOP — Purple) -->
      <g id="node-group-eda-lead" class="cursor-pointer agent-node-group is-idle" onclick="inspectAgent('@eda-lead')">
        <circle id="halo-eda-lead" cx="230" cy="44" r="24" fill="rgba(168, 85, 247, 0.3)" filter="url(#glow-purple)" class="agent-halo-pulse" />
        <text x="230" y="16" text-anchor="middle" fill="#c084fc" font-size="9.5" font-weight="600" font-family="JetBrains Mono, monospace">@eda-lead</text>
        <circle cx="230" cy="44" r="16" fill="#161024" stroke="#a855f7" stroke-width="1.8" />
        <circle cx="230" cy="44" r="10" fill="none" stroke="#c084fc" stroke-width="0.9" stroke-dasharray="2 2" opacity="0.75" />
        <path d="M 230 36 L 231.8 42.2 L 238 44 L 231.8 45.8 L 230 52 L 228.2 45.8 L 222 44 L 228.2 42.2 Z" fill="#f3e8ff" />
        <text id="sub-eda-lead" x="230" y="68" text-anchor="middle" fill="#71717a" font-size="8" font-family="JetBrains Mono, monospace">Orchestrator</text>
      </g>

      <!-- Node 2: @dv-debugger (LEFT — Cyan) -->
      <g id="node-group-dv-debugger" class="cursor-pointer agent-node-group is-idle" onclick="inspectAgent('@dv-debugger')">
        <circle id="halo-dv-debugger" cx="78" cy="125" r="24" fill="rgba(6, 182, 212, 0.32)" filter="url(#glow-cyan)" class="agent-halo-pulse" />
        <circle cx="78" cy="125" r="16" fill="#082830" stroke="#22d3ee" stroke-width="1.8" />
        <circle cx="78" cy="125" r="10" fill="none" stroke="#67e8f9" stroke-width="0.9" stroke-dasharray="2 2" opacity="0.75" />
        <path d="M 78 117 L 79.8 123.2 L 86 125 L 79.8 126.8 L 78 133 L 76.2 126.8 L 70 125 L 76.2 123.2 Z" fill="#ecfeff" />
        <text x="78" y="152" text-anchor="middle" fill="#22d3ee" font-size="9.5" font-weight="600" font-family="JetBrains Mono, monospace">@dv-debugger</text>
        <text id="sub-dv-debugger" x="78" y="163" text-anchor="middle" fill="#71717a" font-size="8" font-family="JetBrains Mono, monospace">Verif / COI</text>
      </g>

      <!-- Node 3: @rtl-architect (RIGHT — Amber) -->
      <g id="node-group-rtl-architect" class="cursor-pointer agent-node-group is-idle" onclick="inspectAgent('@rtl-architect')">
        <circle id="halo-rtl-architect" cx="382" cy="125" r="24" fill="rgba(245, 158, 11, 0.32)" filter="url(#glow-amber)" class="agent-halo-pulse" />
        <circle cx="382" cy="125" r="16" fill="#291805" stroke="#f59e0b" stroke-width="1.8" />
        <circle cx="382" cy="125" r="10" fill="none" stroke="#fbbf24" stroke-width="0.9" stroke-dasharray="2 2" opacity="0.75" />
        <path d="M 382 117 L 383.8 123.2 L 390 125 L 383.8 126.8 L 382 133 L 380.2 126.8 L 374 125 L 380.2 123.2 Z" fill="#fef3c7" />
        <text x="382" y="152" text-anchor="middle" fill="#fbbf24" font-size="9.5" font-weight="600" font-family="JetBrains Mono, monospace">@rtl-architect</text>
        <text id="sub-rtl-architect" x="382" y="163" text-anchor="middle" fill="#71717a" font-size="8" font-family="JetBrains Mono, monospace">RTL / Lint</text>
      </g>

      <!-- Node 4: @synth-qor (BOTTOM — Emerald) -->
      <g id="node-group-synth-qor" class="cursor-pointer agent-node-group is-idle" onclick="inspectAgent('@synth-qor')">
        <circle id="halo-synth-qor" cx="230" cy="206" r="24" fill="rgba(16, 185, 129, 0.3)" filter="url(#glow-emerald)" class="agent-halo-pulse" />
        <circle cx="230" cy="206" r="16" fill="#062419" stroke="#10b981" stroke-width="1.8" />
        <circle cx="230" cy="206" r="10" fill="none" stroke="#34d399" stroke-width="0.9" stroke-dasharray="2 2" opacity="0.75" />
        <path d="M 230 198 L 231.8 204.2 L 238 206 L 231.8 207.8 L 230 214 L 228.2 207.8 L 222 206 L 228.2 204.2 Z" fill="#d1fae5" />
        <text x="230" y="232" text-anchor="middle" fill="#34d399" font-size="9.5" font-weight="600" font-family="JetBrains Mono, monospace">@synth-qor</text>
        <text id="sub-synth-qor" x="230" y="242" text-anchor="middle" fill="#71717a" font-size="8" font-family="JetBrains Mono, monospace">ASIC / PPA</text>
      </g>
    </svg>
  `;
  STATE.topology.mounted = true;
}

function applyTopologyVisualState(activeAgentsList, showBeam, fromAgent, toAgent, subtitleText) {
  mountTopologySvgIfNeeded();
  const activeSet = new Set(activeAgentsList || []);

  Object.keys(AGENT_META).forEach((ag) => {
    const meta = AGENT_META[ag];
    const haloEl = document.getElementById(meta.haloId);
    const groupEl = document.getElementById(meta.groupId);
    const subEl = document.getElementById(meta.subId);
    const isLit = activeSet.has(ag);

    if (haloEl) haloEl.classList.toggle("is-active", isLit);
    if (groupEl) {
      groupEl.classList.toggle("is-active", isLit);
      groupEl.classList.toggle("is-idle", !isLit);
    }
    if (subEl) {
      subEl.textContent = isLit ? "ACTIVE" : meta.defaultRole;
      subEl.setAttribute("fill", isLit ? "#f4f4f5" : "#71717a");
    }
  });

  const beamPathsEl = document.getElementById("active-handoff-paths");
  const sparklesEl = document.getElementById("sparkle-particles");

  if (showBeam && fromAgent && toAgent) {
    let srcAg = fromAgent;
    let dstAg = toAgent;
    if (srcAg === dstAg) {
      srcAg = dstAg === "@eda-lead" ? "@synth-qor" : "@eda-lead";
    }
    const src = AGENT_META[srcAg] || AGENT_META["@dv-debugger"];
    const dst = AGENT_META[dstAg] || AGENT_META["@rtl-architect"];

    const beamToTicket = document.getElementById("beam-to-ticket");
    if (beamToTicket) {
      const dx = 230 - src.x,
        dy = 125 - src.y;
      const len = Math.hypot(dx, dy) || 1;
      beamToTicket.setAttribute(
        "d",
        `M ${(src.x + (dx / len) * 18).toFixed(1)} ${(src.y + (dy / len) * 18).toFixed(1)} L ${(230 - (dx / len) * 22).toFixed(1)} ${(125 - (dy / len) * 22).toFixed(1)}`
      );
    }

    const wavePath = `M ${src.x} ${src.y} Q 230 180, ${dst.x} ${dst.y}`;
    ["beam-wave-glow", "beam-wave-core", "beam-wave-particles"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.setAttribute("d", wavePath);
    });

    if (beamPathsEl) beamPathsEl.classList.add("is-active");
    if (sparklesEl) sparklesEl.classList.add("is-active");
  } else {
    if (beamPathsEl) beamPathsEl.classList.remove("is-active");
    if (sparklesEl) sparklesEl.classList.remove("is-active");
  }

  const subHdr = document.getElementById("topology-handoff-subtitle");
  if (subHdr && subtitleText) {
    subHdr.textContent = subtitleText;
  }
}

function updateEventDrivenTopology(bundle) {
  mountTopologySvgIfNeeded();
  const sess = bundle.session_state || {};
  const activeProj = sess.active_project || sess.project_name || "";
  const tickets = filterLiveProjectTickets(bundle);
  const latestTicket = tickets.length > 0 ? tickets[tickets.length - 1] : null;
  const rawHistory = Array.isArray(sess.tool_history) ? sess.tool_history : [];
  const history = rawHistory.filter((h) => !h.project_name || h.project_name === activeProj);
  const latestLog = history.length > 0 ? history[history.length - 1] : null;

  let kbRule = "";
  if (history.length > 0) {
    for (let i = history.length - 1; i >= 0; i--) {
      const act = String(history[i].action || "");
      if (act.startsWith("query_kb:")) {
        kbRule = act.split(":").pop();
        break;
      }
    }
  }
  if (!kbRule && latestTicket && latestTicket.kb_rule_id) {
    kbRule = latestTicket.kb_rule_id;
  }
  const kbEl = document.getElementById("active-kb-rule-text");
  if (kbEl) kbEl.textContent = kbRule || "None";

  const ticketCount = tickets.length;
  const ticketId = latestTicket ? `TICKET-${String(ticketCount).padStart(3, "0")}` : "NO TICKET";
  const cntEl = document.getElementById("svg-ticket-count");
  const idEl = document.getElementById("svg-ticket-id");
  if (cntEl) cntEl.textContent = String(ticketCount);
  if (idEl) idEl.textContent = ticketId;

  const isExecuting = Boolean(sess.is_executing);
  const activeAgent = sess.active_agent || (latestLog && latestLog.agent) || "@eda-lead";
  const lastAction = String(sess.last_action || (latestLog && latestLog.action) || "");
  const eventKey = `${activeProj}|${isExecuting}|${lastAction}|${history.length}|${latestLog ? latestLog.timestamp : ""}`;

  const execInd = document.getElementById("live-exec-indicator");
  if (execInd) {
    if (isExecuting) {
      execInd.classList.remove("hidden");
      execInd.classList.add("flex");
      document.getElementById("live-exec-text").textContent = `${activeAgent}: ${lastAction}`;
    } else {
      execInd.classList.add("hidden");
      execInd.classList.remove("flex");
    }
  }

  if (isExecuting) {
    if (STATE.topology.decayTimer) {
      clearTimeout(STATE.topology.decayTimer);
      STATE.topology.decayTimer = null;
    }
    const isHandoffAction =
      lastAction.toLowerCase().includes("handoff") ||
      lastAction.toLowerCase().includes("read_agent");
    const fromAg = (latestTicket && latestTicket.from_agent) || "@eda-lead";
    const toAg = (latestTicket && latestTicket.to_agent) || activeAgent;
    const litAgents = isHandoffAction ? [fromAg, toAg] : [activeAgent];

    applyTopologyVisualState(
      litAgents,
      true,
      isHandoffAction ? fromAg : "@eda-lead",
      activeAgent,
      `${activeAgent} → ${lastAction.slice(0, 24)}`
    );
    STATE.topology.lastEventKey = eventKey;
    return;
  }

  if (
    STATE.topology.lastEventKey !== null &&
    STATE.topology.lastEventKey !== eventKey &&
    latestLog
  ) {
    STATE.topology.lastEventKey = eventKey;
    if (STATE.topology.decayTimer) {
      clearTimeout(STATE.topology.decayTimer);
    }

    const isHandoff = lastAction.toLowerCase().includes("handoff");
    const fromAg = isHandoff
      ? (latestTicket && latestTicket.from_agent) || activeAgent
      : "@eda-lead";
    const toAg = isHandoff
      ? (latestTicket && latestTicket.to_agent) || activeAgent
      : activeAgent;
    const litAgents = isHandoff ? [fromAg, toAg] : [activeAgent];

    applyTopologyVisualState(
      litAgents,
      true,
      fromAg,
      toAg,
      isHandoff ? `Handoff: ${fromAg} → ${toAg}` : `Done: ${lastAction.slice(0, 20)}`
    );

    STATE.topology.decayTimer = setTimeout(() => {
      applyTopologyVisualState([], false, null, null, `Idle • Last: ${activeAgent}`);
      STATE.topology.decayTimer = null;
    }, 1500);
    return;
  }

  if (!isExecuting && !STATE.topology.decayTimer) {
    STATE.topology.lastEventKey = eventKey;
    applyTopologyVisualState(
      [],
      false,
      null,
      null,
      history.length > 0 ? `Idle • Last: ${activeAgent}` : "Idle (Standby)"
    );
  }
}
