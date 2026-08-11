from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date
import re
from pathlib import Path
from typing import Any, Mapping

from sec_agent.runtime_resource_registry import read_registered_runtime_json
from sec_agent.research.reviewed_evidence_pack import canonical_digest

from .research_evidence_pack_service import (
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
    ResearchEvidencePackServiceError,
)


CURRENT_RESEARCH_WORKSPACE_CATALOG_RESOURCE_ID = (
    "application.config.current_research_workspace_catalog"
)
EXPECTED_CONFIG_SCHEMA = "fin_ia_research_workspace_catalog_v1_0"
WORKSPACE_PROJECTION_SCHEMA = "fin_ia_research_workspace_projection_v1_0"
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ISSUER_ID = re.compile(r"^[0-9]{10}$")


@dataclass(frozen=True)
class ResearchWorkspacePrincipal:
    mode: str
    permissions: frozenset[str]


class ResearchWorkspaceServiceError(RuntimeError):
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
        raise ResearchWorkspaceServiceError(code, status_code, **detail)


def _projection(value: dict[str, Any]) -> dict[str, Any]:
    return {**value, "projection_digest": canonical_digest(value)}


class ResearchWorkspaceService:
    """Primary, version-neutral product adapter for reviewed research cases.

    A Case is admitted only when its typed issuer identity and research context
    are bound to one immutable Evidence Pack result, artifact and payload.  The
    service owns no retrieval, model, network or write capability.
    """

    def __init__(
        self,
        *,
        config: Mapping[str, Any],
        evidence_packs: ResearchEvidencePackService,
    ) -> None:
        self._config = self._validate_config(config)
        self._evidence_packs = evidence_packs
        self._cases = {
            str(row["case_id"]): deepcopy(dict(row))
            for row in self._config["cases"]
        }
        self._validate_all_bindings()

    @classmethod
    def from_runtime_paths(
        cls,
        repository_root: str | Path,
        evidence_packs: ResearchEvidencePackService,
    ) -> "ResearchWorkspaceService":
        return cls(
            config=read_registered_runtime_json(
                repository_root,
                CURRENT_RESEARCH_WORKSPACE_CATALOG_RESOURCE_ID,
            ),
            evidence_packs=evidence_packs,
        )

    def list_cases(
        self, principal: ResearchWorkspacePrincipal
    ) -> dict[str, Any]:
        self._require_read(principal)
        pack_projection = self._evidence_packs.list_cases(
            self._pack_principal(principal)
        )
        summaries = {
            str(row["case_key"]): dict(row)
            for row in pack_projection["items"]
        }
        items = [
            self._case_summary(row, summaries[str(row["case_key"])])
            for row in self._config["cases"]
        ]
        return _projection(
            {
                "schema_version": WORKSPACE_PROJECTION_SCHEMA,
                "status": "identity_bound_research_case_catalog_ready",
                "product_mode": "current",
                "primary_route": self._config["surface_policy"]["primary_route"],
                "evidence_pack_result_digest": self._evidence_packs.result_digest,
                "items": items,
                "evidence_objects_ready": bool(
                    pack_projection["evidence_objects_ready"]
                ),
                "unavailable_case_keys": deepcopy(
                    pack_projection["unavailable_case_keys"]
                ),
                "next_cursor": None,
                "surface_policy": deepcopy(self._config["surface_policy"]),
                "known_boundary": str(self._config["known_boundary"]),
            }
        )

    def get_case(
        self,
        case_id: str,
        principal: ResearchWorkspacePrincipal,
    ) -> dict[str, Any]:
        self._require_read(principal)
        row = self._case_for_id(case_id)
        pack = self._get_pack(row, principal)
        self._validate_binding(row, pack)
        body = {
            "schema_version": WORKSPACE_PROJECTION_SCHEMA,
            "status": "identity_bound_research_case_ready",
            "product_mode": "current",
            **self._case_summary(
                row,
                {
                    **dict(pack["summary"]),
                    "evidence_object_ready": bool(
                        pack["evidence_object_ready"]
                    ),
                },
            ),
            "research_context": deepcopy(row["research_context"]),
            "evidence_pack_uri": (
                f"/api/v1/research-cases/{row['case_id']}/evidence"
            ),
            "surface_policy": deepcopy(self._config["surface_policy"]),
            "known_boundary": str(self._config["known_boundary"]),
        }
        return _projection(body)

    def get_evidence(
        self,
        case_id: str,
        principal: ResearchWorkspacePrincipal,
    ) -> dict[str, Any]:
        self._require_read(principal)
        row = self._case_for_id(case_id)
        pack = self._get_pack(row, principal)
        binding = self._validate_binding(row, pack)
        return _projection(
            {
                "schema_version": WORKSPACE_PROJECTION_SCHEMA,
                "status": "identity_bound_reviewed_evidence_ready",
                "product_mode": "current",
                "case_id": str(row["case_id"]),
                "case_version": int(row["case_version"]),
                "case_key": str(row["case_key"]),
                "subject": deepcopy(row["subject"]),
                "subject_digest": canonical_digest(row["subject"]),
                "research_context": deepcopy(row["research_context"]),
                "pack_binding": binding,
                "evidence_items": deepcopy(pack["evidence_items"]),
                "rejected_items": deepcopy(pack["rejected_items"]),
                "residual_gaps": deepcopy(pack["residual_gaps"]),
                "consumer_contract": deepcopy(pack["consumer_contract"]),
                "hard_boundaries": deepcopy(pack["hard_boundaries"]),
                "known_boundary": str(self._config["known_boundary"]),
            }
        )

    def _validate_all_bindings(self) -> None:
        principal = ResearchWorkspacePrincipal(
            mode=str(self._config["product_mode"]),
            permissions=frozenset({str(self._config["read_permission"])}),
        )
        _require(
            self._evidence_packs.result_digest
            == self._config["evidence_pack_result_digest"],
            "research_workspace_result_digest_drift",
            503,
        )
        pack_list = self._evidence_packs.list_cases(
            self._pack_principal(principal)
        )
        observed_keys = [str(row["case_key"]) for row in pack_list["items"]]
        expected_keys = [str(row["case_key"]) for row in self._config["cases"]]
        _require(
            observed_keys == expected_keys,
            "research_workspace_case_partition_drift",
            503,
            expected_case_keys=expected_keys,
            observed_case_keys=observed_keys,
        )
        summaries = {
            str(row["case_key"]): dict(row)
            for row in pack_list["items"]
        }
        for row in self._config["cases"]:
            case_key = str(row["case_key"])
            _require(
                summaries[case_key].get("artifact_digest")
                == row["evidence_pack_binding"]["pack_artifact_digest"]
                and row["evidence_pack_binding"]["pack_case_key"]
                == case_key,
                "research_workspace_case_pack_binding_drift",
                503,
                case_id=row.get("case_id"),
                case_key=case_key,
            )

    def _validate_binding(
        self,
        row: Mapping[str, Any],
        pack: Mapping[str, Any],
    ) -> dict[str, Any]:
        expected = dict(row["evidence_pack_binding"])
        context = dict(row["research_context"])
        case_key = str(row["case_key"])
        research_dates = {
            str(item.get("research_as_of") or "")
            for item in pack.get("evidence_items") or ()
        }
        _require(
            pack.get("case_key") == case_key
            and str(row["subject"]["ticker"]) == case_key
            and pack.get("result_digest")
            == self._config["evidence_pack_result_digest"]
            and expected.get("pack_case_key") == case_key
            and pack.get("artifact_digest")
            == expected["pack_artifact_digest"]
            and pack.get("pack_payload_digest")
            == expected["pack_payload_digest"]
            and research_dates == {str(context["research_as_of"])},
            "research_workspace_case_pack_binding_drift",
            503,
            case_id=row.get("case_id"),
            case_key=case_key,
        )
        binding = {
            "binding_state": "identity_and_digest_bound",
            "case_id": str(row["case_id"]),
            "case_version": int(row["case_version"]),
            "case_subject_digest": canonical_digest(row["subject"]),
            "pack_case_key": case_key,
            "evidence_pack_result_digest": str(pack["result_digest"]),
            "pack_artifact_digest": str(pack["artifact_digest"]),
            "pack_payload_digest": str(pack["pack_payload_digest"]),
            "research_as_of": str(context["research_as_of"]),
        }
        return {**binding, "binding_digest": canonical_digest(binding)}

    def _case_summary(
        self,
        row: Mapping[str, Any],
        pack_summary: Mapping[str, Any],
    ) -> dict[str, Any]:
        binding = {
            "binding_state": "identity_and_digest_bound",
            "case_id": str(row["case_id"]),
            "case_version": int(row["case_version"]),
            "case_subject_digest": canonical_digest(row["subject"]),
            "pack_case_key": str(row["case_key"]),
            "evidence_pack_result_digest": str(
                self._config["evidence_pack_result_digest"]
            ),
            "pack_artifact_digest": str(
                row["evidence_pack_binding"]["pack_artifact_digest"]
            ),
            "pack_payload_digest": str(
                row["evidence_pack_binding"]["pack_payload_digest"]
            ),
            "research_as_of": str(row["research_context"]["research_as_of"]),
        }
        binding["binding_digest"] = canonical_digest(binding)
        return {
            "case_id": str(row["case_id"]),
            "case_version": int(row["case_version"]),
            "case_key": str(row["case_key"]),
            "subject": deepcopy(row["subject"]),
            "subject_digest": canonical_digest(row["subject"]),
            "research_as_of": str(row["research_context"]["research_as_of"]),
            "language": str(row["research_context"]["language"]),
            "pack_binding": binding,
            "evidence_summary": {
                key: deepcopy(pack_summary[key])
                for key in (
                    "status",
                    "accepted_evidence_items",
                    "direct_evidence_items",
                    "bounded_context_items",
                    "rejected_items",
                    "residual_gaps",
                    "source_materials",
                )
                if key in pack_summary
            },
            "evidence_object_ready": bool(
                pack_summary.get("evidence_object_ready")
            ),
            "available_surfaces": (
                deepcopy(self._config["surface_policy"]["available_surfaces"])
                if pack_summary.get("evidence_object_ready")
                else []
            ),
        }

    def _case_for_id(self, case_id: str) -> dict[str, Any]:
        normalized = str(case_id).strip().lower()
        row = self._cases.get(normalized)
        if row is None:
            raise ResearchWorkspaceServiceError(
                "research_workspace_case_not_found",
                404,
                case_id=case_id,
            )
        return deepcopy(row)

    def _get_pack(
        self,
        row: Mapping[str, Any],
        principal: ResearchWorkspacePrincipal,
    ) -> dict[str, Any]:
        try:
            return self._evidence_packs.get_case(
                str(row["case_key"]), self._pack_principal(principal)
            )
        except ResearchEvidencePackServiceError as exc:
            detail = {
                key: value
                for key, value in exc.detail.items()
                if key != "reason"
            }
            raise ResearchWorkspaceServiceError(
                exc.error_code,
                exc.status_code,
                **detail,
            ) from exc

    def _require_read(self, principal: ResearchWorkspacePrincipal) -> None:
        if principal.mode != self._config["product_mode"]:
            raise ResearchWorkspaceServiceError(
                "research_workspace_current_mode_required", 403
            )
        if self._config["read_permission"] not in principal.permissions:
            raise ResearchWorkspaceServiceError(
                "research_workspace_read_permission_required", 403
            )

    @staticmethod
    def _pack_principal(
        principal: ResearchWorkspacePrincipal,
    ) -> ResearchEvidencePackPrincipal:
        return ResearchEvidencePackPrincipal(
            mode=principal.mode,
            permissions=principal.permissions,
        )

    @staticmethod
    def _validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
        value = deepcopy(dict(config))
        cases = list(value.get("cases") or ())
        surface = value.get("surface_policy")
        _require(
            value.get("schema_version") == EXPECTED_CONFIG_SCHEMA
            and value.get("status") == "active_read_only_research_workspace"
            and value.get("product_mode") == "current"
            and value.get("read_permission") == "current_product:read"
            and bool(_DIGEST.fullmatch(str(value.get("evidence_pack_result_digest") or "")))
            and isinstance(surface, Mapping)
            and surface.get("primary_route") == "/workspace"
            and surface.get("available_surfaces") == ["overview", "evidence"]
            and surface.get("mutable_case_creation") is False
            and surface.get("complete_investment_report_claimed") is False
            and surface.get("model_or_network_calls") == 0
            and surface.get("residual_gaps_remain_visible") is True
            and str(value.get("known_boundary") or ""),
            "research_workspace_config_invalid",
        )
        _require(
            [row.get("case_key") for row in cases] == ["DELL", "MU", "NVDA"]
            and [row.get("case_id") for row in cases]
            == ["case_dell_current", "case_mu_current", "case_nvda_current"],
            "research_workspace_case_catalog_invalid",
        )
        for row in cases:
            _require(
                ResearchWorkspaceService._valid_case_row(row),
                "research_workspace_case_contract_invalid",
                case_id=row.get("case_id"),
            )
        return value

    @staticmethod
    def _valid_case_row(row: Mapping[str, Any]) -> bool:
        subject = row.get("subject")
        context = row.get("research_context")
        binding = row.get("evidence_pack_binding")
        if not all(
            isinstance(value, Mapping)
            for value in (subject, context, binding)
        ):
            return False
        try:
            date.fromisoformat(str(context.get("research_as_of") or ""))
        except ValueError:
            return False
        aliases = subject.get("aliases")
        return bool(
            row.get("case_version") == 1
            and str(row.get("case_key") or "")
            == str(subject.get("ticker") or "")
            and str(subject.get("entity_id") or "")
            == f"sec_issuer_{subject.get('issuer_id')}"
            and _ISSUER_ID.fullmatch(str(subject.get("issuer_id") or ""))
            and str(subject.get("legal_name") or "")
            and str(subject.get("exchange") or "")
            and subject.get("as_of") == context.get("research_as_of")
            and isinstance(aliases, list)
            and aliases
            and all(str(alias).strip() for alias in aliases)
            and context.get("language") == "zh-CN"
            and str(context.get("research_question") or "")
            and binding.get("pack_case_key") == row.get("case_key")
            and _DIGEST.fullmatch(
                str(binding.get("pack_artifact_digest") or "")
            )
            and _DIGEST.fullmatch(str(binding.get("pack_payload_digest") or ""))
        )


__all__ = [
    "CURRENT_RESEARCH_WORKSPACE_CATALOG_RESOURCE_ID",
    "ResearchWorkspacePrincipal",
    "ResearchWorkspaceService",
    "ResearchWorkspaceServiceError",
    "WORKSPACE_PROJECTION_SCHEMA",
]
