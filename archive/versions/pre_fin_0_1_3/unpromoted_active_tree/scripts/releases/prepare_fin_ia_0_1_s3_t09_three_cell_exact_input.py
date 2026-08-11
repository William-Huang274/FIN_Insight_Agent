from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.case_service import CasePrincipal, CaseService
from apps.workbench.backend.application.evidence_service import EvidenceService
from apps.workbench.backend.application.local_research_service import (
    P36LocalResearchService,
)
from apps.workbench.backend.application.research_runtime import (
    prepare_s3_three_cell_bounded_agent_exact_input,
)


TENANT_ID = "tenant-fin01-s3-t09-eval"
PROJECT_ID = "project-fin01-s3-t09-eval"
ACTOR_ID = "analyst-fin01-s3-t09-eval"
EXECUTION_IDENTITY = "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
PERMISSIONS = frozenset(
    {
        "case:create",
        "case:read",
        "planning:write",
        "planning:review",
        "planning:read",
        "execution:write",
        "execution:read",
        "activity:read",
        "evidence:read",
    }
)


def _headers() -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": TENANT_ID,
        "X-Fin-Case-Project": PROJECT_ID,
        "X-Fin-Case-Actor": ACTOR_ID,
        "X-Fin-Case-Permissions": ",".join(sorted(PERMISSIONS)),
    }


def _principal() -> CasePrincipal:
    return CasePrincipal(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        actor_id=ACTOR_ID,
        permissions=PERMISSIONS,
    )


def _accepted_case(client: TestClient) -> tuple[dict[str, Any], dict[str, Any]]:
    created = client.post(
        "/api/v1/cases",
        headers=_headers(),
        json={
            "query": "分析 NVDA AI 基础设施需求、价值捕获与瓶颈反证",
            "as_of": "2026-07-21T00:00:00Z",
            "language": "zh-CN",
            "source_policy_ref": "local_official_only",
            "idempotency_key": "fin01-s3-t09-evaluation-case-v1",
        },
    )
    if created.status_code != 202:
        raise RuntimeError(f"case_prepare_failed:{created.status_code}:{created.text}")
    case = created.json()
    compiled = client.post(
        f"/api/v1/cases/{case['case_id']}/planning/compile",
        headers=_headers(),
        json={
            "expected_case_version": case["case_version"],
            "expected_summary_version": case["summary_version"],
            "compiler_policy_ref": "fixture:p36-three-cell-v1",
            "pack_selection_ref": "fixture:p36-ai-infrastructure-v1",
            "actor_ref": ACTOR_ID,
            "idempotency_key": "fin01-s3-t09-evaluation-compile-v1",
        },
    )
    if compiled.status_code != 202:
        raise RuntimeError(
            f"planning_compile_failed:{compiled.status_code}:{compiled.text}"
        )
    plan = compiled.json()
    accepted = client.post(
        f"/api/v1/cases/{case['case_id']}/planning/checkpoint",
        headers=_headers(),
        json={
            "decision": "accept",
            "expected_case_version": case["case_version"],
            "expected_decision_surface_contract_version": plan["contract_version"],
            "expected_checkpoint_version": plan["checkpoint_version"],
            "actor_ref": ACTOR_ID,
            "idempotency_key": "fin01-s3-t09-evaluation-accept-v1",
        },
    )
    if accepted.status_code != 202:
        raise RuntimeError(
            f"planning_accept_failed:{accepted.status_code}:{accepted.text}"
        )
    return case, accepted.json()


def _execution_counts(case_service: CaseService, case_id: str) -> dict[str, int]:
    return {
        table: len(case_service._facade.store.list_latest(table, case_id=case_id))
        for table in (
            "canonical_work_units",
            "canonical_attempts",
            "canonical_research_run_versions",
            "canonical_artifact_versions",
        )
    }


def prepare(runtime_root: Path) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    case_service = CaseService.for_fixture_root(
        runtime_root / "canonical-runtime", repo_root=ROOT
    )
    local_service = P36LocalResearchService.from_case_service(
        case_service, repo_root=ROOT
    )
    evidence_service = EvidenceService.from_case_service(case_service, repo_root=ROOT)
    app = create_app(
        runtime_root / "workbench.sqlite",
        p02_case_service=case_service,
        p03_evidence_service=evidence_service,
        p36_local_research_service=local_service,
    )
    with TestClient(app) as client:
        case, accepted = _accepted_case(client)
    before = _execution_counts(case_service, case["case_id"])
    prepared = prepare_s3_three_cell_bounded_agent_exact_input(
        local_service,
        evidence_service,
        case["case_id"],
        _principal(),
        decision_surface_contract_ref=accepted["contract_version_id"],
        execution_identity=EXECUTION_IDENTITY,
    )
    after = _execution_counts(case_service, case["case_id"])
    if before != after or any(after.values()):
        raise RuntimeError("s3_t09_prepare_created_execution_state")
    result = {
        "status": "pass_exact_input_prepared_no_execution_or_provider_call",
        "runtime_root": str(runtime_root),
        "case_id": prepared.case_id,
        "case_version": prepared.case_version,
        "as_of": prepared.input_pack.as_of,
        "decision_surface_contract_ref": prepared.decision_surface_contract_ref,
        "execution_identity": prepared.execution_identity,
        "work_unit_id": prepared.work_unit_id,
        "attempt_id": prepared.attempt_id,
        "research_run_id": prepared.research_run_id,
        "input_digest": prepared.input_digest,
        "preparation_digest": prepared.preparation_digest,
        "input_pack": prepared.input_pack.model_dump(mode="json"),
        "execution_state_counts_before": before,
        "execution_state_counts_after": after,
        "observed_counts": prepared.observed_counts,
        "credential_checked": False,
        "credential_value_read_or_persisted": False,
        "admission_issued": False,
        "live_execution_performed": False,
    }
    _write_json(runtime_root / "prepared_input.json", result)
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "input_pack"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return result


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare the exact S3 T09 six-node input without execution calls."
    )
    parser.add_argument("--runtime-root", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.runtime_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
