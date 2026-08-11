from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence


PRODUCT_FAMILY_GAP_REPAIR_LEDGER_SCHEMA_VERSION = "finsight_product_family_gap_repair_ledger_v0_1"
PRODUCT_FAMILY_GAP_REPAIR_SUMMARY_SCHEMA_VERSION = "finsight_product_family_gap_repair_summary_v0_1"

RUNTIME_READY_SLOT_STATUSES = {
    "product_kpi_exact_slot",
    "filings_taxonomy_slot",
    "official_surface_slot",
    "bounded_context_slot",
}
OPEN_REPAIR_SLOT_STATUSES = {
    "source_discovery_needed",
    "seed_needs_locator",
    "company_route_needs_family_binding",
}
NON_US_SUFFIXES = (".TW", ".HK", ".T", ".KS", ".SZ", ".SS", ".L", ".AS", ".PA", ".TO", ".AX", ".IL")


def build_product_family_gap_repair_ledger(
    *,
    closeout_rows: Iterable[Mapping[str, Any]],
    before_slots: Iterable[Mapping[str, Any]],
    after_slots: Iterable[Mapping[str, Any]],
    materialization_attempts: Iterable[Mapping[str, Any]],
    context_rows: Iterable[Mapping[str, Any]] = (),
    generated_at: str | None = None,
    allow_final_closeout: bool = False,
) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    before_index = _slot_index(before_slots)
    after_index = _slot_index(after_slots)
    attempts_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for attempt in materialization_attempts:
        if not isinstance(attempt, Mapping):
            continue
        ticker = _ticker(attempt)
        if ticker:
            attempts_by_ticker.setdefault(ticker, []).append(dict(attempt))
    context_by_key: Counter[tuple[str, str]] = Counter()
    context_by_ticker: Counter[str] = Counter()
    for row in context_rows:
        if not isinstance(row, Mapping):
            continue
        ticker = _ticker(row)
        if not ticker:
            continue
        context_by_ticker[ticker] += 1
        family_id = str(row.get("family_id") or row.get("product_family_id") or "").strip()
        if family_id:
            context_by_key[(ticker, family_id)] += 1

    rows: list[dict[str, Any]] = []
    for raw in closeout_rows:
        if not isinstance(raw, Mapping):
            continue
        closeout = dict(raw)
        ticker = _ticker(closeout)
        family_id = str(closeout.get("family_id") or "").strip()
        key = (ticker, family_id)
        before = before_index.get(key)
        after = after_index.get(key)
        attempts = attempts_by_ticker.get(ticker, [])
        attempted_steps = infer_attempted_ladder_steps(
            closeout_row=closeout,
            attempts=attempts,
            before_slot=before,
            after_slot=after,
            context_row_count=context_by_ticker.get(ticker, 0),
        )
        required_steps = required_repair_ladder_steps(closeout)
        missing_steps = [step for step in required_steps if step not in attempted_steps]
        after_status = str((after or {}).get("slot_status") or "")
        before_status = str((before or {}).get("slot_status") or closeout.get("slot_status") or "")
        previous_closeout_slot_status = str(closeout.get("slot_status") or before_status)
        repair_state = classify_repair_state(
            previous_closeout_slot_status=previous_closeout_slot_status,
            before_slot_status=before_status,
            after_slot_status=after_status,
            required_steps=required_steps,
            attempted_steps=attempted_steps,
            allow_final_closeout=allow_final_closeout,
        )
        if repair_state == "fixed_to_runtime_row":
            missing_steps = []
        rows.append(
            {
                "schema_version": PRODUCT_FAMILY_GAP_REPAIR_LEDGER_SCHEMA_VERSION,
                "generated_at": generated_at,
                "ticker": ticker,
                "company_name": closeout.get("company_name") or "",
                "family_id": family_id,
                "family_name": closeout.get("family_name") or "",
                "previous_closeout_class": closeout.get("closeout_class") or "",
                "previous_closeout_reason": closeout.get("closeout_reason") or "",
                "previous_closeout_slot_status": previous_closeout_slot_status,
                "before_slot_status": before_status,
                "after_slot_status": after_status,
                "repair_state": repair_state,
                "required_ladder_steps": required_steps,
                "attempted_ladder_steps": attempted_steps,
                "missing_ladder_steps": missing_steps,
                "final_gap_allowed": bool(allow_final_closeout and not missing_steps and repair_state in {"public_source_exhausted_gap", "commercial_tracker_required"}),
                "materialization_attempt_count": len(attempts),
                "materialization_attempt_status_counts": dict(sorted(Counter(str(row.get("status") or "") for row in attempts).items())),
                "sample_attempt_urls": _unique_strings([row.get("url") for row in attempts])[:8],
                "context_row_count_for_ticker": int(context_by_ticker.get(ticker, 0)),
                "context_row_count_for_ticker_family": int(context_by_key.get(key, 0)),
                "allowed_runtime_use": "repair_evidence_or_gap_disclosure_only" if repair_state != "fixed_to_runtime_row" else "product_specialist_bounded_context",
                "forbidden_runtime_use": [
                    "market_share_or_sales_claim_without_stronger_evidence",
                    "product_performance_claim_without_family_binding",
                    "commercial_gap_masking",
                ],
                "next_action": next_action_for_repair_state(repair_state, missing_steps=missing_steps),
            }
        )
    summary = build_gap_repair_summary(rows=rows, generated_at=generated_at, allow_final_closeout=allow_final_closeout)
    return {"rows": rows, "summary": summary}


def required_repair_ladder_steps(closeout_row: Mapping[str, Any]) -> list[str]:
    ticker = _ticker(closeout_row)
    slot_status = str(closeout_row.get("slot_status") or "")
    steps = [
        "closeout_row_loaded",
        "domain_profile_resolved",
        "official_surface_fetch_attempted",
        "browser_official_surface_fetch_attempted",
        "context_parser_attempted",
        "product_graph_rebuilt",
    ]
    if ticker.endswith(NON_US_SUFFIXES):
        steps.append("local_exchange_or_regulator_path_checked")
    if slot_status == "company_route_needs_family_binding":
        steps.append("family_binding_repair_attempted")
    steps.append("family_specific_l2_l3_route_checked")
    return steps


def infer_attempted_ladder_steps(
    *,
    closeout_row: Mapping[str, Any],
    attempts: Sequence[Mapping[str, Any]],
    before_slot: Mapping[str, Any] | None,
    after_slot: Mapping[str, Any] | None,
    context_row_count: int,
) -> list[str]:
    attempted = {"closeout_row_loaded"}
    if before_slot is not None:
        attempted.add("product_graph_before_loaded")
    if after_slot is not None:
        attempted.add("product_graph_rebuilt")
    if attempts:
        attempted.add("domain_profile_resolved")
        attempted.add("official_surface_fetch_attempted")
        attempted.add("browser_official_surface_fetch_attempted")
    if context_row_count > 0:
        attempted.add("context_parser_attempted")
    if str(closeout_row.get("slot_status") or "") == "company_route_needs_family_binding":
        before_status = str((before_slot or {}).get("slot_status") or "")
        after_status = str((after_slot or {}).get("slot_status") or "")
        if after_status and after_status != before_status:
            attempted.add("family_binding_repair_attempted")
    return sorted(attempted)


def classify_repair_state(
    *,
    previous_closeout_slot_status: str = "",
    before_slot_status: str,
    after_slot_status: str,
    required_steps: Sequence[str],
    attempted_steps: Sequence[str],
    allow_final_closeout: bool = False,
) -> str:
    if after_slot_status in RUNTIME_READY_SLOT_STATUSES and previous_closeout_slot_status in OPEN_REPAIR_SLOT_STATUSES:
        return "fixed_to_runtime_row"
    if after_slot_status in RUNTIME_READY_SLOT_STATUSES and before_slot_status in OPEN_REPAIR_SLOT_STATUSES:
        return "fixed_to_runtime_row"
    missing = [step for step in required_steps if step not in set(attempted_steps)]
    if missing:
        if "official_surface_fetch_attempted" in attempted_steps or "browser_official_surface_fetch_attempted" in attempted_steps:
            return "adapter_needed_not_final_gap"
        return "repair_required"
    if not allow_final_closeout:
        return "adapter_needed_not_final_gap"
    return "public_source_exhausted_gap"


def next_action_for_repair_state(repair_state: str, *, missing_steps: Sequence[str]) -> str:
    if repair_state == "fixed_to_runtime_row":
        return "rebuild_full_runtime_context_and_allow_bounded_product_specialist_use"
    if repair_state == "repair_required":
        return f"continue_repair_ladder_before_any_final_gap; missing={','.join(missing_steps)}"
    if repair_state == "adapter_needed_not_final_gap":
        return f"do_not_final_closeout; implement_or_run_missing_adapters; missing={','.join(missing_steps)}"
    if repair_state == "commercial_tracker_required":
        return "expose_commercial_tracker_gap_with_public_source_boundary"
    return "expose_public_source_exhausted_gap_only_if_audit_is_complete"


def build_gap_repair_summary(*, rows: Sequence[Mapping[str, Any]], generated_at: str | None = None, allow_final_closeout: bool = False) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    return {
        "schema_version": PRODUCT_FAMILY_GAP_REPAIR_SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass",
        "row_count": len(rows),
        "ticker_count": len({_ticker(row) for row in rows}),
        "repair_state_counts": dict(sorted(Counter(str(row.get("repair_state") or "") for row in rows).items())),
        "previous_closeout_class_counts": dict(sorted(Counter(str(row.get("previous_closeout_class") or "") for row in rows).items())),
        "allow_final_closeout": bool(allow_final_closeout),
        "final_gap_allowed_count": sum(1 for row in rows if row.get("final_gap_allowed")),
        "missing_ladder_step_counts": dict(sorted(Counter(step for row in rows for step in (row.get("missing_ladder_steps") or [])).items())),
        "policy": "No row can be called unrepairable unless every required public-source repair ladder step is attempted and audited.",
    }


def _slot_index(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        ticker = _ticker(row)
        family_id = str(row.get("family_id") or "").strip()
        if ticker and family_id:
            out[(ticker, family_id)] = dict(row)
    return out


def _ticker(row: Mapping[str, Any]) -> str:
    return str(row.get("ticker") or "").strip().upper()


def _unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
