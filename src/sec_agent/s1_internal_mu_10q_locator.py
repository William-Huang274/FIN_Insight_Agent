from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.s1_internal_supplemental_assets import (
    _validate_public_source_result,
)


POLICY_SCHEMA = "fin_ia_0_1_3_s1_internal_mu_10q_locator_policy_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_internal_mu_10q_locator_observation_v1_0"
CONTRACT_REF = "fin_0_1_3.S1.internal_mu_q3_fy2026_10q_locator:v1"
RUN_SCOPE = "S1_INTERNAL_CURRENT_CORPUS_AND_INDEX_REFRESH"


class S1InternalMu10QLocatorError(RuntimeError):
    pass


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise S1InternalMu10QLocatorError("internal_mu_10q_locator_object_required")
    return value


def load_internal_mu_10q_locator_policy(
    path: str | Path, *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or policy.get("run_scope") != RUN_SCOPE
        or policy.get("binding_hash_profile")
        != "sha256_utf8_lf_normalized_v1"
    ):
        raise S1InternalMu10QLocatorError(
            "internal_mu_10q_locator_policy_identity_invalid"
        )
    inputs = dict(policy.get("immutable_inputs") or {})
    ref = str(inputs.get("source_acquisition_result_ref") or "")
    supplied = str(inputs.get("source_acquisition_result_sha256") or "")
    target = root / ref
    if not ref or not target.is_file() or _normalized_sha256(target) != supplied:
        raise S1InternalMu10QLocatorError(
            "internal_mu_10q_locator_source_result_binding_invalid"
        )
    hard = dict(policy.get("hard_boundaries") or {})
    if (
        hard.get("retained_capture_only") is not True
        or hard.get("benchmark_exact_url_used_for_discovery") is not False
        or any(
            int(hard.get(name, -1)) != 0
            for name in (
                "network",
                "provider",
                "model",
                "embedding",
                "rerank",
                "evidence_promotion",
            )
        )
    ):
        raise S1InternalMu10QLocatorError(
            "internal_mu_10q_locator_boundary_invalid"
        )
    expected = dict(policy.get("target") or {})
    if (
        expected.get("ticker") != "MU"
        or expected.get("cik") != "0000723125"
        or expected.get("form_type") != "10-Q"
    ):
        raise S1InternalMu10QLocatorError(
            "internal_mu_10q_locator_target_invalid"
        )
    return policy


def _submission_rows(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    recent = dict((payload.get("filings") or {}).get("recent") or {})
    fields = (
        "accessionNumber",
        "filingDate",
        "reportDate",
        "form",
        "primaryDocument",
    )
    columns = [list(recent.get(field) or []) for field in fields]
    if not columns or len({len(column) for column in columns}) != 1:
        raise S1InternalMu10QLocatorError(
            "internal_mu_10q_locator_submissions_shape_invalid"
        )
    return [
        {field: str(columns[index][row]) for index, field in enumerate(fields)}
        for row in range(len(columns[0]))
    ]


def build_internal_mu_10q_locator_observation(
    *, policy: Mapping[str, Any], repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    result_ref = str(
        policy["immutable_inputs"]["source_acquisition_result_ref"]
    )
    source_result = _read_json(root / result_ref)
    _validate_public_source_result(source_result)
    mu = [
        row
        for row in source_result.get("source_results") or []
        if row.get("ticker") == "MU"
    ]
    if len(mu) != 1:
        raise S1InternalMu10QLocatorError(
            "internal_mu_10q_locator_mu_result_missing"
        )
    attempts = [
        item
        for item in mu[0].get("attempts") or []
        if str(item.get("route_id") or "").endswith(":sec_submissions")
        and item.get("status") == "captured"
    ]
    if len(attempts) != 1:
        raise S1InternalMu10QLocatorError(
            "internal_mu_10q_locator_submission_capture_missing"
        )
    capture_ref = dict(attempts[0]["response_capture"])
    runtime_ref = str(
        source_result["public_private_separation"]["runtime_root_ref"]
    )
    runtime_root = (root / runtime_ref).resolve()
    runtime_root.relative_to(root / "data" / "workbench_private")
    store = FileCanonicalObjectStore(runtime_root / "objects")
    captured = store.get_json(
        str(capture_ref["object_key"]), expected_digest=str(capture_ref["digest"])
    )
    body = base64.b64decode(str(captured.get("body_base64") or ""), validate=True)
    if (
        captured.get("capture_before_parse") is not True
        or captured.get("credential_cookie_authorization_present") is not False
        or int(captured.get("status_code") or 0) != 200
        or str(captured.get("final_url") or "")
        != "https://data.sec.gov/submissions/CIK0000723125.json"
        or len(body) != int(captured.get("body_bytes") or -1)
        or hashlib.sha256(body).hexdigest()
        != str(captured.get("body_sha256") or "")
    ):
        raise S1InternalMu10QLocatorError(
            "internal_mu_10q_locator_capture_integrity_invalid"
        )
    payload = json.loads(body.decode("utf-8"))
    expected = dict(policy["target"])
    matches = [
        row
        for row in _submission_rows(payload)
        if row["accessionNumber"] == expected["accession_number"]
        and row["filingDate"] == expected["filing_date"]
        and row["reportDate"] == expected["report_date"]
        and row["form"] == expected["form_type"]
        and row["primaryDocument"] == expected["primary_document"]
    ]
    if len(matches) != 1:
        raise S1InternalMu10QLocatorError(
            "internal_mu_10q_locator_target_not_unique"
        )
    accession_digits = expected["accession_number"].replace("-", "")
    source_url = (
        "https://www.sec.gov/Archives/edgar/data/723125/"
        f"{accession_digits}/{expected['primary_document']}"
    )
    body_out = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "status": "retained_capture_locator_proven",
        "source_acquisition_result_digest": str(source_result["result_digest"]),
        "locator_source_capture_ref": str(capture_ref["object_key"]),
        "locator_source_capture_digest": str(capture_ref["digest"]),
        "target": {**expected, "source_url": source_url},
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "model": 0,
            "embedding": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "benchmark_exact_url_used_for_discovery": False,
        "candidate_state": "locator_only_not_source_not_evidence",
    }
    return {**body_out, "locator_digest": canonical_digest(body_out)}


__all__ = [
    "CONTRACT_REF",
    "POLICY_SCHEMA",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "S1InternalMu10QLocatorError",
    "build_internal_mu_10q_locator_observation",
    "load_internal_mu_10q_locator_policy",
]
