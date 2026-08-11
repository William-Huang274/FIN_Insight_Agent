"""P33 no-paid fixture for Research-to-Quant factor handoff.

P33-1.5 proves that bounded research judgment material can be handed to the
internal quant validation lab without turning into trade advice or an
unapproved execution path.  The fixture reuses the S9 Research-to-Quant runtime
rows and adds a stricter L3-contract audit over input/output field mapping,
PIT/leakage sequencing, human approvals, FactorCard/memory writeback, and
paper-trading fail-closed behavior.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.r53_r60_research_to_quant_lab import S9_TASK_ID, build_s9_gate, default_s9_paths, rows_to_dicts
from sec_agent.r53_r60_runtime_task_spine import json_loads, rel_path, utc_now_iso, write_json


SCHEMA_VERSION = "fin_insight_p33_research_to_quant_factor_handoff_fixture_v0_1"
CONTRACT_ID = "l3_research_to_quant_factor_handoff_contract_v0_1"
RELEASE_DECISION_PASS = "P33_1_5_L4_scope_pass_research_to_quant_factor_handoff_fixture"
RELEASE_DECISION_BLOCKED = "P33_1_5_blocked_research_to_quant_factor_handoff_fixture"


@dataclass(frozen=True)
class P33ResearchToQuantFactorHandoffFixturePaths:
    manifest_path: Path
    report_path: Path


def default_p33_research_to_quant_factor_handoff_fixture_paths(
    root: Path,
) -> P33ResearchToQuantFactorHandoffFixturePaths:
    return P33ResearchToQuantFactorHandoffFixturePaths(
        manifest_path=root / "data" / "manifests" / "p33_research_to_quant_factor_handoff_fixture_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "p33_research_to_quant_factor_handoff_fixture_report.zh-CN.md",
    )


def build_p33_research_to_quant_factor_handoff_fixture(
    root: Path,
    *,
    rebuild_dependencies: bool = True,
    write_outputs: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    if rebuild_dependencies:
        s9_summary = build_s9_gate(root)
    else:
        s9_summary = _read_json_if_exists(default_s9_paths(root).summary_path)
    manifest = collect_research_to_quant_factor_handoff_manifest(root, s9_summary=s9_summary)
    if write_outputs:
        paths = default_p33_research_to_quant_factor_handoff_fixture_paths(root)
        write_json(paths.manifest_path, manifest)
        paths.report_path.parent.mkdir(parents=True, exist_ok=True)
        paths.report_path.write_text(render_research_to_quant_factor_handoff_report(manifest), encoding="utf-8")
    return manifest


def collect_research_to_quant_factor_handoff_manifest(
    root: Path,
    *,
    s9_summary: Mapping[str, Any],
) -> dict[str, Any]:
    s9_paths = default_s9_paths(root)
    if not s9_paths.db_path.exists():
        raise FileNotFoundError(f"Runtime DB is missing: {s9_paths.db_path}")

    handoff_records = _collect_handoff_records(s9_paths.db_path)
    judgment_card_audit = _collect_judgment_card_audit(s9_paths.db_path, handoff_records)
    pit_audit = _collect_pit_and_leakage_audit(s9_paths.db_path)
    approval_audit = _collect_human_approval_audit(s9_paths.db_path)
    advice_audit = _collect_advice_and_execution_boundary_audit(s9_paths.db_path)
    memory_audit = _collect_factorcard_memory_audit(s9_paths.db_path)
    runtime_audit = _collect_runtime_artifact_audit(s9_paths.db_path)
    acceptance_gates = evaluate_research_to_quant_factor_handoff_gates(
        s9_summary=s9_summary,
        handoff_records=handoff_records,
        judgment_card_audit=judgment_card_audit,
        pit_audit=pit_audit,
        approval_audit=approval_audit,
        advice_audit=advice_audit,
        memory_audit=memory_audit,
        runtime_audit=runtime_audit,
    )
    fail_count = len([row for row in acceptance_gates if row["status"] != "pass"])
    status = "pass" if fail_count == 0 else "fail"
    paths = default_p33_research_to_quant_factor_handoff_fixture_paths(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "contract_id": CONTRACT_ID,
        "status": status,
        "release_decision": RELEASE_DECISION_PASS if status == "pass" else RELEASE_DECISION_BLOCKED,
        "closeout_level": "L4_scope_pass" if status == "pass" else "blocked",
        "promotion_recommendation": "active_registry_ready_runtime_alignment_only" if status == "pass" else "deferred_pending_repair",
        "promotion_scope": "research_to_quant_initial",
        "absorbed_contract_ids": [CONTRACT_ID],
        "artifacts": [
            {
                "artifact_type": "p33_research_to_quant_factor_handoff_fixture",
                "contract_aligned_plan": {
                    "absorbed_contract_ids": [CONTRACT_ID],
                    "used_case_contract_ids": [CONTRACT_ID],
                },
            }
        ],
        "source_fixture_refs": {
            "s9_summary": rel_path(default_s9_paths(root).summary_path, root),
            "s9_gate_rows": rel_path(default_s9_paths(root).gate_rows_path, root),
            "runtime_db": rel_path(default_s9_paths(root).db_path, root),
            "p33_manifest": rel_path(paths.manifest_path, root),
            "p33_report": rel_path(paths.report_path, root),
        },
        "input_contract_required_fields": [
            "judgment_card_ids",
            "signal_definition",
            "candidate_feature_refs",
            "point_in_time_data_manifest",
            "human_approval_policy",
        ],
        "output_contract_required_fields": [
            "factor_hypothesis_id",
            "signal_observation_refs",
            "backtest_plan_id",
            "leakage_guard_result",
            "validation_status",
            "human_approval_state",
            "research_experience_record_id",
        ],
        "handoff_records": handoff_records,
        "judgment_card_audit": judgment_card_audit,
        "pit_audit": pit_audit,
        "approval_audit": approval_audit,
        "advice_audit": advice_audit,
        "memory_audit": memory_audit,
        "runtime_audit": runtime_audit,
        "acceptance_gates": acceptance_gates,
        "gate_fail_count": fail_count,
        "runtime_entry_policy": (
            "Runtime alignment only: bounded research judgments may become "
            "internal FactorHypothesis / PIT dataset / leakage-guarded backtest "
            "validation artifacts. They cannot become live trading, paper "
            "trading without separate approval, or external investment advice."
        ),
        "do_not_promote": [
            "backtest_as_trade_advice",
            "factor_without_judgment_or_source_refs",
            "factor_without_pit_manifest",
            "dataset_or_backtest_without_human_approval",
            "paper_or_live_trading_without_explicit_approval",
        ],
        "rollback_gate": [
            "judgment_card_ids_missing",
            "backtest_plan_id_missing_for_approved_factor",
            "leakage_guard_missing_or_after_backtest",
            "human_approval_state_missing",
            "factorcard_rendered_as_external_trade_advice",
        ],
    }


def _collect_handoff_records(db_path: Path) -> list[dict[str, Any]]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = rows_to_dicts(
            conn.execute(
                """
                select f.factor_hypothesis_id, f.status as validation_status, f.thesis_driver_id,
                       f.signal_observation_id, f.source_refs_json, f.payload_json as factor_payload_json,
                       s.signal_summary, s.source_evidence_refs_json, s.payload_json as signal_payload_json,
                       fs.feature_spec_id, fs.source_refs_json as feature_source_refs_json,
                       ls.label_spec_id, us.universe_spec_id,
                       p.dataset_build_plan_id, p.status as dataset_plan_status, p.pit_policy_json,
                       p.payload_json as plan_payload_json, p.blocked_reason,
                       lg.leakage_guard_id, lg.status as leakage_guard_status,
                       bt.backtest_result_id, bt.status as backtest_status,
                       exp.experience_id,
                       card.factor_card_id, card.status as factor_card_status
                from factor_hypotheses_s9 f
                left join signal_observations_s9 s on f.signal_observation_id = s.signal_observation_id
                left join feature_specs_s9 fs on f.factor_hypothesis_id = fs.factor_hypothesis_id
                left join label_specs_s9 ls on f.factor_hypothesis_id = ls.factor_hypothesis_id
                left join universe_specs_s9 us on f.factor_hypothesis_id = us.factor_hypothesis_id
                left join dataset_build_plans_s9 p on f.factor_hypothesis_id = p.factor_hypothesis_id
                left join leakage_guard_results_s9 lg on f.factor_hypothesis_id = lg.factor_hypothesis_id
                left join backtest_results_s9 bt on f.factor_hypothesis_id = bt.factor_hypothesis_id
                left join factor_cards_s9 card on f.factor_hypothesis_id = card.factor_hypothesis_id
                left join research_experience_records_s9 exp on f.factor_hypothesis_id = exp.factor_hypothesis_id
                where f.task_id = ?
                order by f.factor_hypothesis_id
                """,
                (S9_TASK_ID,),
            ).fetchall()
        )
    records: list[dict[str, Any]] = []
    for row in rows:
        factor_payload = json_loads(str(row.get("factor_payload_json") or "{}"), {})
        signal_payload = json_loads(str(row.get("signal_payload_json") or "{}"), {})
        plan_payload = json_loads(str(row.get("plan_payload_json") or "{}"), {})
        is_approved = row.get("validation_status") == "approved_for_validation"
        backtest_plan_id = str(plan_payload.get("backtest_plan_id") or "")
        records.append(
            {
                "factor_hypothesis_id": row.get("factor_hypothesis_id"),
                "thesis_driver_id": row.get("thesis_driver_id"),
                "validation_status": row.get("validation_status"),
                "input_mapping": {
                    "judgment_card_ids": factor_payload.get("judgment_card_ids") or signal_payload.get("judgment_card_ids") or [],
                    "signal_definition": factor_payload.get("signal_definition") or row.get("signal_summary") or "",
                    "candidate_feature_refs": factor_payload.get("candidate_feature_refs") or [row.get("feature_spec_id")],
                    "point_in_time_data_manifest": factor_payload.get("point_in_time_data_manifest") or {},
                    "human_approval_policy": factor_payload.get("human_approval_policy") or {},
                    "source_refs": json_loads(str(row.get("source_refs_json") or "[]"), []),
                },
                "output_mapping": {
                    "factor_hypothesis_id": row.get("factor_hypothesis_id"),
                    "signal_observation_refs": [row.get("signal_observation_id")] if row.get("signal_observation_id") else [],
                    "backtest_plan_id": backtest_plan_id,
                    "blocked_before_backtest_plan": bool(plan_payload.get("blocked_before_backtest_plan")),
                    "leakage_guard_result": row.get("leakage_guard_id"),
                    "leakage_guard_status": row.get("leakage_guard_status"),
                    "validation_status": row.get("backtest_status") or row.get("factor_card_status") or row.get("validation_status"),
                    "human_approval_state": _approval_state_for_factor(db_path, str(row.get("factor_hypothesis_id") or "")),
                    "research_experience_record_id": row.get("experience_id"),
                },
                "approved_for_backtest": is_approved,
                "dataset_plan_status": row.get("dataset_plan_status"),
                "source_evidence_refs": json_loads(str(row.get("source_evidence_refs_json") or "[]"), []),
                "feature_spec_id": row.get("feature_spec_id") or "",
                "label_spec_id": row.get("label_spec_id") or "",
                "universe_spec_id": row.get("universe_spec_id") or "",
                "blocked_reason": row.get("blocked_reason") or "",
            }
        )
    return records


def _approval_state_for_factor(db_path: Path, factor_hypothesis_id: str) -> dict[str, str]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = rows_to_dicts(
            conn.execute(
                """
                select approval_scope, decision
                from human_approval_decisions_s9
                where task_id = ? and factor_hypothesis_id = ?
                order by approval_scope
                """,
                (S9_TASK_ID, factor_hypothesis_id),
            ).fetchall()
        )
    return {str(row.get("approval_scope")): str(row.get("decision")) for row in rows}


def _collect_judgment_card_audit(
    db_path: Path,
    handoff_records: list[Mapping[str, Any]],
) -> dict[str, Any]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cards = rows_to_dicts(
            conn.execute(
                """
                select judgment_card_id, thesis_driver_id, signal_domain,
                       source_refs_json, authority_boundary, counter_view,
                       failure_view, forbidden_claims_json
                from research_judgment_cards_s9
                where task_id = ?
                """,
                (S9_TASK_ID,),
            ).fetchall()
        )
    cards_by_id = {str(row.get("judgment_card_id")): row for row in cards}
    referenced_ids: list[str] = []
    missing_ids: list[str] = []
    malformed_ids: list[str] = []
    direct_thesis_id_substitutes: list[str] = []
    required_forbidden = {"external_investment_advice", "live_trading"}
    for record in handoff_records:
        inputs = dict(record.get("input_mapping") or {})
        thesis_driver_id = str(record.get("thesis_driver_id") or "")
        for card_id in inputs.get("judgment_card_ids") or []:
            card_id = str(card_id)
            referenced_ids.append(card_id)
            if card_id == thesis_driver_id:
                direct_thesis_id_substitutes.append(card_id)
            card = cards_by_id.get(card_id)
            if not card:
                missing_ids.append(card_id)
                continue
            source_refs = json_loads(str(card.get("source_refs_json") or "[]"), [])
            forbidden_claims = set(json_loads(str(card.get("forbidden_claims_json") or "[]"), []))
            if (
                not source_refs
                or not str(card.get("authority_boundary") or "").strip()
                or not str(card.get("counter_view") or "").strip()
                or not str(card.get("failure_view") or "").strip()
                or not required_forbidden.issubset(forbidden_claims)
            ):
                malformed_ids.append(card_id)
    referenced_unique = sorted(set(referenced_ids))
    return {
        "status": (
            "pass"
            if cards
            and referenced_unique
            and not missing_ids
            and not malformed_ids
            and not direct_thesis_id_substitutes
            else "fail"
        ),
        "judgment_card_count": len(cards),
        "referenced_judgment_card_count": len(referenced_unique),
        "missing_judgment_card_ids": sorted(set(missing_ids)),
        "malformed_judgment_card_ids": sorted(set(malformed_ids)),
        "direct_thesis_id_substitute_count": len(set(direct_thesis_id_substitutes)),
        "direct_thesis_id_substitutes": sorted(set(direct_thesis_id_substitutes)),
    }


def _collect_pit_and_leakage_audit(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        approved_plan_count = conn.execute(
            "select count(*) from dataset_build_plans_s9 where task_id = ? and status = 'ready_for_leakage_check'",
            (S9_TASK_ID,),
        ).fetchone()[0]
        pit_row_count = conn.execute(
            "select count(*) from pit_dataset_rows_s9 where task_id = ?",
            (S9_TASK_ID,),
        ).fetchone()[0]
        pit_bad = conn.execute(
            """
            select count(*) from pit_dataset_rows_s9
            where task_id = ?
              and (source_refs_json in ('', '[]')
                   or feature_publish_time = ''
                   or feature_available_time = ''
                   or tradable_after = ''
                   or label_window_start = ''
                   or feature_available_time > tradable_after
                   or tradable_after > label_window_start)
            """,
            (S9_TASK_ID,),
        ).fetchone()[0]
        leakage_rows = rows_to_dicts(
            conn.execute(
                """
                select leakage_guard_id, factor_hypothesis_id, dataset_build_plan_id, status, checked_row_count,
                       violation_count
                from leakage_guard_results_s9
                where task_id = ?
                order by factor_hypothesis_id
                """,
                (S9_TASK_ID,),
            ).fetchall()
        )
        backtest_without_passed_leakage = conn.execute(
            """
            select count(*)
            from backtest_results_s9 bt
            left join leakage_guard_results_s9 lg
              on bt.factor_hypothesis_id = lg.factor_hypothesis_id
             and bt.dataset_build_plan_id = lg.dataset_build_plan_id
            where bt.task_id = ?
              and (lg.status is null or lg.status != 'pass')
            """,
            (S9_TASK_ID,),
        ).fetchone()[0]
    return {
        "status": "pass" if approved_plan_count >= 2 and pit_row_count >= 8 and pit_bad == 0 and backtest_without_passed_leakage == 0 else "fail",
        "approved_plan_count": int(approved_plan_count),
        "pit_row_count": int(pit_row_count),
        "pit_bad": int(pit_bad),
        "leakage_rows": leakage_rows,
        "backtest_without_passed_leakage": int(backtest_without_passed_leakage),
    }


def _collect_human_approval_audit(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        approval_rows = rows_to_dicts(
            conn.execute(
                """
                select factor_hypothesis_id, approval_scope, decision, approver_role, approval_mode
                from human_approval_decisions_s9
                where task_id = ?
                order by factor_hypothesis_id, approval_scope
                """,
                (S9_TASK_ID,),
            ).fetchall()
        )
        approved_factor_ids = [
            row["factor_hypothesis_id"]
            for row in conn.execute(
                "select factor_hypothesis_id from factor_hypotheses_s9 where task_id = ? and status = 'approved_for_validation'",
                (S9_TASK_ID,),
            ).fetchall()
        ]
        bad_approved = []
        for factor_id in approved_factor_ids:
            decisions = {
                str(row.get("approval_scope")): str(row.get("decision"))
                for row in approval_rows
                if row.get("factor_hypothesis_id") == factor_id
            }
            if decisions.get("factor_hypothesis") != "approved" or decisions.get("dataset_build") != "approved" or decisions.get("backtest") != "approved":
                bad_approved.append(factor_id)
        blocked_with_rows = conn.execute(
            """
            select count(*)
            from pit_dataset_rows_s9
            where task_id = ?
              and factor_hypothesis_id in (
                select factor_hypothesis_id
                from factor_hypotheses_s9
                where task_id = ? and status = 'blocked_no_human_approval'
              )
            """,
            (S9_TASK_ID, S9_TASK_ID),
        ).fetchone()[0]
        denied_count = conn.execute(
            """
            select count(*)
            from human_approval_decisions_s9
            where task_id = ? and decision = 'denied'
            """,
            (S9_TASK_ID,),
        ).fetchone()[0]
    return {
        "status": "pass" if not bad_approved and blocked_with_rows == 0 and denied_count >= 1 else "fail",
        "approval_count": len(approval_rows),
        "approved_factor_ids": approved_factor_ids,
        "bad_approved_factor_ids": bad_approved,
        "blocked_factor_pit_row_count": int(blocked_with_rows),
        "denied_approval_count": int(denied_count),
    }


def _collect_advice_and_execution_boundary_audit(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        bad_backtests = conn.execute(
            "select count(*) from backtest_results_s9 where task_id = ? and no_investment_advice != 1",
            (S9_TASK_ID,),
        ).fetchone()[0]
        bad_cards = conn.execute(
            """
            select count(*) from factor_cards_s9
            where task_id = ?
              and (no_investment_advice != 1 or forbidden_actions_json not like '%live_trading%')
            """,
            (S9_TASK_ID,),
        ).fetchone()[0]
        paper_started = conn.execute(
            "select count(*) from paper_trading_controls_s9 where task_id = ? and status not like 'not_started%'",
            (S9_TASK_ID,),
        ).fetchone()[0]
        paper_control_count = conn.execute(
            "select count(*) from paper_trading_controls_s9 where task_id = ?",
            (S9_TASK_ID,),
        ).fetchone()[0]
    return {
        "status": "pass" if bad_backtests == 0 and bad_cards == 0 and paper_started == 0 and paper_control_count >= 3 else "fail",
        "bad_backtest_advice_count": int(bad_backtests),
        "bad_factor_card_advice_count": int(bad_cards),
        "paper_started_count": int(paper_started),
        "paper_control_count": int(paper_control_count),
    }


def _collect_factorcard_memory_audit(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = rows_to_dicts(
            conn.execute(
                """
                select card.factor_card_id, card.factor_hypothesis_id, card.status, card.limitations_json,
                       card.failure_scenarios_json, exp.experience_id, exp.outcome,
                       exp.review_status, exp.metrics_json, exp.payload_json
                from factor_cards_s9 card
                left join research_experience_records_s9 exp on card.factor_hypothesis_id = exp.factor_hypothesis_id
                where card.task_id = ?
                order by card.factor_hypothesis_id
                """,
                (S9_TASK_ID,),
            ).fetchall()
        )
    bad_rows = []
    for row in rows:
        metrics = json_loads(str(row.get("metrics_json") or "{}"), {})
        payload = json_loads(str(row.get("payload_json") or "{}"), {})
        if not row.get("experience_id") or not row.get("review_status") or (row.get("status") != "blocked" and not metrics):
            bad_rows.append(row.get("factor_hypothesis_id"))
        if row.get("status") != "blocked" and payload.get("searchable_memory_output") is not True:
            bad_rows.append(row.get("factor_hypothesis_id"))
    return {
        "status": "pass" if rows and not bad_rows else "fail",
        "factor_card_count": len(rows),
        "bad_factor_hypothesis_ids": sorted(set(map(str, bad_rows))),
    }


def _collect_runtime_artifact_audit(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        artifact_count = conn.execute(
            """
            select count(*)
            from artifact_refs
            where task_id = ?
              and artifact_type in (
                'research_to_quant_schema',
                'research_to_quant_summary',
                'research_to_quant_gate_rows',
                'research_to_quant_closeout_report'
              )
            """,
            (S9_TASK_ID,),
        ).fetchone()[0]
        workpaper_event_count = conn.execute(
            "select count(*) from workpaper_events where task_id = ? and event_type = 'research_to_quant_lab_ready'",
            (S9_TASK_ID,),
        ).fetchone()[0]
        quality_gate_count = conn.execute(
            "select count(*) from research_to_quant_quality_gates_s9 where task_id = ?",
            (S9_TASK_ID,),
        ).fetchone()[0]
    return {
        "status": "pass" if artifact_count >= 4 and workpaper_event_count >= 1 and quality_gate_count >= 12 else "fail",
        "runtime_artifact_count": int(artifact_count),
        "workpaper_event_count": int(workpaper_event_count),
        "quality_gate_count": int(quality_gate_count),
    }


def evaluate_research_to_quant_factor_handoff_gates(
    *,
    s9_summary: Mapping[str, Any],
    handoff_records: list[Mapping[str, Any]],
    judgment_card_audit: Mapping[str, Any],
    pit_audit: Mapping[str, Any],
    approval_audit: Mapping[str, Any],
    advice_audit: Mapping[str, Any],
    memory_audit: Mapping[str, Any],
    runtime_audit: Mapping[str, Any],
) -> list[dict[str, Any]]:
    def gate(gate_id: str, passed: bool, description: str, detail: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now_iso(),
            "fixture_id": "P33-1.5",
            "gate_id": gate_id,
            "status": "pass" if passed else "fail",
            "description": description,
            "detail": dict(detail),
            "closeout_level": "L4_scope_pass" if passed else "blocked",
        }

    approved_records = [row for row in handoff_records if row.get("approved_for_backtest")]
    blocked_records = [row for row in handoff_records if not row.get("approved_for_backtest")]
    input_complete = all(_record_input_complete(row) for row in handoff_records)
    approved_output_complete = all(_approved_record_output_complete(row) for row in approved_records)
    blocked_fail_closed = all(_blocked_record_fail_closed(row) for row in blocked_records)
    return [
        gate(
            "p33_1_5_s9_research_to_quant_l4_pass",
            s9_summary.get("release_decision") == "S9_L4_scope_pass"
            and int((s9_summary.get("counts") or {}).get("gate_fail_count") or 0) == 0,
            "S9 Research-to-Quant Lab is already L4-scope pass.",
            {"release_decision": s9_summary.get("release_decision"), "counts": s9_summary.get("counts")},
        ),
        gate(
            "p33_1_5_judgment_signal_source_input_mapping_complete",
            len(handoff_records) >= 3 and input_complete,
            "Every candidate carries judgment IDs, signal definition, feature refs, PIT manifest, approval policy and source refs.",
            {"handoff_record_count": len(handoff_records), "input_complete": input_complete},
        ),
        gate(
            "p33_1_5_judgment_cards_are_first_class_source_backed",
            judgment_card_audit.get("status") == "pass",
            "Judgment card IDs resolve to first-class SQL rows with source refs, authority boundary, counter-view, failure-view and no-advice limits.",
            judgment_card_audit,
        ),
        gate(
            "p33_1_5_factor_output_contract_complete_for_approved_records",
            len(approved_records) >= 2 and approved_output_complete,
            "Approved candidates expose factor, signal, backtest plan, leakage result, validation status, approval state and experience record IDs.",
            {"approved_record_count": len(approved_records), "approved_output_complete": approved_output_complete},
        ),
        gate(
            "p33_1_5_blocked_candidate_fails_closed",
            len(blocked_records) >= 1 and blocked_fail_closed,
            "Unapproved candidate is blocked before PIT rows, backtest plan/result or paper trading.",
            {"blocked_record_count": len(blocked_records), "blocked_fail_closed": blocked_fail_closed},
        ),
        gate(
            "p33_1_5_point_in_time_and_leakage_before_backtest",
            pit_audit.get("status") == "pass",
            "PIT rows have publish/available/asof/tradable/label timestamps and backtests require passed leakage guards.",
            pit_audit,
        ),
        gate(
            "p33_1_5_human_approval_state_blocks_unapproved_paths",
            approval_audit.get("status") == "pass",
            "Approved paths have factor/dataset/backtest approvals; denied paths have no PIT rows.",
            approval_audit,
        ),
        gate(
            "p33_1_5_no_trading_or_external_advice_boundary",
            advice_audit.get("status") == "pass",
            "Backtest and FactorCard rows stay internal validation artifacts; paper trading remains not started.",
            advice_audit,
        ),
        gate(
            "p33_1_5_factorcard_and_experience_memory_written",
            memory_audit.get("status") == "pass",
            "FactorCards and ResearchExperienceRecords are written for future searchable internal learning.",
            memory_audit,
        ),
        gate(
            "p33_1_5_runtime_artifacts_and_workpaper_event_ledgered",
            runtime_audit.get("status") == "pass",
            "Schema, summary, gate rows, closeout report and WorkpaperEvent are replayable from SQL-final ledger.",
            runtime_audit,
        ),
    ]


def _record_input_complete(row: Mapping[str, Any]) -> bool:
    inputs = dict(row.get("input_mapping") or {})
    pit = dict(inputs.get("point_in_time_data_manifest") or {})
    approval_policy = dict(inputs.get("human_approval_policy") or {})
    return (
        bool(inputs.get("judgment_card_ids"))
        and bool(inputs.get("signal_definition"))
        and bool(inputs.get("candidate_feature_refs"))
        and bool(inputs.get("source_refs"))
        and bool(pit.get("source_refs"))
        and bool(pit.get("feature_publish_time"))
        and bool(pit.get("feature_available_time"))
        and bool(pit.get("asof_date"))
        and bool(pit.get("tradable_after"))
        and bool(pit.get("label_window_start"))
        and approval_policy.get("dataset_build") == "required"
        and approval_policy.get("backtest") == "required"
    )


def _approved_record_output_complete(row: Mapping[str, Any]) -> bool:
    outputs = dict(row.get("output_mapping") or {})
    approvals = dict(outputs.get("human_approval_state") or {})
    return (
        bool(outputs.get("factor_hypothesis_id"))
        and bool(outputs.get("signal_observation_refs"))
        and bool(outputs.get("backtest_plan_id"))
        and bool(outputs.get("leakage_guard_result"))
        and outputs.get("leakage_guard_status") == "pass"
        and outputs.get("validation_status") in {"pass", "research_validation_pass"}
        and approvals.get("factor_hypothesis") == "approved"
        and approvals.get("dataset_build") == "approved"
        and approvals.get("backtest") == "approved"
        and bool(outputs.get("research_experience_record_id"))
    )


def _blocked_record_fail_closed(row: Mapping[str, Any]) -> bool:
    outputs = dict(row.get("output_mapping") or {})
    approvals = dict(outputs.get("human_approval_state") or {})
    return (
        row.get("dataset_plan_status") == "blocked_no_human_approval"
        and approvals.get("dataset_build") == "denied"
        and outputs.get("blocked_before_backtest_plan") is True
        and not outputs.get("backtest_plan_id")
        and outputs.get("leakage_guard_status") == "blocked_no_human_approval"
        and outputs.get("validation_status") == "blocked"
        and bool(outputs.get("research_experience_record_id"))
    )


def render_research_to_quant_factor_handoff_report(manifest: Mapping[str, Any]) -> str:
    lines = [
        "# P33-1.5 Research-to-Quant Factor Handoff Fixture",
        "",
        f"Generated: `{manifest['generated_at']}`",
        f"Contract: `{manifest['contract_id']}`",
        f"Status: `{manifest['status']}`",
        f"Release decision: `{manifest['release_decision']}`",
        f"Closeout level: `{manifest['closeout_level']}`",
        "",
        "## Scope",
        "",
        "This no-paid fixture proves bounded research judgment material can become internal quant validation objects with PIT, leakage, human approval and no-advice boundaries.",
        "",
        "## Gate Rows",
        "",
    ]
    for row in manifest.get("acceptance_gates") or []:
        lines.append(f"- `{row['status']}` `{row['gate_id']}`: {row['description']}")
    lines.extend(
        [
            "",
            "## Handoff Counts",
            "",
            f"- Handoff records: `{len(manifest.get('handoff_records') or [])}`",
            f"- Judgment cards: `{manifest.get('judgment_card_audit', {}).get('judgment_card_count')}`",
            f"- PIT rows: `{manifest.get('pit_audit', {}).get('pit_row_count')}`",
            f"- Runtime artifacts: `{manifest.get('runtime_audit', {}).get('runtime_artifact_count')}`",
            "",
            "## Boundary",
            "",
            str(manifest.get("runtime_entry_policy")),
            "",
            "## Source Fixture Refs",
            "",
        ]
    )
    for key, value in (manifest.get("source_fixture_refs") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    import json

    return json.loads(path.read_text(encoding="utf-8"))
