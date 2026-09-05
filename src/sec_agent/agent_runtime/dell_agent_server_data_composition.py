"""Owner-approved data composition for the Dell Agent Server.

This module is deliberately only a composition root.  Parsing, retrieval,
Reviewed Evidence reads, financial-fact queries, source-family compilation and
MCP transport remain owned by the existing mature adapters.  It does not add a
second store, scheduler, runtime or retriever. Default profiles are zero-network;
explicit live-web profiles use the existing Exa MCP adapter, not a fallback.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import os
from pathlib import Path
from typing import Any

from sec_agent.research_foundation.contracts import (
    load_dell_reference_vertical_foundation,
)
from sec_agent.research_foundation.data_ports import (
    CurrentReviewedEvidenceReader,
    ExistingS2FinancialFactReader,
    StructuredLocalKnowledgeReader,
)
from sec_agent.research_foundation.external_sources import (
    ExternalCaptureRequest,
    ExternalSourceDiscovery,
    ExternalSourceError,
)
from sec_agent.research_foundation.frozen_external_candidate_pack import (
    FrozenExternalCandidatePack,
    FrozenExternalCandidatePackProvider,
    FrozenFirstExternalSourceCapture,
)
from sec_agent.research_foundation.mcp_server import (
    DellFoundationMethodReader,
    ResearchDataMCPDependencies,
    build_research_data_mcp_server,
)

from .dell_current_capability_inventory import (
    build_current_capability_inventory,
    build_current_host_owned_baseline_source_plan,
    load_physical_route_catalog,
)
from .dell_owner_data_gate import load_dell_owner_data_gate_decision
from .dell_reference_vertical_contracts import CaseFoundationBinding
from .dell_reference_vertical_graph import DellReferenceVerticalDependencies
from .dell_reference_vertical_mcp_tools import (
    DellMCPToolLaneAdapter,
    compose_dell_mcp_graph_run,
)
from .dell_reviewed_evidence_inventory import (
    load_executable_reviewed_evidence_index_v1_2,
    load_owner_approved_reviewed_case,
)
from .dell_source_family_compiler import (
    HostOwnedBaselineSourcePlan,
    SourceFamilyCompiler,
)
from .planner_tool_capabilities import derive_planner_tool_capabilities


DELL_APPROVED_DATA_SNAPSHOT_ID = (
    "dell-owner-data-gate-739df0f5d2880af8e27a08b5f9e31e10"
)
DELL_APPROVED_RESEARCH_AS_OF = "2026-09-02T00:00:00Z"

_ENV_PATHS = {
    "s1_nodes": "FINSIGHT_DELL_S1_NODES_PATH",
    "reviewed_base": "FINSIGHT_DELL_REVIEWED_BASE_PACK_PATH",
    "reviewed_overlay": "FINSIGHT_DELL_REVIEWED_OVERLAY_PATH",
    "s2_result": "FINSIGHT_DELL_S2_RESULT_PATH",
    "s2_mart": "FINSIGHT_COMPANY_FINANCIAL_FACT_MART_PATH",
    "external_manifest": "FINSIGHT_DELL_EXTERNAL_MANIFEST_PATH",
}


class DellApprovedDataCompositionError(RuntimeError):
    """The exact approved data plane cannot be safely composed."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _NoLiveExternalCapture:
    async def capture(self, _request: ExternalCaptureRequest) -> Any:
        raise ExternalSourceError("live_external_capture_not_authorized")


def _required_file_environment(name: str, environment: Mapping[str, str]) -> Path:
    value = environment.get(name)
    if not isinstance(value, str) or not value.strip():
        raise DellApprovedDataCompositionError(
            f"approved_data_path_environment_missing:{name}"
        )
    try:
        path = Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise DellApprovedDataCompositionError(
            f"approved_data_path_unavailable:{name}"
        ) from exc
    if not path.is_file():
        raise DellApprovedDataCompositionError(
            f"approved_data_path_not_file:{name}"
        )
    return path


def _repository_root(environment: Mapping[str, str]) -> Path:
    value = environment.get("FIN_REPO_ROOT")
    if not isinstance(value, str) or not value.strip():
        raise DellApprovedDataCompositionError("approved_repository_root_missing")
    try:
        root = Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise DellApprovedDataCompositionError(
            "approved_repository_root_unavailable"
        ) from exc
    if not root.is_dir():
        raise DellApprovedDataCompositionError("approved_repository_root_not_directory")
    return root


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _model_execution_not_authorized(*_args: Any, **_kwargs: Any) -> Any:
    raise DellApprovedDataCompositionError("model_execution_not_authorized")


@dataclass(frozen=True)
class DellApprovedDataComposition:
    dependencies: DellReferenceVerticalDependencies
    foundation_binding: CaseFoundationBinding
    baseline_source_plan: HostOwnedBaselineSourcePlan
    source_route_catalog: dict[str, Any]
    decision_digest: str
    inventory_snapshot_digest: str
    source_route_catalog_digest: str
    reviewed_evidence_count: int
    s2_observation_count: int
    external_route_count: int
    local_candidate_count: int
    reviewed_topic_refs_by_branch: dict[str, tuple[str, ...]]
    model_calls_authorized: bool = False
    network_calls_authorized: bool = False
    paid_calls_authorized: bool = False


@contextmanager
def open_dell_approved_data_composition(
    *,
    run_invocation_id: str,
    environment: Mapping[str, str] | None = None,
    source_read_enabled: bool = False,
    live_web_read_enabled: bool = False,
) -> Iterator[DellApprovedDataComposition]:
    """Open the exact Owner-approved data readers behind one MCP lifecycle."""

    if not isinstance(run_invocation_id, str) or not run_invocation_id.strip():
        raise DellApprovedDataCompositionError("run_invocation_id_required")
    env = os.environ if environment is None else environment
    root = _repository_root(env)
    paths = {
        label: _required_file_environment(name, env)
        for label, name in _ENV_PATHS.items()
    }
    config_root = root / "configs" / "research"
    foundation_path = (
        config_root
        / "fin_ia_0_1_3_dell_reference_vertical_foundation_v1_0.json"
    )
    physical_catalog_path = (
        config_root
        / "fin_ia_0_1_3_dell_source_family_physical_route_catalog_v1_0.json"
    )
    enrichment_path = (
        config_root
        / "fin_ia_0_1_3_dell_reviewed_evidence_enrichment_v1_0.json"
    )
    owner_decision_path = (
        config_root
        / "fin_ia_0_1_3_dell_owner_data_gate_decision_v1_0.json"
    )

    try:
        decision = load_dell_owner_data_gate_decision(owner_decision_path)
        catalog = load_physical_route_catalog(
            physical_catalog_path,
            expected_file_sha256=decision.bound_inputs.physical_catalog_sha256,
            expected_catalog_digest=decision.bound_inputs.physical_catalog_digest,
        )
        if _file_sha256(foundation_path) != catalog.foundation_digest:
            raise DellApprovedDataCompositionError(
                "approved_foundation_file_sha256_mismatch"
            )
        foundation = load_dell_reference_vertical_foundation(foundation_path)
        if catalog.research_as_of != DELL_APPROVED_RESEARCH_AS_OF[:10]:
            raise DellApprovedDataCompositionError(
                "approved_research_as_of_catalog_mismatch"
            )
        planner_capabilities = derive_planner_tool_capabilities(
            sqlite_path=paths["s2_mart"],
            expected_mart_sha256=decision.bound_inputs.s2_mart_sha256,
            snapshot_id=DELL_APPROVED_DATA_SNAPSHOT_ID,
        )
        reviewed_index = load_executable_reviewed_evidence_index_v1_2(
            config_path=enrichment_path,
            base_pack_path=paths["reviewed_base"],
            overlay_path=paths["reviewed_overlay"],
            physical_catalog_path=physical_catalog_path,
            owner_decision=decision,
        )
        inventory = build_current_capability_inventory(
            physical_catalog_path=physical_catalog_path,
            expected_physical_catalog_sha256=(
                decision.bound_inputs.physical_catalog_sha256
            ),
            foundation_source_families=tuple(
                row.model_dump(mode="json") for row in foundation.source_families
            ),
            foundation_question_branches=tuple(
                row.model_dump(mode="json")
                for row in foundation.question_branches
            ),
            local_nodes_path=paths["s1_nodes"],
            external_manifest_path=paths["external_manifest"],
            s2_result_path=paths["s2_result"],
            expected_s2_result_sha256=decision.bound_inputs.s2_result_sha256,
            planner_capabilities=planner_capabilities,
            reviewed_index=reviewed_index,
            snapshot_id=DELL_APPROVED_DATA_SNAPSHOT_ID,
            owner_data_gate_decision=decision,
        )
        baseline = build_current_host_owned_baseline_source_plan(
            inventory=inventory,
            owner_data_gate_decision=decision,
        )
        compiler = SourceFamilyCompiler(inventory=inventory, baseline=baseline)
        source_route_catalog = compiler.provider_route_catalog()
        branch_ids = tuple(row.branch_id for row in foundation.question_branches)
        graph_run = compose_dell_mcp_graph_run(
            foundation,
            branch_ids=branch_ids,
            research_as_of=DELL_APPROVED_RESEARCH_AS_OF,
            snapshot_id=DELL_APPROVED_DATA_SNAPSHOT_ID,
            execution_attempt_id=run_invocation_id.strip(),
        )
        reviewed_case = load_owner_approved_reviewed_case(
            config_path=enrichment_path,
            base_pack_path=paths["reviewed_base"],
            overlay_path=paths["reviewed_overlay"],
            physical_catalog_path=physical_catalog_path,
            owner_decision=decision,
        )
        reviewed_reader = CurrentReviewedEvidenceReader(
            case_reader=lambda _case_key: reviewed_case
        )
        local_reader = StructuredLocalKnowledgeReader(
            nodes_path=paths["s1_nodes"],
            expected_sha256=catalog.local_nodes_sha256,
            expected_node_count=catalog.expected_physical_node_count,
            research_as_of=date.fromisoformat(catalog.research_as_of),
            allowed_branch_ids=branch_ids,
        )
        fact_reader = ExistingS2FinancialFactReader(
            paths["s2_mart"],
            expected_sha256=decision.bound_inputs.s2_mart_sha256,
        )
        external_pack = FrozenExternalCandidatePack.load(
            paths["external_manifest"],
            expected_sha256=catalog.external_manifest_sha256,
        )
        if (
            external_pack.case_id != foundation.case_identity.case_id
            or external_pack.manifest_digest != catalog.external_manifest_digest
            or external_pack.source_research_as_of
            != DELL_APPROVED_RESEARCH_AS_OF
        ):
            raise DellApprovedDataCompositionError(
                "approved_external_pack_binding_mismatch"
            )
        discovery = ExternalSourceDiscovery(
            primary=FrozenExternalCandidatePackProvider(external_pack)
        )
        capture = FrozenFirstExternalSourceCapture(
            pack=external_pack,
            fallback=_NoLiveExternalCapture(),  # type: ignore[arg-type]
        )
        source_reader = local_reader.read_source_document if source_read_enabled else None
        if live_web_read_enabled:
            if not source_read_enabled:
                raise DellApprovedDataCompositionError("live_web_requires_source_read_capability")
            from sec_agent.research_foundation.external_sources import (
                ExaHostedMCPProvider, ExaHostedMCPPageFetcher, ExternalSourceCapture,
                PublicURLGuard, StaticHTTPPageFetcher,
            )
            from sec_agent.research_foundation.web_source_navigation import WebSourceReader
            guard = PublicURLGuard()
            web_reader = WebSourceReader(
                discovery=ExternalSourceDiscovery(primary=ExaHostedMCPProvider()),
                capture=ExternalSourceCapture(guard=guard, static_fetcher=StaticHTTPPageFetcher(guard=guard),
                    hosted_fetcher=ExaHostedMCPPageFetcher(guard=guard, max_characters=50000)))

            async def source_reader(*, request, branch_id, run_scope):
                if request.source_space == "web":
                    return await web_reader(request=request, branch_id=branch_id, run_scope=run_scope)
                return local_reader.read_source_document(request=request, branch_id=branch_id, run_scope=run_scope)

        server = build_research_data_mcp_server(
            ResearchDataMCPDependencies(
                method_reader=DellFoundationMethodReader(foundation),
                local_knowledge_reader=local_reader,
                reviewed_evidence_search_reader=reviewed_reader.search,
                reviewed_evidence_reader=reviewed_reader,
                financial_fact_reader=fact_reader,
                external_discovery=discovery,
                external_capture=capture,  # type: ignore[arg-type]
                source_document_reader=source_reader,
            )
        )
    except DellApprovedDataCompositionError:
        raise
    except Exception as exc:
        raise DellApprovedDataCompositionError(
            "approved_data_composition_validation_failed"
        ) from exc

    adapter = DellMCPToolLaneAdapter(
        server,
        run_binding=graph_run.mcp_run_binding,
        source_family_compiler=compiler,
        source_read_enabled=source_read_enabled,
    )
    try:
        with adapter as opened_adapter:
            dependencies = DellReferenceVerticalDependencies(
                foundation_binder=graph_run.foundation_binder,
                planner_tool_capabilities=planner_capabilities.model_dump(
                    mode="json"
                ),
                planner_source_route_catalog=source_route_catalog,
                planner_agent=_model_execution_not_authorized,
                evidence_tool=opened_adapter.evidence_tool,
                finance_tool=opened_adapter.finance_tool,
                specialist_agent=_model_execution_not_authorized,
                counter_agent=_model_execution_not_authorized,
                lead_agent=_model_execution_not_authorized,
            )
            yield DellApprovedDataComposition(
                dependencies=dependencies,
                foundation_binding=graph_run.foundation_binding,
                baseline_source_plan=baseline,
                source_route_catalog=source_route_catalog,
                decision_digest=decision.decision_digest,
                inventory_snapshot_digest=inventory.inventory_snapshot_digest,
                source_route_catalog_digest=source_route_catalog["catalog_digest"],
                reviewed_evidence_count=inventory.reviewed_evidence_count,
                s2_observation_count=inventory.s2_observation_count,
                external_route_count=inventory.external_object_count,
                local_candidate_count=inventory.local_candidate_count,
                network_calls_authorized=live_web_read_enabled,
                reviewed_topic_refs_by_branch={
                    branch_id: tuple(
                        sorted(
                            {
                                topic_ref
                                for row in reviewed_index.rows
                                if branch_id in row.coverage_obligation_ids
                                for topic_ref in row.topic_refs
                            }
                        )
                    )
                    for branch_id in graph_run.foundation_binding.required_branch_ids
                },
            )
    except DellApprovedDataCompositionError:
        raise
    except Exception:
        raise


__all__ = [
    "DELL_APPROVED_DATA_SNAPSHOT_ID",
    "DELL_APPROVED_RESEARCH_AS_OF",
    "DellApprovedDataComposition",
    "DellApprovedDataCompositionError",
    "open_dell_approved_data_composition",
]
