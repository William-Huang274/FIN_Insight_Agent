from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.runtime_resource_registry import read_registered_runtime_json
from sec_agent.research.reviewed_evidence_pack import canonical_digest


CURRENT_RETRIEVAL_SNAPSHOT_RESOURCE_ID = (
    "application.result.current_research_retrieval_snapshot"
)
EXPECTED_SCHEMA = "fin_ia_current_retrieval_snapshot_v1_0"
RETRIEVAL_PROJECTION_SCHEMA = "fin_ia_research_retrieval_projection_v1_0"


@dataclass(frozen=True)
class ResearchRetrievalPrincipal:
    mode: str
    permissions: frozenset[str]


class ResearchRetrievalServiceError(RuntimeError):
    def __init__(self, error_code: str, status_code: int = 500, **detail: Any):
        super().__init__(error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.detail = {"reason": error_code, **detail}


class ResearchRetrievalService:
    """Read-only product projection of the current S1 retrieval snapshot."""

    def __init__(self, *, snapshot: Mapping[str, Any]) -> None:
        self._snapshot = self._validate(snapshot)
        self._cases = {
            str(row["case_key"]): deepcopy(dict(row))
            for row in self._snapshot["cases"]
        }

    @classmethod
    def from_runtime_paths(
        cls,
        repository_root: str | Path,
    ) -> "ResearchRetrievalService":
        return cls(
            snapshot=read_registered_runtime_json(
                repository_root,
                CURRENT_RETRIEVAL_SNAPSHOT_RESOURCE_ID,
            )
        )

    def get_case(
        self,
        case_key: str,
        principal: ResearchRetrievalPrincipal,
    ) -> dict[str, Any]:
        self._require_read(principal)
        key = str(case_key).strip().upper()
        row = self._cases.get(key)
        if row is None:
            raise ResearchRetrievalServiceError(
                "research_retrieval_case_not_found", 404, case_key=case_key
            )
        retrieval = row["retrieval"]
        lanes = []
        for lane in retrieval["lane_results"]:
            lane_contract = lane["lane"]
            candidates = []
            for raw_candidate in lane["candidates"]:
                candidate = deepcopy(dict(raw_candidate))
                candidate.pop("reviewed_pack_match", None)
                candidates.append(candidate)
            lanes.append(
                {
                    "lane_id": lane_contract["lane_id"],
                    "slot_id": lane_contract["slot_id"],
                    "facet_id": lane_contract["facet_id"],
                    "business_question_zh": lane_contract["business_question_zh"],
                    "evidence_owner_tickers": deepcopy(
                        lane_contract["evidence_owner_tickers"]
                    ),
                    "required_source_roles": deepcopy(
                        lane_contract["required_source_roles"]
                    ),
                    "publication_date_lte": lane_contract["publication_date_lte"],
                    "candidates": candidates,
                    "missing_required_source_roles": deepcopy(
                        lane["missing_required_source_roles"]
                    ),
                    "exclusion_counts": deepcopy(lane["exclusion_counts"]),
                }
            )
        raw_summary = retrieval["summary"]
        summary = {
            key: deepcopy(raw_summary[key])
            for key in (
                "lane_count",
                "nonempty_lane_count",
                "slot_count",
                "unique_candidates",
                "slots_missing_required_source_roles",
                "hard_constraint_failures",
            )
        }
        body = {
            "schema_version": RETRIEVAL_PROJECTION_SCHEMA,
            "status": "typed_local_retrieval_snapshot_ready",
            "product_mode": "current",
            "case_key": key,
            "candidate_state": "candidate_not_evidence",
            "query_plan_digest": retrieval["query_plan_digest"],
            "result_digest": retrieval["result_digest"],
            "source_snapshot": deepcopy(self._snapshot["source_snapshot"]),
            "summary": summary,
            "source_gap_summary": deepcopy(row["source_gap_summary"]),
            "business_findings_zh": deepcopy(row["business_findings_zh"]),
            "lanes": lanes,
            "known_boundary": str(self._snapshot["known_boundary"]),
        }
        return {**body, "projection_digest": canonical_digest(body)}

    @staticmethod
    def _validate(snapshot: Mapping[str, Any]) -> dict[str, Any]:
        value = deepcopy(dict(snapshot))
        cases = value.get("cases")
        acceptance = value.get("acceptance")
        if not (
            value.get("schema_version") == EXPECTED_SCHEMA
            and value.get("status")
            in {
                "s1a_typed_local_retrieval_vertical_slice_ready",
                "s1b_current_source_object_retrieval_snapshot_ready_with_typed_gaps",
            }
            and isinstance(cases, list)
            and [row.get("case_key") for row in cases]
            == ["DELL", "MU", "NVDA"]
            and isinstance(acceptance, Mapping)
            and acceptance.get("model_calls") == 0
            and acceptance.get("network_calls") == 0
            and acceptance.get("complete_s1_claimed") is False
            and acceptance.get("evidence_pack_promoted") is False
            and acceptance.get("historical_corpus_sufficient_for_current_product")
            is False
            and str(value.get("known_boundary") or "")
        ):
            raise ResearchRetrievalServiceError(
                "research_retrieval_snapshot_invalid", 503
            )
        for row in cases:
            retrieval = row.get("retrieval")
            if not (
                isinstance(retrieval, Mapping)
                and retrieval.get("candidate_state") == "candidate_not_evidence"
                and not retrieval.get("summary", {}).get("hard_constraint_failures")
                and isinstance(retrieval.get("lane_results"), list)
            ):
                raise ResearchRetrievalServiceError(
                    "research_retrieval_case_snapshot_invalid", 503
                )
        return value

    @staticmethod
    def _require_read(principal: ResearchRetrievalPrincipal) -> None:
        if principal.mode != "current":
            raise ResearchRetrievalServiceError(
                "research_retrieval_current_mode_required", 403
            )
        if "current_product:read" not in principal.permissions:
            raise ResearchRetrievalServiceError(
                "research_retrieval_read_permission_required", 403
            )


__all__ = [
    "CURRENT_RETRIEVAL_SNAPSHOT_RESOURCE_ID",
    "ResearchRetrievalPrincipal",
    "ResearchRetrievalService",
    "ResearchRetrievalServiceError",
    "RETRIEVAL_PROJECTION_SCHEMA",
]
