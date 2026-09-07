from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC_ROOT)]

from retrieval.contracts import load_financial_research_kernel  # noqa: E402
from retrieval.query_atom_shadow import (  # noqa: E402
    aggregate_evidence_role_metrics,
    compile_atom_lane,
    evaluate_controlled_evidence_roles,
    load_query_atoms,
)


AUTHORITY_SCHEMA = "fin_ia_s1c_facet_evidence_role_shadow_authority_v1_0"
RESULT_SCHEMA = "fin_ia_s1c_facet_evidence_role_shadow_result_v1_0"


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path.name}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _load_objects(path: Path) -> tuple[dict[str, Any], ...]:
    return tuple(
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def run(authority_path: Path) -> dict[str, Any]:
    authority = _read_json(authority_path)
    if authority.get("schema_version") != AUTHORITY_SCHEMA:
        raise ValueError("facet_role_authority_schema_invalid")
    if authority.get("status") != "zero_network_zero_model_qrel_successor_role_shadow":
        raise ValueError("facet_role_authority_status_invalid")
    if authority.get("authority") != {
        "network_calls_authorized": False,
        "model_calls_authorized": False,
        "candidate_is_not_evidence": True,
        "role_compatibility_is_not_relevance": True,
        "runtime_promotion_authorized": False,
        "training_authorized": False,
    }:
        raise ValueError("facet_role_authority_invalid")
    bound = authority.get("bound_inputs")
    if not isinstance(bound, Mapping):
        raise ValueError("facet_role_bound_inputs_invalid")
    paths: dict[str, Path] = {}
    for key in ("eval", "kernel", "route_policy", "objects"):
        path = _resolve(str(bound.get(f"{key}_ref") or ""))
        if not path.is_file() or _sha256(path) != bound.get(f"{key}_sha256"):
            raise ValueError(f"facet_role_input_drift:{key}")
        paths[key] = path
    kernel = load_financial_research_kernel(_read_json(paths["kernel"]))
    atoms = load_query_atoms(_read_json(paths["eval"]))
    objects = _load_objects(paths["objects"])
    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    atom_results: list[dict[str, Any]] = []
    all_role_rows: list[dict[str, Any]] = []
    material_errors: list[dict[str, Any]] = []
    for atom in atoms:
        _, lane = compile_atom_lane(atom, kernel)
        controlled_ids = (
            *atom.positive_object_ids,
            *atom.hard_negative_object_ids,
            *atom.unjudged_object_ids,
        )
        role_result = evaluate_controlled_evidence_roles(
            atom=atom,
            lane=lane,
            objects=objects,
            controlled_object_ids=controlled_ids,
        )
        atom_results.append(
            {
                "atom_id": atom.atom_id,
                "case_key": atom.request_payload["case_key"],
                "facet_id": lane.facet_id,
                "evidence_owner_ticker": lane.evidence_owner_tickers[0],
                "metrics": role_result["metrics"],
            }
        )
        all_role_rows.extend(role_result["rows"])
        for row in role_result["rows"]:
            compatibility = row["evaluation"]["compatibility"]
            judgement = row["judgement"]
            if not (
                (judgement == "positive" and compatibility != "compatible")
                or (judgement == "hard_negative" and compatibility == "compatible")
            ):
                continue
            candidate = objects_by_id[row["compiled_object_id"]]
            material_errors.append(
                {
                    "atom_id": atom.atom_id,
                    "case_key": atom.request_payload["case_key"],
                    "facet_id": lane.facet_id,
                    "judgement": judgement,
                    "compatibility": compatibility,
                    "compiled_object_id": row["compiled_object_id"],
                    "expected_roles": row["expected_roles"],
                    "predicted_roles": row["evaluation"]["labels"],
                    "text_excerpt": str(candidate["model_text"])[:420],
                }
            )
    result = {
        "schema_version": RESULT_SCHEMA,
        "status": "facet_aware_role_shadow_complete_not_runtime_promotion",
        "recorded_at": authority["recorded_at"],
        "authority_ref": authority_path.relative_to(ROOT).as_posix(),
        "authority_sha256": _sha256(authority_path),
        "summary": {
            "atom_count": len(atoms),
            "case_count": len(
                {str(atom.request_payload["case_key"]) for atom in atoms}
            ),
            **aggregate_evidence_role_metrics(all_role_rows),
            "material_role_error_count": len(material_errors),
        },
        "atom_results": atom_results,
        "material_role_errors": material_errors,
        "decision": (
            "Role compatibility remains an advisory candidate attribute. It may "
            "partition compatible, abstain and incompatible candidates, but it "
            "does not establish relevance, Evidence, or numeric authority."
        ),
        "authority": dict(authority["authority"]),
    }
    _write_json(_resolve(str(authority["output_ref"])), result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--authority",
        default=(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1c_facet_evidence_role_shadow_authority_v1_0.json"
        ),
    )
    args = parser.parse_args(argv)
    print(
        json.dumps(
            run(_resolve(args.authority)),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
