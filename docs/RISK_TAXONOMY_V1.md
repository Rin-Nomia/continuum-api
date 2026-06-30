# RISK_TAXONOMY_V1

Version: `v1`  
Source of truth: `configs/risk_taxonomy.yaml`

---

## Purpose

This taxonomy standardizes high-risk naming across:

- API response (`/api/v1/analyze`)
- C3 dashboard presentation/export
- Evidence/report payloads

The same case should map to the same:

- `intervention_reason_code` (trigger code)
- `risk_category` (stable machine-readable bucket)
- `risk_label` (business/legal readable label)

---

## Category mapping

| risk_category | risk_label | Main reason codes |
|---|---|---|
| `no_intervention` | No intervention | `no_intervention` |
| `commitment_refund_discount` | Unauthorized refund or discount commitment | `unauthorized_refund_commitment`, `unauthorized_discount_commitment` |
| `commitment_legal_financial` | Unauthorized legal or financial commitment | `unauthorized_compensation_commitment`, `unauthorized_legal_guarantee`, `unauthorized_contract_change`, `mandatory_human_handoff` |
| `policy_authority_override` | Policy or authority override risk | `unauthorized_policy_override`, `ambiguous_commitment_risk`, `pressure_induced_commitment` |
| `escalation_pressure` | Escalation pressure risk | `escalation_pressure`, `guide_public_escalation` |
| `crisis_safety` | Crisis safety risk | `crisis_self_harm`, `OOS_CRISIS` |
| `tone_behavioral_risk` | Tone behavioral risk | `TONE_ANXIOUS`, `TONE_SHARP`, `TONE_COLD`, `TONE_BLUR`, `TONE_PUSHY`, `TONE_RHYTHM`, `TONE_UNKNOWN` |
| `governance_system_error` | Governance system exception | `INTERNAL_GOVERNANCE_BLOCK`, `UNKNOWN_GOVERNANCE_BLOCK`, `INPUT_TOO_SHORT` |

---

## Resolution rules

1. If `decision_state = ALLOW`:
   - `intervention_reason_code = null`
   - `risk_category = no_intervention`
2. If `decision_state in (GUIDE, BLOCK)`:
   - resolve by `intervention_reason_code` using taxonomy config
3. If reason code is unknown:
   - `risk_category = unknown_intervention_risk`
   - `risk_label = Unknown intervention risk`

---

## Notes

- Taxonomy updates should be additive and backward-compatible when possible.
- Renaming existing `risk_category` values should be treated as a contract change.
