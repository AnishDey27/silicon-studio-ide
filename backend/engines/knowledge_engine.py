# =============================================================================
# File Path: backend/engines/knowledge_engine.py
# =============================================================================
"""Sub-Millisecond In-Memory Weighted Inverted Index for Silicon Design Knowledge.

Loads canary-validated JSON rule cards from `schemas/knowledge/rules/*.json` and indexes
them under 3 weighted tiers:
- Exact Rule ID / Category Match: weight = 25
- Priority Tags (specific hardware mechanism / warning signature): weight = 10
- Context Tags (broad architectural context): weight = 2

At runtime, strips `canary_spec` before returning the rule card to save ~120 tokens per turn.
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

STUDIO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_RULES_DIR = STUDIO_ROOT / "schemas" / "knowledge" / "rules"
STAGING_FALLBACK_FILE = (
    STUDIO_ROOT / "schema_factory" / "knowledge_factory" / "staging" / "candidate_rules_batch.json"
)

KNOWLEDGE_STORE: Dict[str, Dict[str, Dict[str, Any]]] = {}
INVERTED_INDEX: Dict[str, Dict[str, List[Tuple[str, int]]]] = {}


def _tokenize(text: str) -> List[str]:
    """Normalizes query or tag strings into lowercase alphanumeric tokens + sub-tokens."""
    clean = re.sub(r"[^a-zA-Z0-9_]+", " ", str(text).lower())
    raw_tokens = [t.strip() for t in clean.split() if t.strip()]
    expanded: List[str] = []
    for t in raw_tokens:
        expanded.append(t)
        if "_" in t:
            expanded.extend(sub for sub in t.split("_") if len(sub) >= 3)
    return list(dict.fromkeys(expanded))


def _index_rule_card(rule: Dict[str, Any]) -> None:
    domain = str(rule.get("domain", "")).strip().lower()
    r_id = str(rule.get("rule_id", "")).strip()
    if not domain or not r_id:
        return

    KNOWLEDGE_STORE.setdefault(domain, {})[r_id] = rule
    INVERTED_INDEX.setdefault(domain, {})

    for id_tok in _tokenize(r_id) + _tokenize(rule.get("category", "")):
        INVERTED_INDEX[domain].setdefault(id_tok, []).append((r_id, 25))

    for p_tag in rule.get("priority_tags", []):
        for pt in _tokenize(p_tag):
            INVERTED_INDEX[domain].setdefault(pt, []).append((r_id, 10))

    for c_tag in rule.get("context_tags", []):
        for ct in _tokenize(c_tag):
            INVERTED_INDEX[domain].setdefault(ct, []).append((r_id, 2))


def init_knowledge_engine() -> Dict[str, int]:
    """Builds the in-memory weighted inverted index on FastMCP server startup (< 2ms)."""
    global KNOWLEDGE_STORE, INVERTED_INDEX
    KNOWLEDGE_STORE.clear()
    INVERTED_INDEX.clear()

    if SCHEMA_RULES_DIR.exists():
        for rule_file in sorted(SCHEMA_RULES_DIR.glob("*_rules.json")):
            try:
                rules = json.loads(rule_file.read_text(encoding="utf-8"))
                for rule in rules:
                    _index_rule_card(rule)
            except Exception:
                continue

    # Fallback: if schemas/knowledge/rules/*.json has not been built yet, load wave-1 seed rules
    if not KNOWLEDGE_STORE:
        try:
            from schema_factory.knowledge_factory.mine_kb_candidates import get_wave1_seed_rules
            for rule in get_wave1_seed_rules():
                _index_rule_card(rule)
        except Exception:
            pass

    return {dom: len(rules) for dom, rules in KNOWLEDGE_STORE.items()}


def query_rule(domain: str, symptom_or_pattern: str) -> Dict[str, Any]:
    """Retrieves the highest-scoring validated rule card in O(M) time with self-correcting fallbacks."""
    if not KNOWLEDGE_STORE:
        init_knowledge_engine()

    dom = domain.strip().lower()
    if dom not in KNOWLEDGE_STORE:
        return {
            "status": "DOMAIN_NOT_FOUND",
            "requested_domain": domain,
            "available_domains": sorted(KNOWLEDGE_STORE.keys()),
            "agent_guidance": (
                "Re-call query_design_knowledge using one of the available_domains: "
                + ", ".join(sorted(KNOWLEDGE_STORE.keys()))
            ),
        }

    raw_query_upper = symptom_or_pattern.strip().upper()
    if raw_query_upper in KNOWLEDGE_STORE[dom]:
        exact_rule = dict(KNOWLEDGE_STORE[dom][raw_query_upper])
        exact_rule.pop("canary_spec", None)
        return {
            "status": "SUCCESS",
            "domain": dom,
            "match_score": 100,
            "matched_tags": [raw_query_upper],
            "rule": exact_rule,
            "related_rule_ids": [],
            "agent_guidance": (
                f"Apply golden_template from '{raw_query_upper}'. "
                f"Pass kb_rule_id='{raw_query_upper}' when calling post_agent_handoff."
            ),
        }

    q_tokens = _tokenize(symptom_or_pattern)
    domain_idx = INVERTED_INDEX.get(dom, {})
    scores: Dict[str, int] = {}
    matched_tags_per_rule: Dict[str, List[str]] = {}

    for qt in q_tokens:
        for idx_tag, postings in domain_idx.items():
            if qt == idx_tag or (len(qt) >= 3 and (qt in idx_tag or idx_tag in qt)):
                mult = 1.0 if qt == idx_tag else 0.7
                for r_id, base_weight in postings:
                    pts = int(round(base_weight * mult))
                    scores[r_id] = scores.get(r_id, 0) + pts
                    if idx_tag not in matched_tags_per_rule.setdefault(r_id, []):
                        matched_tags_per_rule[r_id].append(idx_tag)

    if not scores:
        priority_topics: List[str] = []
        for r in KNOWLEDGE_STORE[dom].values():
            priority_topics.extend(r.get("priority_tags", []))
        return {
            "status": "NOT_FOUND",
            "domain": dom,
            "query": symptom_or_pattern,
            "available_rule_ids": sorted(KNOWLEDGE_STORE[dom].keys()),
            "available_priority_tags": sorted(set(priority_topics)),
            "agent_guidance": (
                f"No match for '{symptom_or_pattern}' in domain '{dom}'. "
                "Re-call query_design_knowledge using one of the available_priority_tags or available_rule_ids."
            ),
        }

    ranked_ids = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    best_id = ranked_ids[0]
    best_rule = dict(KNOWLEDGE_STORE[dom][best_id])
    best_rule.pop("canary_spec", None)

    return {
        "status": "SUCCESS",
        "domain": dom,
        "match_score": scores[best_id],
        "matched_tags": matched_tags_per_rule.get(best_id, []),
        "rule": best_rule,
        "related_rule_ids": ranked_ids[1:3],
        "agent_guidance": (
            f"Apply golden_template from rule '{best_id}' ({best_rule.get('summary')}). "
            f"Include kb_rule_id='{best_id}' when calling post_agent_handoff."
        ),
    }