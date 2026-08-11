from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.project_os_preflight import run_project_os_preflight
from sec_agent.s1_internal_dense_index_diagnostic import (
    validate_dense_index_diagnostic,
)
from sec_agent.s1_internal_supplemental_assets import (
    load_validated_supplemental_asset_manifest,
)


RUN_SCOPE = "S1_INTERNAL_CURRENT_CORPUS_AND_INDEX_REFRESH"
POLICY_SCHEMA = (
    "fin_ia_0_1_3_s1_internal_supplemental_dense_index_policy_v1_0"
)
RESULT_SCHEMA = (
    "fin_ia_0_1_3_s1_internal_supplemental_dense_index_zero_call_proof_v1_0"
)


class S1InternalSupplementalDenseIndexError(RuntimeError):
    pass


class IndexWriter(Protocol):
    def begin(self, *, collection_name: str, embedding_dim: int) -> None: ...

    def insert(self, rows: Sequence[Mapping[str, Any]]) -> int: ...

    def count(self) -> int: ...

    def finalize(self) -> None: ...

    def abort(self) -> None: ...


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S1InternalSupplementalDenseIndexError(code)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "supplemental_dense_json_object_required")
    return value


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _plain_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalized_accession(value: Any) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())


def _bound_inputs(policy: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    immutable = dict(policy.get("immutable_inputs") or {})
    bindings: list[tuple[str, str, str]] = []
    for item in immutable.get("supplemental_asset_manifests") or []:
        key = str(item.get("asset_key") or "")
        bindings.append(
            (
                f"supplemental_asset_manifest:{key}",
                str(item.get("ref") or ""),
                str(item.get("sha256") or ""),
            )
        )
    for stem in (
        "research_qrels",
        "owner_qrels_acceptance",
        "dense_index_diagnostic",
        "historical_milvus_runtime",
    ):
        bindings.append(
            (
                stem,
                str(immutable.get(f"{stem}_ref") or ""),
                str(immutable.get(f"{stem}_sha256") or ""),
            )
        )
    return bindings


def validate_target_isolation(
    policy: Mapping[str, Any],
    *,
    repo_root: str | Path,
    historical_runtime: Mapping[str, Any],
    target_exists: bool | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    target = dict(policy.get("successor_target") or {})
    private_base = (root / "data" / "workbench_private").resolve()
    output_root = (root / str(target.get("private_output_root") or "")).resolve()
    try:
        output_root.relative_to(private_base)
    except ValueError as exc:
        raise S1InternalSupplementalDenseIndexError(
            "supplemental_dense_target_outside_private_root"
        ) from exc
    db_path = (output_root / str(target.get("milvus_db_filename") or "")).resolve()
    historical_db = Path(str(historical_runtime.get("db_path") or "")).resolve()
    collection = str(target.get("collection_name") or "")
    historical_collection = str(historical_runtime.get("collection_name") or "")
    exists = db_path.exists() if target_exists is None else bool(target_exists)
    _require(
        db_path != historical_db
        and bool(collection)
        and collection != historical_collection
        and target.get("historical_collection_is_read_only") is True
        and target.get("overwrite_existing_target") is False
        and not exists,
        "supplemental_dense_historical_or_existing_target_collision",
    )
    return {
        "private_output_root": output_root.as_posix(),
        "target_db_path": db_path.as_posix(),
        "target_collection_name": collection,
        "historical_db_path": historical_db.as_posix(),
        "historical_collection_name": historical_collection,
        "target_exists_at_proof": exists,
        "historical_target_isolated": True,
    }


def _validate_federation_contract(contract: Mapping[str, Any]) -> None:
    _require(
        contract.get("merge_mode") == "rank_only_rrf"
        and int(contract.get("rrf_k") or 0) > 0
        and contract.get("raw_score_cross_collection_comparison_allowed") is False
        and contract.get("dedupe_key") == "canonical_evidence_identity"
        and contract.get("tie_breaker")
        == "canonical_evidence_identity_ascending"
        and len(contract.get("members") or []) == 2,
        "supplemental_dense_raw_score_federation_forbidden",
    )


def load_supplemental_dense_index_policy(
    path: str | Path, *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path))
    _require(
        policy.get("schema_version") == POLICY_SCHEMA
        and policy.get("result_schema") == RESULT_SCHEMA
        and policy.get("contract_ref")
        == "fin_0_1_3.S1.internal_supplemental_dense_index:v1"
        and policy.get("run_scope") == RUN_SCOPE
        and policy.get("binding_hash_profile")
        == "sha256_utf8_lf_normalized_v1",
        "supplemental_dense_policy_identity_invalid",
    )
    manifest_inputs = list(
        (policy.get("immutable_inputs") or {}).get(
            "supplemental_asset_manifests"
        )
        or []
    )
    _require(
        len(manifest_inputs)
        == int((policy.get("source_contract") or {}).get("expected_manifest_count") or 0)
        and len({str(item.get("asset_key") or "") for item in manifest_inputs})
        == len(manifest_inputs),
        "supplemental_dense_manifest_binding_invalid",
    )
    for key, ref, supplied in _bound_inputs(policy):
        target = root / ref
        _require(
            bool(ref)
            and bool(supplied)
            and target.is_file()
            and _normalized_sha256(target) == supplied,
            f"supplemental_dense_policy_binding_invalid:{key}",
        )
    source = dict(policy.get("source_contract") or {})
    vector = dict(policy.get("vector_contract") or {})
    _require(
        int(source.get("expected_vector_spec_count") or 0) == sum(
            int(item.get("expected_evidence_rows") or 0)
            for item in manifest_inputs
        )
        and source.get("source_rows_must_be_capture_backed") is True
        and source.get("source_rows_must_remain_candidate_only") is True
        and source.get("qrels_may_shape_source_row_inclusion") is False
        and source.get("qrels_loaded_only_after_vector_spec_terminal_digest") is True
        and vector.get("vector_kind") == "narrative_chunk"
        and vector.get("vector_id_rule") == "exact_source_evidence_id"
        and int(vector.get("expected_embedding_dim") or 0) == 1024
        and int(vector.get("embedding_batch_size") or 0) > 0,
        "supplemental_dense_source_or_vector_contract_invalid",
    )
    hard = dict(policy.get("hard_boundaries") or {})
    for key in (
        "network",
        "provider",
        "llm_model",
        "document_fetch",
        "real_embedding",
        "milvus_read",
        "milvus_write",
        "rerank",
        "evidence_promotion",
    ):
        _require(
            int(hard.get(key, -1)) == 0,
            "supplemental_dense_policy_call_boundary_invalid",
        )
    _require(
        hard.get("may_write_successor_index") is False
        and hard.get("may_mutate_historical_index") is False
        and hard.get("may_promote_candidate_to_evidence") is False
        and hard.get("may_close_current_quarter_sql_or_external_release_blocker")
        is False,
        "supplemental_dense_policy_promotion_boundary_invalid",
    )
    _validate_federation_contract(dict(policy.get("federation_contract") or {}))
    return policy


def _load_corpus_rows(
    *,
    repo_root: Path,
    manifest_ref: str,
    manifest: Mapping[str, Any],
    expected_rows: int,
) -> list[dict[str, Any]]:
    private_root = (
        repo_root / str(manifest.get("private_asset_root_ref") or "")
    ).resolve()
    corpus_relative = "corpus/supplemental_evidence.jsonl"
    corpus_path = (private_root / corpus_relative).resolve()
    inventory = {
        str(item.get("path") or ""): dict(item)
        for item in manifest.get("private_file_inventory") or []
    }
    _require(
        corpus_relative in inventory and corpus_path.is_file(),
        "supplemental_dense_corpus_inventory_missing",
    )
    rows = [
        json.loads(line)
        for line in corpus_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    _require(
        len(rows) == expected_rows
        and len(rows)
        == int((manifest.get("record_counts") or {}).get("evidence_chunks") or 0),
        "supplemental_dense_corpus_row_count_invalid",
    )
    bindings = {
        _normalized_accession(item.get("accession_number")): dict(item)
        for item in manifest.get("source_bindings") or []
    }
    _require(bool(bindings), "supplemental_dense_source_bindings_missing")
    validated: list[dict[str, Any]] = []
    for row in rows:
        _require(
            isinstance(row, dict),
            "supplemental_dense_corpus_row_object_required",
        )
        metadata = dict(row.get("metadata") or {})
        evidence_id = str(row.get("evidence_id") or "")
        ticker = str(row.get("ticker") or "")
        accession = _normalized_accession(row.get("accession_number"))
        binding = bindings.get(accession)
        _require(
            bool(binding)
            and evidence_id.startswith(f"SUPP::{ticker}::{accession}::CHUNK_")
            and ticker == str(binding.get("ticker") or "")
            and str(row.get("form_type") or "")
            == str(binding.get("form_type") or "")
            and str(row.get("source_url") or "")
            == str(binding.get("selected_url") or "")
            and str(metadata.get("capture_digest") or "")
            == str(binding.get("parsed_capture_digest") or "")
            and str(metadata.get("accession_number") or "")
            == str(binding.get("accession_number") or "")
            and metadata.get("candidate_only_not_evidence") is True,
            "supplemental_dense_cross_manifest_source_mismatch",
        )
        _require(
            bool(str(metadata.get("capture_digest") or ""))
            and bool(str(row.get("source_url") or ""))
            and bool(str(row.get("publication_date") or "")),
            "supplemental_dense_capture_lineage_missing",
        )
        validated.append(
            {
                **row,
                "_source_manifest_ref": manifest_ref,
                "_source_manifest_digest": str(manifest["manifest_digest"]),
            }
        )
    return validated


def _compile_vector_spec(
    row: Mapping[str, Any], *, policy: Mapping[str, Any]
) -> dict[str, Any]:
    source = dict(policy["source_contract"])
    vector = dict(policy["vector_contract"])
    text = " ".join(str(row.get("text") or "").split())
    _require(
        bool(text)
        and len(text) <= int(source["maximum_source_text_chars"]),
        "supplemental_dense_source_text_invalid",
    )
    metadata = dict(row.get("metadata") or {})
    header = " | ".join(
        (
            f"ticker={row['ticker']}",
            f"form={row['form_type']}",
            f"fiscal_year={int(row['fiscal_year'])}",
            f"section={row.get('section') or ''}",
            f"subsection={row.get('subsection') or ''}",
        )
    )
    vector_text = f"{header}\n{text}"
    evidence_id = str(row["evidence_id"])
    return {
        "vector_id": evidence_id,
        "evidence_id": evidence_id,
        "ticker": str(row["ticker"]),
        "fiscal_year": int(row["fiscal_year"]),
        "form_type": str(row["form_type"]),
        "source_tier": str(row["source_tier"]),
        "item_code": "",
        "category_slug": "supplemental_current",
        "period_type": (
            "annual" if str(row["form_type"]) == "10-K" else "quarterly"
        ),
        "contains_table": False,
        "vector_kind": str(vector["vector_kind"]),
        "vector_role": str(vector["vector_role"]),
        "semantic_scope": str(row.get("section") or "official_source"),
        "intent_tags": [],
        "relationship_role": "",
        "object_type": str(row.get("evidence_type") or ""),
        "preview": text[:512],
        "candidate_state": "candidate_only_not_evidence",
        "source_url": str(row["source_url"]),
        "publication_date": str(row["publication_date"]),
        "accession_number": str(row["accession_number"]),
        "capture_digest": str(metadata["capture_digest"]),
        "source_manifest_ref": str(row["_source_manifest_ref"]),
        "source_manifest_digest": str(row["_source_manifest_digest"]),
        "source_text_sha256": _plain_sha256(text),
        "vector_text": vector_text,
        "vector_text_sha256": _plain_sha256(vector_text),
    }


def validate_vector_specs(
    specs: Sequence[Mapping[str, Any]], *, policy: Mapping[str, Any]
) -> None:
    expected = int(policy["source_contract"]["expected_vector_spec_count"])
    required = set(policy["vector_contract"]["required_lineage_fields"])
    identities = [str(item.get("evidence_id") or "") for item in specs]
    _require(
        len(specs) == expected
        and len(set(identities)) == expected
        and all(identities),
        "supplemental_dense_duplicate_or_missing_evidence_identity",
    )
    for item in specs:
        identity = str(item["evidence_id"])
        ticker = str(item.get("ticker") or "")
        _require(
            item.get("vector_id") == identity
            and identity.startswith(f"SUPP::{ticker}::")
            and item.get("vector_kind") == "narrative_chunk"
            and item.get("candidate_state") == "candidate_only_not_evidence"
            and all(bool(item.get(field)) for field in required)
            and item.get("vector_text_sha256")
            == _plain_sha256(str(item.get("vector_text") or "")),
            "supplemental_dense_vector_identity_or_lineage_invalid",
        )


def compile_supplemental_vector_specs(
    policy: Mapping[str, Any], *, repo_root: str | Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    root = Path(repo_root).resolve()
    specs: list[dict[str, Any]] = []
    manifest_summaries: list[dict[str, Any]] = []
    for item in policy["immutable_inputs"]["supplemental_asset_manifests"]:
        ref = str(item["ref"])
        manifest = load_validated_supplemental_asset_manifest(
            root / ref, repo_root=root
        )
        rows = _load_corpus_rows(
            repo_root=root,
            manifest_ref=ref,
            manifest=manifest,
            expected_rows=int(item["expected_evidence_rows"]),
        )
        specs.extend(_compile_vector_spec(row, policy=policy) for row in rows)
        manifest_summaries.append(
            {
                "asset_key": str(item["asset_key"]),
                "manifest_ref": ref,
                "manifest_digest": str(manifest["manifest_digest"]),
                "source_document_count": int(
                    manifest["record_counts"]["source_documents"]
                ),
                "vector_spec_count": len(rows),
            }
        )
    validate_vector_specs(specs, policy=policy)
    _require(
        sum(item["source_document_count"] for item in manifest_summaries)
        == int(policy["source_contract"]["expected_source_document_count"]),
        "supplemental_dense_source_document_count_invalid",
    )
    return specs, manifest_summaries


def execute_index_build_plan(
    specs: Sequence[Mapping[str, Any]],
    *,
    policy: Mapping[str, Any],
    embed_batch: Callable[[Sequence[str]], Sequence[Sequence[float]]],
    writer: IndexWriter,
) -> dict[str, Any]:
    validate_vector_specs(specs, policy=policy)
    vector = dict(policy["vector_contract"])
    target = dict(policy["successor_target"])
    dimension = int(vector["expected_embedding_dim"])
    batch_size = int(vector["embedding_batch_size"])
    embedded = 0
    inserted = 0
    batches = 0
    writer.begin(
        collection_name=str(target["collection_name"]), embedding_dim=dimension
    )
    try:
        for offset in range(0, len(specs), batch_size):
            batch = list(specs[offset : offset + batch_size])
            vectors = list(
                embed_batch([str(item["vector_text"]) for item in batch])
            )
            _require(
                len(vectors) == len(batch)
                and all(len(item) == dimension for item in vectors),
                "supplemental_dense_embedding_dimension_mismatch",
            )
            payload = [
                {**dict(spec), "embedding": list(embedding)}
                for spec, embedding in zip(batch, vectors, strict=True)
            ]
            acknowledged = int(writer.insert(payload))
            _require(
                acknowledged == len(payload),
                "supplemental_dense_partial_insert_acknowledgement",
            )
            batches += 1
            embedded += len(vectors)
            inserted += acknowledged
        terminal_count = int(writer.count())
        _require(
            terminal_count == len(specs),
            "supplemental_dense_terminal_count_mismatch",
        )
        writer.finalize()
    except Exception:
        writer.abort()
        raise
    return {
        "embedding_batch_count": batches,
        "embedding_vector_count": embedded,
        "insert_batch_count": batches,
        "inserted_vector_count": inserted,
        "terminal_count": terminal_count,
    }


class _FakeWriter:
    def __init__(self, *, partial_insert: bool = False) -> None:
        self.partial_insert = partial_insert
        self.rows: dict[str, dict[str, Any]] = {}
        self.started = False
        self.published = False
        self.aborted = False

    def begin(self, *, collection_name: str, embedding_dim: int) -> None:
        _require(
            bool(collection_name) and embedding_dim > 0 and not self.started,
            "supplemental_dense_fake_writer_begin_invalid",
        )
        self.started = True

    def insert(self, rows: Sequence[Mapping[str, Any]]) -> int:
        _require(self.started, "supplemental_dense_fake_writer_not_started")
        accepted = len(rows) - 1 if self.partial_insert and rows else len(rows)
        for row in list(rows)[:accepted]:
            self.rows[str(row["vector_id"])] = dict(row)
        return accepted

    def count(self) -> int:
        return len(self.rows)

    def finalize(self) -> None:
        self.published = True

    def abort(self) -> None:
        self.aborted = True
        self.published = False


def _fake_embedder(
    *, dimension: int, wrong_dimension: bool = False
) -> Callable[[Sequence[str]], Sequence[Sequence[float]]]:
    output_dimension = dimension - 1 if wrong_dimension else dimension

    def embed(texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return [[0.0] * output_dimension for _ in texts]

    return embed


def _qrels_digest(value: Mapping[str, Any]) -> tuple[str, str]:
    body = dict(value)
    return str(body.pop("review_digest", "")), canonical_digest(body)


def evaluate_federated_presence_gate(
    *,
    specs: Sequence[Mapping[str, Any]],
    qrels: Mapping[str, Any],
    owner_acceptance: Mapping[str, Any],
    diagnostic: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    supplied_qrels_digest, calculated_qrels_digest = _qrels_digest(qrels)
    owner_body = dict(owner_acceptance)
    supplied_owner_digest = str(owner_body.pop("decision_digest", ""))
    _require(
        supplied_qrels_digest == calculated_qrels_digest
        and supplied_qrels_digest
        == str((owner_acceptance.get("source_qrels") or {}).get("review_digest") or "")
        and supplied_owner_digest == canonical_digest(owner_body)
        and (owner_acceptance.get("authority") or {}).get("owner_review_complete")
        is True
        and (owner_acceptance.get("owner_decision") or {}).get(
            "ranking_entry_eligible"
        )
        is True
        and int(
            (owner_acceptance.get("owner_decision") or {}).get(
                "accepted_qrel_count"
            )
            or 0
        )
        == len(qrels.get("qrels") or []),
        "supplemental_dense_owner_qrels_binding_invalid",
    )
    validated_diagnostic = validate_dense_index_diagnostic(diagnostic)
    qrel_bundles = {str(row["bundle_id"]) for row in qrels.get("qrels") or []}
    diagnostic_rows = list(validated_diagnostic.get("rows") or [])
    _require(
        len(qrel_bundles) == len(diagnostic_rows)
        and {str(row["bundle_id"]) for row in diagnostic_rows} == qrel_bundles,
        "supplemental_dense_diagnostic_qrels_binding_invalid",
    )
    supplemental_ids = {str(item["evidence_id"]) for item in specs}
    unique: dict[tuple[str, ...], str] = {}
    row_weighted_satisfied = 0
    for row in diagnostic_rows:
        aliases = tuple(sorted(str(value) for value in row["selected_aliases"]))
        _require(bool(aliases), "supplemental_dense_selected_alias_missing")
        if row.get("present_in_milvus") is True:
            location = "historical"
        elif any(alias in supplemental_ids for alias in aliases):
            location = "supplemental"
        else:
            location = "missing"
        previous = unique.setdefault(aliases, location)
        _require(
            previous == location,
            "supplemental_dense_selected_target_location_conflict",
        )
        row_weighted_satisfied += int(location != "missing")
    counts = {
        location: sum(value == location for value in unique.values())
        for location in ("historical", "supplemental", "missing")
    }
    gate = dict(policy["presence_gate"])
    _require(
        len(unique) == int(gate["owner_selected_unique_target_count"])
        and counts["historical"]
        == int(gate["historical_present_unique_target_count"])
        and counts["supplemental"]
        == int(gate["supplemental_required_unique_target_count"])
        and counts["missing"] == 0
        and len(unique) == int(gate["federated_required_unique_target_count"])
        and row_weighted_satisfied
        == int(gate["row_weighted_required_target_count"]),
        "supplemental_dense_owner_selected_target_absent",
    )
    return {
        "owner_selected_unique_target_count": len(unique),
        "historical_present_unique_target_count": counts["historical"],
        "supplemental_present_unique_target_count": counts["supplemental"],
        "missing_unique_target_count": counts["missing"],
        "row_weighted_target_count": len(diagnostic_rows),
        "row_weighted_satisfied_count": row_weighted_satisfied,
        "status": "pass_10_of_10_unique_and_18_of_18_rows_present_after_successor_build",
    }


def _caught_code(action: Callable[[], Any]) -> str:
    try:
        action()
    except S1InternalSupplementalDenseIndexError as exc:
        return str(exc)
    raise S1InternalSupplementalDenseIndexError(
        "supplemental_dense_mutation_unexpectedly_passed"
    )


def _run_mutation_proof(
    *,
    specs: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    qrels: Mapping[str, Any],
    owner_acceptance: Mapping[str, Any],
    diagnostic: Mapping[str, Any],
    repo_root: Path,
    historical_runtime: Mapping[str, Any],
) -> dict[str, str]:
    dimension = int(policy["vector_contract"]["expected_embedding_dim"])
    duplicate = [dict(item) for item in specs] + [dict(specs[0])]
    missing_capture = [dict(item) for item in specs]
    missing_capture[0]["capture_digest"] = ""
    cross_manifest = [dict(item) for item in specs]
    cross_manifest[0]["ticker"] = "MU"
    without_required = [
        dict(item)
        for item in specs
        if str(item["evidence_id"])
        != "SUPP::DELL::000157199626000008::CHUNK_0059"
    ]
    partial_writer = _FakeWriter(partial_insert=True)
    raw_score = deepcopy(dict(policy["federation_contract"]))
    raw_score["merge_mode"] = "raw_score_descending"
    raw_score["raw_score_cross_collection_comparison_allowed"] = True
    outcomes = {
        "duplicate_evidence_identity": _caught_code(
            lambda: validate_vector_specs(duplicate, policy=policy)
        ),
        "missing_capture_digest": _caught_code(
            lambda: validate_vector_specs(missing_capture, policy=policy)
        ),
        "cross_manifest_source_mismatch": _caught_code(
            lambda: validate_vector_specs(cross_manifest, policy=policy)
        ),
        "owner_selected_target_absent": _caught_code(
            lambda: evaluate_federated_presence_gate(
                specs=without_required,
                qrels=qrels,
                owner_acceptance=owner_acceptance,
                diagnostic=diagnostic,
                policy=policy,
            )
        ),
        "historical_or_existing_target_collision": _caught_code(
            lambda: validate_target_isolation(
                policy,
                repo_root=repo_root,
                historical_runtime=historical_runtime,
                target_exists=True,
            )
        ),
        "embedding_dimension_mismatch": _caught_code(
            lambda: execute_index_build_plan(
                specs,
                policy=policy,
                embed_batch=_fake_embedder(
                    dimension=dimension, wrong_dimension=True
                ),
                writer=_FakeWriter(),
            )
        ),
        "partial_insert_acknowledgement": _caught_code(
            lambda: execute_index_build_plan(
                specs,
                policy=policy,
                embed_batch=_fake_embedder(dimension=dimension),
                writer=partial_writer,
            )
        ),
        "raw_score_federation": _caught_code(
            lambda: _validate_federation_contract(raw_score)
        ),
    }
    _require(
        set(outcomes) == set(policy["mutation_contract"])
        and all(value.startswith("supplemental_dense_") for value in outcomes.values())
        and partial_writer.aborted
        and not partial_writer.published,
        "supplemental_dense_mutation_proof_invalid",
    )
    return outcomes


def materialize_supplemental_dense_index_zero_call_proof(
    policy: Mapping[str, Any], *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    preflight = run_project_os_preflight(root, run_scope=RUN_SCOPE)
    _require(
        preflight.get("status") == "pass",
        "supplemental_dense_project_os_preflight_failed",
    )

    # Deliberately compile and terminally digest all 410 source-derived rows before
    # loading qrels. This makes selected-target identities unable to shape the build.
    specs, manifest_summaries = compile_supplemental_vector_specs(
        policy, repo_root=root
    )
    vector_spec_terminal_digest = canonical_digest(specs)

    immutable = dict(policy["immutable_inputs"])
    qrels = _read_json(root / str(immutable["research_qrels_ref"]))
    owner = _read_json(root / str(immutable["owner_qrels_acceptance_ref"]))
    diagnostic = _read_json(root / str(immutable["dense_index_diagnostic_ref"]))
    historical_runtime = _read_json(
        root / str(immutable["historical_milvus_runtime_ref"])
    )
    isolation = validate_target_isolation(
        policy, repo_root=root, historical_runtime=historical_runtime
    )
    presence = evaluate_federated_presence_gate(
        specs=specs,
        qrels=qrels,
        owner_acceptance=owner,
        diagnostic=diagnostic,
        policy=policy,
    )
    dimension = int(policy["vector_contract"]["expected_embedding_dim"])
    fake_writer = _FakeWriter()
    fake_execution = execute_index_build_plan(
        specs,
        policy=policy,
        embed_batch=_fake_embedder(dimension=dimension),
        writer=fake_writer,
    )
    _require(
        fake_writer.published and not fake_writer.aborted,
        "supplemental_dense_fake_terminalization_invalid",
    )
    mutation_outcomes = _run_mutation_proof(
        specs=specs,
        policy=policy,
        qrels=qrels,
        owner_acceptance=owner,
        diagnostic=diagnostic,
        repo_root=root,
        historical_runtime=historical_runtime,
    )
    fake_execution = {
        "fake_embedding_batch_count": fake_execution["embedding_batch_count"],
        "fake_embedding_vector_count": fake_execution["embedding_vector_count"],
        "fake_insert_batch_count": fake_execution["insert_batch_count"],
        "fake_inserted_vector_count": fake_execution["inserted_vector_count"],
        "terminal_count": fake_execution["terminal_count"],
    }
    ticker_counts: dict[str, int] = {}
    form_counts: dict[str, int] = {}
    for spec in specs:
        ticker = str(spec["ticker"])
        form = str(spec["form_type"])
        ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
        form_counts[form] = form_counts.get(form, 0) + 1
    body: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": "fin_0_1_3.S1.internal_supplemental_dense_index:v1",
        "run_scope": RUN_SCOPE,
        "recorded_at": "2026-08-09",
        "status": "terminal_succeeded_zero_call_supplemental_dense_build_proof",
        "project_os_preflight": {
            "status": str(preflight["status"]),
            "run_scope": str(preflight["run_scope"]),
            "open_full_chain_blocker_count": int(
                preflight["open_full_chain_blocker_count"]
            ),
        },
        "policy_digest": canonical_digest(policy),
        "source_inventory": {
            "manifest_count": len(manifest_summaries),
            "source_document_count": sum(
                item["source_document_count"] for item in manifest_summaries
            ),
            "vector_spec_count": len(specs),
            "unique_evidence_identity_count": len(
                {str(item["evidence_id"]) for item in specs}
            ),
            "ticker_counts": dict(sorted(ticker_counts.items())),
            "form_type_counts": dict(sorted(form_counts.items())),
            "manifests": manifest_summaries,
            "vector_spec_terminal_digest": vector_spec_terminal_digest,
            "qrels_loaded_after_vector_spec_terminal_digest": True,
        },
        "target_isolation": isolation,
        "federated_presence_gate": presence,
        "fake_execution": {
            **fake_execution,
            "published_only_after_exact_count": True,
            "historical_collection_write_count": 0,
        },
        "mutation_proof": {
            "scenario_count": len(mutation_outcomes),
            "all_failed_closed": True,
            "outcomes": mutation_outcomes,
        },
        "federation_contract": dict(policy["federation_contract"]),
        "execution_gate": {
            "zero_call_contract_passed": True,
            "real_embedding_build_admitted": False,
            "reason": "A separate fresh execution authority is required before one immutable 410-vector BGE/Milvus build.",
        },
        "observed_real_calls": {
            "network": 0,
            "provider": 0,
            "llm_model": 0,
            "document_fetch": 0,
            "real_embedding": 0,
            "milvus_read": 0,
            "milvus_write": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "preserved_boundaries": {
            "candidate_promoted_to_evidence": False,
            "semantic_ranking_quality_improved": False,
            "current_quarter_exact_sql": "0_of_6_open",
            "external_official_required_slot_coverage": "4_of_12_open_release_blocker",
            "downstream_utilization_proven": False,
            "product_acceptance": False,
            "release": "not_qualified",
        },
        "known_boundary": str(policy["known_boundary"]),
        "implementation": {
            "module_ref": "src/sec_agent/s1_internal_supplemental_dense_index.py",
            "policy_ref": "configs/runtime/fin_ia_0_1_3_s1_internal_supplemental_dense_index_policy_v1_0.json",
            "materializer_ref": "scripts/releases/materialize_fin_ia_0_1_3_s1_internal_supplemental_dense_index_zero_call_proof_v1_0.py",
        },
    }
    body["proof_digest"] = canonical_digest(body)
    return body


def validate_supplemental_dense_index_zero_call_proof(
    value: Mapping[str, Any]
) -> dict[str, Any]:
    body = dict(value)
    supplied = str(body.pop("proof_digest", ""))
    real_calls = dict(value.get("observed_real_calls") or {})
    source = dict(value.get("source_inventory") or {})
    gate = dict(value.get("federated_presence_gate") or {})
    mutation = dict(value.get("mutation_proof") or {})
    _require(
        value.get("schema_version") == RESULT_SCHEMA
        and value.get("status")
        == "terminal_succeeded_zero_call_supplemental_dense_build_proof"
        and supplied == canonical_digest(body)
        and source.get("vector_spec_count") == 410
        and source.get("unique_evidence_identity_count") == 410
        and source.get("qrels_loaded_after_vector_spec_terminal_digest") is True
        and gate.get("owner_selected_unique_target_count") == 10
        and gate.get("missing_unique_target_count") == 0
        and gate.get("row_weighted_satisfied_count") == 18
        and mutation.get("scenario_count") == 8
        and mutation.get("all_failed_closed") is True
        and all(int(value) == 0 for value in real_calls.values())
        and (value.get("execution_gate") or {}).get("real_embedding_build_admitted")
        is False,
        "supplemental_dense_zero_call_proof_invalid",
    )
    return dict(value)


__all__ = [
    "POLICY_SCHEMA",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "S1InternalSupplementalDenseIndexError",
    "compile_supplemental_vector_specs",
    "evaluate_federated_presence_gate",
    "execute_index_build_plan",
    "load_supplemental_dense_index_policy",
    "materialize_supplemental_dense_index_zero_call_proof",
    "validate_supplemental_dense_index_zero_call_proof",
    "validate_target_isolation",
    "validate_vector_specs",
]
