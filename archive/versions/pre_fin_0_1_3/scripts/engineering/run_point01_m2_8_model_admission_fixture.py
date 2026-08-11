from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.model_admission import (  # noqa: E402
    CompilerModelAdmissionService,
    ModelAdmissionPolicy,
    ModelAdmissionRequest,
)


POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m2_8_model_admission_policy_v1_0.json"
PLAN_PATH = ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m2_8_model_admission_fixture_result_v1_0.json"


def _load_m2_2():
    path = ROOT / "scripts/engineering/run_point01_m2_2_full_serializer_fixture.py"
    spec = importlib.util.spec_from_file_location("point01_m2_2_for_m2_8", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M2_2 = _load_m2_2()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _policy() -> ModelAdmissionPolicy:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return ModelAdmissionPolicy.model_validate({key: value for key, value in raw.items() if key not in {"policy_version", "authority_boundary"}})


class CountingAdapter:
    def __init__(self) -> None:
        self.call_count = 0

    def compile(self, prompt_context: dict[str, Any]) -> dict[str, Any]:
        self.call_count += 1
        return {"unexpected": prompt_context}


def build_result() -> dict[str, Any]:
    request, assembler, _ = M2_2._context()
    envelope = assembler.assemble(request).envelope
    service = CompilerModelAdmissionService(_policy())
    adapter = CountingAdapter()
    denied_request = ModelAdmissionRequest(
        envelope=envelope,
        provider_family="deepseek",
        feature_flag_enabled=False,
        explicit_approved_scoped_node=False,
        provider_preflight_status="fail",
        budget_preflight_status="fail",
        permission_snapshot_ref=None,
    )
    denied_proposal, denied_audit = service.propose(denied_request, adapter=adapter)
    otherwise_ready_request = denied_request.model_copy(
        update={
            "feature_flag_enabled": True,
            "explicit_approved_scoped_node": True,
            "provider_preflight_status": "pass",
            "budget_preflight_status": "pass",
            "permission_snapshot_ref": "permission-m2-8",
        }
    )
    otherwise_ready_proposal, otherwise_ready_audit = service.propose(otherwise_ready_request, adapter=adapter)
    checks = {
        "denied_path_records_all_missing_admission_inputs": denied_proposal.admission_decision.status == "denied"
        and {"feature_flag_not_enabled", "explicit_approved_scoped_node_missing", "provider_preflight_not_pass", "budget_preflight_not_pass", "permission_snapshot_missing", "policy_model_execution_disabled"}.issubset(set(denied_proposal.admission_decision.denial_reasons)),
        "policy_stays_denied_even_when_other_inputs_are_ready": otherwise_ready_proposal.admission_decision.status == "denied"
        and otherwise_ready_proposal.admission_decision.denial_reasons == ("policy_model_execution_disabled",),
        "prompt_snapshot_and_repair_trace_are_recorded": denied_proposal.prompt_context_snapshot.envelope_digest == envelope.envelope_digest
        and denied_proposal.structured_output_repair_trace.status == "not_attempted"
        and bool(denied_audit.audit_digest)
        and bool(otherwise_ready_audit.audit_digest),
        "adapter_not_invoked": adapter.call_count == 0,
        "model_free": denied_proposal.model_call_count == 0 and otherwise_ready_proposal.external_call_count == 0,
    }
    return {
        "result_version": "finsight_point01_m2_8_model_admission_fixture_result_v1_0",
        "scope": "Point01_M2_8_model_adapter_admission_denied_path",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "checks": checks,
        "denied_proposal": denied_proposal.model_dump(mode="json"),
        "denied_audit": denied_audit.model_dump(mode="json"),
        "otherwise_ready_but_policy_denied_proposal": otherwise_ready_proposal.model_dump(mode="json"),
        "otherwise_ready_but_policy_denied_audit": otherwise_ready_audit.model_dump(mode="json"),
        "adapter_call_count": adapter.call_count,
        "authority_boundary": {"legacy_task_run": "authoritative", "canonical_lane": "shadow_only", "model_execution_permitted": False, "model_call_count": 0, "external_call_count": 0},
        "fixed_input_sha256": {
            "configs/engineering_handoff/point01_m2_8_model_admission_policy_v1_0.json": _sha256(POLICY_PATH),
            "scripts/engineering/run_point01_m2_8_model_admission_fixture.py": _sha256(Path(__file__).resolve()),
            "src/sec_agent/canonical_runtime/model_admission.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/model_admission.py"),
            "src/sec_agent/canonical_runtime/full_serializer.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/full_serializer.py"),
            "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(PLAN_PATH),
        },
        "boundary": "This is M2.8 denied-path evidence only. No provider adapter is invoked, no model output is created and no legacy or planning authority changes.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Point 01 M2.8 model-admission denied-path fixture.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_result()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output), "checks": result["checks"]}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
