from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from retrieval.artifact_spine import (  # noqa: E402
    ArtifactEnvelope,
    canonical_json_digest,
    load_artifact_spine_policy,
    load_implementation_coverage_matrix,
    validate_coverage_matrix,
)
from retrieval.evaluation_assets import (  # noqa: E402
    EvaluationInput,
    EvaluationProgramManifest,
    EvaluationReference,
    load_evaluation_program_manifest,
    validate_evaluation_program,
)


POLICY_REF = Path(
    "configs/retrieval/fin_ia_0_1_3_s1_canonical_artifact_spine_policy_v1_0.json"
)
MATRIX_REF = Path(
    "configs/retrieval/fin_ia_0_1_3_s1_implementation_coverage_matrix_v1_0.json"
)
EVAL_MANIFEST_REF = Path("eval_sets/fin_0_1_3_s1/program_manifest_v1_0.json")
SCHEMA_REFS = {
    "artifact_envelope.schema.json": ArtifactEnvelope,
    "evaluation_input.schema.json": EvaluationInput,
    "evaluation_reference.schema.json": EvaluationReference,
    "evaluation_program_manifest.schema.json": EvaluationProgramManifest,
}


def emit_schemas(root: Path) -> None:
    schema_root = root / "eval_sets/fin_0_1_3_s1/schemas"
    schema_root.mkdir(parents=True, exist_ok=True)
    for filename, model in SCHEMA_REFS.items():
        payload = model.model_json_schema()
        path = schema_root / filename
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def validate(root: Path) -> dict[str, object]:
    policy = load_artifact_spine_policy(root / POLICY_REF)
    matrix = load_implementation_coverage_matrix(root / MATRIX_REF)
    validate_coverage_matrix(repo_root=root, matrix=matrix, policy=policy)
    manifest = load_evaluation_program_manifest(root / EVAL_MANIFEST_REF)
    evaluation = validate_evaluation_program(repo_root=root, manifest=manifest)
    return {
        "schema_version": "fin_ia_s1_program_foundation_validation_v1_0",
        "status": "pass",
        "policy_id": policy.policy_id,
        "policy_digest": canonical_json_digest(policy.model_dump(mode="json")),
        "coverage_matrix_id": matrix.matrix_id,
        "coverage_matrix_digest": canonical_json_digest(
            matrix.model_dump(mode="json")
        ),
        "coverage_axis_count": len(matrix.rows),
        "coverage_open_gap_count": sum(len(row.known_gaps) for row in matrix.rows),
        "evaluation_program_id": manifest.program_id,
        "evaluation": evaluation,
        "s1_qualified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--emit-schemas", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.emit_schemas:
        emit_schemas(root)
    result = validate(root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
