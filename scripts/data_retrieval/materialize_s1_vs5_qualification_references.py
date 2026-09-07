from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from retrieval.evaluation_assets import (  # noqa: E402
    EVALUATION_REFERENCE_SCHEMA_VERSION,
    EvaluationInput,
    EvaluationReference,
    load_qualification_preregistration,
)


EVIDENCE_ROLE_VOCABULARY = frozenset({"direct", "counter", "bridge", "context"})
EVIDENCE_FACET_VOCABULARY = frozenset(
    {
        "direct_support",
        "counterevidence",
        "numeric_bridge",
        "alternative_explanation",
        "independent_readthrough",
    }
)


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"jsonl_object_required:{path.name}:{line_number}")
            rows.append(value)
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n"
            )
    temporary.replace(path)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _load_inputs(runtime_result: Mapping[str, Any]) -> list[EvaluationInput]:
    rows: list[EvaluationInput] = []
    for binding in runtime_result.get("outputs") or ():
        rows.extend(
            EvaluationInput.model_validate(value)
            for value in _read_jsonl(_resolve(str(binding["ref"])))
        )
    return rows


def _candidate_binding(
    *,
    raw: Mapping[str, Any],
    objects_by_id: Mapping[str, Mapping[str, Any]],
    case_key: str,
    required_roles: set[str],
    required_facets: set[str],
) -> dict[str, Any]:
    object_id = str(raw.get("compiled_object_id") or "")
    if object_id not in objects_by_id:
        raise ValueError(f"qualification_reference_object_missing:{object_id}")
    value = objects_by_id[object_id]
    base = value["base_object_view"]
    if str(base.get("ticker") or "").upper() != case_key.upper():
        raise ValueError(f"qualification_reference_cross_case:{case_key}:{object_id}")
    roles = tuple(dict.fromkeys(str(item) for item in raw.get("roles") or ()))
    facets = tuple(dict.fromkeys(str(item) for item in raw.get("facets") or ()))
    if not roles or not set(roles).issubset(EVIDENCE_ROLE_VOCABULARY):
        raise ValueError(f"qualification_reference_role_invalid:{object_id}")
    if not set(roles).intersection(required_roles):
        raise ValueError(f"qualification_reference_role_unresponsive:{object_id}")
    if not facets or not set(facets).issubset(EVIDENCE_FACET_VOCABULARY):
        raise ValueError(f"qualification_reference_facet_invalid:{object_id}")
    if not set(facets).intersection(required_facets):
        raise ValueError(f"qualification_reference_facet_unresponsive:{object_id}")
    model_text = str(value.get("model_text") or "")
    if not model_text.strip():
        raise ValueError(f"qualification_reference_text_missing:{object_id}")
    return {
        "compiled_object_id": object_id,
        "roles": roles,
        "facets": facets,
        "object_kind": value["object_kind"],
        "source_record_id": base.get("source_record_id"),
        "source_type": base.get("source_type"),
        "fiscal_year": base.get("fiscal_year"),
        "publication_date": base.get("publication_date"),
        "source_excerpt_sha256": _text_digest(model_text),
        "review_note_zh": str(raw.get("review_note_zh") or "").strip(),
        "candidate_not_evidence": True,
        "numeric_authority": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize split-safe evaluator-only references for S1 VS5."
    )
    parser.add_argument(
        "--preregistration",
        default="eval_sets/fin_0_1_3_s1/qualification_preregistration_v1_0.json",
    )
    parser.add_argument(
        "--runtime-result",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_runtime_inputs_result_v1_0.json",
    )
    parser.add_argument(
        "--compiled-result",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_compiled_objects_result_v1_0.json",
    )
    parser.add_argument(
        "--review-decisions",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_source_review_v1_0.json",
    )
    parser.add_argument(
        "--output-root",
        default="eval_sets/fin_0_1_3_s1/references",
    )
    parser.add_argument(
        "--public-result",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_references_result_v1_0.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prereg_path = _resolve(args.preregistration)
    runtime_result_path = _resolve(args.runtime_result)
    compiled_result_path = _resolve(args.compiled_result)
    decisions_path = _resolve(args.review_decisions)
    prereg = load_qualification_preregistration(prereg_path)
    runtime_result = _read_json(runtime_result_path)
    inputs = _load_inputs(runtime_result)
    inputs_by_id = {row.example_id: row for row in inputs}
    compiled_result = _read_json(compiled_result_path)
    object_path = _resolve(str(compiled_result["output_binding"]["objects_ref"]))
    objects = _read_jsonl(object_path)
    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    decisions = _read_json(decisions_path)
    review_rows = decisions.get("proposition_reviews") or ()
    if len(review_rows) != len(inputs):
        raise ValueError("qualification_reference_review_count_invalid")
    review_by_id = {str(row["example_id"]): row for row in review_rows}
    if len(review_by_id) != len(review_rows) or set(review_by_id) != set(inputs_by_id):
        raise ValueError("qualification_reference_review_join_invalid")

    proposition_specs = {
        f"VS5::{case.case_key}::{proposition.proposition_id}": proposition
        for case in prereg.cases
        for proposition in case.propositions
    }
    references_by_split: dict[str, list[dict[str, Any]]] = {}
    finding_counts: dict[str, int] = {}
    missing_role_count = 0
    missing_facet_count = 0
    for example_id, row in inputs_by_id.items():
        review = review_by_id[example_id]
        proposition = proposition_specs[example_id]
        required_roles = set(proposition.required_roles)
        required_facets = set(proposition.required_facets)
        evidence_request = row.runtime_input.get("evidence_request") or {}
        case_key = str(evidence_request.get("case_key") or "").strip()
        if not case_key:
            raise ValueError(f"qualification_reference_case_key_missing:{example_id}")
        positives = [
            _candidate_binding(
                raw=value,
                objects_by_id=objects_by_id,
                case_key=case_key,
                required_roles=required_roles,
                required_facets=required_facets,
            )
            for value in review.get("positive_candidates") or ()
        ]
        if len({value["compiled_object_id"] for value in positives}) != len(positives):
            raise ValueError(f"qualification_reference_positive_duplicate:{example_id}")
        covered_roles = sorted({role for value in positives for role in value["roles"]})
        covered_facets = sorted({facet for value in positives for facet in value["facets"]})
        missing_roles = sorted(required_roles - set(covered_roles))
        missing_facets = sorted(required_facets - set(covered_facets))
        missing_role_count += len(missing_roles)
        missing_facet_count += len(missing_facets)
        findings = []
        for finding in review.get("coverage_findings") or ():
            code = str(finding.get("failure_class") or "")
            if not code:
                raise ValueError(f"qualification_reference_finding_invalid:{example_id}")
            finding_counts[code] = finding_counts.get(code, 0) + 1
            findings.append(dict(finding))
        expected = {
            "case_key": case_key,
            "proposition_id": proposition.proposition_id,
            "positive_candidates": positives,
            "positive_object_ids": [value["compiled_object_id"] for value in positives],
            "required_roles": sorted(required_roles),
            "covered_roles": covered_roles,
            "missing_required_roles": missing_roles,
            "required_facets": sorted(required_facets),
            "covered_facets": covered_facets,
            "missing_required_facets": missing_facets,
            "coverage_findings": findings,
            "authority_boundary": {
                "candidate_is_evidence": False,
                "metric_row_is_numeric_fact": False,
                "runtime_may_read_reference": False,
                "owner_or_qualified_human_review_pending": True,
                "public_information_gap_declared": False,
            },
        }
        reference = EvaluationReference(
            schema_version=EVALUATION_REFERENCE_SCHEMA_VERSION,
            example_id=example_id,
            split=row.split,
            label_type="ordered_candidates",
            expected_outcome=expected,
            hard_gate=True,
            rationale_zh=str(review["rationale_zh"]),
            adjudication_authority=str(decisions["adjudication_authority"]),
            review_state="qualification_blinded",
        )
        references_by_split.setdefault(row.split, []).append(
            reference.model_dump(mode="json")
        )

    outputs = []
    output_root = _resolve(args.output_root)
    for split, rows in sorted(references_by_split.items()):
        rows.sort(key=lambda value: value["example_id"])
        path = output_root / split / "vs5_qualification_references_v1_0.jsonl"
        _write_jsonl(path, rows)
        outputs.append(
            {
                "split": split,
                "ref": _relative(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
                "example_count": len(rows),
            }
        )
    public = {
        "schema_version": "fin_ia_s1_vs5_qualification_references_result_v1_0",
        "status": "source_bound_evaluator_references_materialized_owner_review_pending",
        "recorded_at": "2026-08-18",
        "bound_inputs": {
            "preregistration_ref": _relative(prereg_path),
            "preregistration_sha256": _sha256(prereg_path),
            "runtime_result_ref": _relative(runtime_result_path),
            "runtime_result_sha256": _sha256(runtime_result_path),
            "compiled_objects_ref": _relative(object_path),
            "compiled_objects_sha256": _sha256(object_path),
            "review_decisions_ref": _relative(decisions_path),
            "review_decisions_sha256": _sha256(decisions_path),
        },
        "outputs": outputs,
        "summary": {
            "example_count": len(inputs),
            "positive_binding_count": sum(
                len(row["expected_outcome"]["positive_candidates"])
                for rows in references_by_split.values()
                for row in rows
            ),
            "missing_required_role_count": missing_role_count,
            "missing_required_facet_count": missing_facet_count,
            "coverage_finding_counts": dict(sorted(finding_counts.items())),
            "model_calls": 0,
            "learned_vector_calls": 0,
            "network_calls": 0,
        },
        "authority": {
            "runtime_visible": False,
            "candidate_is_evidence": False,
            "numeric_fact_authority": False,
            "owner_or_qualified_human_review_pending": True,
            "qualification_execution_authorized": False,
        },
    }
    _write_json(_resolve(args.public_result), public)
    print(json.dumps(public["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
