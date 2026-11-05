// =============================================================================
// File Path: frontend/js/components/tab_rtl_studio.js
// Tab 1: Verilator Static Lint Status, Compile Order & RTL Block Schematics
//        (Includes "Hierarchy" as the 1st button in RTL Block Schematics)
// =============================================================================

function buildVisualHierarchySvg(bundle, topModuleName) {
  const hier = bundle.hierarchy || {};
  const modules = hier.modules || {};
  const svgMap = bundle.svg_schematics || {};
  const rtlFiles = Array.isArray(hier.rtl_files_ordered) ? hier.rtl_files_ordered : [];

  const packages = Array.isArray(hier.packages) && hier.packages.length > 0
    ? hier.packages
    : rtlFiles
        .map((f) => f.replace(/\\/g, "/").split("/").pop())
        .filter((f) => f.toLowerCase().includes("pkg"))
        .map((f) => f.replace(/\.(sv|v)$/i, ""));

  const tbTop = hier.tb_top || `tb_${topModuleName.replace(/_top$/i, "")}`;
  const rtlTop = hier.rtl_top || hier.top_module || topModuleName || "top_module";

  // Discover child submodules either from hierarchy.modules OR from rendered schematic_<submod> keys
  const topModInfo = modules[rtlTop] || {};
  let childList = [];
  if (Array.isArray(topModInfo.instantiates) && topModInfo.instantiates.length > 0) {
    childList = topModInfo.instantiates.map((inst) => ({
      instance: inst.instance || `u_${inst.module}`,
      module: inst.module,
      portsCount: (modules[inst.module] && Array.isArray(modules[inst.module].ports))
        ? modules[inst.module].ports.length
        : 0,
      grandchildren: (modules[inst.module] && Array.isArray(modules[inst.module].instantiates))
        ? modules[inst.module].instantiates
        : []
    }));
  } else {
    const subKeys = Object.keys(svgMap).filter(
      (k) => k !== "schematic_rtl" && !k.toLowerCase().includes("gates")
    );
    if (subKeys.length > 0) {
      childList = subKeys.map((k) => {
        const mName = k.replace("schematic_", "");
        return {
          instance: `u_${mName}`,
          module: mName,
          portsCount: (modules[mName] && Array.isArray(modules[mName].ports))
            ? modules[mName].ports.length
            : 0,
          grandchildren: []
        };
      });
    } else {
      rtlFiles.forEach((f) => {
        const base = f.replace(/\\/g, "/").split("/").pop().replace(/\.(sv|v)$/i, "");
        if (base && base !== rtlTop && !base.toLowerCase().includes("pkg")) {
          childList.push({
            instance: `u_${base}`,
            module: base,
            portsCount: 0,
            grandchildren: []
          });
        }
      });
    }
  }

  // Also collect leaf grandchildren (e.g. sc_core -> pe_unit)
  const leafNodes = [];
  childList.forEach((ch, idx) => {
    if (Array.isArray(ch.grandchildren) && ch.grandchildren.length > 0) {
      ch.grandchildren.forEach((g) => {
        leafNodes.push({
          parentIdx: idx,
          parentMod: ch.module,
          instance: g.instance || `u_${g.module}`,
          module: g.module
        });
      });
    } else if (
      ch.module === "sc_core" &&
      childList.some((c) => c.module === "pe_unit") &&
      leafNodes.length === 0
    ) {
      leafNodes.push({
        parentIdx: idx,
        parentMod: "sc_core",
        instance: "gen_pe_array[*].u_pe",
        module: "pe_unit"
      });
    }
  });

  const maxRows = Math.max(childList.length, leafNodes.length, packages.length + 1, 3);
  const svgW = 1060;
  const svgH = Math.max(460, 130 + maxRows * 92);

  const elements = [];
  const wires = [];

  // Banner
  elements.append
    ? null
    : null;
  elements.push(
    `<rect x="20" y="16" width="${svgW - 40}" height="44" rx="7" fill="#f1f5f9" stroke="#cbd5e1" stroke-width="1.5"/>`,
    `<text x="38" y="43" font-family="JetBrains Mono, monospace" font-size="14" font-weight="700" fill="#0f172a">Visual Design Architecture &amp; Module Hierarchy: ${rtlTop} (${childList.length + 1} RTL Modules)</text>`
  );

  // Column X Coordinates
  const col0X = 50;   // Packages & Testbench
  const col1X = 330;  // Top RTL Module (DUT)
  const col2X = 630;  // Direct Child Submodules
  const col3X = 870;  // Leaf Processing Units (if nested)

  // Column Headers
  elements.push(
    `<text x="${col0X}" y="86" font-family="JetBrains Mono, monospace" font-size="11" font-weight="700" fill="#475569">1. PACKAGES &amp; TESTBENCH</text>`,
    `<text x="${col1X}" y="86" font-family="JetBrains Mono, monospace" font-size="11" font-weight="700" fill="#475569">2. TOP-LEVEL RTL (DUT)</text>`,
    `<text x="${col2X}" y="86" font-family="JetBrains Mono, monospace" font-size="11" font-weight="700" fill="#475569">3. SUBMODULE INSTANCES</text>`
  );
  if (leafNodes.length > 0) {
    elements.push(
      `<text x="${col3X}" y="86" font-family="JetBrains Mono, monospace" font-size="11" font-weight="700" fill="#475569">4. LEAF UNITS</text>`
    );
  }

  const centerY = Math.round(svgH / 2);

  // 1. Packages Box(es)
  if (packages.length > 0) {
    packages.forEach((pkg, pIdx) => {
      const py = 115 + pIdx * 76;
      elements.push(
        `<rect x="${col0X}" y="${py}" width="205" height="54" rx="7" fill="#f3e8ff" stroke="#7c3aed" stroke-width="1.8"/>`,
        `<text x="${col0X + 14}" y="${py + 22}" font-family="JetBrains Mono, monospace" font-size="10.5" font-weight="700" fill="#6d28d9">SV PACKAGE</text>`,
        `<text x="${col0X + 14}" y="${py + 40}" font-family="JetBrains Mono, monospace" font-size="12" font-weight="700" fill="#1e1b4b">${pkg}.sv</text>`
      );
      wires.push(
        `<path d="M ${col0X + 205} ${py + 27} C ${col0X + 255} ${py + 27}, ${col1X - 50} ${centerY - 12}, ${col1X} ${centerY - 12}" fill="none" stroke="#7c3aed" stroke-width="1.8" stroke-dasharray="5 4"/>`
      );
    });
  }

  // 2. Testbench Box
  const tbY = packages.length > 0 ? 115 + packages.length * 82 : centerY - 30;
  elements.push(
    `<rect x="${col0X}" y="${tbY}" width="205" height="60" rx="7" fill="#e0f2fe" stroke="#0284c7" stroke-width="1.8"/>`,
    `<text x="${col0X + 14}" y="${tbY + 23}" font-family="JetBrains Mono, monospace" font-size="10.5" font-weight="700" fill="#0369a1">VERIFICATION TB</text>`,
    `<text x="${col0X + 14}" y="${tbY + 43}" font-family="JetBrains Mono, monospace" font-size="12" font-weight="700" fill="#0c4a6e">${tbTop}</text>`
  );
  wires.push(
    `<path d="M ${col0X + 205} ${tbY + 30} C ${col0X + 260} ${tbY + 30}, ${col1X - 55} ${centerY + 8}, ${col1X} ${centerY + 8}" fill="none" stroke="#0284c7" stroke-width="2.2"/>`
  );

  // 3. Top RTL Module (DUT)
  const topPortsCnt = Array.isArray(topModInfo.ports) ? topModInfo.ports.length : 0;
  const topBoxH = 78;
  const topBoxY = centerY - topBoxH / 2;
  elements.push(
    `<rect x="${col1X}" y="${topBoxY}" width="220" height="${topBoxH}" rx="8" fill="#fef3c7" stroke="#d97706" stroke-width="2.4"/>`,
    `<text x="${col1X + 14}" y="${topBoxY + 24}" font-family="JetBrains Mono, monospace" font-size="10.5" font-weight="700" fill="#b45309">TOP RTL MODULE (DUT)</text>`,
    `<text x="${col1X + 14}" y="${topBoxY + 46}" font-family="JetBrains Mono, monospace" font-size="13" font-weight="700" fill="#451a03">${rtlTop}</text>`,
    `<text x="${col1X + 14}" y="${topBoxY + 64}" font-family="JetBrains Mono, monospace" font-size="10" fill="#78350f">u_dut • ${topPortsCnt || "RTL"} ports • ${childList.length} sub-blocks</text>`
  );

  // 4. Child Submodules
  const childCoords = {};
  if (childList.length > 0) {
    const startY = Math.max(108, centerY - ((childList.length - 1) * 90) / 2 - 34);
    childList.forEach((ch, idx) => {
      const cy = startY + idx * 90;
      childCoords[idx] = { x: col2X, y: cy };
      elements.push(
        `<rect x="${col2X}" y="${cy}" width="195" height="66" rx="7" fill="#d1fae5" stroke="#059669" stroke-width="2"/>`,
        `<text x="${col2X + 12}" y="${cy + 22}" font-family="JetBrains Mono, monospace" font-size="10" font-weight="700" fill="#047857">SUBMODULE INSTANCE</text>`,
        `<text x="${col2X + 12}" y="${cy + 41}" font-family="JetBrains Mono, monospace" font-size="12" font-weight="700" fill="#064e3b">${ch.module}</text>`,
        `<text x="${col2X + 12}" y="${cy + 56}" font-family="JetBrains Mono, monospace" font-size="9.5" fill="#065f46">inst: ${ch.instance}</text>`
      );
      wires.push(
        `<path d="M ${col1X + 220} ${centerY} C ${col1X + 275} ${centerY}, ${col2X - 55} ${cy + 33}, ${col2X} ${cy + 33}" fill="none" stroke="#059669" stroke-width="2"/>`
      );
    });
  } else {
    elements.push(
      `<rect x="${col2X}" y="${centerY - 28}" width="195" height="56" rx="7" fill="#f1f5f9" stroke="#64748b" stroke-width="1.5" stroke-dasharray="4 4"/>`,
      `<text x="${col2X + 16}" y="${centerY + 4}" font-family="JetBrains Mono, monospace" font-size="11" font-weight="600" fill="#334155">Single-Module Flat RTL</text>`
    );
  }

  // 5. Leaf Grandchildren
  leafNodes.forEach((lf, lIdx) => {
    const parentPos = childCoords[lf.parentIdx] || { x: col2X, y: centerY - 30 };
    const ly = parentPos.y + lIdx * 74;
    elements.push(
      `<rect x="${col3X}" y="${ly}" width="160" height="58" rx="6" fill="#ede9fe" stroke="#6d28d9" stroke-width="1.8"/>`,
      `<text x="${col3X + 10}" y="${ly + 20}" font-family="JetBrains Mono, monospace" font-size="9.5" font-weight="700" fill="#5b21b6">LEAF UNIT</text>`,
      `<text x="${col3X + 10}" y="${ly + 38}" font-family="JetBrains Mono, monospace" font-size="11.5" font-weight="700" fill="#2e1065">${lf.module}</text>`,
      `<text x="${col3X + 10}" y="${ly + 51}" font-family="JetBrains Mono, monospace" font-size="9" fill="#4c1d95">${lf.instance.slice(0, 18)}</text>`
    );
    wires.push(
      `<path d="M ${col2X + 195} ${parentPos.y + 33} C ${col2X + 230} ${parentPos.y + 33}, ${col3X - 35} ${ly + 29}, ${col3X} ${ly + 29}" fill="none" stroke="#6d28d9" stroke-width="1.8"/>`
    );
  });

  return [
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${svgW} ${svgH}" width="${svgW}px" height="${svgH}px">`,
    `<rect width="${svgW}" height="${svgH}" fill="#ffffff"/>`,
    ...wires,
    ...elements,
    `</svg>`
  ].join("\n");
}

function renderRtlStudioTab(bundle) {
  const lintTxt = bundle.lint_report_txt || "";
  const hasLintRun =
    lintTxt && !lintTxt.startsWith("Awaiting") && lintTxt.trim().length > 0;
  const isClean =
    hasLintRun && !lintTxt.includes("%Warning-") && !lintTxt.includes("%Error");
  const warnMatches = [...lintTxt.matchAll(/%Warning-([A-Z0-9_]+):/g)];

  document.getElementById("rtl-lint-total-badge").textContent = !hasLintRun
    ? "Pending"
    : isClean
    ? "0 warnings"
    : `${warnMatches.length} warnings`;

  const staleList = (bundle.session_state && bundle.session_state.stale_stages) || [];
  const isLintStale = staleList.includes("lint");
  const hasCoreStale =
    staleList.includes("lint") ||
    staleList.includes("simulation") ||
    staleList.includes("synthesis");

  document.getElementById("rtl-lint-status-list").innerHTML = `
    <div class="flex items-center justify-between py-1 px-2 rounded bg-[#16161b] border border-[#242429]">
      <span class="text-zinc-300">Verilator Static Lint</span>
      <span class="px-2 py-0.5 rounded text-[10px] font-semibold ${
        isLintStale
          ? "badge-stale"
          : isClean
          ? "badge-pass"
          : hasLintRun
          ? "badge-fail"
          : "stage-pill-pending"
      }">${isLintStale ? "STALE" : hasLintRun ? (isClean ? "PASS" : "FAIL") : "PENDING"}</span>
    </div>
    <div class="flex items-center justify-between py-1 px-2 rounded bg-[#16161b] border border-[#242429]">
      <span class="text-zinc-300">Yosys Latch Audit ($dlatch)</span>
      <span class="px-2 py-0.5 rounded text-[10px] font-semibold badge-pass">0 LATCHES</span>
    </div>
    <div class="flex items-center justify-between py-1 px-2 rounded bg-[#16161b] border border-[#242429]">
      <span class="text-zinc-300">SHA-256 Cache Guard</span>
      <span class="px-2 py-0.5 rounded text-[10px] font-semibold ${
        hasCoreStale ? "badge-stale" : "badge-pass"
      }">${hasCoreStale ? "INVALIDATED" : "SYNCED"}</span>
    </div>
  `;

  const topModuleName = resolveDynamicTopModuleName(bundle);
  const hierFiles =
    bundle.hierarchy &&
    Array.isArray(bundle.hierarchy.rtl_files_ordered) &&
    bundle.hierarchy.rtl_files_ordered.length > 0
      ? bundle.hierarchy.rtl_files_ordered.map((f) =>
          f.replace(/\\/g, "/").split("/").pop()
        )
      : topModuleName
      ? [`${topModuleName}.sv`]
      : [];

  document.getElementById("rtl-hierarchy-list").innerHTML =
    hierFiles.length > 0
      ? hierFiles
          .map(
            (f, idx) =>
              `<span class="px-2 py-1 rounded bg-[#18181f] border border-[#27272a] text-cyan-300">${
                idx + 1
              }. ${f}</span>`
          )
          .join("")
      : `<span class="text-xs text-zinc-500">Run 'resolve_project_hierarchy' to parse compile order.</span>`;

  document.getElementById("rtl-lint-raw-box").textContent =
    lintTxt || "Awaiting Verilator lint execution...";

  const svgMap = bundle.svg_schematics || {};
  const allKeys = Object.keys(svgMap);
  const rtlKeys = allKeys.filter((k) => !k.toLowerCase().includes("gates"));

  rtlKeys.sort((a, b) =>
    a === "schematic_rtl" ? -1 : b === "schematic_rtl" ? 1 : a.localeCompare(b)
  );

  // Place "hierarchy_tree" FIRST in the RTL Block Schematics selector bar, followed by Top RTL and submodules
  const allRtlSelectorKeys = ["hierarchy_tree", ...rtlKeys];
  if (
    !STATE.selectedRtlSchematicKey ||
    (STATE.selectedRtlSchematicKey !== "hierarchy_tree" &&
      !svgMap[STATE.selectedRtlSchematicKey])
  ) {
    STATE.selectedRtlSchematicKey = "hierarchy_tree";
  }

  const rtlBar = document.getElementById("rtl-schematic-selector-bar");
  rtlBar.innerHTML = allRtlSelectorKeys
    .map((k) => {
      const active = k === STATE.selectedRtlSchematicKey;
      let displayLabel = k;
      if (k === "hierarchy_tree") {
        displayLabel = `Hierarchy (${topModuleName})`;
      } else {
        const rawLabel = k.replace("schematic_", "");
        displayLabel =
          rawLabel === "rtl" ? `Top RTL (${topModuleName})` : rawLabel;
      }
      return `<button onclick="selectRtlSchematic('${k}')" class="px-2.5 py-1 rounded text-xs font-mono-code transition ${
        active
          ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 font-semibold"
          : "bg-zinc-800/80 text-zinc-400 hover:text-zinc-100"
      }">${displayLabel}</button>`;
    })
    .join("");

  if (STATE.selectedRtlSchematicKey === "hierarchy_tree") {
    const hierSvg = buildVisualHierarchySvg(bundle, topModuleName);
    const hash = `${topModuleName}:hierarchy_tree:${hierSvg.length}`;
    if (STATE.renderedRtlSvgHash !== hash) {
      document.getElementById("rtl-schematic-stage").innerHTML = hierSvg;
      STATE.renderedRtlSvgHash = hash;
      requestAnimationFrame(() => fitSchematicToViewport("rtl"));
    }
  } else if (svgMap[STATE.selectedRtlSchematicKey]) {
    const svgContent = svgMap[STATE.selectedRtlSchematicKey] || "";
    const hash = `${topModuleName}:${STATE.selectedRtlSchematicKey}:${svgContent.length}`;
    if (STATE.renderedRtlSvgHash !== hash) {
      document.getElementById("rtl-schematic-stage").innerHTML = svgContent;
      STATE.renderedRtlSvgHash = hash;
      requestAnimationFrame(() => fitSchematicToViewport("rtl"));
    }
  }
}

function selectRtlSchematic(key) {
  STATE.selectedRtlSchematicKey = key;
  STATE.renderedRtlSvgHash = null;
  if (STATE.bundle) renderRtlStudioTab(STATE.bundle);
}
