from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
CASE_PACK = RELEASES / "fin_ia_0_1_s4_t02_dell_oem_exact_case_pack_v1_0.json"
T03_DECISION = RELEASES / (
    "fin_ia_0_1_s4_t03_case_runtime_injection_and_leakage_preflight_v1_0.json"
)
SOURCE_ROUTE_PLAN = (
    ROOT / "docs" / "project_os" / "p34_ai_semis_source_route_plan_v0_1.json"
)
CANONICAL_DATABASE = ROOT / (
    ".codex_runtime/"
    "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/"
    "canonical-runtime/canonical.sqlite"
)
DECIDED_AT = "2026-07-26T18:24:10+08:00"
STATUS = (
    "blocked_zero_call_canary_omitted_source_grounded_exact_input_head_"
    "missing_no_fresh_proof_or_admission"
)
NEXT_ACTION = (
    "S4-T04-DELL-SOURCE-GROUNDED-EXACT-INPUT-HEAD-MATERIALIZATION-"
    "AND-FRESH-PROOF-REPAIR"
)
RC_ID = (
    "RC-P36-056-s4-dell-source-grounded-exact-input-head-and-"
    "canonical-case-gap"
)
CODE_BINDING_PATHS = (
    Path("src/sec_agent/s4_case_runtime.py"),
    Path(
        "apps/workbench/backend/application/"
        "bounded_agent_contract_policies.py"
    ),
    Path(
        "apps/workbench/backend/application/bounded_agent_executor.py"
    ),
    Path(
        "scripts/releases/"
        "run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py"
    ),
    Path(
        "scripts/releases/"
        "supervise_fin_ia_0_1_s3_t09_exact_live_execution.py"
    ),
)


class S4T04DecisionError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T04DecisionError(code)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _audit_canonical_database(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "available": False,
            "database_ref": _relative(path),
            "database_sha256": None,
            "DELL_rows": None,
            "read_only": True,
        }
    before_sha256 = _sha256(path)
    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro",
        uri=True,
    )
    try:
        tables = (
            "canonical_research_cases",
            "canonical_decision_surface_contract_versions",
            "canonical_work_units",
            "canonical_attempts",
            "canonical_research_run_versions",
        )
        counts: dict[str, int] = {}
        totals: dict[str, int] = {}
        for table in tables:
            counts[table] = int(
                connection.execute(
                    f"""
                    select count(*)
                    from {table}
                    where upper(payload_json) like '%DELL%'
                       or upper(coalesce(case_id, '')) like '%DELL%'
                    """
                ).fetchone()[0]
            )
            totals[table] = int(
                connection.execute(
                    f"select count(*) from {table}"
                ).fetchone()[0]
            )
    finally:
        connection.close()
    after_sha256 = _sha256(path)
    _require(
        before_sha256 == after_sha256,
        "canonical_database_changed_during_read_only_audit",
    )
    return {
        "available": True,
        "database_ref": _relative(path),
        "database_sha256": before_sha256,
        "DELL_rows": counts,
        "table_totals": totals,
        "all_DELL_rows_absent": all(value == 0 for value in counts.values()),
        "read_only": True,
        "database_unchanged": True,
    }


def prepare(
    *,
    case_pack_path: Path = CASE_PACK,
    t03_decision_path: Path = T03_DECISION,
    source_route_plan_path: Path = SOURCE_ROUTE_PLAN,
    canonical_database_path: Path = CANONICAL_DATABASE,
) -> dict[str, Any]:
    case_pack = _load(case_pack_path)
    t03_decision = _load(t03_decision_path)
    route_plan = _load(source_route_plan_path)

    _require(
        t03_decision.get("status")
        == (
            "pass_zero_paid_shared_runtime_injected_node_consumed_"
            "and_leakage_preflight"
        ),
        "S4_T03_not_ready",
    )
    _require(
        case_pack.get("case_identity", {}).get("ticker") == "DELL",
        "DELL_case_pack_identity_mismatch",
    )
    boundary = case_pack.get("factual_content_boundary") or {}
    fact_counts = {
        key: len(boundary.get(key) or ())
        for key in (
            "evidence_rows",
            "numeric_rows",
            "graph_edges",
            "claims",
            "judgments",
            "preaccepted_conclusions",
        )
    }
    _require(
        all(value == 0 for value in fact_counts.values()),
        "DELL_case_pack_unexpected_prefilled_fact_content",
    )
    dell_routes = [
        row
        for row in route_plan.get("routes") or ()
        if str(row.get("issuer") or "").upper() == "DELL"
    ]
    _require(len(dell_routes) == 11, "DELL_source_route_count_mismatch")
    _require(
        all(
            row.get("route_execution_status") == "planned_not_executed"
            and row.get("promotion_without_execution_allowed") is False
            for row in dell_routes
        ),
        "DELL_source_route_execution_or_promotion_state_mismatch",
    )
    canonical_audit = _audit_canonical_database(canonical_database_path)

    return {
        "schema_version": (
            "fin_ia_0_1_s4_t04_dell_provider_canary_need_and_"
            "fresh_agent_proof_decision_v1_0"
        ),
        "decision_id": (
            "S4-T04-DELL-PROVIDER-CANARY-NEED-AND-FRESH-AGENT-"
            "PROOF-DECISION-R1"
        ),
        "decided_at": DECIDED_AT,
        "status": STATUS,
        "authority": {
            "user_instruction": "继续",
            "authorized_scope": (
                "S4-T04 zero-call canary-need and fresh-proof decision only"
            ),
            "not_authorized_or_executed": [
                "source_route_execution_or_fact_retrieval",
                "canonical_DELL_Case_or_DecisionSurface_write",
                "model_provider_or_paid_call",
                "exact_admission_issuance_or_consumption",
                "exact_live_or_business_Artifact",
                "paired_assessment_or_Human_review",
                "S4_T05_or_later",
            ],
        },
        "source_refs": {
            "DELL_case_pack": {
                "ref": _relative(case_pack_path),
                "sha256": _sha256(case_pack_path),
            },
            "S4_T03_decision": {
                "ref": _relative(t03_decision_path),
                "sha256": _sha256(t03_decision_path),
            },
            "P34_source_route_plan": {
                "ref": _relative(source_route_plan_path),
                "sha256": _sha256(source_route_plan_path),
            },
        },
        "provider_only_canary_decision": {
            "decision": "omit",
            "named_provider_only_risk": None,
            "reason": (
                "DELL changes case identity, research profile and method "
                "context only; provider, model, endpoint, response schema, "
                "transport, capture, supervision, retry-zero and terminal "
                "contracts are unchanged. A one-node canary would not prove "
                "six-node cross-Cell product coherence."
            ),
            "unchanged_provider_surfaces": [
                "provider_deepseek",
                "model_deepseek_v4_pro",
                "beta_endpoint",
                "specialist_transport_v7",
                "research_lead_transport_v5",
                "memo_writer_transport_v3",
                "output_contract_v4",
                "verifier_state_machine_v2",
                "provider_output_capture_policy_v1",
                "exact_run_supervision_v2",
                "retry_fallback_replay_relaunch_rerun_zero",
            ],
            "changed_non_provider_surfaces": [
                "issuer_identity_NVDA_to_DELL",
                "case_profile_and_research_profile",
                "case_local_method_context",
                "case_local_input_head",
            ],
            "paid_canary_calls_authorized_or_performed": 0,
        },
        "upstream_exact_input_readiness": {
            "DELL_case_pack_fact_counts": fact_counts,
            "canonical_CaseVersion_id": case_pack.get(
                "case_identity", {}
            ).get("canonical_CaseVersion_id"),
            "DELL_source_route_count": len(dell_routes),
            "DELL_routes_planned_not_executed": len(dell_routes),
            "DELL_routes_promotable_without_execution": 0,
            "parser_backed_promotable_DELL_evidence_rows": 0,
            "source_grounded_exact_input_head_available": False,
            "canonical_runtime_audit": canonical_audit,
        },
        "fresh_agent_proof": {
            "decision": "not_frozen_fail_closed",
            "reason": (
                "A runnable exact proof cannot bind a non-existent "
                "source-grounded DELL input head or canonical CaseVersion."
            ),
            "work_unit_id": None,
            "attempt_id": None,
            "research_run_id": None,
            "input_digest": None,
            "preparation_digest": None,
            "prospective_admission": None,
            "admission_issued": False,
            "admission_consumed": False,
            "execution_started": False,
        },
        "exact_code_bindings": {
            path.as_posix(): _sha256(ROOT / path)
            for path in CODE_BINDING_PATHS
        },
        "root_cause_disposition": {
            "issue_id": RC_ID,
            "status": (
                "open_owned_pre_admission_source_grounded_input_gap"
            ),
            "full_chain_blocker": True,
            "model_quality_issue": False,
            "earliest_faulty_artifact": (
                "S4 detailed flow advances from fact-empty T03 fixture to "
                "fresh exact admission without a source-grounded DELL "
                "CaseVersion and input-head materialization step."
            ),
            "required_fix": (
                "Execute and parse bounded official DELL routes, admit only "
                "issuer-bound Evidence/Numeric/Graph rows, materialize the "
                "canonical DELL CaseVersion and exact input head, then rerun "
                "fresh nonreuse proof before any admission issuance."
            ),
        },
        "observed_counts": {
            "source_route_execution_calls": 0,
            "source_fact_retrieval_calls": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "paid_calls": 0,
            "canonical_case_writes": 0,
            "canonical_run_writes": 0,
            "admissions_issued": 0,
            "admissions_consumed": 0,
            "business_artifacts": 0,
            "human_reviews": 0,
        },
        "stage_decision": {
            "S4": "in_progress",
            "S4_T04_canary_decision": "pass_omit",
            "S4_T04_fresh_proof": "blocked_owned_upstream_input_gap",
            "S4_T04_complete": False,
            "S4_T05": "blocked",
            "DELL_R2": "not_started",
            "S4_pass": False,
        },
        "next_action": NEXT_ACTION,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--canonical-database",
        type=Path,
        default=CANONICAL_DATABASE,
    )
    args = parser.parse_args()
    result = prepare(canonical_database_path=args.canonical_database)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
