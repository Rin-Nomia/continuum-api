# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- Added `/api/v1/ops/metrics` for aggregated runtime indicators:
  - decision_state distribution
  - latency percentiles (p50/p95/p99)
  - llm usage rate
  - out-of-scope hit rate
- Added status dashboard route `/status` and runtime status endpoint `/api/v1/status`.

### Changed
- Public analyze contract now exposes governance decision as `decision_state` (`ALLOW|GUIDE|BLOCK`).
- Removed raw user text exposure from API response (`original` is no longer returned).
- Enforced request length contract at API boundary to align with pipeline thresholds.
- Updated docs and deployment test script to use `confidence_final` and `decision_state`.

## [2026-02-14]

### Added
- Added governance rule file `.cursor/rules/governance.mdc`.

### Changed
- Standardized privacy baseline:
  - no raw input text passed to logger
  - content-derived fields scrubbed before log write
- Added mock dashboard page `status.html`.

