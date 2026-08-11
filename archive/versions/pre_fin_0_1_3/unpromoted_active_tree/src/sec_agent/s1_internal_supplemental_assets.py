from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from indexing.build_bm25_index import build_bm25_index
from indexing.build_object_bm25_index import build_object_bm25_index
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore


POLICY_SCHEMA = "fin_ia_0_1_3_s1_internal_supplemental_asset_policy_v1_0"
MANIFEST_SCHEMA = "fin_ia_0_1_3_s1_internal_supplemental_asset_manifest_v1_0"
CONTRACT_REF = "fin_0_1_3.S1.internal_supplemental_candidate_assets:v1"
POLICY_SCHEMA_V1_1 = "fin_ia_0_1_3_s1_internal_supplemental_asset_policy_v1_1"
MANIFEST_SCHEMA_V1_1 = (
    "fin_ia_0_1_3_s1_internal_supplemental_asset_manifest_v1_1"
)
CONTRACT_REF_V1_1 = "fin_0_1_3.S1.internal_supplemental_candidate_assets:v1.1"
POLICY_SCHEMA_V1_2 = "fin_ia_0_1_3_s1_internal_supplemental_asset_policy_v1_2"
MANIFEST_SCHEMA_V1_2 = (
    "fin_ia_0_1_3_s1_internal_supplemental_asset_manifest_v1_2"
)
CONTRACT_REF_V1_2 = "fin_0_1_3.S1.internal_supplemental_candidate_assets:v1.2"
_ASSET_SCHEMA_CONTRACTS = {
    POLICY_SCHEMA: (MANIFEST_SCHEMA, CONTRACT_REF),
    POLICY_SCHEMA_V1_1: (MANIFEST_SCHEMA_V1_1, CONTRACT_REF_V1_1),
    POLICY_SCHEMA_V1_2: (MANIFEST_SCHEMA_V1_2, CONTRACT_REF_V1_2),
}
_MANIFEST_SCHEMA_CONTRACTS = {
    manifest_schema: contract_ref
    for manifest_schema, contract_ref in _ASSET_SCHEMA_CONTRACTS.values()
}
RUN_SCOPE = "S1_INTERNAL_CURRENT_CORPUS_AND_INDEX_REFRESH"
FEDERATED_POLICY_SCHEMA = (
    "fin_ia_0_1_3_s1_internal_supplemental_candidate_refresh_policy_v1_0"
)
FEDERATED_CONTRACT_REF = (
    "fin_0_1_3.S1.internal_supplemental_candidate_refresh:v1.4"
)
FEDERATED_POLICY_SCHEMA_V1_1 = (
    "fin_ia_0_1_3_s1_internal_supplemental_candidate_refresh_policy_v1_1"
)
FEDERATED_CONTRACT_REF_V1_1 = (
    "fin_0_1_3.S1.internal_supplemental_candidate_refresh:v1.5"
)
FEDERATED_POLICY_SCHEMA_V1_2 = (
    "fin_ia_0_1_3_s1_internal_supplemental_candidate_refresh_policy_v1_2"
)
FEDERATED_CONTRACT_REF_V1_2 = (
    "fin_0_1_3.S1.internal_supplemental_candidate_refresh:v1.6"
)
_FEDERATED_SCHEMA_CONTRACTS = {
    FEDERATED_POLICY_SCHEMA: FEDERATED_CONTRACT_REF,
    FEDERATED_POLICY_SCHEMA_V1_1: FEDERATED_CONTRACT_REF_V1_1,
    FEDERATED_POLICY_SCHEMA_V1_2: FEDERATED_CONTRACT_REF_V1_2,
}


class S1InternalSupplementalAssetError(RuntimeError):
    pass


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise S1InternalSupplementalAssetError(
            "internal_supplemental_asset_json_object_required"
        )
    return value


def load_internal_supplemental_asset_policy(
    path: str | Path, *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path))
    expected = _ASSET_SCHEMA_CONTRACTS.get(str(policy.get("schema_version") or ""))
    if (
        expected is None
        or policy.get("manifest_schema") not in (None, expected[0])
        or policy.get("contract_ref") != expected[1]
        or policy.get("run_scope") != RUN_SCOPE
        or policy.get("binding_hash_profile")
        != "sha256_utf8_lf_normalized_v1"
    ):
        raise S1InternalSupplementalAssetError(
            "internal_supplemental_asset_policy_identity_invalid"
        )
    inputs = dict(policy.get("immutable_inputs") or {})
    for stem in ("source_acquisition_result", "benchmark_evidence_pack"):
        ref = str(inputs.get(f"{stem}_ref") or "")
        supplied = str(inputs.get(f"{stem}_sha256") or "")
        target = root / ref
        if not ref or not target.is_file() or _normalized_sha256(target) != supplied:
            raise S1InternalSupplementalAssetError(
                f"internal_supplemental_asset_binding_invalid:{stem}"
            )
    chunking = dict(policy.get("chunking") or {})
    minimum = int(chunking.get("minimum_chars") or 0)
    target = int(chunking.get("target_chars") or 0)
    maximum = int(chunking.get("maximum_chars") or 0)
    overlap = int(chunking.get("overlap_chars") or 0)
    if not (0 < overlap < minimum <= target <= maximum):
        raise S1InternalSupplementalAssetError(
            "internal_supplemental_asset_chunking_invalid"
        )
    bindings = list(policy.get("source_bindings") or [])
    expected_documents = int(policy.get("expected_source_documents") or 3)
    if (
        len(bindings) != expected_documents
        or len({str(item.get("target_id")) for item in bindings})
        != expected_documents
    ):
        raise S1InternalSupplementalAssetError(
            "internal_supplemental_asset_source_bindings_invalid"
        )
    hard = dict(policy.get("hard_boundaries") or {})
    if (
        hard.get("benchmark_url_used_for_discovery") is not False
        or hard.get("source_text_may_be_rewritten") is not False
        or hard.get("document_segment_is_adjudicated_claim") is not False
        or hard.get("candidate_may_be_promoted_to_evidence") is not False
        or any(
            int(hard.get(name, -1)) != 0
            for name in (
                "network",
                "provider",
                "model",
                "embedding",
                "rerank",
                "evidence_promotion",
            )
        )
    ):
        raise S1InternalSupplementalAssetError(
            "internal_supplemental_asset_boundary_invalid"
        )
    return policy


def load_internal_supplemental_candidate_refresh_policy(
    path: str | Path, *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path))
    expected_contract = _FEDERATED_SCHEMA_CONTRACTS.get(
        str(policy.get("schema_version") or "")
    )
    if (
        expected_contract is None
        or policy.get("contract_ref") != expected_contract
        or policy.get("run_scope") != RUN_SCOPE
        or policy.get("binding_hash_profile")
        != "sha256_utf8_lf_normalized_v1"
    ):
        raise S1InternalSupplementalAssetError(
            "internal_supplemental_candidate_refresh_policy_identity_invalid"
        )
    inputs = dict(policy.get("immutable_inputs") or {})
    for stem in ("base_candidate_policy",):
        ref = str(inputs.get(f"{stem}_ref") or "")
        supplied = str(inputs.get(f"{stem}_sha256") or "")
        target = root / ref
        if not ref or not target.is_file() or _normalized_sha256(target) != supplied:
            raise S1InternalSupplementalAssetError(
                f"internal_supplemental_candidate_refresh_binding_invalid:{stem}"
            )
    manifest_inputs = list(inputs.get("supplemental_asset_manifests") or [])
    if manifest_inputs:
        asset_keys = [str(item.get("asset_key") or "") for item in manifest_inputs]
        if (
            len(asset_keys) < 2
            or len(set(asset_keys)) != len(asset_keys)
            or any(not item for item in asset_keys)
        ):
            raise S1InternalSupplementalAssetError(
                "internal_supplemental_candidate_refresh_manifest_set_invalid"
            )
        for item in manifest_inputs:
            ref = str(item.get("ref") or "")
            supplied = str(item.get("sha256") or "")
            target = root / ref
            if (
                not ref
                or not target.is_file()
                or _normalized_sha256(target) != supplied
            ):
                raise S1InternalSupplementalAssetError(
                    "internal_supplemental_candidate_refresh_binding_invalid:"
                    f"manifest:{item.get('asset_key')}"
                )
    else:
        ref = str(inputs.get("supplemental_asset_manifest_ref") or "")
        supplied = str(inputs.get("supplemental_asset_manifest_sha256") or "")
        target = root / ref
        if not ref or not target.is_file() or _normalized_sha256(target) != supplied:
            raise S1InternalSupplementalAssetError(
                "internal_supplemental_candidate_refresh_binding_invalid:"
                "supplemental_asset_manifest"
            )
    hard = dict(policy.get("hard_boundaries") or {})
    if (
        hard.get("cross_asset_raw_score_comparison") is not False
        or hard.get("candidate_may_be_promoted_to_evidence") is not False
        or hard.get("BGE_fusion_rerank_admitted") is not False
        or any(
            int(hard.get(name, -1)) != 0
            for name in (
                "network",
                "provider",
                "model",
                "document_fetch",
                "embedding",
                "rerank",
                "evidence_promotion",
            )
        )
    ):
        raise S1InternalSupplementalAssetError(
            "internal_supplemental_candidate_refresh_boundary_invalid"
        )
    members = dict(policy.get("federated_asset_members") or {})
    if manifest_inputs:
        expected_sources = {
            "internal_bm25": ["base_candidate_policy.bm25_index_dir"]
            + [
                f"supplemental_asset_manifests.{item['asset_key']}.bm25_index_ref"
                for item in manifest_inputs
            ],
            "internal_object_bm25": [
                "base_candidate_policy.object_bm25_index_dir"
            ]
            + [
                "supplemental_asset_manifests."
                f"{item['asset_key']}.object_bm25_index_ref"
                for item in manifest_inputs
            ],
        }
    else:
        expected_sources = {
            "internal_bm25": [
                "base_candidate_policy.bm25_index_dir",
                "supplemental_asset_manifest.bm25_index_ref",
            ],
            "internal_object_bm25": [
                "base_candidate_policy.object_bm25_index_dir",
                "supplemental_asset_manifest.object_bm25_index_ref",
            ],
        }
    for route in ("internal_bm25", "internal_object_bm25"):
        route_members = list(members.get(route) or [])
        identities = [str(item.get("asset_id") or "") for item in route_members]
        sources = [str(item.get("source") or "") for item in route_members]
        if (
            len(route_members) != len(expected_sources[route])
            or len(set(identities)) != len(route_members)
            or any(not item for item in identities)
            or sources != expected_sources[route]
        ):
            raise S1InternalSupplementalAssetError(
                f"internal_supplemental_candidate_refresh_members_invalid:{route}"
            )
    return policy


def load_validated_supplemental_asset_manifest(
    path: str | Path, *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    manifest = _read_json(Path(path))
    body = {
        key: value
        for key, value in manifest.items()
        if key not in {"manifest_digest", "project_os_preflight", "implementation"}
    }
    manifest_schema = str(manifest.get("schema_version") or "")
    if (
        manifest_schema not in _MANIFEST_SCHEMA_CONTRACTS
        or manifest.get("contract_ref")
        != _MANIFEST_SCHEMA_CONTRACTS[manifest_schema]
        or manifest.get("run_scope") != RUN_SCOPE
        or manifest.get("status") != "supplemental_candidate_assets_built"
        or str(manifest.get("manifest_digest") or "") != canonical_digest(body)
        or any(int(value) != 0 for value in (manifest.get("observed_calls") or {}).values())
        or manifest.get("stage_boundary", {}).get("candidate_assets_built") is not True
        or manifest.get("stage_boundary", {}).get("candidate_ceiling_proven") is not False
    ):
        raise S1InternalSupplementalAssetError(
            "internal_supplemental_asset_manifest_identity_invalid"
        )
    private_root = (root / str(manifest.get("private_asset_root_ref") or "")).resolve()
    private_root.relative_to(root / "data" / "workbench_private")
    inventory = list(manifest.get("private_file_inventory") or [])
    if not inventory:
        raise S1InternalSupplementalAssetError(
            "internal_supplemental_asset_manifest_inventory_missing"
        )
    for item in inventory:
        target = (private_root / str(item.get("path") or "")).resolve()
        target.relative_to(private_root)
        if (
            not target.is_file()
            or target.stat().st_size != int(item.get("bytes") or 0)
            or hashlib.sha256(target.read_bytes()).hexdigest()
            != str(item.get("sha256") or "")
        ):
            raise S1InternalSupplementalAssetError(
                "internal_supplemental_asset_manifest_private_file_invalid"
            )
    return manifest


def deterministic_text_chunks(
    text: str,
    *,
    target_chars: int,
    minimum_chars: int,
    maximum_chars: int,
    overlap_chars: int,
) -> list[str]:
    compact = " ".join(str(text or "").split())
    if not compact:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(compact):
        desired = min(len(compact), start + target_chars)
        if desired < len(compact):
            lower = min(len(compact), start + minimum_chars)
            upper = min(len(compact), start + maximum_chars)
            boundary = compact.rfind(" ", lower, upper + 1)
            end = boundary if boundary >= lower else upper
        else:
            end = len(compact)
        chunk = compact[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(compact):
            break
        next_start = max(start + 1, end - overlap_chars)
        while next_start < len(compact) and compact[next_start] != " ":
            next_start += 1
        start = min(len(compact), next_start + 1)
    return chunks


class FederatedReadOnlyRetriever:
    """Deterministically federate immutable indexes without comparing raw scores."""

    def __init__(self, members: Sequence[tuple[str, Any]]) -> None:
        self.members = [(str(asset_id), retriever) for asset_id, retriever in members]
        if not self.members or len({item[0] for item in self.members}) != len(self.members):
            raise S1InternalSupplementalAssetError(
                "internal_supplemental_asset_federation_members_invalid"
            )

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        lanes = [
            [self._annotate(row, asset_id) for row in retriever.search(query, top_k=top_k, filters=filters)]
            for asset_id, retriever in self.members
        ]
        selected: list[dict[str, Any]] = []
        seen: set[str] = set()
        positions = [0 for _ in lanes]
        while len(selected) < max(1, int(top_k)):
            progressed = False
            for lane_index, rows in enumerate(lanes):
                while positions[lane_index] < len(rows):
                    row = rows[positions[lane_index]]
                    positions[lane_index] += 1
                    progressed = True
                    key = str(
                        row.get("object_id")
                        or row.get("evidence_id")
                        or (row.get("record") or {}).get("object_id")
                        or (row.get("record") or {}).get("evidence_id")
                        or (row.get("record") or {}).get("source_evidence_id")
                        or ""
                    )
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    selected.append({**row, "rank": len(selected) + 1})
                    break
                if len(selected) >= max(1, int(top_k)):
                    break
            if not progressed:
                break
        return selected

    @staticmethod
    def _annotate(row: Mapping[str, Any], asset_id: str) -> dict[str, Any]:
        result = dict(row)
        record = dict(result.get("record") or {})
        record["retrieval_asset_id"] = asset_id
        result["record"] = record
        result["retrieval_asset_id"] = asset_id
        return result

    def close(self) -> None:
        for _, retriever in self.members:
            close = getattr(retriever, "close", None)
            if callable(close):
                close()


def _validate_public_source_result(
    result: Mapping[str, Any]
) -> list[dict[str, Any]]:
    body = dict(result)
    supplied = str(body.pop("public_record_digest", ""))
    if supplied != canonical_digest(body):
        raise S1InternalSupplementalAssetError(
            "internal_supplemental_asset_source_result_invalid"
        )
    if (
        result.get("status") == "completed_all_targets_acquired"
        and int((result.get("observed_counts") or {}).get("acquired") or 0) == 3
        and int((result.get("observed_counts") or {}).get("network_calls") or 0)
        == 8
        and result.get("stage_boundary", {}).get(
            "internal_corpus_source_acquisition_proven"
        )
        is True
    ):
        return [dict(item) for item in result.get("source_results") or []]
    if (
        result.get("status") == "completed_target_acquired"
        and int((result.get("observed_counts") or {}).get("acquired") or 0) == 1
        and int((result.get("observed_counts") or {}).get("network_calls") or 0)
        == 1
        and result.get("stage_boundary", {}).get(
            "mu_10q_source_acquisition_proven"
        )
        is True
        and isinstance(result.get("source_result"), Mapping)
    ):
        return [dict(result["source_result"])]
    raise S1InternalSupplementalAssetError(
        "internal_supplemental_asset_source_result_invalid"
    )


def _file_inventory(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def build_internal_supplemental_assets(
    *, policy: Mapping[str, Any], repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    output_root = (root / str(policy["private_output_root"])).resolve()
    output_root.relative_to(root / "data" / "workbench_private")
    if output_root.exists():
        raise S1InternalSupplementalAssetError(
            "internal_supplemental_asset_output_already_exists"
        )
    inputs = dict(policy["immutable_inputs"])
    result = _read_json(root / str(inputs["source_acquisition_result_ref"]))
    source_results = _validate_public_source_result(result)
    benchmark = _read_json(root / str(inputs["benchmark_evidence_pack_ref"]))
    source_registry = {
        str(item.get("source_id") or ""): dict(item)
        for item in benchmark.get("source_registry") or []
    }
    bindings = {
        str(item["target_id"]): dict(item) for item in policy["source_bindings"]
    }
    runtime_ref = str(
        (result.get("public_private_separation") or {}).get("runtime_root_ref") or ""
    )
    runtime_root = (root / runtime_ref).resolve()
    runtime_root.relative_to(root / "data" / "workbench_private")
    store = FileCanonicalObjectStore(runtime_root / "objects")
    evidence_dir = output_root / "corpus"
    structured_dir = output_root / "structured"
    evidence_dir.mkdir(parents=True)
    structured_dir.mkdir(parents=True)
    evidence_path = evidence_dir / "supplemental_evidence.jsonl"
    claim_path = structured_dir / "supplemental_claims.jsonl"
    (structured_dir / "supplemental_tables.jsonl").write_text("", encoding="utf-8")
    (structured_dir / "supplemental_metrics.jsonl").write_text("", encoding="utf-8")
    chunking = dict(policy["chunking"])
    evidence_rows: list[dict[str, Any]] = []
    claim_rows: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    uncovered: set[str] = set()
    if len(source_results) != len(bindings):
        raise S1InternalSupplementalAssetError(
            "internal_supplemental_asset_source_result_count_invalid"
        )
    for source_result in source_results:
        target_id = str(source_result.get("target_id") or "")
        binding = bindings.get(target_id)
        if binding is None:
            raise S1InternalSupplementalAssetError(
                "internal_supplemental_asset_target_binding_missing"
            )
        source = dict(source_result.get("source") or {})
        selected_url = str(source.get("selected_url") or source.get("source_url") or "")
        parsed = store.get_json(
            str(source["parsed_capture_ref"]),
            expected_digest=str(source["parsed_capture_digest"]),
        )
        if (
            str(parsed.get("ticker") or "") != str(binding["ticker"])
            or str(parsed.get("accession_number") or "")
            != str(source["accession_number"])
            or str(parsed.get("source_url") or "") != selected_url
            or hashlib.sha256(str(parsed.get("text") or "").encode()).hexdigest()
            != str(source["parser_text_digest"])
        ):
            raise S1InternalSupplementalAssetError(
                "internal_supplemental_asset_parsed_capture_binding_invalid"
            )
        accepted_refs = [str(item) for item in binding["accepted_source_refs"]]
        unknown_refs = [item for item in accepted_refs if item not in source_registry]
        if unknown_refs and binding.get("accepted_source_ref_authority") != (
            "captured_lineage_extension"
        ):
            raise S1InternalSupplementalAssetError(
                "internal_supplemental_asset_expected_source_unknown"
            )
        chunks = deterministic_text_chunks(
            str(parsed["text"]),
            target_chars=int(chunking["target_chars"]),
            minimum_chars=int(chunking["minimum_chars"]),
            maximum_chars=int(chunking["maximum_chars"]),
            overlap_chars=int(chunking["overlap_chars"]),
        )
        if not chunks:
            raise S1InternalSupplementalAssetError(
                "internal_supplemental_asset_empty_source_text"
            )
        accession = "".join(character for character in str(source["accession_number"]) if character.isdigit())
        for ordinal, chunk in enumerate(chunks, start=1):
            evidence_id = f"SUPP::{binding['ticker']}::{accession}::CHUNK_{ordinal:04d}"
            common = {
                "ticker": str(binding["ticker"]),
                "fiscal_year": int(binding["reporting_fiscal_year"]),
                "section": "Official SEC source",
                "subsection": f"deterministic segment {ordinal}",
                "form_type": str(source["form_type"]),
                "source_type": str(source["form_type"]),
                "source_tier": str(binding["source_tier"]),
                "published_at": str(source["filing_date"]),
                "publication_date": str(source["filing_date"]),
                "source_url": selected_url,
                "accession_number": str(source["accession_number"]),
                "period_end": str(source["report_date"]),
                "metadata": {
                    "form_type": str(source["form_type"]),
                    "source_type": str(source["form_type"]),
                    "source_tier": str(binding["source_tier"]),
                    "filing_date": str(source["filing_date"]),
                    "accession_number": str(source["accession_number"]),
                    "source_url": selected_url,
                    "capture_digest": str(source["parsed_capture_digest"]),
                    "candidate_only_not_evidence": True,
                },
            }
            evidence_rows.append(
                {
                    "evidence_id": evidence_id,
                    "evidence_type": "official_source_document_segment",
                    "text": chunk,
                    **common,
                }
            )
            claim_rows.append(
                {
                    "object_id": f"{evidence_id}::DOCUMENT_SEGMENT",
                    "object_type": "claim",
                    "source_evidence_id": evidence_id,
                    "claim_text": chunk,
                    "claim_type": "document_segment_candidate_not_adjudicated_claim",
                    "polarity": "unclassified",
                    "extraction_method": "deterministic_source_segmentation",
                    **common,
                }
            )
        uncovered.update(str(item) for item in binding["uncovered_source_refs"])
        sources.append(
            {
                "target_id": target_id,
                "ticker": str(binding["ticker"]),
                "accession_number": str(source["accession_number"]),
                "form_type": str(source["form_type"]),
                "filing_date": str(source["filing_date"]),
                "report_date": str(source["report_date"]),
                "selected_url": selected_url,
                "parsed_capture_ref": str(source["parsed_capture_ref"]),
                "parsed_capture_digest": str(source["parsed_capture_digest"]),
                "accepted_source_refs": accepted_refs,
                "uncovered_source_refs": list(binding["uncovered_source_refs"]),
                "equivalence_mode": str(binding["equivalence_mode"]),
                "chunk_count": len(chunks),
            }
        )
    evidence_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in evidence_rows),
        encoding="utf-8",
    )
    claim_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in claim_rows),
        encoding="utf-8",
    )
    bm25_dir = output_root / "bm25"
    object_dir = output_root / "object_bm25"
    bm25_metadata = build_bm25_index(evidence_path, bm25_dir)
    object_metadata = build_object_bm25_index(
        structured_dir,
        object_dir,
        prefix="supplemental",
        record_mode="full",
    )
    file_inventory = _file_inventory(output_root)
    body = {
        "schema_version": str(policy.get("manifest_schema") or MANIFEST_SCHEMA),
        "contract_ref": str(policy["contract_ref"]),
        "run_scope": RUN_SCOPE,
        "status": "supplemental_candidate_assets_built",
        "source_acquisition_result_digest": str(result["result_digest"]),
        "private_asset_root_ref": output_root.relative_to(root).as_posix(),
        "bm25_index_ref": bm25_dir.relative_to(root).as_posix(),
        "object_bm25_index_ref": object_dir.relative_to(root).as_posix(),
        "source_bindings": sources,
        "uncovered_expected_source_refs": sorted(uncovered),
        "record_counts": {
            "source_documents": len(sources),
            "evidence_chunks": len(evidence_rows),
            "document_segment_objects": len(claim_rows),
            "bm25_records": int(bm25_metadata["records"]),
            "object_bm25_records": int(object_metadata["records"]),
        },
        "private_file_inventory": file_inventory,
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "model": 0,
            "embedding": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "stage_boundary": {
            "candidate_assets_built": True,
            "candidate_ceiling_proven": False,
            "qrels_owner_reviewed": False,
            "BGE_fusion_rerank_admitted": False,
            "evidence_or_release": False,
        },
        "known_boundary": str(
            policy.get("known_boundary")
            or (
                "Document segments preserve captured source text and are candidate-only. "
                "They are not adjudicated claims or Evidence."
            )
        ),
    }
    return {**body, "manifest_digest": canonical_digest(body)}


__all__ = [
    "CONTRACT_REF",
    "CONTRACT_REF_V1_1",
    "CONTRACT_REF_V1_2",
    "FEDERATED_CONTRACT_REF",
    "FEDERATED_CONTRACT_REF_V1_1",
    "FEDERATED_CONTRACT_REF_V1_2",
    "FEDERATED_POLICY_SCHEMA",
    "FEDERATED_POLICY_SCHEMA_V1_1",
    "FEDERATED_POLICY_SCHEMA_V1_2",
    "FederatedReadOnlyRetriever",
    "MANIFEST_SCHEMA",
    "MANIFEST_SCHEMA_V1_1",
    "MANIFEST_SCHEMA_V1_2",
    "POLICY_SCHEMA",
    "POLICY_SCHEMA_V1_1",
    "POLICY_SCHEMA_V1_2",
    "RUN_SCOPE",
    "S1InternalSupplementalAssetError",
    "build_internal_supplemental_assets",
    "deterministic_text_chunks",
    "load_internal_supplemental_asset_policy",
    "load_internal_supplemental_candidate_refresh_policy",
    "load_validated_supplemental_asset_manifest",
]
