# Continuum API SLA (Draft)

This is an operational draft for commercial onboarding.

## 1. Scope

- Endpoint: `/api/v1/analyze`
- Health endpoints: `/health`, `/api/v1/status`, `/api/v1/ops/metrics`

## 2. Availability target

- Monthly uptime target: **99.5%** (draft baseline)

## 3. Latency target

- P95 latency target: **<= 1500 ms** (single-sentence input, normal load)
- Measured from API ingress to API egress
- Source of truth: `/api/v1/ops/metrics -> latency_ms.p95`

## 4. Reliability and fallback

- If logging fails, API must still return decision response.
- If LLM path fails, system must degrade to deterministic fallback path.
- Out-of-scope crisis/self-harm content must return `decision_state=BLOCK`.

## 5. Retry and timeout policy

- Provider retries: exponential retry for transient network/rate-limit errors.
- API timeout policy: enforced at infrastructure gateway layer.

## 6. Security and privacy baseline

- Raw user text is not persisted by logger.
- Content-derived fragments (keyword hits/matches/triggers) are scrubbed before storage.
- `LOG_SALT` is strongly recommended in production.

## 7. Reporting metrics

Required operational indicators:

- decision_state distribution
- p50/p95/p99 latency
- llm usage rate
- out-of-scope hit rate

