// =============================================================================
// File Path: frontend/js/store.js
// Central Reactive State Store & Shared Formatting Utilities
// (V3.3: Syncs `filterLiveProjectTickets` with current pipeline stage validity)
// =============================================================================

window.STATE = {
  activeTab: "rtl",
  logFilter: "ALL",
  activeProjectName: null,
  availableProjects: [],
  projectLogCache: {},
  projectStageCache: {},
  selectedRtlSchematicKey: null,
  selectedGatesSchematicKey: null,
  renderedRtlSvgHash: null,
  renderedGatesSvgHash: null,
  lastBundleSignature: null,
  selectedTicketIndex: 0,
  svgDarkFilter: true,
  waveViewMode: "parsed",
  lastDedupedSliceMd: "",
  topology: {
    mounted: false,
    lastEventKey: null,
    activeNodes: new Set(),
    decayTimer: null
  },
  waveTimeScale: 1.0,
  waveBaseSvgWidth: 0,
  waveBaseSvgHeight: 0,
  studios: {
    rtl: {
      zoom: 1.0,
      panX: 0,
      panY: 0,
      vpId: "rtl-schematic-viewport",
      stageId: "rtl-schematic-stage",
      lblId: "rtl-zoom-label"
    },
    gates: {
      zoom: 1.0,
      panX: 0,
      panY: 0,
      vpId: "gates-schematic-viewport",
      stageId: "gates-schematic-stage",
      lblId: "gates-zoom-label"
    },
    coi: {
      zoom: 1.0,
      panX: 0,
      panY: 0,
      vpId: "coi-schematic-viewport",
      stageId: "coi-schematic-stage",
      lblId: "coi-zoom-label"
    }
  },
  wsConnected: false,
  wsSocket: null,
  bundle: null
};

function formatTicketTimestamp(rawTs) {
  if (!rawTs) return "N/A";
  return String(rawTs).replace("T", " ");
}

function formatTicketShortTime(ticket) {
  if (!ticket) return "";
  if (ticket.display_time) return String(ticket.display_time);
  const raw = String(ticket.timestamp || "");
  if (raw.includes("T")) return raw.split("T")[1].slice(0, 8);
  if (raw.includes(" ")) return raw.split(" ")[1].slice(0, 8);
  return raw;
}

function filterLiveProjectTickets(bundle) {
  if (!bundle) return [];
  const sess = bundle.session_state || {};
  const activeProj = sess.active_project || sess.project_name || "";
  const currentSha = sess.rtl_sha256 || "";
  const completed = new Set(Array.isArray(sess.completed_stages) ? sess.completed_stages : []);
  const stale = new Set(Array.isArray(sess.stale_stages) ? sess.stale_stages : []);
  const failed = new Set(Array.isArray(sess.failed_stages) ? sess.failed_stages : []);

  const simPassed =
    completed.has("simulation") && !stale.has("simulation") && !failed.has("simulation");
  const synthPassed =
    completed.has("synthesis") && !stale.has("synthesis") && !failed.has("synthesis");

  const allTickets = Array.isArray(bundle.tickets_history) ? bundle.tickets_history : [];
  const closingStatuses = new Set(["TAPEOUT_READY", "VERIFIED_PASS"]);
  const bugStatuses = new Set(["OPEN_BUG", "FAIL", "RTL_FIXED_PENDING_SIM"]);

  const hasClosingOnCurrentSha = allTickets.some((t) => {
    if (!t || (t.project_name && t.project_name !== activeProj)) return false;
    if (currentSha && t.rtl_sha256 && t.rtl_sha256 !== currentSha) return false;
    const st = String(t.status || "").toUpperCase();
    if (st === "TAPEOUT_READY" && synthPassed) return true;
    if (st === "VERIFIED_PASS" && simPassed) return true;
    return false;
  });

  const valid = allTickets.filter((t) => {
    if (!t || (t.project_name && t.project_name !== activeProj)) return false;
    const tSha = t.rtl_sha256 || "";
    const tStatus = String(t.status || "").toUpperCase();

    // 1. If synthesis was invalidated or hasn't completed yet in this run,
    //    hide any old TAPEOUT_READY ticket from a previous session!
    if (tStatus === "TAPEOUT_READY" && !synthPassed) {
      return false;
    }

    // 2. If simulation was invalidated or hasn't completed yet in this run,
    //    hide any old VERIFIED_PASS ticket!
    if (tStatus === "VERIFIED_PASS" && !simPassed) {
      return false;
    }

    // 3. Tickets from an older RTL SHA-256:
    if (tSha && currentSha && tSha !== currentSha) {
      if (closingStatuses.has(tStatus) || simPassed || synthPassed || hasClosingOnCurrentSha) {
        return false;
      }
    }

    // 4. Superseded bug tickets:
    if ((simPassed || synthPassed || hasClosingOnCurrentSha) && bugStatuses.has(tStatus)) {
      return false;
    }

    return true;
  });

  return valid;
}

function cleanMathText(str) {
  if (!str) return "";
  return String(str)
    .replace(/\$\\mu\\text\{m\}\^2\$/g, "µm²")
    .replace(/\\mu\\text\{m\}\^2/g, "µm²")
    .replace(/\$t_0\$/g, "t₀")
    .replace(/\$\\rightarrow\$/g, "→")
    .replace(/\\rightarrow/g, "→")
    .replace(/`/g, "");
}

function resolveDynamicTopModuleName(bundle) {
  if (!bundle) return "top_module";
  const hier = bundle.hierarchy || {};
  if (hier.top_module && String(hier.top_module).trim()) {
    return String(hier.top_module).trim();
  }
  if (hier.rtl_top && String(hier.rtl_top).trim()) {
    return String(hier.rtl_top).trim();
  }
  if (Array.isArray(hier.rtl_files_ordered) && hier.rtl_files_ordered.length > 0) {
    const lastFile = hier.rtl_files_ordered[hier.rtl_files_ordered.length - 1];
    const base = lastFile.replace(/\\/g, "/").split("/").pop().replace(/\.(sv|v)$/i, "");
    if (base) return base;
  }
  const sess = bundle.session_state || {};
  const projName = sess.active_project || sess.project_name || "top_module";
  return String(projName).replace(/^[0-9]+_/, "");
}

function parseMarkdownTablesToHtml(mdText) {
  if (!mdText || !mdText.includes("|")) {
    return `<div class="text-xs text-zinc-400 font-mono-code p-4">${cleanMathText(mdText || "No data generated yet.")}</div>`;
  }
  const lines = mdText.split(/\r?\n/);
  let htmlParts = [];
  let inTable = false;

  for (let line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith(">")) {
      htmlParts.push(
        `<div class="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-mono-code">${cleanMathText(trimmed.slice(1).trim())}</div>`
      );
    } else if (trimmed.startsWith("###")) {
      if (inTable) {
        htmlParts.push("</tbody></table></div>");
        inTable = false;
      }
      htmlParts.push(
        `<div class="text-xs font-semibold text-cyan-400 font-mono-code pt-1">${cleanMathText(trimmed.replace(/^#+\s*/, ""))}</div>`
      );
    } else if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      const cells = trimmed
        .slice(1, -1)
        .split("|")
        .map((c) => c.trim());
      if (cells.every((c) => /^[-:]+$/.test(c))) continue;
      if (!inTable) {
        inTable = true;
        htmlParts.push(
          `<div class="overflow-x-auto rounded border border-[#27272a]"><table class="data-grid-table"><thead><tr>${cells
            .map((h) => `<th>${cleanMathText(h)}</th>`)
            .join("")}</tr></thead><tbody>`
        );
      } else {
        const isT0 = cells.some((c) => c.includes("[t0"));
        htmlParts.push(
          `<tr class="${isT0 ? "row-t0" : ""}">${cells
            .map((c) => `<td>${cleanMathText(c).replace(/\*\*/g, "")}</td>`)
            .join("")}</tr>`
        );
      }
    }
  }
  if (inTable) htmlParts.push("</tbody></table></div>");
  return htmlParts.join("");
}
