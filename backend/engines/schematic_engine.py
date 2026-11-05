# =============================================================================
# File Path: backend/engines/schematic_engine.py
# =============================================================================
"""Pure SVG Schematic Renderer for Word-Level RTL & Staged Gate-Level Netlists.

Renders crisp, interactive SVG schematics directly from Yosys JSON netlists
(`build/netlists/synth_netlist.json` and `build/netlists/mapped_<target>/synth_gates.json`)
without requiring external Graphviz `dot.exe`:
- `schematic_rtl.svg` (Top-level RTL block & word-level operator schematic)
- `schematic_<submodule>.svg` (Per-submodule word-level datapath schematics)
- `schematic_gates_<target>.svg` (Staged topological gate-level netlist schematics)
"""
import html
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

STUDIO_ROOT = Path(__file__).resolve().parents[2]
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

from backend.core.workspace_manager import ensure_project_structure, get_project_dir
from backend.engines.synth_engine import execute_yosys_synthesis

SEQ_KEYWORDS = (
    "$dff", "$dffe", "$adff", "$adffe", "$sdff", "$sdffe", "$dlatch",
    "$_dff", "$_sdff", "dff", "dfrtp", "dfxtp", "fdre",
)


def _is_seq_type(c_type: str) -> bool:
    low = c_type.lower()
    return any(k in low for k in SEQ_KEYWORDS)


def _friendly_cell_label(cell_type: str) -> str:
    clean = cell_type.lstrip("$").lstrip("_")
    mapping = {
        "add": "ADD (+)",
        "sub": "SUB (-)",
        "mul": "MUL (*)",
        "mux": "MUX",
        "pmux": "PMUX",
        "eq": "CMP (==)",
        "ne": "CMP (!=)",
        "lt": "CMP (<)",
        "le": "CMP (<=)",
        "gt": "CMP (>)",
        "ge": "CMP (>=)",
        "and": "AND",
        "or": "OR",
        "xor": "XOR",
        "xnor": "XNOR",
        "not": "INV",
        "logic_not": "NOT",
        "logic_and": "LAND",
        "logic_or": "LOR",
        "reduce_or": "RED_OR",
        "reduce_and": "RED_AND",
        "reduce_xor": "RED_XOR",
        "shl": "SHL (<<)",
        "shr": "SHR (>>)",
        "adff": "DFF (AsyncRst)",
        "sdff": "DFF (SyncRst)",
        "dff": "DFF",
        "dffe": "DFFE",
    }
    return mapping.get(clean.lower(), clean)


def _render_module_svg(
    mod_name: str,
    mod_data: Dict[str, Any],
    all_modules: Dict[str, Any],
    title_banner: str,
    max_cells: int = 42,
) -> str:
    """Renders a staged left-to-right schematic SVG for a Yosys JSON module."""
    ports = mod_data.get("ports", {})
    raw_cells = mod_data.get("cells", {})

    in_ports: List[Tuple[str, int, List[int]]] = []
    out_ports: List[Tuple[str, int, List[int]]] = []
    for p_name, p_info in sorted(ports.items()):
        p_dir = p_info.get("direction", "input")
        bits = [b for b in p_info.get("bits", []) if isinstance(b, int)]
        if p_dir in ("output", "inout"):
            out_ports.append((p_name, len(bits), bits))
        else:
            in_ports.append((p_name, len(bits), bits))

    # Filter out internal scopeinfo cells and cap display cells for clean visual layout
    cell_items = [
        (c_name, c_info)
        for c_name, c_info in sorted(raw_cells.items())
        if not c_info.get("type", "").startswith("$scopeinfo")
    ]
    total_cells_count = len(cell_items)
    displayed_cells = cell_items[:max_cells]

    submod_cells: List[Tuple[str, Dict[str, Any]]] = []
    comb_cells: List[Tuple[str, Dict[str, Any]]] = []
    seq_cells: List[Tuple[str, Dict[str, Any]]] = []

    for c_name, c_info in displayed_cells:
        c_type = c_info.get("type", "")
        if c_type in all_modules and c_type != mod_name:
            submod_cells.append((c_name, c_info))
        elif _is_seq_type(c_type):
            seq_cells.append((c_name, c_info))
        else:
            comb_cells.append((c_name, c_info))

    # Organize middle columns
    mid_columns: List[Tuple[str, List[Tuple[str, Dict[str, Any]]]]] = []
    if submod_cells:
        mid_columns.append(("Submodule Blocks", submod_cells))
    if comb_cells:
        mid_columns.append(("Combinational / Logic Stage", comb_cells[:22]))
        if len(comb_cells) > 22:
            mid_columns.append(("Datapath / Gate Stage 2", comb_cells[22:42]))
    if seq_cells:
        mid_columns.append(("Sequential Registers (FF)", seq_cells[:22]))

    if not mid_columns:
        mid_columns.append(("Pass-Through Interconnect", []))

    col_count = len(mid_columns) + 2
    col_spacing = 290
    margin_x = 60
    margin_y = 82
    svg_w = max(960, margin_x * 2 + (col_count - 1) * col_spacing + 180)

    max_rows = max(
        len(in_ports),
        len(out_ports),
        *(len(col_list) for _, col_list in mid_columns),
        4,
    )
    row_spacing = 54
    svg_h = max(440, margin_y + max_rows * row_spacing + 80)

    bit_sources: Dict[int, List[Tuple[float, float]]] = {}
    bit_sinks: Dict[int, List[Tuple[float, float]]] = {}

    elements: List[str] = []

    # Title Banner
    trunc_note = (
        f" (Showing {len(displayed_cells)} of {total_cells_count} cells)"
        if total_cells_count > len(displayed_cells)
        else f" ({total_cells_count} cells)"
    )
    elements.append(
        f'<rect x="16" y="14" width="{svg_w - 32}" height="42" rx="6" fill="#f1f5f9" stroke="#cbd5e1" stroke-width="1.2"/>'
    )
    elements.append(
        f'<text x="32" y="40" font-family="JetBrains Mono, monospace" font-size="14" font-weight="700" fill="#0f172a">'
        f"{html.escape(title_banner)}{html.escape(trunc_note)}</text>"
    )

    # Column 0: Input Ports
    in_x = margin_x
    elements.append(
        f'<text x="{in_x}" y="{margin_y - 12}" font-family="JetBrains Mono, monospace" font-size="11" font-weight="700" fill="#475569">PRIMARY INPUTS</text>'
    )
    for idx, (p_name, width, bits) in enumerate(in_ports):
        py = margin_y + idx * row_spacing
        w_tag = f"[{width - 1}:0]" if width > 1 else ""
        label = f"{p_name}{w_tag}"
        elements.append(
            f'<rect x="{in_x}" y="{py}" width="150" height="32" rx="5" fill="#e0f2fe" stroke="#0284c7" stroke-width="1.5"/>'
        )
        elements.append(
            f'<text x="{in_x + 10}" y="{py + 20}" font-family="JetBrains Mono, monospace" font-size="11" font-weight="600" fill="#0369a1">{html.escape(label[:20])}</text>'
        )
        pin_x, pin_y = in_x + 150, py + 16
        elements.append(f'<circle cx="{pin_x}" cy="{pin_y}" r="3.5" fill="#0284c7"/>')
        for b in bits:
            bit_sources.setdefault(b, []).append((pin_x, pin_y))

    # Middle Columns: Submodules, Combinational Logic, Sequential FFs
    for c_idx, (col_title, c_list) in enumerate(mid_columns):
        cx = margin_x + (c_idx + 1) * col_spacing
        elements.append(
            f'<text x="{cx}" y="{margin_y - 12}" font-family="JetBrains Mono, monospace" font-size="11" font-weight="700" fill="#475569">{html.escape(col_title.upper())}</text>'
        )
        for r_idx, (c_name, c_info) in enumerate(c_list):
            cy = margin_y + r_idx * row_spacing
            c_type = c_info.get("type", "")
            is_sub = c_type in all_modules and c_type != mod_name
            is_seq = _is_seq_type(c_type)

            if is_sub:
                fill_c, stroke_c, txt_c = "#fef3c7", "#d97706", "#92400e"
                hdr = f"INST: {c_name.split('$')[-1][:14]}"
                sub = c_type[:20]
            elif is_seq:
                fill_c, stroke_c, txt_c = "#d1fae5", "#059669", "#065f46"
                hdr = _friendly_cell_label(c_type)[:18]
                sub = c_name.split("$")[-1][:18]
            else:
                fill_c, stroke_c, txt_c = "#f3e8ff", "#7c3aed", "#5b21b6"
                hdr = _friendly_cell_label(c_type)[:18]
                sub = c_name.split("$")[-1][:18]

            box_w, box_h = 175, 38
            elements.append(
                f'<rect x="{cx}" y="{cy}" width="{box_w}" height="{box_h}" rx="6" fill="{fill_c}" stroke="{stroke_c}" stroke-width="1.5"/>'
            )
            elements.append(
                f'<text x="{cx + 10}" y="{cy + 16}" font-family="JetBrains Mono, monospace" font-size="10.5" font-weight="700" fill="{txt_c}">{html.escape(hdr)}</text>'
            )
            elements.append(
                f'<text x="{cx + 10}" y="{cy + 30}" font-family="JetBrains Mono, monospace" font-size="9.5" fill="#475569">{html.escape(sub)}</text>'
            )

            in_pin_x, in_pin_y = cx, cy + box_h / 2
            out_pin_x, out_pin_y = cx + box_w, cy + box_h / 2
            elements.append(f'<circle cx="{in_pin_x}" cy="{in_pin_y}" r="3" fill="{stroke_c}"/>')
            elements.append(f'<circle cx="{out_pin_x}" cy="{out_pin_y}" r="3" fill="{stroke_c}"/>')

            p_dirs = c_info.get("port_directions", {})
            conns = c_info.get("connections", {})
            for p_key, p_bits in conns.items():
                int_bits = [b for b in p_bits if isinstance(b, int)]
                p_dir = p_dirs.get(p_key, "output" if p_key in ("Y", "Q", "ZN", "Z", "OUT") else "input")
                if p_dir in ("output", "inout"):
                    for b in int_bits:
                        bit_sources.setdefault(b, []).append((out_pin_x, out_pin_y))
                else:
                    for b in int_bits:
                        bit_sinks.setdefault(b, []).append((in_pin_x, in_pin_y))

    # Last Column: Output Ports
    out_x = margin_x + (col_count - 1) * col_spacing
    elements.append(
        f'<text x="{out_x}" y="{margin_y - 12}" font-family="JetBrains Mono, monospace" font-size="11" font-weight="700" fill="#475569">PRIMARY OUTPUTS</text>'
    )
    for idx, (p_name, width, bits) in enumerate(out_ports):
        py = margin_y + idx * row_spacing
        w_tag = f"[{width - 1}:0]" if width > 1 else ""
        label = f"{p_name}{w_tag}"
        elements.append(
            f'<rect x="{out_x}" y="{py}" width="155" height="32" rx="5" fill="#dcfce7" stroke="#16a34a" stroke-width="1.5"/>'
        )
        elements.append(
            f'<text x="{out_x + 12}" y="{py + 20}" font-family="JetBrains Mono, monospace" font-size="11" font-weight="600" fill="#166534">{html.escape(label[:20])}</text>'
        )
        pin_x, pin_y = out_x, py + 16
        elements.append(f'<circle cx="{pin_x}" cy="{pin_y}" r="3.5" fill="#16a34a"/>')
        for b in bits:
            bit_sinks.setdefault(b, []).append((pin_x, pin_y))

    # Cubic Bezier Wires between Sources and Sinks (deduplicated by coordinate pair)
    wires_svg: List[str] = []
    drawn_pairs: Set[Tuple[float, float, float, float]] = set()
    wire_palette = ("#64748b", "#0284c7", "#7c3aed", "#059669", "#d97706")

    for bit_id, srcs in bit_sources.items():
        sinks = bit_sinks.get(bit_id, [])
        stroke_col = wire_palette[bit_id % len(wire_palette)]
        for sx, sy in srcs[:3]:
            for dx, dy in sinks[:5]:
                pair_key = (round(sx, 1), round(sy, 1), round(dx, 1), round(dy, 1))
                if pair_key in drawn_pairs or (sx == dx and sy == dy):
                    continue
                drawn_pairs.add(pair_key)
                ctrl_offset = max(45.0, abs(dx - sx) * 0.42)
                c1x = sx + ctrl_offset
                c2x = dx - ctrl_offset
                wires_svg.append(
                    f'<path d="M {sx:.1f} {sy:.1f} C {c1x:.1f} {sy:.1f}, {c2x:.1f} {dy:.1f}, {dx:.1f} {dy:.1f}" '
                    f'fill="none" stroke="{stroke_col}" stroke-width="1.35" opacity="0.68"/>'
                )
                if len(drawn_pairs) >= 260:
                    break
            if len(drawn_pairs) >= 260:
                break
        if len(drawn_pairs) >= 260:
            break

    svg_doc = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" width="{svg_w}px" height="{svg_h}px">',
        f'<rect width="{svg_w}" height="{svg_h}" fill="#ffffff"/>',
        *wires_svg,
        *elements,
        "</svg>",
    ]
    return "\n".join(svg_doc) + "\n"


def render_project_views(
    project_name: str, studio_root: Path = STUDIO_ROOT
) -> Dict[str, Any]:
    """Renders Word-Level RTL, Submodule, and Staged Gate-Level Netlist SVGs into `build/views/`."""
    proj_dir = get_project_dir(project_name, create_if_missing=False)
    if not proj_dir.exists():
        return {"status": "ERROR", "message": f"Project not found: {project_name}"}

    comp = ensure_project_structure(proj_dir)
    netlists_dir = comp["netlists"]
    views_dir = comp["views"]

    rtl_netlist_path = netlists_dir / "synth_netlist.json"
    if not rtl_netlist_path.exists():
        execute_yosys_synthesis(project_name=proj_dir.name, studio_root=studio_root)

    if not rtl_netlist_path.exists():
        return {
            "status": "ERROR",
            "message": f"synth_netlist.json not found for {proj_dir.name}. Run run_yosys_synthesis first.",
        }

    generated_svgs: List[str] = []

    # 1. Render Word-Level RTL Schematics (Top + Submodules)
    rtl_data = json.loads(rtl_netlist_path.read_text(encoding="utf-8"))
    rtl_modules = rtl_data.get("modules", {})
    top_mod_name = next(
        (
            m_name
            for m_name, m_info in rtl_modules.items()
            if int(m_info.get("attributes", {}).get("top", "0"), 2) == 1
        ),
        next(iter(rtl_modules.keys()), ""),
    )

    for m_name, m_info in sorted(rtl_modules.items()):
        is_top = m_name == top_mod_name
        svg_filename = "schematic_rtl.svg" if is_top else f"schematic_{m_name}.svg"
        banner = (
            f"Top RTL Architecture: {m_name} ({proj_dir.name})"
            if is_top
            else f"RTL Submodule: {m_name}"
        )
        svg_text = _render_module_svg(m_name, m_info, rtl_modules, banner, max_cells=42)
        out_path = views_dir / svg_filename
        out_path.write_text(svg_text, encoding="utf-8")
        generated_svgs.append(out_path.relative_to(studio_root).as_posix())

    # 2. Render Staged Gate-Level Netlist SVGs for every mapped_<target> directory
    for mapped_dir in sorted(netlists_dir.glob("mapped_*")):
        if not mapped_dir.is_dir():
            continue
        target_slug = mapped_dir.name.replace("mapped_", "")
        gates_json = mapped_dir / "synth_gates.json"
        if not gates_json.exists():
            continue
        try:
            g_data = json.loads(gates_json.read_text(encoding="utf-8"))
            g_modules = g_data.get("modules", {})
            g_top_name = next(
                (
                    m_name
                    for m_name, m_info in g_modules.items()
                    if int(m_info.get("attributes", {}).get("top", "0"), 2) == 1
                ),
                next(iter(g_modules.keys()), ""),
            )
            if g_top_name and g_top_name in g_modules:
                g_banner = f"Synthesized Gate Netlist ({target_slug.upper()}): {g_top_name}"
                g_svg = _render_module_svg(
                    g_top_name,
                    g_modules[g_top_name],
                    g_modules,
                    g_banner,
                    max_cells=48,
                )
                g_out = views_dir / f"schematic_gates_{target_slug}.svg"
                g_out.write_text(g_svg, encoding="utf-8")
                generated_svgs.append(g_out.relative_to(studio_root).as_posix())
        except Exception:
            continue

    return {
        "status": "SUCCESS",
        "project_name": proj_dir.name,
        "top_module": top_mod_name,
        "svg_count": len(generated_svgs),
        "generated_svgs": generated_svgs,
        "agent_guidance": (
            f"Rendered {len(generated_svgs)} interactive SVG schematics into "
            f"projects/{proj_dir.name}/build/views/."
        ),
    }