"""
core/commitment_guard.py
------------------------
Authority-boundary commitment guard for customer-service AI.

Purpose:
- Detect unauthorized commitment intent (refund/discount/compensation/legal/contract)
- Return governance decision hints (GUIDE/BLOCK) with reason_code
- Keep output content-free (counts + category only)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import re
import yaml


@dataclass
class CommitmentGuardResult:
    hit: bool
    decision: str = "ALLOW"  # ALLOW/GUIDE/BLOCK
    reason_code: str = ""
    category: str = ""
    matched_count: int = 0
    handoff_required: bool = False
    source: str = ""  # category_match / handoff_keyword


def _safe_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        x = v.strip().lower()
        if x in {"1", "true", "yes", "y", "on"}:
            return True
        if x in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    try:
        return str(v)
    except Exception:
        return default


class CommitmentGuard:
    def __init__(self, rules_path: str = "configs/commitment_rules.yaml"):
        self.rules_path = rules_path
        self.rules: Dict[str, Any] = self._load_rules()
        self.enabled: bool = _safe_bool(self.rules.get("enabled", True), True)
        self.default_decision: str = _safe_str(self.rules.get("default_decision", "ALLOW"), "ALLOW").upper()

        # Compiled structures
        self._allow_patterns: List[re.Pattern] = []
        self._category_entries: List[Tuple[str, str, str, List[re.Pattern]]] = []
        self._mandatory_category: set[str] = set()
        self._mandatory_keyword_triggers: List[Tuple[str, List[re.Pattern]]] = []

        self._compile_all()

    def _load_rules(self) -> Dict[str, Any]:
        try:
            with open(self.rules_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _compile_patterns(self, items: List[str]) -> List[re.Pattern]:
        compiled: List[re.Pattern] = []
        for it in items or []:
            s = _safe_str(it, "").strip()
            if not s:
                continue
            try:
                compiled.append(re.compile(s, re.IGNORECASE))
            except re.error:
                continue
        return compiled

    def _compile_all(self) -> None:
        allowlist = self.rules.get("allowlist", {}) if isinstance(self.rules.get("allowlist"), dict) else {}
        allow_zh = allowlist.get("patterns_zh", []) if isinstance(allowlist.get("patterns_zh"), list) else []
        allow_en = allowlist.get("patterns_en", []) if isinstance(allowlist.get("patterns_en"), list) else []
        self._allow_patterns = self._compile_patterns(allow_zh + allow_en)

        categories = self.rules.get("categories", {}) if isinstance(self.rules.get("categories"), dict) else {}
        for category, node in categories.items():
            if not isinstance(node, dict):
                continue
            decision = _safe_str(node.get("decision", "GUIDE"), "GUIDE").upper()
            reason_code = _safe_str(node.get("reason_code", f"commitment_{category}"), f"commitment_{category}")
            p_zh = node.get("patterns_zh", []) if isinstance(node.get("patterns_zh"), list) else []
            p_en = node.get("patterns_en", []) if isinstance(node.get("patterns_en"), list) else []
            pats = self._compile_patterns(p_zh + p_en)
            if pats:
                self._category_entries.append((str(category), decision, reason_code, pats))

        mh = self.rules.get("mandatory_human_handoff", {}) if isinstance(self.rules.get("mandatory_human_handoff"), dict) else {}
        triggers = mh.get("triggers", []) if isinstance(mh.get("triggers"), list) else []
        for tr in triggers:
            if not isinstance(tr, dict):
                continue
            cat = _safe_str(tr.get("category"), "").strip()
            if cat:
                self._mandatory_category.add(cat)
            kzh = tr.get("keyword_zh", []) if isinstance(tr.get("keyword_zh"), list) else []
            ken = tr.get("keyword_en", []) if isinstance(tr.get("keyword_en"), list) else []
            pats = self._compile_patterns(kzh + ken)
            if pats:
                reason = _safe_str(tr.get("reason"), "mandatory_human_handoff")
                self._mandatory_keyword_triggers.append((reason, pats))

        # additional_patterns are treated as normal categories
        ap = self.rules.get("additional_patterns", {}) if isinstance(self.rules.get("additional_patterns"), dict) else {}
        for category, node in ap.items():
            if not isinstance(node, dict):
                continue
            decision = _safe_str(node.get("decision", "GUIDE"), "GUIDE").upper()
            reason_code = _safe_str(node.get("reason_code", f"commitment_{category}"), f"commitment_{category}")
            p_zh = node.get("patterns_zh", []) if isinstance(node.get("patterns_zh"), list) else []
            p_en = node.get("patterns_en", []) if isinstance(node.get("patterns_en"), list) else []
            pats = self._compile_patterns(p_zh + p_en)
            if pats:
                self._category_entries.append((str(category), decision, reason_code, pats))

    def _matched_count(self, text: str, patterns: List[re.Pattern]) -> int:
        cnt = 0
        for rx in patterns:
            try:
                if rx.search(text):
                    cnt += 1
            except Exception:
                continue
        return cnt

    def evaluate(self, text: str, lang: str = "zh", config: Optional[Dict[str, Any]] = None) -> CommitmentGuardResult:
        if not self.enabled:
            return CommitmentGuardResult(hit=False)
        if not isinstance(text, str) or not text.strip():
            return CommitmentGuardResult(hit=False)

        cfg = config or {}
        if isinstance(cfg, dict) and "enabled" in cfg and not _safe_bool(cfg.get("enabled"), True):
            return CommitmentGuardResult(hit=False)

        tx = text.lower()

        # Allowlist first: policy-safe wording should not be treated as commitment breach.
        if self._allow_patterns and self._matched_count(tx, self._allow_patterns) > 0:
            return CommitmentGuardResult(hit=False)

        # Category match
        for category, decision, reason_code, pats in self._category_entries:
            mcnt = self._matched_count(tx, pats)
            if mcnt > 0:
                handoff = category in self._mandatory_category
                return CommitmentGuardResult(
                    hit=True,
                    decision=decision if decision in {"GUIDE", "BLOCK"} else "GUIDE",
                    reason_code=reason_code,
                    category=category,
                    matched_count=mcnt,
                    handoff_required=handoff,
                    source="category_match",
                )

        # Mandatory handoff keyword-only trigger
        for reason, pats in self._mandatory_keyword_triggers:
            mcnt = self._matched_count(tx, pats)
            if mcnt > 0:
                return CommitmentGuardResult(
                    hit=True,
                    decision="GUIDE",
                    reason_code="mandatory_human_handoff",
                    category="mandatory_human_handoff",
                    matched_count=mcnt,
                    handoff_required=True,
                    source="handoff_keyword",
                )

        return CommitmentGuardResult(hit=False)
