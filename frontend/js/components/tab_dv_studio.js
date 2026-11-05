// =============================================================================
// File Path: frontend/js/components/tab_dv_studio.js
// Tab 2: Deduplicated WaveDrom Studio, Dual-Edge COI Grid & Interactive Pan/Zoom COI Graph
//        (V3.4: True `is_seq` Sequential Register Column Placement & Unpacked Array Support)
// =============================================================================

function stripBitRangePreserveArrayIdx(rawName) {
  let s = String(rawName || "").trim().replace(/^\\+/, "");
  s = s.replace(/\s*\[\s*[^\[\]:]+\s*:\s*[^\[\]]+\s*\]/g, "");
  s = s.replace(/\s+\[(\d+)\]/g, "[$1]");
  return s.trim();
}

function computeWaveSegmentLengths(waveStr) {
  const lengths = [];
  if (!waveStr) return lengths;
  const s = String(waveStr);
  let i = 0;
  while (i < s.length) {
    const ch = s[i];
    if ("=23456789".includes(ch)) {
      let span = 1;
      while (i + span < s.length && s[i + span] === ".") {
        span++;
      }
      lengths.push(span);
      i += span;
    } else {
      i++;
    }
  }
  return lengths;
}

function sanitizeWaveDromForVivadoUx(rawWd, timeScale = 1.0) {
  const cloned = JSON.parse(JSON.stringify(rawWd || { signal: [] }));
  cloned.config = Object.assign({}, cloned.config || {}, { hscale: 2 });
  const fullValueMap = {};

  if (Array.isArray(cloned.signal)) {
    const seenLeafAndWave = new Set();
    const filteredSignals = [];

    for (const sig of cloned.signal) {
      if (!sig || !sig.name) continue;
      const rawName = String(sig.name).trim();
      const leafName = stripBitRangePreserveArrayIdx(rawName.split(".").pop());
      const waveStr = String(sig.wave || "");
      const isStaticWave = /^[=0123456789]\.*$/.test(waveStr);
      const isAllCapsParam = /^[A-Z][A-Z0-9_]*$/.test(leafName.split("[")[0]);
      if (isStaticWave && isAllCapsParam) continue;

      const dataSig = Array.isArray(sig.data) ? sig.data.join(",") : "";
      const dedupKey = `${leafName.toLowerCase()}|${waveStr}|${dataSig}`;
      if (seenLeafAndWave.has(dedupKey)) continue;
      seenLeafAndWave.add(dedupKey);

      sig.name = leafName;
      filteredSignals.push(sig);
    }

    const scoreSignalPriority = (name) => {
      const n = String(name).toLowerCase();
      if (n.includes("clk") || n.includes("clock")) return 1;
      if (n.includes("rst") || n.includes("reset")) return 2;
      if (
        n.includes("en") ||
        n.includes("valid") ||
        n.includes("ready") ||
        n.includes("full") ||
        n.includes("empty")
      )
        return 3;
      if (n.includes("round") || n.includes("err")) return 5;
      return 4;
    };
    filteredSignals.sort((a, b) => scoreSignalPriority(a.name) - scoreSignalPriority(b.name));
    cloned.signal = filteredSignals;

    cloned.signal.forEach((sig) => {
      if (Array.isArray(sig.data)) {
        const segSpans = computeWaveSegmentLengths(sig.wave || "");
        sig.data = sig.data.map((val, idx) => {
          const fullStr = String(val).trim();
          const spanCycles = segSpans[idx] || 1;
          const maxChars = Math.max(4, Math.floor(spanCycles * 7 * Math.max(0.65, timeScale)));
          if (fullStr.length > maxChars) {
            const keepPrefix = Math.max(2, maxChars - 3);
            const truncated = `${fullStr.slice(0, keepPrefix)}...`;
            fullValueMap[truncated] = fullStr;
            return truncated;
          }
          return fullStr;
        });
      }
    });
  }
  return { wd: cloned, fullValueMap };
}

function deduplicateMarkdownTableColumns(mdText) {
  if (!mdText || !mdText.includes("|")) return mdText;
  const lines = mdText.split(/\r?\n/);
  const out = [];
  let keepColIndices = null;

  for (const line of lines) {
    const t = line.trim();
    if (t.startsWith("|")) {
      const rawCells = t.slice(1, -1).split("|").map((c) => c.trim());
      const isSeparator = rawCells.every((c) => /^[-:]+$/.test(c));
      const isHeader = rawCells[0].toLowerCase().includes("time");

      if (isHeader) {
        keepColIndices = [0];
        const seenLeaves = new Set();
        const cleanedHeaders = [rawCells[0]];

        for (let i = 1; i < rawCells.length; i++) {
          const h = rawCells[i];
          const leaf = stripBitRangePreserveArrayIdx(h.split(".").pop());
          const leafKey = leaf.toLowerCase();
          if (!seenLeaves.has(leafKey)) {
            seenLeaves.add(leafKey);
            keepColIndices.push(i);
            cleanedHeaders.push(leaf);
          }
        }
        out.push("| " + cleanedHeaders.join(" | ") + " |");
      } else if (keepColIndices && rawCells.length >= keepColIndices.length) {
        const kept = keepColIndices.map((idx) => (idx < rawCells.length ? rawCells[idx] : ""));
        out.push("| " + kept.join(" | ") + " |");
      } else if (isSeparator && keepColIndices) {
        out.push("| " + keepColIndices.map(() => ":---:").join(" | ") + " |");
      } else {
        out.push(line);
      }
    } else {
      out.push(line);
    }
  }
  return out.join("\n");
}

function extractActiveCoiSignalSet(bundle, sliceMd) {
  const activeSet = new Set();
  const coiGraph = bundle.coi_graph || {};
  if (Array.isArray(coiGraph.coi_signals)) {
    coiGraph.coi_signals.forEach((s) => {
      const cleanFull = stripBitRangePreserveArrayIdx(s).toLowerCase();
      const cleanLeaf = stripBitRangePreserveArrayIdx(String(s).split(".").pop()).toLowerCase();
      if (cleanFull) activeSet.add(cleanFull);
      if (cleanLeaf) activeSet.add(cleanLeaf);
    });
  }

  if (sliceMd && sliceMd.includes("|")) {
    for (const line of sliceMd.split(/\r?\n/)) {
      const t = line.trim();
      if (t.startsWith("|") && t.toLowerCase().includes("time")) {
        const cells = t.slice(1, -1).split("|").map((c) => c.trim());
        cells.slice(1).forEach((sig) => {
          const clean = stripBitRangePreserveArrayIdx(sig.split(".").pop()).toLowerCase();
          if (clean) activeSet.add(clean);
        });
        break;
      }
    }
  }

  const validTickets = filterLiveProjectTickets(bundle);
  const latestTicket = validTickets.length > 0 ? validTickets[validTickets.length - 1] : {};
  if (latestTicket && latestTicket.coi_signals) {
    String(latestTicket.coi_signals)
      .split(",")
      .forEach((s) => {
        const clean = stripBitRangePreserveArrayIdx(s.trim().split(".").pop()).toLowerCase();
        if (clean) activeSet.add(clean);
      });
  }
  return activeSet;
}

function isSequentialSignalNode(name, seqHintSet) {
  const clean = stripBitRangePreserveArrayIdx(String(name).split(":").shift().split(".").pop());
  const low = clean.toLowerCase();
  const baseNoIdx = low.split("[")[0];
  if (seqHintSet && (seqHintSet.has(low) || seqHintSet.has(baseNoIdx))) {
    return true;
  }
  return (
    baseNoIdx.endsWith("_q") ||
    baseNoIdx.includes("_reg") ||
    baseNoIdx.startsWith("reg_") ||
    baseNoIdx.includes("state") ||
    baseNoIdx.includes("cnt") ||
    baseNoIdx.includes("count") ||
    baseNoIdx.includes("ptr") ||
    baseNoIdx.includes("mem")
  );
}

function renderCoiDependencyGraphSvg(bundle, sliceMd) {
  const graphBox = document.getElementById("coi-graph-visualizer");
  if (!graphBox) return;

  const activeSet = extractActiveCoiSignalSet(bundle, sliceMd);
  const coiGraph = bundle.coi_graph || {};
  const coiDetails = Array.isArray(coiGraph.coi_details) ? coiGraph.coi_details : [];

  // Map each COI signal's logical hop distance (0 = Target Output, 1 = H1 direct driver, etc.)
  const hopMap = new Map();
  coiDetails.forEach((item) => {
    if (!item) return;
    const sn = stripBitRangePreserveArrayIdx(item.short_name || item.signal).toLowerCase();
    const hops = typeof item.logical_hops === "number" ? item.logical_hops : 1;
    if (!hopMap.has(sn) || hops < hopMap.get(sn)) {
      hopMap.set(sn, hops);
    }
  });

  // Build explicit sequential signal set from Yosys netlist COI details
  const seqHintSet = new Set();
  if (Array.isArray(coiGraph.sequential_coi_signals)) {
    coiGraph.sequential_coi_signals.forEach((s) =>
      seqHintSet.add(stripBitRangePreserveArrayIdx(s).toLowerCase())
    );
  }
  coiDetails.forEach((item) => {
    if (item && (item.is_seq || isSequentialSignalNode(item.short_name || item.signal, null))) {
      const sn = stripBitRangePreserveArrayIdx(item.short_name || item.signal).toLowerCase();
      seqHintSet.add(sn);
      seqHintSet.add(sn.split("[")[0]);
    }
  });

  const hier = bundle.hierarchy || {};
  const modules = hier.modules || {};
  const topModName = resolveDynamicTopModuleName(bundle);
  const topMod = modules[topModName] || Object.values(modules)[0] || {};
  const ports = Array.isArray(topMod.ports) ? topMod.ports : [];

  const inputs = ports.filter((p) => p.direction === "input").map((p) => p.name);
  const outputs = ports.filter((p) => p.direction !== "input").map((p) => p.name);
  const inputLowSet = new Set(inputs.map((x) => x.toLowerCase()));
  const outputLowSet = new Set(outputs.map((x) => x.toLowerCase()));

  const childMods = Array.isArray(topMod.instantiates)
    ? topMod.instantiates.map((i) => `${i.instance}:${i.module}`)
    : [];

  const pwrSignals = ((bundle.power_activity || {}).signals || []).map((s) => s.signal);
  const allDesignSigs = coiGraph.all_design_signals || [];
  const coiDetailNames = coiDetails.map((d) => d.short_name || d.signal);
  const internalMap = new Map();

  // Prioritize COI signals first so active sequential registers like pm_reg[0] & pm_reg[1] are never truncated
  coiDetailNames
    .concat(pwrSignals)
    .concat(allDesignSigs)
    .forEach((s) => {
      const clean = stripBitRangePreserveArrayIdx(String(s).split(".").pop());
      const low = clean.toLowerCase();
      const baseLow = low.split("[")[0];
      if (!clean || inputLowSet.has(low) || inputLowSet.has(baseLow) || outputLowSet.has(low) || outputLowSet.has(baseLow)) {
        return;
      }
      if (!internalMap.has(low)) {
        internalMap.set(low, clean);
      }
    });

  activeSet.forEach((s) => {
    const clean = stripBitRangePreserveArrayIdx(String(s).split(".").pop());
    const low = clean.toLowerCase();
    const baseLow = low.split("[")[0];
    if (
      clean &&
      !clean.includes(".") &&
      !inputLowSet.has(low) &&
      !inputLowSet.has(baseLow) &&
      !outputLowSet.has(low) &&
      !outputLowSet.has(baseLow) &&
      !internalMap.has(low)
    ) {
      internalMap.set(low, clean);
    }
  });

  const internalList = Array.from(internalMap.values());
  const seqNodes = internalList.filter((n) => isSequentialSignalNode(n, seqHintSet));
  const combNodes = internalList.filter((n) => !seqNodes.includes(n));

  if (combNodes.length === 0 && childMods.length > 0) {
    childMods.forEach((cm) => combNodes.push(cm));
  } else if (combNodes.length === 0) {
    combNodes.push("comb_datapath", "next_state_d");
  }
  if (seqNodes.length === 0) {
    seqNodes.push("state_q", "data_reg_q");
  }

  const columns = [
    { title: "PRIMARY INPUTS", nodes: inputs.length ? inputs.slice(0, 14) : ["clk", "rst_n", "in_i"] },
    { title: "COMB / SUBMODULES", nodes: combNodes.slice(0, 14) },
    { title: "SEQ REGISTERS (FF)", nodes: seqNodes.slice(0, 14) },
    { title: "PRIMARY OUTPUTS", nodes: outputs.length ? outputs.slice(0, 14) : ["out_o", "done_o"] }
  ];

  // Strictly match exact signal name (including array index `[0]` vs `[1]`) so `pm_reg[1]` is only active if in COI
  const isNodeActive = (name) => {
    const clean = stripBitRangePreserveArrayIdx(String(name).split(":").shift().split(".").pop()).toLowerCase();
    if (activeSet.has(clean)) return true;
    if (!clean.includes("[")) {
      const baseNoIdx = clean.split("[")[0];
      if (activeSet.has(baseNoIdx)) return true;
    }
    return false;
  };

  const svgW = 880;
  const maxRows = Math.max(...columns.map((c) => c.nodes.length), 4);
  const rowH = 52;
  const marginY = 68;
  const svgH = Math.max(390, marginY + maxRows * rowH + 44);
  const colX = [36, 250, 475, 695];
  const nodeW = 154;
  const nodeH = 34;

  const coords = [];
  const nodeByShortName = new Map();

  columns.forEach((col, cIdx) => {
    coords[cIdx] = col.nodes.map((n, rIdx) => {
      const cleanKey = stripBitRangePreserveArrayIdx(String(n).split(":").shift().split(".").pop()).toLowerCase();
      const nodeObj = {
        name: n,
        cleanKey,
        colIdx: cIdx,
        rowIdx: rIdx,
        x: colX[cIdx],
        y: marginY + rIdx * rowH,
        active: isNodeActive(n),
        hops: hopMap.has(cleanKey) ? hopMap.get(cleanKey) : null
      };
      nodeByShortName.set(cleanKey, nodeObj);
      return nodeObj;
    });
  });

  const anyActive = coords.some((col) => col.some((n) => n.active));
  if (!anyActive && coords[3].length > 0) {
    coords[3][0].active = true;
    if (coords[2][0]) coords[2][0].active = true;
    if (coords[1][0]) coords[1][0].active = true;
    if (coords[0][0]) coords[0][0].active = true;
  }

  const bgEdges = [];
  const activeEdges = [];
  const drawnEdgeKeys = new Set();

  function drawDirectedCurve(sNode, dNode, isActiveEdge) {
    if (!sNode || !dNode || sNode === dNode) return;
    const edgeKey = `${sNode.cleanKey}->${dNode.cleanKey}`;
    if (drawnEdgeKeys.has(edgeKey)) return;
    drawnEdgeKeys.add(edgeKey);

    let x1, y1, x2, y2, pathD;
    if (sNode.colIdx <= dNode.colIdx) {
      x1 = sNode.x + nodeW;
      y1 = sNode.y + nodeH / 2;
      x2 = dNode.x;
      y2 = dNode.y + nodeH / 2;
      const dx = Math.max(40, (x2 - x1) * 0.45);
      pathD = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
    } else {
      // Feedback edge (e.g., Seq Register `pm_reg[0]` -> Comb `pm_in_packed`)
      x1 = sNode.x;
      y1 = sNode.y + nodeH * 0.72;
      x2 = dNode.x + nodeW;
      y2 = dNode.y + nodeH * 0.72;
      const dx = Math.max(36, Math.abs(x1 - x2) * 0.35);
      pathD = `M ${x1} ${y1} C ${x1 - dx} ${y1 + 18}, ${x2 + dx} ${y2 + 18}, ${x2} ${y2}`;
    }

    if (isActiveEdge) {
      activeEdges.push(
        `<path d="${pathD}" fill="none" stroke="#22d3ee" stroke-width="3.8" opacity="0.22" />` +
          `<path d="${pathD}" fill="none" stroke="url(#coi-grad)" stroke-width="2.1" stroke-dasharray="6 4" class="beam-animated" />`
      );
    } else {
      bgEdges.push(
        `<path d="${pathD}" fill="none" stroke="#3f3f46" stroke-width="1.1" opacity="0.26" />`
      );
    }
  }

  const realCoiEdges = Array.isArray(coiGraph.coi_edges) ? coiGraph.coi_edges : [];
  const realBgEdges = Array.isArray(coiGraph.background_edges) ? coiGraph.background_edges : [];

  if (realCoiEdges.length > 0 || realBgEdges.length > 0) {
    // 1. Draw real non-COI background netlist edges
    realBgEdges.forEach((e) => {
      const sKey = stripBitRangePreserveArrayIdx(e.source).toLowerCase();
      const dKey = stripBitRangePreserveArrayIdx(e.target).toLowerCase();
      const sNode = nodeByShortName.get(sKey);
      const dNode = nodeByShortName.get(dKey);
      if (sNode && dNode) {
        drawDirectedCurve(sNode, dNode, sNode.active && dNode.active);
      }
    });

    // 2. Draw real Yosys netlist COI edges (`src -> dst`)
    realCoiEdges.forEach((e) => {
      const sKey = stripBitRangePreserveArrayIdx(e.source).toLowerCase();
      const dKey = stripBitRangePreserveArrayIdx(e.target).toLowerCase();
      const sNode = nodeByShortName.get(sKey);
      const dNode = nodeByShortName.get(dKey);
      if (sNode && dNode) {
        drawDirectedCurve(sNode, dNode, sNode.active && dNode.active);
      }
    });

    // 3. Connect primary clock (`clk`) to active sequential registers only
    const clkNode = coords[0].find((n) => n.active && n.cleanKey.includes("clk"));
    if (clkNode) {
      coords[2].forEach((seqNode) => {
        if (seqNode.active) {
          drawDirectedCurve(clkNode, seqNode, true);
        }
      });
    }
  } else {
    // Fallback if coi_edges hasn't been generated yet: connect each active node only to its nearest active neighbor
    for (let c = 0; c < 3; c++) {
      const srcCol = coords[c];
      const dstCol = coords[c + 1];
      srcCol.forEach((sNode, sIdx) => {
        if (sNode.active) {
          const activeTargets = dstCol.filter((d) => d.active);
          if (activeTargets.length > 0) {
            const closest = activeTargets.reduce((best, curr) =>
              Math.abs(curr.rowIdx - sIdx) < Math.abs(best.rowIdx - sIdx) ? curr : best
            );
            drawDirectedCurve(sNode, closest, true);
          }
        } else if (dstCol[sIdx]) {
          drawDirectedCurve(sNode, dstCol[sIdx], false);
        }
      });
    }
  }

  const nodeRects = [];
  columns.forEach((col, cIdx) => {
    nodeRects.push(
      `<text x="${colX[cIdx]}" y="${marginY - 14}" fill="#94a3b8" font-family="JetBrains Mono, monospace" font-size="10.5" font-weight="700">${col.title}</text>`
    );
    coords[cIdx].forEach((n) => {
      if (n.active) {
        const isTargetCol = cIdx === 3;
        const isSeqCol = cIdx === 2;
        const strokeCol = isTargetCol ? "#f59e0b" : isSeqCol ? "#10b981" : "#22d3ee";
        const fillCol = isTargetCol
          ? "rgba(245, 158, 11, 0.2)"
          : isSeqCol
          ? "rgba(16, 185, 129, 0.2)"
          : "rgba(6, 182, 212, 0.18)";
        const textCol = isTargetCol ? "#fde68a" : isSeqCol ? "#d1fae5" : "#ecfeff";
        const hopBadge =
          n.hops === 0
            ? "TGT"
            : typeof n.hops === "number"
            ? `H${n.hops}`
            : "";
        nodeRects.push(
          `<g>` +
            `<rect x="${n.x - 2}" y="${n.y - 2}" width="${nodeW + 4}" height="${nodeH + 4}" rx="7" fill="none" stroke="${strokeCol}" stroke-width="1.5" opacity="0.45" />` +
            `<rect x="${n.x}" y="${n.y}" width="${nodeW}" height="${nodeH}" rx="5" fill="${fillCol}" stroke="${strokeCol}" stroke-width="1.8" />` +
            `<circle cx="${n.x + 11}" cy="${n.y + nodeH / 2}" r="3.5" fill="${strokeCol}" />` +
            `<text x="${n.x + 20}" y="${n.y + 21}" fill="${textCol}" font-family="JetBrains Mono, monospace" font-size="10.5" font-weight="700">${n.name.slice(0, 14)}</text>` +
            (hopBadge
              ? `<text x="${n.x + nodeW - 8}" y="${n.y + 20}" text-anchor="end" fill="${strokeCol}" font-family="JetBrains Mono, monospace" font-size="9" font-weight="700" opacity="0.9">${hopBadge}</text>`
              : "") +
          `</g>`
        );
      } else {
        nodeRects.push(
          `<g opacity="0.35">` +
            `<rect x="${n.x}" y="${n.y}" width="${nodeW}" height="${nodeH}" rx="5" fill="#18181b" stroke="#3f3f46" stroke-width="1" />` +
            `<text x="${n.x + 12}" y="${n.y + 21}" fill="#71717a" font-family="JetBrains Mono, monospace" font-size="10">${n.name.slice(0, 16)}</text>` +
          `</g>`
        );
      }
    });
  });

  const coiSvgMarkup = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${svgW} ${svgH}" width="${svgW}px" height="${svgH}px" class="bg-[#09090b] rounded">
      <defs>
        <linearGradient id="coi-grad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#22d3ee" />
          <stop offset="50%" stop-color="#10b981" />
          <stop offset="100%" stop-color="#f59e0b" />
        </linearGradient>
      </defs>
      <rect width="${svgW}" height="${svgH}" fill="#09090b" />
      ${bgEdges.join("")}
      ${activeEdges.join("")}
      ${nodeRects.join("")}
    </svg>
  `;

  let stageEl = document.getElementById("coi-schematic-stage");
  if (!stageEl) {
    graphBox.innerHTML = `
      <div id="coi-studio-panel" class="flex flex-col h-full min-h-[460px] rounded-lg border border-[#242429] bg-[#09090b] overflow-hidden">
        <div class="px-3 py-2 flex flex-wrap items-center justify-between gap-2 bg-[#141418] border-b border-[#242429] z-20 shrink-0">
          <div class="flex items-center gap-3 flex-wrap text-[11px] font-mono-code">
            <span class="flex items-center gap-1.5 text-cyan-300 font-semibold">
              <span class="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_#22d3ee]"></span>
              <span id="coi-legend-active-cnt">Active COI Cone (${activeSet.size} signals)</span>
            </span>
            <span class="flex items-center gap-1.5 text-emerald-300 font-semibold">
              <span class="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
              Sequential FFs
            </span>
            <span class="flex items-center gap-1.5 text-amber-300 font-semibold">
              <span class="w-2.5 h-2.5 rounded-full bg-amber-400"></span>
              COI Target Output
            </span>
            <span class="flex items-center gap-1.5 text-zinc-500">
              <span class="w-2.5 h-2.5 rounded-full bg-zinc-700"></span>
              Shaded Non-COI
            </span>
          </div>

          <div class="flex items-center gap-1">
            <span class="text-[10px] font-mono-code text-zinc-500 mr-1 hidden xl:inline">Drag to Pan • Scroll to Zoom</span>
            <button onclick="zoomStudioCentered('coi', 1.25)" title="Zoom In (+)" class="px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-xs font-mono-code text-zinc-200 transition">+</button>
            <button onclick="zoomStudioCentered('coi', 0.8)" title="Zoom Out (-)" class="px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-xs font-mono-code text-zinc-200 transition">−</button>
            <button onclick="fitSchematicToViewport('coi')" title="Fit COI Graph to Window" class="px-2 py-0.5 rounded bg-cyan-500/20 border border-cyan-500/40 hover:bg-cyan-500/30 text-[11px] font-mono-code text-cyan-300 font-semibold transition">Fit</button>
            <button onclick="resetStudioTo100('coi')" id="coi-zoom-label" title="Reset to Centered 100%" class="px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-[11px] font-mono-code text-zinc-300 transition">100%</button>
            <button onclick="toggleStudioFullscreen('coi-studio-panel')" title="Maximize COI Graph Fullscreen" class="p-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"/>
              </svg>
            </button>
          </div>
        </div>

        <div id="coi-schematic-viewport" class="schematic-interactive-viewport blueprint-grid flex-1 w-full min-h-[410px] cursor-grab active:cursor-grabbing">
          <div id="coi-schematic-stage" class="schematic-stage-box"></div>
        </div>
      </div>
    `;
    bindInteractivePanZoom("coi-schematic-viewport", "coi");
    stageEl = document.getElementById("coi-schematic-stage");
  }

  const cntLbl = document.getElementById("coi-legend-active-cnt");
  if (cntLbl) {
    cntLbl.textContent = `Active COI Cone (${activeSet.size} signals)`;
  }

  if (stageEl) {
    stageEl.innerHTML = coiSvgMarkup;
    if (STATE.waveViewMode === "coi_graph") {
      requestAnimationFrame(() => fitSchematicToViewport("coi"));
    }
  }
}

function applyWaveformHorizontalScale() {
  const svgEl = document.querySelector("#wavedrom-container svg");
  const lblEl = document.getElementById("wave-zoom-label");
  if (lblEl) lblEl.textContent = `${Math.round(STATE.waveTimeScale * 100)}%`;
  if (!svgEl) return;

  if (!STATE.waveBaseSvgWidth || !STATE.waveBaseSvgHeight) {
    const dims = getIntrinsicSvgSize(svgEl);
    STATE.waveBaseSvgWidth = dims.w;
    STATE.waveBaseSvgHeight = dims.h;
  }

  const scaledW = Math.round(STATE.waveBaseSvgWidth * STATE.waveTimeScale);
  const lockedH = STATE.waveBaseSvgHeight;

  svgEl.setAttribute("preserveAspectRatio", "none");
  svgEl.setAttribute("width", `${scaledW}px`);
  svgEl.setAttribute("height", `${lockedH}px`);
  svgEl.style.width = `${scaledW}px`;
  svgEl.style.height = `${lockedH}px`;

  const invScaleX = (1 / STATE.waveTimeScale).toFixed(4);
  svgEl.querySelectorAll("text").forEach((tNode) => {
    tNode.style.transformBox = "fill-box";
    tNode.style.transformOrigin = "left center";
    tNode.style.transform = `scaleX(${invScaleX})`;
  });
}

function zoomWaveformHorizontal(factor) {
  STATE.waveTimeScale = Math.min(6.0, Math.max(0.35, STATE.waveTimeScale * factor));
  if (STATE.bundle) renderWaveDromDiagramOnly(STATE.bundle);
  else applyWaveformHorizontalScale();
}

function fitWaveformHorizontal() {
  const vp = document.getElementById("wave-schematic-viewport");
  if (!vp || !STATE.waveBaseSvgWidth) {
    STATE.waveTimeScale = 1.0;
    applyWaveformHorizontalScale();
    return;
  }
  const availW = Math.max(240, vp.clientWidth - 32);
  STATE.waveTimeScale = Math.min(3.0, Math.max(0.4, availW / STATE.waveBaseSvgWidth));
  if (STATE.bundle) renderWaveDromDiagramOnly(STATE.bundle);
  else applyWaveformHorizontalScale();
}

function resetWaveformHorizontal100() {
  STATE.waveTimeScale = 1.0;
  if (STATE.bundle) renderWaveDromDiagramOnly(STATE.bundle);
  else applyWaveformHorizontalScale();
}

function toggleWaveformFullscreen() {
  const target = document.getElementById("wave-fullscreen-target");
  if (!target) return;
  if (!document.fullscreenElement) {
    target
      .requestFullscreen()
      .then(() => {
        setTimeout(() => applyWaveformHorizontalScale(), 100);
      })
      .catch(() => {});
  } else {
    document.exitFullscreen().catch(() => {});
  }
}

function renderWaveDromDiagramOnly(bundle) {
  const rawWdData = bundle.wavedrom_json || { signal: [] };
  if (!Array.isArray(rawWdData.signal) || rawWdData.signal.length === 0) {
    document.getElementById("wavedrom-container").innerHTML = `
      <div class="py-10 text-center text-xs text-slate-500">
        No digital waveform vectors generated yet. Run <code class="text-cyan-600 font-semibold">run_iverilog_simulation</code>.
      </div>
    `;
    return;
  }

  const { wd, fullValueMap } = sanitizeWaveDromForVivadoUx(rawWdData, STATE.waveTimeScale);
  document.getElementById("wavedrom-container").innerHTML =
    `<script type="WaveDrom">${JSON.stringify(wd)}<\/script>`;
  if (window.WaveDrom && typeof WaveDrom.ProcessAll === "function") {
    setTimeout(() => {
      WaveDrom.ProcessAll();
      const wdSvg = document.querySelector("#wavedrom-container svg");
      if (wdSvg) {
        const dims = getIntrinsicSvgSize(wdSvg);
        STATE.waveBaseSvgWidth = dims.w;
        STATE.waveBaseSvgHeight = dims.h;
        wdSvg.querySelectorAll("text").forEach((tNode) => {
          const txt = (tNode.textContent || "").trim();
          if (fullValueMap[txt]) {
            const titleEl = document.createElementNS("http://www.w3.org/2000/svg", "title");
            titleEl.textContent = `Full Bus Value: ${fullValueMap[txt]}`;
            tNode.appendChild(titleEl);
          }
        });
      }
      applyWaveformHorizontalScale();
    }, 35);
  }
}

function renderDvStudioTab(bundle) {
  const simLog = bundle.sim_report_txt || "";
  const hasSimRun = simLog.trim().length > 0 && !simLog.startsWith("Awaiting");
  const simPass =
    hasSimRun && !simLog.toUpperCase().includes("FAIL") && !simLog.toUpperCase().includes("ERROR");

  const badge = document.getElementById("dv-sim-status-badge");
  badge.textContent = !hasSimRun ? "PENDING" : simPass ? "SIM PASS" : "SIM FAIL";
  badge.className = `font-mono-code text-[11px] px-2.5 py-0.5 rounded-full ${
    !hasSimRun ? "stage-pill-pending" : simPass ? "badge-pass" : "badge-fail"
  }`;
  document.getElementById("dv-sim-log-box").textContent = simLog || "Awaiting simulation run...";

  const rawSliceMd = bundle.wave_slice_md || "";
  const dedupedSliceMd = deduplicateMarkdownTableColumns(rawSliceMd);
  STATE.lastDedupedSliceMd = dedupedSliceMd;

  document.getElementById("coi-table-rendered").innerHTML = dedupedSliceMd.includes("|")
    ? parseMarkdownTablesToHtml(dedupedSliceMd)
    : `<div class="p-8 text-center text-xs text-zinc-500">No COI slice generated yet. Run <code class="text-cyan-400 font-semibold">read_coi_sliced_waveform</code> to isolate signals around t₀.</div>`;
  document.getElementById("coi-table-raw").textContent = dedupedSliceMd;

  renderCoiDependencyGraphSvg(bundle, dedupedSliceMd);
  setWaveTableMode(STATE.waveViewMode || "parsed");
  renderWaveDromDiagramOnly(bundle);
}

function setWaveTableMode(mode) {
  STATE.waveViewMode = mode || "parsed";
  const parsedEl = document.getElementById("coi-table-rendered");
  const graphEl = document.getElementById("coi-graph-visualizer");
  const rawEl = document.getElementById("coi-table-raw");

  if (parsedEl) parsedEl.classList.toggle("hidden", STATE.waveViewMode !== "parsed");
  if (graphEl) graphEl.classList.toggle("hidden", STATE.waveViewMode !== "coi_graph");
  if (rawEl) rawEl.classList.toggle("hidden", STATE.waveViewMode !== "raw");

  if (STATE.waveViewMode === "coi_graph" && STATE.bundle) {
    renderCoiDependencyGraphSvg(
      STATE.bundle,
      STATE.lastDedupedSliceMd || STATE.bundle.wave_slice_md || ""
    );
    requestAnimationFrame(() => fitSchematicToViewport("coi"));
  }

  const btnParsed = document.getElementById("btn-wave-parsed");
  const btnGraph = document.getElementById("btn-wave-coi-graph");
  const btnRaw = document.getElementById("btn-wave-raw");

  const activeCls =
    "px-2.5 py-1 rounded text-xs font-mono-code bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-semibold transition";
  const idleCls =
    "px-2.5 py-1 rounded text-xs font-mono-code bg-zinc-800 text-zinc-400 hover:text-zinc-100 border border-transparent transition";

  if (btnParsed) btnParsed.className = STATE.waveViewMode === "parsed" ? activeCls : idleCls;
  if (btnGraph) btnGraph.className = STATE.waveViewMode === "coi_graph" ? activeCls : idleCls;
  if (btnRaw) btnRaw.className = STATE.waveViewMode === "raw" ? activeCls : idleCls;
}
