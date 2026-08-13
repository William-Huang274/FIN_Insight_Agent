from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ingestion.official_pdf import (  # noqa: E402
    parse_captured_official_pdf,
    public_parsed_official_pdf_projection,
)
from retrieval.official_pdf_objects import compile_official_pdf_document  # noqa: E402
from sec_agent.research.official_pdf_evidence import (  # noqa: E402
    build_reviewed_pack_successor,
    combine_official_pdf_evidence_results,
    evaluate_official_pdf_evidence,
)
from sec_agent.research.reviewed_evidence_pack import (  # noqa: E402
    canonical_bytes,
    canonical_digest,
    validate_reviewed_evidence_pack,
)


AUTHORITY_SCHEMA_VERSION = (
    "fin_ia_s1d_official_pdf_successor_execution_authority_v1_0"
)
RESULT_SCHEMA_VERSION = "fin_ia_s1d_official_pdf_successor_result_v1_0"
class OfficialPdfSuccessorRunnerError(RuntimeError):
    """The zero-network PDF successor execution was not exactly authorized."""


def validate_authority(
    payload: Mapping[str, Any],
    *,
    repository_root: Path,
) -> dict[str, Any]:
    value = dict(payload)
    if not (
        value.get("schema_version") == AUTHORITY_SCHEMA_VERSION
        and value.get("status")
        == "fresh_zero_network_official_pdf_successor_authorized"
    ):
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_authority_status_invalid"
        )
    clean = value.get("clean_implementation")
    bound = value.get("bound_inputs")
    budget = value.get("execution_budget")
    output = value.get("output_contract")
    source = value.get("source_contract")
    if not all(
        isinstance(row, Mapping)
        for row in (clean, bound, budget, output, source)
    ):
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_authority_shape_invalid"
        )
    assert isinstance(clean, Mapping)
    assert isinstance(bound, Mapping)
    assert isinstance(budget, Mapping)
    assert isinstance(output, Mapping)
    assert isinstance(source, Mapping)
    if not (
        clean.get("working_tree_required_clean_before_execution") is True
        and clean.get("pushed_head_required") is True
        and int(
            budget.get("network_calls")
            if budget.get("network_calls") is not None
            else -1
        )
        == 0
        and int(
            budget.get("model_calls")
            if budget.get("model_calls") is not None
            else -1
        )
        == 0
        and int(
            budget.get("retries")
            if budget.get("retries") is not None
            else -1
        )
        == 0
        and budget.get("current_product_pointer_mutation") == "forbidden"
        and budget.get("raw_source_publication") == "forbidden"
        and str(source.get("route_id") or "")
        and str(source.get("ticker") or "")
        and str(source.get("consumer_case_key") or "")
        and str(source.get("company") or "")
        and source.get("source_type") == "EARNINGS_CALL_TRANSCRIPT"
        and str(source.get("source_tier") or "")
        and str(source.get("publication_date") or "")
        and str(source.get("period_end") or "")
        and isinstance(source.get("fiscal_year"), int)
        and str(source.get("source_url") or "")
        and source.get("redistributable") is False
        and str(source.get("license_scope") or "")
    ):
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_authority_budget_or_source_invalid"
        )

    input_pairs = [
        ("attempt_manifest_ref", "attempt_manifest_sha256"),
        ("predecessor_pack_ref", "predecessor_pack_sha256"),
        ("s2_result_ref", "s2_result_sha256"),
        ("runner_ref", "runner_sha256"),
    ]
    if bound.get("source_intake_result_ref") is not None:
        input_pairs.append(
            ("source_intake_result_ref", "source_intake_result_sha256")
        )
    for ref_key, digest_key in input_pairs:
        path = _safe_repository_path(
            repository_root, str(bound.get(ref_key) or "")
        )
        _assert_digest(path, str(bound.get(digest_key) or ""))
    policy_bindings = _policy_bindings(bound)
    for binding in policy_bindings:
        path = _safe_repository_path(repository_root, str(binding["ref"]))
        _assert_digest(path, str(binding["sha256"]))
    raw_pdf_sha256 = str(bound.get("raw_pdf_sha256") or "")
    if (
        len(raw_pdf_sha256) != 64
        or raw_pdf_sha256 == "0" * 64
        or any(
            character not in "0123456789abcdef"
            for character in raw_pdf_sha256
        )
    ):
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_raw_digest_invalid"
        )

    successor_contract = value.get("successor_contract")
    if successor_contract is not None and not (
        isinstance(successor_contract, Mapping)
        and isinstance(successor_contract.get("gap_ids_satisfied"), list)
        and all(
            str(gap_id).strip()
            for gap_id in successor_contract["gap_ids_satisfied"]
        )
    ):
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_contract_invalid"
        )
    if not (
        str(output.get("private_output_root_ref") or "")
        and str(output.get("public_result_ref") or "")
        and str(output.get("result_id") or "")
    ):
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_output_contract_invalid"
        )

    private_root = _safe_repository_path(
        repository_root, str(output.get("private_output_root_ref") or "")
    )
    public_result = _safe_repository_path(
        repository_root, str(output.get("public_result_ref") or "")
    )
    if private_root.exists() or public_result.exists():
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_output_already_exists"
        )
    return value


def assert_repository_state(
    authority: Mapping[str, Any],
    *,
    repository_root: Path,
) -> None:
    clean = authority["clean_implementation"]
    branch = _git(repository_root, "branch", "--show-current")
    if branch != str(clean["branch"]):
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_repository_branch_mismatch"
        )
    implementation = str(clean["git_commit"])
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, "HEAD"],
        cwd=repository_root,
        capture_output=True,
        check=False,
        text=True,
    )
    if ancestor.returncode != 0:
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_implementation_not_ancestor"
        )
    if _git(repository_root, "status", "--porcelain"):
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_repository_not_clean"
        )
    if _git(repository_root, "rev-parse", "HEAD") != _git(
        repository_root, "rev-parse", "@{upstream}"
    ):
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_head_not_pushed"
        )


def execute(
    authority: Mapping[str, Any],
    *,
    authority_path: Path,
    repository_root: Path,
) -> dict[str, Any]:
    bound = authority["bound_inputs"]
    output = authority["output_contract"]
    source_contract = authority["source_contract"]
    if bound.get("source_intake_result_ref") is not None:
        _validate_source_result_assertions(
            _read_json(repository_root / str(bound["source_intake_result_ref"])),
            list(authority.get("source_result_assertions") or ()),
            source_route_id=str(source_contract["route_id"]),
            raw_pdf_sha256=str(bound["raw_pdf_sha256"]),
        )

    attempt = _read_json(repository_root / str(bound["attempt_manifest_ref"]))
    if (
        attempt.get("route_id") != source_contract["route_id"]
        or attempt.get("raw_object_sha256") != bound["raw_pdf_sha256"]
    ):
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_attempt_identity_invalid"
        )
    parsed = parse_captured_official_pdf(
        attempt,
        private_source_intake_root=(
            repository_root / "data" / "workbench_private" / "source_intake"
        ),
    )
    parsed_bytes = canonical_bytes(parsed)
    parsed_sha256 = hashlib.sha256(parsed_bytes).hexdigest()

    parent, children = compile_official_pdf_document(
        parsed,
        source_spec=source_contract,
        parsed_ref="parsed_document.json",
        parsed_sha256=parsed_sha256,
    )
    policy_results = [
        evaluate_official_pdf_evidence(
            parent=parent,
            children=children,
            policy=_read_json(repository_root / str(binding["ref"])),
            research_as_of=str(authority["research_as_of"]),
        )
        for binding in _policy_bindings(bound)
    ]
    if any(
        result.get("status") != "official_pdf_evidence_gate_passed"
        for result in policy_results
    ):
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_evidence_gate_failed"
        )
    evidence_result = (
        policy_results[0]
        if len(policy_results) == 1
        else combine_official_pdf_evidence_results(policy_results)
    )

    predecessor = _read_json(
        repository_root / str(bound["predecessor_pack_ref"])
    )
    validate_reviewed_evidence_pack(predecessor)
    s2 = _validate_s2_dependency(
        _read_json(repository_root / str(bound["s2_result_ref"])),
        repository_root=repository_root,
    )
    if any(
        row.get("object_type") == "metric" or row.get("structured_metric")
        for row in evidence_result["accepted_evidence_items"]
    ):
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_numeric_authority_forbidden"
        )

    lineage = {
        "schema_version": "fin_ia_s1d_official_pdf_successor_lineage_v1_0",
        "authority_ref": authority_path.relative_to(repository_root).as_posix(),
        "source_attempt_id": attempt["attempt_id"],
        "raw_pdf_sha256": bound["raw_pdf_sha256"],
        "parsed_document_sha256": parsed_sha256,
        "evidence_gate_result_digest": evidence_result["result_digest"],
        "evidence_gate_policy_ids": [
            str(result["policy_id"]) for result in policy_results
        ],
        "predecessor_pack_payload_digest": predecessor["pack_payload_digest"],
        "s2_result_digest": s2["result_digest"],
        "network_calls": 0,
        "model_calls": 0,
        "current_product_pointer_mutated": False,
    }
    successor = build_reviewed_pack_successor(
        predecessor=predecessor,
        evidence_result=evidence_result,
        gap_ids_satisfied=list(
            (authority.get("successor_contract") or {}).get(
                "gap_ids_satisfied", []
            )
        ),
        successor_lineage=lineage,
    )
    validate_reviewed_evidence_pack(successor)

    private_root = repository_root / str(output["private_output_root_ref"])
    private_root.mkdir(parents=True, exist_ok=False)
    _write_exclusive(private_root / "parsed_document.json", parsed)
    _write_exclusive(private_root / "document_parent.json", parent)
    _write_jsonl_exclusive(private_root / "retrieval_children.jsonl", children)
    for index, result in enumerate(policy_results, start=1):
        _write_exclusive(
            private_root / f"evidence_gate_result_{index:02d}.json", result
        )
    _write_exclusive(
        private_root / "evidence_gate_bundle_result.json", evidence_result
    )
    pack_digest = canonical_digest(successor)
    pack_relative = (
        PurePosixPath("objects")
        / "fin-0.1.3"
        / str(output.get("object_family") or "s1d-official-pdf-successor")
        / str(source_contract["consumer_case_key"]).lower()
        / "v1"
        / pack_digest[:2]
        / pack_digest[2:4]
        / f"{pack_digest}.json"
    )
    pack_path = private_root.joinpath(*pack_relative.parts)
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    _write_exclusive(pack_path, successor)

    before_counts = dict(predecessor["observed_counts"])
    after_counts = dict(successor["observed_counts"])
    public_unsigned = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "result_id": str(output["result_id"]),
        "recorded_at": str(authority["recorded_at"]),
        "status": str(
            output.get("result_status")
            or "official_pdf_successor_candidate_ready_current_pointer_unchanged"
        ),
        "authority_ref": authority_path.relative_to(repository_root).as_posix(),
        "source": {
            "route_id": source_contract["route_id"],
            "evidence_owner_ticker": source_contract["ticker"],
            "consumer_case_key": source_contract["consumer_case_key"],
            "raw_pdf_sha256": bound["raw_pdf_sha256"],
            "page_count": parsed["page_count"],
            "nonempty_page_count": parsed["nonempty_page_count"],
            "parsed_document_sha256": parsed_sha256,
            "promotion_status": str(
                output.get("promotion_status")
                or "bounded_official_pdf_evidence_accepted"
            ),
        },
        "evidence_gate": {
            "result_digest": evidence_result["result_digest"],
            "policy_ids": [
                str(result["policy_id"]) for result in policy_results
            ],
            "accepted_items": len(evidence_result["accepted_evidence_items"]),
            "accepted_page_numbers": sorted(
                int(row["page_number"])
                for row in evidence_result["source_materials"]
            ),
            "slot_ids": sorted(
                {
                    str(binding.get("slot_id") or "")
                    for item in evidence_result["accepted_evidence_items"]
                    for binding in item.get("slot_bindings") or ()
                }
            ),
            "facet_ids": sorted(
                {
                    str(facet)
                    for item in evidence_result["accepted_evidence_items"]
                    for binding in item.get("slot_bindings") or ()
                    for facet in binding.get("facet_ids") or ()
                }
            ),
            "gaps_closed": list(
                (authority.get("successor_contract") or {}).get(
                    "gap_ids_satisfied", []
                )
            ),
            "causal_attribution_authorized": False,
            "numeric_authority_granted": False,
        },
        "successor_pack": {
            "private_object_key": pack_relative.as_posix(),
            "artifact_sha256": _file_sha256(pack_path),
            "pack_payload_digest": successor["pack_payload_digest"],
            "evidence_before_after": [
                before_counts["accepted_evidence_items"],
                after_counts["accepted_evidence_items"],
            ],
            "gaps_before_after": [
                before_counts["residual_gaps"],
                after_counts["residual_gaps"],
            ],
            "current_product_pointer_mutated": False,
        },
        "s2_dependency_regression": {
            "status": "unchanged_pass",
            "result_digest": s2["result_digest"],
            "sqlite_sha256": s2["storage"]["sqlite_sha256"],
            "observations": s2["counts"]["observations"],
            "numeric_fact_authority_changed": False,
            "transcript_numeric_authority": False,
        },
        "remaining_boundaries": dict(
            authority.get("remaining_boundaries") or {}
        ),
        "execution": {
            "network_calls": 0,
            "model_calls": 0,
            "retries": 0,
            "raw_source_published": False,
        },
    }
    public_result = {
        **public_unsigned,
        "result_digest": canonical_digest(public_unsigned),
    }
    _write_exclusive(
        repository_root / str(output["public_result_ref"]), public_result
    )
    return public_result


def _validate_s2_dependency(
    result: Mapping[str, Any],
    *,
    repository_root: Path,
) -> dict[str, Any]:
    value = dict(result)
    storage = value.get("storage")
    counts = value.get("counts")
    if not (
        value.get("schema_version")
        == "fin_ia_s2_company_financial_fact_mart_build_result_v1_0"
        and value.get("status") == "s2_company_financial_fact_mart_engineering_pass"
        and isinstance(storage, Mapping)
        and isinstance(counts, Mapping)
        and int(counts.get("observations") or 0) == 1319
        and int(counts.get("tickers") or 0) == 3
        and int(counts.get("metrics") or 0) == 12
    ):
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_s2_result_invalid"
        )
    sqlite_path = _safe_repository_path(
        repository_root, str(storage.get("sqlite_ref") or "")
    )
    if _file_sha256(sqlite_path) != str(storage.get("sqlite_sha256") or ""):
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_s2_sqlite_digest_mismatch"
        )
    return value


def _policy_bindings(bound: Mapping[str, Any]) -> list[dict[str, str]]:
    raw = bound.get("evidence_gate_policies")
    if raw is None:
        raw = [
            {
                "ref": bound.get("evidence_gate_policy_ref"),
                "sha256": bound.get("evidence_gate_policy_sha256"),
            }
        ]
    if not isinstance(raw, list) or not raw:
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_policy_bindings_invalid"
        )
    bindings: list[dict[str, str]] = []
    for row in raw:
        if not isinstance(row, Mapping):
            raise OfficialPdfSuccessorRunnerError(
                "official_pdf_successor_policy_bindings_invalid"
            )
        ref = str(row.get("ref") or "")
        digest = str(row.get("sha256") or "")
        if not ref or len(digest) != 64:
            raise OfficialPdfSuccessorRunnerError(
                "official_pdf_successor_policy_bindings_invalid"
            )
        bindings.append({"ref": ref, "sha256": digest})
    if len({binding["ref"] for binding in bindings}) != len(bindings):
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_policy_bindings_invalid"
        )
    return bindings


def _validate_source_result_assertions(
    source_result: Mapping[str, Any],
    assertions: list[Mapping[str, Any]],
    *,
    source_route_id: str,
    raw_pdf_sha256: str,
) -> None:
    if not assertions:
        assertions = [
            {
                "route_id": source_route_id,
                "equals": {
                    "status": "captured_ready_for_parse",
                    "raw_object_sha256": raw_pdf_sha256,
                },
            }
        ]
    route_by_id = {
        str(row.get("route_id") or ""): dict(row)
        for row in source_result.get("route_results") or ()
    }
    for assertion in assertions:
        route = route_by_id.get(str(assertion.get("route_id") or ""))
        expected = dict(assertion.get("equals") or {})
        if not route or not expected or any(
            route.get(key) != value for key, value in expected.items()
        ):
            raise OfficialPdfSuccessorRunnerError(
                "official_pdf_successor_source_result_boundary_invalid"
            )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise OfficialPdfSuccessorRunnerError(
            f"official_pdf_successor_json_object_required:{path.name}"
        )
    return value


def _safe_repository_path(root: Path, value: str) -> Path:
    if not value or Path(value).is_absolute():
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_path_invalid"
        )
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_path_invalid"
        ) from exc
    return path


def _assert_digest(path: Path, expected: str) -> None:
    if len(expected) != 64 or not path.is_file() or _file_sha256(path) != expected:
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_input_digest_mismatch"
        )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(body)
    except FileExistsError as exc:
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_output_already_exists"
        ) from exc


def _write_jsonl_exclusive(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(
                    json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                )
    except FileExistsError as exc:
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_output_already_exists"
        ) from exc


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise OfficialPdfSuccessorRunnerError(
            "official_pdf_successor_repository_state_unavailable"
        )
    return completed.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run an authorized zero-network official PDF successor."
    )
    parser.add_argument("--authority", type=Path, required=True)
    args = parser.parse_args()
    authority_path = args.authority.resolve()
    authority = validate_authority(
        _read_json(authority_path), repository_root=ROOT
    )
    assert_repository_state(authority, repository_root=ROOT)
    result = execute(
        authority,
        authority_path=authority_path,
        repository_root=ROOT,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
