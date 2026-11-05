# =============================================================================
# File Path: backend/engines/coi_slicer_engine.py
# =============================================================================
"""Neuro-Symbolic Cone-of-Influence (COI) Graph Builder & Dual-Edge VCD Waveform Slicer.

Fixes:
1. Preserves unpacked array element indices (`pm_reg[0]`, `pm_reg[1]`, `path_mem[0]`) via
   `_strip_bit_range_preserve_array_index()` instead of blindly stripping everything after `[`
   (which previously turned `pm_reg[0]` into `pm_reg` and broke explicit signal matching).
2. Tags every signal node in `build_rtl_dependency_graph()` and `coi_details` with
   `"is_seq": True/False` based on whether it is driven by a Yosys sequential `$dff`/`$adff` cell,
   so the Tab 2 COI Graph Visualizer places `pm_reg[0]`, `pm_reg[1]`, and `state_q` directly
   into the `SEQ REGISTERS (FF)` column.
3. Adds an Icarus Verilog unpacked-array packed-bus proxy resolver in `_match_vcd_signal_against_coi()`
   so if `iverilog` `$dumpvars(0, tb)` did not dump an unpacked SystemVerilog array (`pm_reg[0]`),
   its packed concatenation bus (`pm_in_packed`, `sorted_pm`) is automatically matched and a clear
   `unpacked_array_proxy_notes` field is returned so the agent never falls back to `read_waveform`.
4. Deduplicates VCD signals by `vcd_id` AND leaf name in `_parse_vcd()` (preferring the DUT scope
   over testbench top-level wire aliases) so `clk` and `decoded_u_o` never appear twice.
"""
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import networkx as nx

SEQ_CELL_KEYWORDS = (
    "$dff",
    "$dffe",
    "$adff",
    "$adffe",
    "$sdff",
    "$sdffe",
    "$sdffce",
    "$dffsr",
    "$dffsre",
    "$dlatch",
    "$adlatch",
    "$mem",
    "$_dff",
    "$_sdff",
    "$_dlatch",
)

CLK_RST_PIN_NAMES = {
    "CLK",
    "C",
    "CK",
    "ARST",
    "SRST",
    "RST",
    "RST_N",
    "RESET_B",
    "RN",
    "SN",
    "R",
    "S",
    "CLR",
    "SET",
    "RD_CLK",
    "WR_CLK",
}


def _strip_bit_range_preserve_array_index(raw_name: str) -> str:
    """Strips bit-slice ranges like `[7:0]` while preserving unpacked array indices like `[0]`.

    Examples:
      `best_pm_o[7:0]`       -> `best_pm_o`
      `\\pm_reg[0] [7:0]`    -> `pm_reg[0]`
      `pm_reg[0][7:0]`       -> `pm_reg[0]`
      `pm_reg[0]`            -> `pm_reg[0]`
    """
    s = str(raw_name or "").strip().lstrip("\\")
    # Remove any bit-range `[MSB:LSB]` or `[idx+:width]` (brackets containing `:`)
    s = re.sub(r"\s*\[\s*[^\[\]:]+\s*:\s*[^\[\]]+\s*\]", "", s)
    # Collapse any space before a remaining single-index bracket `[0]`
    s = re.sub(r"\s+\[(\d+)\]", r"[\1]", s)
    return s.strip()


def _base_ident_without_brackets(raw_name: str) -> str:
    """Returns the base identifier with all brackets removed (e.g. `pm_reg[0]` -> `pm_reg`)."""
    return _strip_bit_range_preserve_array_index(raw_name).split("[")[0].strip()


def _is_sequential_cell(cell_type: str) -> bool:
    low = cell_type.lower()
    return any(low.startswith(k) or k in low for k in SEQ_CELL_KEYWORDS)


def _is_sequential_signal_name(net_name: str) -> bool:
    base = _base_ident_without_brackets(net_name.split(".")[-1]).lower()
    return (
        base.endswith("_q")
        or "_reg" in base
        or base.startswith("reg_")
        or "state" in base
        or "cnt" in base
        or "count" in base
        or "ptr" in base
        or "mem" in base
    )


def _is_clock_or_reset_net(net_name: str) -> bool:
    base = _base_ident_without_brackets(net_name.split(".")[-1]).lower()
    if any(
        k in base
        for k in ("clk", "clock", "wclk", "rclk", "wr_clk", "rd_clk", "pclk", "aclk")
    ):
        return True
    if any(
        k in base
        for k in (
            "rst",
            "reset",
            "arst",
            "srst",
            "aresetn",
            "wr_rst",
            "rd_rst",
        )
    ):
        return True
    return False


def _is_clock_only(net_name: str) -> bool:
    base = _base_ident_without_brackets(net_name.split(".")[-1]).lower()
    return any(
        k in base
        for k in ("clk", "clock", "wclk", "rclk", "wr_clk", "rd_clk", "pclk", "aclk")
    )


def _resolve_cell_port_directions(
    cell_info: Dict[str, Any], modules: Dict[str, Any]
) -> Dict[str, str]:
    p_dirs = dict(cell_info.get("port_directions", {}))
    c_type = cell_info.get("type", "")
    if not p_dirs and c_type in modules:
        for sp_name, sp_info in modules[c_type].get("ports", {}).items():
            p_dirs[sp_name] = sp_info.get("direction", "input")
    return p_dirs


def build_rtl_dependency_graph(
    netlist_json_path: Path, include_clk_rst_edges: bool = False
) -> nx.DiGraph:
    """Builds a multi-module directed signal dependency graph from Yosys `synth_netlist.json`."""
    data = json.loads(netlist_json_path.read_text(encoding="utf-8"))
    modules = data.get("modules", {})
    graph = nx.DiGraph()

    top_mod_name = next(
        (
            m_name
            for m_name, m_data in modules.items()
            if int(m_data.get("attributes", {}).get("top", "0"), 2) == 1
        ),
        next(iter(modules.keys()), ""),
    )

    for mod_name, mod_data in modules.items():
        bit_to_public_names: Dict[int, List[str]] = {}
        is_top = mod_name == top_mod_name

        for net_name, net_info in mod_data.get("netnames", {}).items():
            if net_info.get("hide_name", 0) == 0 and not net_name.startswith("$"):
                clean_net = _strip_bit_range_preserve_array_index(net_name)
                bits = [b for b in net_info.get("bits", []) if isinstance(b, int)]
                qualified_name = clean_net if is_top else f"{mod_name}.{clean_net}"
                for b in bits:
                    bit_to_public_names.setdefault(b, []).append(qualified_name)
                graph.add_node(
                    qualified_name,
                    short_name=clean_net,
                    module=mod_name,
                    width=len(bits),
                    is_seq=_is_sequential_signal_name(clean_net),
                    is_clock_or_reset=_is_clock_or_reset_net(clean_net),
                )

        for cell_name, cell_info in mod_data.get("cells", {}).items():
            cell_type = cell_info.get("type", "")
            port_dirs = _resolve_cell_port_directions(cell_info, modules)
            conns = cell_info.get("connections", {})
            is_seq = _is_sequential_cell(cell_type)

            in_bits: Set[int] = set()
            out_bits: Set[int] = set()

            for p_name, bits in conns.items():
                p_dir = port_dirs.get(p_name, "input")
                int_bits = [b for b in bits if isinstance(b, int)]
                if p_dir in ("output", "inout"):
                    out_bits.update(int_bits)
                else:
                    if (
                        not include_clk_rst_edges
                        and is_seq
                        and p_name.upper() in CLK_RST_PIN_NAMES
                    ):
                        continue
                    in_bits.update(int_bits)

            # Mark any public net driven by a sequential cell as `is_seq = True`
            if is_seq:
                for ob in out_bits:
                    for pub_dst in bit_to_public_names.get(ob, []):
                        if graph.has_node(pub_dst):
                            graph.nodes[pub_dst]["is_seq"] = True

            for ib in in_bits:
                b_node = f"{mod_name}:bit_{ib}"
                for pub_src in bit_to_public_names.get(ib, []):
                    if not include_clk_rst_edges and _is_clock_or_reset_net(pub_src):
                        continue
                    graph.add_edge(
                        pub_src, b_node, via="net", is_seq=False, is_bit_hop=True
                    )
                for ob in out_bits:
                    ob_node = f"{mod_name}:bit_{ob}"
                    graph.add_edge(
                        b_node,
                        ob_node,
                        via=cell_type,
                        cell=cell_name,
                        is_seq=is_seq,
                        is_bit_hop=False,
                    )
                    for pub_dst in bit_to_public_names.get(ob, []):
                        graph.add_edge(
                            ob_node, pub_dst, via="net", is_seq=False, is_bit_hop=True
                        )

            if cell_type in modules:
                clean_inst = cell_name.lstrip("$").split(".")[-1]
                for p_name, bits in conns.items():
                    p_dir = port_dirs.get(p_name, "input")
                    int_bits = [b for b in bits if isinstance(b, int)]
                    sub_mod_node = (
                        p_name if cell_type == top_mod_name else f"{cell_type}.{p_name}"
                    )
                    inst_port_node = f"{clean_inst}.{p_name}"
                    if not graph.has_node(inst_port_node):
                        graph.add_node(
                            inst_port_node,
                            short_name=p_name,
                            module=cell_type,
                            instance=clean_inst,
                            width=len(int_bits),
                            is_seq=False,
                            is_clock_or_reset=_is_clock_or_reset_net(p_name),
                        )

                    if p_dir == "input":
                        for ib in int_bits:
                            for pub_src in bit_to_public_names.get(ib, []):
                                if not include_clk_rst_edges and _is_clock_or_reset_net(
                                    pub_src
                                ):
                                    continue
                                graph.add_edge(
                                    pub_src,
                                    sub_mod_node,
                                    via=f"submod_in:{clean_inst}({cell_type})",
                                    is_seq=False,
                                    is_bit_hop=False,
                                )
                                graph.add_edge(
                                    pub_src,
                                    inst_port_node,
                                    via=f"submod_in:{clean_inst}",
                                    is_seq=False,
                                    is_bit_hop=False,
                                )
                                graph.add_edge(
                                    inst_port_node,
                                    sub_mod_node,
                                    via="net",
                                    is_seq=False,
                                    is_bit_hop=True,
                                )
                    elif p_dir in ("output", "inout"):
                        for ob in int_bits:
                            for pub_dst in bit_to_public_names.get(ob, []):
                                graph.add_edge(
                                    sub_mod_node,
                                    pub_dst,
                                    via=f"submod_out:{clean_inst}({cell_type})",
                                    is_seq=False,
                                    is_bit_hop=False,
                                )
                                graph.add_edge(
                                    sub_mod_node,
                                    inst_port_node,
                                    via="net",
                                    is_seq=False,
                                    is_bit_hop=True,
                                )
                                graph.add_edge(
                                    inst_port_node,
                                    pub_dst,
                                    via=f"submod_out:{clean_inst}",
                                    is_seq=False,
                                    is_bit_hop=False,
                                )

    return graph


def _resolve_signal_node_in_graph(
    graph: nx.DiGraph, raw_target: str
) -> Optional[str]:
    clean = _strip_bit_range_preserve_array_index(raw_target)
    if clean in graph and ":bit_" not in clean:
        return clean
    short = clean.split(".")[-1].strip()
    if short in graph and ":bit_" not in short:
        return short
    public_nodes = [str(n) for n in graph.nodes if ":bit_" not in str(n)]
    for n in public_nodes:
        if n.split(".")[-1].lower() == short.lower():
            return n
    base_no_idx = _base_ident_without_brackets(short).lower()
    for n in public_nodes:
        if _base_ident_without_brackets(n.split(".")[-1]).lower() == base_no_idx:
            return n
    for n in public_nodes:
        if short.lower() in n.lower():
            return n
    return None


def _trace_single_target_coi(
    search_graph: nx.DiGraph,
    base_graph: nx.DiGraph,
    resolved_target: str,
    max_hops: int,
) -> Dict[str, Dict[str, Any]]:
    effective_hops = min(max(max_hops, 1), 6)
    paths = nx.single_source_shortest_path(
        search_graph, resolved_target, cutoff=effective_hops * 3
    )
    cone_map: Dict[str, Dict[str, Any]] = {}

    for node, path_nodes in paths.items():
        node_str = str(node)
        if ":bit_" in node_str:
            continue
        seq_hops = 0
        comb_hops = 0
        driving_cells: List[str] = []

        for i in range(len(path_nodes) - 1):
            u, v = path_nodes[i], path_nodes[i + 1]
            edge_data = search_graph.get_edge_data(u, v) or {}
            via = edge_data.get("via", "net")
            if via != "net":
                driving_cells.append(via)
                if edge_data.get("is_seq", False):
                    seq_hops += 1
                else:
                    comb_hops += 1

        total_logical_hops = seq_hops + comb_hops
        if total_logical_hops <= effective_hops:
            node_meta = base_graph.nodes[node]
            short_n = node_meta.get("short_name", node_str.split(".")[-1])
            is_seq_node = bool(
                node_meta.get("is_seq", False)
                or _is_sequential_signal_name(short_n)
            )
            cone_map[node_str] = {
                "signal": node_str,
                "short_name": short_n,
                "module": node_meta.get("module", ""),
                "width": node_meta.get("width", 1),
                "is_seq": is_seq_node,
                "logical_hops": total_logical_hops,
                "combinational_hops": comb_hops,
                "sequential_depth_cycles": seq_hops,
                "via_cells": driving_cells[:6],
            }

    return cone_map


def _extract_public_signal_edges(
    base_graph: nx.DiGraph,
    coi_public_nodes: Set[str],
    all_displayed_nodes: Set[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Collapses `:bit_X` intermediate nodes in `base_graph` into true directed signal-to-signal edges (`src -> dst`).

    Returns `(coi_edges, background_edges)` where every edge represents an actual
    hardware dependency in Yosys `synth_netlist.json`.
    """
    coi_edges: List[Dict[str, Any]] = []
    bg_edges: List[Dict[str, Any]] = []
    seen_pairs: Set[Tuple[str, str]] = set()

    # For each displayed signal node, find public signals 1 cell-hop (up to 3 graph steps across :bit_ nodes) downstream
    for src_node in sorted(all_displayed_nodes):
        if src_node not in base_graph:
            continue
        src_short = base_graph.nodes[src_node].get(
            "short_name", str(src_node).split(".")[-1]
        )
        # BFS up to depth 3 through `:bit_` nodes to find immediate public signal sinks
        queue: List[Tuple[str, int, str]] = [(src_node, 0, "net")]
        visited_local: Set[str] = {src_node}

        while queue:
            curr, depth, via_cell = queue.pop(0)
            if depth >= 3:
                continue
            for _, nxt, edata in base_graph.edges(curr, data=True):
                nxt_str = str(nxt)
                edge_via = edata.get("via", "net")
                effective_via = edge_via if edge_via != "net" else via_cell
                if ":bit_" in nxt_str:
                    if nxt_str not in visited_local:
                        visited_local.add(nxt_str)
                        queue.append((nxt_str, depth + 1, effective_via))
                else:
                    dst_short = base_graph.nodes[nxt].get(
                        "short_name", nxt_str.split(".")[-1]
                    )
                    if src_short != dst_short:
                        pair = (src_short, dst_short)
                        if pair not in seen_pairs:
                            seen_pairs.add(pair)
                            edge_obj = {
                                "source": src_short,
                                "target": dst_short,
                                "source_full": str(src_node),
                                "target_full": nxt_str,
                                "via": effective_via,
                            }
                            if (
                                str(src_node) in coi_public_nodes
                                and nxt_str in coi_public_nodes
                            ):
                                coi_edges.append(edge_obj)
                            elif (
                                str(src_node) in all_displayed_nodes
                                and nxt_str in all_displayed_nodes
                            ):
                                bg_edges.append(edge_obj)

    return coi_edges, bg_edges


def extract_coi_subgraph(
    netlist_json_path: Path,
    target_signals: Union[str, List[str]],
    max_hops: int = 4,
    direction: str = "backward",
    combine_mode: str = "union",
    max_signals_cap: int = 16,
) -> Dict[str, Any]:
    """Traces the backward/forward Cone of Influence and persists `coi_graph.json` for UI visualization."""
    if not netlist_json_path.exists():
        return {
            "status": "ERROR",
            "message": f"Netlist JSON not found: {netlist_json_path}.",
        }

    if isinstance(target_signals, str):
        raw_targets = [t.strip() for t in target_signals.split(",") if t.strip()]
    else:
        raw_targets = [
            sub.strip()
            for item in target_signals
            for sub in str(item).split(",")
            if sub.strip()
        ]

    if not raw_targets:
        return {"status": "ERROR", "message": "No target_signals provided."}

    base_graph = build_rtl_dependency_graph(
        netlist_json_path, include_clk_rst_edges=False
    )
    available_public = sorted(
        [str(n) for n in base_graph.nodes if ":bit_" not in str(n)]
    )

    resolved_targets: List[str] = []
    unresolved_targets: List[str] = []
    for rt in raw_targets:
        matched = _resolve_signal_node_in_graph(base_graph, rt)
        if matched:
            if matched not in resolved_targets:
                resolved_targets.append(matched)
        else:
            unresolved_targets.append(rt)

    if not resolved_targets:
        return {
            "status": "NOT_FOUND",
            "message": f"Signal(s) {raw_targets} not found in synthesized netlist.",
            "available_signals": available_public[:40],
        }

    dir_norm = direction.strip().lower()
    if dir_norm == "forward":
        search_graphs = [base_graph]
    elif dir_norm == "both":
        search_graphs = [base_graph.reverse(copy=False), base_graph]
    else:
        dir_norm = "backward"
        search_graphs = [base_graph.reverse(copy=False)]

    per_target_cones: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for tgt in resolved_targets:
        merged_for_tgt: Dict[str, Dict[str, Any]] = {}
        for sg in search_graphs:
            c_map = _trace_single_target_coi(
                sg, base_graph, tgt, max_hops=min(max_hops, 4)
            )
            for sig_k, sig_v in c_map.items():
                if (
                    sig_k not in merged_for_tgt
                    or sig_v["logical_hops"] < merged_for_tgt[sig_k]["logical_hops"]
                ):
                    merged_for_tgt[sig_k] = sig_v
        per_target_cones[tgt] = merged_for_tgt

    mode_norm = combine_mode.strip().lower()
    all_target_keys = list(per_target_cones.keys())
    if mode_norm == "intersection" and len(all_target_keys) > 1:
        common_keys = set(per_target_cones[all_target_keys[0]].keys())
        for tk in all_target_keys[1:]:
            common_keys &= set(per_target_cones[tk].keys())
        combined_keys = common_keys
    else:
        mode_norm = "union"
        union_keys: Set[str] = set()
        for tk in all_target_keys:
            union_keys |= set(per_target_cones[tk].keys())
        combined_keys = union_keys

    coi_details: List[Dict[str, Any]] = []
    for k in combined_keys:
        best_entry = min(
            (
                per_target_cones[tk][k]
                for tk in all_target_keys
                if k in per_target_cones[tk]
            ),
            key=lambda x: (x["logical_hops"], x["sequential_depth_cycles"]),
        )
        coi_details.append(best_entry)

    coi_details.sort(
        key=lambda x: (
            x["logical_hops"],
            x["sequential_depth_cycles"],
            x["signal"],
        )
    )
    coi_details = coi_details[:max_signals_cap]

    coi_signal_names: List[str] = []
    sequential_coi_signals: List[str] = []
    combinational_coi_signals: List[str] = []
    coi_public_node_set: Set[str] = set()
    for item in coi_details:
        coi_public_node_set.add(item["signal"])
        if item["signal"] not in coi_signal_names:
            coi_signal_names.append(item["signal"])
        if item["short_name"] not in coi_signal_names:
            coi_signal_names.append(item["short_name"])
        if item.get("is_seq"):
            if item["short_name"] not in sequential_coi_signals:
                sequential_coi_signals.append(item["short_name"])
        else:
            if item["short_name"] not in combinational_coi_signals:
                combinational_coi_signals.append(item["short_name"])

    displayed_node_set = set(available_public[:48]) | coi_public_node_set
    coi_edges, bg_edges = _extract_public_signal_edges(
        base_graph, coi_public_node_set, displayed_node_set
    )

    result_payload = {
        "status": "SUCCESS",
        "target_signal": resolved_targets[0],
        "target_signals_resolved": resolved_targets,
        "unresolved_targets": unresolved_targets,
        "direction": dir_norm,
        "combine_mode": mode_norm,
        "max_hops": min(max_hops, 4),
        "coi_signal_count": len(coi_details),
        "coi_signals": coi_signal_names,
        "sequential_coi_signals": sequential_coi_signals,
        "combinational_coi_signals": combinational_coi_signals,
        "coi_details": coi_details,
        "coi_edges": coi_edges,
        "background_edges": bg_edges[:90],
        "all_design_signals": available_public[:48],
    }

    try:
        sim_dir = netlist_json_path.parent.parent / "simulation"
        sim_dir.mkdir(parents=True, exist_ok=True)
        (sim_dir / "coi_graph.json").write_text(
            json.dumps(result_payload, indent=2) + "\n", encoding="utf-8"
        )
    except Exception:
        pass

    return result_payload


def _parse_time_to_ps(time_str: Optional[str], default_ps: int = 0) -> int:
    if not time_str:
        return default_ps
    s = str(time_str).strip().lower()
    m = re.match(r"^([+-]?[0-9.]+)\s*(ps|ns|us|ms|s)?$", s)
    if not m:
        return default_ps
    val = float(m.group(1))
    unit = m.group(2) or "ns"
    mult = {"ps": 1, "ns": 1000, "us": 1_000_000, "ms": 1_000_000_000}.get(unit, 1000)
    return int(round(val * mult))


def _parse_vcd(vcd_path: Path) -> Dict[str, Any]:
    """Parses VCD declarations, preserving unpacked array indices (`pm_reg[0]`) and deduplicating shared `vcd_id` aliases."""
    raw = vcd_path.read_text(encoding="utf-8", errors="replace")
    timescale_ps = 1
    ts_match = re.search(r"\$timescale\s+(\d+)\s*(fs|ps|ns|us)\s+\$end", raw, re.DOTALL)
    if ts_match:
        mag = int(ts_match.group(1))
        unit = ts_match.group(2).lower()
        timescale_ps = mag * {"fs": 1, "ps": 1, "ns": 1000, "us": 1_000_000}.get(unit, 1)

    scopes: List[str] = []
    primary_by_id: Dict[str, Dict[str, Any]] = {}
    aliases_by_id: Dict[str, List[str]] = {}

    lines = raw.splitlines()
    idx = 0
    n_lines = len(lines)

    while idx < n_lines:
        line = lines[idx].strip()
        idx += 1
        if not line:
            continue
        if line.startswith("$scope"):
            parts = line.split()
            if len(parts) >= 3:
                scopes.append(parts[2])
        elif line.startswith("$upscope"):
            if scopes:
                scopes.pop()
        elif line.startswith("$var"):
            # Example: `$var wire 8 ! \pm_reg[0] [7:0] $end` or `$var wire 8 ! best_pm_o [7:0] $end`
            parts = line.split()
            if len(parts) >= 5:
                v_type = parts[1].lower()
                width = int(parts[2]) if parts[2].isdigit() else 1
                v_id = parts[3]
                # Join tokens between v_id and `$end`
                end_idx = len(parts) - 1 if parts[-1] == "$end" else len(parts)
                raw_name = " ".join(parts[4:end_idx])
                clean_name = _strip_bit_range_preserve_array_index(raw_name)
                full_name = ".".join(scopes + [clean_name])
                aliases_by_id.setdefault(v_id, []).append(full_name)

                sig_entry = {
                    "id": v_id,
                    "name": clean_name,
                    "base_name": _base_ident_without_brackets(clean_name),
                    "full_name": full_name,
                    "scope": ".".join(scopes),
                    "scope_depth": len(scopes),
                    "width": width,
                    "var_type": v_type,
                    "aliases": aliases_by_id[v_id],
                }
                if v_id not in primary_by_id:
                    primary_by_id[v_id] = sig_entry
                else:
                    existing = primary_by_id[v_id]
                    if existing["scope_depth"] == 1 and len(scopes) == 2 and v_type != "parameter":
                        primary_by_id[v_id] = sig_entry
        elif line.startswith("$enddefinitions"):
            break

    all_signals = list(primary_by_id.values())

    timestamps_ps: List[int] = []
    snapshots: List[Dict[str, str]] = []
    current_vals: Dict[str, str] = {}
    current_ps: Optional[int] = None

    while idx < n_lines:
        line = lines[idx].strip()
        idx += 1
        if not line or line.startswith("$"):
            continue
        if line.startswith("#"):
            if current_ps is not None:
                timestamps_ps.append(current_ps)
                snapshots.append(dict(current_vals))
            try:
                current_ps = int(line[1:]) * timescale_ps
            except ValueError:
                current_ps = 0
        elif line[0] in "01xzXZ":
            val = line[0].lower()
            v_id = line[1:].strip()
            current_vals[v_id] = val
        elif line[0] in "bB":
            parts = line.split()
            if len(parts) >= 2:
                current_vals[parts[1].strip()] = parts[0][1:].lower()

    if current_ps is not None:
        timestamps_ps.append(current_ps)
        snapshots.append(dict(current_vals))

    return {
        "timescale_ps": timescale_ps,
        "signals": all_signals,
        "timestamps_ps": timestamps_ps,
        "snapshots": snapshots,
    }


def _format_val(raw_val: str, width: int) -> str:
    if not raw_val:
        return "x"
    low = raw_val.lower()
    if "x" in low or "z" in low:
        return low
    if width == 1:
        return low[-1]
    try:
        ival = int(low, 2)
        hex_digits = max(1, (width + 3) // 4)
        return f"0x{ival:0{hex_digits}X}"
    except ValueError:
        return low


def _hamming_distance(v1: str, v2: str, width: int) -> int:
    if not v1 or not v2 or v1 == v2:
        return 0
    if any(c in v1.lower() for c in "xz") or any(c in v2.lower() for c in "xz"):
        return 1
    try:
        i1 = int(v1, 2)
        i2 = int(v2, 2)
        return bin(i1 ^ i2).count("1")
    except ValueError:
        return 1


def _match_vcd_signal_against_coi(
    sig: Dict[str, Any],
    coi_targets: Set[str],
    explicit_targets: Set[str],
) -> Tuple[bool, int]:
    """Strictly matches a VCD signal (including unpacked array elements and packed-bus proxies) against COI/explicit targets."""
    short_n = sig["name"].lower()
    base_n = sig.get("base_name", _base_ident_without_brackets(short_n)).lower()
    full_n = sig["full_name"].lower()
    aliases = [a.lower() for a in sig.get("aliases", [full_n])]
    parts = full_n.split(".")
    dut_rel = ".".join(parts[2:]) if len(parts) > 2 else (".".join(parts[1:]) if len(parts) > 1 else full_n)

    if _is_clock_only(short_n) and len(parts) <= 3:
        return True, 0

    for exp in explicit_targets:
        exp_clean = _strip_bit_range_preserve_array_index(exp).lower()
        exp_base = _base_ident_without_brackets(exp_clean).lower()
        if not exp_clean:
            continue
        if (
            short_n == exp_clean
            or base_n == exp_clean
            or full_n == exp_clean
            or dut_rel == exp_clean
            or any(a == exp_clean or a.endswith("." + exp_clean) for a in aliases)
        ):
            return True, 1
        # Packed-bus proxy match when Icarus Verilog omits an unpacked array element (e.g. `pm_reg[0]` -> `pm_in_packed` / `sorted_pm`)
        if "[" in exp_clean and len(exp_base) >= 4:
            prefix = exp_base.split("_")[0]
            if len(prefix) >= 2 and (
                short_n.startswith(prefix + "_") or short_n.endswith("_" + prefix)
            ):
                return True, 2

    for cf in coi_targets:
        cf_clean = _strip_bit_range_preserve_array_index(cf).lower()
        if not cf_clean:
            continue
        cf_leaf = cf_clean.split(".")[-1]
        cf_base = _base_ident_without_brackets(cf_leaf)
        if (
            full_n == cf_clean
            or dut_rel == cf_clean
            or any(a == cf_clean or a.endswith("." + cf_clean) for a in aliases)
        ):
            return True, 2
        if (short_n == cf_leaf or base_n == cf_base) and len(parts) <= 4:
            return True, 3

    return False, 99


def _compact_header_name(sig: Dict[str, Any], seen_short: Dict[str, int]) -> str:
    short = sig["name"]
    if seen_short.get(short, 0) <= 1:
        return short
    parts = sig["full_name"].split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else short


def convert_vcd_to_artifacts(
    vcd_path: Path,
    work_dir: Path,
    filter_signals: Optional[Set[str]] = None,
    explicit_signals: Optional[Union[str, List[str]]] = None,
    start_cycle: int = 0,
    end_cycle: Optional[int] = None,
    center_time: Optional[str] = None,
    window_before: str = "-30ns",
    window_after: str = "+10ns",
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    hide_constant_signals: bool = False,
    max_slice_signals: int = 14,
    max_slice_rows: int = 16,
) -> Dict[str, Any]:
    """Converts `wave.vcd` into full artifacts (`wave_full.md`, `power_activity.json`, `wavedrom_full.json`)
    OR into a compact, deduplicated COI Dual-Edge slice (`wave_slice.md`).
    """
    sim_dir = work_dir / "simulation"
    reports_dir = work_dir / "reports"
    sim_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    parsed = _parse_vcd(vcd_path)
    signals = parsed["signals"]
    timestamps_ps = parsed["timestamps_ps"]
    snapshots = parsed["snapshots"]

    dynamic_signals: List[Dict[str, Any]] = []
    for s in signals:
        if s["var_type"] in ("parameter", "real"):
            continue
        vid = s["id"]
        distinct_vals = {snap.get(vid, "") for snap in snapshots if vid in snap}
        if s["var_type"] == "integer" and len(distinct_vals) <= 1:
            continue
        dynamic_signals.append(s)

    total_event_toggles = 0
    total_hamming_toggles = 0
    per_sig_power: List[Dict[str, Any]] = []
    x_z_anomalies: List[Dict[str, Any]] = []
    n_snaps = max(1, len(snapshots))

    for s in dynamic_signals:
        vid = s["id"]
        w = s["width"]
        ev_cnt = 0
        ham_cnt = 0
        prev_v: Optional[str] = None
        for t_idx, snap in enumerate(snapshots):
            cur_v = snap.get(vid, "")
            if not cur_v:
                continue
            if ("x" in cur_v.lower() or "z" in cur_v.lower()) and timestamps_ps[t_idx] > 0:
                if len(x_z_anomalies) < 12:
                    x_z_anomalies.append(
                        {
                            "signal": s["full_name"],
                            "time_ns": round(timestamps_ps[t_idx] / 1000.0, 3),
                            "value": cur_v,
                        }
                    )
            if prev_v is not None and cur_v != prev_v:
                ev_cnt += 1
                ham_cnt += _hamming_distance(prev_v, cur_v, w)
            prev_v = cur_v

        total_event_toggles += ev_cnt
        total_hamming_toggles += ham_cnt
        per_sig_power.append(
            {
                "signal": s["name"],
                "hier_name": s["full_name"],
                "full_name": s["full_name"],
                "width_bits": w,
                "width": w,
                "event_toggle_count": ev_cnt,
                "event_toggles": ev_cnt,
                "bit_hamming_toggles": ham_cnt,
                "bit_activity_factor_alpha": round(ham_cnt / float(w * n_snaps), 4),
                "activity_factor_alpha": round(ham_cnt / float(w * n_snaps), 4),
            }
        )

    per_sig_power.sort(key=lambda x: x["bit_hamming_toggles"], reverse=True)
    power_payload = {
        "sampled_cycles": n_snaps,
        "unique_signals_tracked": len(dynamic_signals),
        "total_signal_event_toggles": total_event_toggles,
        "total_bit_hamming_toggles": total_hamming_toggles,
        "avg_bit_toggles_per_cycle": round(total_hamming_toggles / float(n_snaps), 3),
        "signals": per_sig_power[:20],
        "top_switching_signals": per_sig_power[:20],
    }
    (reports_dir / "power_activity.json").write_text(
        json.dumps(power_payload, indent=2) + "\n", encoding="utf-8"
    )

    exp_set: Set[str] = set()
    if explicit_signals:
        if isinstance(explicit_signals, str):
            exp_set = {x.strip().lower() for x in explicit_signals.split(",") if x.strip()}
        else:
            exp_set = {
                sub.strip().lower()
                for item in explicit_signals
                for sub in str(item).split(",")
                if sub.strip()
            }

    coi_set = {x.strip().lower() for x in (filter_signals or set()) if x.strip()}
    is_sliced = bool(
        coi_set
        or exp_set
        or center_time is not None
        or start_time is not None
        or end_time is not None
        or start_cycle > 0
        or end_cycle is not None
    )

    if coi_set or exp_set:
        scored_matches: List[Tuple[int, int, Dict[str, Any]]] = []
        seen_leaf_names: Set[str] = set()
        for idx_s, s in enumerate(dynamic_signals):
            matched, rank = _match_vcd_signal_against_coi(s, coi_set, exp_set)
            if matched:
                leaf_low = s["name"].lower()
                if leaf_low not in seen_leaf_names:
                    seen_leaf_names.add(leaf_low)
                    scored_matches.append((rank, idx_s, s))
        scored_matches.sort(key=lambda x: (x[0], x[1]))
        selected_sigs = [item[2] for item in scored_matches[:max_slice_signals]]
        if not selected_sigs:
            selected_sigs = dynamic_signals[: min(10, len(dynamic_signals))]
    else:
        seen_leaf_names = set()
        selected_sigs = []
        for s in dynamic_signals:
            leaf_low = s["name"].lower()
            if leaf_low not in seen_leaf_names:
                seen_leaf_names.add(leaf_low)
                selected_sigs.append(s)
        if is_sliced and len(selected_sigs) > max_slice_signals:
            selected_sigs = selected_sigs[:max_slice_signals]

    # Identify any requested unpacked array signals not dumped by Icarus Verilog `$dumpvars`
    vcd_leaf_set = {s["name"].lower() for s in dynamic_signals}
    unpacked_array_notes: List[str] = []
    for req_sig in sorted(exp_set | coi_set):
        req_clean = _strip_bit_range_preserve_array_index(req_sig).split(".")[-1].lower()
        if "[" in req_clean and req_clean not in vcd_leaf_set:
            unpacked_array_notes.append(
                f"'{req_clean}' is a SystemVerilog unpacked array element omitted by Icarus Verilog `$dumpvars(0, tb)` in `wave.vcd`; "
                f"its values are directly observable in the slice via its packed bus signals (e.g., `pm_in_packed`, `sorted_pm`). "
                f"Do NOT call `read_waveform` — `wave.vcd` does not contain separate VCD `$var` entries for unpacked array elements."
            )

    anchor_ps: Optional[int] = None
    if center_time:
        anchor_ps = _parse_time_to_ps(center_time, 0)
        t_min = max(0, anchor_ps + _parse_time_to_ps(window_before, -30000))
        t_max = anchor_ps + abs(_parse_time_to_ps(window_after, 10000))
    elif start_time or end_time:
        t_min = _parse_time_to_ps(start_time, 0)
        t_max = _parse_time_to_ps(
            end_time, timestamps_ps[-1] if timestamps_ps else 100000
        )
    elif is_sliced and timestamps_ps:
        anchor_ps = timestamps_ps[-1]
        t_min = max(0, anchor_ps - 40000)
        t_max = anchor_ps
    else:
        t_min = timestamps_ps[min(start_cycle, len(timestamps_ps) - 1)] if timestamps_ps else 0
        t_max = (
            timestamps_ps[min(end_cycle, len(timestamps_ps) - 1)]
            if (end_cycle is not None and timestamps_ps)
            else (timestamps_ps[-1] if timestamps_ps else 0)
        )

    window_indices = [
        i for i, t_ps in enumerate(timestamps_ps) if t_min <= t_ps <= t_max
    ]
    if not window_indices and timestamps_ps:
        window_indices = list(range(max(0, len(timestamps_ps) - 10), len(timestamps_ps)))

    if (hide_constant_signals or is_sliced) and len(window_indices) > 1:
        non_const: List[Dict[str, Any]] = []
        for s in selected_sigs:
            vid = s["id"]
            vals_in_win = {snapshots[i].get(vid, "0") for i in window_indices}
            is_target = any(
                s["name"].lower() == _strip_bit_range_preserve_array_index(t).split(".")[-1].lower()
                for t in (coi_set | exp_set)
            )
            if len(vals_in_win) > 1 or _is_clock_only(s["name"]) or is_target:
                non_const.append(s)
        if non_const:
            selected_sigs = non_const

    if is_sliced and len(window_indices) > 1:
        active_indices: List[int] = []
        prev_tuple_vals: Optional[Tuple[str, ...]] = None
        for idx_w in window_indices:
            cur_tuple = tuple(
                snapshots[idx_w].get(s["id"], "0") for s in selected_sigs
            )
            is_anchor = anchor_ps is not None and abs(timestamps_ps[idx_w] - anchor_ps) <= 1000
            if cur_tuple != prev_tuple_vals or is_anchor:
                active_indices.append(idx_w)
                prev_tuple_vals = cur_tuple
        if len(active_indices) > max_slice_rows:
            if anchor_ps is not None:
                active_indices.sort(key=lambda i: abs(timestamps_ps[i] - anchor_ps))
                active_indices = sorted(active_indices[:max_slice_rows])
            else:
                active_indices = active_indices[-max_slice_rows:]
        window_indices = active_indices

    short_counts: Dict[str, int] = {}
    for s in selected_sigs:
        short_counts[s["name"]] = short_counts.get(s["name"], 0) + 1
    headers = [_compact_header_name(s, short_counts) for s in selected_sigs]

    md_lines = [
        "> **Dual-Edge COI Temporal Slice (`t` vs `t - 1ps`)**"
        if is_sliced
        else "> **Full Simulation Waveform Table (`wave_full.md`)**",
        "",
        "### Table 1: Post-Posedge Registered State (`at t`)",
        "| Time | " + " | ".join(headers) + " |",
        "| :--- | " + " | ".join(":---:" for _ in headers) + " |",
    ]

    for i in window_indices:
        t_ns = timestamps_ps[i] / 1000.0
        is_t0 = anchor_ps is not None and abs(timestamps_ps[i] - anchor_ps) <= 500
        t_label = f"**[t0] {t_ns:g}ns**" if is_t0 else f"{t_ns:g}ns"
        row_vals = [
            _format_val(snapshots[i].get(s["id"], "0"), s["width"])
            for s in selected_sigs
        ]
        md_lines.append("| " + t_label + " | " + " | ".join(row_vals) + " |")

    setup_indices = (
        window_indices[-min(6, len(window_indices)) :]
        if is_sliced
        else window_indices[: min(25, len(window_indices))]
    )
    md_lines.extend(
        [
            "",
            "### Table 2: Pre-Posedge Combinational Setup (`at t - 1ps`)",
            "| Time (`t - 1ps`) | " + " | ".join(headers) + " |",
            "| :--- | " + " | ".join(":---:" for _ in headers) + " |",
        ]
    )

    for i in setup_indices:
        prev_i = max(0, i - 1)
        t_ns = timestamps_ps[i] / 1000.0
        is_t0 = anchor_ps is not None and abs(timestamps_ps[i] - anchor_ps) <= 500
        t_label = f"**[t0-1ps] {t_ns:g}ns**" if is_t0 else f"{t_ns:g}ns - 1ps"
        row_vals = [
            _format_val(snapshots[prev_i].get(s["id"], "0"), s["width"])
            for s in selected_sigs
        ]
        md_lines.append("| " + t_label + " | " + " | ".join(row_vals) + " |")

    table_md_text = "\n".join(md_lines) + "\n"

    wd_signals: List[Dict[str, Any]] = []
    sorted_for_wd = sorted(
        selected_sigs,
        key=lambda s: (0 if _is_clock_only(s["name"]) else 1, s["name"]),
    )
    wd_indices = window_indices[:48]
    for s in sorted_for_wd[:24]:
        vid = s["id"]
        w = s["width"]
        wave_chars: List[str] = []
        data_items: List[str] = []
        last_tok: Optional[str] = None
        for i in wd_indices:
            raw_v = snapshots[i].get(vid, "0")
            if "x" in raw_v.lower() or "z" in raw_v.lower():
                tok = "x"
            elif w == 1:
                tok = "1" if raw_v[-1] == "1" else "0"
            else:
                tok = "="
            if tok == last_tok and tok in ("0", "1", "x"):
                wave_chars.append(".")
            elif tok == "=" and last_tok == "=" and data_items and data_items[-1] == _format_val(raw_v, w):
                wave_chars.append(".")
            else:
                wave_chars.append(tok)
                if tok == "=":
                    data_items.append(_format_val(raw_v, w))
                last_tok = tok
        entry: Dict[str, Any] = {"name": s["name"], "wave": "".join(wave_chars)}
        if data_items:
            entry["data"] = data_items
        wd_signals.append(entry)

    wavedrom_payload = {"signal": wd_signals}

    if is_sliced:
        out_md = sim_dir / "wave_slice.md"
        out_wd = sim_dir / "wavedrom_slice.json"
        out_md.write_text(table_md_text, encoding="utf-8")
        out_wd.write_text(json.dumps(wavedrom_payload, indent=2) + "\n", encoding="utf-8")
        shutil.copy2(out_md, sim_dir / "wave_slice_diagnostic.md")
    else:
        out_md = sim_dir / "wave_full.md"
        out_wd = sim_dir / "wavedrom_full.json"
        out_md.write_text(table_md_text, encoding="utf-8")
        out_wd.write_text(json.dumps(wavedrom_payload, indent=2) + "\n", encoding="utf-8")
        diag_slice = sim_dir / "wave_slice_diagnostic.md"
        slice_path = sim_dir / "wave_slice.md"
        if diag_slice.exists() and not slice_path.exists():
            shutil.copy2(diag_slice, slice_path)

    return {
        "status": "SUCCESS",
        "is_sliced": is_sliced,
        "slice_file_written": out_md.name,
        "signals_included": headers,
        "unpacked_array_proxy_notes": unpacked_array_notes[:4],
        "rows_included": len(window_indices),
        "char_count": len(table_md_text),
        "estimated_tokens": max(1, len(table_md_text) // 4),
        "anchor_t0_ns": (anchor_ps / 1000.0) if anchor_ps is not None else None,
        "x_z_anomalies": x_z_anomalies,
        "power_activity": power_payload,
        "cycle_table_md": table_md_text,
        "wavedrom_json": wavedrom_payload,
    }
