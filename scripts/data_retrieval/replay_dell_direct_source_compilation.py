from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC)]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.direct_source_capture import (  # noqa: E402
    validate_dell_direct_source_capture_plan,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from scripts.data_retrieval.run_dell_direct_source_capture import (  # noqa: E402
    DEFAULT_PRIVATE_ROOT,
    _head,
    _read_json,
    _relative,
    _require_clean,
    _sha256,
    _write_new,
)
from scripts.data_retrieval.run_dell_external_source_ladder import (  # noqa: E402
    compile_captured_originals,
)


PLAN = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_direct_source_compilation_replay_plan_v1_0.json"
)
DEFAULT_PUBLIC = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_direct_source_compilation_replay_result_v1_0.json"
)


def _bound_path(ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _validated_digest(value: Mapping[str, Any], field: str, code: str) -> None:
    body = deepcopy(dict(value))
    digest = str(body.pop(field, ""))
    if digest != canonical_digest(body):
        raise ValueError(code)


def validate_replay_plan(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    _validated_digest(
        value,
        "plan_digest",
        "dell_direct_source_compilation_replay_plan_digest_invalid",
    )
    expected_fields = {
        "schema_version",
        "status",
        "recorded_at",
        "case_key",
        "research_as_of",
        "plan_id",
        "predecessor_terminal_binding",
        "effective_capture_plan_binding",
        "defect_receipt_binding",
        "expected_capture_count",
        "expected_corrected_source_url",
        "expected_corrected_publication_date",
        "execution_budget",
        "token_budget_basis",
        "authority",
        "plan_digest",
    }
    predecessor = value.get("predecessor_terminal_binding")
    effective = value.get("effective_capture_plan_binding")
    defect = value.get("defect_receipt_binding")
    budget = value.get("execution_budget")
    token_basis = value.get("token_budget_basis")
    authority = value.get("authority")
    if not (
        set(value) == expected_fields
        and value.get("schema_version")
        == "fin_ia_s1_dell_direct_source_compilation_replay_plan_v1_0"
        and value.get("status")
        == "approved_zero_network_publication_date_correction_replay"
        and str(value.get("case_key") or "").upper() == "DELL"
        and str(value.get("plan_id") or "")
        and str(value.get("research_as_of") or "")
        and isinstance(predecessor, Mapping)
        and str(predecessor.get("ref") or "")
        and len(str(predecessor.get("sha256") or "")) == 64
        and len(str(predecessor.get("result_digest") or "")) == 64
        and str(predecessor.get("attempt_id") or "")
        and isinstance(effective, Mapping)
        and str(effective.get("ref") or "")
        and len(str(effective.get("sha256") or "")) == 64
        and len(str(effective.get("plan_digest") or "")) == 64
        and isinstance(defect, Mapping)
        and str(defect.get("ref") or "")
        and len(str(defect.get("sha256") or "")) == 64
        and len(str(defect.get("receipt_digest") or "")) == 64
        and int(value.get("expected_capture_count") or 0) == 5
        and str(value.get("expected_corrected_source_url") or "").startswith(
            "https://"
        )
        and str(value.get("expected_corrected_publication_date") or "")
        and isinstance(budget, Mapping)
        and budget.get("network_call_ceiling") == 0
        and budget.get("provider_call_ceiling") == 0
        and budget.get("model_call_ceiling") == 0
        and budget.get("generation_call_ceiling") == 0
        and budget.get("capture_reuse_count_required") == 5
        and isinstance(token_basis, Mapping)
        and token_basis.get("model_tokens") == 0
        and token_basis.get("cost_and_latency_are_secondary_constraints") is True
        and str(token_basis.get("node_purpose") or "")
        and str(token_basis.get("input_scale_basis") or "")
        and isinstance(token_basis.get("required_outputs"), list)
        and bool(token_basis["required_outputs"])
        and str(token_basis.get("schema_burden") or "")
        and str(token_basis.get("materiality_and_quality_risk") or "")
        and str(token_basis.get("comparable_run_evidence") or "")
        and str(token_basis.get("reasoning_profile") or "")
        and str(token_basis.get("stop_and_truncation_behavior") or "")
        and isinstance(authority, Mapping)
        and authority.get("predecessor_source_objects_reusable") is False
        and authority.get("predecessor_raw_captures_reusable") is True
        and authority.get("candidate_is_not_evidence") is True
        and authority.get("candidate_decision_and_evidence_gate_required") is True
        and authority.get("gap_closure_authorized") is False
        and authority.get("S1_qualification_authorized") is False
        and authority.get("product_publication_authorized") is False
    ):
        raise ValueError(
            "dell_direct_source_compilation_replay_plan_shape_invalid"
        )
    return value


def _validate_bound_json(
    binding: Mapping[str, Any],
    *,
    digest_field: str,
    code: str,
) -> tuple[Path, dict[str, Any]]:
    path = _bound_path(str(binding["ref"]))
    if not path.is_file() or _sha256(path) != str(binding["sha256"]):
        raise RuntimeError(code + "_file_invalid")
    value = _read_json(path)
    if str(value.get(digest_field) or "") != str(binding[digest_field]):
        raise RuntimeError(code + "_content_invalid")
    _validated_digest(value, digest_field, code + "_digest_invalid")
    return path, value


def _validate_capture_objects(capture_result: Mapping[str, Any], expected: int) -> None:
    rows = [dict(row) for row in capture_result.get("sources") or ()]
    if len(rows) != expected or any(row.get("status") != "captured" for row in rows):
        raise RuntimeError("dell_direct_source_compilation_replay_capture_set_invalid")
    for row in rows:
        for field in ("request_capture", "response_capture"):
            binding = dict(row.get(field) or {})
            path = _bound_path(str(binding.get("object_ref") or ""))
            if not path.is_file() or _sha256(path) != str(binding.get("sha256") or ""):
                raise RuntimeError(
                    "dell_direct_source_compilation_replay_capture_object_invalid"
                )


def run(
    *,
    attempt_id: str,
    plan_path: Path = PLAN,
    private_root: Path = DEFAULT_PRIVATE_ROOT,
    public_output: Path = DEFAULT_PUBLIC,
) -> dict[str, Any]:
    _require_clean()
    plan_path = plan_path.resolve()
    private_root = private_root.resolve()
    public_output = public_output.resolve()
    plan = validate_replay_plan(_read_json(plan_path))
    attempt_root = private_root / attempt_id
    if attempt_root.exists() or public_output.exists():
        raise RuntimeError(
            "dell_direct_source_compilation_replay_attempt_or_output_exists"
        )

    predecessor_path, predecessor = _validate_bound_json(
        plan["predecessor_terminal_binding"],
        digest_field="result_digest",
        code="dell_direct_source_compilation_replay_predecessor",
    )
    effective_path, effective_plan = _validate_bound_json(
        plan["effective_capture_plan_binding"],
        digest_field="plan_digest",
        code="dell_direct_source_compilation_replay_effective_plan",
    )
    defect_path, defect = _validate_bound_json(
        plan["defect_receipt_binding"],
        digest_field="receipt_digest",
        code="dell_direct_source_compilation_replay_defect_receipt",
    )
    effective_plan = validate_dell_direct_source_capture_plan(effective_plan)
    if (
        str(predecessor.get("attempt_id") or "")
        != str(plan["predecessor_terminal_binding"]["attempt_id"])
        or str(predecessor.get("plan_binding", {}).get("plan_digest") or "")
        != str(effective_plan["plan_digest"])
        or defect.get("authority", {}).get("r2_source_object_eligible") is not False
    ):
        raise RuntimeError(
            "dell_direct_source_compilation_replay_lineage_invalid"
        )
    predecessor_capture = deepcopy(
        dict(predecessor.get("original_capture_result") or {})
    )
    expected_capture_count = int(plan["expected_capture_count"])
    _validate_capture_objects(predecessor_capture, expected_capture_count)
    replay_rows = []
    for raw in predecessor_capture["sources"]:
        row = deepcopy(dict(raw))
        row.update(
            {
                "capture_reused_from_predecessor": True,
                "predecessor_capture_status": "captured",
                "transport_attempts": 0,
            }
        )
        replay_rows.append(row)
    replay_capture = {
        "schema_version": (
            "fin_ia_s1_dell_direct_source_compilation_replay_capture_set_v1_0"
        ),
        "status": "immutable_capture_set_replayed_zero_network",
        "source_routes_executed": expected_capture_count,
        "predecessor_captures_reused": expected_capture_count,
        "fresh_network_routes": 0,
        "fresh_network_attempts_lower_bound": 0,
        "fresh_network_attempts_upper_bound": 0,
        "model_calls": 0,
        "sources": replay_rows,
    }
    shortlist = deepcopy(dict(predecessor.get("fetch_shortlist") or {}))
    original_result = compile_captured_originals(
        plan=effective_plan,
        shortlist=shortlist,
        capture_result=replay_capture,
    )

    corrected_url = str(plan["expected_corrected_source_url"])
    corrected_date = str(plan["expected_corrected_publication_date"])
    corrected_sources = [
        dict(row)
        for row in original_result.get("source_objects") or ()
        if str(row.get("source_url") or "") == corrected_url
    ]
    corrected_receipts = [
        dict(row)
        for row in original_result.get("route_receipts") or ()
        if str(row.get("canonical_url") or "") == corrected_url
    ]
    if not (
        len(corrected_sources) == 1
        and len(corrected_receipts) == 1
        and corrected_sources[0].get("publication_date") == corrected_date
        and corrected_receipts[0]
        .get("publication_date_receipt", {})
        .get("selected_publication_date")
        == corrected_date
        and corrected_receipts[0]
        .get("publication_date_receipt", {})
        .get("provider_date_corroborates_selected")
        is True
    ):
        raise RuntimeError(
            "dell_direct_source_compilation_replay_date_correction_failed"
        )

    predecessor_sources = {
        str(row.get("source_url") or ""): dict(row)
        for row in (
            predecessor.get("original_compilation_result", {}).get(
                "source_objects"
            )
            or ()
        )
    }
    successor_sources = {
        str(row.get("source_url") or ""): dict(row)
        for row in original_result.get("source_objects") or ()
    }
    unchanged_urls = sorted(set(successor_sources) - {corrected_url})
    if not (
        len(unchanged_urls) == 4
        and all(
            predecessor_sources[url].get("source_object_digest")
            == successor_sources[url].get("source_object_digest")
            for url in unchanged_urls
        )
    ):
        raise RuntimeError(
            "dell_direct_source_compilation_replay_unaffected_source_changed"
        )
    source_delta_body = {
        "schema_version": (
            "fin_ia_s1_dell_direct_source_compilation_delta_receipt_v1_0"
        ),
        "case_key": "DELL",
        "unchanged_source_object_urls": unchanged_urls,
        "corrected_source_url": corrected_url,
        "predecessor_source_id": predecessor_sources[corrected_url]["source_id"],
        "predecessor_source_object_digest": predecessor_sources[corrected_url][
            "source_object_digest"
        ],
        "predecessor_publication_date": predecessor_sources[corrected_url][
            "publication_date"
        ],
        "successor_source_id": corrected_sources[0]["source_id"],
        "successor_source_object_digest": corrected_sources[0][
            "source_object_digest"
        ],
        "successor_publication_date": corrected_date,
        "network_calls": 0,
        "model_calls": 0,
    }
    source_delta = {
        **source_delta_body,
        "receipt_digest": canonical_digest(source_delta_body),
    }

    prepared_from_commit = _head()
    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    replay_plan_path = attempt_root / "effective_replay_plan.json"
    _write_new(replay_plan_path, plan)
    replay_capture_path = attempt_root / "replayed_capture_set.json"
    _write_new(replay_capture_path, replay_capture)
    original_result_path = attempt_root / "original_compilation_result.json"
    _write_new(original_result_path, original_result)
    source_delta_path = attempt_root / "source_object_delta_receipt.json"
    _write_new(source_delta_path, source_delta)

    private_body = {
        "schema_version": (
            "fin_ia_s1_dell_direct_source_compilation_replay_private_result_v1_0"
        ),
        "status": "dell_external_source_ladder_exact_once_complete",
        "execution_mode": "immutable_raw_capture_compilation_replay_zero_network",
        "attempt_id": attempt_id,
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "replay_plan_binding": {
            "ref": _relative(plan_path),
            "sha256": _sha256(plan_path),
            "plan_digest": plan["plan_digest"],
        },
        "plan_binding": {
            "ref": _relative(effective_path),
            "sha256": _sha256(effective_path),
            "plan_digest": effective_plan["plan_digest"],
        },
        "predecessor_binding": {
            "terminal_ref": _relative(predecessor_path),
            "terminal_sha256": _sha256(predecessor_path),
            "terminal_result_digest": predecessor["result_digest"],
            "attempt_id": predecessor["attempt_id"],
        },
        "defect_receipt_binding": {
            "ref": _relative(defect_path),
            "sha256": _sha256(defect_path),
            "receipt_digest": defect["receipt_digest"],
        },
        "source_object_delta_receipt": source_delta,
        "fetch_shortlist": shortlist,
        "original_capture_result": replay_capture,
        "original_compilation_result": original_result,
        "observed_counts": {
            "raw_captures_reused": expected_capture_count,
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "generation_calls": 0,
            "source_objects_recompiled": len(
                original_result.get("source_objects") or ()
            ),
            "candidate_evidence_promotions": 0,
        },
        "authority": deepcopy(dict(plan["authority"])),
    }
    private_result = {
        **private_body,
        "result_digest": canonical_digest(private_body),
    }
    private_result_path = attempt_root / "terminal_result.json"
    _write_new(private_result_path, private_result)

    public_body = {
        "schema_version": (
            "fin_ia_s1_dell_direct_source_compilation_replay_result_v1_0"
        ),
        "status": "dell_direct_source_compilation_replay_complete",
        "case_key": "DELL",
        "research_as_of": str(plan["research_as_of"]),
        "attempt_id": attempt_id,
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "plan_id": plan["plan_id"],
        "plan_digest": plan["plan_digest"],
        "predecessor_attempt_id": predecessor["attempt_id"],
        "predecessor_terminal_result_digest": predecessor["result_digest"],
        "defect_receipt_digest": defect["receipt_digest"],
        "private_terminal_ref": _relative(private_result_path),
        "private_terminal_sha256": _sha256(private_result_path),
        "private_terminal_result_digest": private_result["result_digest"],
        "source_object_delta_receipt": source_delta,
        "observed_counts": deepcopy(private_result["observed_counts"]),
        "original_compilation_summary": deepcopy(
            dict(original_result.get("summary") or {})
        ),
        "route_receipts": deepcopy(
            list(original_result.get("route_receipts") or ())
        ),
        "authority": deepcopy(dict(plan["authority"])),
        "known_boundary": (
            "This attempt reuses five immutable raw response captures and corrects "
            "only the original-source compilation/date adjudication. It performs "
            "zero network, provider, model and generation calls. Recompiled "
            "proposals remain candidate-only until exhaustive CandidateDecision "
            "and Evidence Gate; no gap closure or S1 qualification is authorized."
        ),
    }
    public_result = {
        **public_body,
        "result_digest": canonical_digest(public_body),
    }
    _write_new(public_output, public_result)
    return public_result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Replay Dell direct-source compilation from immutable raw captures "
            "after a publication-date adjudication fix."
        )
    )
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--private-root", type=Path, default=DEFAULT_PRIVATE_ROOT)
    parser.add_argument("--public-output", type=Path, default=DEFAULT_PUBLIC)
    args = parser.parse_args(argv)
    result = run(
        attempt_id=str(args.attempt_id),
        plan_path=args.plan,
        private_root=args.private_root,
        public_output=args.public_output,
    )
    print(json.dumps(result["observed_counts"], ensure_ascii=False, indent=2))
    print(
        json.dumps(
            result["source_object_delta_receipt"],
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"result_digest={result['result_digest']}")
    print(f"output={args.public_output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
