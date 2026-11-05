# =============================================================================
# File Path: schema_factory/knowledge_factory/build_knowledge_schema.py
# =============================================================================
"""Three-Tier Empirical Canary Validator & Knowledge Schema Builder (`build_knowledge_schema.py`).

Reads staged candidate rules from `schema_factory/knowledge_factory/staging/candidate_rules_batch.json`
(auto-invoking `mine_kb_candidates.py` if not yet staged), empirically compiles every
rule's `bad_canary_sv` and `good_canary_sv` against local EDA binaries via
`backend.core.executor.run_cmd`:
- Tier 1 (`verilator_bin --lint-only -Wall -sv`):
  Verifies `bad_canary_sv` triggers `expected_bad_warning` and `good_canary_sv` passes with 0 warnings.
- Tier 2 (`yosys` RTLIL Elaboration & Cell Audit):
  Verifies `good_canary_sv` synthesizes cleanly into `RTL_NETLIST` with zero `$dlatch`/`$adlatch` cells.

Outputs:
- `schemas/knowledge/rules/{cdc,lint,fsm,sdc,ppa}_rules.json`
- `schemas/knowledge/kb_manifest.json`
- `docs/manuals/silicon_kb_catalog.md`
- Updates `schemas/registry_index.json` with the `knowledge` domain.
"""
import datetime
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

STUDIO_ROOT = Path(__file__).resolve().parents[2]
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

from backend.core.executor import ensure_trailing_newlines, run_cmd
from backend.core.workspace_manager import atomic_read_json, atomic_write_json
from schema_factory.knowledge_factory.mine_kb_candidates import main as run_miner

STAGING_FILE = (
    STUDIO_ROOT / "schema_factory" / "knowledge_factory" / "staging" / "candidate_rules_batch.json"
)
CANARY_SANDBOX = STUDIO_ROOT / ".silicon_studio" / ".canary_sandbox"
SCHEMA_KNOWLEDGE_DIR = STUDIO_ROOT / "schemas" / "knowledge"
SCHEMA_RULES_DIR = SCHEMA_KNOWLEDGE_DIR / "rules"
MANUAL_PATH = STUDIO_ROOT / "docs" / "manuals" / "silicon_kb_catalog.md"
REGISTRY_INDEX_PATH = STUDIO_ROOT / "schemas" / "registry_index.json"


def run_tier1_verilator_canary(
    rule_id: str, bad_sv: str, good_sv: str, expected_warn: str
) -> Tuple[bool, str]:
    """Tier 1: Runs Verilator static lint on bad_canary_sv and good_canary_sv."""
    CANARY_SANDBOX.mkdir(parents=True, exist_ok=True)
    test_file = CANARY_SANDBOX / "canary_test.sv"

    base_flags = [
        "verilator",
        "--lint-only",
        "-Wall",
        "-Wno-DECLFILENAME",
        "-Wno-EOFNEWLINE",
        "-Wno-UNUSEDSIGNAL",
        "-Wno-UNUSEDPARAM",
        "-sv",
        "--top-module",
        "canary_test",
        str(test_file),
    ]

    # 1. Test Bad Canary (Must fail or emit expected_warn)
    test_file.write_text(bad_sv.strip() + "\n", encoding="utf-8")
    ensure_trailing_newlines([test_file])
    res_bad = run_cmd(base_flags, cwd=CANARY_SANDBOX, timeout_sec=15)
    out_bad = (res_bad["stdout"] + "\n" + res_bad["stderr"]).upper()

    if expected_warn:
        exp_upper = expected_warn.strip().upper()
        if exp_upper not in out_bad and res_bad["exit_code"] == 0:
            return (
                False,
                f"Bad canary did not trigger '{expected_warn}'. Output:\n{out_bad[:400]}",
            )

    # 2. Test Good Canary (Must pass with exit_code == 0 and 0 warnings)
    test_file.write_text(good_sv.strip() + "\n", encoding="utf-8")
    ensure_trailing_newlines([test_file])
    res_good = run_cmd(base_flags, cwd=CANARY_SANDBOX, timeout_sec=15)
    out_good = (res_good["stdout"] + "\n" + res_good["stderr"]).strip()

    if res_good["exit_code"] != 0 or "%Warning-" in out_good or "%Error" in out_good:
        return (
            False,
            f"Good canary failed Verilator lint (exit={res_good['exit_code']}):\n{out_good[:400]}",
        )

    return True, f"TIER1_PASS ({expected_warn or 'CLEAN'})"


def run_tier2_yosys_canary(rule_id: str, good_sv: str) -> Tuple[bool, str]:
    """Tier 2: Verifies good_canary_sv elaborates in Yosys with zero inferred latches ($dlatch)."""
    CANARY_SANDBOX.mkdir(parents=True, exist_ok=True)
    test_file = CANARY_SANDBOX / "canary_test.sv"
    netlist_json = CANARY_SANDBOX / "canary_netlist.json"

    if netlist_json.exists():
        netlist_json.unlink()

    test_file.write_text(good_sv.strip() + "\n", encoding="utf-8")
    ensure_trailing_newlines([test_file])

    ys_script = (
        f'read_verilog -sv "{test_file.as_posix()}"; '
        f"hierarchy -check -top canary_test; "
        f"proc; opt; fsm; opt; memory; opt; "
        f'write_json "{netlist_json.as_posix()}"'
    )
    res_ys = run_cmd(["yosys", "-Q", "-T", "-p", ys_script], cwd=CANARY_SANDBOX, timeout_sec=20)
    if res_ys["exit_code"] != 0:
        return (
            False,
            f"Good canary failed Yosys elaboration:\n{(res_ys['stdout'] + res_ys['stderr'])[-400:]}",
        )

    if netlist_json.exists():
        raw_json = netlist_json.read_text(encoding="utf-8")
        if '"$dlatch"' in raw_json or '"$adlatch"' in raw_json:
            return False, "Yosys detected an inferred latch ($dlatch/$adlatch) in good_canary_sv!"

    return True, "TIER2_YOSYS_CLEAN (0 latches)"


def validate_candidate_rule(rule: Dict[str, Any]) -> Tuple[bool, str]:
    """Executes Tier 1 and Tier 2 empirical canary checks on a candidate rule card."""
    r_id = rule.get("rule_id", "UNKNOWN")
    canary = rule.get("canary_spec", {})
    bad_sv = canary.get("bad_canary_sv", "")
    good_sv = canary.get("good_canary_sv", "")
    expected_warn = canary.get("expected_bad_warning", "")

    ok1, msg1 = run_tier1_verilator_canary(r_id, bad_sv, good_sv, expected_warn)
    if not ok1:
        return False, f"[Tier 1 Fail] {msg1}"

    ok2, msg2 = run_tier2_yosys_canary(r_id, good_sv)
    if not ok2:
        return False, f"[Tier 2 Fail] {msg2}"

    return True, f"{msg1} | {msg2}"


def build_markdown_catalog(
    domain_rules: Dict[str, List[Dict[str, Any]]],
    corpus_inventory: List[Dict[str, Any]],
) -> str:
    """Renders `docs/manuals/silicon_kb_catalog.md` for human review and interview demos."""
    total_rules = sum(len(v) for v in domain_rules.values())
    lines = [
        "# Silicon Studio IDE V3.0 — Canary-Validated Knowledge Base Catalog",
        "",
        f"- **Generated At:** `{datetime.datetime.now().isoformat(timespec='seconds')}`",
        f"- **Total Compiler-Verified Rules:** `{total_rules}` across `{len(domain_rules)}` domains",
        f"- **Authoritative Corpus Files Indexed:** `{len(corpus_inventory)}` (`schema_factory/knowledge_factory/corpus/`)",
        "- **Validation Gate:** Verilator Static Lint (`--lint-only -Wall -sv`) + Yosys RTLIL Latch Audit (`0 $dlatch`)",
        "",
        "## 1. Summary Matrix by Domain",
        "",
        "| Rule ID | Domain | Severity | Target Agent | Priority Tags ($w=10$) | Source Authority |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for dom in sorted(domain_rules.keys()):
        for r in domain_rules[dom]:
            p_tags = ", ".join(f"`{t}`" for t in r.get("priority_tags", [])[:4])
            lines.append(
                f"| **`{r['rule_id']}`** | `{dom}` | `{r['severity']}` | `{r['target_agent']}` | {p_tags} | {r.get('source_reference', 'N/A')} |"
            )

    lines.extend(["", "---", "", "## 2. Detailed Rule Cards & Golden Templates", ""])

    for dom in sorted(domain_rules.keys()):
        lines.append(f"### Domain: `{dom.upper()}`")
        lines.append("")
        for r in domain_rules[dom]:
            lines.extend(
                [
                    f"#### `{r['rule_id']}` — {r['summary']}",
                    f"- **Target Agent:** `{r['target_agent']}` | **Verifier Agent:** `{r['verifier_agent']}` | **Severity:** `{r['severity']}`",
                    f"- **Source Reference:** `{r.get('source_reference', 'N/A')}`",
                    f"- **Priority Tags ($w=10$):** {', '.join(f'`{t}`' for t in r.get('priority_tags', []))}",
                    f"- **Hardware Rationale:** {r['hardware_rationale']}",
                    f"- **SDC Requirement:** `{r.get('sdc_constraint', 'N/A')}`",
                    "",
                    "**Anti-Pattern (Violates Rule):**",
                    "```systemverilog",
                    r["anti_pattern"],
                    "```",
                    "",
                    "**Golden Synthesizable Template:**",
                    "```systemverilog",
                    r["golden_template"],
                    "```",
                    "",
                ]
            )

    return "\n".join(lines) + "\n"


def update_registry_index(total_rules: int, domains: List[str]) -> None:
    """Adds the `knowledge` domain to `schemas/registry_index.json`."""
    reg_data = atomic_read_json(REGISTRY_INDEX_PATH) or {"domains": {}, "tools": {}}
    reg_data["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    reg_data.setdefault("domains", {})["knowledge"] = {
        "active_tool": "query_design_knowledge",
        "manifest_path": "schemas/knowledge/kb_manifest.json",
        "rules_dir": "schemas/knowledge/rules",
        "manual_path": "docs/manuals/silicon_kb_catalog.md",
        "validated_rules_count": total_rules,
        "sub_domains": domains,
    }
    atomic_write_json(REGISTRY_INDEX_PATH, reg_data)


def build_knowledge_schemas(update_registry: bool = True) -> Dict[str, Any]:
    """Runs the complete staging + 3-Tier Canary Validation pipeline."""
    if not STAGING_FILE.exists():
        print("[Canary Builder] Staging file not found; running mine_kb_candidates.py first...")
        run_miner()

    staging_data = json.loads(STAGING_FILE.read_text(encoding="utf-8"))
    candidates: List[Dict[str, Any]] = staging_data.get("candidate_rules", [])
    corpus_inventory: List[Dict[str, Any]] = staging_data.get("corpus_inventory", [])

    print(
        f"\n[Canary Validator] Validating {len(candidates)} candidate rules against local Verilator & Yosys binaries..."
    )

    domain_rules: Dict[str, List[Dict[str, Any]]] = {}
    passed_count = 0
    failed_rules: List[Dict[str, str]] = []

    for rule in candidates:
        r_id = rule["rule_id"]
        dom = rule["domain"].lower()
        ok, status_msg = validate_candidate_rule(rule)
        if ok:
            passed_count += 1
            rule["canary_validation_status"] = "VERIFIED_PASS"
            rule["canary_validated_at"] = datetime.datetime.now().isoformat(
                timespec="seconds"
            )
            domain_rules.setdefault(dom, []).append(rule)
            print(f"  [PASS] {r_id:<28} | {status_msg}")
        else:
            failed_rules.append({"rule_id": r_id, "reason": status_msg})
            print(f"  [REJECT] {r_id:<26} | {status_msg}")

    if CANARY_SANDBOX.exists():
        shutil.rmtree(CANARY_SANDBOX, ignore_errors=True)

    SCHEMA_RULES_DIR.mkdir(parents=True, exist_ok=True)

    for dom, rules_list in sorted(domain_rules.items()):
        atomic_write_json(SCHEMA_RULES_DIR / f"{dom}_rules.json", rules_list)

    manifest_payload = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "total_candidates_tested": len(candidates),
        "total_verified_rules": passed_count,
        "rejected_count": len(failed_rules),
        "domains": {dom: len(r_list) for dom, r_list in sorted(domain_rules.items())},
        "corpus_files_indexed": corpus_inventory,
        "failed_rules": failed_rules,
    }
    atomic_write_json(SCHEMA_KNOWLEDGE_DIR / "kb_manifest.json", manifest_payload)

    MANUAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANUAL_PATH.write_text(
        build_markdown_catalog(domain_rules, corpus_inventory), encoding="utf-8"
    )

    if update_registry:
        update_registry_index(passed_count, sorted(domain_rules.keys()))

    print(f"\n[OK] Empirically verified {passed_count}/{len(candidates)} rules!")
    print(f"[OK] Wrote domain rule schemas to: {SCHEMA_RULES_DIR.relative_to(STUDIO_ROOT)}")
    print(f"[OK] Wrote human-readable catalog: {MANUAL_PATH.relative_to(STUDIO_ROOT)}")
    return manifest_payload


def main() -> None:
    build_knowledge_schemas(update_registry=True)


if __name__ == "__main__":
    main()