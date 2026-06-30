# pipeline/z1_pipeline.py
"""
Continuum — RIN Protocol｜Tone Rhythm Repair Module
Deploy-ready v4.2.3 (Sealing Alignment + Audit Timing + No Derived-Content Leak)

Key alignment goals (w/ app.py Evidence Schema v1.0):
- ✅ Pipeline remains source-of-truth for: mode/freq_type/output/audit/metrics/llm_used/cache_hit/model/usage/output_source
- ✅ audit always exists at BOTH: output.audit and result["audit"] (top-level)
- ✅ audit always includes: timing_ms.total, input_hash, input_length, pipeline_version_fingerprint
- ✅ BLOCK is explicit and never looks like no-op (repaired_text="")
- ✅ Privacy hardening in pipeline outputs:
    - Remove/avoid content-derived lists in audit/debug (oos_matched, detected_keywords, matched, etc.)
    - If debug=True, allow richer internal debug, but still avoid returning raw text fields beyond normal outputs
    - Default debug=False stays enterprise-safe

NOTE:
- app.py is the ONLY component that packages Evidence Schema for logging.
- logger.py is receiver + defense-in-depth scrub.
"""

from __future__ import annotations

import yaml
import json
import time
import hashlib
from datetime import datetime

from core import (
    normalizer,
    language_detector,
    rhythm_analyzer,
    classifier,
    router,
    repairer
)
from core.confidence import ConfidenceCalculator
from core.commitment_guard import CommitmentGuard
from core.safety_gate import check_out_of_scope, detect_guide_signal
from core.language_utils import normalize_lang
from core.runtime_controls import get_runtime_controls


_CANON_TONE_KEYS = ["Sharp", "Cold", "Blur", "Pushy", "Anxious", "Rhythm", "Unknown"]
_ALLOWED_MODES = {"repair", "suggest", "no-op", "block"}  # ✅ add block


# ----------------------------
# Helpers
# ----------------------------
def _canonicalize_key(k: str) -> str:
    if not isinstance(k, str):
        return k
    k2 = k.strip()
    if not k2:
        return k
    low = k2.lower()
    mapping = {
        "sharp": "Sharp",
        "cold": "Cold",
        "blur": "Blur",
        "pushy": "Pushy",
        "anxious": "Anxious",
        "rhythm": "Rhythm",
        "unknown": "Unknown",
        "outofscope": "OutOfScope",
        "out_of_scope": "OutOfScope",
        "out-of-scope": "OutOfScope",
    }
    return mapping.get(low, k2)


def _normalize_mode(m) -> str:
    """
    Hard normalize any mode into {"repair","suggest","no-op","block"}.
    Default is "suggest" (conservative).
    """
    if not isinstance(m, str):
        return "suggest"
    ml = m.strip().lower()

    if ml in _ALLOWED_MODES:
        return ml

    if ml in {"block", "terminate", "intercept"}:
        return "block"

    if ml in {"noop", "no_op", "no op", "pass", "passthrough", "pass-through"}:
        return "no-op"

    if ml in {"fix", "rewrite"}:
        return "repair"

    return "suggest"


def _safe_float(v, default=0.0) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _safe_int(v, default=0) -> int:
    try:
        if v is None:
            return int(default)
        return int(v)
    except Exception:
        return int(default)


def _sha256_text(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now().isoformat()


def _ensure_dict(x):
    return x if isinstance(x, dict) else {}


def _ensure_usage(x):
    return x if isinstance(x, dict) else {}


def _set_audit_timing(audit: dict, total_ms: int) -> dict:
    audit = _ensure_dict(audit)
    tm = audit.get("timing_ms")
    if not isinstance(tm, dict):
        tm = {}
    # IMPORTANT: pipeline owns timing_ms.total; app.py adds server_overhead
    tm.setdefault("total", _safe_int(total_ms, 0))
    audit["timing_ms"] = tm
    return audit


def _audit_defaults(
    audit: dict,
    *,
    llm_used,
    cache_hit,
    output_source,
    pipeline_version_fingerprint: str,
    input_hash: str,
    input_length: int,
    total_ms: int,
) -> dict:
    audit = _ensure_dict(audit)

    audit.setdefault("llm_used", llm_used)
    audit.setdefault("cache_hit", cache_hit)
    audit.setdefault("output_source", output_source)
    audit.setdefault("fallback_used", False)
    audit.setdefault("fallback_reason", "")
    audit.setdefault("pipeline_version_fingerprint", pipeline_version_fingerprint)

    # governance purity proof (content-free)
    audit.setdefault("input_hash", input_hash)
    audit.setdefault("input_length", _safe_int(input_length, 0))

    # timing contract
    audit = _set_audit_timing(audit, total_ms)
    return audit


# ----------------------------
# UI Presentation Translator
# (does not affect logic; output only)
# ----------------------------
def _build_ui_summary(freq_type: str, mode: str, conf_final: float, scenario: str) -> dict:
    m = (mode or "").strip().lower()
    f = (freq_type or "Unknown").strip()
    sc = (scenario or "unknown").strip()

    conf = _safe_float(conf_final, 0.0)
    conf = max(0.0, min(1.0, conf))

    if m == "block":
        return {
            "label": "BLOCK",
            "badge_text": "BLOCK · diverted",
            "badge_color": "red",
            "show_confidence": False,
            "confidence_percent": None,
            "message": "High-risk content detected. Output intercepted and diverted to a safe flow.",
            "scenario": sc,
            "freq_type": f,
            "mode": m,
        }

    if m == "no-op":
        return {
            "label": "SAFE",
            "badge_text": "SAFE · within range",
            "badge_color": "green",
            "show_confidence": False,
            "confidence_percent": None,
            "message": "Tone within safe range. Transparent pass-through.",
            "scenario": sc,
            "freq_type": f,
            "mode": m,
        }

    if m == "repair":
        return {
            "label": "REPAIR",
            "badge_text": "REPAIR",
            "badge_color": "green",
            "show_confidence": True,
            "confidence_percent": int(round(conf * 100)),
            "message": f"Detected {f}. Repair applied.",
            "scenario": sc,
            "freq_type": f,
            "mode": m,
        }

    if m == "suggest":
        return {
            "label": "SUGGEST",
            "badge_text": "SUGGEST",
            "badge_color": "orange",
            "show_confidence": True,
            "confidence_percent": int(round(conf * 100)),
            "message": f"Possible {f}. Suggested understanding.",
            "scenario": sc,
            "freq_type": f,
            "mode": m,
        }

    return {
        "label": "UNKNOWN",
        "badge_text": "UNKNOWN",
        "badge_color": "grey",
        "show_confidence": False,
        "confidence_percent": None,
        "message": "No clear risk detected.",
        "scenario": sc,
        "freq_type": f,
        "mode": m or "unknown",
    }


def _ui_flat_fields(base: dict, output: dict, freq_type: str, mode: str, conf_final: float) -> dict:
    """
    UI backward-compat:
    - Always include flat fields so the static playground can render.
    - Attach output.ui for new badge rendering.
    - Keep compat flat fields: llm_used/cache_hit/model/usage/output_source + audit at top-level.
    """
    if not isinstance(base, dict):
        base = {}

    out = output if isinstance(output, dict) else {}

    scenario = out.get("scenario") or base.get("scenario") or "general"
    repaired_text = out.get("repaired_text", None)
    repair_note = out.get("repair_note", "")

    mode = _normalize_mode(mode)

    if mode == "block":
        if repaired_text is None:
            repaired_text = ""
    elif mode == "no-op":
        if repaired_text is None:
            repaired_text = base.get("normalized") or ""
    else:
        if repaired_text is None:
            repaired_text = ""

    # attach UI summary
    try:
        ui = _build_ui_summary(
            freq_type=freq_type,
            mode=mode,
            conf_final=_safe_float(conf_final, 0.0),
            scenario=scenario,
        )
        out = dict(out) if isinstance(out, dict) else {}
        out["ui"] = ui
    except Exception:
        out = dict(out) if isinstance(out, dict) else {}
        out["ui"] = {
            "label": "UNKNOWN",
            "badge_text": "UNKNOWN",
            "badge_color": "grey",
            "show_confidence": False,
            "confidence_percent": None,
            "message": "UI summary unavailable.",
            "scenario": scenario,
            "freq_type": freq_type,
            "mode": mode,
        }

    audit_out = out.get("audit") if isinstance(out.get("audit"), dict) else {}
    llm_used = out.get("llm_used", None)
    cache_hit = out.get("cache_hit", None)
    model_name = out.get("model", "")
    usage = out.get("usage", {})

    # Pipeline is source of truth; if missing, only infer from audit minimally
    if llm_used is None:
        if isinstance(audit_out, dict) and audit_out.get("output_source") == "llm":
            llm_used = True
        elif isinstance(audit_out, dict) and "llm_used" in audit_out:
            llm_used = bool(audit_out.get("llm_used"))
        else:
            llm_used = None

    if cache_hit is None:
        if isinstance(audit_out, dict) and "cache_hit" in audit_out:
            cache_hit = bool(audit_out.get("cache_hit"))
        else:
            cache_hit = None

    output_source = out.get("output_source", None)
    if output_source is None and isinstance(audit_out, dict):
        output_source = audit_out.get("output_source", None)

    base.update({
        "scenario": scenario,
        "repaired_text": repaired_text,
        "repair_note": repair_note,
        "confidence_final": round(_safe_float(conf_final, 0.0), 3),
        "mode": mode,
        "freq_type": freq_type,

        "llm_used": llm_used,
        "cache_hit": cache_hit,
        "model": model_name or "",
        "usage": usage if isinstance(usage, dict) else {},
        "output_source": output_source,

        "output": out,
    })
    return base


# ----------------------------
# Governance Metrics (truth-based)
# ----------------------------
def _to_decision_state(freq_type: str, mode: str, scenario: str = "") -> str:
    ft = (freq_type or "").strip()
    md = (mode or "").strip().lower()

    if ft == "OutOfScope":
        return "BLOCK"
    if md == "block":
        return "BLOCK"
    if md == "no-op":
        return "ALLOW"
    return "GUIDE"


def _reason_code(freq_type: str, scenario: str = "") -> str:
    ft = (freq_type or "Unknown").strip()
    sc = (scenario or "").strip().lower()

    if ft == "OutOfScope" or "out_of_scope" in sc or "crisis" in sc:
        return "OOS_CRISIS"
    mapping = {
        "Anxious": "TONE_ANXIOUS",
        "Sharp": "TONE_SHARP",
        "Cold": "TONE_COLD",
        "Blur": "TONE_BLUR",
        "Pushy": "TONE_PUSHY",
        "Rhythm": "TONE_RHYTHM",
        "Unknown": "TONE_UNKNOWN",
    }
    return mapping.get(ft, "TONE_UNKNOWN")


def _guide_type(normalized_text: str, governed_text: str, mode: str) -> str:
    md = (mode or "").strip().lower()
    if md in ("block", "no-op"):
        return "n/a"
    n = (normalized_text or "").strip()
    g = (governed_text or "").strip()
    return "echo" if g == n else "rewrite"


def _tone_boost_multipliers(runtime_controls: dict, tone: str) -> tuple[float, float, float]:
    defaults = {"ge1": 2.25, "ge2": 2.5, "ge3": 3.0}
    if isinstance(runtime_controls, dict):
        boost_cfg = runtime_controls.get("boost_multipliers")
        if isinstance(boost_cfg, dict):
            tone_cfg = boost_cfg.get(tone)
            if isinstance(tone_cfg, dict):
                defaults["ge1"] = _safe_float(tone_cfg.get("ge1"), defaults["ge1"])
                defaults["ge2"] = _safe_float(tone_cfg.get("ge2"), defaults["ge2"])
                defaults["ge3"] = _safe_float(tone_cfg.get("ge3"), defaults["ge3"])
    return (
        max(0.1, defaults["ge1"]),
        max(0.1, defaults["ge2"]),
        max(0.1, defaults["ge3"]),
    )


def _mask_sensitive_signals(obj):
    """
    Remove content-derived or keyword-derived signal lists from response payload.
    This function is applied before returning final pipeline output.
    """
    risky_keys = {
        "matched",
        "matches",
        "matched_keywords",
        "detected_keywords",
        "oos_matched",
        "trigger_words",
        "trigger_words_list",
        "keywords",
        "keyword_list",
        "patterns",
    }
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            lk = str(k).strip().lower()
            if lk in risky_keys:
                continue
            if "matched" in lk and not lk.endswith("_count"):
                continue
            if "keyword" in lk and not lk.endswith("_count"):
                continue
            out[k] = _mask_sensitive_signals(v)
        return out
    if isinstance(obj, list):
        return [_mask_sensitive_signals(x) for x in obj]
    return obj


def _contract_block_response(
    *,
    reason_code: str,
    scenario: str,
    total_ms: int,
    input_hash: str,
    input_length: int,
    pipeline_version_fingerprint: str,
    output_source: str = "block_handler",
    audit_extra: dict | None = None,
) -> dict:
    audit = _audit_defaults(
        dict(audit_extra or {}),
        llm_used=False,
        cache_hit=False,
        output_source=output_source,
        pipeline_version_fingerprint=pipeline_version_fingerprint,
        input_hash=input_hash,
        input_length=input_length,
        total_ms=total_ms,
    )
    output = {
        "scenario": scenario,
        "repaired_text": "",
        "repair_note": "Blocked by governance policy.",
        "repair_strategy": {"mode": "block"},
        "usage": {},
        "model": "",
        "audit": audit,
        "llm_used": False,
        "cache_hit": False,
        "output_source": output_source,
    }
    result = {
        "error": True,
        "reason": "governance_blocked",
        "scenario": scenario,
        "repaired_text": "",
        "repair_note": output["repair_note"],
        "confidence_final": 0.0,
        "mode": "block",
        "freq_type": "OutOfScope",
        "llm_used": False,
        "cache_hit": False,
        "model": "",
        "usage": {},
        "output_source": output_source,
        "output": output,
        "processing_time_ms": _safe_int(total_ms, 0),
        "pipeline_stages": {},
        "audit": audit,
        "pipeline_version_fingerprint": pipeline_version_fingerprint,
        "metrics": {
            "decision_state": "BLOCK",
            "action": "intercept",
            "guide_type": "n/a",
            "reason_code": reason_code,
            "suppressed": True,
            "latency_ms": _safe_int(total_ms, 0),
            "suppressed_chars": None,
        },
        "decision_state": "BLOCK",
    }
    return _mask_sensitive_signals(result)


def _commitment_safe_reply(lang: str, handoff_required: bool = False) -> str:
    if (lang or "").lower().startswith("en"):
        if handoff_required:
            return (
                "This request involves policy or contractual commitments and must be "
                "handled by an authorized human specialist."
            )
        return (
            "This request may involve a commitment beyond assistant authority. "
            "Please follow official policy and authorized review flow."
        )
    if handoff_required:
        return "此請求涉及政策或契約承諾，需由授權人工專員處理。"
    return "此請求可能涉及超出權限的承諾，請依官方政策與授權流程處理。"


def _contract_commitment_response(
    *,
    decision: str,
    reason_code: str,
    category: str,
    matched_count: int,
    handoff_required: bool,
    lang_for_ops: str,
    total_ms: int,
    input_hash: str,
    input_length: int,
    pipeline_version_fingerprint: str,
    output_source: str = "authority_boundary_check",
) -> dict:
    mode = "block" if (decision or "").upper() == "BLOCK" else "suggest"
    decision_state = "BLOCK" if mode == "block" else "GUIDE"
    scenario = "authority_boundary_commitment"

    audit = _audit_defaults(
        {
            "authority_boundary": {
                "category": category,
                "reason_code": reason_code,
                "matched_count": _safe_int(matched_count, 0),
                "handoff_required": bool(handoff_required),
            }
        },
        llm_used=False,
        cache_hit=False,
        output_source=output_source,
        pipeline_version_fingerprint=pipeline_version_fingerprint,
        input_hash=input_hash,
        input_length=input_length,
        total_ms=total_ms,
    )

    output = {
        "scenario": scenario,
        "repaired_text": "" if mode == "block" else _commitment_safe_reply(lang_for_ops, handoff_required),
        "repair_note": f"Commitment boundary triggered: {reason_code}",
        "repair_strategy": {"mode": mode, "type": "authority_boundary"},
        "usage": {},
        "model": "",
        "audit": audit,
        "llm_used": False,
        "cache_hit": False,
        "output_source": output_source,
    }

    base = {
        "language": lang_for_ops,
        "freq_type": "CommitmentRisk",
        "rhythm": {"total": 0, "speed_index": 0.5, "risk_score": 0.0},
        "confidence": {"classifier": 1.0, "base": 1.0, "final": 1.0, "debug": {}},
        "mode": mode,
        "output": output,
        "processing_time_ms": _safe_int(total_ms, 0),
        "pipeline_stages": {},
        "audit": dict(audit),
        "metrics": {
            "decision_state": decision_state,
            "action": "intercept" if decision_state == "BLOCK" else "constrain",
            "guide_type": "n/a" if decision_state == "BLOCK" else "rewrite",
            "reason_code": reason_code or "AUTHORITY_BOUNDARY",
            "suppressed": decision_state != "BLOCK",
            "latency_ms": _safe_int(total_ms, 0),
            "suppressed_chars": None,
        },
        "llm_used": False,
        "cache_hit": False,
        "model": "",
        "usage": {},
        "output_source": output_source,
        "pipeline_version_fingerprint": pipeline_version_fingerprint,
    }
    result = _ui_flat_fields(base, output, "CommitmentRisk", mode, 1.0)
    result["decision_state"] = decision_state
    return _mask_sensitive_signals(result)


class Z1Pipeline:
    def __init__(self, config_path="configs/settings.yaml", debug: bool = False):
        self.debug = debug

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f) or {}

        with open("configs/keywords.json", "r", encoding="utf-8") as f:
            raw_keywords = json.load(f)

        self.keywords = self._normalize_keywords_keys(raw_keywords)

        with open("configs/templates.json", "r", encoding="utf-8") as f:
            self.templates = json.load(f)

        self.confidence_calc = ConfidenceCalculator(self.config)

        self.routing_cfg = self.config.get("routing", {}) or {}
        self.oos_cfg = self.config.get("out_of_scope", {}) or {}
        self.commitment_cfg = self.config.get("commitment_guard", {}) or {}
        self.long_cfg = self.config.get("long_input_safety", {}) or {}

        self.len_cfg = self.config.get("length_check", {}) or {}
        self.min_len = _safe_int(self.len_cfg.get("min", 1), 1)
        self.max_len = _safe_int(self.len_cfg.get("max", 2000), 2000)

        # ✅ Version fingerprint: configs as "governance build ID"
        self.pipeline_version_fingerprint = self._compute_pipeline_version_fingerprint(
            files=[
                "configs/settings.yaml",
                "configs/keywords.json",
                "configs/templates.json",
                "configs/commitment_rules.yaml",
            ]
        )
        commitment_rules_path = self.commitment_cfg.get("rules_path", "configs/commitment_rules.yaml")
        self.commitment_guard = CommitmentGuard(rules_path=commitment_rules_path)

    def _compute_pipeline_version_fingerprint(self, files) -> str:
        h = hashlib.sha256()
        for p in files:
            try:
                with open(p, "rb") as f:
                    b = f.read()
                h.update(p.encode("utf-8"))
                h.update(b)
            except Exception:
                h.update(p.encode("utf-8"))
                h.update(b"<missing>")
        return h.hexdigest()

    def _normalize_keywords_keys(self, kw: dict) -> dict:
        if not isinstance(kw, dict):
            return {k: {} for k in _CANON_TONE_KEYS}

        normalized = {}
        for k, v in kw.items():
            ck = _canonicalize_key(k)
            if ck in normalized and isinstance(normalized[ck], dict) and isinstance(v, dict):
                merged = dict(normalized[ck])
                for kk, vv in v.items():
                    merged[kk] = vv
                normalized[ck] = merged
            else:
                normalized[ck] = v

        for k in _CANON_TONE_KEYS:
            normalized.setdefault(k, {})

        if self.debug:
            present = [k for k in _CANON_TONE_KEYS if normalized.get(k)]
            print(f"[Keywords] canonical keys ready: {present}")

        return normalized

    def smart_truncate(self, text: str, max_len: int) -> str:
        if not isinstance(text, str):
            return ""
        if len(text) <= max_len:
            return text

        head_len = int(max_len * 0.6)
        tail_len = max_len - head_len - 5

        head = text[:head_len]
        tail = text[-tail_len:]

        punctuations = [".", "!", "?", "。", "！", "？"]

        for punct in punctuations:
            pos = head.rfind(punct)
            if pos > head_len * 0.7:
                head = head[:pos + 1]
                break

        for punct in punctuations:
            pos = tail.find(punct)
            if 0 < pos < tail_len * 0.3:
                tail = tail[pos + 1:].lstrip()
                break

        return head + " ... " + tail

    def process(self, text: str) -> dict:
        start = time.time()
        stages = {}

        try:
            # Governance purity: store hash + length only in audit
            input_hash = _sha256_text(text or "")
            input_length = len(text or "")

            normalized = normalizer.normalize(text)
            stages["1_normalization"] = {
                "timestamp": _now_iso(),
                "len_in": input_length,
                "len_out": len(normalized or ""),
            }

            lang_raw = language_detector.detect_language(normalized)
            lang_for_ops = normalize_lang(lang_raw, default="zh")
            stages["2_language_detection"] = {
                "timestamp": _now_iso(),
                "lang_raw": lang_raw,
                "lang_for_ops": lang_for_ops,
            }

            # ---------- Too short ----------
            if not isinstance(normalized, str) or len(normalized) < self.min_len:
                total_ms = int((time.time() - start) * 1000)
                return _contract_block_response(
                    reason_code="INPUT_TOO_SHORT",
                    scenario="input_too_short_blocked",
                    total_ms=total_ms,
                    input_hash=input_hash,
                    input_length=input_length,
                    pipeline_version_fingerprint=self.pipeline_version_fingerprint,
                    output_source="block_handler",
                    audit_extra={
                        "fallback_used": False,
                        "fallback_reason": "",
                    },
                )

            # ---------- Length check/truncate ----------
            truncated = False
            original_len = len(normalized)
            if original_len > self.max_len:
                normalized = self.smart_truncate(normalized, self.max_len)
                truncated = True

            stages["2.5_length_check"] = {
                "timestamp": _now_iso(),
                "min": self.min_len,
                "max": self.max_len,
                "original_length": original_len,
                "final_length": len(normalized),
                "truncated": truncated,
                "method": "smart_truncate" if truncated else "none",
            }

            # ---------- Safety gate (Out of scope) ----------
            oos = check_out_of_scope(normalized, lang=lang_raw, config=self.oos_cfg)
            stages["2.8_safety_gate"] = {
                "timestamp": _now_iso(),
                "hit": bool(oos.hit),
                "reason": oos.reason_code,
            }

            if oos.hit:
                total_ms = int((time.time() - start) * 1000)

                # PRIVACY: do NOT include oos matched lists in audit/output.
                matched_count = 0
                try:
                    matched_count = len(oos.matched or [])
                except Exception:
                    matched_count = 0

                output_audit = _audit_defaults(
                    {
                        "safe_flow": "crisis_handoff",
                        "oos_reason_code": oos.reason_code,
                        "oos_matched_count": matched_count,  # ✅ count only
                    },
                    llm_used=False,
                    cache_hit=False,
                    output_source="block_handler",
                    pipeline_version_fingerprint=self.pipeline_version_fingerprint,
                    input_hash=input_hash,
                    input_length=input_length,
                    total_ms=total_ms,
                )

                output = {
                    "scenario": "crisis_out_of_scope",
                    "repaired_text": "",
                    "repair_note": "Out of scope: crisis/self-harm content. Output diverted to safe flow.",
                    "repair_strategy": {"mode": "block", "safe_flow": "crisis_handoff"},
                    "usage": {},
                    "model": "",
                    "audit": output_audit,
                    "llm_used": False,
                    "cache_hit": False,
                    "output_source": "block_handler",
                }

                # Debug info: keep reason_code only (no matched list)
                conf_debug = {"out_of_scope": {"reason_code": oos.reason_code, "matched_count": matched_count}}

                base = {
                    "language": lang_raw,
                    "freq_type": "OutOfScope",
                    "rhythm": {"total": 0, "speed_index": 0.5, "risk_score": 0.0},
                    "confidence": {"classifier": 0.0, "base": 0.0, "final": 0.0, "debug": conf_debug},
                    "mode": "block",
                    "output": output,
                    "processing_time_ms": total_ms,
                    "pipeline_stages": stages,

                    "audit": dict(output_audit),
                    "metrics": {
                        "decision_state": "BLOCK",
                        "action": "intercept",
                        "guide_type": "n/a",
                        "reason_code": "OOS_CRISIS",
                        "suppressed": True,
                        "latency_ms": total_ms,
                        "suppressed_chars": None,
                    },

                    "llm_used": False,
                    "cache_hit": False,
                    "model": "",
                    "usage": {},
                    "output_source": "block_handler",
                    "pipeline_version_fingerprint": self.pipeline_version_fingerprint,
                }

                result = _ui_flat_fields(base, output, "OutOfScope", "block", 0.0)
                result["decision_state"] = "BLOCK"
                return _mask_sensitive_signals(result)

            # ---------- Authority boundary check (commitment risk) ----------
            commitment_hit = self.commitment_guard.evaluate(
                normalized,
                lang=lang_raw,
                config=self.commitment_cfg,
            )
            stages["2.9_authority_boundary_check"] = {
                "timestamp": _now_iso(),
                "hit": bool(commitment_hit.hit),
                "category": commitment_hit.category or "",
                "decision": commitment_hit.decision or "ALLOW",
                "reason_code": commitment_hit.reason_code or "",
                "matched_count": _safe_int(commitment_hit.matched_count, 0),
                "handoff_required": bool(commitment_hit.handoff_required),
            }

            if commitment_hit.hit:
                total_ms = int((time.time() - start) * 1000)
                result = _contract_commitment_response(
                    decision=commitment_hit.decision,
                    reason_code=commitment_hit.reason_code,
                    category=commitment_hit.category,
                    matched_count=commitment_hit.matched_count,
                    handoff_required=commitment_hit.handoff_required,
                    lang_for_ops=lang_for_ops,
                    total_ms=total_ms,
                    input_hash=input_hash,
                    input_length=input_length,
                    pipeline_version_fingerprint=self.pipeline_version_fingerprint,
                    output_source="authority_boundary_check",
                )
                result["pipeline_stages"] = _mask_sensitive_signals(stages)
                return result

            # ---------- Rhythm ----------
            rhythm = rhythm_analyzer.analyze(normalized, self.keywords, self.config.get("rin_weights", {}))
            rin_total = _safe_float((rhythm or {}).get("total", 0.0), 0.0)
            speed_index = _safe_float((rhythm or {}).get("speed_index", 0.5), 0.5)
            risk_score = _safe_float((rhythm or {}).get("risk_score", 0.0), 0.0)
            stages["3_rhythm"] = {
                "timestamp": _now_iso(),
                "rin_total": rin_total,
                "speed_index": speed_index,
                "risk_score": risk_score,
            }

            # ---------- Classify ----------
            if hasattr(classifier, "classify_with_confidence"):
                freq_type, cls_conf = classifier.classify_with_confidence(normalized, rin_total, self.keywords)
            else:
                freq_type = classifier.classify(normalized, rin_total, self.keywords) or "Unknown"
                cls_conf = 0.5

            freq_type = _canonicalize_key(freq_type or "Unknown")
            cls_conf = _safe_float(cls_conf, 0.5)
            stages["4_classify"] = {
                "timestamp": _now_iso(),
                "freq_type": freq_type,
                "cls_conf": cls_conf,
            }

            # ---------- GUIDE signal rescue ----------
            # If classifier returns Unknown, try lightweight guide-signal detection
            # so low-confidence edge cases can still route into GUIDE path.
            if freq_type == "Unknown":
                guide_signal = detect_guide_signal(normalized, lang=lang_raw, config=self.routing_cfg)
                stages["4.5_guide_signal"] = {
                    "timestamp": _now_iso(),
                    "hit": bool(guide_signal.hit),
                    "reason_code": guide_signal.reason_code,
                    "matched_count": len(guide_signal.matched or []),
                }
                if guide_signal.hit and guide_signal.freq_hint:
                    prior_cls_conf = cls_conf
                    freq_type = _canonicalize_key(guide_signal.freq_hint)
                    cls_conf = max(cls_conf, _safe_float(guide_signal.confidence_hint, cls_conf))
                    stages["4.5_guide_signal"].update(
                        {
                            "promoted": True,
                            "promoted_freq_type": freq_type,
                            "cls_conf_before": prior_cls_conf,
                            "cls_conf_after": cls_conf,
                        }
                    )

            # ---------- Confidence ----------
            conf = self.confidence_calc.calculate(
                {"freq_type": freq_type, "confidence": cls_conf},
                {"speed_index": speed_index, "risk_score": risk_score},
            )
            base_conf = _safe_float(conf.get("base_confidence", 0.0), 0.0)
            conf_final = _safe_float(conf.get("final_confidence", 0.5), 0.5)
            conf_debug = conf.get("debug", {}) if isinstance(conf.get("debug", {}), dict) else {}

            stages["5_confidence"] = {
                "timestamp": _now_iso(),
                "base": base_conf,
                "final": conf_final,
            }

            # ---------- Boost (privacy-hardened) ----------
            # NOTE: We avoid returning detected keyword lists in outputs by default (debug=False).
            boost_info = {}
            text_lower = (normalized or "").lower()
            runtime_controls = get_runtime_controls()

            if freq_type == "Anxious":
                primary_policy_kw = self.keywords.get("Anxious", {})
                primary_signal_count = 0

                # optionally collect keywords only when debug=True
                detected_keywords = None

                for category in ["help_seeking", "uncertainty", "worry", "risk_signal"]:
                    if isinstance(primary_policy_kw, dict) and category in primary_policy_kw:
                        for kw in primary_policy_kw[category]:
                            if (kw or "").lower() in text_lower:
                                primary_signal_count += 1
                                if self.debug and isinstance(detected_keywords, list):
                                    detected_keywords.append(kw)

                original_conf = conf_final
                multiplier = 1.0
                ge1, ge2, ge3 = _tone_boost_multipliers(runtime_controls, "Anxious")
                if primary_signal_count >= 3:
                    conf_final = min(0.75, conf_final * ge3); multiplier = ge3
                elif primary_signal_count >= 2:
                    conf_final = min(0.70, conf_final * ge2); multiplier = ge2
                elif primary_signal_count >= 1:
                    conf_final = min(0.60, conf_final * ge1); multiplier = ge1

                if primary_signal_count >= 1:
                    boost_info = {
                        "type": "PolicyImpact",
                        "keyword_count": primary_signal_count,
                        "multiplier": multiplier,
                        "original_confidence": original_conf,
                        "boosted_confidence": conf_final,
                    }
                    if self.debug and isinstance(detected_keywords, list):
                        boost_info["detected_keywords"] = detected_keywords  # debug-only

                    if self.debug and isinstance(conf_debug, dict):
                        conf_debug["policy_impact_boost"] = boost_info

            elif freq_type in {"Cold", "Sharp"}:
                tone_kw = self.keywords.get(freq_type, {})
                tone_count = 0

                detected_keywords = None

                if isinstance(tone_kw, dict):
                    for category in tone_kw.values():
                        if isinstance(category, list):
                            for kw in category:
                                if (kw or "").lower() in text_lower:
                                    tone_count += 1
                                    if self.debug and isinstance(detected_keywords, list):
                                        detected_keywords.append(kw)
                elif isinstance(tone_kw, list):
                    for kw in tone_kw:
                        if (kw or "").lower() in text_lower:
                            tone_count += 1
                            if self.debug and isinstance(detected_keywords, list):
                                detected_keywords.append(kw)

                original_conf = conf_final
                multiplier = 1.0
                ge1, ge2, ge3 = _tone_boost_multipliers(runtime_controls, freq_type)
                if tone_count >= 3:
                    conf_final = min(0.75, conf_final * ge3); multiplier = ge3
                elif tone_count >= 2:
                    conf_final = min(0.70, conf_final * ge2); multiplier = ge2
                elif tone_count >= 1:
                    conf_final = min(0.60, conf_final * ge1); multiplier = ge1

                if tone_count >= 1:
                    boost_info = {
                        "type": freq_type,
                        "keyword_count": tone_count,
                        "multiplier": multiplier,
                        "original_confidence": original_conf,
                        "boosted_confidence": conf_final,
                    }
                    if self.debug and isinstance(detected_keywords, list):
                        boost_info["detected_keywords"] = detected_keywords  # debug-only

                    if self.debug and isinstance(conf_debug, dict):
                        conf_debug[f"{freq_type.lower()}_boost"] = boost_info

            if boost_info:
                # stages are included in output; keep stages content-free by default
                safe_stage = dict(boost_info)
                if not self.debug:
                    safe_stage.pop("detected_keywords", None)
                stages["5.5_confidence_boost"] = {**safe_stage, "timestamp": _now_iso()}

            # ---------- Long input safety ----------
            threshold = _safe_float(self.config.get("confidence_threshold", 0.50), 0.50)
            long_enabled = bool(self.long_cfg.get("enabled", False))
            long_len_th = _safe_int(self.long_cfg.get("length_threshold", 200), 200)
            bump = _safe_float(self.long_cfg.get("confidence_threshold_bump", 0.10), 0.10)

            effective_threshold = threshold
            if long_enabled and len(normalized) >= long_len_th:
                effective_threshold = min(0.95, threshold + bump)
                stages["5.7_long_input_safety"] = {
                    "timestamp": _now_iso(),
                    "enabled": True,
                    "length_threshold": long_len_th,
                    "bump": bump,
                    "threshold_before": threshold,
                    "threshold_after": effective_threshold,
                }
            else:
                stages["5.7_long_input_safety"] = {
                    "timestamp": _now_iso(),
                    "enabled": False,
                    "threshold": threshold,
                }

            # ---------- Routing ----------
            mode = router.route(
                confidence=conf_final,
                threshold=effective_threshold,
                cls_conf=cls_conf,
                freq_type=freq_type,
                config=self.routing_cfg,
                debug=self.debug,
            )
            mode = _normalize_mode(mode)
            stages["6_routing"] = {
                "timestamp": _now_iso(),
                "mode": mode,
                "threshold": effective_threshold,
                "conf_final": conf_final,
                "cls_conf": cls_conf,
                "freq_type": freq_type,
            }

            # ---------- Output ----------
            if mode == "no-op":
                # no-op always content-free audit
                output = {
                    "scenario": "transparent_pass_through",
                    "repaired_text": normalized,
                    "repair_note": "Tone within safe range. Transparent pass-through.",
                    "repair_strategy": {"mode": "no-op"},
                    "usage": {},
                    "model": "",
                    "audit": {
                        "output_source": "no-op",
                        "fallback_used": False,
                        "fallback_reason": "",
                        "pipeline_version_fingerprint": self.pipeline_version_fingerprint,
                        "input_hash": input_hash,
                        "input_length": input_length,
                    },
                    "llm_used": False,
                    "cache_hit": False,
                    "output_source": "no-op",
                }
            else:
                output = repairer.repair_with_rhythm(
                    normalized,
                    freq_type,
                    conf_final,
                    mode,
                    self.templates,
                    speed_index,
                    lang=lang_for_ops,
                )
                if not isinstance(output, dict):
                    output = {
                        "scenario": "repairer_invalid_output",
                        "repaired_text": normalized,
                        "repair_note": "Repairer returned invalid output; pass-through.",
                        "usage": {},
                        "model": "",
                        "audit": {
                            "output_source": "passthrough",
                            "fallback_used": True,
                            "fallback_reason": "repairer_invalid_output",
                            "pipeline_version_fingerprint": self.pipeline_version_fingerprint,
                            "input_hash": input_hash,
                            "input_length": input_length,
                        },
                        "llm_used": False,
                        "cache_hit": False,
                        "output_source": "passthrough",
                    }

            # ---------- Normalize audit + compat (pipeline is truth) ----------
            total_ms = int((time.time() - start) * 1000)

            audit_out = output.get("audit") if isinstance(output.get("audit"), dict) else {}
            llm_used = output.get("llm_used", None)
            cache_hit = output.get("cache_hit", None)
            model_name = output.get("model", "")
            usage = output.get("usage", {})

            if llm_used is None:
                if isinstance(audit_out, dict) and "llm_used" in audit_out:
                    llm_used = bool(audit_out.get("llm_used"))
                elif isinstance(audit_out, dict) and audit_out.get("output_source") == "llm":
                    llm_used = True
                else:
                    llm_used = None

            if cache_hit is None:
                if isinstance(audit_out, dict) and "cache_hit" in audit_out:
                    cache_hit = bool(audit_out.get("cache_hit"))
                else:
                    cache_hit = None

            output_source = output.get("output_source", None)
            if output_source is None and isinstance(audit_out, dict):
                output_source = audit_out.get("output_source", None)

            # enforce output compat
            output["llm_used"] = llm_used
            output["cache_hit"] = cache_hit
            output["output_source"] = output_source
            output["model"] = model_name or ""
            output["usage"] = _ensure_usage(usage)

            # enforce top-level audit defaults (+ timing_ms.total)
            audit_top = _audit_defaults(
                dict(audit_out) if isinstance(audit_out, dict) else {},
                llm_used=llm_used,
                cache_hit=cache_hit,
                output_source=output_source,
                pipeline_version_fingerprint=self.pipeline_version_fingerprint,
                input_hash=input_hash,
                input_length=input_length,
                total_ms=total_ms,
            )

            # Make sure output.audit is the hardened audit (not a stale one)
            output["audit"] = audit_top

            # ---------- Base result ----------
            base = {
                "language": lang_raw,
                "freq_type": freq_type,
                "rhythm": {
                    "total": rin_total,
                    "speed_index": speed_index,
                    "risk_score": risk_score,
                },
                "confidence": {
                    "classifier": cls_conf,
                    "base": base_conf,
                    "final": conf_final,
                    "debug": conf_debug if self.debug else {},  # ✅ keep debug empty by default
                },
                "mode": mode,
                "output": output,
                "processing_time_ms": total_ms,
                "pipeline_stages": _mask_sensitive_signals(stages),
                "llm_used": llm_used,
                "cache_hit": cache_hit,
                "model": model_name or "",
                "usage": _ensure_usage(usage),
                "output_source": output_source,

                # top-level audit
                "audit": audit_top,
                "pipeline_version_fingerprint": self.pipeline_version_fingerprint,
            }

            # ---------- Governance Metrics ----------
            scenario = output.get("scenario", "") if isinstance(output, dict) else ""
            decision_state = _to_decision_state(freq_type, mode, scenario)

            governed_text = output.get("repaired_text")
            if governed_text is None:
                governed_text = ""
            governed_text = governed_text if isinstance(governed_text, str) else str(governed_text or "")

            normalized_text = normalized if isinstance(normalized, str) else str(normalized or "")

            suppressed = (decision_state == "GUIDE" and governed_text.strip() == normalized_text.strip())
            guide_type = _guide_type(normalized_text, governed_text, mode)

            if decision_state == "ALLOW":
                action = "pass"
            elif decision_state == "BLOCK":
                action = "intercept"
            else:
                action = "constrain" if guide_type == "echo" else "rewrite"

            base["metrics"] = {
                "decision_state": decision_state,
                "action": action,
                "guide_type": guide_type,
                "reason_code": _reason_code(freq_type, scenario),
                "suppressed": bool(suppressed),
                "latency_ms": _safe_int(total_ms, 0),

                # propagate if repairer provides it; else None (content-free)
                "suppressed_chars": (audit_top or {}).get("suppressed_chars", None),
            }

            result = _ui_flat_fields(base, output, freq_type, mode, conf_final)
            result["decision_state"] = decision_state
            return _mask_sensitive_signals(result)

        except Exception as e:
            total_ms = int((time.time() - start) * 1000)
            if self.debug:
                import traceback
                traceback.print_exc()
            return _contract_block_response(
                reason_code="INTERNAL_GOVERNANCE_BLOCK",
                scenario="internal_error_blocked",
                total_ms=total_ms,
                input_hash=input_hash if "input_hash" in locals() else _sha256_text(text or ""),
                input_length=input_length if "input_length" in locals() else len(text or ""),
                pipeline_version_fingerprint=self.pipeline_version_fingerprint,
                output_source="block_handler",
            )

        return _contract_block_response(
            reason_code="UNKNOWN_GOVERNANCE_BLOCK",
            scenario="unknown_error_blocked",
            total_ms=0,
            input_hash=_sha256_text(text or ""),
            input_length=len(text or ""),
            pipeline_version_fingerprint=self.pipeline_version_fingerprint,
            output_source="block_handler",
        )

    def __repr__(self) -> str:
        return f"Z1Pipeline(debug={self.debug})"