"""Fail closed when an exportable M6.3/M6.5 audit artifact leaks a secret.

The restricted v4 source is read only to derive a non-exported comparison
value.  This script emits only hashes, paths and pass/fail booleans; it never
prints or persists a nonce, SEC User-Agent, or raw document content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
RESTRICTED_SOURCE = ROOT / "data/manifests/point01_m6_3_5_v4_single_fixed_nvda_10k_live_pilot_result_v1_0.json"
DEFAULT_EXPORTABLE_ARTIFACTS = (
    ROOT / "data/manifests/point01_m6_3_5_v5_sanitized_authorized_live_audit_projection_v1_0.json",
    ROOT / "data/manifests/point01_m6_3_5_v5_artifact_contract_refreeze_result_v1_0.json",
)
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m6_3_5_v5_artifact_secret_scan_result_v1_0.json"
FORBIDDEN_KEYS = frozenset({"approval_nonce", "global_approval_nonce", "user_agent", "raw_html"})


class ArtifactSecretScanError(RuntimeError):
    """An exportable artifact contains a forbidden secret surface."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactSecretScanError(f"artifact_unreadable:{path.name}") from exc


def _keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, nested in value.items():
            yield str(key)
            yield from _keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _keys(nested)


def build_result(*, restricted_source: Path = RESTRICTED_SOURCE, exportable_artifacts: tuple[Path, ...] = DEFAULT_EXPORTABLE_ARTIFACTS) -> dict[str, Any]:
    restricted = _read_json(restricted_source)
    raw_nonce = str(((restricted.get("receipt") or {}).get("global_approval_nonce") or "")) if isinstance(restricted, dict) else ""
    if len(raw_nonce) < 16:
        raise ArtifactSecretScanError("restricted_source_nonce_not_available")
    scanned: list[dict[str, Any]] = []
    violations: list[str] = []
    for path in exportable_artifacts:
        value = _read_json(path)
        rendered = path.read_text(encoding="utf-8")
        keys = set(_keys(value))
        forbidden_keys = sorted(FORBIDDEN_KEYS & keys)
        raw_nonce_present = raw_nonce in rendered
        user_agent_plaintext_present = "SEC_USER_AGENT" in rendered or "User-Agent" in rendered
        if forbidden_keys or raw_nonce_present or user_agent_plaintext_present:
            violations.append(path.name)
        scanned.append(
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "forbidden_keys": forbidden_keys,
                "raw_nonce_present": raw_nonce_present,
                "user_agent_plaintext_present": user_agent_plaintext_present,
            }
        )
    return {
        "result_version": "finsight_point01_m6_3_5_artifact_secret_scan_result_v1_0",
        "status": "pass" if not violations else "fail_closed",
        "restricted_source_sha256": hashlib.sha256(restricted_source.read_bytes()).hexdigest(),
        "scanned_exportable_artifacts": scanned,
        "violations": violations,
        "external_call_count": 0,
        "network_request_count": 0,
        "tool_invocation_count": 0,
        "model_call_count": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Secret-scan exportable v5 M6.3/M6.5 audit artifacts.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_result()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "violations": len(result["violations"]), "external_call_count": 0}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
