from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .model_identity import _regular_files_without_links
from .query_plan import canonical_digest


QUANTIZED_MANIFEST_NAME = "fin_ia_quantized_acquisition_manifest_v1_0.json"
QUANTIZED_MANIFEST_SCHEMA = "fin_ia_quantized_acquisition_manifest_v1_0"
TOOL_MANIFEST_NAME = "fin_ia_tool_acquisition_manifest_v1_0.json"
TOOL_MANIFEST_SCHEMA = "fin_ia_tool_acquisition_manifest_v1_0"
QWEN3_RERANKER_SYSTEM = (
    "Judge whether the Document meets the requirements based on the Query and "
    'the Instruct provided. Note that the answer can only be "yes" or "no".'
)
QWEN3_RERANKER_SUFFIX = (
    "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_qwen3_reranker_prompt(
    *, instruction: str, query: str, document: str
) -> str:
    values = (instruction.strip(), query.strip(), document.strip())
    if not all(values):
        raise ValueError("quantized_shadow_reranker_prompt_field_empty")
    return (
        f"<|im_start|>system\n{QWEN3_RERANKER_SYSTEM}"
        "<|im_end|>\n<|im_start|>user\n"
        f"<Instruct>: {values[0]}\n<Query>: {values[1]}\n"
        f"<Document>: {values[2]}{QWEN3_RERANKER_SUFFIX}"
    )


def parse_llama_yes_no_margin(
    response: Mapping[str, Any],
    *,
    yes_token_id: int,
    no_token_id: int,
) -> dict[str, Any]:
    if (
        isinstance(yes_token_id, bool)
        or isinstance(no_token_id, bool)
        or not isinstance(yes_token_id, int)
        or not isinstance(no_token_id, int)
        or yes_token_id < 0
        or no_token_id < 0
        or yes_token_id == no_token_id
        or response.get("truncated") is not False
    ):
        raise ValueError("quantized_shadow_yes_no_response_invalid")
    probabilities = response.get("probs")
    if probabilities is None:
        probabilities = response.get("completion_probabilities")
    if not isinstance(probabilities, list) or len(probabilities) != 1:
        raise ValueError("quantized_shadow_yes_no_probability_row_invalid")
    row = probabilities[0]
    if not isinstance(row, Mapping):
        raise ValueError("quantized_shadow_yes_no_probability_row_invalid")
    top = row.get("top_logprobs")
    if not isinstance(top, list):
        raise ValueError("quantized_shadow_yes_no_top_logprobs_missing")
    by_id: dict[int, float] = {}
    token_text: dict[int, str] = {}
    for item in top:
        if not isinstance(item, Mapping):
            raise ValueError("quantized_shadow_yes_no_top_logprobs_invalid")
        token_id = item.get("id")
        logprob = item.get("logprob")
        if (
            isinstance(token_id, bool)
            or not isinstance(token_id, int)
            or token_id in by_id
            or isinstance(logprob, bool)
            or not isinstance(logprob, (int, float))
            or not math.isfinite(float(logprob))
        ):
            raise ValueError("quantized_shadow_yes_no_top_logprobs_invalid")
        by_id[token_id] = float(logprob)
        token_text[token_id] = str(item.get("token") or "")
    if yes_token_id not in by_id or no_token_id not in by_id:
        raise ValueError("quantized_shadow_yes_no_tokens_absent_from_top_logprobs")
    margin = by_id[yes_token_id] - by_id[no_token_id]
    if not math.isfinite(margin):
        raise ValueError("quantized_shadow_yes_no_margin_not_finite")
    return {
        "score": margin,
        "yes_token_id": yes_token_id,
        "no_token_id": no_token_id,
        "yes_token": token_text[yes_token_id],
        "no_token": token_text[no_token_id],
        "yes_logprob": by_id[yes_token_id],
        "no_logprob": by_id[no_token_id],
        "generated_content": str(response.get("content") or ""),
        "generated_token_ids": list(response.get("tokens") or []),
        "tokens_evaluated": response.get("tokens_evaluated"),
        "timings": deepcopy(response.get("timings") or {}),
    }


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(code) from exc
    if not isinstance(value, dict):
        raise ValueError(code)
    return value


def _validate_manifest_closure(
    root: Path,
    *,
    manifest_name: str,
    schema_version: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("quantized_shadow_absolute_artifact_directory_required")
    manifest_path = root / manifest_name
    manifest = _read_json(
        manifest_path, "quantized_shadow_acquisition_manifest_invalid"
    )
    if manifest.get("schema_version") != schema_version:
        raise ValueError("quantized_shadow_acquisition_manifest_schema_invalid")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise ValueError("quantized_shadow_acquisition_manifest_files_invalid")
    by_name: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("quantized_shadow_acquisition_manifest_files_invalid")
        name = str(row.get("path") or "")
        relative = Path(name)
        if (
            not name
            or relative.is_absolute()
            or "\\" in name
            or relative.as_posix() != name
            or ".." in relative.parts
            or name in {manifest_name, "."}
            or name in by_name
        ):
            raise ValueError("quantized_shadow_acquisition_manifest_path_invalid")
        by_name[name] = row
    actual = {
        path.relative_to(root).as_posix(): path
        for path in _regular_files_without_links(root)
        if path != manifest_path
    }
    if set(actual) != set(by_name):
        raise ValueError("quantized_shadow_acquisition_manifest_file_set_mismatch")
    validated: list[dict[str, Any]] = []
    for name in sorted(actual):
        path = actual[name]
        row = by_name[name]
        size = row.get("bytes")
        digest = row.get("sha256")
        if (
            not isinstance(size, int)
            or size < 0
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or path.stat().st_size != size
            or sha256_file(path) != digest
        ):
            raise ValueError(f"quantized_shadow_acquisition_file_drift:{name}")
        validated.append({"path": name, "bytes": size, "sha256": digest})
    return manifest, validated


def quantized_gguf_identity(
    model_dir: Path,
    *,
    expected_repo_id: str,
    expected_revision: str,
    expected_source_model_id: str,
    expected_quantization: str,
) -> dict[str, Any]:
    manifest, files = _validate_manifest_closure(
        model_dir,
        manifest_name=QUANTIZED_MANIFEST_NAME,
        schema_version=QUANTIZED_MANIFEST_SCHEMA,
    )
    gguf_rows = [row for row in files if row["path"].lower().endswith(".gguf")]
    if not (
        manifest.get("repo_id") == expected_repo_id
        and manifest.get("resolved_revision") == expected_revision
        and re.fullmatch(r"[0-9a-f]{40}", expected_revision)
        and manifest.get("source_model_id") == expected_source_model_id
        and manifest.get("quantization") == expected_quantization
        and manifest.get("acquisition_tool")
        == "huggingface_hub.snapshot_download"
        and len(gguf_rows) == 1
        and manifest.get("selected_model_file") == gguf_rows[0]["path"]
    ):
        raise ValueError("quantized_shadow_model_manifest_identity_invalid")
    body = {
        "identity_schema": "fin_ia_quantized_gguf_identity_v1_0",
        "repo_id": expected_repo_id,
        "resolved_revision": expected_revision,
        "source_model_id": expected_source_model_id,
        "quantization": expected_quantization,
        "selected_model_file": gguf_rows[0],
        "files": files,
        "artifact_closure": "manifest_exact_recursive_regular_files_no_links",
    }
    return {**body, "model_digest": canonical_digest(body)}


def llama_cpp_tool_identity(
    tool_dir: Path,
    *,
    expected_release_tag: str,
    expected_server_relative_path: str,
) -> dict[str, Any]:
    manifest, files = _validate_manifest_closure(
        tool_dir,
        manifest_name=TOOL_MANIFEST_NAME,
        schema_version=TOOL_MANIFEST_SCHEMA,
    )
    paths = {row["path"] for row in files}
    if not (
        manifest.get("tool_id") == "ggml-org/llama.cpp"
        and manifest.get("release_tag") == expected_release_tag
        and manifest.get("server_relative_path") == expected_server_relative_path
        and expected_server_relative_path in paths
    ):
        raise ValueError("quantized_shadow_tool_manifest_identity_invalid")
    body = {
        "identity_schema": "fin_ia_llama_cpp_tool_identity_v1_0",
        "tool_id": "ggml-org/llama.cpp",
        "release_tag": expected_release_tag,
        "server_relative_path": expected_server_relative_path,
        "files": files,
        "artifact_closure": "manifest_exact_recursive_regular_files_no_links",
    }
    return {**body, "tool_digest": canonical_digest(body)}


def compile_controlled_ranking_metrics(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not rows:
        raise ValueError("quantized_shadow_metric_rows_empty")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for raw in rows:
        query_id = str(raw.get("query_id") or "")
        case_key = str(raw.get("case_key") or "")
        candidates = raw.get("candidates")
        if (
            not query_id
            or query_id in seen
            or case_key not in {"DELL", "MU", "NVDA"}
            or not isinstance(candidates, list)
            or not candidates
        ):
            raise ValueError("quantized_shadow_metric_row_invalid")
        seen.add(query_id)
        candidate_rows: list[dict[str, Any]] = []
        candidate_ids: set[str] = set()
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                raise ValueError("quantized_shadow_metric_candidate_invalid")
            label = str(candidate.get("label") or "")
            score = candidate.get("score")
            candidate_id = str(candidate.get("candidate_id") or "")
            if (
                label not in {"positive", "hard_negative"}
                or not candidate_id
                or isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(float(score))
                or candidate_id in candidate_ids
            ):
                raise ValueError("quantized_shadow_metric_candidate_invalid")
            candidate_ids.add(candidate_id)
            candidate_rows.append(
                {"candidate_id": candidate_id, "label": label, "score": float(score)}
            )
        normalized.append(
            {"query_id": query_id, "case_key": case_key, "candidates": candidate_rows}
        )

    def aggregate(group: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        comparisons = wins = ties = 0
        eligible = top1_positive = 0
        reciprocal_ranks: list[float] = []
        critical_errors: list[str] = []
        for row in group:
            positives = [c for c in row["candidates"] if c["label"] == "positive"]
            negatives = [
                c for c in row["candidates"] if c["label"] == "hard_negative"
            ]
            if not positives or not negatives:
                continue
            eligible += 1
            ranked = sorted(
                row["candidates"], key=lambda value: (-value["score"], value["candidate_id"])
            )
            first_positive = next(
                index for index, value in enumerate(ranked, start=1) if value["label"] == "positive"
            )
            reciprocal_ranks.append(1.0 / first_positive)
            if ranked[0]["label"] == "positive":
                top1_positive += 1
            else:
                critical_errors.append(str(row["query_id"]))
            for positive in positives:
                for negative in negatives:
                    comparisons += 1
                    if positive["score"] > negative["score"]:
                        wins += 1
                    elif positive["score"] == negative["score"]:
                        ties += 1
        accuracy = None
        if comparisons:
            accuracy = round((wins + 0.5 * ties) / comparisons, 6)
        return {
            "query_count": len(group),
            "eligible_query_count": eligible,
            "pairwise_comparisons": comparisons,
            "pairwise_wins": wins,
            "pairwise_ties": ties,
            "pairwise_accuracy": accuracy,
            "top1_positive_count": top1_positive,
            "top1_positive_rate": (
                round(top1_positive / eligible, 6) if eligible else None
            ),
            "mean_reciprocal_rank": (
                round(sum(reciprocal_ranks) / len(reciprocal_ranks), 6)
                if reciprocal_ranks
                else None
            ),
            "critical_error_query_ids": critical_errors,
        }

    return {
        "overall": aggregate(normalized),
        "by_case": {
            case_key: aggregate(
                [row for row in normalized if row["case_key"] == case_key]
            )
            for case_key in ("DELL", "MU", "NVDA")
        },
        "metric_digest": canonical_digest(normalized),
    }


def compile_quantized_shadow_decision(
    *,
    baseline_embedding: Mapping[str, Any],
    challenger_embedding: Mapping[str, Any],
    baseline_reranker: Mapping[str, Any],
    challenger_reranker: Mapping[str, Any],
    gates: Mapping[str, Any],
) -> dict[str, Any]:
    values = {
        "baseline_embedding": deepcopy(dict(baseline_embedding)),
        "challenger_embedding": deepcopy(dict(challenger_embedding)),
        "baseline_reranker": deepcopy(dict(baseline_reranker)),
        "challenger_reranker": deepcopy(dict(challenger_reranker)),
    }
    overall = {key: value["overall"] for key, value in values.items()}
    embedding_floor = float(gates["embedding_pairwise_accuracy_minimum"])
    reranker_floor = float(gates["reranker_pairwise_accuracy_minimum"])
    reranker_delta = float(gates["reranker_pairwise_improvement_minimum"])
    embedding_credible = (
        overall["challenger_embedding"]["pairwise_accuracy"] is not None
        and overall["baseline_embedding"]["pairwise_accuracy"] is not None
        and overall["challenger_embedding"]["pairwise_accuracy"] >= embedding_floor
        and overall["challenger_embedding"]["pairwise_accuracy"]
        >= overall["baseline_embedding"]["pairwise_accuracy"]
    )
    reranker_credible = (
        overall["challenger_reranker"]["pairwise_accuracy"] is not None
        and overall["baseline_reranker"]["pairwise_accuracy"] is not None
        and overall["challenger_reranker"]["pairwise_accuracy"] >= reranker_floor
        and overall["challenger_reranker"]["pairwise_accuracy"]
        - overall["baseline_reranker"]["pairwise_accuracy"]
        >= reranker_delta
    )
    def no_regression(
        baseline: Mapping[str, Any],
        challenger: Mapping[str, Any],
        case_key: str,
    ) -> bool:
        baseline_score = baseline["by_case"][case_key]["pairwise_accuracy"]
        challenger_score = challenger["by_case"][case_key]["pairwise_accuracy"]
        return (
            isinstance(baseline_score, (int, float))
            and not isinstance(baseline_score, bool)
            and isinstance(challenger_score, (int, float))
            and not isinstance(challenger_score, bool)
            and math.isfinite(float(baseline_score))
            and math.isfinite(float(challenger_score))
            and challenger_score >= baseline_score
        )

    no_case_regression = all(
        no_regression(baseline_embedding, challenger_embedding, case_key)
        and no_regression(baseline_reranker, challenger_reranker, case_key)
        for case_key in ("DELL", "MU", "NVDA")
    )
    credible = embedding_credible and reranker_credible and no_case_regression
    body = {
        "decision": (
            "quantized_4b_shadow_credible_requires_fresh_natural_pool_eval"
            if credible
            else "quantized_4b_shadow_not_credible_on_controlled_pool"
        ),
        "embedding_credible": embedding_credible,
        "reranker_credible": reranker_credible,
        "no_case_pairwise_regression": no_case_regression,
        "runtime_promotion_authorized": False,
        "S1_qualification_authorized": False,
        "natural_candidate_recall_proved": False,
        "controlled_pool_only": True,
    }
    return {**body, "decision_digest": canonical_digest(body)}


__all__ = [
    "QUANTIZED_MANIFEST_NAME",
    "QUANTIZED_MANIFEST_SCHEMA",
    "TOOL_MANIFEST_NAME",
    "TOOL_MANIFEST_SCHEMA",
    "build_qwen3_reranker_prompt",
    "compile_controlled_ranking_metrics",
    "compile_quantized_shadow_decision",
    "llama_cpp_tool_identity",
    "parse_llama_yes_no_margin",
    "quantized_gguf_identity",
    "sha256_file",
]
