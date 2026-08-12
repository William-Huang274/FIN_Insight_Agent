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
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.contracts import load_evidence_request, load_financial_research_kernel  # noqa: E402
from retrieval.query_atom_shadow import (  # noqa: E402
    QUERY_ATOM_EVAL_SCHEMA_VERSION,
    compile_atom_lane,
    load_query_atoms,
)
from retrieval.query_plan import canonical_digest  # noqa: E402


MANIFEST_SCHEMA_VERSION = "fin_ia_s1c_runtime_query_atom_manifest_v1_0"


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


def _sha256(path: Path, *, normalize_text: bool = False) -> str:
    if normalize_text:
        return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_object_index(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            object_id = str(row.get("compiled_object_id") or "")
            if not object_id or object_id in rows:
                raise ValueError(f"compiled_object_identity_invalid:{line_number}")
            rows[object_id] = row
    if not rows:
        raise ValueError("compiled_object_population_empty")
    return rows


def materialize(
    *,
    manifest_path: Path,
    kernel_path: Path,
    objects_path: Path,
) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    kernel_payload = _read_json(kernel_path)
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError("runtime_query_atom_manifest_schema_invalid")
    kernel = load_financial_research_kernel(kernel_payload)
    objects = _read_object_index(objects_path)
    defaults = manifest.get("request_defaults")
    if not isinstance(defaults, Mapping):
        raise ValueError("runtime_query_atom_defaults_invalid")

    materialized_atoms: list[dict[str, Any]] = []
    for raw in manifest.get("atoms") or ():
        atom_id = str(raw.get("atom_id") or "")
        case_key = str(raw.get("case_key") or "").upper()
        profile = kernel.cases.get(case_key)
        if profile is None:
            raise ValueError(f"runtime_query_atom_case_unknown:{atom_id}")
        target = str(raw.get("target_entity") or "").upper()
        facet = str(raw.get("facet_id") or "")
        request = {
            "schema_version": "fin_ia_evidence_request_v1_0",
            "request_id": f"REQ::{atom_id}",
            "cell_id": f"CELL::{atom_id}",
            "requester_role": str(defaults["requester_role"]),
            "evidence_domain": str(defaults["evidence_domain"]),
            "case_key": case_key,
            "subject_ticker": profile.subject_ticker,
            "research_as_of": str(defaults["research_as_of"]),
            "target_entities": [target],
            "requested_facet_ids": [facet],
            "metric_intents": list(raw.get("metric_intents") or ()),
            "product_intents": list(raw.get("product_intents") or ()),
            "period": dict(defaults["period"]),
            "granularity": str(defaults["granularity"]),
            "unit": str(defaults["unit"]),
            "acceptable_sources": list(defaults["acceptable_sources"]),
            "acceptable_proxy": bool(defaults["acceptable_proxy"]),
            "forbidden_proxy": list(defaults["forbidden_proxy"]),
            "stop_condition": str(defaults["stop_condition"]),
            "clarification_policy": str(defaults["clarification_policy"]),
        }
        load_evidence_request(request, kernel)
        labels = dict(raw.get("labels") or {})
        label_ids = {
            str(value)
            for key in (
                "positive_object_ids",
                "hard_negative_object_ids",
                "unjudged_object_ids",
            )
            for value in labels.get(key) or ()
        }
        missing = sorted(label_ids - set(objects))
        if missing:
            raise ValueError(f"runtime_query_atom_label_missing:{atom_id}:{missing}")
        wrong_owner = sorted(
            object_id
            for object_id in label_ids
            if str(objects[object_id]["base_object_view"].get("ticker") or "").upper()
            != target
        )
        if wrong_owner:
            raise ValueError(
                f"runtime_query_atom_label_owner_mismatch:{atom_id}:{wrong_owner}"
            )
        materialized_atoms.append(
            {"atom_id": atom_id, "request": request, "labels": labels}
        )

    unsigned = {
        "schema_version": QUERY_ATOM_EVAL_SCHEMA_VERSION,
        "status": "runtime_query_atoms_materialized_before_reranker_scoring",
        "recorded_at": "2026-08-13",
        "bound_inputs": {
            "manifest_ref": _relative(manifest_path),
            "manifest_sha256_lf": _sha256(manifest_path, normalize_text=True),
            "kernel_ref": _relative(kernel_path),
            "kernel_sha256_lf": _sha256(kernel_path, normalize_text=True),
            "compiled_objects_ref": _relative(objects_path),
            "compiled_objects_sha256": _sha256(objects_path),
        },
        "policy": {
            "compile_request_before_label_join": True,
            "one_facet_and_one_owner_per_atom": True,
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
            "typed_gap_is_valid_outcome": True,
            "observed_validation_cases_forbidden_from_tuning": list(
                manifest["policy"]["observed_validation_cases_forbidden_from_tuning"]
            ),
        },
        "summary": {
            "atom_count": len(materialized_atoms),
            "case_count": len({row["request"]["case_key"] for row in materialized_atoms}),
            "positive_label_count": sum(
                len(row["labels"].get("positive_object_ids") or ())
                for row in materialized_atoms
            ),
            "hard_negative_label_count": sum(
                len(row["labels"].get("hard_negative_object_ids") or ())
                for row in materialized_atoms
            ),
            "typed_gap_atom_count": sum(
                not bool(row["labels"].get("positive_object_ids"))
                for row in materialized_atoms
            ),
        },
        "atoms": materialized_atoms,
    }
    output = {**unsigned, "eval_digest": canonical_digest(unsigned)}
    # Re-load and compile every request after output assembly. This proves that
    # the labels never participate in query generation.
    for atom in load_query_atoms(output):
        compile_atom_lane(atom, kernel)
    return output


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default="configs/retrieval/fin_ia_0_1_3_s1c_runtime_query_atom_manifest_v1_0.json",
    )
    parser.add_argument(
        "--kernel",
        default="configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_1.json",
    )
    parser.add_argument(
        "--objects",
        default="data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/v1/objects.jsonl",
    )
    parser.add_argument(
        "--output",
        default="configs/retrieval/fin_ia_0_1_3_s1c_runtime_query_atom_eval_v1_0.json",
    )
    args = parser.parse_args()
    result = materialize(
        manifest_path=_resolve(args.manifest),
        kernel_path=_resolve(args.kernel),
        objects_path=_resolve(args.objects),
    )
    output = _resolve(args.output)
    _write_json(output, result)
    print(
        json.dumps(
            {
                "output": _relative(output),
                "summary": result["summary"],
                "eval_digest": result["eval_digest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
