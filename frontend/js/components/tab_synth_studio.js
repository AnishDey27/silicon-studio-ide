// =============================================================================
// File Path: frontend/js/components/tab_synth_studio.js
// Tab 3: Multi-PDK PPA Matrix, Visual Area Bars, Hamming Power & Gate Netlists
// =============================================================================

function renderSynthStudioTab(bundle) {
  const ppaMd = bundle.ppa_comparison_matrix_md || "";
  document.getElementById("ppa-table-container").innerHTML = ppaMd.includes("|")
    ? parseMarkdownTablesToHtml(ppaMd)
    : `<div class="p-6 text-center text-xs text-zinc-500">Run <code class="text-emerald-400 font-semibold">run_yosys_synthesis</code> to benchmark PPA across Sky130, Nangate45, and ASAP7.</div>`;

  const barsEl = document.getElementById("ppa-visual-bars");
  if (barsEl) {
    const parsedRows = [];
    if (ppaMd.includes("|")) {
      const lines = ppaMd.split(/\r?\n/);
      for (const line of lines) {
        const t = line.trim();
        if (!t.startsWith("|") || !t.endsWith("|")) continue;
        const cols = t
          .slice(1, -1)
          .split("|")
          .map((c) => cleanMathText(c.trim()));
        if (
          cols.length >= 6 &&
          !cols[0].toLowerCase().includes("target") &&
          !/^[-:]+$/.test(cols[0])
        ) {
          const areaVal = parseFloat(cols[5].replace(/[^0-9.]/g, "")) || 0;
          parsedRows.push({
            target: cols[0],
            mode: cols[1],
            comb: cols[2],
            dff: cols[3],
            totalCells: cols[4],
            areaStr: cols[5],
            areaNum: areaVal,
            ltp: cols[7] || cols[6] || "N/A"
          });
        }
      }
    }
    if (parsedRows.length > 0) {
      const maxArea = Math.max(...parsedRows.map((r) => r.areaNum), 1);
      const accents = ["cyan", "emerald", "purple", "amber"];
      barsEl.innerHTML = parsedRows
        .map((r, i) => {
          const col = accents[i % accents.length];
          const pct =
            r.areaNum > 0
              ? Math.max(8, Math.min(100, Math.round((r.areaNum / maxArea) * 100)))
              : 25;
          const badgeText =
            !r.ltp || r.ltp.startsWith("0 ") ? `${r.totalCells} cells` : r.ltp;
          return `<div class="p-3 rounded-lg bg-[#15151a] border border-[#242429] flex flex-col justify-between">
          <div class="flex items-center justify-between">
            <span class="text-xs font-semibold font-mono-code text-zinc-100 uppercase">${r.target}</span>
            <span class="text-[10px] font-mono-code px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300">${badgeText}</span>
          </div>
          <div class="text-base font-bold font-mono-code text-${col}-400 mt-1.5">${
            r.areaStr !== "—" ? r.areaStr + " µm²" : r.totalCells + " cells"
          }</div>
          <div class="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden my-1.5">
            <div class="h-full bg-${col}-400 rounded-full" style="width:${pct}%"></div>
          </div>
          <div class="flex items-center justify-between text-[10.5px] font-mono-code text-zinc-400">
            <span>Comb: ${r.comb}</span>
            <span>DFF: ${r.dff}</span>
          </div>
        </div>`;
        })
        .join("");
    } else {
      barsEl.innerHTML = "";
    }
  }

  const pwr = bundle.power_activity || {};
  const totalToggles = pwr.total_bit_hamming_toggles || 0;
  document.getElementById("power-total-toggles").textContent = `${totalToggles} Bit Flips`;

  document.getElementById("power-kpi-cards").innerHTML = `
    <div class="p-2.5 rounded-lg bg-[#15151a] border border-[#27272a]">
      <div class="text-[10px] text-zinc-400 uppercase">Sampled Cycles</div>
      <div class="text-sm font-bold font-mono-code text-zinc-100 mt-0.5">${
        pwr.sampled_cycles || 0
      }</div>
    </div>
    <div class="p-2.5 rounded-lg bg-[#15151a] border border-[#27272a]">
      <div class="text-[10px] text-zinc-400 uppercase">Event Toggles</div>
      <div class="text-sm font-bold font-mono-code text-cyan-400 mt-0.5">${
        pwr.total_signal_event_toggles || 0
      }</div>
    </div>
    <div class="p-2.5 rounded-lg bg-[#15151a] border border-[#27272a]">
      <div class="text-[10px] text-zinc-400 uppercase">Flips / Cycle</div>
      <div class="text-sm font-bold font-mono-code text-emerald-400 mt-0.5">${
        pwr.avg_bit_toggles_per_cycle || 0
      }</div>
    </div>
  `;

  const sigs = Array.isArray(pwr.signals) ? pwr.signals.slice(0, 8) : [];
  document.getElementById("power-signals-table").innerHTML =
    sigs.length > 0
      ? `
    <table class="data-grid-table">
      <thead><tr><th>Signal</th><th>Width</th><th>Events</th><th>Hamming Flips</th><th>Alpha (α)</th></tr></thead>
      <tbody>
        ${sigs
          .map(
            (s) => `
          <tr>
            <td>${s.signal}</td>
            <td>${s.width_bits}b</td>
            <td>${s.event_toggle_count}</td>
            <td class="text-amber-300 font-semibold">${s.bit_hamming_toggles}</td>
            <td>${s.bit_activity_factor_alpha}</td>
          </tr>
        `
          )
          .join("")}
      </tbody>
    </table>
  `
      : `<div class="p-4 text-center text-xs text-zinc-500">No activity data yet.</div>`;

  // Synthesized Gate-Level Netlists Studio
  const topModuleName = resolveDynamicTopModuleName(bundle);
  const svgMap = bundle.svg_schematics || {};
  const gatesKeys = Object.keys(svgMap).filter((k) => k.toLowerCase().includes("gates"));

  const gatesBar = document.getElementById("gates-schematic-selector-bar");
  if (gatesKeys.length > 0) {
    if (!STATE.selectedGatesSchematicKey || !svgMap[STATE.selectedGatesSchematicKey]) {
      STATE.selectedGatesSchematicKey =
        gatesKeys.find((k) => k.includes("asap7")) || gatesKeys[0];
    }
    gatesBar.innerHTML = gatesKeys
      .map((k) => {
        const active = k === STATE.selectedGatesSchematicKey;
        const label = k.replace("schematic_", "");
        return `<button onclick="selectGatesSchematic('${k}')" class="px-2.5 py-1 rounded text-xs font-mono-code transition ${
          active
            ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-semibold"
            : "bg-zinc-800/80 text-zinc-400 hover:text-zinc-100"
        }">${label}</button>`;
      })
      .join("");

    const gContent = svgMap[STATE.selectedGatesSchematicKey] || "";
    const gHash = `${topModuleName}:${STATE.selectedGatesSchematicKey}:${gContent.length}`;
    if (STATE.renderedGatesSvgHash !== gHash) {
      document.getElementById("gates-schematic-stage").innerHTML = gContent;
      STATE.renderedGatesSvgHash = gHash;
      requestAnimationFrame(() => fitSchematicToViewport("gates"));
    }
  } else {
    gatesBar.innerHTML = `<span class="text-xs font-mono-code text-zinc-400 px-2 py-0.5 rounded bg-zinc-800 border border-zinc-700">Gate Netlist</span>`;
    document.getElementById("gates-schematic-stage").innerHTML = `
      <div class="flex flex-col items-center justify-center h-[420px] text-center p-8">
        <svg class="w-12 h-12 text-zinc-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/>
        </svg>
        <div class="text-sm font-semibold text-zinc-300">No Gate Netlists Synthesized</div>
        <p class="text-xs text-zinc-500 max-w-sm mt-1">Run <code class="text-emerald-400">run_yosys_synthesis</code> (asap7, nangate45, or sky130) to map standard cells and view gate schematics.</p>
      </div>
    `;
    STATE.renderedGatesSvgHash = `EMPTY_GATES_${topModuleName}`;
  }
}

function selectGatesSchematic(key) {
  STATE.selectedGatesSchematicKey = key;
  STATE.renderedGatesSvgHash = null;
  if (STATE.bundle) renderSynthStudioTab(STATE.bundle);
}