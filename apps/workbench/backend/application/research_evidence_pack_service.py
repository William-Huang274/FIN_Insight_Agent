from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from urllib.parse import urlparse

from sec_agent.runtime_bridge.paths import RuntimePathRegistry
from sec_agent.runtime_resource_registry import read_registered_runtime_json
from sec_agent.research.reviewed_evidence_pack import (
    canonical_digest,
    file_sha256,
    validate_reviewed_evidence_pack,
)
from sec_agent.research.reviewed_evidence_anchor import (
    ReviewedEvidenceAnchorCatalog,
    ReviewedEvidenceAnchorError,
    load_reviewed_evidence_anchor_catalog,
    project_reviewed_claim_anchor,
    validate_anchor_catalog_pack_binding,
)
from sec_agent.research.actionable_research_state import (
    ActionableResearchStateError,
    compile_actionable_research_state,
)
from sec_agent.research.quantitative_authority import (
    QuantitativeAuthorityError,
    compile_quantitative_authority_state,
)
from retrieval.source_use_policy import (
    SourceUsePolicy,
    SourceUsePolicyError,
)
from retrieval.artifact_spine import ArtifactSpinePolicy
from retrieval.vertical_slice import (
    load_s1_vs1_vertical_slice_result,
    project_s1_vs1_case,
)
from retrieval.supplement_vertical import (
    SupplementVerticalError,
    project_capture_bound_supplement_lineage,
    resolve_supplement_successor_binding,
    validate_supplement_vertical_resource,
)
from retrieval.product_evidence_successor import (
    ProductEvidenceSuccessorError,
    project_current_product_evidence_successor_lineage,
)


CURRENT_RESEARCH_EVIDENCE_PACK_CONFIG_RESOURCE_ID = (
    "application.config.current_research_evidence_pack_projection"
)
CURRENT_S1_ARTIFACT_SPINE_POLICY_RESOURCE_ID = (
    "application.config.current_s1_artifact_spine_policy"
)
CURRENT_S1_VS1_VERTICAL_SLICE_RESOURCE_ID = (
    "application.result.current_s1_vs1_vertical_slice"
)
CURRENT_S1_VS4_SUPPLEMENT_VERTICAL_RESOURCE_ID = (
    "application.result.current_s1_vs4_supplement_vertical"
)
CURRENT_S1_PRODUCT_READINESS_CATALOG_RESOURCE_ID = (
    "application.config.current_s1_product_readiness_catalog"
)
CURRENT_S1_SOURCE_USE_POLICY_RESOURCE_ID = (
    "application.config.current_s1_source_use_policy"
)
EXPECTED_CONFIG_SCHEMA = (
    "fin_ia_current_research_evidence_pack_projection_config_v1_0"
)
EXPECTED_ANCHORED_CONFIG_SCHEMA = (
    "fin_ia_current_research_evidence_pack_projection_config_v1_1"
)
EXPECTED_RESULT_SCHEMAS = frozenset(
    {
        "fin_ia_0_1_3_s1_six_case_local_evidence_pack_result_v1_0",
        "fin_ia_current_research_evidence_pack_result_v1_1",
    }
)
EXPECTED_RESULT_STATUSES = frozenset(
    {
        "terminal_succeeded_six_case_local_evidence_packs_with_declared_gaps",
        "terminal_succeeded_current_pack_composition_with_declared_gaps",
    }
)
EXPECTED_RESULT_CONTRACTS = frozenset(
    {
        (
            "fin_ia_0_1_3_s1_six_case_local_evidence_pack_result_v1_0",
            "terminal_succeeded_six_case_local_evidence_packs_with_declared_gaps",
        ),
        (
            "fin_ia_current_research_evidence_pack_result_v1_1",
            "terminal_succeeded_current_pack_composition_with_declared_gaps",
        ),
    }
)
PROJECTION_SCHEMA = "fin_ia_current_research_evidence_pack_projection_v1_0"
EXPECTED_PRODUCT_READINESS_CATALOG_SCHEMA = (
    "fin_ia_current_s1_product_readiness_catalog_v1_1"
)
EXPECTED_PRODUCT_READINESS_RESULT_SCHEMA = (
    "fin_ia_s1_current_product_readiness_result_v1_1"
)
EXPECTED_PRODUCT_READINESS_PRIVATE_SCHEMA = (
    "fin_ia_s1_current_product_readiness_full_result_v1_1"
)
EXPECTED_CANDIDATE_REVIEW_PACKET_SCHEMA = (
    "fin_ia_s1_product_candidate_review_packet_v1_0"
)
EXPECTED_PRODUCT_READINESS_STATUS = (
    "current_product_pack_readiness_materialized"
)


@dataclass(frozen=True)
class ResearchEvidencePackPrincipal:
    mode: str
    permissions: frozenset[str]


class ResearchEvidencePackServiceError(RuntimeError):
    def __init__(self, error_code: str, status_code: int = 500, **detail: Any):
        super().__init__(error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.detail = {"reason": error_code, **detail}


def _require(
    condition: bool,
    code: str,
    status_code: int = 500,
    **detail: Any,
) -> None:
    if not condition:
        raise ResearchEvidencePackServiceError(code, status_code, **detail)


def _projection(value: dict[str, Any]) -> dict[str, Any]:
    return {**value, "projection_digest": canonical_digest(value)}


class ResearchEvidencePackService:
    """Read-only product adapter over digest-bound reviewed local Evidence Packs.

    The service deliberately owns no retrieval, model, network or Evidence
    promotion capability.  It turns an immutable S1 result and private object
    store into a safe Workbench projection without making the historical
    attempt module part of the long-term application API.
    """

    def __init__(
        self,
        *,
        config: Mapping[str, Any],
        result: Mapping[str, Any],
        private_object_root: str | Path,
        private_root_base: str | Path | None = None,
        reviewed_anchor_catalog: Mapping[str, Any] | None = None,
        s1_vertical_slice: Mapping[str, Any] | None = None,
        s1_supplement_vertical: Mapping[str, Any] | None = None,
        artifact_spine_policy: Mapping[str, Any] | None = None,
        product_readiness_catalog: Mapping[str, Any] | None = None,
        product_readiness_results: Mapping[
            str, Mapping[str, Any]
        ] | None = None,
        product_readiness_private_root: str | Path | None = None,
        source_use_policy: Mapping[str, Any] | None = None,
    ) -> None:
        self._config = self._validate_config(config)
        self._result = self._validate_result(result, self._config)
        try:
            self._anchor_catalog = (
                load_reviewed_evidence_anchor_catalog(reviewed_anchor_catalog)
                if reviewed_anchor_catalog is not None
                else None
            )
        except ReviewedEvidenceAnchorError as exc:
            raise ResearchEvidencePackServiceError(
                exc.code, 503
            ) from exc
        _require(
            (
                self._config["schema_version"] == EXPECTED_CONFIG_SCHEMA
                and self._anchor_catalog is None
            )
            or (
                self._config["schema_version"]
                == EXPECTED_ANCHORED_CONFIG_SCHEMA
                and self._anchor_catalog is not None
            ),
            "current_research_evidence_anchor_catalog_required",
            503,
        )
        self._object_root = Path(private_object_root).resolve()
        self._private_root_base = (
            Path(private_root_base).resolve()
            if private_root_base is not None
            else None
        )
        self._summaries = {
            str(row["case_key"]): deepcopy(dict(row))
            for row in self._result["case_summaries"]
            if str(row.get("case_key") or "")
            in self._config["published_case_keys"]
        }
        if (s1_vertical_slice is None) != (artifact_spine_policy is None):
            raise ResearchEvidencePackServiceError(
                "current_research_evidence_vertical_slice_policy_binding_invalid",
                503,
            )
        self._s1_vertical_slice = None
        if s1_vertical_slice is not None and artifact_spine_policy is not None:
            try:
                self._s1_vertical_slice = load_s1_vs1_vertical_slice_result(
                    s1_vertical_slice,
                    policy=ArtifactSpinePolicy.model_validate(
                        artifact_spine_policy
                    ),
                )
            except (ValueError, TypeError) as exc:
                raise ResearchEvidencePackServiceError(
                    "current_research_evidence_vertical_slice_invalid", 503
                ) from exc
        try:
            self._s1_supplement_vertical = (
                validate_supplement_vertical_resource(s1_supplement_vertical)
                if s1_supplement_vertical is not None
                else None
            )
        except SupplementVerticalError as exc:
            raise ResearchEvidencePackServiceError(
                "current_research_evidence_supplement_vertical_invalid",
                503,
                supplement_reason=str(exc),
            ) from exc
        if (
            self._s1_supplement_vertical is not None
            and self._s1_vertical_slice is None
        ):
            raise ResearchEvidencePackServiceError(
                "current_research_evidence_supplement_without_base_vertical", 503
            )
        try:
            self._source_use_policy = (
                SourceUsePolicy.from_mapping(source_use_policy)
                if source_use_policy is not None
                else None
            )
        except SourceUsePolicyError as exc:
            raise ResearchEvidencePackServiceError(
                "current_s1_source_use_policy_invalid", 503
            ) from exc
        self._product_readiness = self._validate_product_readiness_surface(
            product_readiness_catalog,
            product_readiness_results,
            product_readiness_private_root,
        )
        # Keep the already validated, immutable public receipts separately for
        # digest-bound lineage projection. The Workbench-safe projection above
        # intentionally adds bounded review excerpts and therefore no longer has
        # the same canonical digest as its source receipt.
        self._product_readiness_lineage = {
            str(case_key).strip().upper(): deepcopy(dict(value))
            for case_key, value in (product_readiness_results or {}).items()
        }

    @classmethod
    def from_runtime_paths(
        cls,
        repository_root: str | Path,
        runtime_paths: RuntimePathRegistry,
        *,
        load_s1_vertical_slice: bool = True,
    ) -> "ResearchEvidencePackService":
        config = read_registered_runtime_json(
            repository_root,
            CURRENT_RESEARCH_EVIDENCE_PACK_CONFIG_RESOURCE_ID,
        )
        result = read_registered_runtime_json(
            repository_root,
            str(config.get("source_result_resource_id") or ""),
        )
        anchor_catalog = (
            read_registered_runtime_json(
                repository_root,
                str(config.get("reviewed_anchor_catalog_resource_id") or ""),
            )
            if config.get("reviewed_anchor_catalog_resource_id")
            else None
        )
        product_readiness_catalog = read_registered_runtime_json(
            repository_root,
            CURRENT_S1_PRODUCT_READINESS_CATALOG_RESOURCE_ID,
        )
        product_readiness_results = {
            str(case_key).strip().upper(): read_registered_runtime_json(
                repository_root, str(resource_id)
            )
            for case_key, resource_id in dict(
                product_readiness_catalog.get("case_resource_ids") or {}
            ).items()
        }
        source_use_policy = read_registered_runtime_json(
            repository_root,
            CURRENT_S1_SOURCE_USE_POLICY_RESOURCE_ID,
        )
        default_object_root = (
            runtime_paths.reviewed_evidence_root
            / str(config.get("private_object_root_relative") or "")
        )
        return cls(
            config=config,
            result=result,
            private_object_root=default_object_root,
            private_root_base=runtime_paths.reviewed_evidence_root,
            reviewed_anchor_catalog=anchor_catalog,
            s1_vertical_slice=(
                read_registered_runtime_json(
                    repository_root,
                    CURRENT_S1_VS1_VERTICAL_SLICE_RESOURCE_ID,
                )
                if load_s1_vertical_slice
                else None
            ),
            s1_supplement_vertical=(
                read_registered_runtime_json(
                    repository_root,
                    CURRENT_S1_VS4_SUPPLEMENT_VERTICAL_RESOURCE_ID,
                )
                if load_s1_vertical_slice
                else None
            ),
            artifact_spine_policy=(
                read_registered_runtime_json(
                    repository_root,
                    CURRENT_S1_ARTIFACT_SPINE_POLICY_RESOURCE_ID,
                )
                if load_s1_vertical_slice
                else None
            ),
            product_readiness_catalog=product_readiness_catalog,
            product_readiness_results=product_readiness_results,
            product_readiness_private_root=runtime_paths.workbench_private_root,
            source_use_policy=source_use_policy,
        )

    @property
    def result_digest(self) -> str:
        return str(self._result["result_digest"])

    def list_cases(
        self, principal: ResearchEvidencePackPrincipal
    ) -> dict[str, Any]:
        self._require_read(principal)
        readiness = self.readiness()
        readiness_by_case = {
            str(row["case_key"]): bool(row["ready"])
            for row in readiness["cases"]
        }
        items = []
        artifacts = dict(self._result["pack_artifacts"])
        for case_key in self._config["published_case_keys"]:
            summary = self._summaries[case_key]
            artifact = dict(artifacts[case_key])
            item = {
                **deepcopy(summary),
                "artifact_digest": str(artifact["digest"]),
                "artifact_type": str(artifact["artifact_type"]),
                "evidence_object_ready": readiness_by_case[case_key],
            }
            product_readiness = self._product_readiness.get(case_key)
            if product_readiness is not None:
                item["product_readiness_state"] = str(
                    product_readiness["readiness_state"]
                )
                item["product_readiness_result_digest"] = str(
                    product_readiness["result_digest"]
                )
            if self._s1_vertical_slice is not None:
                item["canonical_vertical_ready"] = (
                    project_s1_vs1_case(
                        self._s1_vertical_slice, case_key=case_key
                    )
                    is not None
                )
            items.append(item)
        return _projection(
            {
                "schema_version": PROJECTION_SCHEMA,
                "projection_mode": "current",
                "status": "reviewed_evidence_catalog_ready",
                "result_digest": self.result_digest,
                "items": items,
                "evidence_objects_ready": bool(readiness["all_ready"]),
                "unavailable_case_keys": list(readiness["unavailable_case_keys"]),
                "next_cursor": None,
                "hard_boundaries": self._hard_boundaries(),
                "known_boundary": str(self._config["known_boundary"]),
            }
        )

    def readiness(self) -> dict[str, Any]:
        """Report mounted-object readiness without exposing private paths."""

        cases: list[dict[str, Any]] = []
        for case_key in self._config["published_case_keys"]:
            try:
                self._load_pack(str(case_key))
            except ResearchEvidencePackServiceError as exc:
                cases.append(
                    {
                        "case_key": str(case_key),
                        "ready": False,
                        "reason": exc.error_code,
                    }
                )
            else:
                cases.append(
                    {"case_key": str(case_key), "ready": True, "reason": None}
                )
        unavailable = [row["case_key"] for row in cases if not row["ready"]]
        return {
            "status": "ready" if not unavailable else "data_mount_required",
            "all_ready": not unavailable,
            "unavailable_case_keys": unavailable,
            "cases": cases,
        }

    def get_case(
        self,
        case_key: str,
        principal: ResearchEvidencePackPrincipal,
    ) -> dict[str, Any]:
        self._require_read(principal)
        normalized = str(case_key).strip().upper()
        if normalized not in self._summaries:
            raise ResearchEvidencePackServiceError(
                "current_research_evidence_pack_case_not_found",
                404,
                case_key=case_key,
            )
        pack, artifact = self._load_pack(normalized)
        source_by_ref = {
            str(row["material_ref"]): dict(row)
            for row in pack["source_materials"]
        }
        evidence = [
            self._project_evidence_item(dict(row), source_by_ref)
            for row in pack["evidence_items"]
        ]
        rejected = [
            self._project_rejected_item(dict(row))
            for row in pack["rejected_items"]
        ]
        body = {
            "schema_version": PROJECTION_SCHEMA,
            "projection_mode": "current",
            "status": "reviewed_local_evidence_pack_ready_with_declared_gaps",
            "result_digest": self.result_digest,
            "case_key": normalized,
            "evidence_object_ready": True,
            "artifact_digest": str(artifact["digest"]),
            "pack_payload_digest": str(pack["pack_payload_digest"]),
            "summary": deepcopy(self._summaries[normalized]),
            "evidence_items": evidence,
            "rejected_items": rejected,
            "residual_gaps": deepcopy(list(pack["residual_gaps"])),
            "consumer_contract": deepcopy(dict(pack["consumer_contract"])),
            "hard_boundaries": self._hard_boundaries(),
            "known_boundary": str(pack["known_boundary"]),
        }
        canonical_spine = self._canonical_spine_for_pack(
            normalized,
            artifact_digest=str(artifact["digest"]),
            pack_payload_digest=str(pack["pack_payload_digest"]),
        )
        if self._s1_vertical_slice is not None:
            body["canonical_spine"] = canonical_spine
        product_readiness = self._product_readiness.get(normalized)
        if product_readiness is not None:
            readiness_projection = deepcopy(product_readiness)
            quantitative_authority = readiness_projection.pop(
                "_quantitative_authority", None
            )
            body["product_readiness"] = readiness_projection
            if quantitative_authority is not None:
                body["quantitative_authority"] = deepcopy(
                    quantitative_authority
                )
            if (
                quantitative_authority is not None
                and self._source_use_policy is not None
            ):
                try:
                    body["actionable_research_state"] = (
                        compile_actionable_research_state(
                            case_key=normalized,
                            product_readiness=readiness_projection,
                            residual_gaps=body["residual_gaps"],
                            evidence_items=evidence,
                            quantitative_authority=quantitative_authority,
                            source_use_policy=self._source_use_policy,
                            recorded_at=str(
                                readiness_projection.get("recorded_at") or ""
                            ),
                        )
                    )
                except (
                    ActionableResearchStateError,
                    QuantitativeAuthorityError,
                ) as exc:
                    raise ResearchEvidencePackServiceError(
                        "current_actionable_research_state_invalid",
                        503,
                        case_key=normalized,
                        typed_reason=str(exc),
                    ) from exc
        return _projection(body)

    def _validate_product_readiness_surface(
        self,
        catalog: Mapping[str, Any] | None,
        results: Mapping[str, Mapping[str, Any]] | None,
        private_root: str | Path | None,
    ) -> dict[str, dict[str, Any]]:
        if catalog is None and results is None:
            return {}
        _require(
            isinstance(catalog, Mapping) and isinstance(results, Mapping),
            "current_s1_product_readiness_surface_incomplete",
            503,
        )
        _require(
            catalog.get("schema_version")
            == EXPECTED_PRODUCT_READINESS_CATALOG_SCHEMA
            and catalog.get("status")
            == "active_read_only_s1_product_readiness_catalog"
            and catalog.get("read_permission") == "current_product:read",
            "current_s1_product_readiness_catalog_invalid",
            503,
        )
        _require(
            private_root is not None
            and int(catalog.get("max_candidate_review_excerpt_chars") or 0)
            in range(120, 801),
            "current_s1_product_readiness_private_review_binding_invalid",
            503,
        )
        private_base = Path(private_root).resolve()
        excerpt_limit = int(catalog["max_candidate_review_excerpt_chars"])
        resource_ids = {
            str(key).strip().upper(): str(value)
            for key, value in dict(
                catalog.get("case_resource_ids") or {}
            ).items()
        }
        expected_keys = tuple(self._config["published_case_keys"])
        _require(
            tuple(resource_ids) == expected_keys
            and set(results) == set(expected_keys),
            "current_s1_product_readiness_case_partition_invalid",
            503,
        )
        validated: dict[str, dict[str, Any]] = {}
        for case_key in expected_keys:
            value = deepcopy(dict(results[case_key]))
            digest = str(value.pop("result_digest", ""))
            requests = value.get("requests")
            authority = value.get("authority") or {}
            private_ref = str(value.get("full_result_ref") or "")
            private_sha256 = str(value.get("full_result_sha256") or "")
            review_summary = value.get("candidate_review_packet_summary") or {}
            _require(
                value.get("schema_version")
                == EXPECTED_PRODUCT_READINESS_RESULT_SCHEMA
                and value.get("status") == EXPECTED_PRODUCT_READINESS_STATUS
                and value.get("case_key") == case_key
                and isinstance(requests, list)
                and int(value.get("request_count") or -1) == len(requests)
                and digest == canonical_digest(value)
                and authority.get("candidate_is_not_evidence") is True
                and authority.get("public_information_gap_authority") is False
                and authority.get("S1_qualification_claimed") is False,
                "current_s1_product_readiness_result_invalid",
                503,
                case_key=case_key,
            )
            private_result = self._load_product_readiness_private_result(
                private_base=private_base,
                repo_relative_ref=private_ref,
                expected_sha256=private_sha256,
                case_key=case_key,
            )
            private_readiness = deepcopy(
                dict(private_result.get("pack_readiness") or {})
            )
            _require(
                private_readiness.get("schema_version")
                == "fin_ia_s1_product_pack_readiness_v1_2"
                and private_readiness.get("case_key") == case_key
                and isinstance(private_readiness.get("requests"), list)
                and isinstance(
                    private_readiness.get("gap_eligibility_receipts"), list
                ),
                "current_s1_product_readiness_private_pack_invalid",
                503,
                case_key=case_key,
            )
            private_requests = {
                str(row.get("request_id") or ""): deepcopy(dict(row))
                for row in private_readiness["requests"]
            }
            private_gap_receipts: dict[str, list[dict[str, Any]]] = {}
            for raw_receipt in private_readiness["gap_eligibility_receipts"]:
                receipt = deepcopy(dict(raw_receipt))
                private_gap_receipts.setdefault(
                    str(receipt.get("request_id") or ""), []
                ).append(receipt)
            candidate_replay = self._load_candidate_replay(
                private_base=private_base,
                private_result=private_result,
                case_key=case_key,
            )
            try:
                quantitative_authority = compile_quantitative_authority_state(
                    case_key=case_key,
                    request_results=(
                        candidate_replay.get("product_projection", {}).get(
                            "request_results"
                        )
                        or ()
                    ),
                    recorded_at=str(value.get("recorded_at") or ""),
                )
            except QuantitativeAuthorityError as exc:
                raise ResearchEvidencePackServiceError(
                    "current_s2_quantitative_authority_invalid",
                    503,
                    case_key=case_key,
                    typed_reason=str(exc),
                ) from exc
            review_packet = self._validate_candidate_review_packet(
                private_result=private_result,
                public_summary=review_summary,
                case_key=case_key,
                excerpt_limit=excerpt_limit,
            )
            review_requests = {
                str(row.get("request_id") or ""): row
                for row in review_packet["requests"]
            }
            safe_requests = []
            for request in requests:
                _require(
                    isinstance(request, Mapping),
                    "current_s1_product_readiness_request_invalid",
                    503,
                    case_key=case_key,
                )
                request_id = str(request.get("request_id") or "")
                private_request = private_requests.get(request_id)
                private_review = review_requests.get(request_id)
                _require(
                    isinstance(private_request, Mapping)
                    and isinstance(private_review, Mapping)
                    and request.get("candidate_review_summary")
                    == {
                        "review_item_count": private_review.get(
                            "review_item_count"
                        ),
                        "human_review_required_count": private_review.get(
                            "human_review_required_count"
                        ),
                        "issue_class_counts": private_review.get(
                            "issue_class_counts"
                        ),
                        "request_review_digest": private_review.get(
                            "request_review_digest"
                        ),
                    },
                    "current_s1_product_readiness_review_request_binding_invalid",
                    503,
                    case_key=case_key,
                    request_id=request_id,
                )
                safe_request = {
                        key: deepcopy(request[key])
                        for key in (
                            "request_id",
                            "slot_id",
                            "facet_id",
                            "business_question_zh",
                            "material_scope_ready",
                            "requirement_count",
                            "requirement_state_counts",
                            "candidate_decision_counts",
                            "numeric_authority_state",
                            "readiness_state",
                            "unexecuted_or_unavailable_routes",
                            "candidate_review_summary",
                        )
                        if key in request
                }
                safe_request["candidate_review_items"] = [
                    self._project_candidate_review_item(
                        item, excerpt_limit=excerpt_limit
                    )
                    for item in private_review.get("review_items") or ()
                ]
                safe_request["route_execution_state"] = deepcopy(
                    dict(private_request.get("route_execution_state") or {})
                )
                safe_request["requirements"] = [
                    {
                        "requirement_id": str(
                            requirement.get("requirement_id") or ""
                        ),
                        "facet_id": str(requirement.get("facet_id") or ""),
                        "role": str(requirement.get("role") or ""),
                        "readiness_state": str(
                            requirement.get("readiness_state") or ""
                        ),
                        "candidate_set_complete_in_bounded_union": (
                            requirement.get(
                                "candidate_set_complete_in_bounded_union"
                            )
                            is True
                        ),
                        "accepted_reviewed_evidence_count": len(
                            requirement.get(
                                "accepted_reviewed_evidence_digests"
                            )
                            or ()
                        ),
                        "candidate_text_promoted": False,
                        "numeric_authority": False,
                    }
                    for requirement in private_request.get("requirements") or ()
                ]
                safe_request["gap_eligibility_receipts"] = [
                    {
                        key: deepcopy(receipt[key])
                        for key in (
                            "schema_version",
                            "request_id",
                            "slot_id",
                            "facet_id",
                            "requirement_id",
                            "requirement_role",
                            "readiness_state",
                            "candidate_set_complete_in_bounded_union",
                            "candidate_decision_counts",
                            "checks",
                            "blockers",
                            "earliest_responsible_layer",
                            "next_legal_action",
                            "eligible_as_true_public_information_gap",
                            "public_information_gap_authority",
                            "receipt_digest",
                        )
                        if key in receipt
                    }
                    for receipt in private_gap_receipts.get(request_id, ())
                ]
                safe_requests.append(safe_request)
            validated[case_key] = {
                key: deepcopy(value[key])
                for key in (
                    "schema_version",
                    "status",
                    "recorded_at",
                    "prepared_from_commit",
                    "case_key",
                    "readiness_state",
                    "request_count",
                    "accepted_reviewed_evidence_count",
                    "candidate_count",
                    "declared_pack_gap_receipt_count",
                    "gap_eligibility_receipt_count",
                    "request_state_counts",
                    "candidate_review_packet_summary",
                    "authority",
                    "known_boundary",
                )
                if key in value
            }
            validated[case_key]["requests"] = safe_requests
            validated[case_key]["research_as_of"] = str(
                private_readiness.get("research_as_of") or ""
            )
            validated[case_key]["_quantitative_authority"] = (
                quantitative_authority
            )
            validated[case_key]["result_digest"] = digest
        return validated

    @staticmethod
    def _load_product_readiness_private_result(
        *,
        private_base: Path,
        repo_relative_ref: str,
        expected_sha256: str,
        case_key: str,
    ) -> dict[str, Any]:
        ref = PurePosixPath(repo_relative_ref)
        _require(
            ref.parts[:2] == ("data", "workbench_private")
            and len(ref.parts) > 2
            and ".." not in ref.parts
            and len(expected_sha256) == 64,
            "current_s1_product_readiness_private_ref_invalid",
            503,
            case_key=case_key,
        )
        target = (private_base / Path(*ref.parts[2:])).resolve()
        try:
            target.relative_to(private_base)
        except ValueError as exc:
            raise ResearchEvidencePackServiceError(
                "current_s1_product_readiness_private_ref_escape",
                503,
                case_key=case_key,
            ) from exc
        _require(
            target.is_file() and file_sha256(target) == expected_sha256,
            "current_s1_product_readiness_private_result_unavailable",
            503,
            case_key=case_key,
        )
        try:
            value = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ResearchEvidencePackServiceError(
                "current_s1_product_readiness_private_result_invalid",
                503,
                case_key=case_key,
            ) from exc
        _require(
            isinstance(value, dict)
            and value.get("schema_version")
            == EXPECTED_PRODUCT_READINESS_PRIVATE_SCHEMA
            and value.get("case_key") == case_key,
            "current_s1_product_readiness_private_result_invalid",
            503,
            case_key=case_key,
        )
        body = dict(value)
        result_digest = str(body.pop("result_digest", ""))
        _require(
            result_digest == canonical_digest(body),
            "current_s1_product_readiness_private_result_digest_invalid",
            503,
            case_key=case_key,
        )
        return value

    @staticmethod
    def _load_candidate_replay(
        *,
        private_base: Path,
        private_result: Mapping[str, Any],
        case_key: str,
    ) -> dict[str, Any]:
        source_bindings = dict(private_result.get("source_bindings") or {})
        binding = dict(source_bindings.get("candidate_replay") or {})
        ref = PurePosixPath(str(binding.get("ref") or ""))
        expected_sha256 = str(binding.get("sha256") or "")
        expected_digest = str(binding.get("result_digest") or "")
        _require(
            ref.parts[:2] == ("data", "workbench_private")
            and len(ref.parts) > 2
            and ".." not in ref.parts
            and len(expected_sha256) == 64
            and len(expected_digest) == 64,
            "current_s1_candidate_replay_ref_invalid",
            503,
            case_key=case_key,
        )
        target = (private_base / Path(*ref.parts[2:])).resolve()
        try:
            target.relative_to(private_base)
        except ValueError as exc:
            raise ResearchEvidencePackServiceError(
                "current_s1_candidate_replay_ref_escape",
                503,
                case_key=case_key,
            ) from exc
        _require(
            target.is_file() and file_sha256(target) == expected_sha256,
            "current_s1_candidate_replay_unavailable",
            503,
            case_key=case_key,
        )
        try:
            value = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ResearchEvidencePackServiceError(
                "current_s1_candidate_replay_invalid",
                503,
                case_key=case_key,
            ) from exc
        body = dict(value)
        digest = str(body.pop("result_digest", ""))
        _require(
            value.get("schema_version")
            == "fin_ia_s1_source_route_truth_replay_successor_full_v1_0"
            and value.get("case_key") == case_key
            and digest == expected_digest
            and digest == canonical_digest(body)
            and isinstance(
                value.get("product_projection", {}).get("request_results"),
                list,
            ),
            "current_s1_candidate_replay_invalid",
            503,
            case_key=case_key,
        )
        return value

    @staticmethod
    def _validate_candidate_review_packet(
        *,
        private_result: Mapping[str, Any],
        public_summary: Mapping[str, Any],
        case_key: str,
        excerpt_limit: int,
    ) -> dict[str, Any]:
        packet = deepcopy(dict(private_result.get("candidate_review_packet") or {}))
        digest = str(packet.pop("review_packet_digest", ""))
        authority = packet.get("authority") or {}
        requests = packet.get("requests")
        _require(
            packet.get("schema_version") == EXPECTED_CANDIDATE_REVIEW_PACKET_SCHEMA
            and packet.get("status")
            == "candidate_review_packet_materialized_no_promotion"
            and packet.get("case_key") == case_key
            and isinstance(requests, list)
            and int(packet.get("request_count") or -1) == len(requests)
            and digest == canonical_digest(packet)
            and public_summary.get("review_packet_digest") == digest
            and public_summary.get("review_item_count")
            == packet.get("review_item_count")
            and public_summary.get("human_review_required_count")
            == packet.get("human_review_required_count")
            and public_summary.get("issue_class_counts")
            == packet.get("issue_class_counts")
            and authority.get("candidate_is_not_evidence") is True
            and authority.get("automatic_evidence_promotion") is False
            and authority.get("numeric_fact_authority") is False
            and authority.get("public_information_gap_authority") is False
            and authority.get("S1_qualification_claimed") is False,
            "current_s1_candidate_review_packet_invalid",
            503,
            case_key=case_key,
        )
        packet["review_packet_digest"] = digest
        for request in requests:
            _require(
                isinstance(request, Mapping)
                and int(request.get("review_item_count") or 0)
                == len(request.get("review_items") or ()),
                "current_s1_candidate_review_request_invalid",
                503,
                case_key=case_key,
            )
            for item in request.get("review_items") or ():
                source = item.get("source") if isinstance(item, Mapping) else None
                excerpt = (
                    str(source.get("bounded_excerpt") or "")
                    if isinstance(source, Mapping)
                    else ""
                )
                _require(
                    isinstance(item, Mapping)
                    and item.get("candidate_is_not_evidence") is True
                    and item.get("candidate_text_promoted") is False
                    and item.get("new_evidence_created") is False
                    and item.get("numeric_authority") is False
                    and bool(excerpt)
                    and len(excerpt) <= excerpt_limit,
                    "current_s1_candidate_review_item_invalid",
                    503,
                    case_key=case_key,
                )
        return packet

    @staticmethod
    def _project_candidate_review_item(
        item: Mapping[str, Any], *, excerpt_limit: int
    ) -> dict[str, Any]:
        source = dict(item.get("source") or {})
        url = str(source.get("source_url") or "")
        parsed = urlparse(url) if url else None
        _require(
            not url
            or (
                parsed is not None
                and parsed.scheme in {"http", "https"}
                and bool(parsed.netloc)
            ),
            "current_s1_candidate_review_source_url_invalid",
            503,
        )
        excerpt = str(source.get("bounded_excerpt") or "")
        _require(
            bool(excerpt) and len(excerpt) <= excerpt_limit,
            "current_s1_candidate_review_excerpt_invalid",
            503,
        )
        safe_source = {
            key: deepcopy(source[key])
            for key in (
                "company",
                "source_type",
                "source_tier",
                "publication_date",
                "period_end",
                "section",
                "subsection",
                "source_url",
                "surface_digest",
                "bounded_excerpt",
            )
            if key in source
        }
        projected = {
            key: deepcopy(item[key])
            for key in (
                "review_item_ref",
                "review_item_digest",
                "review_scope",
                "source_lineage_digest",
                "subject_ticker",
                "evidence_owner_ticker",
                "object_kind",
                "requirement_contexts",
                "advisory_evidence_role",
                "rank_trace",
                "route_membership",
                "decision_state",
                "reason_codes",
                "issue_classes",
                "next_legal_action",
                "human_review_required",
                "candidate_is_not_evidence",
                "candidate_text_promoted",
                "new_evidence_created",
                "numeric_authority",
            )
            if key in item
        }
        projected["source"] = safe_source
        return projected

    def _canonical_spine_for_pack(
        self,
        case_key: str,
        *,
        artifact_digest: str,
        pack_payload_digest: str,
    ) -> dict[str, Any] | None:
        if self._s1_vertical_slice is None:
            return None
        base_projection = project_s1_vs1_case(
            self._s1_vertical_slice, case_key=case_key
        )
        historical_projection = None
        historical_binding = resolve_supplement_successor_binding(
            self._s1_supplement_vertical, case_key=case_key
        )
        if historical_binding is not None:
            try:
                historical_projection = project_capture_bound_supplement_lineage(
                    base_projection=base_projection,
                    supplement_summary=self._s1_supplement_vertical,
                    case_key=case_key,
                    artifact_digest=historical_binding["artifact_digest"],
                    pack_payload_digest=historical_binding[
                        "pack_payload_digest"
                    ],
                )
            except SupplementVerticalError as exc:
                raise ResearchEvidencePackServiceError(
                    "current_research_evidence_historical_lineage_invalid",
                    503,
                    supplement_reason=str(exc),
                ) from exc
        try:
            successor = project_current_product_evidence_successor_lineage(
                historical_projection=historical_projection,
                current_result=self._result,
                product_readiness=self._product_readiness_lineage.get(case_key)
                or {},
                case_key=case_key,
            )
        except ProductEvidenceSuccessorError as exc:
            raise ResearchEvidencePackServiceError(
                "current_research_evidence_successor_lineage_invalid",
                503,
                successor_reason=str(exc),
            ) from exc
        if successor is not None:
            _require(
                successor["pack_binding"]
                == {
                    "case_key": case_key,
                    "artifact_digest": artifact_digest,
                    "pack_payload_digest": pack_payload_digest,
                },
                "current_research_evidence_successor_pack_binding_drift",
                503,
                case_key=case_key,
            )
            return successor
        try:
            return project_capture_bound_supplement_lineage(
                base_projection=base_projection,
                supplement_summary=self._s1_supplement_vertical,
                case_key=case_key,
                artifact_digest=artifact_digest,
                pack_payload_digest=pack_payload_digest,
            )
        except SupplementVerticalError as exc:
            raise ResearchEvidencePackServiceError(
                "current_research_evidence_vertical_slice_pack_binding_drift",
                503,
                supplement_reason=str(exc),
            ) from exc

    def _load_pack(self, case_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
        artifact = dict(self._result["pack_artifacts"][case_key])
        object_root = self._artifact_object_root(artifact)
        object_key = str(artifact.get("object_key") or "")
        relative = PurePosixPath(object_key)
        _require(
            object_key
            and not relative.is_absolute()
            and "\\" not in object_key
            and ".." not in relative.parts,
            "current_research_evidence_pack_object_key_invalid",
        )
        path = object_root.joinpath(*relative.parts).resolve()
        try:
            path.relative_to(object_root)
        except ValueError as exc:
            raise ResearchEvidencePackServiceError(
                "current_research_evidence_pack_object_escape"
            ) from exc
        _require(
            path.is_file(),
            "current_research_evidence_pack_object_unavailable",
            503,
            case_key=case_key,
        )
        _require(
            path.stat().st_size == int(artifact["byte_size"])
            and file_sha256(path) == str(artifact["digest"]),
            "current_research_evidence_pack_object_identity_drift",
            503,
            case_key=case_key,
        )
        try:
            pack = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ResearchEvidencePackServiceError(
                "current_research_evidence_pack_object_parse_failed",
                503,
                case_key=case_key,
            ) from exc
        _require(
            isinstance(pack, dict),
            "current_research_evidence_pack_object_not_mapping",
            503,
            case_key=case_key,
        )
        try:
            validate_reviewed_evidence_pack(pack)
        except (TypeError, ValueError, RuntimeError) as exc:
            raise ResearchEvidencePackServiceError(
                "current_research_evidence_pack_contract_invalid",
                503,
                case_key=case_key,
            ) from exc
        _require(
            pack.get("case_key") == case_key
            and pack.get("pack_payload_digest")
            == self._result["pack_payload_digests"][case_key],
            "current_research_evidence_pack_case_or_payload_drift",
            503,
            case_key=case_key,
        )
        self._validate_source_materials(pack, case_key)
        if self._anchor_catalog is not None:
            try:
                validate_anchor_catalog_pack_binding(
                    self._anchor_catalog,
                    case_key=case_key,
                    artifact_digest=str(artifact["digest"]),
                    pack_payload_digest=str(pack["pack_payload_digest"]),
                )
            except ReviewedEvidenceAnchorError as exc:
                raise ResearchEvidencePackServiceError(
                    exc.code, 503, case_key=case_key
                ) from exc
        return pack, artifact

    def _artifact_object_root(self, artifact: Mapping[str, Any]) -> Path:
        root_ref = str(artifact.get("private_object_root_relative") or "")
        if not root_ref:
            return self._object_root
        relative = PurePosixPath(root_ref)
        _require(
            self._private_root_base is not None
            and not relative.is_absolute()
            and "\\" not in root_ref
            and ".." not in relative.parts,
            "current_research_evidence_pack_private_root_invalid",
        )
        root = self._private_root_base.joinpath(*relative.parts).resolve()
        try:
            root.relative_to(self._private_root_base)
        except ValueError as exc:
            raise ResearchEvidencePackServiceError(
                "current_research_evidence_pack_private_root_escape"
            ) from exc
        return root

    @staticmethod
    def _validate_source_materials(pack: Mapping[str, Any], case_key: str) -> None:
        rows = [dict(row) for row in pack.get("source_materials") or ()]
        by_ref = {str(row.get("material_ref") or ""): row for row in rows}
        _require(
            rows and len(rows) == len(by_ref) and "" not in by_ref,
            "current_research_evidence_pack_source_partition_invalid",
            503,
            case_key=case_key,
        )
        for item in pack.get("evidence_items") or ():
            material = by_ref.get(str(item.get("source_material_ref") or ""))
            _require(
                material is not None,
                "current_research_evidence_pack_source_binding_missing",
                503,
                case_key=case_key,
            )
            source_text = str(material.get("source_text") or "")
            source_digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
            _require(
                source_digest == str(material.get("source_text_digest") or "")
                and source_digest == str(item.get("source_content_digest") or ""),
                "current_research_evidence_pack_source_content_drift",
                503,
                case_key=case_key,
            )

    def _project_evidence_item(
        self,
        item: dict[str, Any],
        source_by_ref: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        source = dict(source_by_ref[str(item["source_material_ref"])])
        raw_source_text = str(source.get("source_text") or "")
        source_text = (
            raw_source_text
            if self._anchor_catalog is not None
            else raw_source_text.strip()
        )
        maximum = int(self._config["max_reviewed_source_excerpt_chars"])
        excerpt_projection = {
            "reviewed_source_excerpt": source_text[:maximum],
            "excerpt_truncated": len(source_text) > maximum,
        }
        if self._anchor_catalog is not None:
            excerpt_projection.update(
                {
                    "excerpt_projection_kind": "bounded_source_prefix",
                    "reviewed_anchor_bound": False,
                }
            )
        if str(item.get("object_type") or "") == "claim" and (
            self._anchor_catalog is not None
        ):
            try:
                excerpt_projection = project_reviewed_claim_anchor(
                    catalog=self._anchor_catalog,
                    item=item,
                    source=source,
                )
            except ReviewedEvidenceAnchorError as exc:
                raise ResearchEvidencePackServiceError(
                    exc.code,
                    503,
                    case_key=str(item.get("case_key") or ""),
                    target_id=str(item.get("target_id") or ""),
                ) from exc
        projected = {
            key: deepcopy(item[key])
            for key in (
                "case_key",
                "target_id",
                "compiled_object_id",
                "source_record_id",
                "object_type",
                "disposition",
                "evidence_role",
                "publication_date",
                "source_reporting_period_end",
                "research_as_of",
                "relationship_directions",
                "slot_bindings",
                "numeric_use_boundary",
                "causal_attribution_authorized",
                "writer_citable",
                "evidence_item_digest",
            )
            if key in item
        }
        if isinstance(item.get("structured_metric"), Mapping):
            projected["structured_metric"] = self._safe_metric(
                item["structured_metric"]
            )
        projected["source"] = {
            key: deepcopy(source.get(key))
            for key in (
                "material_ref",
                "source_record_id",
                "evidence_owner_ticker",
                "source_tier",
                "source_type",
                "source_url",
                "publication_date",
                "period_end",
                "license_scope",
                "redistributable",
                "source_text_digest",
            )
        }
        if str(source.get("source_type") or "") == "PUBLIC_WEB":
            for key in (
                "claim_use",
                "speaker_entity",
                "proposition_id",
                "target_company_exact_numeric_authority",
            ):
                if key in item:
                    projected[key] = deepcopy(item[key])
            if "speaker_entity" in source:
                projected["source"]["speaker_entity"] = deepcopy(
                    source["speaker_entity"]
                )
        projected["source"].update(
            {
                **excerpt_projection,
                "excerpt_use_boundary": (
                    "Authenticated internal review only; never auto-promote the excerpt "
                    "into a deliverable or financial-truth store."
                ),
            }
        )
        return projected

    @staticmethod
    def _safe_metric(metric: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {
            "metric_id",
            "metric_name",
            "raw_value",
            "normalized_value",
            "currency",
            "unit",
            "scale",
            "period_start",
            "period_end",
            "fiscal_period",
            "table_path",
            "formula",
            "currency_unit_authority",
        }
        return {
            key: deepcopy(value)
            for key, value in metric.items()
            if key in allowed
        }

    @staticmethod
    def _project_rejected_item(item: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "target_id",
            "source_record_id",
            "object_type",
            "disposition",
            "rejection_code",
            "rejection_reason_zh",
            "writer_citable",
        }
        return {
            key: deepcopy(value)
            for key, value in item.items()
            if key in allowed
        }

    def _hard_boundaries(self) -> dict[str, Any]:
        policy = dict(self._config["surface_policy"])
        return {
            **deepcopy(policy),
            "model_calls": 0,
            "provider_calls": 0,
            "live_network_calls": 0,
            "mutable_writes": 0,
        }

    def _require_read(self, principal: ResearchEvidencePackPrincipal) -> None:
        if principal.mode != self._config["read_mode"]:
            raise ResearchEvidencePackServiceError(
                "current_research_evidence_pack_mode_required", 403
            )
        if self._config["read_permission"] not in principal.permissions:
            raise ResearchEvidencePackServiceError(
                "current_research_evidence_pack_read_permission_required", 403
            )

    @staticmethod
    def _validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
        value = deepcopy(dict(config))
        schema_version = str(value.get("schema_version") or "")
        cases = list(value.get("published_case_keys") or ())
        surface = value.get("surface_policy")
        common_fields = {
            "schema_version",
            "status",
            "source_result_resource_id",
            "private_object_root_relative",
            "published_case_keys",
            "read_mode",
            "read_permission",
            "max_reviewed_source_excerpt_chars",
            "surface_policy",
            "known_boundary",
        }
        expected_fields = (
            common_fields
            if schema_version == EXPECTED_CONFIG_SCHEMA
            else common_fields | {"reviewed_anchor_catalog_resource_id"}
        )
        _require(
            schema_version
            in {EXPECTED_CONFIG_SCHEMA, EXPECTED_ANCHORED_CONFIG_SCHEMA}
            and set(value) == expected_fields
            and value.get("status") == "active_read_only_workbench_projection"
            and str(value.get("source_result_resource_id") or "")
            and str(value.get("private_object_root_relative") or "")
            and cases == ["DELL", "MU", "NVDA"]
            and value.get("read_mode") == "current"
            and value.get("read_permission") == "current_product:read"
            and isinstance(value.get("max_reviewed_source_excerpt_chars"), int)
            and 200 <= int(value["max_reviewed_source_excerpt_chars"]) <= 4000
            and isinstance(surface, Mapping)
            and surface.get("full_source_material_exposure") is False
            and surface.get("raw_capture_exposure") is False
            and surface.get("automatic_evidence_promotion") is False
            and surface.get("automatic_financial_truth_write") is False
            and surface.get("model_provider_or_live_network_calls") == 0
            and surface.get("residual_gaps_remain_visible") is True,
            "current_research_evidence_pack_config_invalid",
        )
        if schema_version == EXPECTED_ANCHORED_CONFIG_SCHEMA:
            _require(
                str(value.get("reviewed_anchor_catalog_resource_id") or ""),
                "current_research_evidence_anchor_resource_invalid",
            )
        return value

    @staticmethod
    def _validate_result(
        result: Mapping[str, Any], config: Mapping[str, Any]
    ) -> dict[str, Any]:
        value = deepcopy(dict(result))
        body = deepcopy(value)
        digest = str(body.pop("result_digest", ""))
        summaries = {
            str(row.get("case_key") or ""): dict(row)
            for row in value.get("case_summaries") or ()
        }
        artifacts = value.get("pack_artifacts")
        payload_digests = value.get("pack_payload_digests")
        published = list(config["published_case_keys"])
        _require(
            value.get("schema_version") in EXPECTED_RESULT_SCHEMAS
            and value.get("status") in EXPECTED_RESULT_STATUSES
            and (value.get("schema_version"), value.get("status"))
            in EXPECTED_RESULT_CONTRACTS
            and digest == canonical_digest(body)
            and all(case_key in summaries for case_key in published)
            and isinstance(artifacts, Mapping)
            and isinstance(payload_digests, Mapping)
            and all(case_key in artifacts for case_key in published)
            and all(case_key in payload_digests for case_key in published)
            and value.get("stage_acceptance", {}).get(
                "complete_investment_report_claimed"
            )
            is False,
            "current_research_evidence_pack_result_invalid",
        )
        for case_key in published:
            artifact = artifacts[case_key]
            _require(
                isinstance(artifact, Mapping)
                and str(artifact.get("object_key") or "")
                and str(artifact.get("digest") or "")
                and type(artifact.get("byte_size")) is int,
                "current_research_evidence_pack_artifact_invalid",
            )
            _require(
                "private_object_root_relative" not in artifact
                or value.get("schema_version")
                == "fin_ia_current_research_evidence_pack_result_v1_1",
                "current_research_evidence_pack_artifact_root_version_invalid",
            )
        return value


__all__ = [
    "CURRENT_RESEARCH_EVIDENCE_PACK_CONFIG_RESOURCE_ID",
    "PROJECTION_SCHEMA",
    "ResearchEvidencePackPrincipal",
    "ResearchEvidencePackService",
    "ResearchEvidencePackServiceError",
]
