from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from retrieval.contracts import load_financial_research_kernel  # noqa: E402
from retrieval.object_view_compiler_v2 import (  # noqa: E402
    compile_record_object_views,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.route_compiler import (  # noqa: E402
    load_query_object_fact_route_policy,
)


DEFAULT_KERNEL = Path(
    "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_5.json"
)
DEFAULT_PREDECESSOR_ROUTE_POLICY = Path(
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_5.json"
)
DEFAULT_SUCCESSOR_ROUTE_POLICY = Path(
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_6.json"
)
DEFAULT_SOURCE_RECORDS = Path(
    "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/"
    "v5/records.jsonl"
)
DEFAULT_BASE_OBJECTS = Path(
    "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/"
    "v8/objects.jsonl"
)
DEFAULT_OUTPUT_DIR = Path(
    "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/v9"
)
DEFAULT_RESULT = Path(
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_abbreviation_claim_repair_successor_result_v1_0.json"
)

TARGET_PAGE_ID = "PUBLIC::DELL-EXT::2184F13EB685F627C757"
TARGET_SLICE_ID = (
    TARGET_PAGE_ID + "::SLICE::62BC91E7D73822D5A187"
)
TARGET_SENTENCE = (
    "One of Dell’s U.S. factories can ship thousands of NVIDIA Blackwell "
    "GPUs to customers in a week."
)
EXPECTED_BASE_SOURCE_COUNT = 1888
EXPECTED_BASE_OBJECT_COUNT = 34198


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _repo_ref(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"abbreviation_repair_json_object_required:{path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(
                    "abbreviation_repair_jsonl_object_required:"
                    f"{path}:{line_number}"
                )
            rows.append(value)
    return rows


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        raise FileExistsError(f"abbreviation_repair_temporary_exists:{temporary}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        raise FileExistsError(f"abbreviation_repair_temporary_exists:{temporary}")
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _count_by(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def build_successor_route_policy(
    predecessor: Mapping[str, Any],
) -> dict[str, Any]:
    """Enable only the abbreviation-aware, receipt-bearing claim mode."""

    value = deepcopy(dict(predecessor))
    compiler = dict(value.get("object_compiler") or {})
    compiler.update(
        {
            "claim_segmentation_mode": (
                "sentence_with_wrapped_line_reflow_v2"
            ),
            "claim_overflow_policy": (
                "emit_typed_diagnostic_and_fail_qualification"
            ),
        }
    )
    value["object_compiler"] = compiler
    value["successor_change"] = {
        "change_id": "R39_abbreviation_aware_claim_segmentation",
        "predecessor_ref": _repo_ref(
            _resolve(DEFAULT_PREDECESSOR_ROUTE_POLICY)
        ),
        "historical_v1_segmentation_immutable": True,
        "abbreviation_aware_exact_offset_claims": True,
        "candidate_authority_changed": False,
        "numeric_authority_changed": False,
        "evidence_authority_changed": False,
    }
    return value


def _parent_from_slice(record: Mapping[str, Any]) -> dict[str, Any]:
    metadata = dict(record.get("metadata") or {})
    return {
        "document_id": str(metadata.get("parent_document_id") or ""),
        "ticker": str(record.get("ticker") or ""),
        "company": str(record.get("company") or ""),
        "source_type": str(record.get("source_type") or ""),
        "source_tier": str(record.get("source_tier") or ""),
        "publication_date": str(record.get("publication_date") or ""),
        "period_end": str(record.get("period_end") or ""),
        "fiscal_year": record.get("fiscal_year"),
        "section": str(record.get("section") or ""),
        "subsection": str(record.get("subsection") or ""),
        "source_url": str(record.get("source_url") or ""),
        "source_content_digest": str(
            metadata.get("source_content_digest") or ""
        ),
        "raw_capture_sha256": str(metadata.get("raw_capture_sha256") or ""),
        "license_scope": str(metadata.get("license_scope") or ""),
        "redistributable": metadata.get("redistributable") is True,
    }


def _compile_repair_object(
    *,
    source_rows: Sequence[Mapping[str, Any]],
    base_objects: Sequence[Mapping[str, Any]],
    route_policy: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    by_source_id = {
        str(row.get("evidence_id") or ""): dict(row) for row in source_rows
    }
    if set((TARGET_PAGE_ID, TARGET_SLICE_ID)) - set(by_source_id):
        raise ValueError("abbreviation_repair_bound_source_missing")
    slice_record = by_source_id[TARGET_SLICE_ID]
    raw_text = str(slice_record.get("text") or "")
    if raw_text.count(TARGET_SENTENCE) != 1:
        raise ValueError("abbreviation_repair_target_sentence_drift")
    parent = _parent_from_slice(slice_record)
    compiled, diagnostics = compile_record_object_views(
        record=slice_record,
        parent=parent,
        policy=route_policy,
    )
    matches = [
        dict(row)
        for row in compiled
        if str(row.get("object_kind") or "") == "claim"
        and str(row.get("model_text") or "") == TARGET_SENTENCE
    ]
    if len(matches) != 1:
        raise ValueError("abbreviation_repair_target_object_population_invalid")
    candidate = matches[0]
    base = dict(candidate.get("base_object_view") or {})
    binding = dict(base.get("focus_binding") or {})
    start = int(binding.get("char_start") or -1)
    end = int(binding.get("char_end") or -1)
    if (
        binding.get("mode") != "offset_bound_text"
        or raw_text[start:end] != TARGET_SENTENCE
        or "::claim_offset::" not in str(base.get("object_key") or "")
    ):
        raise ValueError("abbreviation_repair_exact_offset_binding_invalid")

    existing_family = [
        row
        for row in base_objects
        if str(
            (
                (row.get("base_object_view") or {}).get("source_lineage")
                or {}
            ).get("source_page_record_id")
            or ""
        )
        == TARGET_PAGE_ID
    ]
    if not existing_family:
        raise ValueError("abbreviation_repair_existing_family_missing")
    if {
        str((row.get("base_object_view") or {}).get("parent_document_digest") or "")
        for row in existing_family
    } != {str(base.get("parent_document_digest") or "")}:
        raise ValueError("abbreviation_repair_parent_digest_drift")
    if any(
        " ".join(str(row.get("model_text") or "").split()).casefold()
        == " ".join(TARGET_SENTENCE.split()).casefold()
        for row in base_objects
    ):
        raise ValueError("abbreviation_repair_target_already_compiled")

    metadata = dict(slice_record.get("metadata") or {})
    base["source_lineage"] = {
        "source_page_record_id": TARGET_PAGE_ID,
        "source_slice_record_id": TARGET_SLICE_ID,
        "material_ref": str(metadata.get("material_ref") or ""),
        "source_content_digest": str(
            metadata.get("source_content_digest") or ""
        ),
        "source_url": str(metadata.get("source_url") or ""),
        "raw_capture_sha256": str(metadata.get("raw_capture_sha256") or ""),
        "license_scope": str(metadata.get("license_scope") or ""),
        "redistributable": metadata.get("redistributable") is True,
    }
    candidate.update(
        {
            "base_object_view": base,
            "lineage_source_record_ids": [TARGET_PAGE_ID, TARGET_SLICE_ID],
            "duplicate_lineage_count": 0,
        }
    )
    object_id = str(candidate.get("compiled_object_id") or "")
    base_ids = {
        str(row.get("compiled_object_id") or "") for row in base_objects
    }
    if not object_id or object_id in base_ids:
        raise ValueError("abbreviation_repair_object_identity_collision")
    if not (
        candidate.get("candidate_not_evidence") is True
        and candidate.get("evidence_promoted") is False
        and candidate.get("numeric_authority") is False
    ):
        raise ValueError("abbreviation_repair_candidate_authority_invalid")
    return candidate, [dict(row) for row in diagnostics]


def materialize(
    *,
    kernel_path: Path,
    predecessor_route_policy_path: Path,
    successor_route_policy_path: Path,
    source_records_path: Path,
    base_objects_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if len(_read_jsonl(source_records_path)) != EXPECTED_BASE_SOURCE_COUNT:
        raise ValueError("abbreviation_repair_source_population_drift")
    source_rows = _read_jsonl(source_records_path)
    base_objects = _read_jsonl(base_objects_path)
    if len(base_objects) != EXPECTED_BASE_OBJECT_COUNT:
        raise ValueError("abbreviation_repair_object_population_drift")

    kernel = load_financial_research_kernel(_read_json(kernel_path))
    predecessor_policy = _read_json(predecessor_route_policy_path)
    successor_policy = build_successor_route_policy(predecessor_policy)
    route_policy = load_query_object_fact_route_policy(successor_policy, kernel)
    repair_object, diagnostics = _compile_repair_object(
        source_rows=source_rows,
        base_objects=base_objects,
        route_policy=route_policy,
    )
    successor_objects = [*base_objects, repair_object]
    if successor_objects[: len(base_objects)] != base_objects:
        raise ValueError("abbreviation_repair_base_prefix_drift")

    objects_path = output_dir / "objects.jsonl"
    diagnostics_path = output_dir / "diagnostics.jsonl"
    _write_json(successor_route_policy_path, successor_policy)
    _write_jsonl(objects_path, successor_objects)
    _write_jsonl(diagnostics_path, diagnostics)
    unsigned = {
        "schema_version": (
            "fin_ia_s1_abbreviation_claim_repair_successor_result_v1_0"
        ),
        "status": "missing_local_claim_compiled_into_append_only_candidate_successor",
        "recorded_at": "2026-08-26",
        "inputs": {
            "kernel_ref": _repo_ref(kernel_path),
            "kernel_sha256": _sha256(kernel_path),
            "predecessor_route_policy_ref": _repo_ref(
                predecessor_route_policy_path
            ),
            "predecessor_route_policy_sha256": _sha256(
                predecessor_route_policy_path
            ),
            "successor_route_policy_ref": _repo_ref(
                successor_route_policy_path
            ),
            "successor_route_policy_sha256": _sha256(
                successor_route_policy_path
            ),
            "base_objects_ref": _repo_ref(base_objects_path),
            "base_objects_sha256": _sha256(base_objects_path),
            "records": {
                "ref": _repo_ref(source_records_path),
                "sha256": _sha256(source_records_path),
            },
        },
        "outputs": {
            "objects_ref": _repo_ref(objects_path),
            "objects_sha256": _sha256(objects_path),
            "diagnostics_ref": _repo_ref(diagnostics_path),
            "diagnostics_sha256": _sha256(diagnostics_path),
        },
        "output_binding": {
            "objects_ref": _repo_ref(objects_path),
            "objects_sha256": _sha256(objects_path),
            "diagnostics_ref": _repo_ref(diagnostics_path),
            "diagnostics_sha256": _sha256(diagnostics_path),
        },
        "object_compilation_summary": {
            "source_record_count": len(source_rows),
            "compiled_object_count": len(successor_objects),
            "compiled_object_kind_counts": _count_by(
                successor_objects, "object_kind"
            ),
        },
        "summary": {
            "base_source_record_count": len(source_rows),
            "successor_source_record_count": len(source_rows),
            "base_object_count": len(base_objects),
            "appended_object_count": 1,
            "successor_object_count": len(successor_objects),
            "target_page_id": TARGET_PAGE_ID,
            "target_slice_id": TARGET_SLICE_ID,
            "target_sentence_sha256": hashlib.sha256(
                TARGET_SENTENCE.encode("utf-8")
            ).hexdigest(),
            "appended_compiled_object_id": repair_object[
                "compiled_object_id"
            ],
            "appended_char_start": repair_object["base_object_view"][
                "focus_binding"
            ]["char_start"],
            "appended_char_end": repair_object["base_object_view"][
                "focus_binding"
            ]["char_end"],
        },
        "acceptance": {
            "source_records_unchanged": True,
            "base_objects_retained_exactly": True,
            "single_previously_missing_material_claim_internalized": True,
            "abbreviation_aware_exact_offset_binding": True,
            "historical_v8_immutable": True,
        },
        "authority": {
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
            "evidence_promoted": False,
            "gap_closed_by_compilation_alone": False,
            "network_calls": 0,
            "model_calls": 0,
            "provider_calls": 0,
        },
        "known_boundary": (
            "R39 repairs one proved local source-to-object loss caused by the "
            "historical U.S. abbreviation split. It retains the complete v8 "
            "object prefix and unchanged v5 source store, grants no Evidence or "
            "NumericFact authority, and does not by itself prove any external "
            "information boundary or close any research proposition."
        ),
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Append the single source-bound claim lost by abbreviation splitting "
            "without rewriting the immutable current object prefix."
        )
    )
    parser.add_argument("--kernel", type=Path, default=DEFAULT_KERNEL)
    parser.add_argument(
        "--predecessor-route-policy",
        type=Path,
        default=DEFAULT_PREDECESSOR_ROUTE_POLICY,
    )
    parser.add_argument(
        "--successor-route-policy",
        type=Path,
        default=DEFAULT_SUCCESSOR_ROUTE_POLICY,
    )
    parser.add_argument(
        "--source-records", type=Path, default=DEFAULT_SOURCE_RECORDS
    )
    parser.add_argument("--base-objects", type=Path, default=DEFAULT_BASE_OBJECTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--result-output", type=Path, default=DEFAULT_RESULT)
    args = parser.parse_args()

    kernel_path = _resolve(args.kernel)
    predecessor_policy_path = _resolve(args.predecessor_route_policy)
    successor_policy_path = _resolve(args.successor_route_policy)
    source_records_path = _resolve(args.source_records)
    base_objects_path = _resolve(args.base_objects)
    output_dir = _resolve(args.output_dir)
    result_path = _resolve(args.result_output)
    for path in (successor_policy_path, output_dir, result_path):
        if path.exists():
            raise FileExistsError(f"abbreviation_repair_successor_exists:{path}")
    result = materialize(
        kernel_path=kernel_path,
        predecessor_route_policy_path=predecessor_policy_path,
        successor_route_policy_path=successor_policy_path,
        source_records_path=source_records_path,
        base_objects_path=base_objects_path,
        output_dir=output_dir,
    )
    _write_json(result_path, result)
    print(result_path)
    print(json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
