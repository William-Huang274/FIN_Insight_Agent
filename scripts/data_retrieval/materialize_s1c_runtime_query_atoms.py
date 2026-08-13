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
    QUERY_ATOM_EVAL_SUCCESSOR_SCHEMA_VERSION,
    compile_atom_lane,
    load_query_atoms,
)
from retrieval.query_plan import canonical_digest  # noqa: E402


MANIFEST_SCHEMA_VERSION = "fin_ia_s1c_runtime_query_atom_manifest_v1_0"
ADJUDICATION_SCHEMA_VERSION = (
    "fin_ia_s1c_runtime_query_atom_v2_adjudication_v1_0"
)
LABEL_ID_FIELDS = (
    "positive_object_ids",
    "hard_negative_object_ids",
    "unjudged_object_ids",
)
LABEL_KEY_FIELDS = {
    "positive_object_ids": "positive_object_keys",
    "hard_negative_object_ids": "hard_negative_object_keys",
    "unjudged_object_ids": "unjudged_object_keys",
}


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


def _object_key(row: Mapping[str, Any]) -> str:
    base = row.get("base_object_view")
    if not isinstance(base, Mapping):
        raise ValueError("compiled_object_base_view_invalid")
    value = str(base.get("object_key") or "").strip()
    if not value:
        raise ValueError("compiled_object_key_missing")
    return value


def _object_key_index(
    objects: Mapping[str, Mapping[str, Any]],
) -> dict[str, tuple[Mapping[str, Any], ...]]:
    mutable: dict[str, list[Mapping[str, Any]]] = {}
    for row in objects.values():
        key = _object_key(row)
        mutable.setdefault(key, []).append(row)
    return {key: tuple(values) for key, values in mutable.items()}


def _resolve_target_locator(
    locator: object,
    *,
    target_by_key: Mapping[str, tuple[Mapping[str, Any], ...]],
) -> Mapping[str, Any]:
    if isinstance(locator, str):
        key = locator.strip()
        filters: Mapping[str, Any] = {}
    elif isinstance(locator, Mapping):
        key = str(locator.get("object_key") or "").strip()
        filters = locator
    else:
        raise ValueError("runtime_query_atom_adjudication_locator_invalid")
    if not key:
        raise ValueError("runtime_query_atom_adjudication_object_key_invalid")
    candidates = list(target_by_key.get(key) or ())
    if filters.get("object_kind"):
        candidates = [
            row
            for row in candidates
            if str(row.get("object_kind") or "") == str(filters["object_kind"])
        ]
    if filters.get("metric_row_label"):
        candidates = [
            row
            for row in candidates
            if str((row.get("structured_projection") or {}).get("metric_row_label") or "")
            == str(filters["metric_row_label"])
        ]
    if filters.get("model_text_contains"):
        candidates = [
            row
            for row in candidates
            if str(filters["model_text_contains"]) in str(row.get("model_text") or "")
        ]
    if len(candidates) != 1:
        raise ValueError(
            "runtime_query_atom_adjudication_locator_not_unique:"
            f"{key}:{len(candidates)}"
        )
    return candidates[0]


def _successor_for_source(
    source: Mapping[str, Any],
    *,
    target_by_key: Mapping[str, tuple[Mapping[str, Any], ...]],
) -> Mapping[str, Any]:
    key = _object_key(source)
    source_kind = str(source.get("object_kind") or "")
    source_text = str(source.get("model_text") or "")
    matches = [
        row
        for row in target_by_key.get(key) or ()
        if str(row.get("object_kind") or "") == source_kind
        and str(row.get("model_text") or "") == source_text
    ]
    if len(matches) != 1:
        raise ValueError(
            f"runtime_query_atom_successor_identity_not_unique:{key}:{len(matches)}"
        )
    return matches[0]


def _labels_from_object_keys(
    labels: Mapping[str, Any],
    *,
    target_by_key: Mapping[str, tuple[Mapping[str, Any], ...]],
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    labelled_ids: set[str] = set()
    for id_field, key_field in LABEL_KEY_FIELDS.items():
        values = labels.get(key_field, [])
        if not isinstance(values, list):
            raise ValueError(f"runtime_query_atom_adjudication_{key_field}_invalid")
        target_rows = [
            _resolve_target_locator(value, target_by_key=target_by_key)
            for value in values
        ]
        ids = [str(row["compiled_object_id"]) for row in target_rows]
        if len(ids) != len(set(ids)) or labelled_ids.intersection(ids):
            raise ValueError("runtime_query_atom_adjudication_label_overlap")
        labelled_ids.update(ids)
        output[id_field] = ids

    expected_raw = labels.get("expected_roles_by_object_key") or {}
    if not isinstance(expected_raw, Mapping):
        raise ValueError("runtime_query_atom_adjudication_expected_roles_invalid")
    expected_targets = {
        str(
            _resolve_target_locator(key, target_by_key=target_by_key)[
                "compiled_object_id"
            ]
        ): list(roles)
        for key, roles in expected_raw.items()
    }
    orphan = sorted(set(expected_targets) - labelled_ids)
    if orphan:
        raise ValueError(
            f"runtime_query_atom_adjudication_expected_role_orphan:{orphan}"
        )
    output["expected_roles_by_object_id"] = expected_targets
    return output


def _remap_labels(
    labels: Mapping[str, Any],
    *,
    source_objects: Mapping[str, Mapping[str, Any]],
    target_by_key: Mapping[str, tuple[Mapping[str, Any], ...]],
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    source_to_target: dict[str, str] = {}
    for field in LABEL_ID_FIELDS:
        remapped: list[str] = []
        for raw_object_id in labels.get(field) or ():
            object_id = str(raw_object_id)
            source = source_objects.get(object_id)
            if source is None:
                raise ValueError(
                    f"runtime_query_atom_source_label_missing:{object_id}"
                )
            target = _successor_for_source(source, target_by_key=target_by_key)
            target_id = str(target["compiled_object_id"])
            source_to_target[object_id] = target_id
            remapped.append(target_id)
        output[field] = remapped

    expected_raw = labels.get("expected_roles_by_object_id") or {}
    if not isinstance(expected_raw, Mapping):
        raise ValueError("runtime_query_atom_source_expected_roles_invalid")
    output["expected_roles_by_object_id"] = {
        source_to_target[str(object_id)]: list(roles)
        for object_id, roles in expected_raw.items()
        if str(object_id) in source_to_target
    }
    return output


def _validate_label_owners(
    atom_id: str,
    target: str,
    labels: Mapping[str, Any],
    objects: Mapping[str, Mapping[str, Any]],
) -> None:
    ids = {
        str(value)
        for field in LABEL_ID_FIELDS
        for value in labels.get(field) or ()
    }
    missing = sorted(ids - set(objects))
    if missing:
        raise ValueError(f"runtime_query_atom_label_missing:{atom_id}:{missing}")
    wrong_owner = sorted(
        object_id
        for object_id in ids
        if str(objects[object_id]["base_object_view"].get("ticker") or "").upper()
        != target
    )
    if wrong_owner:
        raise ValueError(
            f"runtime_query_atom_label_owner_mismatch:{atom_id}:{wrong_owner}"
        )


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


def materialize_successor(
    *,
    source_eval_path: Path,
    kernel_path: Path,
    source_objects_path: Path,
    target_objects_path: Path,
    adjudication_path: Path,
) -> dict[str, Any]:
    source_eval = _read_json(source_eval_path)
    adjudication = _read_json(adjudication_path)
    kernel = load_financial_research_kernel(_read_json(kernel_path))
    if source_eval.get("schema_version") != QUERY_ATOM_EVAL_SCHEMA_VERSION:
        raise ValueError("runtime_query_atom_successor_source_schema_invalid")
    if adjudication.get("schema_version") != ADJUDICATION_SCHEMA_VERSION:
        raise ValueError("runtime_query_atom_adjudication_schema_invalid")
    load_query_atoms(source_eval)

    source_objects = _read_object_index(source_objects_path)
    target_objects = _read_object_index(target_objects_path)
    target_by_key = _object_key_index(target_objects)
    replacements_raw = adjudication.get("replacements")
    if not isinstance(replacements_raw, list):
        raise ValueError("runtime_query_atom_adjudication_replacements_invalid")
    replacements: dict[str, Mapping[str, Any]] = {}
    for replacement in replacements_raw:
        if not isinstance(replacement, Mapping):
            raise ValueError("runtime_query_atom_adjudication_replacement_invalid")
        atom_id = str(replacement.get("atom_id") or "").strip()
        reason = str(replacement.get("business_reason_zh") or "").strip()
        labels = replacement.get("labels")
        if (
            not atom_id
            or atom_id in replacements
            or not reason
            or not isinstance(labels, Mapping)
        ):
            raise ValueError("runtime_query_atom_adjudication_replacement_invalid")
        replacements[atom_id] = replacement

    source_rows = source_eval.get("atoms")
    if not isinstance(source_rows, list) or not source_rows:
        raise ValueError("runtime_query_atom_successor_source_rows_missing")
    source_atom_ids = {str(row.get("atom_id") or "") for row in source_rows}
    unknown_replacements = sorted(set(replacements) - source_atom_ids)
    if unknown_replacements:
        raise ValueError(
            f"runtime_query_atom_adjudication_atom_unknown:{unknown_replacements}"
        )

    materialized_atoms: list[dict[str, Any]] = []
    adjudicated_atoms: list[dict[str, Any]] = []
    source_label_ids: set[str] = set()
    target_label_ids: set[str] = set()
    for raw in source_rows:
        atom_id = str(raw["atom_id"])
        request = dict(raw["request"])
        source_labels = dict(raw["labels"])
        source_label_ids.update(
            str(value)
            for field in LABEL_ID_FIELDS
            for value in source_labels.get(field) or ()
        )
        replacement = replacements.get(atom_id)
        if replacement is None:
            labels = _remap_labels(
                source_labels,
                source_objects=source_objects,
                target_by_key=target_by_key,
            )
        else:
            labels = _labels_from_object_keys(
                replacement["labels"],
                target_by_key=target_by_key,
            )
            adjudicated_atoms.append(
                {
                    "atom_id": atom_id,
                    "business_reason_zh": str(replacement["business_reason_zh"]),
                }
            )
        target = str((request.get("target_entities") or [""])[0]).upper()
        _validate_label_owners(atom_id, target, labels, target_objects)
        target_label_ids.update(
            str(value)
            for field in LABEL_ID_FIELDS
            for value in labels.get(field) or ()
        )
        materialized_atoms.append(
            {"atom_id": atom_id, "request": request, "labels": labels}
        )

    policy = adjudication.get("policy")
    if not isinstance(policy, Mapping):
        raise ValueError("runtime_query_atom_adjudication_policy_invalid")
    identity_overlap = sorted(source_label_ids.intersection(target_label_ids))
    if policy.get("require_target_identity_rotation") is True and identity_overlap:
        raise ValueError(
            f"runtime_query_atom_successor_identity_not_rotated:{identity_overlap}"
        )
    source_query_digest = canonical_digest(
        [
            {"atom_id": str(row["atom_id"]), "request": row["request"]}
            for row in source_rows
        ]
    )
    target_query_digest = canonical_digest(
        [
            {"atom_id": row["atom_id"], "request": row["request"]}
            for row in materialized_atoms
        ]
    )
    if source_query_digest != target_query_digest:
        raise ValueError("runtime_query_atom_successor_query_contract_changed")

    unsigned = {
        "schema_version": QUERY_ATOM_EVAL_SUCCESSOR_SCHEMA_VERSION,
        "status": "current_object_qrels_successor_materialized_before_runtime_ranking",
        "recorded_at": "2026-08-13",
        "bound_inputs": {
            "source_eval_ref": _relative(source_eval_path),
            "source_eval_sha256_lf": _sha256(
                source_eval_path, normalize_text=True
            ),
            "kernel_ref": _relative(kernel_path),
            "kernel_sha256_lf": _sha256(kernel_path, normalize_text=True),
            "source_compiled_objects_ref": _relative(source_objects_path),
            "source_compiled_objects_sha256": _sha256(source_objects_path),
            "target_compiled_objects_ref": _relative(target_objects_path),
            "target_compiled_objects_sha256": _sha256(target_objects_path),
            "adjudication_ref": _relative(adjudication_path),
            "adjudication_sha256_lf": _sha256(
                adjudication_path, normalize_text=True
            ),
        },
        "policy": {
            **dict(source_eval["policy"]),
            "qrel_successor_not_attempt_rewrite": True,
            "stable_object_key_before_compiled_id": True,
            "source_level_match_is_not_object_level_relevance": True,
            "adjudication_authority": str(policy["adjudication_authority"]),
            "owner_acceptance": False,
        },
        "query_contract": {
            "source_query_digest": source_query_digest,
            "target_query_digest": target_query_digest,
            "unchanged": True,
        },
        "adjudication_summary": {
            "replacement_atom_count": len(adjudicated_atoms),
            "replacement_atoms": adjudicated_atoms,
            "source_target_label_identity_overlap_count": len(identity_overlap),
        },
        "summary": {
            "atom_count": len(materialized_atoms),
            "case_count": len(
                {row["request"]["case_key"] for row in materialized_atoms}
            ),
            "positive_label_count": sum(
                len(row["labels"].get("positive_object_ids") or ())
                for row in materialized_atoms
            ),
            "hard_negative_label_count": sum(
                len(row["labels"].get("hard_negative_object_ids") or ())
                for row in materialized_atoms
            ),
            "unjudged_label_count": sum(
                len(row["labels"].get("unjudged_object_ids") or ())
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
        "--successor-eval",
        help="Immutable predecessor eval used for an object-contract successor.",
    )
    parser.add_argument(
        "--source-objects",
        help="Compiled object population bound by --successor-eval.",
    )
    parser.add_argument(
        "--adjudication",
        help="Small object-key adjudication overlay for successor materialization.",
    )
    parser.add_argument(
        "--output",
        default="configs/retrieval/fin_ia_0_1_3_s1c_runtime_query_atom_eval_v1_0.json",
    )
    args = parser.parse_args()
    successor_values = (
        args.successor_eval,
        args.source_objects,
        args.adjudication,
    )
    if any(successor_values) and not all(successor_values):
        parser.error(
            "--successor-eval, --source-objects, and --adjudication are required together"
        )
    if all(successor_values):
        result = materialize_successor(
            source_eval_path=_resolve(args.successor_eval),
            kernel_path=_resolve(args.kernel),
            source_objects_path=_resolve(args.source_objects),
            target_objects_path=_resolve(args.objects),
            adjudication_path=_resolve(args.adjudication),
        )
    else:
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
