from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from sec_agent.non_financial_signal_authority import attach_non_financial_signal_authority_to_rows


RUNTIME_SOURCE_CONTEXT_STORE_SCHEMA_VERSION = "finsight_runtime_source_context_store_v0_1"

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_RUNTIME_SOURCE_CONTEXT_PATHS: dict[str, Path] = {
    "company_reported_product_operating_metrics": REPO_ROOT
    / "data"
    / "manifests"
    / "company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
    "r16_product_kpi_deep_repair": REPO_ROOT
    / "data"
    / "manifests"
    / "r16_product_kpi_deep_repair_runtime_rows_v0_1.jsonl",
    "r17_known_public_product_kpi_repair": REPO_ROOT
    / "data"
    / "manifests"
    / "r17_known_public_product_kpi_repair_runtime_rows_v0_1.jsonl",
    "r17_product_family_evidence": REPO_ROOT
    / "data"
    / "manifests"
    / "r17_product_family_evidence_runtime_rows_v0_1.jsonl",
    "official_product_surface_context": REPO_ROOT
    / "data"
    / "manifests"
    / "official_product_surface_context_rows_v0_1.jsonl",
    "official_product_spec_context": REPO_ROOT
    / "data"
    / "manifests"
    / "official_product_spec_context_rows_v0_1.jsonl",
    "public_official_api_context": REPO_ROOT
    / "data"
    / "manifests"
    / "public_official_api_context_rows_v0_1.jsonl",
    "developer_ecosystem_context": REPO_ROOT
    / "data"
    / "manifests"
    / "developer_ecosystem_context_rows_v0_1.jsonl",
    "app_marketplace_context": REPO_ROOT / "data" / "manifests" / "app_marketplace_context_rows_v0_1.jsonl",
    "hiring_capacity_context": REPO_ROOT / "data" / "manifests" / "hiring_capacity_context_rows_v0_1.jsonl",
    "public_contract_award_context": REPO_ROOT / "data" / "manifests" / "public_contract_award_context_rows_v0_1.jsonl",
    "channel_offer_context": REPO_ROOT / "data" / "manifests" / "channel_offer_context_rows_v0_1.jsonl",
}

PRODUCT_SOURCE_FAMILY = "company_product_evidence_graph"
PUBLIC_SOURCE_FAMILIES = {"public_source_context", "live_public_web_context"}


def runtime_source_context_enabled(state: Mapping[str, Any] | None = None) -> bool:
    """Return whether default runtime source context manifests should be attached."""
    state = state or {}
    for container_key in ("multi_agent_context", "query_contract", "project_inventory"):
        container = state.get(container_key) if isinstance(state.get(container_key), Mapping) else {}
        value = _nested_runtime_source_context_value(container)
        if value is not None:
            return _bool_value(value)
    value = _nested_runtime_source_context_value(state)
    if value is not None:
        return _bool_value(value)
    return _bool_value(os.environ.get("FIN_AGENT_RUNTIME_SOURCE_CONTEXT") or os.environ.get("RUNTIME_SOURCE_CONTEXT"))


def attach_runtime_source_context_rows(
    state: Mapping[str, Any],
    *,
    enabled: bool | None = None,
    paths: Mapping[str, str | Path] | Sequence[str | Path] | str | None = None,
    max_product_rows_per_ticker: int | None = None,
    max_public_rows_per_ticker: int | None = None,
    max_unbound_public_rows: int | None = None,
) -> dict[str, Any]:
    """Attach selected generated source-layer rows to graph runtime state."""
    should_attach = runtime_source_context_enabled(state) if enabled is None else bool(enabled)
    if not should_attach:
        return dict(state)
    config = _runtime_source_context_config(state)
    bundle = load_runtime_source_context_bundle(
        paths=paths or config.get("paths") or config.get("manifest_paths"),
        focus_tickers=_state_focus_tickers(state),
        search_scope_tickers=_state_search_scope_tickers(state),
        max_product_rows_per_ticker=max_product_rows_per_ticker
        or _positive_int(config.get("max_product_rows_per_ticker"), default=24),
        max_public_rows_per_ticker=max_public_rows_per_ticker
        or _positive_int(config.get("max_public_rows_per_ticker"), default=24),
        max_unbound_public_rows=max_unbound_public_rows
        or _positive_int(config.get("max_unbound_public_rows"), default=24),
    )
    next_state = dict(state)
    next_state["product_evidence_rows"] = _append_unique_rows(
        [dict(row) for row in state.get("product_evidence_rows") or [] if isinstance(row, Mapping)],
        bundle.get("product_evidence_rows") or [],
    )
    next_state["public_source_context_rows"] = _append_unique_rows(
        [dict(row) for row in state.get("public_source_context_rows") or [] if isinstance(row, Mapping)],
        bundle.get("public_source_context_rows") or [],
    )
    existing_context = dict(next_state.get("multi_agent_context") or {}) if isinstance(next_state.get("multi_agent_context"), Mapping) else {}
    existing_context["runtime_source_context_store"] = bundle.get("summary") or {}
    next_state["multi_agent_context"] = existing_context
    next_state["runtime_source_context_store"] = bundle
    if bundle.get("source_gaps"):
        next_state["source_gaps"] = _append_unique_rows(
            [dict(row) for row in state.get("source_gaps") or [] if isinstance(row, Mapping)],
            bundle.get("source_gaps") or [],
        )
    return next_state


def load_runtime_source_context_bundle(
    *,
    paths: Mapping[str, str | Path] | Sequence[str | Path] | str | None = None,
    focus_tickers: Iterable[str] | None = None,
    search_scope_tickers: Iterable[str] | None = None,
    max_product_rows_per_ticker: int = 24,
    max_public_rows_per_ticker: int = 24,
    max_unbound_public_rows: int = 24,
) -> dict[str, Any]:
    resolved_paths = resolve_runtime_source_context_paths(paths)
    scope_tickers = _unique_upper([*(focus_tickers or []), *(search_scope_tickers or [])])
    focus = set(_unique_upper(focus_tickers or []))
    product_candidates: list[dict[str, Any]] = []
    public_candidates: list[dict[str, Any]] = []
    path_refs: list[dict[str, Any]] = []
    source_gaps: list[dict[str, Any]] = []
    input_count = 0
    for source_key, path in resolved_paths.items():
        exists = path.exists() and path.is_file()
        path_refs.append({"source_key": source_key, "path": str(path), "exists": exists})
        if not exists:
            source_gaps.append(
                {
                    "gap_id": f"runtime_source_context_missing::{source_key}",
                    "source_family": "public_source_context",
                    "gap_type": "runtime_source_manifest_missing",
                    "reason": f"Runtime source context manifest is missing: {path}",
                    "claim_boundary": "missing manifest cannot be mocked or used as fallback evidence",
                }
            )
            continue
        for row in _read_jsonl_cached(_cache_key(path)):
            input_count += 1
            family = _row_source_family(row)
            if family == PRODUCT_SOURCE_FAMILY:
                if _row_matches_ticker_scope(row, scope_tickers, include_unbound=False):
                    product_candidates.append({**row, "runtime_source_context_source_key": source_key})
            elif family in PUBLIC_SOURCE_FAMILIES or str(row.get("runtime_source_family") or "") == "public_source_context":
                if _row_matches_ticker_scope(row, scope_tickers, include_unbound=True):
                    public_candidates.append({**row, "runtime_source_context_source_key": source_key})
    product_rows = _select_product_rows(
        product_candidates,
        focus_tickers=focus,
        max_rows_per_ticker=max(1, int(max_product_rows_per_ticker)),
    )
    public_rows = _select_public_rows(
        public_candidates,
        focus_tickers=focus,
        max_rows_per_ticker=max(1, int(max_public_rows_per_ticker)),
        max_unbound_rows=max(0, int(max_unbound_public_rows)),
    )
    product_rows = attach_non_financial_signal_authority_to_rows(product_rows)
    public_rows = attach_non_financial_signal_authority_to_rows(public_rows)
    all_selected = [*product_rows, *public_rows]
    summary = _summary(
        all_selected,
        product_rows=product_rows,
        public_rows=public_rows,
        path_refs=path_refs,
        input_count=input_count,
        scope_tickers=scope_tickers,
    )
    return {
        "schema_version": RUNTIME_SOURCE_CONTEXT_STORE_SCHEMA_VERSION,
        "product_evidence_rows": product_rows,
        "public_source_context_rows": public_rows,
        "source_gaps": source_gaps,
        "summary": summary,
        "path_refs": path_refs,
        "selection_policy": "focus_scope_budgeted_runtime_source_context_rows_v0_1",
    }


def resolve_runtime_source_context_paths(
    paths: Mapping[str, str | Path] | Sequence[str | Path] | str | None = None,
) -> dict[str, Path]:
    if paths is None or paths == "":
        env_value = os.environ.get("FIN_AGENT_RUNTIME_SOURCE_CONTEXT_PATHS") or os.environ.get("RUNTIME_SOURCE_CONTEXT_PATHS")
        if env_value:
            return resolve_runtime_source_context_paths(env_value)
        return dict(DEFAULT_RUNTIME_SOURCE_CONTEXT_PATHS)
    if isinstance(paths, Mapping):
        return {str(key): _repo_path(value) for key, value in paths.items() if str(value or "").strip()}
    if isinstance(paths, str):
        parts = [part.strip() for part in re.split(r"[;\n]", paths) if part.strip()]
        return {f"runtime_source_context_{index:02d}": _repo_path(part) for index, part in enumerate(parts, start=1)}
    return {f"runtime_source_context_{index:02d}": _repo_path(path) for index, path in enumerate(paths, start=1) if str(path or "").strip()}


def _runtime_source_context_config(state: Mapping[str, Any]) -> dict[str, Any]:
    for container_key in ("multi_agent_context", "query_contract", "project_inventory"):
        container = state.get(container_key) if isinstance(state.get(container_key), Mapping) else {}
        config = container.get("runtime_source_context") if isinstance(container.get("runtime_source_context"), Mapping) else {}
        if config:
            return dict(config)
    config = state.get("runtime_source_context") if isinstance(state.get("runtime_source_context"), Mapping) else {}
    return dict(config)


def _nested_runtime_source_context_value(container: Mapping[str, Any]) -> Any:
    if "runtime_source_context_enabled" in container:
        return container.get("runtime_source_context_enabled")
    config = container.get("runtime_source_context") if isinstance(container.get("runtime_source_context"), Mapping) else {}
    if "enabled" in config:
        return config.get("enabled")
    return None


def _select_product_rows(rows: list[dict[str, Any]], *, focus_tickers: set[str], max_rows_per_ticker: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _dedupe_rows(rows):
        grouped[_row_ticker(row) or "UNKNOWN"].append(row)
    selected: list[dict[str, Any]] = []
    for ticker in sorted(grouped):
        candidates = sorted(grouped[ticker], key=lambda row: _row_rank(row, focus_tickers=focus_tickers, product=True))
        selected.extend(candidates[:max_rows_per_ticker])
    return selected


def _select_public_rows(
    rows: list[dict[str, Any]],
    *,
    focus_tickers: set[str],
    max_rows_per_ticker: int,
    max_unbound_rows: int,
) -> list[dict[str, Any]]:
    bound: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unbound: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in _dedupe_rows(rows):
        ticker = _row_ticker(row)
        if ticker:
            bound[ticker].append(row)
        else:
            unbound[_unbound_public_group_key(row)].append(row)
    selected: list[dict[str, Any]] = []
    for ticker in sorted(bound):
        candidates = sorted(bound[ticker], key=lambda row: _row_rank(row, focus_tickers=focus_tickers, product=False))
        selected.extend(_select_public_rows_for_ticker(candidates, max_rows=max_rows_per_ticker, focus_tickers=focus_tickers))
    unbound_latest = [
        sorted(candidates, key=lambda row: _row_rank(row, focus_tickers=focus_tickers, product=False))[0]
        for candidates in unbound.values()
    ]
    selected.extend(sorted(unbound_latest, key=lambda row: _row_rank(row, focus_tickers=focus_tickers, product=False))[:max_unbound_rows])
    return selected


def _select_public_rows_for_ticker(
    candidates: list[dict[str, Any]],
    *,
    max_rows: int,
    focus_tickers: set[str],
) -> list[dict[str, Any]]:
    if len(candidates) <= max_rows:
        return candidates
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        grouped[_public_source_group(row)].append(row)
    for source_key in grouped:
        grouped[source_key] = sorted(grouped[source_key], key=lambda row: _row_rank(row, focus_tickers=focus_tickers, product=False))
    source_order = sorted(
        grouped,
        key=lambda source_key: _row_rank(grouped[source_key][0], focus_tickers=focus_tickers, product=False),
    )
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    # First pass: keep role-specific product/spec/deployment rows ahead of generic page context.
    for row in [item for item in candidates if _is_priority_public_context(item)]:
        if len(selected) >= max_rows:
            break
        key = _row_key(row)
        if key in seen:
            continue
        seen.add(key)
        selected.append(row)
    # Second pass: preserve source diversity so one prolific source cannot starve L3/proxy rows.
    for source_key in source_order:
        if len(selected) >= max_rows:
            break
        row = grouped[source_key][0]
        key = _row_key(row)
        if key in seen:
            continue
        seen.add(key)
        selected.append(row)
    # Fill the rest by rank across all candidates.
    for row in candidates:
        if len(selected) >= max_rows:
            break
        key = _row_key(row)
        if key in seen:
            continue
        seen.add(key)
        selected.append(row)
    return selected


def _is_priority_public_context(row: Mapping[str, Any]) -> bool:
    source_role = str(row.get("source_role") or "")
    runtime_contract = str(row.get("runtime_contract") or "")
    return source_role in {
        "technical_product_spec",
        "customer_deployment_proxy",
        "product_benchmark_proxy",
        "product_generation_edge",
        "product_ecosystem_deployment_context",
    } or runtime_contract in {
        "ProductSpecSlot",
        "CustomerDeploymentProxy",
        "ProductBenchmarkProxy",
        "ProductGenerationEdge",
        "ProductEcosystemContext",
    }


def _public_source_group(row: Mapping[str, Any]) -> str:
    return str(row.get("source_id") or row.get("source_class") or row.get("runtime_source_context_source_key") or "unknown")


def _summary(
    rows: list[Mapping[str, Any]],
    *,
    product_rows: list[Mapping[str, Any]],
    public_rows: list[Mapping[str, Any]],
    path_refs: list[Mapping[str, Any]],
    input_count: int,
    scope_tickers: list[str],
) -> dict[str, Any]:
    public_exact_violations = [
        row
        for row in public_rows
        if bool(row.get("exact_value_authority")) or bool(row.get("can_support_company_exact_fact"))
    ]
    return {
        "schema_version": "finsight_runtime_source_context_store_summary_v0_1",
        "input_row_count": input_count,
        "selected_row_count": len(rows),
        "product_evidence_row_count": len(product_rows),
        "public_source_context_row_count": len(public_rows),
        "scope_tickers": scope_tickers,
        "path_count": len(path_refs),
        "missing_path_count": len([ref for ref in path_refs if not ref.get("exists")]),
        "by_source_family": _count(rows, "source_family"),
        "by_source_id": _count(rows, "source_id"),
        "by_source_layer": _count(rows, "source_layer_id", fallback_key="layer_id"),
        "by_ticker": _count(rows, "ticker"),
        "by_signal_authority_type": _count(rows, "signal_authority_type"),
        "by_signal_promotion_level": _count(rows, "signal_promotion_level"),
        "thesis_driver_authority_row_count": sum(1 for row in rows if bool(row.get("thesis_driver_authority"))),
        "public_exact_authority_violation_count": len(public_exact_violations),
        "policy": "generated_source_layer_rows_are_runtime_visible_with_separate_non_financial_signal_authority_v0_2",
    }


def _row_rank(row: Mapping[str, Any], *, focus_tickers: set[str], product: bool) -> tuple[int, int, int, str, str]:
    ticker = _row_ticker(row)
    focus_rank = 0 if ticker and ticker in focus_tickers else 1 if ticker else 2
    year = _row_year(row)
    metric_rank = _metric_rank(row, product=product)
    date_key = _date_int(row)
    return (focus_rank, metric_rank, -year, -date_key, str(row.get("evidence_ref") or row.get("evidence_id") or ""))


def _metric_rank(row: Mapping[str, Any], *, product: bool) -> int:
    text = " ".join(
        str(row.get(key) or "").lower()
        for key in ("metric_family", "metric_name", "structured_context_type", "claim_scope", "source_id")
    )
    text = " ".join(
        [
            text,
            str(row.get("source_role") or "").lower(),
            str(row.get("runtime_contract") or "").lower(),
            str(row.get("slot_id") or "").lower(),
        ]
    )
    if product:
        order = ("product_revenue", "unit_sales", "deliver", "backlog", "orders", "production", "throughput", "subscriber", "arpu")
    else:
        order = (
            "technical_product_spec",
            "customer_deployment_proxy",
            "product_benchmark_proxy",
            "product_generation_edge",
            "product_ecosystem_deployment_context",
            "official_product",
            "product_spec",
            "regulated_product",
            "auto_product",
            "macro",
            "energy",
            "financial",
            "technology",
        )
    for index, term in enumerate(order):
        if term in text:
            return index
    return len(order)


def _unbound_public_group_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("source_id") or row.get("source_class") or ""),
        str(row.get("metric_name") or row.get("product_or_segment") or row.get("product_family") or ""),
        str(row.get("record_type") or row.get("structured_context_type") or ""),
        str(row.get("identifier") or row.get("api_route") or ""),
    )


def _row_matches_ticker_scope(row: Mapping[str, Any], scope_tickers: Sequence[str], *, include_unbound: bool) -> bool:
    if not scope_tickers:
        return True
    ticker = _row_ticker(row)
    if ticker:
        return ticker in set(scope_tickers)
    return include_unbound


def _append_unique_rows(existing: list[dict[str, Any]], new_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output = list(existing)
    seen = {_row_key(row) for row in output}
    for row in new_rows:
        item = dict(row)
        key = _row_key(item)
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _dedupe_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        item = dict(row)
        key = _row_key(item)
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _row_key(row: Mapping[str, Any]) -> str:
    return str(
        row.get("evidence_ref")
        or row.get("evidence_id")
        or row.get("snapshot_id")
        or row.get("metric_id")
        or row.get("source_candidate_id")
        or json.dumps(row, sort_keys=True, ensure_ascii=False)[:500]
    )


def _row_source_family(row: Mapping[str, Any]) -> str:
    family = str(row.get("source_family") or "").strip()
    runtime_family = str(row.get("runtime_source_family") or "").strip()
    if family in {PRODUCT_SOURCE_FAMILY, "public_source_context", "live_public_web_context"}:
        return family
    if runtime_family in {PRODUCT_SOURCE_FAMILY, "public_source_context"}:
        return runtime_family
    return family or runtime_family or str(row.get("source_tier") or "").strip()


def _row_ticker(row: Mapping[str, Any]) -> str:
    return str(row.get("ticker") or row.get("issuer_ticker") or "").upper().strip()


def _state_focus_tickers(state: Mapping[str, Any]) -> list[str]:
    contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    scope = contract.get("scope") if isinstance(contract.get("scope"), Mapping) else {}
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    return _unique_upper(
        state.get("focus_tickers")
        or state.get("selected_tickers")
        or activation.get("focus_tickers")
        or contract.get("focus_tickers")
        or scope.get("focus_tickers")
        or []
    )


def _state_search_scope_tickers(state: Mapping[str, Any]) -> list[str]:
    contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    scope = contract.get("scope") if isinstance(contract.get("scope"), Mapping) else {}
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    return _unique_upper(
        state.get("search_scope_tickers")
        or activation.get("search_scope_tickers")
        or contract.get("search_scope_tickers")
        or scope.get("universe_tickers")
        or _state_focus_tickers(state)
    )


def _row_year(row: Mapping[str, Any]) -> int:
    for key in ("fiscal_year", "year", "source_fiscal_year"):
        value = row.get(key)
        if isinstance(value, int):
            return value
        match = re.search(r"\b(19\d{2}|20\d{2})\b", str(value or ""))
        if match:
            return int(match.group(1))
    for key in ("period", "period_end", "observation_date", "as_of_date", "as_of_datetime"):
        match = re.search(r"\b(19\d{2}|20\d{2})\b", str(row.get(key) or ""))
        if match:
            return int(match.group(1))
    return 0


def _date_int(row: Mapping[str, Any]) -> int:
    text = " ".join(str(row.get(key) or "") for key in ("period_end", "observation_date", "as_of_date", "as_of_datetime", "period"))
    match = re.search(r"\b(19\d{2}|20\d{2})[-/]?(\d{2})?[-/]?(\d{2})?\b", text)
    if not match:
        return 0
    year = match.group(1)
    month = match.group(2) or "00"
    day = match.group(3) or "00"
    return int(f"{year}{month}{day}")


def _count(rows: Iterable[Mapping[str, Any]], key: str, *, fallback_key: str | None = None) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        value = str(row.get(key) or (row.get(fallback_key) if fallback_key else "") or "").strip() or "unknown"
        counter[value] += 1
    return dict(sorted(counter.items()))


def _unique_upper(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value or "").upper().strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _repo_path(value: str | Path) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else REPO_ROOT / path


def _cache_key(path: Path) -> tuple[str, int, int]:
    try:
        stat = path.stat()
        return (str(path.resolve()), int(stat.st_mtime_ns), int(stat.st_size))
    except FileNotFoundError:
        return (str(path), 0, 0)


@lru_cache(maxsize=16)
def _read_jsonl_cached(cache_key: tuple[str, int, int]) -> tuple[dict[str, Any], ...]:
    path = Path(cache_key[0])
    rows: list[dict[str, Any]] = []
    if not path.exists() or not path.is_file():
        return tuple()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            if isinstance(payload, dict):
                rows.append(payload)
    return tuple(rows)


def _positive_int(value: Any, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(1, number)


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "enabled"}
