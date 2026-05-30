from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run post-processing gates for SEC benchmark outputs.")
    parser.add_argument("--gold-run-dir", required=True)
    parser.add_argument("--pipeline-run-dir", default="")
    parser.add_argument("--cases-path", default="eval/sec_cases/test_cases_v1.jsonl")
    parser.add_argument("--output-dir", default="reports/quality")
    parser.add_argument("--max-score-drop", type=float, default=0.25)
    parser.add_argument("--min-overlap-cases", type=int, default=2)
    parser.add_argument(
        "--skip-trap-gate",
        action="store_true",
        help="Skip anti-hallucination trap validation for case-filtered non-trap smoke runs.",
    )
    parser.add_argument(
        "--skip-gold-vs-pipeline-gate",
        action="store_true",
        help="Skip gold-vs-pipeline comparison when the run intentionally contains only one mode.",
    )
    parser.add_argument(
        "--min-qwen-answer-ratio",
        type=float,
        default=0.0,
        help="Hard gate: minimum ratio of answered_qwen9b among non-trap eligible outputs in pipeline run.",
    )
    parser.add_argument(
        "--ledger-path",
        default="reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json",
    )
    parser.add_argument(
        "--skip-answer-ledger-gate",
        action="store_true",
        help="Skip answer prose exact-value validation against the Exact-Value Ledger.",
    )
    parser.add_argument(
        "--skip-ledger-unit-gate",
        action="store_true",
        help="Skip ledger unit validation against source table scale markers.",
    )
    parser.add_argument(
        "--skip-metric-role-term-gate",
        action="store_true",
        help="Skip answer prose metric-family terminology validation.",
    )
    parser.add_argument(
        "--skip-table-cell-gate",
        action="store_true",
        help="Skip metric-table cell validation for table-output benchmark cases.",
    )
    parser.add_argument(
        "--skip-named-fact-gate",
        action="store_true",
        help="Skip named fact support validation against cited evidence text.",
    )
    parser.add_argument(
        "--skip-ledger-missing-consistency-gate",
        action="store_true",
        help="Skip validation that not_found/limitations do not contradict available ledger rows.",
    )
    parser.add_argument(
        "--abstract-rubric-path",
        default="eval/sec_cases/abstract_judgment_rubric_v0_1.json",
        help="Manual rubric for abstract judgment coverage validation.",
    )
    parser.add_argument(
        "--skip-abstract-judgment-gate",
        action="store_true",
        help="Skip Chinese abstract-judgment coverage validation.",
    )
    parser.add_argument(
        "--skip-caveat-claim-gate",
        action="store_true",
        help="Skip manifest-native required_caveats and disallowed_claims validation.",
    )
    parser.add_argument(
        "--skip-v2-semantic-contract-gate",
        action="store_true",
        help="Skip v2 semantic contract validation for peer separation, proxy/direct use, source policy, and target-value roles.",
    )
    parser.add_argument(
        "--judgment-plan-path",
        default="",
        help="Optional validated Judgment Plan used to gate final answers against planned drivers.",
    )
    parser.add_argument(
        "--skip-answer-vs-judgment-plan-gate",
        action="store_true",
        help="Skip final answer-vs-Judgment-Plan validation.",
    )
    parser.add_argument(
        "--skip-metric-source-grounding-gate",
        action="store_true",
        help="Skip validation that metric-backed answer points cite their ledger source evidence.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    gold_scored = output_dir / "sec_benchmark_gold_scored_report.json"
    _run(
        [
            sys.executable,
            "scripts/score_sec_benchmark_outputs.py",
            "--cases-path",
            args.cases_path,
            "--run-dir",
            args.gold_run_dir,
            "--output-path",
            str(gold_scored),
        ]
    )
    trap_run_dir = args.pipeline_run_dir or args.gold_run_dir
    trap_report = None
    if not args.skip_trap_gate:
        trap_report = output_dir / "sec_benchmark_trap_smoke_gate.json"
        _run(
            [
                sys.executable,
                "scripts/validate_trap_refusal_smoke.py",
                "--cases-path",
                args.cases_path,
                "--run-dir",
                trap_run_dir,
                "--output-path",
                str(trap_report),
            ]
        )

    compare_report = None
    pipeline_scored = None
    qwen_usage = None
    answer_ledger_report = None
    metric_role_term_report = None
    named_fact_report = None
    table_cell_report = None
    ledger_missing_consistency_report = None
    abstract_judgment_report = None
    caveat_claim_report = None
    v2_semantic_contract_report = None
    answer_vs_judgment_plan_report = None
    metric_source_grounding_report = None
    if args.pipeline_run_dir:
        pipeline_scored = output_dir / "sec_benchmark_pipeline_scored_report.json"
        _run(
            [
                sys.executable,
                "scripts/score_sec_benchmark_outputs.py",
                "--cases-path",
                args.cases_path,
                "--run-dir",
                args.pipeline_run_dir,
                "--output-path",
                str(pipeline_scored),
            ]
        )
        qwen_usage = _qwen_usage(REPO_ROOT / args.pipeline_run_dir, _case_task_types(REPO_ROOT / args.cases_path))
        if not args.skip_answer_ledger_gate:
            answer_ledger_report = output_dir / "sec_benchmark_answer_ledger_gate.json"
            _run(
                [
                    sys.executable,
                    "scripts/validate_sec_benchmark_answer_ledger.py",
                    "--run-dir",
                    args.pipeline_run_dir,
                    "--ledger-path",
                    args.ledger_path,
                    "--output-path",
                    str(answer_ledger_report),
                ]
            )
        if not args.skip_metric_role_term_gate:
            metric_role_term_report = output_dir / "sec_benchmark_metric_role_term_gate.json"
            _run(
                [
                    sys.executable,
                    "scripts/validate_sec_benchmark_metric_role_terms.py",
                    "--run-dir",
                    args.pipeline_run_dir,
                    "--ledger-path",
                    args.ledger_path,
                    "--output-path",
                    str(metric_role_term_report),
                ]
            )
        if not args.skip_table_cell_gate:
            table_cell_report = output_dir / "sec_benchmark_table_cell_gate.json"
            _run(
                [
                    sys.executable,
                    "scripts/validate_sec_benchmark_table_cells.py",
                    "--run-dir",
                    args.pipeline_run_dir,
                    "--cases-path",
                    args.cases_path,
                    "--ledger-path",
                    args.ledger_path,
                    "--output-path",
                    str(table_cell_report),
                ]
            )
        if not args.skip_named_fact_gate:
            named_fact_report = output_dir / "sec_benchmark_named_fact_support_gate.json"
            _run(
                [
                    sys.executable,
                    "scripts/validate_sec_benchmark_named_fact_support.py",
                    "--run-dir",
                    args.pipeline_run_dir,
                    "--cases-path",
                    args.cases_path,
                    "--output-path",
                    str(named_fact_report),
                ]
            )
        if not args.skip_ledger_missing_consistency_gate:
            ledger_missing_consistency_report = output_dir / "sec_benchmark_ledger_missing_consistency_gate.json"
            _run(
                [
                    sys.executable,
                    "scripts/validate_sec_benchmark_ledger_missing_consistency.py",
                    "--run-dir",
                    args.pipeline_run_dir,
                    "--ledger-path",
                    args.ledger_path,
                    "--output-path",
                    str(ledger_missing_consistency_report),
                ]
            )
        if not args.skip_abstract_judgment_gate:
            abstract_judgment_report = output_dir / "sec_benchmark_abstract_judgment_gate.json"
            _run(
                [
                    sys.executable,
                    "scripts/validate_sec_benchmark_abstract_judgment_rubric.py",
                    "--run-dir",
                    args.pipeline_run_dir,
                    "--cases-path",
                    args.cases_path,
                    "--rubric-path",
                    args.abstract_rubric_path,
                    "--output-path",
                    str(abstract_judgment_report),
                ]
            )
        if not args.skip_caveat_claim_gate:
            caveat_claim_report = output_dir / "sec_benchmark_caveat_claim_gate.json"
            _run(
                [
                    sys.executable,
                    "scripts/validate_sec_benchmark_caveat_claims.py",
                    "--run-dir",
                    args.pipeline_run_dir,
                    "--cases-path",
                    args.cases_path,
                    "--output-path",
                    str(caveat_claim_report),
                ]
            )
        if not args.skip_v2_semantic_contract_gate:
            v2_semantic_contract_report = output_dir / "sec_benchmark_v2_semantic_contract_gate.json"
            _run(
                [
                    sys.executable,
                    "scripts/validate_sec_benchmark_v2_semantic_contracts.py",
                    "--run-dir",
                    args.pipeline_run_dir,
                    "--cases-path",
                    args.cases_path,
                    "--ledger-path",
                    args.ledger_path,
                    "--output-path",
                    str(v2_semantic_contract_report),
                ]
            )
        if args.judgment_plan_path and not args.skip_answer_vs_judgment_plan_gate:
            answer_vs_judgment_plan_report = output_dir / "sec_benchmark_answer_vs_judgment_plan_gate.json"
            _run(
                [
                    sys.executable,
                    "scripts/validate_sec_benchmark_answer_vs_judgment_plan.py",
                    "--run-dir",
                    args.pipeline_run_dir,
                    "--judgment-plan-path",
                    args.judgment_plan_path,
                    "--output-path",
                    str(answer_vs_judgment_plan_report),
                ]
            )
        if not args.skip_metric_source_grounding_gate:
            metric_source_grounding_report = output_dir / "sec_benchmark_metric_source_grounding_gate.json"
            _run(
                [
                    sys.executable,
                    "scripts/validate_sec_benchmark_metric_source_grounding.py",
                    "--run-dir",
                    args.pipeline_run_dir,
                    "--ledger-path",
                    args.ledger_path,
                    "--cases-path",
                    args.cases_path,
                    "--output-path",
                    str(metric_source_grounding_report),
                ]
            )
        if not args.skip_gold_vs_pipeline_gate:
            compare_report = output_dir / "sec_benchmark_gold_vs_pipeline_gate.json"
            _run(
                [
                    sys.executable,
                    "scripts/validate_gold_vs_pipeline_gate.py",
                    "--gold-scored-report",
                    str(gold_scored),
                    "--pipeline-scored-report",
                    str(pipeline_scored),
                    "--max-score-drop",
                    str(args.max_score_drop),
                    "--min-overlap-cases",
                    str(args.min_overlap_cases),
                    "--output-path",
                    str(compare_report),
                ]
            )

    if not args.pipeline_run_dir and not args.skip_answer_ledger_gate:
        answer_ledger_report = output_dir / "sec_benchmark_answer_ledger_gate.json"
        _run(
            [
                sys.executable,
                "scripts/validate_sec_benchmark_answer_ledger.py",
                "--run-dir",
                args.gold_run_dir,
                "--ledger-path",
                args.ledger_path,
                "--output-path",
                str(answer_ledger_report),
            ]
        )
    if not args.pipeline_run_dir and not args.skip_metric_role_term_gate:
        metric_role_term_report = output_dir / "sec_benchmark_metric_role_term_gate.json"
        _run(
            [
                sys.executable,
                "scripts/validate_sec_benchmark_metric_role_terms.py",
                "--run-dir",
                args.gold_run_dir,
                "--ledger-path",
                args.ledger_path,
                "--output-path",
                str(metric_role_term_report),
            ]
        )
    if not args.pipeline_run_dir and not args.skip_table_cell_gate:
        table_cell_report = output_dir / "sec_benchmark_table_cell_gate.json"
        _run(
            [
                sys.executable,
                "scripts/validate_sec_benchmark_table_cells.py",
                "--run-dir",
                args.gold_run_dir,
                "--cases-path",
                args.cases_path,
                "--ledger-path",
                args.ledger_path,
                "--output-path",
                str(table_cell_report),
            ]
        )
    if not args.pipeline_run_dir and not args.skip_named_fact_gate:
        named_fact_report = output_dir / "sec_benchmark_named_fact_support_gate.json"
        _run(
            [
                sys.executable,
                "scripts/validate_sec_benchmark_named_fact_support.py",
                "--run-dir",
                args.gold_run_dir,
                "--cases-path",
                args.cases_path,
                "--output-path",
                str(named_fact_report),
            ]
        )
    if not args.pipeline_run_dir and not args.skip_ledger_missing_consistency_gate:
        ledger_missing_consistency_report = output_dir / "sec_benchmark_ledger_missing_consistency_gate.json"
        _run(
            [
                sys.executable,
                "scripts/validate_sec_benchmark_ledger_missing_consistency.py",
                "--run-dir",
                args.gold_run_dir,
                "--ledger-path",
                args.ledger_path,
                "--output-path",
                str(ledger_missing_consistency_report),
            ]
        )
    if not args.pipeline_run_dir and not args.skip_abstract_judgment_gate:
        abstract_judgment_report = output_dir / "sec_benchmark_abstract_judgment_gate.json"
        _run(
            [
                sys.executable,
                "scripts/validate_sec_benchmark_abstract_judgment_rubric.py",
                "--run-dir",
                args.gold_run_dir,
                "--cases-path",
                args.cases_path,
                "--rubric-path",
                args.abstract_rubric_path,
                "--output-path",
                str(abstract_judgment_report),
            ]
        )
    if not args.pipeline_run_dir and not args.skip_caveat_claim_gate:
        caveat_claim_report = output_dir / "sec_benchmark_caveat_claim_gate.json"
        _run(
            [
                sys.executable,
                "scripts/validate_sec_benchmark_caveat_claims.py",
                "--run-dir",
                args.gold_run_dir,
                "--cases-path",
                args.cases_path,
                "--output-path",
                str(caveat_claim_report),
            ]
        )
    if not args.pipeline_run_dir and not args.skip_v2_semantic_contract_gate:
        v2_semantic_contract_report = output_dir / "sec_benchmark_v2_semantic_contract_gate.json"
        _run(
            [
                sys.executable,
                "scripts/validate_sec_benchmark_v2_semantic_contracts.py",
                "--run-dir",
                args.gold_run_dir,
                "--cases-path",
                args.cases_path,
                "--ledger-path",
                args.ledger_path,
                "--output-path",
                str(v2_semantic_contract_report),
            ]
        )
    if (
        not args.pipeline_run_dir
        and args.judgment_plan_path
        and not args.skip_answer_vs_judgment_plan_gate
    ):
        answer_vs_judgment_plan_report = output_dir / "sec_benchmark_answer_vs_judgment_plan_gate.json"
        _run(
            [
                sys.executable,
                "scripts/validate_sec_benchmark_answer_vs_judgment_plan.py",
                "--run-dir",
                args.gold_run_dir,
                "--judgment-plan-path",
                args.judgment_plan_path,
                "--output-path",
                str(answer_vs_judgment_plan_report),
            ]
        )
    if not args.pipeline_run_dir and not args.skip_metric_source_grounding_gate:
        metric_source_grounding_report = output_dir / "sec_benchmark_metric_source_grounding_gate.json"
        _run(
            [
                sys.executable,
                "scripts/validate_sec_benchmark_metric_source_grounding.py",
                "--run-dir",
                args.gold_run_dir,
                "--ledger-path",
                args.ledger_path,
                "--cases-path",
                args.cases_path,
                "--output-path",
                str(metric_source_grounding_report),
            ]
        )
    ledger_unit_report = None
    if not args.skip_ledger_unit_gate:
        ledger_unit_report = output_dir / "sec_benchmark_ledger_unit_gate.json"
        _run(
            [
                sys.executable,
                "scripts/validate_sec_benchmark_ledger_units.py",
                "--ledger-path",
                args.ledger_path,
                "--output-path",
                str(ledger_unit_report),
            ]
        )

    trap = _read_json(trap_report) if trap_report else None
    gold = _read_json(gold_scored)
    compare = _read_json(compare_report) if compare_report else None
    answer_ledger = _read_json(answer_ledger_report) if answer_ledger_report else None
    metric_role_terms = _read_json(metric_role_term_report) if metric_role_term_report else None
    table_cells = _read_json(table_cell_report) if table_cell_report else None
    named_facts = _read_json(named_fact_report) if named_fact_report else None
    ledger_missing_consistency = (
        _read_json(ledger_missing_consistency_report) if ledger_missing_consistency_report else None
    )
    abstract_judgment = _read_json(abstract_judgment_report) if abstract_judgment_report else None
    caveat_claim = _read_json(caveat_claim_report) if caveat_claim_report else None
    v2_semantic_contract = (
        _read_json(v2_semantic_contract_report) if v2_semantic_contract_report else None
    )
    answer_vs_judgment_plan = (
        _read_json(answer_vs_judgment_plan_report) if answer_vs_judgment_plan_report else None
    )
    metric_source_grounding = (
        _read_json(metric_source_grounding_report) if metric_source_grounding_report else None
    )
    ledger_unit = _read_json(ledger_unit_report) if ledger_unit_report else None
    qwen_gate_pass = True
    qwen_ratio = None
    model_ratio = None
    if qwen_usage is not None:
        qwen_ratio = qwen_usage["qwen_ratio"]
        model_ratio = qwen_usage.get("model_ratio", qwen_ratio)
        qwen_gate_pass = True if model_ratio is None else model_ratio >= args.min_qwen_answer_ratio
    summary = {
        "schema_version": "sec_benchmark_post_gates_v0.1",
        "gold_run_dir": str((REPO_ROOT / args.gold_run_dir).resolve()),
        "pipeline_run_dir": str((REPO_ROOT / args.pipeline_run_dir).resolve()) if args.pipeline_run_dir else None,
        "trap_run_dir": str((REPO_ROOT / trap_run_dir).resolve()),
        "gold_scored_report": str(gold_scored.resolve()),
        "trap_gate_report": str(trap_report.resolve()) if trap_report else None,
        "pipeline_scored_report": str(pipeline_scored.resolve()) if pipeline_scored else None,
        "gold_vs_pipeline_report": str(compare_report.resolve()) if compare_report else None,
        "answer_ledger_report": str(answer_ledger_report.resolve()) if answer_ledger_report else None,
        "metric_role_term_report": str(metric_role_term_report.resolve()) if metric_role_term_report else None,
        "table_cell_report": str(table_cell_report.resolve()) if table_cell_report else None,
        "named_fact_report": str(named_fact_report.resolve()) if named_fact_report else None,
        "ledger_missing_consistency_report": (
            str(ledger_missing_consistency_report.resolve()) if ledger_missing_consistency_report else None
        ),
        "abstract_judgment_report": str(abstract_judgment_report.resolve()) if abstract_judgment_report else None,
        "caveat_claim_report": str(caveat_claim_report.resolve()) if caveat_claim_report else None,
        "v2_semantic_contract_report": (
            str(v2_semantic_contract_report.resolve()) if v2_semantic_contract_report else None
        ),
        "answer_vs_judgment_plan_report": (
            str(answer_vs_judgment_plan_report.resolve()) if answer_vs_judgment_plan_report else None
        ),
        "metric_source_grounding_report": (
            str(metric_source_grounding_report.resolve()) if metric_source_grounding_report else None
        ),
        "ledger_unit_report": str(ledger_unit_report.resolve()) if ledger_unit_report else None,
        "trap_gate_skipped": bool(args.skip_trap_gate),
        "gold_vs_pipeline_gate_skipped": bool(args.skip_gold_vs_pipeline_gate),
        "answer_ledger_gate_skipped": bool(args.skip_answer_ledger_gate),
        "metric_role_term_gate_skipped": bool(args.skip_metric_role_term_gate),
        "table_cell_gate_skipped": bool(args.skip_table_cell_gate),
        "named_fact_gate_skipped": bool(args.skip_named_fact_gate),
        "ledger_missing_consistency_gate_skipped": bool(args.skip_ledger_missing_consistency_gate),
        "abstract_judgment_gate_skipped": bool(args.skip_abstract_judgment_gate),
        "caveat_claim_gate_skipped": bool(args.skip_caveat_claim_gate),
        "v2_semantic_contract_gate_skipped": bool(args.skip_v2_semantic_contract_gate),
        "answer_vs_judgment_plan_gate_skipped": bool(
            args.skip_answer_vs_judgment_plan_gate or not args.judgment_plan_path
        ),
        "metric_source_grounding_gate_skipped": bool(args.skip_metric_source_grounding_gate),
        "ledger_unit_gate_skipped": bool(args.skip_ledger_unit_gate),
        "trap_gate_pass": (bool(trap.get("can_enter_gate")) if trap else None),
        "gold_scored_count": gold.get("summary", {}).get("scored_count"),
        "gold_mean_score_pct": gold.get("summary", {}).get("mean_score_pct"),
        "gold_vs_pipeline_pass": (compare.get("can_enter_gate") if compare else None),
        "answer_ledger_gate_pass": (answer_ledger.get("can_enter_gate") if answer_ledger else None),
        "answer_ledger_summary": (answer_ledger.get("summary") if answer_ledger else None),
        "metric_role_term_gate_pass": (metric_role_terms.get("can_enter_gate") if metric_role_terms else None),
        "metric_role_term_summary": (metric_role_terms.get("summary") if metric_role_terms else None),
        "table_cell_gate_pass": (table_cells.get("can_enter_gate") if table_cells else None),
        "table_cell_summary": (table_cells.get("summary") if table_cells else None),
        "named_fact_gate_pass": (named_facts.get("can_enter_gate") if named_facts else None),
        "named_fact_summary": (named_facts.get("summary") if named_facts else None),
        "ledger_missing_consistency_gate_pass": (
            ledger_missing_consistency.get("can_enter_gate") if ledger_missing_consistency else None
        ),
        "ledger_missing_consistency_summary": (
            ledger_missing_consistency.get("summary") if ledger_missing_consistency else None
        ),
        "abstract_judgment_gate_pass": (abstract_judgment.get("can_enter_gate") if abstract_judgment else None),
        "abstract_judgment_summary": (abstract_judgment.get("summary") if abstract_judgment else None),
        "caveat_claim_gate_pass": (caveat_claim.get("can_enter_gate") if caveat_claim else None),
        "caveat_claim_summary": (caveat_claim.get("summary") if caveat_claim else None),
        "v2_semantic_contract_gate_pass": (
            v2_semantic_contract.get("can_enter_gate") if v2_semantic_contract else None
        ),
        "v2_semantic_contract_summary": (
            v2_semantic_contract.get("summary") if v2_semantic_contract else None
        ),
        "answer_vs_judgment_plan_gate_pass": (
            answer_vs_judgment_plan.get("can_enter_gate") if answer_vs_judgment_plan else None
        ),
        "answer_vs_judgment_plan_summary": (
            answer_vs_judgment_plan.get("summary") if answer_vs_judgment_plan else None
        ),
        "metric_source_grounding_gate_pass": (
            metric_source_grounding.get("can_enter_gate") if metric_source_grounding else None
        ),
        "metric_source_grounding_summary": (
            metric_source_grounding.get("summary") if metric_source_grounding else None
        ),
        "ledger_unit_gate_pass": (ledger_unit.get("can_enter_gate") if ledger_unit else None),
        "ledger_unit_summary": (ledger_unit.get("summary") if ledger_unit else None),
        "min_qwen_answer_ratio": args.min_qwen_answer_ratio,
        "qwen_answer_ratio": qwen_ratio,
        "model_answer_ratio": model_ratio,
        "qwen_answer_gate_pass": qwen_gate_pass,
        "qwen_usage": qwen_usage,
    }
    summary_path = output_dir / "sec_benchmark_post_gates_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary_path": str(summary_path), **summary}, ensure_ascii=False, indent=2))


def _run(cmd: list[str]) -> None:
    completed = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _case_task_types(cases_path: Path) -> dict[str, str]:
    if not cases_path.exists():
        return {}
    rows = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {str(row.get("case_id") or ""): str(row.get("task_type") or "") for row in rows}


def _qwen_usage(run_dir: Path, case_task_types: dict[str, str]) -> dict:
    path = run_dir / "agent_outputs.jsonl"
    if not path.exists():
        return {
            "total_outputs": 0,
            "total_answered": 0,
            "eligible_outputs": 0,
            "eligible_answered": 0,
            "qwen_answered": 0,
            "qwen_ledger_repaired": 0,
            "api_model_answered": 0,
            "api_model_repaired": 0,
            "model_answered": 0,
            "model_repaired": 0,
            "fallback_answered": 0,
            "failed_eligible_outputs": 0,
            "trap_outputs_excluded": 0,
            "qwen_ratio": 0.0,
            "model_ratio": 0.0,
        }
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    trap_rows = [
        row
        for row in rows
        if str(case_task_types.get(str(row.get("case_id") or ""), "")).startswith("anti_hallucination")
    ]
    eligible = [
        row
        for row in rows
        if not str(case_task_types.get(str(row.get("case_id") or ""), "")).startswith("anti_hallucination")
    ]
    answered = [row for row in rows if str(row.get("status")) == "answered"]
    eligible_answered = [row for row in eligible if str(row.get("status")) == "answered"]
    total_answered = len(answered)
    qwen_answered = sum(str(row.get("answer_status")) == "answered_qwen9b" for row in eligible)
    qwen_ledger_repaired = sum(str(row.get("answer_status")) == "answered_qwen9b_ledger_repair" for row in eligible)
    api_model_answered = sum(str(row.get("answer_status")) == "answered_api_model" for row in eligible)
    api_model_repaired = sum(_is_api_model_repair(row) for row in eligible)
    model_answered = qwen_answered + api_model_answered
    model_repaired = qwen_ledger_repaired + api_model_repaired
    model_supported_answered = model_answered + model_repaired
    fallback_answered = sum(_is_contract_fallback(row) for row in eligible)
    failed_eligible_outputs = sum(str(row.get("status")) != "answered" for row in eligible)
    qwen_ratio = (qwen_answered / len(eligible)) if eligible else None
    model_ratio = (model_supported_answered / len(eligible)) if eligible else None
    return {
        "total_outputs": len(rows),
        "total_answered": total_answered,
        "eligible_outputs": len(eligible),
        "eligible_answered": len(eligible_answered),
        "qwen_answered": qwen_answered,
        "qwen_ledger_repaired": qwen_ledger_repaired,
        "api_model_answered": api_model_answered,
        "api_model_repaired": api_model_repaired,
        "model_answered": model_answered,
        "model_repaired": model_repaired,
        "model_supported_answered": model_supported_answered,
        "fallback_answered": fallback_answered,
        "failed_eligible_outputs": failed_eligible_outputs,
        "trap_outputs_excluded": len(trap_rows),
        "qwen_ratio": round(qwen_ratio, 4) if qwen_ratio is not None else None,
        "model_ratio": round(model_ratio, 4) if model_ratio is not None else None,
    }


def _is_contract_fallback(row: dict) -> bool:
    answer_status = str(row.get("answer_status") or "")
    notes = " ".join(str(note) for note in row.get("score_notes") or [])
    return answer_status.startswith("answered_contract_fallback") or "backend_mode:contract_fallback" in notes


def _is_api_model_repair(row: dict) -> bool:
    answer_status = str(row.get("answer_status") or "")
    return answer_status.startswith("answered_api_model_") and answer_status != "answered_api_model"


if __name__ == "__main__":
    main()
