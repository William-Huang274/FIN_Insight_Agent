"""Canonical package identity validation for the isolated Point 01 M1-A1 audit.

This is audit-harness code, not M1 runtime authority.  It deliberately makes
the package verification source and every package-authority field digest-bound,
then requires an external total-reviewer admission before an audit gate may
execute actual probes.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Callable

from sec_agent.canonical_runtime.models import canonical_digest


PACKAGE_MANIFEST_SCHEMA_VERSION = "finsight_point01_m1_a1_adversarial_audit_package_manifest_v1_1"
PACKAGE_ADMISSION_SCHEMA_VERSION = "finsight_point01_m1_a1_external_package_admission_v1_0"
PACKAGE_INPUT_BYTES_SOURCE = "git_index"
TOTAL_REVIEWER_IDENTITY = "william/003/total_reviewer"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

PACKAGE_PAYLOAD_FIELDS = (
    "schema_version",
    "scope",
    "package_ref",
    "authority_boundary",
    "input_bytes_source",
    "a0_design_digest",
    "input_file_sha256",
    "fixed_store_fingerprints",
    "fixture_corpus_digest",
    "oracle_policy_digest",
    "package_admission_ref",
    "package_admission_required",
)
PACKAGE_MANIFEST_FIELDS = frozenset((*PACKAGE_PAYLOAD_FIELDS, "package_digest"))
PACKAGE_ADMISSION_FIELDS = frozenset(
    {
        "schema_version",
        "admission_ref",
        "reviewer_identity",
        "decision",
        "package_manifest_schema_version",
        "package_ref",
        "package_digest",
        "scope",
        "authority_boundary",
    }
)


def canonical_package_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the full digest-covered package identity payload.

    The explicit field list prevents a future authority-affecting field from
    being silently accepted outside the signed identity.  Unknown fields are
    rejected by ``verify_package_manifest`` rather than ignored.
    """

    return {field: manifest[field] for field in PACKAGE_PAYLOAD_FIELDS}


def package_payload_digest(manifest: dict[str, Any]) -> str:
    return canonical_digest(canonical_package_payload(manifest))


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _schema_errors(manifest: dict[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    keys = set(manifest)
    missing = sorted(PACKAGE_MANIFEST_FIELDS - keys)
    unexpected = sorted(keys - PACKAGE_MANIFEST_FIELDS)
    if missing:
        errors.append(f"missing_fields:{','.join(missing)}")
    if unexpected:
        errors.append(f"unexpected_fields:{','.join(unexpected)}")
    if missing:
        return tuple(errors)
    if manifest["schema_version"] != PACKAGE_MANIFEST_SCHEMA_VERSION:
        errors.append("schema_version_invalid")
    for field in ("scope", "package_ref", "authority_boundary", "package_admission_ref"):
        if not isinstance(manifest[field], str) or not manifest[field].strip():
            errors.append(f"{field}_invalid")
    if manifest["package_admission_required"] is not True:
        errors.append("package_admission_required_must_be_true")
    for field in ("a0_design_digest", "fixture_corpus_digest", "oracle_policy_digest", "package_digest"):
        if not _is_sha256(manifest[field]):
            errors.append(f"{field}_must_be_sha256")
    file_hashes = manifest["input_file_sha256"]
    if not isinstance(file_hashes, dict) or not file_hashes:
        errors.append("input_file_sha256_invalid")
    else:
        for relative_path, digest in sorted(file_hashes.items()):
            candidate = Path(relative_path)
            if not isinstance(relative_path, str) or candidate.is_absolute() or ".." in candidate.parts:
                errors.append(f"input_path_invalid:{relative_path}")
            if not _is_sha256(digest):
                errors.append(f"input_hash_invalid:{relative_path}")
    fingerprints = manifest["fixed_store_fingerprints"]
    if not isinstance(fingerprints, dict):
        errors.append("fixed_store_fingerprints_invalid")
    else:
        approval = fingerprints.get("fixed_approval_store")
        absence = fingerprints.get("canonical_or_business_store_absence_manifest")
        if not isinstance(approval, dict) or not isinstance(approval.get("path"), str) or not _is_sha256(approval.get("sha256")):
            errors.append("fixed_approval_store_fingerprint_invalid")
        if not isinstance(absence, dict) or not isinstance(absence.get("registered_paths"), list) or not isinstance(absence.get("status"), str) or not isinstance(absence.get("enforcement"), str):
            errors.append("canonical_or_business_store_absence_manifest_invalid")
    return tuple(errors)


def verify_package_manifest(
    root: Path,
    manifest: dict[str, Any],
    *,
    read_bytes: Callable[[Path], bytes] | None = None,
) -> dict[str, Any]:
    """Verify digest-bound identity first, then fixed-source input hashes.

    No working-tree fallback exists.  A tampered ``input_bytes_source`` changes
    the payload digest; a self-signed replacement still fails later unless an
    exact external admission is supplied to the gate.
    """

    try:
        calculated_package_digest = package_payload_digest(manifest)
    except (KeyError, TypeError):
        return {
            "status": "package_schema_validation_failed",
            "mismatches": (),
            "schema_errors": _schema_errors(manifest),
            "calculated_package_digest": None,
            "manifest_digest": canonical_digest(manifest),
        }
    if manifest.get("package_digest") != calculated_package_digest:
        return {
            "status": "package_digest_mismatch",
            "mismatches": (),
            "schema_errors": (),
            "calculated_package_digest": calculated_package_digest,
            "manifest_digest": canonical_digest(manifest),
        }
    schema_errors = _schema_errors(manifest)
    if schema_errors:
        return {
            "status": "package_schema_validation_failed",
            "mismatches": (),
            "schema_errors": schema_errors,
            "calculated_package_digest": calculated_package_digest,
            "manifest_digest": canonical_digest(manifest),
        }
    if manifest["input_bytes_source"] != PACKAGE_INPUT_BYTES_SOURCE:
        return {
            "status": "package_input_source_forbidden",
            "mismatches": (),
            "schema_errors": (),
            "calculated_package_digest": calculated_package_digest,
            "manifest_digest": canonical_digest(manifest),
        }
    mismatches: list[str] = []
    loader = read_bytes or Path.read_bytes
    for relative_path, expected in sorted(manifest["input_file_sha256"].items()):
        candidate = (root / relative_path).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            mismatches.append(relative_path)
            continue
        if not candidate.is_file() or hashlib.sha256(loader(candidate)).hexdigest() != expected:
            mismatches.append(relative_path)
    return {
        "status": "pass" if not mismatches else "package_input_digest_mismatch",
        "mismatches": tuple(mismatches),
        "schema_errors": (),
        "calculated_package_digest": calculated_package_digest,
        "manifest_digest": canonical_digest(manifest),
    }


def verify_package_admission(manifest: dict[str, Any], admission: dict[str, Any] | None) -> dict[str, Any]:
    """Validate an explicit package-external total-reviewer admission.

    Authority resolution is intentionally injected; this package verifier never
    opens an ambient, fixed, or production approval store.  ``None`` is the
    normal pre-review state and is fail-closed.
    """

    if admission is None:
        return {"status": "package_admission_required", "admission_digest": None}
    if set(admission) != PACKAGE_ADMISSION_FIELDS:
        return {"status": "package_admission_schema_invalid", "admission_digest": canonical_digest(admission)}
    if admission["schema_version"] != PACKAGE_ADMISSION_SCHEMA_VERSION:
        return {"status": "package_admission_schema_invalid", "admission_digest": canonical_digest(admission)}
    if admission["decision"] != "admitted":
        return {"status": "package_admission_not_admitted", "admission_digest": canonical_digest(admission)}
    if admission["reviewer_identity"] != TOTAL_REVIEWER_IDENTITY:
        return {"status": "package_admission_reviewer_untrusted", "admission_digest": canonical_digest(admission)}
    bindings = ("admission_ref", "package_manifest_schema_version", "package_ref", "package_digest", "scope", "authority_boundary")
    expected = {
        "admission_ref": manifest["package_admission_ref"],
        "package_manifest_schema_version": manifest["schema_version"],
        "package_ref": manifest["package_ref"],
        "package_digest": manifest["package_digest"],
        "scope": manifest["scope"],
        "authority_boundary": manifest["authority_boundary"],
    }
    mismatch_fields = tuple(field for field in bindings if admission[field] != expected[field])
    return {
        "status": "pass" if not mismatch_fields else "package_admission_binding_mismatch",
        "mismatch_fields": mismatch_fields,
        "admission_digest": canonical_digest(admission),
    }
