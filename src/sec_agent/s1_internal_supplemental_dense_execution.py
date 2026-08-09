from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.project_os_preflight import run_project_os_preflight
from sec_agent.s1_internal_supplemental_dense_index import (
    RUN_SCOPE,
    compile_supplemental_vector_specs,
    execute_index_build_plan,
    load_supplemental_dense_index_policy,
    validate_supplemental_dense_index_zero_call_proof,
    validate_target_isolation,
)


EXECUTION_POLICY_SCHEMA = (
    "fin_ia_0_1_3_s1_internal_supplemental_dense_execution_policy_v1_0"
)
IMPLEMENTATION_PROOF_SCHEMA = (
    "fin_ia_0_1_3_s1_internal_supplemental_dense_"
    "execution_implementation_proof_v1_0"
)
TERMINAL_RESULT_SCHEMA = (
    "fin_ia_0_1_3_s1_internal_supplemental_dense_execution_result_v1_0"
)
PRESENCE_RESULT_SCHEMA = (
    "fin_ia_0_1_3_s1_internal_supplemental_dense_real_presence_proof_v1_0"
)
AUTHORITY_SCHEMA = (
    "fin_ia_0_1_3_s1_internal_supplemental_dense_build_authority_v1_0"
)
REQUIRED_IMPLEMENTATION_BINDING_REFS = (
    "configs/runtime/fin_ia_0_1_3_s1_internal_supplemental_dense_execution_policy_v1_0.json",
    "configs/releases/fin_ia_0_1_3_s1_internal_supplemental_dense_execution_implementation_proof_v1_0.json",
    "configs/releases/fin_ia_0_1_3_s1_internal_supplemental_dense_index_zero_call_proof_v1_0.json",
    "src/sec_agent/s1_internal_supplemental_dense_index.py",
    "src/sec_agent/s1_internal_supplemental_dense_execution.py",
    "scripts/releases/run_fin_ia_0_1_3_s1_internal_supplemental_dense_build_r1.py",
    "scripts/releases/materialize_fin_ia_0_1_3_s1_internal_supplemental_dense_real_presence_proof_v1_0.py",
)


class S1InternalSupplementalDenseExecutionError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S1InternalSupplementalDenseExecutionError(code)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "supplemental_dense_execution_json_object_required")
    return value


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    _require(
        result.returncode == 0,
        f"supplemental_dense_git_command_failed:{args[0] if args else 'unknown'}",
    )
    return result.stdout.strip()


def clean_synced_git_state(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    head = _git(root, "rev-parse", "HEAD")
    branch = _git(root, "branch", "--show-current")
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    upstream = _git(root, "rev-parse", "--abbrev-ref", "@{upstream}")
    ahead = int(_git(root, "rev-list", "--count", "@{upstream}..HEAD") or 0)
    behind = int(_git(root, "rev-list", "--count", "HEAD..@{upstream}") or 0)
    return {
        "head": head,
        "branch": branch,
        "upstream": upstream,
        "clean": status == "",
        "ahead": ahead,
        "behind": behind,
        "synced": ahead == 0 and behind == 0,
    }


def load_supplemental_dense_execution_policy(
    path: str | Path, *, repo_root: str | Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path))
    _require(
        policy.get("schema_version") == EXECUTION_POLICY_SCHEMA
        and policy.get("implementation_proof_schema") == IMPLEMENTATION_PROOF_SCHEMA
        and policy.get("terminal_result_schema") == TERMINAL_RESULT_SCHEMA
        and policy.get("presence_result_schema") == PRESENCE_RESULT_SCHEMA
        and policy.get("authority_schema") == AUTHORITY_SCHEMA
        and policy.get("run_scope") == RUN_SCOPE
        and policy.get("binding_hash_profile")
        == "sha256_utf8_lf_normalized_v1",
        "supplemental_dense_execution_policy_identity_invalid",
    )
    immutable = dict(policy.get("immutable_inputs") or {})
    for stem in ("build_contract_policy", "zero_call_proof"):
        ref = str(immutable.get(f"{stem}_ref") or "")
        target = root / ref
        _require(
            bool(ref)
            and target.is_file()
            and _normalized_sha256(target)
            == str(immutable.get(f"{stem}_sha256") or ""),
            f"supplemental_dense_execution_binding_invalid:{stem}",
        )
    build_policy = load_supplemental_dense_index_policy(
        root / str(immutable["build_contract_policy_ref"]), repo_root=root
    )
    zero_proof = validate_supplemental_dense_index_zero_call_proof(
        _read_json(root / str(immutable["zero_call_proof_ref"]))
    )
    resources = dict(policy.get("resource_bindings") or {})
    base_resources = dict(build_policy["vector_contract"])
    private = dict(policy.get("private_execution") or {})
    base_target = dict(build_policy["successor_target"])
    ceiling = dict(policy.get("execution_ceiling") or {})
    publication = dict(policy.get("publication_contract") or {})
    _require(
        resources.get("embedding_model") == base_resources.get("embedding_model")
        and int(resources.get("expected_embedding_dim") or 0)
        == int(base_resources.get("expected_embedding_dim") or -1)
        and int(resources.get("embedding_batch_size") or 0)
        == int(base_resources.get("embedding_batch_size") or -1)
        and int(resources.get("model_micro_batch_size") or 0) == 8
        and resources.get("milvus_dependencies_dir")
        == base_resources.get("milvus_dependencies_dir")
        and private.get("final_root") == base_target.get("private_output_root")
        and private.get("milvus_db_filename")
        == base_target.get("milvus_db_filename")
        and private.get("collection_name") == base_target.get("collection_name"),
        "supplemental_dense_execution_resource_drift",
    )
    private_base = (root / "data" / "workbench_private").resolve()
    working_root = (root / str(private.get("working_root") or "")).resolve()
    final_root = (root / str(private.get("final_root") or "")).resolve()
    try:
        working_root.relative_to(private_base)
        final_root.relative_to(private_base)
    except ValueError as exc:
        raise S1InternalSupplementalDenseExecutionError(
            "supplemental_dense_execution_target_outside_private_root"
        ) from exc
    _require(
        working_root != final_root,
        "supplemental_dense_execution_working_final_target_collision",
    )
    model_root = Path(str(resources["embedding_model"])).resolve()
    required_model_files = (
        "config.json",
        "modules.json",
        "tokenizer.json",
        "pytorch_model.bin",
        "1_Pooling/config.json",
    )
    model_config = (
        _read_json(model_root / "config.json")
        if all((model_root / name).is_file() for name in required_model_files)
        else {}
    )
    dependency_root = Path(str(resources["milvus_dependencies_dir"])).resolve()
    _require(
        all((model_root / name).is_file() for name in required_model_files)
        and int(model_config.get("hidden_size") or 0)
        == int(resources["expected_embedding_dim"])
        and (dependency_root / "pymilvus").is_dir()
        and any(dependency_root.glob("pymilvus-*.dist-info")),
        "supplemental_dense_execution_local_resource_unqualified",
    )
    expected_ceiling = {
        "maximum_executions": 1,
        "network": 0,
        "provider": 0,
        "llm_model": 0,
        "document_fetch": 0,
        "embedding_model_loads": 1,
        "embedding_vectors": 410,
        "embedding_batches": 13,
        "embedding_model_micro_batches": 52,
        "milvus_database_creates": 1,
        "milvus_collection_creates": 1,
        "milvus_inserted_vectors": 410,
        "milvus_insert_batches": 13,
        "post_build_metadata_queries": 20,
        "post_build_collection_stats_reads": 1,
        "vector_search": 0,
        "rerank": 0,
        "evidence_promotion": 0,
    }
    _require(
        all(int(ceiling.get(key, -1)) == value for key, value in expected_ceiling.items())
        and ceiling.get("automatic_retry") is False
        and publication.get("historical_collection_write_count") == 0
        and publication.get("expected_terminal_entity_count") == 410
        and publication.get("failure_result_is_immutable") is True
        and publication.get("ranking_successor_is_not_automatically_authorized")
        is True
        and zero_proof["execution_gate"]["zero_call_contract_passed"] is True,
        "supplemental_dense_execution_boundary_invalid",
    )
    return policy, build_policy, zero_proof


def _external_resource_fingerprint(policy: Mapping[str, Any]) -> dict[str, Any]:
    resources = dict(policy["resource_bindings"])
    model_root = Path(str(resources["embedding_model"])).resolve()
    model_files = (
        "config.json",
        "modules.json",
        "tokenizer.json",
        "pytorch_model.bin",
        "1_Pooling/config.json",
    )
    dependency_root = Path(str(resources["milvus_dependencies_dir"])).resolve()
    dist_info = sorted(dependency_root.glob("pymilvus-*.dist-info"))
    _require(bool(dist_info), "supplemental_dense_execution_pymilvus_dist_info_missing")
    metadata = dist_info[-1] / "METADATA"
    init_file = dependency_root / "pymilvus" / "__init__.py"
    _require(
        metadata.is_file() and init_file.is_file(),
        "supplemental_dense_execution_pymilvus_fingerprint_input_missing",
    )
    return {
        "embedding_model_root": model_root.as_posix(),
        "embedding_model_files": [
            {
                "path": name,
                "bytes": (model_root / name).stat().st_size,
                "sha256": _file_sha256(model_root / name),
            }
            for name in model_files
        ],
        "milvus_dependencies_root": dependency_root.as_posix(),
        "pymilvus_metadata": {
            "path": metadata.as_posix(),
            "bytes": metadata.stat().st_size,
            "sha256": _file_sha256(metadata),
        },
        "pymilvus_init": {
            "path": init_file.as_posix(),
            "bytes": init_file.stat().st_size,
            "sha256": _file_sha256(init_file),
        },
    }


class MilvusIndexWriter:
    FIXED_FIELDS = (
        "vector_id",
        "embedding",
        "evidence_id",
        "ticker",
        "fiscal_year",
        "form_type",
        "source_tier",
        "item_code",
        "category_slug",
        "period_type",
        "contains_table",
        "vector_kind",
        "vector_role",
        "semantic_scope",
        "intent_tags",
        "relationship_role",
        "object_type",
        "preview",
    )

    def __init__(
        self,
        *,
        uri: str,
        dependency_dir: str,
        milvus_client_cls: Any | None = None,
        data_type: Any | None = None,
    ) -> None:
        self.uri = uri
        self.dependency_dir = dependency_dir
        self._client_cls = milvus_client_cls
        self._data_type = data_type
        self.client: Any | None = None
        self.collection_name = ""
        self.calls = {
            "database_create": 0,
            "collection_create": 0,
            "insert_batches": 0,
            "inserted_vectors": 0,
            "flush": 0,
            "count": 0,
        }

    def _imports(self) -> tuple[Any, Any]:
        if self._client_cls is not None and self._data_type is not None:
            return self._client_cls, self._data_type
        if self.dependency_dir not in sys.path:
            sys.path.insert(0, self.dependency_dir)
        from pymilvus import DataType, MilvusClient

        return MilvusClient, DataType

    def begin(self, *, collection_name: str, embedding_dim: int) -> None:
        client_cls, data_type = self._imports()
        self.client = client_cls(uri=self.uri)
        self.calls["database_create"] += 1
        _require(
            not self.client.has_collection(collection_name=collection_name),
            "supplemental_dense_execution_collection_preexists",
        )
        schema = client_cls.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field(
            field_name="vector_id",
            datatype=data_type.VARCHAR,
            is_primary=True,
            max_length=512,
        )
        schema.add_field(
            field_name="embedding", datatype=data_type.FLOAT_VECTOR, dim=embedding_dim
        )
        for name, datatype, maximum in (
            ("evidence_id", data_type.VARCHAR, 256),
            ("ticker", data_type.VARCHAR, 16),
            ("form_type", data_type.VARCHAR, 16),
            ("source_tier", data_type.VARCHAR, 80),
            ("item_code", data_type.VARCHAR, 16),
            ("category_slug", data_type.VARCHAR, 96),
            ("period_type", data_type.VARCHAR, 40),
            ("vector_kind", data_type.VARCHAR, 32),
            ("vector_role", data_type.VARCHAR, 64),
            ("semantic_scope", data_type.VARCHAR, 64),
            ("intent_tags", data_type.VARCHAR, 512),
            ("relationship_role", data_type.VARCHAR, 64),
            ("object_type", data_type.VARCHAR, 64),
            ("preview", data_type.VARCHAR, 4096),
        ):
            schema.add_field(field_name=name, datatype=datatype, max_length=maximum)
        schema.add_field(field_name="fiscal_year", datatype=data_type.INT64)
        schema.add_field(field_name="contains_table", datatype=data_type.BOOL)
        indexes = client_cls.prepare_index_params()
        indexes.add_index(
            field_name="embedding", metric_type="COSINE", index_type="FLAT"
        )
        self.client.create_collection(
            collection_name=collection_name, schema=schema, index_params=indexes
        )
        self.collection_name = collection_name
        self.calls["collection_create"] += 1

    def insert(self, rows: Sequence[Mapping[str, Any]]) -> int:
        _require(self.client is not None, "supplemental_dense_execution_writer_not_started")
        payload: list[dict[str, Any]] = []
        for source in rows:
            row = dict(source)
            row.pop("vector_text", None)
            tags = row.get("intent_tags")
            if not isinstance(tags, str):
                row["intent_tags"] = json.dumps(tags or [], ensure_ascii=False)
            payload.append(row)
        result = self.client.insert(
            collection_name=self.collection_name, data=payload
        )
        acknowledged = int((result or {}).get("insert_count") or 0)
        self.calls["insert_batches"] += 1
        self.calls["inserted_vectors"] += acknowledged
        return acknowledged

    def count(self) -> int:
        _require(self.client is not None, "supplemental_dense_execution_writer_not_started")
        self.client.flush(collection_name=self.collection_name)
        self.calls["flush"] += 1
        stats = self.client.get_collection_stats(collection_name=self.collection_name)
        self.calls["count"] += 1
        return int((stats or {}).get("row_count") or 0)

    def finalize(self) -> None:
        _require(self.client is not None, "supplemental_dense_execution_writer_not_started")
        self.client.flush(collection_name=self.collection_name)
        self.calls["flush"] += 1

    def abort(self) -> None:
        self.close()

    def close(self) -> None:
        if self.client is None:
            return
        for name in ("close", "disconnect"):
            method = getattr(self.client, name, None)
            if callable(method):
                method()
                break
        self.client = None


class LocalBGEEmbedder:
    def __init__(
        self,
        *,
        model_path: str,
        expected_dim: int,
        batch_size: int,
        normalize: bool,
        model_factory: Callable[[str, str], Any] | None = None,
    ) -> None:
        self.expected_dim = expected_dim
        self.batch_size = batch_size
        self.normalize = normalize
        self.device = self._device()
        started = time.perf_counter()
        self.model = (model_factory or self._default_factory)(model_path, self.device)
        self.model_load_ms = round((time.perf_counter() - started) * 1000, 3)
        self.embedding_calls = 0
        self.embedding_micro_batches = 0
        self.embedding_vectors = 0
        self.embedding_ms = 0.0

    @staticmethod
    def _device() -> str:
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    @staticmethod
    def _default_factory(path: str, device: str) -> Any:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(path, device=device, local_files_only=True)

    def __call__(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        started = time.perf_counter()
        encoded = self.model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=self.normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        self.embedding_ms += (time.perf_counter() - started) * 1000
        self.embedding_calls += 1
        self.embedding_micro_batches += math.ceil(len(texts) / self.batch_size)
        self.embedding_vectors += len(texts)
        matrix = encoded.tolist() if hasattr(encoded, "tolist") else encoded
        return [[float(value) for value in row] for row in matrix]


class _FakeSchema:
    def __init__(self) -> None:
        self.fields: list[str] = []

    def add_field(self, *, field_name: str, **_: Any) -> None:
        self.fields.append(field_name)


class _FakeIndexes:
    def __init__(self) -> None:
        self.indexes: list[dict[str, Any]] = []

    def add_index(self, **kwargs: Any) -> None:
        self.indexes.append(dict(kwargs))


class _FakeDataType:
    VARCHAR = "VARCHAR"
    FLOAT_VECTOR = "FLOAT_VECTOR"
    INT64 = "INT64"
    BOOL = "BOOL"


class _FakeMilvusClient:
    latest: "_FakeMilvusClient | None" = None

    def __init__(self, *, uri: str) -> None:
        self.uri = uri
        self.rows: dict[str, dict[str, Any]] = {}
        self.schema: _FakeSchema | None = None
        self.closed = False
        _FakeMilvusClient.latest = self

    @staticmethod
    def create_schema(**_: Any) -> _FakeSchema:
        return _FakeSchema()

    @staticmethod
    def prepare_index_params() -> _FakeIndexes:
        return _FakeIndexes()

    def has_collection(self, **_: Any) -> bool:
        return False

    def create_collection(self, *, schema: _FakeSchema, **_: Any) -> None:
        self.schema = schema

    def insert(self, *, data: Sequence[Mapping[str, Any]], **_: Any) -> dict[str, Any]:
        for row in data:
            self.rows[str(row["vector_id"])] = dict(row)
        return {"insert_count": len(data)}

    def flush(self, **_: Any) -> None:
        return None

    def get_collection_stats(self, **_: Any) -> dict[str, int]:
        return {"row_count": len(self.rows)}

    def close(self) -> None:
        self.closed = True


def materialize_execution_implementation_proof(
    policy: Mapping[str, Any],
    build_policy: Mapping[str, Any],
    *,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    preflight = run_project_os_preflight(root, run_scope=RUN_SCOPE)
    _require(
        preflight.get("status") == "pass",
        "supplemental_dense_execution_project_os_preflight_failed",
    )
    specs, _ = compile_supplemental_vector_specs(build_policy, repo_root=root)
    resources = dict(policy["resource_bindings"])
    private = dict(policy["private_execution"])
    dimension = int(resources["expected_embedding_dim"])
    writer = MilvusIndexWriter(
        uri="fake://supplemental-dense",
        dependency_dir=str(resources["milvus_dependencies_dir"]),
        milvus_client_cls=_FakeMilvusClient,
        data_type=_FakeDataType,
    )

    def fake_embed(texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return [[0.0] * dimension for _ in texts]

    execution = execute_index_build_plan(
        specs, policy=build_policy, embed_batch=fake_embed, writer=writer
    )
    client = _FakeMilvusClient.latest
    _require(client is not None, "supplemental_dense_execution_fake_client_missing")
    _require(
        set(MilvusIndexWriter.FIXED_FIELDS) == set(client.schema.fields if client.schema else []),
        "supplemental_dense_execution_schema_field_drift",
    )
    writer.close()
    working = (root / str(private["working_root"])).resolve()
    final = (root / str(private["final_root"])).resolve()
    _require(
        not working.exists() and not final.exists(),
        "supplemental_dense_execution_target_preexists",
    )
    body: dict[str, Any] = {
        "schema_version": IMPLEMENTATION_PROOF_SCHEMA,
        "contract_ref": "fin_0_1_3.S1.internal_supplemental_dense_execution:v1",
        "run_scope": RUN_SCOPE,
        "recorded_at": "2026-08-09",
        "status": "terminal_succeeded_full_fake_execution_adapter_proof",
        "project_os_preflight": {
            "status": str(preflight["status"]),
            "run_scope": str(preflight["run_scope"]),
            "open_full_chain_blocker_count": int(preflight["open_full_chain_blocker_count"]),
        },
        "policy_digest": canonical_digest(policy),
        "vector_spec_terminal_digest": canonical_digest(specs),
        "fake_execution": execution,
        "milvus_adapter": {
            "fixed_schema_fields": list(MilvusIndexWriter.FIXED_FIELDS),
            "dynamic_lineage_preserved": True,
            "stored_vector_text": False,
            "terminal_entity_count": len(client.rows),
            "writer_calls": dict(writer.calls),
            "working_target_created": False,
            "final_target_created": False,
        },
        "execution_gate": {
            "implementation_full_fake_passed": True,
            "real_build_authorized": False,
            "clean_commit_and_separate_authority_required": True,
        },
        "observed_real_calls": {
            "network": 0,
            "provider": 0,
            "llm_model": 0,
            "document_fetch": 0,
            "real_embedding": 0,
            "milvus_read": 0,
            "milvus_write": 0,
            "vector_search": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "known_boundary": "The real BGE and Milvus adapters are exercised only through fake dependencies. No private target is created and no execution authority is granted.",
    }
    body["proof_digest"] = canonical_digest(body)
    return body


def validate_execution_implementation_proof(value: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(value)
    supplied = str(body.pop("proof_digest", ""))
    _require(
        value.get("schema_version") == IMPLEMENTATION_PROOF_SCHEMA
        and value.get("status") == "terminal_succeeded_full_fake_execution_adapter_proof"
        and supplied == canonical_digest(body)
        and (value.get("fake_execution") or {}).get("terminal_count") == 410
        and (value.get("milvus_adapter") or {}).get("terminal_entity_count") == 410
        and (value.get("milvus_adapter") or {}).get("writer_calls", {}).get("count") == 1
        and (value.get("milvus_adapter") or {}).get("writer_calls", {}).get("flush") == 2
        and all(int(item) == 0 for item in (value.get("observed_real_calls") or {}).values())
        and (value.get("execution_gate") or {}).get("real_build_authorized") is False,
        "supplemental_dense_execution_implementation_proof_invalid",
    )
    return dict(value)


def build_clean_execution_authority(
    *,
    policy: Mapping[str, Any],
    implementation_proof: Mapping[str, Any],
    repo_root: str | Path,
    binding_refs: Sequence[str],
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    state = clean_synced_git_state(root)
    _require(
        state["clean"] and state["synced"],
        "supplemental_dense_authority_git_state_invalid",
    )
    validate_execution_implementation_proof(implementation_proof)
    _require(
        set(binding_refs) == set(REQUIRED_IMPLEMENTATION_BINDING_REFS)
        and len(binding_refs) == len(REQUIRED_IMPLEMENTATION_BINDING_REFS),
        "supplemental_dense_authority_binding_set_invalid",
    )
    preflight = run_project_os_preflight(root, run_scope=RUN_SCOPE)
    _require(
        preflight.get("status") == "pass",
        "supplemental_dense_authority_project_os_preflight_failed",
    )
    private = dict(policy["private_execution"])
    public = dict(policy["public_outputs"])
    _require(
        not (root / str(private["working_root"])).exists()
        and not (root / str(private["final_root"])).exists()
        and not (root / str(public["terminal_result_ref"])).exists()
        and not (root / str(public["presence_result_ref"])).exists(),
        "supplemental_dense_authority_target_or_result_preexists",
    )
    bindings = [
        {"ref": ref, "sha256": _normalized_sha256(root / ref)}
        for ref in binding_refs
    ]
    body: dict[str, Any] = {
        "schema_version": AUTHORITY_SCHEMA,
        "decision_id": "FIN-0.1.3-S1-SUPPLEMENTAL-DENSE-REAL-BUILD-R1-AUTHORITY",
        "recorded_at": "2026-08-09",
        "status": "clean_authority_issued_not_consumed",
        "run_scope": RUN_SCOPE,
        "attempt_id": str(policy["attempt_id"]),
        "user_authority": {
            "message": "继续",
            "interpreted_scope": "continue_the_frozen_supplemental_dense_sequence_after_zero_call_pass",
            "automatic_retry": False,
        },
        "implementation": {
            "commit": str(state["head"]),
            "branch": str(state["branch"]),
            "upstream": str(state["upstream"]),
            "clean": True,
            "synced": True,
            "bindings": bindings,
        },
        "policy_digest": canonical_digest(policy),
        "implementation_proof_digest": str(implementation_proof["proof_digest"]),
        "external_resource_fingerprint": _external_resource_fingerprint(policy),
        "execution_ceiling": dict(policy["execution_ceiling"]),
        "private_target": dict(policy["private_execution"]),
        "public_outputs": dict(policy["public_outputs"]),
        "maximum_executions": 1,
        "consumed": False,
        "preserved_boundaries": {
            "ranking_successor_authorized": False,
            "reranker_authorized": False,
            "evidence_promotion_authorized": False,
            "current_quarter_sql_refresh_authorized": False,
            "external_search_authorized": False,
            "release_authorized": False,
        },
        "known_boundary": "Authority is limited to one local 410-vector incremental build and its read-only 10-target metadata proof. Any failure is terminal with no retry.",
    }
    body["authority_digest"] = canonical_digest(body)
    return body


def validate_clean_execution_authority(
    authority: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path,
    require_clean_synced: bool,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    body = dict(authority)
    supplied = str(body.pop("authority_digest", ""))
    implementation = dict(authority.get("implementation") or {})
    _require(
        authority.get("schema_version") == AUTHORITY_SCHEMA
        and authority.get("status") == "clean_authority_issued_not_consumed"
        and authority.get("run_scope") == RUN_SCOPE
        and authority.get("attempt_id") == policy.get("attempt_id")
        and supplied == canonical_digest(body)
        and authority.get("policy_digest") == canonical_digest(policy)
        and authority.get("maximum_executions") == 1
        and authority.get("consumed") is False
        and (authority.get("user_authority") or {}).get("automatic_retry") is False,
        "supplemental_dense_authority_identity_invalid",
    )
    _require(
        authority.get("external_resource_fingerprint")
        == _external_resource_fingerprint(policy),
        "supplemental_dense_authority_external_resource_drift",
    )
    for item in implementation.get("bindings") or []:
        target = root / str(item.get("ref") or "")
        _require(
            target.is_file()
            and _normalized_sha256(target) == str(item.get("sha256") or ""),
            "supplemental_dense_authority_implementation_drift",
        )
    _require(
        {str(item.get("ref") or "") for item in implementation.get("bindings") or []}
        == set(REQUIRED_IMPLEMENTATION_BINDING_REFS)
        and len(implementation.get("bindings") or [])
        == len(REQUIRED_IMPLEMENTATION_BINDING_REFS),
        "supplemental_dense_authority_binding_set_invalid",
    )
    if require_clean_synced:
        state = clean_synced_git_state(root)
        _require(
            state["clean"] and state["synced"],
            "supplemental_dense_authority_execution_git_state_invalid",
        )
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", str(implementation["commit"]), "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        _require(
            ancestor.returncode == 0,
            "supplemental_dense_authority_commit_not_ancestor",
        )
    return dict(authority)


def _canonical_result(value: Mapping[str, Any], digest_field: str) -> dict[str, Any]:
    body = dict(value)
    supplied = str(body.pop(digest_field, ""))
    _require(
        bool(supplied) and supplied == canonical_digest(body),
        f"supplemental_dense_{digest_field}_invalid",
    )
    return dict(value)


def validate_terminal_result(value: Mapping[str, Any]) -> dict[str, Any]:
    result = _canonical_result(value, "result_digest")
    _require(
        result.get("schema_version") == TERMINAL_RESULT_SCHEMA
        and str(result.get("status") or "").startswith("terminal_")
        and result.get("automatic_retry") is False,
        "supplemental_dense_terminal_result_invalid",
    )
    if result["status"] == "terminal_succeeded_real_incremental_dense_build":
        observed = dict(result.get("observed_calls") or {})
        build = dict(result.get("build") or {})
        _require(
            build.get("terminal_entity_count") == 410
            and build.get("historical_collection_write_count") == 0
            and build.get("private_db_bytes", 0) > 0
            and len(str(build.get("private_db_sha256") or "")) == 64
            and observed.get("network") == 0
            and observed.get("provider") == 0
            and observed.get("llm_model") == 0
            and observed.get("document_fetch") == 0
            and observed.get("embedding_model_loads") == 1
            and observed.get("embedding_batches") == 13
            and observed.get("embedding_model_micro_batches") == 52
            and observed.get("embedding_vectors") == 410
            and observed.get("milvus_database_creates") == 1
            and observed.get("milvus_collection_creates") == 1
            and observed.get("milvus_insert_batches") == 13
            and observed.get("milvus_inserted_vectors") == 410
            and observed.get("vector_search") == 0
            and observed.get("rerank") == 0
            and observed.get("evidence_promotion") == 0
            and (result.get("execution_gate") or {}).get("presence_reproof_required") is True
            and (result.get("execution_gate") or {}).get("ranking_successor_authorized")
            is False,
            "supplemental_dense_terminal_success_boundary_invalid",
        )
    elif result["status"] == "terminal_failed_real_incremental_dense_build_no_retry":
        observed = dict(result.get("observed_calls") or {})
        failure = dict(result.get("failure") or {})
        private_state = dict(result.get("private_state") or {})
        _require(
            all(
                bool(str(failure.get(key) or ""))
                for key in ("phase", "error_type", "error_code")
            )
            and bool(str(private_state.get("working_root_ref") or ""))
            and isinstance(private_state.get("working_root_exists"), bool)
            and bool(str(private_state.get("final_root_ref") or ""))
            and isinstance(private_state.get("final_root_exists"), bool)
            and observed.get("network") == 0
            and observed.get("provider") == 0
            and observed.get("llm_model") == 0
            and observed.get("document_fetch") == 0
            and observed.get("vector_search") == 0
            and observed.get("rerank") == 0
            and observed.get("evidence_promotion") == 0
            and (result.get("execution_gate") or {}).get(
                "real_incremental_build_passed"
            )
            is False
            and (result.get("execution_gate") or {}).get(
                "ranking_successor_authorized"
            )
            is False,
            "supplemental_dense_terminal_failure_boundary_invalid",
        )
    else:
        raise S1InternalSupplementalDenseExecutionError(
            "supplemental_dense_terminal_status_invalid"
        )
    return result


def build_real_presence_proof(
    *,
    repo_root: str | Path,
    policy: Mapping[str, Any],
    build_policy: Mapping[str, Any],
    terminal_result: Mapping[str, Any],
    client_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    result = validate_terminal_result(terminal_result)
    _require(
        result.get("status") == "terminal_succeeded_real_incremental_dense_build",
        "supplemental_dense_presence_requires_successful_build",
    )
    immutable = dict(build_policy["immutable_inputs"])
    diagnostic = _read_json(root / str(immutable["dense_index_diagnostic_ref"]))
    runtime = _read_json(root / str(immutable["historical_milvus_runtime_ref"]))
    rows = list(diagnostic.get("rows") or [])
    unique_aliases = sorted({tuple(sorted(map(str, row["selected_aliases"]))) for row in rows})
    _require(len(unique_aliases) == 10, "supplemental_dense_presence_unique_target_count_invalid")
    resources = dict(policy["resource_bindings"])

    def default_factory(*, uri: str) -> Any:
        dependency = str(resources["milvus_dependencies_dir"])
        if dependency not in sys.path:
            sys.path.insert(0, dependency)
        from pymilvus import MilvusClient

        return MilvusClient(uri=uri)

    factory = client_factory or default_factory
    supplemental_db = root / str(result["build"]["private_db_ref"])
    _require(
        supplemental_db.is_file()
        and supplemental_db.stat().st_size
        == int(result["build"]["private_db_bytes"])
        and _file_sha256(supplemental_db)
        == str(result["build"]["private_db_sha256"]),
        "supplemental_dense_presence_database_integrity_invalid",
    )
    clients = {
        "historical": factory(uri=str(runtime["db_path"])),
        "supplemental": factory(uri=str(supplemental_db)),
    }
    collections = {
        "historical": str(runtime["collection_name"]),
        "supplemental": str(result["build"]["collection_name"]),
    }
    locations: dict[tuple[str, ...], list[str]] = {}
    query_count = 0
    try:
        for client_name, client in clients.items():
            client.load_collection(collection_name=collections[client_name])
        supplemental_stats = clients["supplemental"].get_collection_stats(
            collection_name=collections["supplemental"]
        )
        _require(
            int((supplemental_stats or {}).get("row_count") or 0) == 410,
            "supplemental_dense_presence_terminal_entity_count_invalid",
        )
        for aliases in unique_aliases:
            encoded = ", ".join(json.dumps(alias) for alias in aliases)
            found: list[str] = []
            for client_name, client in clients.items():
                hits = client.query(
                    collection_name=collections[client_name],
                    filter=f"evidence_id in [{encoded}]",
                    output_fields=["evidence_id", "ticker", "fiscal_year", "form_type"],
                    limit=64,
                )
                query_count += 1
                if hits:
                    found.append(client_name)
            locations[aliases] = found
    finally:
        for client_name, client in clients.items():
            release = getattr(client, "release_collection", None)
            if callable(release):
                release(collection_name=collections[client_name])
            close = getattr(client, "close", None)
            if callable(close):
                close()
    _require(
        query_count == 20 and all(locations.values()),
        "supplemental_dense_real_presence_gate_failed",
    )
    row_satisfied = sum(
        bool(locations[tuple(sorted(map(str, row["selected_aliases"])))]) for row in rows
    )
    location_counts = {
        name: sum(name in found for found in locations.values())
        for name in ("historical", "supplemental")
    }
    body: dict[str, Any] = {
        "schema_version": PRESENCE_RESULT_SCHEMA,
        "contract_ref": "fin_0_1_3.S1.internal_supplemental_dense_real_presence:v1",
        "run_scope": RUN_SCOPE,
        "recorded_at": "2026-08-09",
        "status": "terminal_succeeded_real_federated_physical_presence_10_of_10",
        "build_attempt_id": str(result["attempt_id"]),
        "build_result_digest": str(result["result_digest"]),
        "unique_selected_target_count": len(unique_aliases),
        "unique_selected_targets_present": sum(bool(value) for value in locations.values()),
        "historical_presence_count": location_counts["historical"],
        "supplemental_presence_count": location_counts["supplemental"],
        "row_weighted_target_count": len(rows),
        "row_weighted_satisfied_count": row_satisfied,
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "llm_model": 0,
            "embedding": 0,
            "milvus_metadata_queries": query_count,
            "milvus_collection_stats_reads": 1,
            "milvus_vector_searches": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "execution_gate": {
            "physical_presence_passed": True,
            "ranking_successor_authorized": False,
            "separate_same_matrix_authority_required": True,
        },
        "known_boundary": "This is read-only physical identity presence, not semantic ranking quality, Evidence, current-quarter exact readiness, external coverage, product acceptance or release.",
    }
    body["presence_digest"] = canonical_digest(body)
    return body


def validate_real_presence_proof(value: Mapping[str, Any]) -> dict[str, Any]:
    result = _canonical_result(value, "presence_digest")
    _require(
        result.get("schema_version") == PRESENCE_RESULT_SCHEMA
        and result.get("status")
        == "terminal_succeeded_real_federated_physical_presence_10_of_10"
        and result.get("unique_selected_targets_present") == 10
        and result.get("row_weighted_satisfied_count") == 18
        and (result.get("observed_calls") or {}).get("milvus_metadata_queries") == 20
        and (result.get("observed_calls") or {}).get("milvus_collection_stats_reads")
        == 1
        and (result.get("observed_calls") or {}).get("milvus_vector_searches") == 0
        and (result.get("execution_gate") or {}).get("ranking_successor_authorized")
        is False,
        "supplemental_dense_real_presence_proof_invalid",
    )
    return result


__all__ = [
    "AUTHORITY_SCHEMA",
    "EXECUTION_POLICY_SCHEMA",
    "IMPLEMENTATION_PROOF_SCHEMA",
    "PRESENCE_RESULT_SCHEMA",
    "REQUIRED_IMPLEMENTATION_BINDING_REFS",
    "TERMINAL_RESULT_SCHEMA",
    "LocalBGEEmbedder",
    "MilvusIndexWriter",
    "S1InternalSupplementalDenseExecutionError",
    "build_clean_execution_authority",
    "build_real_presence_proof",
    "clean_synced_git_state",
    "load_supplemental_dense_execution_policy",
    "materialize_execution_implementation_proof",
    "validate_clean_execution_authority",
    "validate_execution_implementation_proof",
    "validate_real_presence_proof",
    "validate_terminal_result",
]
