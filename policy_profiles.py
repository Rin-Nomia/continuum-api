"""
Policy profile manager for multi-tenant commitment governance.

Supports:
- multiple profile manifests under configs/policy_profiles/*.yaml
- rule CRUD (upsert/disable)
- version snapshots and rollback
- compiled effective commitment rules per profile
"""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


_PROFILE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_RULE_GROUPS = {"categories", "additional_patterns"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return int(default)


class PolicyProfileManager:
    def __init__(self, repo_dir: str):
        self.repo_dir = Path(repo_dir).resolve()
        self.profiles_dir = self.repo_dir / "configs" / "policy_profiles"
        self.versions_dir = self.profiles_dir / "versions"
        self.compiled_dir = self.profiles_dir / ".compiled"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        self.compiled_dir.mkdir(parents=True, exist_ok=True)
        self._seed_profiles_if_missing()

    def _validate_profile_id(self, profile_id: str) -> str:
        pid = str(profile_id or "").strip()
        if not _PROFILE_ID_RE.match(pid):
            raise ValueError("invalid_profile_id")
        return pid

    def _profile_path(self, profile_id: str) -> Path:
        pid = self._validate_profile_id(profile_id)
        return self.profiles_dir / f"{pid}.yaml"

    def _history_path(self, profile_id: str) -> Path:
        return self.versions_dir / profile_id / "history.jsonl"

    def _version_snapshot_path(self, profile_id: str, version: int) -> Path:
        return self.versions_dir / profile_id / f"v{int(version)}.yaml"

    def _compiled_rules_path(self, profile_id: str) -> Path:
        return self.compiled_dir / f"{profile_id}.compiled.yaml"

    def _read_yaml(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return raw if isinstance(raw, dict) else {}

    def _write_yaml(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")

    def _read_base_rules(self, source_rules_path: str) -> Dict[str, Any]:
        source = (source_rules_path or "").strip() or "configs/commitment_rules.yaml"
        path = Path(source)
        if not path.is_absolute():
            path = self.repo_dir / source
        payload = self._read_yaml(path)
        if not payload:
            fallback = self.repo_dir / "configs" / "commitment_rules.yaml"
            payload = self._read_yaml(fallback)
        if "enabled" not in payload:
            payload["enabled"] = True
        if "default_decision" not in payload:
            payload["default_decision"] = "ALLOW"
        payload.setdefault("categories", {})
        payload.setdefault("allowlist", {})
        payload.setdefault("mandatory_human_handoff", {"triggers": []})
        payload.setdefault("additional_patterns", {})
        return payload

    def _merge_rule_group(
        self,
        *,
        effective: Dict[str, Any],
        overrides: Dict[str, Any],
        group_name: str,
    ) -> None:
        base_group = effective.get(group_name, {})
        if not isinstance(base_group, dict):
            base_group = {}

        ov_group = overrides.get(group_name, {})
        if not isinstance(ov_group, dict):
            ov_group = {}

        merged = dict(base_group)
        for rule_name, node in ov_group.items():
            if not isinstance(node, dict):
                continue
            enabled = node.get("enabled", True)
            if isinstance(enabled, bool) and not enabled:
                merged.pop(str(rule_name), None)
                continue
            old_node = merged.get(str(rule_name), {})
            if not isinstance(old_node, dict):
                old_node = {}
            new_node = dict(old_node)
            for k, v in node.items():
                if k == "enabled":
                    continue
                new_node[k] = v
            merged[str(rule_name)] = new_node
        effective[group_name] = merged

    def _compile_effective_rules(self, profile_payload: Dict[str, Any]) -> Dict[str, Any]:
        source_rules_path = str(profile_payload.get("source_rules_path", "configs/commitment_rules.yaml"))
        base = self._read_base_rules(source_rules_path)
        effective = copy.deepcopy(base)

        overrides = profile_payload.get("overrides", {})
        if not isinstance(overrides, dict):
            overrides = {}

        # top-level direct overrides
        for top_key in ("enabled", "default_decision", "allowlist", "mandatory_human_handoff"):
            if top_key in overrides:
                effective[top_key] = copy.deepcopy(overrides[top_key])

        self._merge_rule_group(effective=effective, overrides=overrides, group_name="categories")
        self._merge_rule_group(effective=effective, overrides=overrides, group_name="additional_patterns")

        # metadata for auditability (ignored by commitment guard)
        effective["policy_profile"] = {
            "profile_id": str(profile_payload.get("profile_id", "default")),
            "version": _safe_int(profile_payload.get("version"), 1),
            "updated_at_utc": str(profile_payload.get("updated_at_utc", "")),
            "source_rules_path": source_rules_path,
        }
        return effective

    def _record_version_snapshot(self, profile_id: str, payload: Dict[str, Any], action: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        pid = self._validate_profile_id(profile_id)
        version = _safe_int(payload.get("version"), 1)
        snapshot_path = self._version_snapshot_path(pid, version)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_yaml(snapshot_path, payload)

        event = {
            "ts_utc": _utc_now(),
            "profile_id": pid,
            "version": version,
            "action": action,
            "metadata": metadata or {},
        }
        history_path = self._history_path(pid)
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _save_profile(self, profile_id: str, payload: Dict[str, Any], action: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pid = self._validate_profile_id(profile_id)
        payload = copy.deepcopy(payload)
        payload["profile_id"] = pid
        payload["version"] = _safe_int(payload.get("version"), 1)
        payload["updated_at_utc"] = _utc_now()
        payload.setdefault("status", "active")
        payload.setdefault("source_rules_path", "configs/commitment_rules.yaml")
        payload.setdefault("overrides", {})
        self._write_yaml(self._profile_path(pid), payload)
        self._record_version_snapshot(pid, payload, action=action, metadata=metadata)
        self.compile_profile(pid)
        return payload

    def _seed_profiles_if_missing(self) -> None:
        default_path = self._profile_path("default")
        if not default_path.exists():
            payload = {
                "profile_id": "default",
                "display_name": "Default Policy",
                "description": "Default commitment governance profile.",
                "status": "active",
                "version": 1,
                "source_rules_path": "configs/commitment_rules.yaml",
                "overrides": {},
            }
            self._save_profile("default", payload, action="seed_default")

        a_path = self._profile_path("customer_a")
        if not a_path.exists():
            payload = {
                "profile_id": "customer_a",
                "display_name": "Customer A Policy",
                "description": "Customer A: stricter discount policy.",
                "status": "active",
                "version": 1,
                "source_rules_path": "configs/commitment_rules.yaml",
                "overrides": {
                    "categories": {
                        "discount_commitment": {
                            "decision": "BLOCK",
                            "reason_code": "unauthorized_discount_commitment",
                        }
                    }
                },
            }
            self._save_profile("customer_a", payload, action="seed_customer_a")

        b_path = self._profile_path("customer_b")
        if not b_path.exists():
            payload = {
                "profile_id": "customer_b",
                "display_name": "Customer B Policy",
                "description": "Customer B: strict refund commitment handling.",
                "status": "active",
                "version": 1,
                "source_rules_path": "configs/commitment_rules.yaml",
                "overrides": {
                    "categories": {
                        "refund_commitment": {
                            "decision": "BLOCK",
                            "reason_code": "unauthorized_refund_commitment",
                        }
                    }
                },
            }
            self._save_profile("customer_b", payload, action="seed_customer_b")

    def list_profiles(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for path in sorted(self.profiles_dir.glob("*.yaml")):
            payload = self._read_yaml(path)
            if not payload:
                continue
            pid = str(payload.get("profile_id", path.stem))
            out.append(
                {
                    "profile_id": pid,
                    "display_name": str(payload.get("display_name", pid)),
                    "description": str(payload.get("description", "")),
                    "status": str(payload.get("status", "active")),
                    "version": _safe_int(payload.get("version"), 1),
                    "updated_at_utc": str(payload.get("updated_at_utc", "")),
                    "compiled_rules_path": str(self._compiled_rules_path(pid)),
                }
            )
        return out

    def load_profile(self, profile_id: str) -> Dict[str, Any]:
        pid = self._validate_profile_id(profile_id)
        payload = self._read_yaml(self._profile_path(pid))
        if not payload:
            raise FileNotFoundError("policy_profile_not_found")
        return payload

    def list_versions(self, profile_id: str) -> List[int]:
        pid = self._validate_profile_id(profile_id)
        d = self.versions_dir / pid
        if not d.exists():
            return []
        versions: List[int] = []
        for p in d.glob("v*.yaml"):
            name = p.stem
            if not name.startswith("v"):
                continue
            versions.append(_safe_int(name[1:], 0))
        return sorted([v for v in versions if v > 0])

    def compile_profile(self, profile_id: str) -> Dict[str, Any]:
        pid = self._validate_profile_id(profile_id)
        profile = self.load_profile(pid)
        effective = self._compile_effective_rules(profile)
        compiled_path = self._compiled_rules_path(pid)
        self._write_yaml(compiled_path, effective)
        return {
            "profile_id": pid,
            "version": _safe_int(profile.get("version"), 1),
            "compiled_rules_path": str(compiled_path),
            "status": str(profile.get("status", "active")),
        }

    def resolve_profile(self, profile_id: Optional[str] = None) -> Dict[str, Any]:
        requested = str(profile_id or "").strip() or "default"
        pid = self._validate_profile_id(requested)
        try:
            return self.compile_profile(pid)
        except Exception:
            # Always provide a working default profile path.
            return self.compile_profile("default")

    def upsert_rule(
        self,
        *,
        profile_id: str,
        rule_group: str,
        rule_name: str,
        rule_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        pid = self._validate_profile_id(profile_id)
        group = str(rule_group or "").strip()
        if group not in _RULE_GROUPS:
            raise ValueError("invalid_rule_group")
        rn = str(rule_name or "").strip()
        if not rn:
            raise ValueError("invalid_rule_name")
        if not isinstance(rule_payload, dict):
            raise ValueError("invalid_rule_payload")

        profile = self.load_profile(pid)
        profile["version"] = _safe_int(profile.get("version"), 1) + 1
        overrides = profile.get("overrides")
        if not isinstance(overrides, dict):
            overrides = {}
        group_payload = overrides.get(group)
        if not isinstance(group_payload, dict):
            group_payload = {}

        node = dict(rule_payload)
        if "enabled" not in node:
            node["enabled"] = True
        group_payload[rn] = node
        overrides[group] = group_payload
        profile["overrides"] = overrides
        saved = self._save_profile(
            pid,
            profile,
            action="rule_upsert",
            metadata={"rule_group": group, "rule_name": rn},
        )
        return {
            "profile_id": pid,
            "version": _safe_int(saved.get("version"), 1),
            "rule_group": group,
            "rule_name": rn,
        }

    def disable_rule(
        self,
        *,
        profile_id: str,
        rule_group: str,
        rule_name: str,
    ) -> Dict[str, Any]:
        pid = self._validate_profile_id(profile_id)
        group = str(rule_group or "").strip()
        if group not in _RULE_GROUPS:
            raise ValueError("invalid_rule_group")
        rn = str(rule_name or "").strip()
        if not rn:
            raise ValueError("invalid_rule_name")

        profile = self.load_profile(pid)
        profile["version"] = _safe_int(profile.get("version"), 1) + 1
        overrides = profile.get("overrides")
        if not isinstance(overrides, dict):
            overrides = {}
        group_payload = overrides.get(group)
        if not isinstance(group_payload, dict):
            group_payload = {}
        group_payload[rn] = {"enabled": False}
        overrides[group] = group_payload
        profile["overrides"] = overrides
        saved = self._save_profile(
            pid,
            profile,
            action="rule_disable",
            metadata={"rule_group": group, "rule_name": rn},
        )
        return {
            "profile_id": pid,
            "version": _safe_int(saved.get("version"), 1),
            "rule_group": group,
            "rule_name": rn,
            "disabled": True,
        }

    def rollback(self, *, profile_id: str, target_version: int) -> Dict[str, Any]:
        pid = self._validate_profile_id(profile_id)
        tv = _safe_int(target_version, 0)
        if tv <= 0:
            raise ValueError("invalid_target_version")

        snapshot_path = self._version_snapshot_path(pid, tv)
        if not snapshot_path.exists():
            raise FileNotFoundError("target_version_not_found")

        snapshot_payload = self._read_yaml(snapshot_path)
        if not snapshot_payload:
            raise RuntimeError("target_version_invalid")

        current = self.load_profile(pid)
        new_version = _safe_int(current.get("version"), 1) + 1
        snapshot_payload["version"] = new_version
        snapshot_payload["rollback_of_version"] = tv
        saved = self._save_profile(
            pid,
            snapshot_payload,
            action="rollback",
            metadata={"target_version": tv},
        )
        return {
            "profile_id": pid,
            "target_version": tv,
            "version": _safe_int(saved.get("version"), 1),
        }

