"""
core/dual_orchestrator.py
-------------------------
Backend orchestration for dual-path governance:
- A path: user utterance analysis
- B path: AI draft analysis (optional)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


_RANK = {"ALLOW": 1, "GUIDE": 2, "BLOCK": 3}


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    try:
        return str(v)
    except Exception:
        return default


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


def _normalize_locale(locale: Optional[str]) -> str:
    x = _safe_str(locale, "").strip().lower()
    if x.startswith("en"):
        return "en"
    return "zh"


class DualOrchestrator:
    def __init__(self, policy: Optional[Dict[str, Any]] = None, fallback_messages: Optional[Dict[str, Any]] = None):
        self.policy = policy if isinstance(policy, dict) else {}
        self.fallback_messages = fallback_messages if isinstance(fallback_messages, dict) else {}
        self.default_a_only_policy = _safe_str(self.policy.get("default_a_only_policy"), "balanced") or "balanced"

    def _decision_rank(self, decision_state: str) -> int:
        return int(_RANK.get(_safe_str(decision_state, "ALLOW").strip().upper(), 1))

    def _select_final_result(
        self,
        *,
        user_result: Dict[str, Any],
        ai_result: Optional[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], str]:
        if not isinstance(ai_result, dict):
            return user_result, "user"

        user_rank = self._decision_rank(user_result.get("decision_state", "ALLOW"))
        ai_rank = self._decision_rank(ai_result.get("decision_state", "ALLOW"))
        if ai_rank > user_rank:
            return ai_result, "ai_draft"
        if user_rank > ai_rank:
            return user_result, "user"

        user_reason = _safe_str(user_result.get("intervention_reason_code"), "").strip()
        ai_reason = _safe_str(ai_result.get("intervention_reason_code"), "").strip()
        if ai_reason and not user_reason:
            return ai_result, "ai_draft_tiebreak"
        return user_result, "user_tiebreak"

    def _block_safe_message(self, locale: str) -> str:
        msg_obj = self.fallback_messages.get("block_safe_message")
        if isinstance(msg_obj, dict):
            candidate = _safe_str(msg_obj.get(locale), "").strip()
            if candidate:
                return candidate
        if locale == "en":
            return "Please hold while I connect you with a specialist."
        return "請稍候，我為您轉接專員。"

    def _need_ai_draft_message(self, locale: str) -> str:
        msg_obj = self.fallback_messages.get("need_ai_draft_message")
        if isinstance(msg_obj, dict):
            candidate = _safe_str(msg_obj.get(locale), "").strip()
            if candidate:
                return candidate
        if locale == "en":
            return "Please provide the AI draft response so the system can complete dual-path governance."
        return "請提供 AI 草稿回答，讓系統完成雙路治理整合。"

    def _guide_instruction(
        self,
        *,
        locale: str,
        final_result: Dict[str, Any],
        user_result: Dict[str, Any],
        ai_result: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        block = self.policy.get("guide_instruction") if isinstance(self.policy.get("guide_instruction"), dict) else {}
        objective = (
            block.get("objective", {}).get(locale)
            if isinstance(block.get("objective"), dict)
            else ""
        )
        if not objective:
            objective = (
                "Provide an empathetic and actionable response without unauthorized commitments."
                if locale == "en"
                else "請在不做未授權承諾的前提下，提供可執行且同理的客服回覆。"
            )

        must_include = block.get("must_include_phrases", {}).get(locale) if isinstance(block.get("must_include_phrases"), dict) else []
        if not isinstance(must_include, list):
            must_include = []

        forbidden_commitments = block.get("forbidden_commitments", [])
        if not isinstance(forbidden_commitments, list):
            forbidden_commitments = []

        reasons: List[str] = []
        for node in [user_result, ai_result, final_result]:
            if isinstance(node, dict):
                rc = _safe_str(node.get("intervention_reason_code"), "").strip()
                if rc and rc not in reasons:
                    reasons.append(rc)

        return {
            "objective": objective,
            "forbidden_commitments": forbidden_commitments,
            "must_include_phrases": must_include,
            "focus_reason_codes": reasons,
            "delivery_mode": "reference_only",
            "do_not_use_as_final_reply": True,
        }

    def _handoff_event(
        self,
        *,
        timestamp_utc: str,
        session_id: Optional[str],
        locale: str,
        final_result: Dict[str, Any],
        user_result: Dict[str, Any],
        ai_result: Optional[Dict[str, Any]],
        a_only_policy: str,
    ) -> Dict[str, Any]:
        hcfg = self.policy.get("handoff_event") if isinstance(self.policy.get("handoff_event"), dict) else {}
        decision = _safe_str(final_result.get("decision_state"), "BLOCK").upper() or "BLOCK"
        priority_map = hcfg.get("priority_by_decision") if isinstance(hcfg.get("priority_by_decision"), dict) else {}
        priority = _safe_str(priority_map.get(decision), "high" if decision == "BLOCK" else "normal")

        trigger_paths: List[str] = []
        for key, node in [("user", user_result), ("ai_draft", ai_result)]:
            if isinstance(node, dict):
                d = _safe_str(node.get("decision_state"), "ALLOW").upper()
                if d in {"GUIDE", "BLOCK"}:
                    trigger_paths.append(key)

        return {
            "event_type": _safe_str(hcfg.get("event_type"), "trust_layer_handoff_required"),
            "event_version": _safe_str(hcfg.get("event_version"), "v1"),
            "timestamp_utc": _safe_str(timestamp_utc),
            "session_id": _safe_str(session_id),
            "locale": locale,
            "queue": _safe_str(hcfg.get("queue"), "customer_support_human"),
            "priority": priority,
            "a_only_policy": a_only_policy,
            "trigger_paths": trigger_paths,
            "final_decision_state": decision,
            "governance_mode": _safe_str(final_result.get("governance_mode"), "Block"),
            "intervention_reason_code": _safe_str(final_result.get("intervention_reason_code"), ""),
            "risk_category": _safe_str(final_result.get("risk_category"), ""),
            "risk_label": _safe_str(final_result.get("risk_label"), ""),
        }

    def orchestrate(
        self,
        *,
        user_result: Dict[str, Any],
        ai_result: Optional[Dict[str, Any]],
        ai_draft: Optional[str],
        locale: Optional[str],
        session_id: Optional[str],
        a_only_policy: Optional[str],
        timestamp_utc: str,
    ) -> Dict[str, Any]:
        locale_norm = _normalize_locale(locale)
        policy_name = _safe_str(a_only_policy, self.default_a_only_policy).strip().lower() or self.default_a_only_policy
        if policy_name != "balanced":
            policy_name = self.default_a_only_policy

        final_result, final_source = self._select_final_result(user_result=user_result, ai_result=ai_result)
        final_decision = _safe_str(final_result.get("decision_state"), "ALLOW").upper()
        output: Dict[str, Any] = {
            "a_only_policy": policy_name,
            "locale": locale_norm,
            "session_id": _safe_str(session_id),
            "final_source": final_source,
            "final_decision_state": final_decision,
            "final_governance_mode": _safe_str(final_result.get("governance_mode"), "Sense"),
            "final_intervention_reason_code": _safe_str(final_result.get("intervention_reason_code"), "") or None,
            "final_risk_category": _safe_str(final_result.get("risk_category"), "no_intervention"),
            "final_risk_label": _safe_str(final_result.get("risk_label"), "No intervention"),
            "need_ai_draft": False,
            "delivery_mode": "direct_pass",
            "assistant_instruction": None,
            "draft_reference": None,
            "safe_message": None,
            "handoff_required": False,
            "handoff_event": None,
            "need_ai_draft_message": None,
            "approved_response": None,
        }

        has_ai_draft = isinstance(ai_draft, str) and ai_draft.strip() != ""
        if not has_ai_draft:
            if final_decision == "ALLOW":
                output["delivery_mode"] = "direct_pass"
                return output
            if final_decision == "GUIDE":
                output["delivery_mode"] = "reference_only"
                output["need_ai_draft"] = True
                output["assistant_instruction"] = self._guide_instruction(
                    locale=locale_norm,
                    final_result=final_result,
                    user_result=user_result,
                    ai_result=ai_result,
                )
                output["need_ai_draft_message"] = self._need_ai_draft_message(locale_norm)
                return output

            output["delivery_mode"] = "safe_message"
            output["safe_message"] = self._block_safe_message(locale_norm)
            output["handoff_required"] = True
            output["handoff_event"] = self._handoff_event(
                timestamp_utc=timestamp_utc,
                session_id=session_id,
                locale=locale_norm,
                final_result=final_result,
                user_result=user_result,
                ai_result=ai_result,
                a_only_policy=policy_name,
            )
            return output

        if final_decision == "BLOCK":
            output["delivery_mode"] = "safe_message"
            output["safe_message"] = self._block_safe_message(locale_norm)
            output["handoff_required"] = True
            output["handoff_event"] = self._handoff_event(
                timestamp_utc=timestamp_utc,
                session_id=session_id,
                locale=locale_norm,
                final_result=final_result,
                user_result=user_result,
                ai_result=ai_result,
                a_only_policy=policy_name,
            )
            return output

        if final_decision == "GUIDE":
            output["delivery_mode"] = "reference_only"
            output["assistant_instruction"] = self._guide_instruction(
                locale=locale_norm,
                final_result=final_result,
                user_result=user_result,
                ai_result=ai_result,
            )
            output["draft_reference"] = _safe_str(ai_draft)
            return output

        output["delivery_mode"] = "direct_pass"
        output["approved_response"] = _safe_str(ai_draft)
        return output
