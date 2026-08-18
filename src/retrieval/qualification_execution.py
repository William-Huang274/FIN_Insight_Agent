from __future__ import annotations

import gc
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .cross_encoder import cross_encoder_model_identity
from .embedding_runtime import local_model_identity
from .evidence_role import evaluate_evidence_role
from .query_plan import QueryLane, canonical_digest


class QualificationExecutionError(ValueError):
    """The qualification execution surface drifted from its frozen inputs."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise QualificationExecutionError(f"json_object_required:{path.name}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise QualificationExecutionError(
                f"jsonl_object_required:{path.name}:{line_number}"
            )
        output.append(value)
    return output


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def load_policy_lineage(path: Path, *, repo_root: Path) -> dict[str, Any]:
    def load(current: Path, lineage: tuple[Path, ...]) -> dict[str, Any]:
        resolved = current.resolve()
        if resolved in lineage:
            raise QualificationExecutionError("candidate_policy_lineage_cycle")
        raw = read_json(resolved)
        schema = raw.get("schema_version")
        if schema == "fin_ia_s1_vs3_candidate_ranking_policy_v1_0":
            return raw
        if schema != "fin_ia_s1_vs3_candidate_ranking_policy_v1_1":
            raise QualificationExecutionError("candidate_policy_schema_invalid")
        parent = repo_root / str(raw.get("parent_policy_ref") or "")
        expected = str(raw.get("parent_policy_sha256_lf") or "")
        actual = hashlib.sha256(parent.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        if actual != expected:
            raise QualificationExecutionError("candidate_policy_parent_digest_drift")
        base = load(parent, (*lineage, resolved))
        merged = dict(base)
        merged.update(
            {
                "schema_version": schema,
                "status": raw["status"],
                "recorded_at": raw["recorded_at"],
                "experiment_id": raw["experiment_id"],
            }
        )
        for target, override in (
            ("bound_inputs", "bound_input_overrides"),
            ("candidate_contract", "candidate_contract_overrides"),
            ("decision_gates", "decision_gate_overrides"),
            ("token_budget_basis", "token_budget_basis_overrides"),
            ("authority", "authority_overrides"),
        ):
            values = dict(base.get(target) or {})
            values.update(raw.get(override) or {})
            merged[target] = values
        return merged

    return load(path, ())


def model_identities(
    *, model_policy: Mapping[str, Any], expected_digests: Mapping[str, str]
) -> tuple[dict[str, Any], dict[str, Path]]:
    paths = {
        key: Path(str(model_policy[key]["local_directory"])).resolve()
        for key in ("bge_embedding", "qwen_embedding", "bge_reranker", "qwen_reranker")
    }
    identities = {
        "bge_embedding": local_model_identity(paths["bge_embedding"], "BAAI/bge-m3"),
        "qwen_embedding": local_model_identity(
            paths["qwen_embedding"], "Qwen/Qwen3-Embedding-0.6B"
        ),
        "bge_reranker": cross_encoder_model_identity(paths["bge_reranker"]),
        "qwen_reranker": cross_encoder_model_identity(
            paths["qwen_reranker"], model_id="Qwen/Qwen3-Reranker-0.6B"
        ),
    }
    for key, identity in identities.items():
        if str(identity["model_digest"]) != str(expected_digests.get(key) or ""):
            raise QualificationExecutionError(f"qualification_model_digest_drift:{key}")
    return identities, paths


def empty_cuda() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def need_slices(counts: Sequence[int]) -> list[slice]:
    output: list[slice] = []
    offset = 0
    for count in counts:
        output.append(slice(offset, offset + count))
        offset += count
    return output


def combined_role_evaluation(
    *,
    candidate_id: str,
    selected_need_ids: Sequence[str],
    need_to_lane: Mapping[str, QueryLane],
    objects_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    row = objects_by_id[candidate_id]
    base = row["base_object_view"]
    evaluations = []
    for need_id in selected_need_ids:
        lane = need_to_lane[need_id]
        value = evaluate_evidence_role(
            {
                "ticker": base.get("ticker"),
                "section": base.get("section"),
                "subsection": base.get("subsection"),
                "source_type": base.get("source_type"),
                "object_kind": row.get("object_kind"),
                "document_text": row.get("model_text"),
                "structured_projection": row.get("structured_projection"),
            },
            slot_id=lane.slot_id,
            facet_id=lane.facet_id,
            subject_ticker=lane.subject_ticker,
            evidence_owner_ticker=lane.evidence_owner_tickers[0],
            relationship_direction=lane.relationship_constraints[0],
        ).as_dict()
        evaluations.append({"need_id": need_id, "facet_id": lane.facet_id, **value})
    tier = {"incompatible": 0, "abstain": 1, "compatible": 2}
    best = max(
        evaluations,
        key=lambda value: (tier[str(value["compatibility"])], str(value["need_id"])),
    )
    return {
        "compiled_object_id": candidate_id,
        "compatibility": best["compatibility"],
        "best_need_id": best["need_id"],
        "evaluations": evaluations,
        "candidate_not_evidence": True,
    }


def score_cache_key(
    *,
    scorer_id: str,
    model_digest: str,
    pair_manifest_digest: str,
    maximum_sequence_length: int,
    instruction: str = "",
) -> str:
    return canonical_digest(
        {
            "schema_version": "fin_ia_local_reranker_score_cache_key_v1_0",
            "scorer_id": scorer_id,
            "model_digest": model_digest,
            "pair_manifest_digest": pair_manifest_digest,
            "maximum_sequence_length": maximum_sequence_length,
            "instruction": instruction,
        }
    )


def load_score_cache(
    path: Path, *, cache_key: str, expected_count: int
) -> list[float] | None:
    if not path.is_file():
        return None
    raw = read_json(path)
    if (
        raw.get("schema_version") != "fin_ia_local_reranker_score_cache_v1_0"
        or raw.get("cache_key") != cache_key
        or raw.get("score_count") != expected_count
    ):
        return None
    scores = [float(value) for value in raw.get("scores") or ()]
    if len(scores) != expected_count or not all(np.isfinite(value) for value in scores):
        return None
    return scores


def write_score_cache(
    path: Path,
    *,
    cache_key: str,
    pair_manifest_digest: str,
    scores: Sequence[float],
) -> None:
    write_json(
        path,
        {
            "schema_version": "fin_ia_local_reranker_score_cache_v1_0",
            "cache_key": cache_key,
            "pair_manifest_digest": pair_manifest_digest,
            "score_count": len(scores),
            "scores": [float(value) for value in scores],
        },
    )


__all__ = [
    "QualificationExecutionError",
    "combined_role_evaluation",
    "empty_cuda",
    "load_policy_lineage",
    "load_score_cache",
    "model_identities",
    "need_slices",
    "read_json",
    "read_jsonl",
    "score_cache_key",
    "sha256_file",
    "write_json",
    "write_score_cache",
]
