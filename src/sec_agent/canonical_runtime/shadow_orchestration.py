from __future__ import annotations

from typing import Any

from .facade import RuntimeFacade
from .full_serializer import (
    DecisionSurfaceArtifactSerializer,
    DecisionSurfaceReadbackReport,
    FullSerializationAssembly,
    FullSerializerPolicy,
)
from .model_admission import ModelCompilationProposal
from .models import CommandEnvelope, StrictModel, canonical_digest


class ShadowCompilationAttemptTrace(StrictModel):
    case_id: str
    work_unit_id: str
    attempt_id: str
    envelope_digest: str
    model_admission_decision_digest: str
    status: str
    artifact_version_id: str | None = None
    event_ids: tuple[str, ...] = ()
    error_code: str | None = None
    model_call_count: int = 0
    external_call_count: int = 0


class ShadowRepairProjection(StrictModel):
    status: str
    reason: str
    affected_contract_version_id: str
    next_action: str
    repair_attempt_count: int = 0


class ShadowReplayReport(StrictModel):
    status: str
    projection_digest: str
    artifact_version_id: str | None = None
    work_unit_state: str | None = None
    attempt_state: str | None = None
    external_call_count: int = 0


class ShadowCompilationResult(StrictModel):
    status: str
    attempt_trace: ShadowCompilationAttemptTrace
    readback_report: DecisionSurfaceReadbackReport | None = None
    replay_report: ShadowReplayReport | None = None
    repair_projection: ShadowRepairProjection
    planning_authority: str = "legacy"
    model_call_count: int = 0
    external_call_count: int = 0


class ShadowCompilerOrchestrator:
    """M2.9 integration of M2.2 artifact commit with M2.8 denied model admission and M1 replay."""

    def __init__(self, serializer_policy: FullSerializerPolicy):
        self.serializer = DecisionSurfaceArtifactSerializer(serializer_policy)

    def execute(
        self,
        facade: RuntimeFacade,
        command: CommandEnvelope,
        assembly: FullSerializationAssembly,
        proposal: ModelCompilationProposal,
        *,
        artifact_id: str,
    ) -> ShadowCompilationResult:
        work_unit_id = str(command.payload.get("work_unit_id") or "")
        attempt_id = str(command.payload.get("attempt_id") or "")
        contract_version_id = assembly.contract_version_id
        if facade.mode != "shadow":
            trace = ShadowCompilationAttemptTrace(
                case_id=str(command.case_id or ""),
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
                envelope_digest=assembly.envelope.envelope_digest,
                model_admission_decision_digest=proposal.admission_decision.decision_digest,
                status="skipped_feature_flag_off",
            )
            return ShadowCompilationResult(
                status="skipped_feature_flag_off",
                attempt_trace=trace,
                repair_projection=ShadowRepairProjection(
                    status="not_required",
                    reason="shadow_feature_flag_off",
                    affected_contract_version_id=contract_version_id,
                    next_action="enable approved shadow feature flag before creating a WorkUnit attempt",
                ),
            )
        if proposal.admission_decision.status != "denied" or proposal.model_call_count != 0:
            return self._failed(
                command,
                assembly,
                proposal,
                reason="model_admission_boundary_violation",
                next_action="restore denied no-model admission policy before shadow compilation",
            )
        try:
            committed = self.serializer.commit(facade, command, assembly, artifact_id=artifact_id)
        except Exception as exc:
            return self._failed(
                command,
                assembly,
                proposal,
                reason=f"shadow_commit_failed:{type(exc).__name__}:{exc}",
                next_action="repair input, lease, object-store or transaction boundary and start a new immutable Attempt",
            )
        artifact_version_id = committed.artifact_refs[0] if committed.artifact_refs else None
        from .full_serializer import DecisionSurfaceReadbackVerifier

        readback = DecisionSurfaceReadbackVerifier().verify(facade, assembly, artifact_version_id=str(artifact_version_id))
        replay = facade.replay_projection()
        work_unit_state = replay["work_units"].get(work_unit_id, {}).get("state")
        attempt_state = replay["attempts"].get(attempt_id, {}).get("state")
        replay_report = ShadowReplayReport(
            status="pass" if readback.status == "pass" and artifact_version_id in replay["artifacts"] else "fail",
            projection_digest=str(replay["projection_digest"]),
            artifact_version_id=artifact_version_id,
            work_unit_state=work_unit_state,
            attempt_state=attempt_state,
            external_call_count=int(replay["external_call_count"]),
        )
        trace = ShadowCompilationAttemptTrace(
            case_id=str(command.case_id or ""),
            work_unit_id=work_unit_id,
            attempt_id=attempt_id,
            envelope_digest=assembly.envelope.envelope_digest,
            model_admission_decision_digest=proposal.admission_decision.decision_digest,
            status="succeeded" if readback.status == "pass" and replay_report.status == "pass" else "failed_readback_or_replay",
            artifact_version_id=artifact_version_id,
            event_ids=committed.event_ids,
        )
        status = "pass" if trace.status == "succeeded" else "fail"
        return ShadowCompilationResult(
            status=status,
            attempt_trace=trace,
            readback_report=readback,
            replay_report=replay_report,
            repair_projection=ShadowRepairProjection(
                status="not_required" if status == "pass" else "required",
                reason="shadow_compile_committed" if status == "pass" else "readback_or_replay_failed",
                affected_contract_version_id=contract_version_id,
                next_action="none" if status == "pass" else "inspect readback/replay evidence before retry",
            ),
        )

    @staticmethod
    def _failed(
        command: CommandEnvelope,
        assembly: FullSerializationAssembly,
        proposal: ModelCompilationProposal,
        *,
        reason: str,
        next_action: str,
    ) -> ShadowCompilationResult:
        trace = ShadowCompilationAttemptTrace(
            case_id=str(command.case_id or ""),
            work_unit_id=str(command.payload.get("work_unit_id") or ""),
            attempt_id=str(command.payload.get("attempt_id") or ""),
            envelope_digest=assembly.envelope.envelope_digest,
            model_admission_decision_digest=proposal.admission_decision.decision_digest,
            status="failed",
            error_code=reason,
        )
        return ShadowCompilationResult(
            status="fail",
            attempt_trace=trace,
            repair_projection=ShadowRepairProjection(
                status="required",
                reason=reason,
                affected_contract_version_id=assembly.contract_version_id,
                next_action=next_action,
            ),
        )
