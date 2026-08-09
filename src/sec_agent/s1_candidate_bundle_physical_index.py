from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import pickle
import platform
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Callable, Mapping, Sequence


POLICY_SCHEMA = "fin_ia_0_1_3_s1_candidate_bundle_physical_index_build_policy_v1_0"
IMPLEMENTATION_PROOF_SCHEMA = (
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_implementation_proof_v1_0"
)
AUTHORITY_SCHEMA = (
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_build_authority_v1_0"
)
TERMINAL_RESULT_SCHEMA = (
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_build_result_v1_0"
)
PRIVATE_MANIFEST_SCHEMA = (
    "fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_private_manifest_v1_0"
)
RUN_SCOPE = "S1_IMMUTABLE_SUPPLEMENTAL_DENSE_INDEX_REPLACEMENT_BUILD"
EXPECTED_CASE_KEYS = ("DELL", "MU", "NVDA", "ORCL", "ASML", "ANET")


class CandidateBundlePhysicalIndexError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CandidateBundlePhysicalIndexError(code)


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "candidate_bundle_physical_json_object_required")
    return value


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _resolve_repo_ref(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_physical_index_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(path)
    _require(
        policy.get("schema_version") == POLICY_SCHEMA
        and policy.get("implementation_proof_schema") == IMPLEMENTATION_PROOF_SCHEMA
        and policy.get("authority_schema") == AUTHORITY_SCHEMA
        and policy.get("terminal_result_schema") == TERMINAL_RESULT_SCHEMA
        and policy.get("contract_ref")
        == "fin_0_1_3.S1.candidate_bundle_physical_sparse_dense_index:v1"
        and policy.get("run_scope") == RUN_SCOPE,
        "candidate_bundle_physical_policy_identity_invalid",
    )
    inputs = dict(policy.get("immutable_inputs") or {})
    for stem in ("manifest_result", "manifest_clean_proof"):
        ref = str(inputs.get(f"{stem}_ref") or "")
        target = _resolve_repo_ref(root, ref)
        _require(
            bool(ref)
            and target.is_file()
            and normalized_sha256(target) == str(inputs.get(f"{stem}_sha256") or ""),
            f"candidate_bundle_physical_input_binding_invalid:{stem}",
        )
        payload = _read_json(target)
        expected_digest = str(inputs.get(f"{stem}_digest") or "")
        observed_digest = str(
            payload.get("proof_digest")
            or payload.get("result_digest")
            or ""
        )
        _require(
            observed_digest == expected_digest,
            f"candidate_bundle_physical_input_digest_invalid:{stem}",
        )
    result = _read_json(_resolve_repo_ref(root, str(inputs["manifest_result_ref"])))
    proof = _read_json(_resolve_repo_ref(root, str(inputs["manifest_clean_proof_ref"])))
    _require(
        result.get("status")
        == "terminal_succeeded_zero_call_candidate_bundle_index_manifest"
        and int(result.get("selection_summary", {}).get("primary_spec_count") or 0)
        == int(inputs.get("expected_spec_count") or 0)
        and result.get("selection_summary", {}).get("manifest_spec_digest")
        == inputs.get("manifest_spec_digest")
        and result.get("private_manifest", {}).get("digest")
        == inputs.get("private_manifest_file_sha256")
        and result.get("private_manifest", {}).get("manifest_digest")
        == inputs.get("private_manifest_digest")
        and proof.get("stage_acceptance", {}).get(
            "ubuntu_real_build_authority_decision_admitted"
        )
        is True
        and proof.get("stage_acceptance", {}).get("real_embedding_or_index_build")
        is False,
        "candidate_bundle_physical_upstream_acceptance_invalid",
    )
    runtime = dict(policy.get("runtime_contract") or {})
    required_packages = dict(runtime.get("required_packages") or {})
    _require(
        runtime.get("distribution") == "Ubuntu-22.04"
        and runtime.get("runtime") == "WSL2"
        and runtime.get("filesystem_role")
        == "linux_root_filesystem_not_windows_mounted_drive"
        and runtime.get("embedding_device") == "cpu"
        and int(runtime.get("embedding_dimension") or 0) == 1024
        and int(runtime.get("embedding_batch_size") or 0) == 8
        and required_packages
        == {
            "torch": "2.10.0+cpu",
            "transformers": "5.2.0",
            "sentence-transformers": "5.2.3",
            "pymilvus": "3.0.0",
            "milvus-lite": "3.0",
            "rank-bm25": "0.2.2",
            "numpy": "2.2.6",
            "scikit-learn": "1.7.2",
        },
        "candidate_bundle_physical_runtime_contract_invalid",
    )
    index = dict(policy.get("index_contract") or {})
    _require(
        index.get("shared_manifest_for_sparse_and_dense") is True
        and index.get("sparse_kind") == "object_bm25"
        and index.get("dense_kind") == "bge_m3_milvus_lite"
        and index.get("candidate_state") == "candidate_only_not_evidence"
        and index.get("historical_indexes_read_only") is True,
        "candidate_bundle_physical_index_contract_invalid",
    )
    target = dict(policy.get("private_target") or {})
    prefix = str(target.get("target_prefix") or "")
    working = str(target.get("working_root") or "")
    final = str(target.get("final_root") or "")
    _require(
        prefix.startswith("/home/william/.cache/fin_insight/")
        and working.startswith(prefix + "/")
        and final.startswith(prefix + "/")
        and working != final
        and target.get("working_and_final_must_not_preexist") is True
        and target.get("publish_by_same_filesystem_rename") is True,
        "candidate_bundle_physical_target_contract_invalid",
    )
    ceiling = dict(policy.get("execution_ceiling") or {})
    expected_count = int(inputs["expected_spec_count"])
    expected_batches = math.ceil(expected_count / int(runtime["embedding_batch_size"]))
    _require(
        int(ceiling.get("maximum_executions") or 0) == 1
        and ceiling.get("automatic_retry") is False
        and int(ceiling.get("embedding_vectors") or 0) == expected_count
        and int(ceiling.get("sparse_records") or 0) == expected_count
        and int(ceiling.get("milvus_inserted_vectors") or 0) == expected_count
        and int(ceiling.get("embedding_batches") or 0) == expected_batches
        and int(ceiling.get("milvus_insert_batches") or 0) == expected_batches,
        "candidate_bundle_physical_execution_ceiling_invalid",
    )
    for key in (
        "network",
        "provider",
        "llm_model",
        "document_fetch",
        "vector_search",
        "rerank",
        "evidence_promotion",
    ):
        _require(
            int(ceiling.get(key, -1)) == 0,
            "candidate_bundle_physical_forbidden_call_budget_invalid",
        )
    boundaries = dict(policy.get("stage_boundaries") or {})
    for key in (
        "may_write_historical_index",
        "may_search_vectors",
        "may_rerank",
        "may_promote_evidence",
        "may_run_external_supplement",
        "may_call_deepseek",
        "may_claim_retrieval_quality",
        "may_claim_workbench_integration",
        "may_accept_release",
    ):
        _require(
            boundaries.get(key) is False,
            "candidate_bundle_physical_stage_boundary_invalid",
        )
    return policy


def load_bound_private_manifest(
    policy: Mapping[str, Any],
    *,
    repo_root: str | Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    root = Path(repo_root).resolve()
    inputs = dict(policy["immutable_inputs"])
    manifest_path = (
        _resolve_repo_ref(root, str(inputs["private_manifest_root_ref"]))
        / str(inputs["private_manifest_object_key"])
    )
    _require(
        manifest_path.is_file()
        and file_sha256(manifest_path)
        == str(inputs["private_manifest_file_sha256"]),
        "candidate_bundle_physical_private_manifest_file_invalid",
    )
    manifest = _read_json(manifest_path)
    body = {key: value for key, value in manifest.items() if key != "manifest_digest"}
    _require(
        manifest.get("schema_version") == PRIVATE_MANIFEST_SCHEMA
        and manifest.get("candidate_state") == "candidate_only_not_evidence"
        and canonical_digest(body) == str(manifest.get("manifest_digest") or "")
        and manifest.get("manifest_digest") == inputs["private_manifest_digest"],
        "candidate_bundle_physical_private_manifest_digest_invalid",
    )
    specs = [dict(item) for item in manifest.get("specs") or []]
    validate_candidate_specs(specs, policy=policy, require_manifest_digest=True)
    return manifest, specs


def validate_candidate_specs(
    specs: Sequence[Mapping[str, Any]],
    *,
    policy: Mapping[str, Any],
    require_manifest_digest: bool = True,
) -> list[dict[str, Any]]:
    inputs = dict(policy["immutable_inputs"])
    rows = [dict(item) for item in specs]
    _require(
        len(rows) == int(inputs["expected_spec_count"])
        and (
            not require_manifest_digest
            or canonical_digest(rows) == inputs["manifest_spec_digest"]
        )
        and dict(Counter(str(item.get("case_key") or "") for item in rows))
        == dict(inputs["expected_specs_by_case"]),
        "candidate_bundle_physical_private_manifest_population_invalid",
    )
    identities: set[str] = set()
    for spec in rows:
        body = {key: value for key, value in spec.items() if key != "spec_digest"}
        identity = str(spec.get("vector_id") or "")
        _require(
            bool(identity)
            and identity not in identities
            and spec.get("candidate_state") == "bundle_candidate_only_not_evidence"
            and spec.get("index_lanes") == ["object_bm25", "bge_m3_milvus"]
            and canonical_digest(body) == str(spec.get("spec_digest") or "")
            and hashlib.sha256(str(spec.get("vector_text") or "").encode("utf-8")).hexdigest()
            == str(spec.get("vector_text_sha256") or ""),
            "candidate_bundle_physical_spec_integrity_invalid",
        )
        identities.add(identity)
    return rows


def candidate_spec_to_sparse_record(spec: Mapping[str, Any]) -> dict[str, Any]:
    period = str(spec.get("source_reporting_period_end") or "")
    year_match = re.match(r"(?P<year>\d{4})-", period)
    return {
        "object_id": str(spec["vector_id"]),
        "object_type": str(spec["object_type"]),
        "source_evidence_id": str(spec["source_record_id"]),
        "ticker": str(spec["case_key"]),
        "fiscal_year": int(year_match.group("year")) if year_match else None,
        "section": ",".join(str(item) for item in spec.get("slot_ids") or []),
        "subsection": ",".join(str(item) for item in spec.get("facet_ids") or []),
        "source_type": "candidate_bundle_manifest",
        "source_tier": str(spec["quality_tier"]),
        "publication_date": str(spec["publication_date"]),
        "period_end": period,
        "period": period,
        "preview": str(spec["vector_text"]),
        "search_text": str(spec["vector_text"]),
        "metadata": {
            "candidate_state": str(spec["candidate_state"]),
            "target_id": str(spec["target_id"]),
            "spec_digest": str(spec["spec_digest"]),
            "vector_text_sha256": str(spec["vector_text_sha256"]),
            "source_locator": str(spec["source_locator"]),
            "slot_ids": list(spec.get("slot_ids") or []),
            "facet_ids": list(spec.get("facet_ids") or []),
        },
    }


def tokenize_candidate_text(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9&'/-]*", text.lower())


def build_object_bm25_from_specs(
    specs: Sequence[Mapping[str, Any]],
    *,
    output_dir: str | Path,
    bm25_factory: Callable[[list[list[str]]], Any] | None = None,
) -> dict[str, Any]:
    target = Path(output_dir)
    _require(
        not target.exists(),
        "candidate_bundle_physical_sparse_target_preexists",
    )
    target.mkdir(parents=True, exist_ok=False)
    records = [candidate_spec_to_sparse_record(spec) for spec in specs]
    tokenized = [tokenize_candidate_text(str(record["search_text"])) for record in records]
    _require(
        all(tokens for tokens in tokenized),
        "candidate_bundle_physical_sparse_empty_document",
    )
    if bm25_factory is None:
        from rank_bm25 import BM25Okapi

        bm25_factory = BM25Okapi
    bm25 = bm25_factory(tokenized)
    records_payload = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for record in records
    ).encode("utf-8")
    _write_bytes_atomic(target / "records.slim.jsonl", records_payload)
    _write_bytes_atomic(target / "bm25.pkl", pickle.dumps(bm25, protocol=pickle.HIGHEST_PROTOCOL))
    metadata = {
        "schema_version": "fin_ia_candidate_bundle_object_bm25_metadata_v1_0",
        "index_name": "fin_ia_0_1_3_s1_candidate_bundle_object_bm25_v1",
        "index_type": "rank_bm25",
        "records": len(records),
        "record_file": "records.slim.jsonl",
        "record_digest": canonical_digest(records),
        "tokenized_corpus_digest": canonical_digest(tokenized),
        "vector_identity_digest": canonical_digest(
            [str(item["object_id"]) for item in records]
        ),
        "candidate_state": "candidate_only_not_evidence",
    }
    _write_json_atomic(target / "metadata.json", metadata)
    metadata["files"] = {
        name: {
            "bytes": (target / name).stat().st_size,
            "sha256": file_sha256(target / name),
        }
        for name in ("records.slim.jsonl", "bm25.pkl", "metadata.json")
    }
    return metadata


class LocalBgeM3Embedder:
    def __init__(
        self,
        *,
        model_path: str,
        expected_dimension: int,
        batch_size: int,
        normalize: bool,
        device: str,
    ) -> None:
        from sentence_transformers import SentenceTransformer

        started = time.perf_counter()
        self.model = SentenceTransformer(
            model_path,
            device=device,
            local_files_only=True,
        )
        self.load_ms = round((time.perf_counter() - started) * 1000, 3)
        self.expected_dimension = expected_dimension
        self.batch_size = batch_size
        self.normalize = normalize
        self.device = device
        self.calls = 0
        self.vectors = 0
        self.embedding_ms = 0.0

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        started = time.perf_counter()
        value = self.model.encode(
            list(texts),
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize,
        )
        rows = value.tolist()
        self.embedding_ms += (time.perf_counter() - started) * 1000
        self.calls += 1
        self.vectors += len(rows)
        _require(
            len(rows) == len(texts)
            and all(len(row) == self.expected_dimension for row in rows),
            "candidate_bundle_physical_embedding_shape_invalid",
        )
        return rows


class MilvusCandidateBundleWriter:
    def __init__(self, *, uri: str) -> None:
        from pymilvus import DataType, MilvusClient

        self.uri = uri
        self.client_cls = MilvusClient
        self.data_type = DataType
        self.client: Any | None = None
        self.collection_name = ""
        self.calls = {
            "database_create": 0,
            "collection_create": 0,
            "insert_batches": 0,
            "inserted_vectors": 0,
            "flush": 0,
            "count": 0,
            "metadata_query": 0,
            "reopen": 0,
        }

    def begin(self, *, collection_name: str, embedding_dimension: int) -> None:
        self.client = self.client_cls(uri=self.uri)
        self.calls["database_create"] += 1
        _require(
            not self.client.has_collection(collection_name=collection_name),
            "candidate_bundle_physical_dense_collection_preexists",
        )
        schema = self.client_cls.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(
            field_name="vector_id",
            datatype=self.data_type.VARCHAR,
            is_primary=True,
            max_length=128,
        )
        schema.add_field(
            field_name="embedding",
            datatype=self.data_type.FLOAT_VECTOR,
            dim=embedding_dimension,
        )
        for name, maximum in (
            ("case_key", 16),
            ("target_id", 1024),
            ("object_type", 64),
            ("quality_tier", 80),
            ("candidate_state", 80),
            ("slot_ids_json", 2048),
            ("facet_ids_json", 4096),
            ("source_reporting_period_end", 32),
            ("source_locator", 4096),
            ("spec_digest", 64),
            ("vector_text_sha256", 64),
            ("preview", 8192),
        ):
            schema.add_field(
                field_name=name,
                datatype=self.data_type.VARCHAR,
                max_length=maximum,
            )
        indexes = self.client_cls.prepare_index_params()
        indexes.add_index(
            field_name="embedding",
            metric_type="COSINE",
            index_type="FLAT",
        )
        self.client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=indexes,
        )
        self.collection_name = collection_name
        self.calls["collection_create"] += 1

    def insert(
        self,
        specs: Sequence[Mapping[str, Any]],
        vectors: Sequence[Sequence[float]],
    ) -> int:
        _require(
            self.client is not None and len(specs) == len(vectors),
            "candidate_bundle_physical_dense_insert_shape_invalid",
        )
        rows = [
            _milvus_row(spec, vector)
            for spec, vector in zip(specs, vectors, strict=True)
        ]
        result = self.client.insert(collection_name=self.collection_name, data=rows)
        acknowledged = int((result or {}).get("insert_count") or 0)
        _require(
            acknowledged == len(rows),
            "candidate_bundle_physical_dense_partial_insert",
        )
        self.calls["insert_batches"] += 1
        self.calls["inserted_vectors"] += acknowledged
        return acknowledged

    def finalize(self) -> int:
        _require(self.client is not None, "candidate_bundle_physical_dense_not_started")
        self.client.flush(collection_name=self.collection_name)
        self.calls["flush"] += 1
        self.client.flush(collection_name=self.collection_name)
        self.calls["flush"] += 1
        stats = self.client.get_collection_stats(collection_name=self.collection_name)
        self.calls["count"] += 1
        return int((stats or {}).get("row_count") or 0)

    def close(self) -> None:
        if self.client is not None:
            close = getattr(self.client, "close", None)
            if callable(close):
                close()
            self.client = None

    def reopen_and_read_identities(self, *, limit: int) -> list[dict[str, Any]]:
        self.close()
        client = self.client_cls(uri=self.uri)
        self.calls["reopen"] += 1
        try:
            stats = client.get_collection_stats(collection_name=self.collection_name)
            self.calls["count"] += 1
            count = int((stats or {}).get("row_count") or 0)
            rows = client.query(
                collection_name=self.collection_name,
                filter='vector_id != ""',
                output_fields=["vector_id", "case_key", "spec_digest"],
                limit=limit,
            )
            self.calls["metadata_query"] += 1
            _require(
                count == len(rows),
                "candidate_bundle_physical_dense_reopen_count_mismatch",
            )
            return [dict(item) for item in rows]
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()


def _milvus_row(
    spec: Mapping[str, Any],
    vector: Sequence[float],
) -> dict[str, Any]:
    vector_text = str(spec.get("vector_text") or "")
    values = {
        "vector_id": str(spec["vector_id"]),
        "embedding": [float(value) for value in vector],
        "case_key": str(spec["case_key"]),
        "target_id": str(spec["target_id"]),
        "object_type": str(spec["object_type"]),
        "quality_tier": str(spec["quality_tier"]),
        "candidate_state": str(spec["candidate_state"]),
        "slot_ids_json": json.dumps(spec.get("slot_ids") or [], ensure_ascii=False),
        "facet_ids_json": json.dumps(spec.get("facet_ids") or [], ensure_ascii=False),
        "source_reporting_period_end": str(spec["source_reporting_period_end"]),
        "source_locator": str(spec["source_locator"]),
        "spec_digest": str(spec["spec_digest"]),
        "vector_text_sha256": str(spec["vector_text_sha256"]),
        "preview": vector_text[:8192],
    }
    maximums = {
        "vector_id": 128,
        "case_key": 16,
        "target_id": 1024,
        "object_type": 64,
        "quality_tier": 80,
        "candidate_state": 80,
        "slot_ids_json": 2048,
        "facet_ids_json": 4096,
        "source_reporting_period_end": 32,
        "source_locator": 4096,
        "spec_digest": 64,
        "vector_text_sha256": 64,
        "preview": 8192,
    }
    _require(
        all(len(str(values[key])) <= maximum for key, maximum in maximums.items()),
        "candidate_bundle_physical_dense_metadata_too_long",
    )
    return values


@dataclass
class FakeEmbedder:
    dimension: int
    calls: int = 0
    vectors: int = 0
    load_ms: float = 0.0
    embedding_ms: float = 0.0
    device: str = "fake"

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        self.vectors += len(texts)
        rows: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            base = [float(value) / 255.0 for value in digest]
            rows.append([base[index % len(base)] for index in range(self.dimension)])
        return rows


class FakeMilvusWriter:
    def __init__(self) -> None:
        self.collection_name = ""
        self.rows: list[dict[str, Any]] = []
        self.calls = {
            "database_create": 0,
            "collection_create": 0,
            "insert_batches": 0,
            "inserted_vectors": 0,
            "flush": 0,
            "count": 0,
            "metadata_query": 0,
            "reopen": 0,
        }

    def begin(self, *, collection_name: str, embedding_dimension: int) -> None:
        _require(embedding_dimension > 0, "candidate_bundle_physical_fake_dimension_invalid")
        self.collection_name = collection_name
        self.calls["database_create"] += 1
        self.calls["collection_create"] += 1

    def insert(
        self,
        specs: Sequence[Mapping[str, Any]],
        vectors: Sequence[Sequence[float]],
    ) -> int:
        rows = [
            _milvus_row(spec, vector)
            for spec, vector in zip(specs, vectors, strict=True)
        ]
        self.rows.extend(rows)
        self.calls["insert_batches"] += 1
        self.calls["inserted_vectors"] += len(rows)
        return len(rows)

    def finalize(self) -> int:
        self.calls["flush"] += 2
        self.calls["count"] += 1
        return len(self.rows)

    def close(self) -> None:
        return None

    def reopen_and_read_identities(self, *, limit: int) -> list[dict[str, Any]]:
        self.calls["reopen"] += 1
        self.calls["count"] += 1
        self.calls["metadata_query"] += 1
        return [
            {
                "vector_id": row["vector_id"],
                "case_key": row["case_key"],
                "spec_digest": row["spec_digest"],
            }
            for row in self.rows[:limit]
        ]


def execute_dense_build(
    specs: Sequence[Mapping[str, Any]],
    *,
    policy: Mapping[str, Any],
    embedder: Any,
    writer: Any,
) -> dict[str, Any]:
    validate_candidate_specs(specs, policy=policy, require_manifest_digest=True)
    runtime = dict(policy["runtime_contract"])
    index = dict(policy["index_contract"])
    ceiling = dict(policy["execution_ceiling"])
    batch_size = int(runtime["embedding_batch_size"])
    writer.begin(
        collection_name=str(index["dense_collection_name"]),
        embedding_dimension=int(runtime["embedding_dimension"]),
    )
    acknowledged = 0
    for start in range(0, len(specs), batch_size):
        batch = list(specs[start : start + batch_size])
        vectors = embedder.encode([str(item["vector_text"]) for item in batch])
        acknowledged += writer.insert(batch, vectors)
    count_before_close = writer.finalize()
    rows = writer.reopen_and_read_identities(limit=len(specs) + 1)
    expected_identities = sorted(
        (str(item["vector_id"]), str(item["case_key"]), str(item["spec_digest"]))
        for item in specs
    )
    observed_identities = sorted(
        (str(item["vector_id"]), str(item["case_key"]), str(item["spec_digest"]))
        for item in rows
    )
    _require(
        acknowledged == len(specs)
        and count_before_close == len(specs)
        and expected_identities == observed_identities,
        "candidate_bundle_physical_dense_terminal_identity_mismatch",
    )
    calls = dict(writer.calls)
    expected_batches = math.ceil(len(specs) / batch_size)
    _require(
        int(embedder.calls) == expected_batches
        and int(embedder.vectors) == len(specs)
        and calls
        == {
            "database_create": 1,
            "collection_create": 1,
            "insert_batches": expected_batches,
            "inserted_vectors": len(specs),
            "flush": 2,
            "count": 2,
            "metadata_query": 1,
            "reopen": 1,
        }
        and int(ceiling["embedding_batches"]) == expected_batches,
        "candidate_bundle_physical_dense_call_ceiling_mismatch",
    )
    return {
        "terminal_count": len(specs),
        "batch_count": expected_batches,
        "identity_digest": canonical_digest(expected_identities),
        "writer_calls": calls,
        "embedding_calls": int(embedder.calls),
        "embedding_vectors": int(embedder.vectors),
    }


def execute_fake_physical_index_proof(
    *,
    policy: Mapping[str, Any],
    specs: Sequence[Mapping[str, Any]],
    output_root: str | Path,
) -> dict[str, Any]:
    validate_candidate_specs(specs, policy=policy, require_manifest_digest=True)
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=False)
    sparse = build_object_bm25_from_specs(specs, output_dir=root / "object_bm25")
    embedder = FakeEmbedder(dimension=int(policy["runtime_contract"]["embedding_dimension"]))
    writer = FakeMilvusWriter()
    dense = execute_dense_build(
        specs,
        policy=policy,
        embedder=embedder,
        writer=writer,
    )
    _require(
        int(sparse["records"]) == dense["terminal_count"] == len(specs),
        "candidate_bundle_physical_sparse_dense_population_mismatch",
    )
    return {
        "sparse": sparse,
        "dense": dense,
        "shared_identity_digest": dense["identity_digest"],
    }


def inspect_bound_linux_environment(policy: Mapping[str, Any]) -> dict[str, Any]:
    runtime = dict(policy["runtime_contract"])
    _require(
        platform.system().lower() == "linux",
        "candidate_bundle_physical_linux_required",
    )
    packages = {
        name: importlib.metadata.version(name)
        for name in runtime["required_packages"]
    }
    _require(
        packages == dict(runtime["required_packages"]),
        "candidate_bundle_physical_package_version_drift",
    )
    freeze = subprocess.check_output(
        [sys.executable, "-m", "pip", "freeze"],
        text=True,
        encoding="utf-8",
    )
    model_root = Path(str(runtime["embedding_model_linux_ref"]))
    model_files: list[dict[str, Any]] = []
    for expected in runtime["required_model_files"]:
        target = model_root / str(expected["path"])
        _require(
            target.is_file()
            and target.stat().st_size == int(expected["bytes"])
            and file_sha256(target) == str(expected["sha256"]),
            "candidate_bundle_physical_model_file_drift",
        )
        model_files.append(dict(expected))
    targets = dict(policy["private_target"])
    working = Path(str(targets["working_root"]))
    final = Path(str(targets["final_root"]))
    prefix = Path(str(targets["target_prefix"]))
    anchor = prefix
    while not anchor.exists() and anchor != anchor.parent:
        anchor = anchor.parent
    disk = shutil.disk_usage(anchor)
    distribution_fingerprints = {
        name: _distribution_fingerprint(name)
        for name in ("pymilvus", "milvus-lite", "sentence-transformers", "transformers")
    }
    import milvus_lite.storage.manifest as milvus_manifest

    milvus_manifest_path = Path(str(milvus_manifest.__file__)).resolve()
    milvus_manifest_text = milvus_manifest_path.read_text(
        encoding="utf-8", errors="replace"
    )
    if "os.replace(" in milvus_manifest_text:
        commit_primitive = "os.replace"
    elif "os.rename(" in milvus_manifest_text:
        commit_primitive = "os.rename"
    else:
        commit_primitive = "unknown"
    import torch

    result = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "packages": packages,
        "pip_freeze_sha256": hashlib.sha256(freeze.encode("utf-8")).hexdigest(),
        "pip_freeze_line_count": len(freeze.splitlines()),
        "distribution_fingerprints": distribution_fingerprints,
        "milvus_manifest_source": {
            "path": milvus_manifest_path.as_posix(),
            "bytes": milvus_manifest_path.stat().st_size,
            "sha256": file_sha256(milvus_manifest_path),
            "commit_primitive": commit_primitive,
        },
        "model_root": model_root.as_posix(),
        "model_files": model_files,
        "embedding_device": "cpu",
        "torch_cuda_available_but_not_authorized": bool(torch.cuda.is_available()),
        "target": {
            "working_root": working.as_posix(),
            "working_root_absent": not working.exists(),
            "final_root": final.as_posix(),
            "final_root_absent": not final.exists(),
            "filesystem_anchor": anchor.as_posix(),
            "disk_free_bytes": disk.free,
        },
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "llm_model": 0,
            "embedding_model_loads": 0,
            "embedding_vectors": 0,
            "milvus_read": 0,
            "milvus_write": 0,
        },
    }
    _require(
        result["target"]["working_root_absent"]
        and result["target"]["final_root_absent"]
        and int(result["target"]["disk_free_bytes"]) >= 10 * 1024**3,
        "candidate_bundle_physical_target_or_disk_unqualified",
    )
    return result


def _distribution_fingerprint(name: str) -> dict[str, Any]:
    distribution = importlib.metadata.distribution(name)
    rows: list[dict[str, Any]] = []
    for relative in sorted(distribution.files or [], key=lambda value: str(value)):
        relative_text = str(relative).replace("\\", "/")
        if "__pycache__" in relative_text or relative_text.endswith((".pyc", ".pyo")):
            continue
        absolute = Path(distribution.locate_file(relative))
        if not absolute.is_file():
            continue
        rows.append(
            {
                "path": relative_text,
                "bytes": absolute.stat().st_size,
                "sha256": file_sha256(absolute),
            }
        )
    return {
        "distribution": name,
        "version": distribution.version,
        "file_count": len(rows),
        "total_bytes": sum(int(item["bytes"]) for item in rows),
        "tree_sha256": canonical_digest(rows),
    }


def environment_identity(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    target = dict(snapshot.get("target") or {})
    return {
        "platform": snapshot.get("platform"),
        "python": snapshot.get("python"),
        "python_executable": snapshot.get("python_executable"),
        "packages": snapshot.get("packages"),
        "pip_freeze_sha256": snapshot.get("pip_freeze_sha256"),
        "pip_freeze_line_count": snapshot.get("pip_freeze_line_count"),
        "distribution_fingerprints": snapshot.get("distribution_fingerprints"),
        "milvus_manifest_source": snapshot.get("milvus_manifest_source"),
        "model_root": snapshot.get("model_root"),
        "model_files": snapshot.get("model_files"),
        "embedding_device": snapshot.get("embedding_device"),
        "target": {
            "working_root": target.get("working_root"),
            "working_root_absent": target.get("working_root_absent"),
            "final_root": target.get("final_root"),
            "final_root_absent": target.get("final_root_absent"),
            "filesystem_anchor": target.get("filesystem_anchor"),
        },
    }


def validate_build_authority(
    authority: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    body = {key: value for key, value in authority.items() if key != "authority_digest"}
    environment = dict(authority.get("environment_qualification") or {})
    implementation = dict(authority.get("implementation") or {})
    target = dict(authority.get("private_target") or {})
    manifest = dict(authority.get("manifest_binding") or {})
    runtime = dict(policy["runtime_contract"])
    expected_target = dict(policy["private_target"])
    _require(
        authority.get("schema_version") == AUTHORITY_SCHEMA
        and authority.get("status") == "issued_unconsumed"
        and authority.get("run_scope") == RUN_SCOPE
        and authority.get("attempt_id") == policy.get("attempt_id")
        and canonical_digest(body) == str(authority.get("authority_digest") or "")
        and authority.get("policy_digest") == canonical_digest(policy)
        and int(authority.get("maximum_executions") or 0) == 1
        and authority.get("automatic_retry") is False
        and authority.get("execution_ceiling") == policy.get("execution_ceiling")
        and authority.get("preserved_boundaries") == policy.get("stage_boundaries")
        and implementation.get("clean") is True
        and implementation.get("synced") is True
        and int(implementation.get("ahead") or 0) == 0
        and int(implementation.get("behind") or 0) == 0
        and re.fullmatch(r"[0-9a-f]{40}", str(implementation.get("commit") or ""))
        is not None
        and bool(implementation.get("bindings"))
        and environment.get("qualified") is True
        and environment.get("python_executable") == runtime["python_executable"]
        and environment.get("packages") == runtime["required_packages"]
        and environment.get("model_files") == runtime["required_model_files"]
        and environment.get("embedding_device") == runtime["embedding_device"]
        and all(
            int(value) == 0
            for value in dict(environment.get("observed_calls") or {}).values()
        )
        and target.get("working_root") == expected_target["working_root"]
        and target.get("final_root") == expected_target["final_root"]
        and target.get("working_root_absent") is True
        and target.get("final_root_absent") is True
        and int(target.get("disk_free_bytes") or 0) >= 10 * 1024**3
        and int(manifest.get("spec_count") or 0)
        == int(policy["immutable_inputs"]["expected_spec_count"])
        and manifest.get("spec_digest")
        == policy["immutable_inputs"]["manifest_spec_digest"]
        and manifest.get("private_manifest_file_sha256")
        == policy["immutable_inputs"]["private_manifest_file_sha256"]
        and manifest.get("candidate_state") == "candidate_only_not_evidence",
        "candidate_bundle_physical_authority_invalid",
    )
    if repo_root is not None:
        root = Path(repo_root).resolve()
        for binding in implementation["bindings"]:
            ref = str(binding.get("ref") or "")
            target_path = _resolve_repo_ref(root, ref)
            _require(
                bool(ref)
                and target_path.is_file()
                and normalized_sha256(target_path)
                == str(binding.get("sha256") or ""),
                "candidate_bundle_physical_authority_binding_drift",
            )
    return dict(authority)


def materialize_terminal_result(
    *,
    policy: Mapping[str, Any],
    authority: Mapping[str, Any],
    repo_root: str | Path,
    output_path: str | Path,
    embedder_factory: Callable[..., Any] = LocalBgeM3Embedder,
    writer_factory: Callable[..., Any] = MilvusCandidateBundleWriter,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    output = Path(output_path)
    _require(not output.exists(), "candidate_bundle_physical_terminal_result_preexists")
    validate_build_authority(authority, policy=policy, repo_root=root)
    targets = dict(policy["private_target"])
    working = Path(str(targets["working_root"]))
    final = Path(str(targets["final_root"]))
    phase = "validate_fresh_targets"
    started = time.perf_counter()
    embedder: Any | None = None
    writer: Any | None = None
    try:
        phase = "requalify_bound_linux_environment"
        current_environment = inspect_bound_linux_environment(policy)
        _require(
            environment_identity(current_environment)
            == environment_identity(authority["environment_qualification"]),
            "candidate_bundle_physical_environment_drift_after_authority",
        )
        phase = "validate_fresh_targets"
        _require(
            not working.exists() and not final.exists(),
            "candidate_bundle_physical_target_preexists",
        )
        _manifest, specs = load_bound_private_manifest(policy, repo_root=root)
        working.parent.mkdir(parents=True, exist_ok=True)
        working.mkdir()
        phase = "build_object_bm25"
        sparse = build_object_bm25_from_specs(
            specs,
            output_dir=working / str(targets["sparse_subdir"]),
        )
        phase = "load_local_bge_m3"
        runtime = dict(policy["runtime_contract"])
        embedder = embedder_factory(
            model_path=str(runtime["embedding_model_linux_ref"]),
            expected_dimension=int(runtime["embedding_dimension"]),
            batch_size=int(runtime["embedding_batch_size"]),
            normalize=bool(runtime["normalize_embeddings"]),
            device=str(runtime["embedding_device"]),
        )
        phase = "build_bge_m3_milvus"
        dense_root = working / str(targets["dense_subdir"])
        dense_root.mkdir()
        database_path = dense_root / str(targets["milvus_db_filename"])
        writer = writer_factory(uri=str(database_path))
        dense = execute_dense_build(
            specs,
            policy=policy,
            embedder=embedder,
            writer=writer,
        )
        writer.close()
        _require(
            database_path.is_file(),
            "candidate_bundle_physical_dense_database_missing",
        )
        phase = "write_private_receipt"
        private_receipt_body = {
            "schema_version": "fin_ia_candidate_bundle_physical_private_receipt_v1_0",
            "attempt_id": str(policy["attempt_id"]),
            "manifest_spec_digest": str(
                policy["immutable_inputs"]["manifest_spec_digest"]
            ),
            "sparse": sparse,
            "dense": dense,
            "database": {
                "relative_path": (
                    Path(str(targets["dense_subdir"]))
                    / str(targets["milvus_db_filename"])
                ).as_posix(),
                "bytes": database_path.stat().st_size,
                "sha256": file_sha256(database_path),
            },
            "candidate_state": "candidate_only_not_evidence",
        }
        private_receipt = {
            **private_receipt_body,
            "receipt_digest": canonical_digest(private_receipt_body),
        }
        _write_json_atomic(working / "build_receipt.json", private_receipt)
        phase = "publish_linux_root"
        working.rename(final)
        final_database = (
            final
            / str(targets["dense_subdir"])
            / str(targets["milvus_db_filename"])
        )
        _require(
            final_database.is_file(),
            "candidate_bundle_physical_published_database_missing",
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        body = {
            "schema_version": TERMINAL_RESULT_SCHEMA,
            "contract_ref": policy["contract_ref"],
            "run_scope": RUN_SCOPE,
            "recorded_at": policy["recorded_at"],
            "attempt_id": policy["attempt_id"],
            "status": "terminal_succeeded_physical_sparse_dense_build",
            "automatic_retry": False,
            "authority_digest": authority["authority_digest"],
            "implementation_commit": authority["implementation"]["commit"],
            "manifest_spec_digest": policy["immutable_inputs"]["manifest_spec_digest"],
            "resource": {
                "embedding_model": runtime["embedding_model"],
                "embedding_device": str(embedder.device),
                "embedding_dimension": int(runtime["embedding_dimension"]),
                "model_load_ms": float(embedder.load_ms),
                "embedding_ms": round(float(embedder.embedding_ms), 3),
                "wall_time_ms": elapsed_ms,
                "environment_identity_digest": canonical_digest(
                    environment_identity(current_environment)
                ),
            },
            "build": {
                "sparse": sparse,
                "dense": dense,
                "private_final_root": final.as_posix(),
                "private_receipt_digest": private_receipt["receipt_digest"],
                "milvus_database_bytes": final_database.stat().st_size,
                "milvus_database_sha256": file_sha256(final_database),
            },
            "observed_calls": {
                "network": 0,
                "provider": 0,
                "llm_model": 0,
                "document_fetch": 0,
                "embedding_model_loads": 1,
                "embedding_batches": int(embedder.calls),
                "embedding_vectors": int(embedder.vectors),
                "milvus_database_creates": int(writer.calls["database_create"]),
                "milvus_collection_creates": int(writer.calls["collection_create"]),
                "milvus_insert_batches": int(writer.calls["insert_batches"]),
                "milvus_inserted_vectors": int(writer.calls["inserted_vectors"]),
                "milvus_flushes": int(writer.calls["flush"]),
                "milvus_count_reads": int(writer.calls["count"]),
                "milvus_metadata_queries": int(writer.calls["metadata_query"]),
                "vector_search": 0,
                "rerank": 0,
                "evidence_promotion": 0,
            },
            "stage_acceptance": {
                "physical_sparse_index": True,
                "physical_dense_index": True,
                "shared_population_integrity": True,
                "retrieval_quality": False,
                "workbench_integration": False,
                "evidence_pack": False,
                "external_residual_supplement": False,
                "deepseek_research": False,
                "release": False,
            },
            "known_boundary": (
                "Physical ObjectBM25 and BGE-M3/Milvus indexes contain the same 93 "
                "CandidateBundle objects. No vector search, ranking, Evidence promotion, "
                "external supplement, DeepSeek call, Workbench integration or release is proven."
            ),
        }
        result = {**body, "result_digest": canonical_digest(body)}
        _write_json_atomic(output, result)
        return result
    except Exception as exc:
        if writer is not None:
            try:
                writer.close()
            except Exception:
                pass
        body = {
            "schema_version": TERMINAL_RESULT_SCHEMA,
            "contract_ref": policy["contract_ref"],
            "run_scope": RUN_SCOPE,
            "recorded_at": policy["recorded_at"],
            "attempt_id": policy["attempt_id"],
            "status": "terminal_failed_physical_sparse_dense_build_no_retry",
            "automatic_retry": False,
            "authority_digest": authority["authority_digest"],
            "implementation_commit": authority["implementation"]["commit"],
            "failure": {
                "phase": phase,
                "error_type": type(exc).__name__,
                "error_code": getattr(exc, "code", str(exc)),
            },
            "private_state": {
                "working_root": working.as_posix(),
                "working_root_exists": working.exists(),
                "final_root": final.as_posix(),
                "final_root_exists": final.exists(),
            },
            "observed_calls": {
                "network": 0,
                "provider": 0,
                "llm_model": 0,
                "document_fetch": 0,
                "embedding_model_loads": int(embedder is not None),
                "embedding_batches": int(getattr(embedder, "calls", 0)),
                "embedding_vectors": int(getattr(embedder, "vectors", 0)),
                "milvus_database_creates": int(
                    getattr(writer, "calls", {}).get("database_create", 0)
                ),
                "milvus_collection_creates": int(
                    getattr(writer, "calls", {}).get("collection_create", 0)
                ),
                "milvus_insert_batches": int(
                    getattr(writer, "calls", {}).get("insert_batches", 0)
                ),
                "milvus_inserted_vectors": int(
                    getattr(writer, "calls", {}).get("inserted_vectors", 0)
                ),
                "vector_search": 0,
                "rerank": 0,
                "evidence_promotion": 0,
            },
            "stage_acceptance": {
                "physical_sparse_index": False,
                "physical_dense_index": False,
                "retrieval_quality": False,
                "release": False,
            },
            "known_boundary": (
                "This immutable failure consumes R1. The failed working root is preserved "
                "and no automatic retry or replacement attempt is authorized."
            ),
        }
        result = {**body, "result_digest": canonical_digest(body)}
        _write_json_atomic(output, result)
        return result


__all__ = [
    "AUTHORITY_SCHEMA",
    "CandidateBundlePhysicalIndexError",
    "FakeEmbedder",
    "FakeMilvusWriter",
    "IMPLEMENTATION_PROOF_SCHEMA",
    "POLICY_SCHEMA",
    "RUN_SCOPE",
    "TERMINAL_RESULT_SCHEMA",
    "build_object_bm25_from_specs",
    "canonical_digest",
    "execute_dense_build",
    "execute_fake_physical_index_proof",
    "file_sha256",
    "environment_identity",
    "inspect_bound_linux_environment",
    "load_bound_private_manifest",
    "load_physical_index_policy",
    "materialize_terminal_result",
    "normalized_sha256",
    "validate_candidate_specs",
    "validate_build_authority",
]
