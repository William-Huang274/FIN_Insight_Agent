"""Point 01 canonical runtime public surface.

This package deliberately resolves public services lazily.  Planning-only code
must not acquire an outbound-capable M6 transport merely because Python first
loads ``sec_agent.canonical_runtime`` before the requested submodule.  The
lazy table preserves the historical public imports while keeping transport
ownership inside the explicitly admitted execution modules.
"""

from __future__ import annotations

from importlib import import_module
from typing import Final


_EXPORTS: Final[dict[str, tuple[str, str]]] = {
    "RuntimeFacade": (".facade", "RuntimeFacade"),
    "FeatureFlagRegistry": (".feature_flags", "FeatureFlagRegistry"),
    "FileCanonicalObjectStore": (".object_store", "FileCanonicalObjectStore"),
    "MultiSectorCalibrationMatrix": (".shadow_calibration", "MultiSectorCalibrationMatrix"),
    "NegativeControlVerifier": (".shadow_calibration", "NegativeControlVerifier"),
    "P36FiveChainEvaluator": (".shadow_calibration", "P36FiveChainEvaluator"),
    "PatternCandidateAdjudicator": (".shadow_calibration", "PatternCandidateAdjudicator"),
    "CellCoverageGranularityAuditor": (".shadow_comparison", "CellCoverageGranularityAuditor"),
    "LegacyRequiredItemComparator": (".shadow_comparison", "LegacyRequiredItemComparator"),
    "ShadowComparisonReviewService": (".shadow_review", "ShadowComparisonReviewService"),
    "PlanningLaneCutoverService": (".planning_cutover", "PlanningLaneCutoverService"),
    "DurableSchedulerService": (".durable_scheduler", "DurableSchedulerService"),
    "CheckpointArtifactService": (".checkpoint_artifacts", "CheckpointArtifactService"),
    "CapabilitySecurityService": (".capability_security", "CapabilitySecurityService"),
    "BudgetControlService": (".budget_control", "BudgetControlService"),
    "HITLGovernanceService": (".hitl_governance", "HITLGovernanceService"),
    "ParallelContextService": (".parallel_context", "ParallelContextService"),
    "ObservabilityOpsService": (".observability_ops", "ObservabilityOpsService"),
    "RecoveryLifecycleService": (".recovery_lifecycle", "RecoveryLifecycleService"),
    "EvidenceRequestCompiler": (".evidence_request", "EvidenceRequestCompiler"),
    "BoundedToolPlanner": (".tool_planner", "BoundedToolPlanner"),
    "CandidateBundleCompiler": (".candidate_bundle", "CandidateBundleCompiler"),
    "CandidateBundleProjection": (".local_retrieval_skeleton", "CandidateBundleProjection"),
    "EvidenceGateCandidateProjection": (".local_retrieval_skeleton", "EvidenceGateCandidateProjection"),
    "ExactValueSqlBindingCompiler": (".local_retrieval_skeleton", "ExactValueSqlBindingCompiler"),
    "ExactValueSqlBindingPolicy": (".local_retrieval_skeleton", "ExactValueSqlBindingPolicy"),
    "ExactValueSqlExecutionScope": (".local_retrieval_skeleton", "ExactValueSqlExecutionScope"),
    "LegacyEvidenceRequestTopKAdapter": (".local_retrieval_skeleton", "LegacyEvidenceRequestTopKAdapter"),
    "LegacyTopKMappingRegistry": (".local_retrieval_skeleton", "LegacyTopKMappingRegistry"),
    "LocalAdapterSnapshot": (".local_retrieval_skeleton", "LocalAdapterSnapshot"),
    "LocalRetrievalQuery": (".local_retrieval_skeleton", "LocalRetrievalQuery"),
    "NonExecutingLocalRetrievalSkeleton": (".local_retrieval_skeleton", "NonExecutingLocalRetrievalSkeleton"),
    "TopKPolicyResolver": (".local_retrieval_skeleton", "TopKPolicyResolver"),
    "ToolSelectionPlanScopeReference": (".local_retrieval_skeleton", "ToolSelectionPlanScopeReference"),
    "LocalRetrievalFixtureAdmissionPolicy": (".local_retrieval_fixture", "LocalRetrievalFixtureAdmissionPolicy"),
    "LocalRetrievalFixtureCorpus": (".local_retrieval_fixture", "LocalRetrievalFixtureCorpus"),
    "LocalRetrievalFixtureHarness": (".local_retrieval_fixture", "LocalRetrievalFixtureHarness"),
    "LocalRetrievalFixtureOracle": (".local_retrieval_fixture_oracle", "LocalRetrievalFixtureOracle"),
    "ReceiptBoundCandidateBundleService": (".receipt_bound_candidate_bundle", "ReceiptBoundCandidateBundleService"),
    "ReceiptBoundRepairTicketService": (".receipt_bound_repair_ticket", "ReceiptBoundRepairTicketService"),
    "ReceiptBoundParserNumericStopService": (".receipt_bound_parser_numeric_stop", "ReceiptBoundParserNumericStopService"),
    "M6GlobalOneShotApprovalService": (".m6_pilot_global_approval", "M6GlobalOneShotApprovalService"),
    "RepairTicketRouter": (".repair_ticket", "RepairTicketRouter"),
    "ParserNumericFixtureCompiler": (".parser_numeric", "ParserNumericFixtureCompiler"),
    "FixtureEvidenceGate": (".evidence_gate", "FixtureEvidenceGate"),
    "SQLiteCanonicalStore": (".store", "SQLiteCanonicalStore"),
}

__all__ = tuple(_EXPORTS)


def __getattr__(name: str) -> object:
    """Resolve a public runtime export only when its owning module is requested."""

    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    resolved = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = resolved
    return resolved


def __dir__() -> list[str]:
    return sorted({*globals(), *_EXPORTS})
