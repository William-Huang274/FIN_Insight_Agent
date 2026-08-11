from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from sec_agent.capital_macro_pack import build_capital_macro_pack, validate_capital_macro_pack  # noqa: E402
from sec_agent.multi_agent_contracts import (  # noqa: E402
    aggregate_specialist_judgment_plan,
    build_multi_agent_memo_draft,
    validate_specialist_memolet,
    verify_multi_agent_memo_draft,
)
from sec_agent.multi_agent_runtime import build_agent_data_view  # noqa: E402
from sec_agent.product_spec_pack import build_product_spec_pack, validate_product_spec_pack  # noqa: E402
from sec_agent.specialist_llm import build_specialist_request_from_state  # noqa: E402


SUMMARY_SCHEMA_VERSION = "sec_agent_kg_subagent_k8_gate_summary_v0.1"
CASE_SCORE_SCHEMA_VERSION = "sec_agent_kg_subagent_k8_case_score_v0.1"
DEFAULT_CASES_PATH = REPO_ROOT / "tests" / "fixtures" / "kg_subagent_k8_cases_v0_1.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "kg_subagent_k8_gate"
DEFAULT_PRODUCT_EVIDENCE_ROWS = REPO_ROOT / "data" / "manifests" / "evidence_fusion_context_rows_v0_1" / "product_evidence_rows.jsonl"
DEFAULT_PUBLIC_CONTEXT_ROWS = REPO_ROOT / "data" / "manifests" / "evidence_fusion_context_rows_v0_1" / "public_source_context_rows.jsonl"
DEFAULT_CAPITAL_OWNERSHIP_ROWS = Path(
    "Z:/FIN_Insight_Agent_data/processed_private/capital_macro_source_adapters/capital_macro_source_adapter_v0_1/capital_ownership_rows.jsonl"
)
DEFAULT_MACRO_DRIVER_ROWS = Path(
    "Z:/FIN_Insight_Agent_data/processed_private/capital_macro_source_adapters/capital_macro_source_adapter_v0_1/macro_driver_rows.jsonl"
)
DEFAULT_MACRO_EXPOSURE_ROWS = Path(
    "Z:/FIN_Insight_Agent_data/processed_private/capital_macro_source_adapters/capital_macro_source_adapter_v0_1/macro_exposure_rows.jsonl"
)
DEFAULT_VERTICAL_OFFICIAL_OBJECT_ROWS = Path(
    "Z:/FIN_Insight_Agent_data/processed_private/capital_macro_source_adapters/capital_macro_source_adapter_v0_1/vertical_official_object_rows.jsonl"
)
DEFAULT_CAPITAL_MACRO_SUMMARY = REPO_ROOT / "data" / "manifests" / "capital_macro_source_adapter_summary_v0_1.json"

STATE_ROW_KEYS = (
    "product_evidence_rows",
    "public_source_context_rows",
    "capital_ownership_rows",
    "macro_driver_rows",
    "macro_exposure_rows",
    "vertical_official_object_rows",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run K8 KG sub-agent pack and boundary gate on 10-20 cases.")
    parser.add_argument("--cases-path", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--product-evidence-rows", type=Path, default=DEFAULT_PRODUCT_EVIDENCE_ROWS)
    parser.add_argument("--public-context-rows", type=Path, default=DEFAULT_PUBLIC_CONTEXT_ROWS)
    parser.add_argument("--capital-ownership-rows", type=Path, default=DEFAULT_CAPITAL_OWNERSHIP_ROWS)
    parser.add_argument("--macro-driver-rows", type=Path, default=DEFAULT_MACRO_DRIVER_ROWS)
    parser.add_argument("--macro-exposure-rows", type=Path, default=DEFAULT_MACRO_EXPOSURE_ROWS)
    parser.add_argument("--vertical-official-object-rows", type=Path, default=DEFAULT_VERTICAL_OFFICIAL_OBJECT_ROWS)
    parser.add_argument("--capital-macro-summary", type=Path, default=DEFAULT_CAPITAL_MACRO_SUMMARY)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cases = _selected_cases(_read_jsonl(args.cases_path), args.case_id, limit=args.limit)
    run_id = args.run_id or _default_run_id()
    output_dir = args.output_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    source_paths = _source_paths(args)
    capital_macro_summary = _read_json(args.capital_macro_summary) if _resolve_path(args.capital_macro_summary).exists() else {}
    started = time.time()
    scores: list[dict[str, Any]] = []

    for ordinal, case in enumerate(cases, start=1):
        case_started = time.time()
        score = score_case(
            case,
            source_paths=source_paths,
            run_id=run_id,
            ordinal=ordinal,
            total=len(cases),
            elapsed_sec=lambda: round(time.time() - case_started, 4),
        )
        case_dir = output_dir / str(score["case_id"])
        case_dir.mkdir(parents=True, exist_ok=True)
        _write_json(case_dir / "kg_subagent_k8_case_score.json", score)
        scores.append(score)

    summary = _aggregate(
        run_id=run_id,
        args=args,
        cases=cases,
        scores=scores,
        source_paths=source_paths,
        capital_macro_summary=capital_macro_summary,
        elapsed_sec=round(time.time() - started, 4),
        output_dir=output_dir,
    )
    _write_jsonl(output_dir / "kg_subagent_k8_case_scores.jsonl", scores)
    summary_path = output_dir / "kg_subagent_k8_gate_summary.json"
    _write_json(summary_path, summary)
    print(json.dumps(_stdout_summary(summary, summary_path), ensure_ascii=False, indent=2))
    if args.strict and summary["gate_status"] != "pass":
        return 1
    return 0


def score_case(
    case: Mapping[str, Any],
    *,
    source_paths: Mapping[str, Path],
    run_id: str,
    ordinal: int,
    total: int,
    elapsed_sec,
) -> dict[str, Any]:
    state, materialization = _materialize_state(case, source_paths=source_paths, run_id=run_id)
    expected = case.get("expected") if isinstance(case.get("expected"), Mapping) else {}
    agent_id = str(case.get("agent_id") or "product_technology_analyst")
    product_pack = build_product_spec_pack(state, max_items=int(case.get("max_pack_items") or 32))
    capital_macro_pack = build_capital_macro_pack(state, max_items=int(case.get("max_pack_items") or 32))
    data_view = build_agent_data_view(agent_id, {**state, "product_spec_pack": product_pack, "capital_macro_pack": capital_macro_pack})
    specialist_request = build_specialist_request_from_state(agent_id, {**state, "product_spec_pack": product_pack, "capital_macro_pack": capital_macro_pack})

    pack_context = {"product_spec_pack": product_pack, "capital_macro_pack": capital_macro_pack}
    known_refs = set(_strings(specialist_request.get("known_evidence_refs")))
    checks: dict[str, bool] = {
        "input_rows_present": materialization["selected_row_count"] + materialization["inline_contract_row_count"] >= int(expected.get("min_input_rows") or 1),
        "specialist_request_policy_present": bool((specialist_request.get("output_contract") or {}).get("policy")),
        "specialist_request_refs_known": bool(known_refs),
    }
    check_details: dict[str, Any] = {
        "materialization": materialization,
        "product_pack_summary": product_pack.get("summary") or {},
        "capital_macro_pack_summary": capital_macro_pack.get("summary") or {},
        "data_view_keys": sorted(data_view.keys()),
        "request_policy": (specialist_request.get("output_contract") or {}).get("policy") or "",
    }

    _score_pack_expectations(
        checks,
        check_details,
        expected.get("product_pack") if isinstance(expected.get("product_pack"), Mapping) else {},
        pack=product_pack,
        prefix="product_pack",
        validator=validate_product_spec_pack,
    )
    _score_pack_expectations(
        checks,
        check_details,
        expected.get("capital_macro_pack") if isinstance(expected.get("capital_macro_pack"), Mapping) else {},
        pack=capital_macro_pack,
        prefix="capital_macro_pack",
        validator=validate_capital_macro_pack,
    )
    _score_specialist_request_expectations(checks, expected, specialist_request)
    _score_boundary_expectations(checks, check_details, expected.get("boundary") if isinstance(expected.get("boundary"), Mapping) else {}, product_pack, capital_macro_pack)

    allowed_probe_results = [
        _score_allowed_probe(probe, agent_id=agent_id, known_refs=known_refs, pack_context=pack_context)
        for probe in expected.get("allowed_claim_probes") or []
        if isinstance(probe, Mapping)
    ]
    forbidden_probe_results = [
        _score_forbidden_probe(probe, agent_id=agent_id, known_refs=known_refs, pack_context=pack_context)
        for probe in expected.get("forbidden_claim_probes") or []
        if isinstance(probe, Mapping)
    ]
    if expected.get("allowed_claim_probes"):
        checks["allowed_claim_probes_pass"] = all(row["status"] == "pass" for row in allowed_probe_results)
    if expected.get("forbidden_claim_probes"):
        checks["forbidden_claim_probes_blocked"] = all(row["status"] == "pass" for row in forbidden_probe_results)
    check_details["allowed_claim_probes"] = allowed_probe_results
    check_details["forbidden_claim_probes"] = forbidden_probe_results

    return {
        "schema_version": CASE_SCORE_SCHEMA_VERSION,
        "case_id": case.get("case_id"),
        "case_group": case.get("case_group"),
        "agent_id": agent_id,
        "ordinal": ordinal,
        "total": total,
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "details": check_details,
        "elapsed_sec": elapsed_sec(),
        "source_boundary_policy": "parser_gated_kg_objects_only_weak_proxy_gap_not_fallback",
    }


def _score_pack_expectations(
    checks: dict[str, bool],
    details: dict[str, Any],
    expected: Mapping[str, Any],
    *,
    pack: Mapping[str, Any],
    prefix: str,
    validator,
) -> None:
    if not expected:
        return
    summary = pack.get("summary") if isinstance(pack.get("summary"), Mapping) else {}
    validation = validator(pack)
    checks[f"{prefix}.status_pass"] = pack.get("status") == "pass"
    checks[f"{prefix}.validation_pass"] = validation.get("status") == "pass"
    for key, value in expected.items():
        if key.startswith("min_"):
            summary_key = key[4:]
            checks[f"{prefix}.{summary_key}_gte"] = int(summary.get(summary_key) or 0) >= int(value or 0)
    details[f"{prefix}_validation"] = validation


def _score_specialist_request_expectations(checks: dict[str, bool], expected: Mapping[str, Any], request: Mapping[str, Any]) -> None:
    request_expected = expected.get("specialist_request") if isinstance(expected.get("specialist_request"), Mapping) else {}
    if not request_expected:
        return
    if request_expected.get("requires_product_spec_pack"):
        checks["specialist_request.product_spec_pack_present"] = bool((request.get("product_spec_pack") or {}).get("summary"))
    if request_expected.get("requires_capital_macro_pack"):
        checks["specialist_request.capital_macro_pack_present"] = bool((request.get("capital_macro_pack") or {}).get("summary"))
    min_refs = int(request_expected.get("min_known_evidence_refs") or 0)
    if min_refs:
        checks["specialist_request.known_refs_gte"] = len(_strings(request.get("known_evidence_refs"))) >= min_refs


def _score_boundary_expectations(
    checks: dict[str, bool],
    details: dict[str, Any],
    expected: Mapping[str, Any],
    product_pack: Mapping[str, Any],
    capital_macro_pack: Mapping[str, Any],
) -> None:
    if not expected:
        return
    if expected.get("channel_offer_context_only"):
        offers = _items(product_pack.get("channel_offers"))
        checks["boundary.channel_offer_context_only"] = bool(offers) and all(
            offer.get("claim_scope") == "price_availability_configuration_context_only"
            and offer.get("exact_value_authority") is False
            and {"company_sales", "sell_through", "market_share", "channel_inventory"} <= set(_strings(offer.get("forbidden_claims")))
            for offer in offers
        )
    if expected.get("field_inquiry_context_only"):
        notes = _items(product_pack.get("field_inquiry_notes"))
        checks["boundary.field_inquiry_context_only"] = bool(notes) and all(
            note.get("claim_scope") == "qualitative_channel_lead_only"
            and note.get("exact_value_authority") is False
            and "authority_fact" in _strings(note.get("forbidden_claims"))
            for note in notes
        )
    if expected.get("ownership_lagged_not_realtime"):
        positions = _items(capital_macro_pack.get("ownership_positions"))
        checks["boundary.ownership_lagged_not_realtime"] = bool(positions) and all(
            pos.get("not_realtime_flag") is True and pos.get("claim_scope") == "lagged_ownership_context_only" for pos in positions
        )
    if expected.get("macro_requires_exposure_bridge"):
        drivers = _items(capital_macro_pack.get("macro_drivers"))
        edges = _items(capital_macro_pack.get("company_exposure_edges"))
        checks["boundary.macro_requires_exposure_bridge"] = bool(drivers) and bool(edges) and all(
            driver.get("exact_value_authority") is False and driver.get("claim_scope") == "macro_or_industry_context_only" for driver in drivers
        )
    if expected.get("vertical_official_context_only"):
        objects = _items(capital_macro_pack.get("vertical_official_objects"))
        checks["boundary.vertical_official_context_only"] = bool(objects) and all(
            obj.get("exact_value_authority") is False and obj.get("claim_scope") == "official_object_context_only" for obj in objects
        )
    if expected.get("commercial_gap_exposed_not_fallback"):
        gaps = _items(product_pack.get("commercial_gaps"))
        checks["boundary.commercial_gap_exposed_not_fallback"] = bool(gaps) and all(
            str(gap.get("gap_status") or "").endswith("not_fallback") or "gap" in str(gap.get("claim_scope") or "").lower() for gap in gaps
        )
    required_rejections = set(_strings(expected.get("required_rejection_reasons")))
    if required_rejections:
        actual = {str(row.get("reason") or "") for row in _items(product_pack.get("rejected_objects")) + _items(capital_macro_pack.get("rejected_objects"))}
        checks["boundary.required_rejections_present"] = required_rejections <= actual
        details["required_rejection_reasons"] = sorted(required_rejections)
        details["actual_rejection_reasons"] = sorted(actual)


def _score_allowed_probe(
    probe: Mapping[str, Any],
    *,
    agent_id: str,
    known_refs: set[str],
    pack_context: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    observation = _probe_observation(probe, pack_context=pack_context)
    memolet = {"agent_id": agent_id, "evidence_boundary": "bounded_rows_only", "observations": [observation]}
    validation = validate_specialist_memolet(memolet, known_evidence_refs=known_refs)
    judgment = aggregate_specialist_judgment_plan([validation.get("memolet") or memolet])
    memo = build_multi_agent_memo_draft(judgment)
    verification = verify_multi_agent_memo_draft(memo, judgment)
    status = "pass" if validation.get("status") == "pass" and verification.get("status") == "pass" else "fail"
    return {
        "probe_id": probe.get("probe_id") or "",
        "status": status,
        "validation_status": validation.get("status"),
        "verification_status": verification.get("status"),
        "verification_error_types": sorted({str(error.get("type") or "") for error in verification.get("errors") or [] if isinstance(error, Mapping)}),
        "evidence_refs": observation.get("evidence_refs") or [],
    }


def _score_forbidden_probe(
    probe: Mapping[str, Any],
    *,
    agent_id: str,
    known_refs: set[str],
    pack_context: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    observation = _probe_observation(probe, pack_context=pack_context)
    memolet = {"agent_id": agent_id, "evidence_boundary": "bounded_rows_only", "observations": [observation]}
    validation = validate_specialist_memolet(memolet, known_evidence_refs=known_refs)
    judgment = aggregate_specialist_judgment_plan([validation.get("memolet") or memolet])
    memo = build_multi_agent_memo_draft(judgment)
    verification = verify_multi_agent_memo_draft(memo, judgment)
    error_types = {str(error.get("type") or "") for error in verification.get("errors") or [] if isinstance(error, Mapping)}
    expected_errors = set(_strings(probe.get("expected_error_types")))
    status = "pass" if validation.get("status") == "pass" and verification.get("status") == "fail" and expected_errors <= error_types else "fail"
    return {
        "probe_id": probe.get("probe_id") or "",
        "status": status,
        "validation_status": validation.get("status"),
        "verification_status": verification.get("status"),
        "expected_error_types": sorted(expected_errors),
        "verification_error_types": sorted(error_types),
        "evidence_refs": observation.get("evidence_refs") or [],
    }


def _probe_observation(probe: Mapping[str, Any], *, pack_context: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    observation = {key: value for key, value in probe.items() if key not in {"probe_id", "expected_error_types", "evidence_ref_selector"}}
    selector = probe.get("evidence_ref_selector") if isinstance(probe.get("evidence_ref_selector"), Mapping) else {}
    if selector and not observation.get("evidence_refs"):
        refs = _refs_from_selector(selector, pack_context)
        if refs:
            observation["evidence_refs"] = refs
    return observation


def _refs_from_selector(selector: Mapping[str, Any], pack_context: Mapping[str, Mapping[str, Any]]) -> list[str]:
    pack_name = str(selector.get("pack") or "")
    collection = str(selector.get("collection") or "")
    index = int(selector.get("index") or 0)
    pack = pack_context.get(pack_name) if isinstance(pack_context.get(pack_name), Mapping) else {}
    items = _items(pack.get(collection))
    if index < 0 or index >= len(items):
        return []
    refs = _strings(items[index].get("evidence_refs"))
    if refs:
        return refs
    ref = str(items[index].get("evidence_ref") or items[index].get("source_id") or "").strip()
    return [ref] if ref else []


def _materialize_state(case: Mapping[str, Any], *, source_paths: Mapping[str, Path], run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    state: dict[str, Any] = {
        "run_id": f"{run_id}:{case.get('case_id')}",
        "agent_activation_plan": {
            "execution_mode": str(case.get("execution_mode") or "standard_memo"),
            "activate_agents": [str(case.get("agent_id") or "product_technology_analyst")],
            "agent_priorities": {str(case.get("agent_id") or "product_technology_analyst"): "primary"},
        },
    }
    selected_counts: dict[str, int] = {}
    inline_counts: dict[str, int] = {}
    for key in STATE_ROW_KEYS:
        state[key] = []
    for selector in case.get("input_selectors") or []:
        if not isinstance(selector, Mapping):
            continue
        source = str(selector.get("source") or "")
        target_key = str(selector.get("target_key") or _default_target_key(source))
        rows = _select_rows(source_paths.get(source), selector)
        state.setdefault(target_key, []).extend(rows)
        selected_counts[source] = selected_counts.get(source, 0) + len(rows)
    inline_state = case.get("inline_state") if isinstance(case.get("inline_state"), Mapping) else {}
    for key in STATE_ROW_KEYS:
        rows = [dict(row) for row in inline_state.get(key) or [] if isinstance(row, Mapping)]
        if rows:
            state.setdefault(key, []).extend(rows)
            inline_counts[key] = inline_counts.get(key, 0) + len(rows)
    selected_row_count = sum(selected_counts.values())
    inline_contract_row_count = sum(inline_counts.values())
    return state, {
        "selected_row_count": selected_row_count,
        "inline_contract_row_count": inline_contract_row_count,
        "selected_counts": selected_counts,
        "inline_counts": inline_counts,
        "source_paths": {key: _path_str(path) for key, path in source_paths.items()},
    }


def _select_rows(path: Path | None, selector: Mapping[str, Any]) -> list[dict[str, Any]]:
    if path is None:
        return []
    resolved = _resolve_path(path)
    if not resolved.exists():
        return []
    limit = int(selector.get("limit") or 1)
    filters = selector.get("filters") if isinstance(selector.get("filters"), Mapping) else {}
    rows: list[dict[str, Any]] = []
    with resolved.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, Mapping) and _row_matches(row, filters):
                rows.append(dict(row))
    return rows


def _row_matches(row: Mapping[str, Any], filters: Mapping[str, Any]) -> bool:
    for key, expected in filters.items():
        actual = row.get(key)
        if isinstance(expected, list):
            if str(actual) not in {str(item) for item in expected}:
                return False
        elif str(actual) != str(expected):
            return False
    return True


def _aggregate(
    *,
    run_id: str,
    args: argparse.Namespace,
    cases: list[dict[str, Any]],
    scores: list[dict[str, Any]],
    source_paths: Mapping[str, Path],
    capital_macro_summary: Mapping[str, Any],
    elapsed_sec: float,
    output_dir: Path,
) -> dict[str, Any]:
    pass_count = sum(1 for score in scores if score.get("status") == "pass")
    fail_count = len(scores) - pass_count
    groups: dict[str, dict[str, int]] = {}
    for score in scores:
        group = str(score.get("case_group") or "unknown")
        groups.setdefault(group, {"case_count": 0, "pass_count": 0, "fail_count": 0})
        groups[group]["case_count"] += 1
        if score.get("status") == "pass":
            groups[group]["pass_count"] += 1
        else:
            groups[group]["fail_count"] += 1
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gate_status": "pass" if fail_count == 0 and len(scores) >= 10 else "fail",
        "case_count": len(scores),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "case_group_summary": groups,
        "case_ids": [case.get("case_id") for case in cases],
        "failed_case_ids": [score.get("case_id") for score in scores if score.get("status") != "pass"],
        "output_dir": _path_str(output_dir),
        "elapsed_sec": elapsed_sec,
        "source_paths": {key: _path_str(path) for key, path in source_paths.items()},
        "capital_macro_adapter_status": {
            "summary_schema_version": capital_macro_summary.get("schema_version") or "",
            "status": capital_macro_summary.get("status") or "",
            "target_company_count": capital_macro_summary.get("target_company_count") or 0,
            "pack_summary": capital_macro_summary.get("capital_macro_pack_summary") or {},
            "known_source_family_gaps": capital_macro_summary.get("known_source_family_gaps") or [],
        },
        "boundary_policy": "K8 validates KG pack/sub-agent boundaries; public proxy, channel, field inquiry, 13F, macro, vertical official and semantic/public rows cannot be promoted into unsupported company facts.",
        "large_artifact_policy": "Only small scores are written under eval; raw materialized JSONL inputs remain referenced by path and are not copied into Git.",
        "config": {
            "cases_path": _path_str(args.cases_path),
            "strict": bool(args.strict),
        },
    }


def _source_paths(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "product_evidence_rows": args.product_evidence_rows,
        "public_context_rows": args.public_context_rows,
        "capital_ownership_rows": args.capital_ownership_rows,
        "macro_driver_rows": args.macro_driver_rows,
        "macro_exposure_rows": args.macro_exposure_rows,
        "vertical_official_object_rows": args.vertical_official_object_rows,
    }


def _default_target_key(source: str) -> str:
    return {
        "product_evidence_rows": "product_evidence_rows",
        "public_context_rows": "public_source_context_rows",
        "capital_ownership_rows": "capital_ownership_rows",
        "macro_driver_rows": "macro_driver_rows",
        "macro_exposure_rows": "macro_exposure_rows",
        "vertical_official_object_rows": "vertical_official_object_rows",
    }.get(source, source)


def _selected_cases(cases: list[dict[str, Any]], selected_ids: list[str], *, limit: int = 0) -> list[dict[str, Any]]:
    rows = cases
    if selected_ids:
        selected = {str(item) for item in selected_ids}
        rows = [case for case in rows if str(case.get("case_id") or "") in selected]
    if limit > 0:
        rows = rows[:limit]
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    resolved = _resolve_path(path)
    if not resolved.exists():
        return {}
    with resolved.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    return value if isinstance(value, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    resolved = _resolve_path(path)
    rows: list[dict[str, Any]] = []
    with resolved.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _default_run_id() -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%d')}_kg_subagent_k8_pack_boundary_gate_v0_1"


def _stdout_summary(summary: Mapping[str, Any], summary_path: Path) -> dict[str, Any]:
    return {
        "run_id": summary.get("run_id"),
        "gate_status": summary.get("gate_status"),
        "case_count": summary.get("case_count"),
        "pass_count": summary.get("pass_count"),
        "fail_count": summary.get("fail_count"),
        "failed_case_ids": summary.get("failed_case_ids"),
        "summary_path": _path_str(summary_path),
    }


def _resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _path_str(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _items(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, Mapping)]


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item or "").strip()]
    return [str(value)] if str(value or "").strip() else []


if __name__ == "__main__":
    raise SystemExit(main())
