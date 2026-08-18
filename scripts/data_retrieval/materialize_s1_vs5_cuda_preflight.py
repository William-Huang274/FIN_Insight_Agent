from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from retrieval.cross_encoder import cross_encoder_model_identity  # noqa: E402
from retrieval.cuda_execution import required_cuda_fp16_receipt  # noqa: E402
from retrieval.embedding_runtime import local_model_identity  # noqa: E402


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path.name}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _bound_ref(path: Path, *, purpose: str) -> dict[str, str]:
    return {"ref": _relative(path), "sha256": _sha256(path), "purpose": purpose}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the fail-closed CUDA/FP16 preflight for S1 VS5."
    )
    parser.add_argument(
        "--overlay",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_runtime_overlay_v1_0.json",
    )
    parser.add_argument(
        "--program-manifest",
        default="eval_sets/fin_0_1_3_s1/program_manifest_v1_0.json",
    )
    parser.add_argument(
        "--runtime-result",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_runtime_inputs_result_v1_0.json",
    )
    parser.add_argument(
        "--reference-result",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_references_result_v1_0.json",
    )
    parser.add_argument(
        "--compiled-result",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_compiled_objects_result_v1_0.json",
    )
    parser.add_argument(
        "--bge-model-dir",
        default=os.environ.get("FIN_BGE_M3_MODEL_DIR", "D:/hf_models/BAAI__bge-m3"),
    )
    parser.add_argument(
        "--qwen-model-dir",
        default=os.environ.get(
            "FIN_QWEN_EMBEDDING_MODEL_DIR", "D:/hf_models/Qwen__Qwen3-Embedding-0.6B"
        ),
    )
    parser.add_argument(
        "--bge-reranker-dir",
        default=os.environ.get(
            "FIN_BGE_RERANKER_MODEL_DIR",
            "D:/hf_models/modelscope_BAAI__bge-reranker-v2-m3",
        ),
    )
    parser.add_argument(
        "--qwen-reranker-dir",
        default=os.environ.get(
            "FIN_QWEN_RERANKER_MODEL_DIR", "D:/hf_models/Qwen__Qwen3-Reranker-0.6B"
        ),
    )
    parser.add_argument(
        "--output",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs5_cuda_preflight_result_v1_0.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    overlay_path = _resolve(args.overlay)
    program_path = _resolve(args.program_manifest)
    runtime_result_path = _resolve(args.runtime_result)
    reference_result_path = _resolve(args.reference_result)
    compiled_result_path = _resolve(args.compiled_result)
    overlay = _read_json(overlay_path)
    compiled_result = _read_json(compiled_result_path)
    object_path = _resolve(str(compiled_result["output_binding"]["objects_ref"]))
    expected_object_digest = str(compiled_result["output_binding"]["objects_sha256"])
    if _sha256(object_path) != expected_object_digest:
        raise ValueError("qualification_cuda_preflight_object_digest_drift")

    authority = overlay["authority"]
    if not (
        authority["learned_vector_device"] == "cuda"
        and authority["learned_vector_precision"] == "fp16"
        and authority["cpu_vector_fallback_allowed"] is False
    ):
        raise ValueError("qualification_cuda_preflight_policy_invalid")

    bge_dir = _resolve(args.bge_model_dir)
    qwen_dir = _resolve(args.qwen_model_dir)
    bge_reranker_dir = _resolve(args.bge_reranker_dir)
    qwen_reranker_dir = _resolve(args.qwen_reranker_dir)
    models = {
        "bge_embedding": local_model_identity(bge_dir, "BAAI/bge-m3"),
        "qwen_embedding": local_model_identity(
            qwen_dir, "Qwen/Qwen3-Embedding-0.6B"
        ),
        "bge_reranker": cross_encoder_model_identity(bge_reranker_dir),
        "qwen_reranker": cross_encoder_model_identity(
            qwen_reranker_dir, model_id="Qwen/Qwen3-Reranker-0.6B"
        ),
    }
    receipt = required_cuda_fp16_receipt(
        purpose="S1 VS5 learned embedding and reranking preflight"
    )
    output = {
        "schema_version": "fin_ia_s1_vs5_cuda_preflight_result_v1_0",
        "status": "cuda_fp16_eligible_not_execution_authority",
        "recorded_at": "2026-08-18",
        "program_id": str(overlay["program_id"]),
        "bound_inputs": {
            "overlay": _bound_ref(
                overlay_path, purpose="frozen learned retrieval and token budget policy"
            ),
            "program_manifest": _bound_ref(
                program_path, purpose="active split-safe inputs and evaluator references"
            ),
            "runtime_inputs_result": _bound_ref(
                runtime_result_path, purpose="label-free qualification runtime inputs"
            ),
            "evaluator_references_result": _bound_ref(
                reference_result_path, purpose="physically separate evaluator references"
            ),
            "compiled_objects_result": _bound_ref(
                compiled_result_path, purpose="compiled qualification object snapshot"
            ),
            "compiled_objects": {
                "ref": _relative(object_path),
                "sha256": expected_object_digest,
                "object_count": 10618,
                "purpose": "fixed candidate corpus; Candidate is not Evidence",
            },
        },
        "cuda_execution_receipt": receipt,
        "models": {
            key: {
                "model_digest": value["model_digest"],
                "model_name": value.get("model_name") or value.get("model_id"),
                "local_directory_name": value.get("directory_name")
                or value.get("local_directory_name"),
            }
            for key, value in models.items()
        },
        "execution_contract": {
            "embedding_device": "cuda",
            "embedding_precision": "fp16",
            "reranker_device": "cuda",
            "reranker_precision": "fp16",
            "cpu_vector_fallback_allowed": False,
            "cpu_allowed_work": [
                "bm25",
                "tokenization",
                "sql",
                "hard_filters",
                "ledger",
                "deterministic_orchestration",
            ],
            "models_loaded_during_preflight": False,
            "vectors_computed_during_preflight": False,
            "failure_policy": "fail_closed_before_learned_execution",
        },
        "authority": {
            "valid_temporal_execution_authorized": False,
            "hidden_split_execution_authorized": False,
            "candidate_is_evidence": False,
            "numeric_fact_authority": False,
        },
    }
    _write_json(_resolve(args.output), output)
    print(
        json.dumps(
            {
                "device": receipt["device_name"],
                "execution_device": receipt["execution_device"],
                "precision": receipt["embedding_precision"],
                "cpu_fallback_allowed": receipt["cpu_fallback_allowed"],
                "model_digests": {
                    key: value["model_digest"] for key, value in output["models"].items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
