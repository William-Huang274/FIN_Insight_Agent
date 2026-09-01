from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import subprocess
import time
from typing import Any, Mapping

import numpy as np


SCHEMA_VERSION = "fin_ia_s1_qwen_query_embedding_qualification_v1_0"
QUALIFICATION_ROOT = Path(r"Z:\FIN_Insight_Agent_qualification")
EXPECTED_QRELS_SHA256 = (
    "1d56f1deef3d7082b4e308a9caae1e7b70941a66cd025620adbcc80231b7562b"
)
EXPECTED_QREL_MANIFEST_DIGEST = (
    "116d52a44569109ac47f0ce8e0875987673862d741d952eccee1a29c607ab7f4"
)
EXPECTED_POLICY_SHA256 = (
    "6857a41fea14cd3ffd0e9e524a11d06955287a6bd28f37e63e9d1eb102df53ac"
)
EXPECTED_MODEL_DIGEST = (
    "4a3dd5cbc715bf1031d9d10ed6c7f43ff38f2ac5bc19b7fbcdc21787c68be76c"
)
EXPECTED_INFERENCE_PACKAGE_DIGEST = (
    "6b2038c8c4b044a7feff6909abc6c84537abd4da2ce1ace9cf84e0c75ddefe66"
)
EXPECTED_RUNTIME_VERSIONS = {
    "numpy": "2.4.6",
    "safetensors": "0.8.0",
    "scipy": "1.17.1",
    "sentence-transformers": "6.0.0",
    "tokenizers": "0.23.1",
    "torch": "2.7.1+cu118",
    "transformers": "5.16.1",
}
EXPECTED_PYTHON_VERSION = "3.11.14"
INFERENCE_PACKAGE_FILES = (
    "1_Pooling/config.json",
    "config.json",
    "config_sentence_transformers.json",
    "configuration.json",
    "generation_config.json",
    "merges.txt",
    "model.safetensors",
    "modules.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
)


class QueryEmbeddingQualificationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise QueryEmbeddingQualificationError(f"expected_json_object:{path}")
    return value


def _legacy_model_identity(model_dir: Path, expected_name: str) -> dict[str, Any]:
    """Reproduce the identity bound by the existing v1_9 runtime policy."""
    config = model_dir / "config.json"
    weights = [
        path
        for name in ("model.safetensors", "pytorch_model.bin")
        if (path := model_dir / name).is_file()
    ]
    if not config.is_file() or not weights:
        raise QueryEmbeddingQualificationError(
            f"local_model_incomplete:{expected_name}"
        )
    tokenizer_files = [
        path
        for name in (
            "tokenizer.json",
            "tokenizer_config.json",
            "sentencepiece.bpe.model",
        )
        if (path := model_dir / name).is_file()
    ]
    files = [config, *weights, *tokenizer_files]
    body = {
        "model_name": expected_name,
        "directory_name": model_dir.name,
        "files": [
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ],
    }
    return {**body, "model_digest": canonical_digest(body)}


def _inference_package_identity(model_dir: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for relative_path in INFERENCE_PACKAGE_FILES:
        path = model_dir / Path(relative_path)
        if not path.is_file():
            raise QueryEmbeddingQualificationError(
                f"inference_package_file_missing:{relative_path}"
            )
        files.append(
            {
                "relative_path": relative_path,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    body = {"directory_name": model_dir.name, "files": files}
    return {**body, "package_digest": canonical_digest(body)}


def _runtime_versions() -> dict[str, str]:
    versions = {
        package: importlib.metadata.version(package)
        for package in EXPECTED_RUNTIME_VERSIONS
    }
    if versions != EXPECTED_RUNTIME_VERSIONS:
        raise QueryEmbeddingQualificationError(
            f"runtime_version_drift:{versions}:{EXPECTED_RUNTIME_VERSIONS}"
        )
    if platform.python_version() != EXPECTED_PYTHON_VERSION:
        raise QueryEmbeddingQualificationError(
            f"python_version_drift:{platform.python_version()}:{EXPECTED_PYTHON_VERSION}"
        )
    return versions


def _installed_distribution_manifest() -> list[dict[str, str]]:
    packages: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        name = str(distribution.metadata.get("Name") or "").strip().casefold()
        if name:
            packages[name] = distribution.version
    return [
        {"name": name, "version": version}
        for name, version in sorted(packages.items())
    ]


def _git_state(repository_root: Path) -> dict[str, Any]:
    def invoke(*arguments: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(repository_root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    status = invoke("status", "--short")
    return {
        "head": invoke("rev-parse", "HEAD"),
        "branch": invoke("branch", "--show-current"),
        "status_digest": canonical_digest(status.splitlines()),
        "dirty": bool(status),
    }


def _qualification_path(path: Path) -> Path:
    resolved = path.resolve()
    root = QUALIFICATION_ROOT.resolve()
    try:
        common = Path(os.path.commonpath((str(root), str(resolved))))
    except ValueError as exc:
        raise QueryEmbeddingQualificationError(
            f"qualification_path_drive_mismatch:{path}"
        ) from exc
    if str(common).casefold() != str(root).casefold() or resolved == root:
        raise QueryEmbeddingQualificationError(
            f"qualification_path_outside_root:{path}"
        )
    return resolved


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _load_queries(payload: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    if payload.get("schema_version") != "fin_ia_s1c_requalified_ranking_qrels_v1_0":
        raise QueryEmbeddingQualificationError("qrels_schema_mismatch")
    if payload.get("qrel_manifest_digest") != EXPECTED_QREL_MANIFEST_DIGEST:
        raise QueryEmbeddingQualificationError("qrel_manifest_digest_mismatch")
    policy = payload.get("policy")
    if not (
        isinstance(policy, Mapping)
        and policy.get("labels_joined_after_candidate_generation") is True
        and policy.get("target_ids_forbidden_from_query_text") is True
        and policy.get("candidate_is_not_evidence") is True
    ):
        raise QueryEmbeddingQualificationError("qrels_policy_mismatch")
    rows = payload.get("qrels")
    if not isinstance(rows, list) or len(rows) != 18:
        raise QueryEmbeddingQualificationError("qrel_count_mismatch")
    qrel_ids: list[str] = []
    queries: list[str] = []
    all_targets: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise QueryEmbeddingQualificationError("qrel_row_invalid")
        qrel_id = str(row.get("qrel_id") or "")
        values = [
            str(value).strip()
            for value in row.get("semantic_query_texts") or ()
            if str(value).strip()
        ]
        targets = [
            str(value).strip()
            for value in row.get("target_current_source_record_ids") or ()
            if str(value).strip()
        ]
        query = "\n".join(values)
        if not qrel_id or not query or not targets:
            raise QueryEmbeddingQualificationError("qrel_semantic_query_incomplete")
        qrel_ids.append(qrel_id)
        queries.append(query)
        all_targets.extend(targets)
    if len(set(qrel_ids)) != len(qrel_ids):
        raise QueryEmbeddingQualificationError("qrel_id_duplicate")
    for qrel_id, query in zip(qrel_ids, queries, strict=True):
        if any(target.casefold() in query.casefold() for target in all_targets):
            raise QueryEmbeddingQualificationError(
                f"cross_qrel_target_leakage:{qrel_id}"
            )
    return qrel_ids, queries


def run(args: argparse.Namespace) -> dict[str, Any]:
    import torch
    from sentence_transformers import SentenceTransformer

    output_dir = _qualification_path(Path(args.output_dir))
    if output_dir.exists() and any(output_dir.iterdir()):
        raise QueryEmbeddingQualificationError("fresh_attempt_output_not_empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    embeddings_path = output_dir / "query_embeddings.float32.npy"
    manifest_path = output_dir / "manifest.json"
    qrels_path = Path(args.qrels).resolve()
    policy_path = Path(args.policy).resolve()
    model_dir = Path(args.model_dir).resolve()
    for path in (qrels_path, policy_path):
        if not path.is_file():
            raise QueryEmbeddingQualificationError(f"input_file_missing:{path}")
    if not model_dir.is_dir():
        raise QueryEmbeddingQualificationError(f"model_directory_missing:{model_dir}")
    if any(model_dir.glob("*.py")):
        raise QueryEmbeddingQualificationError("custom_model_code_present")
    if sha256_file(qrels_path) != EXPECTED_QRELS_SHA256:
        raise QueryEmbeddingQualificationError("qrels_file_digest_mismatch")
    if sha256_file(policy_path) != EXPECTED_POLICY_SHA256:
        raise QueryEmbeddingQualificationError("runtime_policy_digest_mismatch")

    qrel_payload = _read_json(qrels_path)
    policy = _read_json(policy_path)
    qrel_ids, queries = _load_queries(qrel_payload)
    qwen_policy = policy.get("qwen_embedding")
    if not isinstance(qwen_policy, Mapping):
        raise QueryEmbeddingQualificationError("qwen_policy_missing")
    instruction = str(qwen_policy.get("query_instruction") or "")
    maximum_sequence_length = int(qwen_policy.get("maximum_sequence_length") or 0)
    if not instruction or maximum_sequence_length != 512:
        raise QueryEmbeddingQualificationError("qwen_query_contract_mismatch")

    model_identity = _legacy_model_identity(
        model_dir,
        str(qwen_policy.get("model_id") or "Qwen/Qwen3-Embedding-0.6B"),
    )
    if model_identity["model_digest"] != EXPECTED_MODEL_DIGEST:
        raise QueryEmbeddingQualificationError("local_model_digest_mismatch")
    if str(qwen_policy.get("model_digest") or "") != EXPECTED_MODEL_DIGEST:
        raise QueryEmbeddingQualificationError("policy_model_digest_mismatch")
    inference_package_identity = _inference_package_identity(model_dir)
    if (
        inference_package_identity["package_digest"]
        != EXPECTED_INFERENCE_PACKAGE_DIGEST
    ):
        raise QueryEmbeddingQualificationError("inference_package_digest_mismatch")
    runtime_versions = _runtime_versions()
    if not torch.cuda.is_available():
        raise QueryEmbeddingQualificationError("cuda_runtime_unavailable")

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
    started = time.perf_counter()
    runtime = SentenceTransformer(
        str(model_dir),
        device="cuda",
        local_files_only=True,
        trust_remote_code=False,
    )
    runtime.half()
    runtime.eval()
    runtime.max_seq_length = maximum_sequence_length
    prompted_inputs = [instruction + query for query in queries]
    tokenized = runtime.tokenizer(
        prompted_inputs,
        add_special_tokens=True,
        truncation=False,
        return_attention_mask=True,
    )
    input_ids = tokenized["input_ids"]
    attention_masks = tokenized["attention_mask"]
    token_counts = [len(values) for values in input_ids]
    if max(token_counts) > maximum_sequence_length:
        raise QueryEmbeddingQualificationError("query_would_be_truncated")
    runtime_tokenized = runtime.tokenize(prompted_inputs)
    runtime_input_ids = runtime_tokenized["input_ids"].detach().cpu().tolist()
    runtime_attention_masks = (
        runtime_tokenized["attention_mask"].detach().cpu().tolist()
    )
    batch_size = len(queries)
    torch.cuda.reset_peak_memory_stats()
    encoded = runtime.encode(
        queries,
        batch_size=batch_size,
        prompt=instruction,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    embeddings = np.asarray(encoded, dtype=np.float32)
    expected_shape = (len(queries), 1024)
    if embeddings.shape != expected_shape:
        raise QueryEmbeddingQualificationError(
            f"query_embedding_shape_mismatch:{embeddings.shape}:{expected_shape}"
        )
    if not np.isfinite(embeddings).all():
        raise QueryEmbeddingQualificationError("query_embedding_non_finite")
    norms = np.linalg.norm(embeddings, axis=1)
    if float(norms.min()) < 0.999 or float(norms.max()) > 1.001:
        raise QueryEmbeddingQualificationError("query_embedding_normalization_drift")
    unique_row_count = int(np.unique(embeddings, axis=0).shape[0])
    if unique_row_count != len(queries):
        raise QueryEmbeddingQualificationError("query_embedding_duplicate_rows")
    similarity = embeddings @ embeddings.T
    off_diagonal = similarity[~np.eye(len(queries), dtype=bool)]
    maximum_off_diagonal_similarity = float(off_diagonal.max())
    if maximum_off_diagonal_similarity >= 0.999999:
        raise QueryEmbeddingQualificationError("query_embedding_collapse_detected")
    repeated = np.asarray(
        runtime.encode(
            queries,
            batch_size=batch_size,
            prompt=instruction,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ),
        dtype=np.float32,
    )
    maximum_repeat_absolute_difference = float(
        np.max(np.abs(embeddings - repeated))
    )
    if maximum_repeat_absolute_difference > 1e-6:
        raise QueryEmbeddingQualificationError(
            "query_embedding_repeatability_drift"
        )
    np.save(embeddings_path, embeddings, allow_pickle=False)

    first_parameter = next(runtime.parameters())
    repository_root = Path(__file__).resolve().parents[2]
    embedding_runtime_path = repository_root / "src" / "retrieval" / "embedding_runtime.py"
    distribution_manifest = _installed_distribution_manifest()

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "bounded_development_query_embedding_pass",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "attempt_id": args.attempt_id,
        "authority": {
            "candidate_is_not_evidence": True,
            "development_qrels_only": True,
            "blind_qualification": False,
            "paid_call": False,
            "evidence_admission_authorized": False,
            "production_cutover_authorized": False,
        },
        "inputs": {
            "qrels_sha256": EXPECTED_QRELS_SHA256,
            "qrel_manifest_digest": EXPECTED_QREL_MANIFEST_DIGEST,
            "runtime_policy_sha256": EXPECTED_POLICY_SHA256,
            "query_text_digest": canonical_digest(queries),
            "prompted_input_digest": canonical_digest(prompted_inputs),
            "untruncated_tokenized_input_digest": canonical_digest(
                {
                    "input_ids": input_ids,
                    "attention_mask": attention_masks,
                }
            ),
            "runtime_tokenized_input_digest": canonical_digest(
                {
                    "input_ids": runtime_input_ids,
                    "attention_mask": runtime_attention_masks,
                }
            ),
            "qrel_order": qrel_ids,
            "query_count": len(queries),
            "query_character_count": sum(len(value) for value in queries),
        },
        "model": {
            "model_id": str(qwen_policy.get("model_id") or ""),
            "model_identity": model_identity,
            "inference_package_identity": inference_package_identity,
            "query_instruction": instruction,
            "prompt_concatenation": "instruction_plus_query_without_inserted_separator",
            "trust_remote_code": False,
            "maximum_sequence_length": maximum_sequence_length,
            "normalize_embeddings": True,
            "batch_size": batch_size,
            "parameter_dtype": str(first_parameter.dtype).removeprefix("torch."),
            "output_dtype": "float32",
            "execution_device": str(first_parameter.device),
            "gpu_name": torch.cuda.get_device_name(0),
        },
        "runtime": {
            "python": platform.python_version(),
            **runtime_versions,
            "torch_cuda": torch.version.cuda,
            "installed_distribution_manifest": distribution_manifest,
            "installed_distribution_digest": canonical_digest(
                distribution_manifest
            ),
        },
        "implementation": {
            "qualification_script_sha256": sha256_file(Path(__file__).resolve()),
            "production_embedding_runtime_sha256": sha256_file(
                embedding_runtime_path
            ),
            "repository": _git_state(repository_root),
        },
        "TokenBudgetBasis": {
            "node_purpose": "Generate source-bound dense query vectors for 18 development retrieval qrels.",
            "input_scale": {
                "query_count": len(queries),
                "query_character_count": sum(len(value) for value in queries),
                "minimum_token_count_with_instruction": min(token_counts),
                "maximum_token_count_with_instruction": max(token_counts),
            },
            "required_output": "One normalized 1024-dimensional float32 vector per qrel in frozen qrel order.",
            "schema_burden": "Fixed numpy shape, dtype, qrel order, hashes and manifest.",
            "materiality_and_quality_risk": "Development candidate ranking only; a bad vector can hide a source candidate but cannot grant Evidence.",
            "comparable_run_evidence": "Document side is the frozen 34,199-row Qwen FP16 cache bound by model and object digests.",
            "reasoning_profile": "Deterministic embedding inference; no generative reasoning.",
            "stop_and_truncation": "Fail before inference if any instructed query exceeds 512 tokens; fail on shape, finite or norm drift.",
        },
        "output": {
            "embedding_ref": str(embeddings_path),
            "embedding_sha256": sha256_file(embeddings_path),
            "shape": list(embeddings.shape),
            "dtype": str(embeddings.dtype),
            "minimum_l2_norm": float(norms.min()),
            "maximum_l2_norm": float(norms.max()),
            "unique_row_count": unique_row_count,
            "maximum_off_diagonal_similarity": maximum_off_diagonal_similarity,
            "maximum_repeat_absolute_difference": maximum_repeat_absolute_difference,
            "peak_cuda_memory_bytes": int(torch.cuda.max_memory_allocated()),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        },
        "known_boundaries": [
            "The qrels are development labels with historical exposure, not a blind holdout.",
            "Target IDs do not enter query text or embedding inference.",
            "This uses the v1_9 current-runtime instruction and is not input-parity with the older compiled-object retriever comparison instruction.",
            "The locally observed small-file Hugging Face revision metadata does not independently attest the weight file's repository revision; the full local inference bundle is content-addressed instead.",
            "This artifact enables dense candidate comparison only and grants no Evidence or numeric authority.",
        ],
    }
    manifest["result_digest"] = canonical_digest(manifest)
    _atomic_write_json(manifest_path, manifest)
    return manifest


def _write_failure(args: argparse.Namespace, exc: Exception) -> None:
    try:
        output_dir = _qualification_path(Path(args.output_dir))
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "failure-receipt.json"
        if path.exists():
            return
        receipt: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "status": "failed_immutable_attempt",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "attempt_id": str(args.attempt_id),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "production_cutover_authorized": False,
        }
        receipt["result_digest"] = canonical_digest(receipt)
        _atomic_write_json(path, receipt)
    except Exception:
        return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--qrels", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--model-dir", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run(args)
    except Exception as exc:
        _write_failure(args, exc)
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "status": result["status"],
                "attempt_id": result["attempt_id"],
                "shape": result["output"]["shape"],
                "elapsed_seconds": result["output"]["elapsed_seconds"],
                "peak_cuda_memory_bytes": result["output"][
                    "peak_cuda_memory_bytes"
                ],
                "result_digest": result["result_digest"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
