from __future__ import annotations

import argparse
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
from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.reviewed_public_object_compiler import (  # noqa: E402
    compile_reviewed_public_source_objects,
)
from retrieval.route_compiler import (  # noqa: E402
    load_query_object_fact_route_policy,
)


DEFAULT_KERNEL = Path(
    "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_5.json"
)
DEFAULT_ROUTE_POLICY = Path(
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_5.json"
)
DEFAULT_BASE_OBJECTS = Path(
    "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/"
    "v7/objects.jsonl"
)
DEFAULT_BASE_SOURCE_RECORDS = Path(
    "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/"
    "v4/records.jsonl"
)
DEFAULT_SOURCE_RECORDS_OUTPUT = Path(
    "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/"
    "v5/records.jsonl"
)
DEFAULT_PACK = Path(
    "data/workbench_private/fin_0_1_3_s1_dell_direct_source_evidence/"
    "r4/successor/pack.json"
)
DEFAULT_OUTPUT_DIR = Path(
    "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/v8"
)
DEFAULT_RESULT_OUTPUT = Path(
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_reviewed_public_web_incremental_successor_result_v1_0.json"
)


EXPECTED_MISSING_PAGE_IDS = frozenset(
    {"PUBLIC::DELL-EXT::2184F13EB685F627C757"}
)


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"jsonl_object_required:{path}:{line_number}")
            rows.append(value)
    return rows


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
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


def _repo_ref(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _count_by(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _source_page_id(row: Mapping[str, Any]) -> str:
    metadata = row.get("metadata") or {}
    if metadata.get("object_level") == "source_page_lineage_parent":
        return str(row.get("evidence_id") or "")
    return str(metadata.get("source_page_record_id") or "")


def materialize(
    *,
    kernel_path: Path,
    route_policy_path: Path,
    base_objects_path: Path,
    base_source_records_path: Path,
    source_records_output_path: Path,
    evidence_pack_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    kernel = load_financial_research_kernel(_read_json(kernel_path))
    route_policy = load_query_object_fact_route_policy(
        _read_json(route_policy_path), kernel
    )
    evidence_pack = _read_json(evidence_pack_path)
    compiled = compile_reviewed_public_source_objects(
        evidence_pack=evidence_pack,
        route_policy=route_policy,
        allowed_source_types=("PUBLIC_WEB",),
    )

    base_source_records = _read_jsonl(base_source_records_path)
    base_source_ids = [
        str(row.get("evidence_id") or "") for row in base_source_records
    ]
    if (
        not all(base_source_ids)
        or len(base_source_ids) != len(set(base_source_ids))
    ):
        raise ValueError("public_web_incremental_base_source_identity_invalid")
    observed_missing_page_ids = (
        set(compiled.summary["source_page_record_ids"]) - set(base_source_ids)
    )
    if observed_missing_page_ids != set(EXPECTED_MISSING_PAGE_IDS):
        raise ValueError(
            "public_web_incremental_missing_page_set_drift:"
            + ",".join(sorted(observed_missing_page_ids))
        )

    appended_source_records = [
        dict(row)
        for row in compiled.source_records
        if _source_page_id(row) in EXPECTED_MISSING_PAGE_IDS
    ]
    appended_source_ids = [
        str(row.get("evidence_id") or "") for row in appended_source_records
    ]
    if (
        len(appended_source_records) != 2
        or len(appended_source_ids) != len(set(appended_source_ids))
        or set(base_source_ids).intersection(appended_source_ids)
        or {row.get("source_type") for row in appended_source_records}
        != {"PUBLIC_WEB"}
        or sum(
            (row.get("metadata") or {}).get("object_level")
            == "source_page_lineage_parent"
            for row in appended_source_records
        )
        != 1
    ):
        raise ValueError("public_web_incremental_source_append_invalid")
    source_records = [*base_source_records, *appended_source_records]
    _write_jsonl(source_records_output_path, source_records)

    base_objects = _read_jsonl(base_objects_path)
    base_object_ids = [
        str(row.get("compiled_object_id") or "") for row in base_objects
    ]
    if (
        not all(base_object_ids)
        or len(base_object_ids) != len(set(base_object_ids))
    ):
        raise ValueError("public_web_incremental_base_object_identity_invalid")
    appended_objects = [
        dict(row)
        for row in compiled.objects
        if str(
            (row.get("base_object_view", {}).get("source_lineage") or {}).get(
                "source_page_record_id"
            )
            or ""
        )
        in EXPECTED_MISSING_PAGE_IDS
    ]
    appended_object_ids = [
        str(row.get("compiled_object_id") or "") for row in appended_objects
    ]
    if (
        not appended_objects
        or not all(appended_object_ids)
        or len(appended_object_ids) != len(set(appended_object_ids))
        or set(base_object_ids).intersection(appended_object_ids)
        or {
            str(row.get("base_object_view", {}).get("source_type") or "")
            for row in appended_objects
        }
        != {"PUBLIC_WEB"}
    ):
        raise ValueError("public_web_incremental_object_append_invalid")
    objects = [*base_objects, *appended_objects]
    objects_path = output_dir / "objects.jsonl"
    diagnostics_path = output_dir / "diagnostics.jsonl"
    _write_jsonl(objects_path, objects)
    selected_material_refs = {
        str((row.get("metadata") or {}).get("material_ref") or "")
        for row in appended_source_records
    }
    _write_jsonl(
        diagnostics_path,
        [
            dict(row)
            for row in compiled.diagnostics
            if str(row.get("material_ref") or "") in selected_material_refs
        ],
    )

    unsigned = {
        "schema_version": (
            "fin_ia_s1_reviewed_public_web_incremental_successor_result_v1_0"
        ),
        "status": (
            "missing_reviewed_public_web_source_compiled_into_candidate_successor"
        ),
        "recorded_at": "2026-08-25",
        "inputs": {
            "kernel_ref": _repo_ref(kernel_path),
            "kernel_sha256": _sha256(kernel_path),
            "route_policy_ref": _repo_ref(route_policy_path),
            "route_policy_sha256": _sha256(route_policy_path),
            "base_objects_ref": _repo_ref(base_objects_path),
            "base_objects_sha256": _sha256(base_objects_path),
            "base_source_records_ref": _repo_ref(base_source_records_path),
            "base_source_records_sha256": _sha256(base_source_records_path),
            "evidence_pack_ref": _repo_ref(evidence_pack_path),
            "evidence_pack_sha256": _sha256(evidence_pack_path),
            "evidence_pack_payload_digest": evidence_pack.get(
                "pack_payload_digest"
            ),
            "records": {
                "ref": _repo_ref(source_records_output_path),
                "sha256": _sha256(source_records_output_path),
            },
        },
        "outputs": {
            "objects_ref": _repo_ref(objects_path),
            "objects_sha256": _sha256(objects_path),
            "source_records_ref": _repo_ref(source_records_output_path),
            "source_records_sha256": _sha256(source_records_output_path),
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
            "source_record_count": len(source_records),
            "compiled_object_count": len(objects),
            "compiled_object_kind_counts": _count_by(objects, "object_kind"),
        },
        "summary": {
            "base_source_record_count": len(base_source_records),
            "appended_canonical_source_record_count": len(
                appended_source_records
            ),
            "successor_source_record_count": len(source_records),
            "base_object_count": len(base_objects),
            "appended_object_count": len(appended_objects),
            "successor_object_count": len(objects),
            "appended_page_ids": sorted(EXPECTED_MISSING_PAGE_IDS),
            "appended_slice_ids": sorted(
                value
                for value in appended_source_ids
                if value not in EXPECTED_MISSING_PAGE_IDS
            ),
        },
        "acceptance": {
            "base_source_records_retained_exactly": source_records[
                : len(base_source_records)
            ]
            == base_source_records,
            "base_objects_retained_exactly": objects[: len(base_objects)]
            == base_objects,
            "missing_reviewed_public_web_page_and_slice_internalized": True,
            "missing_reviewed_public_web_source_indexed": True,
            "external_owner_identity_preserved": True,
        },
        "authority": {
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
            "reviewed_relevance_labels_copied_into_candidate_index": False,
            "exact_lineage_join_required_for_evidence_reselection": True,
            "public_relationship_does_not_prove_private_allocation": True,
            "network_calls": 0,
            "model_calls": 0,
        },
        "known_boundary": (
            "This successor appends only the one writer-citable NVIDIA public-web "
            "page introduced by the current DELL R4 Pack and its exact reviewed "
            "slice. It fixes source/object synchronization without changing the "
            "Pack, copying relevance labels, granting Evidence or NumericFact "
            "authority, or treating a public collaboration as private allocation."
        ),
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Append only reviewed PUBLIC_WEB pages that are missing from the "
            "immutable current source/object prefix."
        )
    )
    parser.add_argument("--kernel", type=Path, default=DEFAULT_KERNEL)
    parser.add_argument(
        "--route-policy", type=Path, default=DEFAULT_ROUTE_POLICY
    )
    parser.add_argument("--base-objects", type=Path, default=DEFAULT_BASE_OBJECTS)
    parser.add_argument(
        "--base-source-records",
        type=Path,
        default=DEFAULT_BASE_SOURCE_RECORDS,
    )
    parser.add_argument(
        "--source-records-output",
        type=Path,
        default=DEFAULT_SOURCE_RECORDS_OUTPUT,
    )
    parser.add_argument("--evidence-pack", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--result-output", type=Path, default=DEFAULT_RESULT_OUTPUT
    )
    args = parser.parse_args()

    result_path = _resolve(args.result_output)
    if result_path.exists():
        raise FileExistsError(
            f"public_web_incremental_result_exists:{result_path}"
        )
    result = materialize(
        kernel_path=_resolve(args.kernel),
        route_policy_path=_resolve(args.route_policy),
        base_objects_path=_resolve(args.base_objects),
        base_source_records_path=_resolve(args.base_source_records),
        source_records_output_path=_resolve(args.source_records_output),
        evidence_pack_path=_resolve(args.evidence_pack),
        output_dir=_resolve(args.output_dir),
    )
    _write_json(result_path, result)
    print(result_path)
    print(json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
