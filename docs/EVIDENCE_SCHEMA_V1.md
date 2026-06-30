# EVIDENCE_SCHEMA_V1 and API Governance Contract

Version: `1.0`  
Source of truth: `continuum-api-repo/app.py`

---

## 1) Purpose

This document defines:

1. The external `/api/v1/analyze` response contract for business/legal readability.
2. The content-free evidence schema written by logger (`build_evidence_v1`).

Key addition in A-P0-2:
- `governance_mode` (`Sense`/`Guide`/`Block`)
- `intervention_reason_code` (why the system intervened)

---

## 2) Analyze API response fields (external contract)

| Field | Type | Description | Example |
|---|---|---|---|
| decision_state | string (`ALLOW`/`GUIDE`/`BLOCK`) | Internal governance decision state | `GUIDE` |
| governance_mode | string (`Sense`/`Guide`/`Block`) | External-readable mode mapped from `decision_state` | `Guide` |
| intervention_reason_code | string or null | Specific intervention trigger reason. `null` when no intervention | `unauthorized_refund_commitment` |
| freq_type | string | Risk/tone category label | `CommitmentRisk` |
| confidence_final | float | Final confidence in [0,1] | `1.0` |
| confidence_classifier | float or null | Classifier confidence in [0,1] | `1.0` |
| scenario | string | Scenario routing label | `authority_boundary_commitment` |
| repaired_text | string or null | Governed output text (or empty on hard block) | `此請求可能涉及超出權限的承諾，請依官方政策與授權流程處理。` |
| repair_note | string or null | Human-readable note for intervention | `Commitment boundary triggered: unauthorized_refund_commitment` |
| privacy_guard_ok | boolean | Privacy guard status | `true` |
| llm_used | boolean or null | Whether LLM was used | `false` |
| cache_hit | boolean or null | Whether cache was hit | `false` |
| model | string | Model name if any | `""` |
| usage | object | Token/runtime usage info | `{}` |
| output_source | string or null | Output path source | `authority_boundary_check` |
| audit | object | Content-free audit metadata | `{"input_hash":"...","timing_ms":{"total":1}}` |
| metrics | object | Governance metrics summary | `{"reason_code":"unauthorized_refund_commitment","decision_state":"GUIDE"}` |

---

## 3) decision_state -> governance_mode mapping

| decision_state | governance_mode | Meaning |
|---|---|---|
| `ALLOW` | `Sense` | Monitor-only, no direct intervention |
| `GUIDE` | `Guide` | Soft intervention / constrained response |
| `BLOCK` | `Block` | Hard interception / safe diversion |

---

## 4) intervention_reason_code catalog

When `decision_state = ALLOW`, `intervention_reason_code = null`.

### 4.1 commitment_guard (authority boundary)

- `unauthorized_refund_commitment`
- `unauthorized_discount_commitment`
- `unauthorized_compensation_commitment`
- `unauthorized_legal_guarantee`
- `escalation_pressure`
- `unauthorized_policy_override`
- `unauthorized_contract_change`
- `ambiguous_commitment_risk`
- `pressure_induced_commitment`
- `mandatory_human_handoff` (keyword-triggered handoff)

### 4.2 safety_gate

- `crisis_self_harm`

### 4.3 tone classifier / tone routing

- `TONE_ANXIOUS`
- `TONE_SHARP`
- `TONE_COLD`
- `TONE_BLUR`
- `TONE_PUSHY`
- `TONE_RHYTHM`
- `TONE_UNKNOWN`

---

## 5) Evidence payload required keys (logger schema)

The logger evidence payload (`build_evidence_v1`) is content-free and requires:

1. `schema_version`
2. `input_fp_sha256`
3. `input_length`
4. `output_fp_sha256`
5. `output_length`
6. `freq_type`
7. `mode`
8. `scenario`
9. `confidence`
10. `metrics`
11. `audit`
12. `llm_used`
13. `cache_hit`
14. `model`
15. `usage`
16. `output_source`
17. `governance_mode`
18. `intervention_reason_code`
19. `api_version`
20. `pipeline_version_fingerprint`

---

## 6) Privacy and validation notes

- No raw input/output text is persisted in evidence.
- `metrics` and `audit` are scrubbed from content-derived keys before persistence.
- If schema validation fails, runtime does not crash; evidence includes:
  - `schema_valid: false`
  - `schema_errors: [...]`
