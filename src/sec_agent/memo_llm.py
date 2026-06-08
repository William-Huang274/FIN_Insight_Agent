from __future__ import annotations

import json
import os
import re
import hashlib
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from sec_agent.llm_gateway import chat_completion
from sec_agent.multi_agent_contracts import build_multi_agent_memo_draft, verify_multi_agent_memo_draft
from sec_agent.research_skills import research_skill_prompt


MEMO_ROUTE_SCHEMA_VERSION = "sec_agent_memo_llm_route_v0.1"
VERIFIER_ROUTE_SCHEMA_VERSION = "sec_agent_verifier_llm_route_v0.1"
VERIFIER_PROJECTION_SCHEMA_VERSION = "sec_agent_verifier_minimal_projection_v0.1"
SHARED_MEMO_CONTEXT_SCHEMA_VERSION = "sec_agent_shared_memo_context_v0.1"
RESPONSE_LANGUAGE_SCHEMA_VERSION = "sec_agent_response_language_v0.1"
MEMO_ROUTE_SOURCE = "memo_writer_llm_v0.1"
VERIFIER_ROUTE_SOURCE = "verifier_llm_v0.1"
MEMO_ROUTER_ENV = "SEC_AGENT_MULTI_AGENT_MEMO_ROUTER"
MEMO_SUPPORTED_CLAIM_CAP = 5
MEMO_UNSUPPORTED_CLAIM_CAP = 2
MEMO_CONFLICT_CAP = 2
MEMO_LENGTH_REPAIR_SUPPORTED_CLAIM_CAP = 4
MEMO_SALVAGE_SUPPORTED_CLAIM_CAP = 6
MEMO_PROFILE_SCHEMA_VERSION = "sec_agent_memo_profile_v0.1"
MEMO_PROFILE_ORDER = ("compact", "standard", "expanded", "deep_research")

ChatCompletionFunc = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class MemoLLMConfig:
    llm_backend: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    chat_completions_path: str = "/chat/completions"
    model: str = "deepseek-v4-pro"
    api_key_env: str = "DEEPSEEK_API_KEY"
    temperature: float = 0.0
    memo_max_tokens: int = 3600
    verifier_max_tokens: int = 1000
    timeout_s: int = 180
    max_repair_attempts: int = 2


@dataclass(frozen=True)
class MemoProfileSpec:
    profile: str
    direct_answer_max_chars: int
    direct_answer_min_chars: int
    memo_claims_min_when_thesis_ready: int
    memo_claims_max: int
    memo_claim_max_chars: int
    caveats_max: int
    unsupported_claims_excluded_max: int
    source_boundary_notes_max: int
    supported_claim_cap_with_thesis_pack: int
    rendered_claim_max: int


MEMO_PROFILE_SPECS: dict[str, MemoProfileSpec] = {
    "compact": MemoProfileSpec(
        profile="compact",
        direct_answer_max_chars=420,
        direct_answer_min_chars=0,
        memo_claims_min_when_thesis_ready=3,
        memo_claims_max=5,
        memo_claim_max_chars=220,
        caveats_max=3,
        unsupported_claims_excluded_max=2,
        source_boundary_notes_max=3,
        supported_claim_cap_with_thesis_pack=0,
        rendered_claim_max=5,
    ),
    "standard": MemoProfileSpec(
        profile="standard",
        direct_answer_max_chars=900,
        direct_answer_min_chars=420,
        memo_claims_min_when_thesis_ready=4,
        memo_claims_max=6,
        memo_claim_max_chars=260,
        caveats_max=4,
        unsupported_claims_excluded_max=3,
        source_boundary_notes_max=4,
        supported_claim_cap_with_thesis_pack=4,
        rendered_claim_max=6,
    ),
    "expanded": MemoProfileSpec(
        profile="expanded",
        direct_answer_max_chars=1200,
        direct_answer_min_chars=500,
        memo_claims_min_when_thesis_ready=5,
        memo_claims_max=8,
        memo_claim_max_chars=300,
        caveats_max=5,
        unsupported_claims_excluded_max=4,
        source_boundary_notes_max=5,
        supported_claim_cap_with_thesis_pack=5,
        rendered_claim_max=8,
    ),
    "deep_research": MemoProfileSpec(
        profile="deep_research",
        direct_answer_max_chars=1600,
        direct_answer_min_chars=620,
        memo_claims_min_when_thesis_ready=5,
        memo_claims_max=8,
        memo_claim_max_chars=320,
        caveats_max=5,
        unsupported_claims_excluded_max=4,
        source_boundary_notes_max=5,
        supported_claim_cap_with_thesis_pack=6,
        rendered_claim_max=8,
    ),
}


def memo_llm_config_from_env(env: Mapping[str, str] | None = None) -> MemoLLMConfig:
    values = dict(os.environ if env is None else env)
    return MemoLLMConfig(
        llm_backend=values.get("LLM_BACKEND", "deepseek"),
        base_url=values.get("BASE_URL", "https://api.deepseek.com"),
        chat_completions_path=values.get("CHAT_COMPLETIONS_PATH", "/chat/completions"),
        model=values.get("MODEL_NAME", "deepseek-v4-pro"),
        api_key_env=values.get("API_KEY_ENV", "DEEPSEEK_API_KEY"),
        temperature=_float_env(values.get("MEMO_TEMPERATURE"), default=0.0),
        memo_max_tokens=_int_env(values.get("MEMO_MAX_TOKENS"), default=3600),
        verifier_max_tokens=_int_env(values.get("VERIFIER_MAX_TOKENS"), default=1000),
        timeout_s=_int_env(values.get("MEMO_TIMEOUT_S"), default=180),
        max_repair_attempts=_int_env(values.get("MEMO_MAX_REPAIR_ATTEMPTS"), default=2),
    )


def memo_writer_from_env(
    env: Mapping[str, str] | None = None,
    *,
    call_chat_completion: ChatCompletionFunc = chat_completion,
) -> Callable[[Mapping[str, Any]], dict[str, Any]] | None:
    values = dict(os.environ if env is None else env)
    mode = str(values.get(MEMO_ROUTER_ENV) or "mock").strip().lower()
    if mode in {"", "mock", "deterministic", "off", "false", "0"}:
        return None
    if mode not in {"llm", "deepseek", "api"}:
        raise ValueError(f"unsupported {MEMO_ROUTER_ENV}: {mode}")
    config = memo_llm_config_from_env(values)

    def _route(state: Mapping[str, Any]) -> dict[str, Any]:
        return route_memo_writer_llm(state, config=config, call_chat_completion=call_chat_completion)

    return _route


def verifier_from_env(
    env: Mapping[str, str] | None = None,
    *,
    call_chat_completion: ChatCompletionFunc = chat_completion,
) -> Callable[[Mapping[str, Any]], dict[str, Any]] | None:
    values = dict(os.environ if env is None else env)
    mode = str(values.get(MEMO_ROUTER_ENV) or "mock").strip().lower()
    if mode in {"", "mock", "deterministic", "off", "false", "0"}:
        return None
    if mode not in {"llm", "deepseek", "api"}:
        raise ValueError(f"unsupported {MEMO_ROUTER_ENV}: {mode}")
    config = memo_llm_config_from_env(values)

    def _route(state: Mapping[str, Any]) -> dict[str, Any]:
        return route_verifier_llm(state, config=config, call_chat_completion=call_chat_completion)

    return _route


def route_memo_writer_llm(
    state: Mapping[str, Any],
    *,
    config: MemoLLMConfig | None = None,
    call_chat_completion: ChatCompletionFunc = chat_completion,
) -> dict[str, Any]:
    route_config = config or MemoLLMConfig()
    judgment = state.get("verified_judgment_plan") or state.get("judgment_plan") or {}
    shared_context = _compact_shared_memo_context_for_prompt(build_shared_memo_context(state))
    response_language = _response_language_from_context(shared_context.get("response_language"))
    specialist_verification = state.get("specialist_verification") if isinstance(state.get("specialist_verification"), Mapping) else {}
    if specialist_verification.get("memo_writer_allowed") is False or (isinstance(judgment, Mapping) and judgment.get("memo_writer_allowed") is False):
        blocked = build_multi_agent_memo_draft(judgment, specialist_verification=specialist_verification)
        blocked["response_language"] = _response_language_dict(response_language, source="memo_writer_context")
        return {"memo_answer": blocked}

    model_calls: list[dict[str, Any]] = []
    previous_content = ""
    last_failure: dict[str, Any] = {"type": "not_run"}
    for attempt_index in range(max(0, int(route_config.max_repair_attempts)) + 1):
        messages = _memo_messages(
            state,
            prior_failure=last_failure if attempt_index else None,
            prior_content=previous_content if attempt_index else "",
        )
        llm_result = call_chat_completion(
            llm_backend=route_config.llm_backend,
            base_url=route_config.base_url,
            chat_completions_path=route_config.chat_completions_path,
            model=route_config.model,
            messages=messages,
            response_format={"type": "json_object"},
            api_key_env=route_config.api_key_env,
            temperature=route_config.temperature,
            max_tokens=route_config.memo_max_tokens,
            timeout_s=route_config.timeout_s,
            stream=False,
            enable_thinking=False,
            role="memo_writer",
            profile="strong",
            trace_tags={"route_source": MEMO_ROUTE_SOURCE, "repair_attempt": attempt_index},
        )
        model_calls.append(_model_call_summary(llm_result))
        previous_content = str(llm_result.get("content") or "")
        if llm_result.get("status") != "ok":
            last_failure = {"type": "provider_error", "reason": str(llm_result.get("failure_reason") or "")}
            break
        if llm_result.get("tool_calls"):
            last_failure = {"type": "direct_tool_call_forbidden", "detail": "Memo Writer may not call tools."}
            continue
        parsed = extract_json_object(previous_content)
        if parsed is None:
            if str(llm_result.get("finish_reason") or "").lower() == "length":
                last_failure = {
                    "type": "model_output_truncated",
                    "detail": "The model hit max_tokens before closing JSON.",
                    "finish_reason": llm_result.get("finish_reason"),
                    "output_tokens": llm_result.get("output_tokens"),
                }
                continue
            last_failure = {"type": "json_parse_failed", "detail": "No MemoDraft JSON object was found."}
            continue
        shared_context = build_shared_memo_context(state)
        memo_profile = _memo_profile_spec_from_name(
            ((shared_context.get("memo_profile") or {}) if isinstance(shared_context.get("memo_profile"), Mapping) else {}).get("profile")
        )
        response_language = _response_language_from_context(shared_context.get("response_language"))
        memo = _normalize_memo_llm_output(parsed, judgment, memo_profile=memo_profile, response_language=response_language)
        hard_check = verify_multi_agent_memo_draft(memo, judgment)
        if hard_check.get("status") == "pass":
            memo["model_diagnostics"] = _aggregate_model_calls(model_calls)
            memo["schema_version"] = memo.get("schema_version") or "sec_agent_multi_agent_memo_draft_v0.1"
            memo["llm_route_source"] = MEMO_ROUTE_SOURCE
            diagnostics = _aggregate_model_calls(model_calls)
            repair_trigger = last_failure if len(model_calls) > 1 else {}
            return {
                "memo_answer": memo,
                "memo_route_result": {
                    "status": "pass",
                    "memo_profile": memo_profile.profile,
                    "attempt_count": len(model_calls),
                    "repair_attempts": max(0, len(model_calls) - 1),
                    "repair_trigger": repair_trigger,
                    "finish_reasons": diagnostics.get("finish_reasons") or [],
                    "total_tokens": diagnostics.get("total_tokens"),
                },
            }
        last_failure = {"type": "deterministic_memo_gate_failed", "errors": hard_check.get("errors") or []}

    shared_context = build_shared_memo_context(state)
    memo_profile = _memo_profile_spec_from_name(
        ((shared_context.get("memo_profile") or {}) if isinstance(shared_context.get("memo_profile"), Mapping) else {}).get("profile")
    )
    fallback = _deterministic_memo_salvage(
        judgment if isinstance(judgment, Mapping) else {},
        specialist_verification=specialist_verification,
        memo_profile=memo_profile,
        response_language=response_language,
        model_calls=model_calls,
        last_failure=last_failure,
    )
    fallback_check = verify_multi_agent_memo_draft(fallback, judgment if isinstance(judgment, Mapping) else {})
    fallback_status = "pass" if fallback_check.get("status") == "pass" else "fallback"
    return {
        "memo_answer": fallback,
        "memo_route_result": {
            "status": fallback_status,
            "memo_profile": ((fallback.get("memo_profile") or {}) if isinstance(fallback.get("memo_profile"), Mapping) else {}).get("profile")
            or memo_profile.profile,
            "failure_reason": _format_failure_reason(last_failure),
            "deterministic_salvage_used": True,
            "deterministic_salvage_verification": fallback_check.get("status"),
            "attempt_count": len(model_calls),
            "repair_attempts": max(0, len(model_calls) - 1),
            "finish_reasons": (_aggregate_model_calls(model_calls).get("finish_reasons") or []),
            "total_tokens": (_aggregate_model_calls(model_calls).get("total_tokens")),
        },
    }


def route_verifier_llm(
    state: Mapping[str, Any],
    *,
    config: MemoLLMConfig | None = None,
    call_chat_completion: ChatCompletionFunc = chat_completion,
) -> dict[str, Any]:
    route_config = config or MemoLLMConfig()
    judgment = state.get("verified_judgment_plan") or state.get("judgment_plan") or {}
    memo = state.get("memo_answer") or {}
    deterministic = verify_multi_agent_memo_draft(memo, judgment)
    if deterministic.get("status") != "pass":
        deterministic["llm_verifier_skipped"] = "deterministic_gate_failed"
        return {"claim_verification": deterministic, "specialist_verification": state.get("specialist_verification") or {}}

    verifier_projection = _verifier_minimal_projection(state, deterministic=deterministic)
    projection_stats = verifier_projection.get("projection_stats") if isinstance(verifier_projection.get("projection_stats"), Mapping) else {}
    messages = _verifier_messages(state, projection=verifier_projection)
    llm_result = call_chat_completion(
        llm_backend=route_config.llm_backend,
        base_url=route_config.base_url,
        chat_completions_path=route_config.chat_completions_path,
        model=route_config.model,
        messages=messages,
        response_format={"type": "json_object"},
        api_key_env=route_config.api_key_env,
        temperature=0.0,
        max_tokens=route_config.verifier_max_tokens,
        timeout_s=route_config.timeout_s,
        stream=False,
        enable_thinking=False,
        role="verifier",
        profile="strong",
        trace_tags={
            "route_source": VERIFIER_ROUTE_SOURCE,
            "projection_schema": VERIFIER_PROJECTION_SCHEMA_VERSION,
            "projected_claim_count": projection_stats.get("projected_claim_count"),
            "projected_evidence_ref_count": projection_stats.get("projected_evidence_ref_count"),
        },
    )
    summary = _model_call_summary(llm_result)
    if llm_result.get("status") != "ok" or llm_result.get("tool_calls"):
        merged = {
            **deterministic,
            "status": "fail",
            "errors": [
                *list(deterministic.get("errors") or []),
                {"type": "llm_verifier_failed", "reason": str(llm_result.get("failure_reason") or "tool_call_forbidden")},
            ],
            "bounded_answer_allowed": True,
            "verifier_input_projection": projection_stats,
            "model_diagnostics": {"calls": [summary], "raw_response_saved": False},
        }
        return {"claim_verification": merged, "specialist_verification": state.get("specialist_verification") or {}}

    parsed = extract_json_object(str(llm_result.get("content") or "")) or {}
    llm_status = str(parsed.get("status") or "pass").strip()
    llm_errors = [dict(item) for item in parsed.get("errors") or [] if isinstance(item, Mapping)]
    dropped_bounded_errors: list[dict[str, Any]] = []
    if _is_bounded_block_memo(memo):
        llm_errors, dropped_bounded_errors = _filter_soft_verifier_errors(
            llm_errors,
            warning_type="bounded_block_verifier_warning_downgraded",
            reason="bounded_block_answer_does_not_need_full_memo_evidence_when_deterministic_gate_passes",
        )
        if not llm_errors and llm_status == "fail":
            llm_status = "pass"
    elif deterministic.get("status") == "pass":
        llm_errors, dropped_bounded_errors = _filter_soft_verifier_errors(
            llm_errors,
            warning_type="deterministic_pass_verifier_warning_downgraded",
            reason="deterministic_gate_passed_and_llm_error_was_not_a_hard_source_boundary_violation",
        )
        if not llm_errors and llm_status == "fail":
            llm_status = "pass"
    merged = {
        **deterministic,
        "status": "fail" if llm_status == "fail" or llm_errors else "pass",
        "errors": [*list(deterministic.get("errors") or []), *llm_errors],
        "warnings": [
            *list(deterministic.get("warnings") or []),
            *[dict(item) for item in parsed.get("warnings") or [] if isinstance(item, Mapping)],
            *dropped_bounded_errors,
        ],
        "repair_instruction": str(parsed.get("repair_instruction") or deterministic.get("repair_instruction") or ""),
        "bounded_answer_allowed": bool(parsed.get("bounded_answer_allowed") or llm_errors),
        "llm_verifier_policy": "minimal_projection_cannot_override_deterministic_gate",
        "verifier_input_projection": projection_stats,
        "model_diagnostics": {"calls": [summary], "raw_response_saved": False},
    }
    return {"claim_verification": merged, "specialist_verification": state.get("specialist_verification") or {}}


def extract_json_object(text: str) -> dict[str, Any] | None:
    for candidate in _json_candidates(str(text or "")):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _json_for_prompt(value: Any, *, sort_keys: bool = False) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=sort_keys, separators=(",", ":"))


def _normalize_memo_llm_output(
    payload: Mapping[str, Any],
    judgment: Any,
    *,
    memo_profile: MemoProfileSpec | None = None,
    response_language: str = "en-US",
) -> dict[str, Any]:
    profile = memo_profile or MEMO_PROFILE_SPECS["compact"]
    language = _normalize_response_language(response_language) or "en-US"
    memo = dict(payload or {})
    nested = memo.get("memo_draft")
    if isinstance(nested, Mapping):
        wrapper_fields = {key: value for key, value in memo.items() if key != "memo_draft"}
        memo = {**dict(nested), **wrapper_fields}
    for forbidden_key in (
        "verified_judgment_plan",
        "judgment_plan",
        "supported_claims",
        "bounded_evidence_rows",
        "context_rows",
        "analysis_trace",
        "reasoning",
    ):
        memo.pop(forbidden_key, None)
    base = build_multi_agent_memo_draft(judgment if isinstance(judgment, Mapping) else {})
    memo.setdefault("schema_version", base.get("schema_version"))
    memo.setdefault("answer_status", "draft")
    memo.setdefault("memo_writer_allowed", True)
    memo["consumed_input_views"] = ["verified_judgment_plan", "verified_summary"]
    memo["raw_rows_consumed"] = False
    memo["tool_calls_requested"] = []
    memo.setdefault("source_boundary", base.get("source_boundary") or "verified judgment plan only")
    if language == "zh-CN":
        memo["source_boundary"] = _localize_source_boundary_for_zh(memo.get("source_boundary"))
    memo.setdefault("source_boundary_notes", base.get("source_boundary_notes") or [])
    memo.setdefault("evidence_strength", base.get("evidence_strength") or {})
    memo.setdefault("counterevidence", base.get("counterevidence") or [])
    memo.setdefault("missing_evidence", base.get("missing_evidence") or [])
    memo["evidence_gap_requests"] = _merge_memo_evidence_gap_requests(
        memo.get("evidence_gap_requests"),
        base.get("evidence_gap_requests"),
    )
    if language == "zh-CN" and "unsupported_claims_excluded" not in memo:
        memo["unsupported_claims_excluded"] = []
    else:
        memo.setdefault("unsupported_claims_excluded", base.get("unsupported_claims_excluded") or [])
    memo.setdefault("memo_constraints", base.get("memo_constraints") or {})
    memo.setdefault("memo_outline", base.get("memo_outline") or [])
    memo["memo_profile"] = _memo_profile_dict(profile)
    memo["response_language"] = _response_language_dict(language, source="memo_writer_context")
    memo["memo_thesis_plan"] = _normalize_output_memo_thesis_plan(
        memo.get("memo_thesis_plan") if isinstance(memo.get("memo_thesis_plan"), Mapping) else base.get("memo_thesis_plan") or {}
    )
    memo.setdefault("memo_thesis_pack", base.get("memo_thesis_pack") or {})
    memo.setdefault("claim_card_stats", base.get("claim_card_stats") or {})
    memo.setdefault("bounded_answer_allowed", False)
    if str(memo.get("answer_status") or "draft") == "draft":
        memo["memo_generation_policy"] = "thesis_led_claim_cards_v0_1"
    else:
        memo.setdefault("memo_generation_policy", "thesis_led_claim_cards_v0_1")
    allowed_statuses = {
        "draft",
        "blocked_by_specialist_verification",
        "blocked_by_judgment_plan",
        "blocked_by_verifier_repair",
    }
    answer_status = str(memo.get("answer_status") or "draft")
    if answer_status not in allowed_statuses:
        memo.setdefault("memo_writer_diagnostics", {})
        diagnostics = memo["memo_writer_diagnostics"]
        if isinstance(diagnostics, dict):
            diagnostics["normalized_answer_status_from"] = answer_status
        memo["answer_status"] = "draft" if memo.get("memo_claims") else "blocked_by_judgment_plan"
        if memo["answer_status"] == "draft":
            memo["memo_generation_policy"] = "thesis_led_claim_cards_v0_1"
    memo["memo_claims"] = _normalize_output_memo_claims(
        memo.get("memo_claims"),
        judgment if isinstance(judgment, Mapping) else {},
        max_claims=profile.memo_claims_max,
        response_language=language,
    )
    memo["investment_implications"] = _normalize_memo_action_items(
        memo.get("investment_implications"),
        max_items=profile.memo_claims_max,
        max_chars=180,
    )
    memo["what_would_change_view"] = _normalize_memo_action_items(
        memo.get("what_would_change_view"),
        max_items=4 if profile.profile in {"expanded", "deep_research"} else 3,
        max_chars=180,
    )
    memo["monitoring_items"] = _normalize_memo_action_items(
        memo.get("monitoring_items"),
        max_items=5 if profile.profile in {"expanded", "deep_research"} else 3,
        max_chars=180,
    )
    if profile.profile in {"standard", "expanded", "deep_research"} and memo["memo_claims"]:
        if not memo["investment_implications"]:
            memo["investment_implications"] = _default_profile_action_items(
                memo["memo_claims"],
                response_language=language,
                kind="investment_implications",
            )
        if not memo["what_would_change_view"]:
            memo["what_would_change_view"] = _default_profile_action_items(
                memo["memo_claims"],
                response_language=language,
                kind="what_would_change_view",
            )
        if not memo["monitoring_items"]:
            memo["monitoring_items"] = _default_profile_action_items(
                memo["memo_claims"],
                response_language=language,
                kind="monitoring_items",
            )
    memo["evidence_gaps_but_actionable"] = _normalize_memo_action_items(
        memo.get("evidence_gaps_but_actionable"),
        max_items=4,
        max_chars=180,
    )
    memo = _normalize_direct_answer_numeric_fidelity(
        memo,
        judgment if isinstance(judgment, Mapping) else {},
        base,
        max_chars=profile.direct_answer_max_chars,
        response_language=language,
    )
    memo = _localize_memo_user_text(memo, response_language=language)
    memo = _sanitize_memo_internal_user_labels(memo, response_language=language)
    return memo


def _sanitize_memo_internal_user_labels(memo: Mapping[str, Any], *, response_language: str) -> dict[str, Any]:
    sanitized = dict(memo)
    text = str(sanitized.get("direct_answer") or "")
    if not text:
        return sanitized
    replacement = "已验证证据" if _normalize_response_language(response_language) == "zh-CN" else "verified evidence"
    cleaned = text
    cleaned = re.sub(
        r"Synthesized\s+thesis\s+from\s+bounded\s+ClaimCards?\s*:?",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\bbounded\s+ClaimCards?\b", replacement, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bverified\s+ClaimCards?\b", replacement, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bClaimCards?\b", replacement, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bclaim\s+cards?\b", replacement, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*\|\s*", "；" if _normalize_response_language(response_language) == "zh-CN" else "; ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ;；:：")
    if cleaned != text:
        sanitized["direct_answer"] = _normalize_zh_punctuation(cleaned) if _normalize_response_language(response_language) == "zh-CN" else cleaned
        sanitized["direct_answer_internal_labels_sanitized"] = True
    return sanitized


def _merge_memo_evidence_gap_requests(primary: Any, fallback: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, tuple[str, ...], tuple[str, ...]]] = set()
    for item in [
        *([row for row in primary if isinstance(row, Mapping)] if isinstance(primary, list) else []),
        *([row for row in fallback if isinstance(row, Mapping)] if isinstance(fallback, list) else []),
    ]:
        row = {
            "request_type": str(item.get("request_type") or item.get("type") or "").strip(),
            "owner_agent": str(item.get("owner_agent") or "").strip(),
            "tickers": [ticker.upper() for ticker in _string_list(item.get("tickers") or item.get("ticker_scope") or item.get("ticker"))],
            "metric_families": _string_list(item.get("metric_families") or item.get("metrics") or item.get("metric_scope")),
            "source_family": str(item.get("source_family") or "").strip(),
            "reason": str(item.get("reason") or item.get("rationale") or "").strip(),
            "blocking_level": str(item.get("blocking_level") or item.get("materiality") or "").strip(),
            "can_answer_bounded_without": bool(item.get("can_answer_bounded_without", True)),
        }
        key = (
            row["request_type"],
            row["owner_agent"],
            row["source_family"],
            row["blocking_level"],
            tuple(row["tickers"]),
            tuple(row["metric_families"]),
        )
        if not row["request_type"] or key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows


def _localize_memo_user_text(memo: Mapping[str, Any], *, response_language: str) -> dict[str, Any]:
    if _normalize_response_language(response_language) != "zh-CN":
        return dict(memo)
    localized = dict(memo)
    localized["source_boundary"] = _localize_source_boundary_for_zh(localized.get("source_boundary"))
    localized["direct_answer"] = _normalize_zh_punctuation(localized.get("direct_answer"))
    if _needs_zh_wrapper(localized.get("direct_answer")):
        localized["direct_answer"] = _zh_wrapped_user_text(str(localized.get("direct_answer") or ""), kind="direct")
        localized["response_language_normalized_user_text"] = True

    memo_claims: list[dict[str, Any]] = []
    for claim in localized.get("memo_claims") or []:
        if not isinstance(claim, Mapping):
            continue
        row = dict(claim)
        row["claim"] = _normalize_zh_punctuation(row.get("claim"))
        if _needs_zh_wrapper(row.get("claim")):
            row["claim"] = _zh_wrapped_user_text(str(row.get("claim") or ""), kind="claim")
            row["response_language_normalized_user_text"] = True
            localized["response_language_normalized_user_text"] = True
        memo_claims.append(row)
    localized["memo_claims"] = memo_claims

    for key in (
        "investment_implications",
        "what_would_change_view",
        "monitoring_items",
        "evidence_gaps_but_actionable",
        "caveats",
        "unsupported_claims_excluded",
        "source_boundary_notes",
    ):
        localized[key] = _localize_memo_loose_items(localized.get(key), key=key)
        if any(isinstance(item, Mapping) and item.get("response_language_normalized_user_text") for item in localized[key]):
            localized["response_language_normalized_user_text"] = True
    return localized


def _normalize_zh_punctuation(value: Any) -> str:
    text = str(value or "")
    if not text or not _contains_cjk(text):
        return text
    text = re.sub(r"([。！？；，、])\s*\.", r"\1", text)
    text = re.sub(r"\.\s*([。！？；，、])", r"\1", text)
    text = re.sub(r"([。！？]){2,}", r"\1", text)
    text = re.sub(
        r"([\u4e00-\u9fff])"
        r"(AMZN|MSFT|GOOGL|GOOG|NVDA|AMD|JPM|BAC|C|WFC|GS|WMT|TGT|XOM|CVX|LLY|PFE|BMY|AMGN|HCA|NEE|DUK|SO|SRE|XEL|DELL|ANET|VRT)\b",
        r"\1；\2",
        text,
    )
    return text.strip()


def _localize_memo_loose_items(value: Any, *, key: str) -> list[Any]:
    rows: list[Any] = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, Mapping):
            row = dict(item)
            field = "text" if row.get("text") else "claim" if row.get("claim") else "reason" if row.get("reason") else ""
            if field:
                row[field] = _normalize_zh_punctuation(row.get(field))
            if field and _needs_zh_wrapper(row.get(field)):
                row[field] = _zh_wrapped_user_text(str(row.get(field) or ""), kind=key)
                row["response_language_normalized_user_text"] = True
            rows.append(row)
        elif _needs_zh_wrapper(item):
            rows.append(_zh_wrapped_user_text(str(item or ""), kind=key))
        else:
            rows.append(item)
    return rows


def _needs_zh_wrapper(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if _contains_cjk(text):
        return False
    stripped = re.sub(r"\[[^\]]+\]", " ", text)
    stripped = re.sub(r"\b(?:[A-Z]{1,6}|10-[KQ]|8-K|GAAP|SEC|FY\d{2,4}|Q[1-4])\b", " ", stripped)
    return len(stripped.strip()) >= 16


def _first_iso_date(values: list[str]) -> str:
    for value in values:
        match = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", str(value or ""))
        if match:
            return match.group(0)
    return ""


def _zh_wrapped_user_text(text: str, *, kind: str) -> str:
    clean = str(text or "").strip()
    if not clean:
        return clean
    if kind == "direct":
        prefix = "基于已验证证据并在当前证据边界内，本段结论概括为："
    elif kind == "claim":
        prefix = "基于已验证证据并在当前证据边界内，本条论据概括为："
    else:
        prefix = "基于已验证证据并在当前证据边界内，此项说明概括为："
    suffix = "以上表述仅对应已列证据引用，不代表超出来源范围的新增事实。"
    return f"{prefix}{clean}。{suffix}"


def _localize_source_boundary_for_zh(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"verified judgment plan only", "bounded verified judgment plan only"}:
        return "仅限已验证 judgment plan；不包含原始检索行。"
    if not _contains_cjk(text):
        return "仅限已验证 judgment plan 和 source_boundary_notes 指定的证据范围；不包含原始检索行。"
    return text


def _normalize_output_memo_thesis_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "status": str(value.get("status") or ""),
        "primary_thesis_claim_id": str(value.get("primary_thesis_claim_id") or ""),
        "primary_thesis": _truncate(str(value.get("primary_thesis") or ""), 260),
        "thesis_direction": str(value.get("thesis_direction") or ""),
    }


def _normalize_output_memo_claims(
    value: Any,
    judgment: Mapping[str, Any],
    *,
    max_claims: int = 5,
    response_language: str = "en-US",
) -> list[dict[str, Any]]:
    supported_by_id = {
        str(item.get("claim_id") or ""): dict(item)
        for item in judgment.get("supported_claims") or []
        if isinstance(item, Mapping) and str(item.get("claim_id") or "")
    }
    claims = [dict(item) for item in value or [] if isinstance(item, Mapping)]
    normalized: list[dict[str, Any]] = []
    for claim in claims[: max(1, max_claims)]:
        row = dict(claim)
        source = supported_by_id.get(str(row.get("claim_id") or ""))
        if source:
            for key in (
                "claim_type",
                "ticker_scope",
                "metric_scope",
                "memo_slot",
                "materiality",
                "direction",
                "evidence_refs",
                "source_families",
                "confidence",
                "caveats",
                "missing_confirmations",
                "as_of_date",
                "snapshot_id",
                "period_role",
            ):
                if not row.get(key) and source.get(key):
                    row[key] = source.get(key)
            source_families = _string_list(row.get("source_families") or row.get("source_family"))
            if "relationship_graph" in source_families and str(row.get("claim_type") or "") not in {
                "relationship_hypothesis",
                "scope_hypothesis",
                "industry_context_only",
                "investment_thesis_synthesis",
            }:
                row["claim_type"] = "relationship_hypothesis"
                row["relationship_claim_type_normalized"] = True
            if "market_snapshot" in source_families and not str(row.get("as_of_date") or ""):
                refs = _string_list(row.get("evidence_refs") or row.get("refs"))
                row["as_of_date"] = _first_iso_date(refs) or "latest_available_market_snapshot"
                row["market_as_of_date_inferred"] = True
            unknown_numeric_tokens = _unknown_numeric_tokens(str(row.get("claim") or ""), _claim_scope_text(source))
            hard_unknown_tokens = [token for token in unknown_numeric_tokens if _is_material_numeric_token(token)]
            if hard_unknown_tokens:
                current_claim = str(row.get("claim") or "")
                if response_language == "zh-CN" and _contains_cjk(current_claim):
                    row["claim"] = _remove_unknown_numeric_tokens_from_text(current_claim, set(hard_unknown_tokens))
                    row["numeric_fidelity_removed_tokens"] = sorted(hard_unknown_tokens)[:8]
                else:
                    row["claim"] = str(source.get("claim") or row.get("claim") or "")
                row["numeric_fidelity_normalized"] = True
        normalized.append(row)
    return normalized


def _normalize_memo_action_items(value: Any, *, max_items: int, max_chars: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, Mapping):
            text = str(item.get("text") or item.get("claim") or item.get("reason") or item.get("driver") or "").strip()
            row = {
                "text": _truncate(text, max_chars),
                "claim_id": str(item.get("claim_id") or ""),
                "evidence_refs": _string_list(item.get("evidence_refs") or item.get("refs"))[:4],
            }
        else:
            row = {"text": _truncate(str(item or "").strip(), max_chars), "claim_id": "", "evidence_refs": []}
        if row["text"]:
            rows.append(row)
        if len(rows) >= max(0, max_items):
            break
    return rows


def _default_profile_action_items(
    memo_claims: list[dict[str, Any]],
    *,
    response_language: str,
    kind: str,
) -> list[dict[str, Any]]:
    first = memo_claims[0] if memo_claims and isinstance(memo_claims[0], Mapping) else {}
    claim_id = str(first.get("claim_id") or "")
    refs = _string_list(first.get("evidence_refs") or first.get("refs"))[:3]
    zh = _normalize_response_language(response_language) == "zh-CN"
    templates_zh = {
        "investment_implications": "把已验证的核心论据作为当前判断依据，但置信度和结论强度必须受证据边界约束。",
        "what_would_change_view": "如果后续披露推翻核心论据对应的指标方向、管理层解释或市场反应，需要重新评估当前判断。",
        "monitoring_items": "继续跟踪下一期10-Q/8-K中与核心论据相同的指标和证据缺口，确认当前判断是否仍成立。",
    }
    templates_en = {
        "investment_implications": "Use the verified core claim as the current view anchor while sizing confidence to the evidence boundary.",
        "what_would_change_view": "Reassess the view if later filings contradict the core claim's metric direction, management explanation, or market reaction.",
        "monitoring_items": "Track the same metrics and evidence gaps in the next 10-Q/8-K to confirm whether the current view still holds.",
    }
    text = (templates_zh if zh else templates_en).get(kind, "")
    return [{"text": text, "claim_id": claim_id, "evidence_refs": refs}] if text else []


def _normalize_direct_answer_numeric_fidelity(
    memo: dict[str, Any],
    judgment: Mapping[str, Any],
    base_memo: Mapping[str, Any],
    *,
    max_chars: int,
    response_language: str = "en-US",
) -> dict[str, Any]:
    supported_scope = " ".join(
        _claim_scope_text(item)
        for item in judgment.get("supported_claims") or []
        if isinstance(item, Mapping)
    )
    if not supported_scope:
        return memo
    unknown_tokens = _unknown_numeric_tokens(str(memo.get("direct_answer") or ""), supported_scope)
    hard_unknown_tokens = [token for token in unknown_tokens if _is_material_numeric_token(token)]
    if not hard_unknown_tokens:
        return memo
    safe_direct_answer = _safe_direct_answer_from_claims(
        memo.get("memo_claims") or [],
        str(base_memo.get("direct_answer") or ""),
        max_chars=max_chars,
    )
    next_memo = dict(memo)
    current_direct = str(memo.get("direct_answer") or "")
    if response_language == "zh-CN" and _contains_cjk(current_direct):
        cleaned_direct = _truncate(_remove_unknown_numeric_tokens_from_text(current_direct, set(hard_unknown_tokens)), max_chars)
        next_memo["direct_answer"] = (
            safe_direct_answer
            if _numeric_removal_damaged_direct_answer(current_direct, cleaned_direct)
            else cleaned_direct
        )
    else:
        next_memo["direct_answer"] = safe_direct_answer
    next_memo["direct_answer_numeric_fidelity_normalized"] = True
    next_memo["direct_answer_numeric_fidelity_removed_tokens"] = hard_unknown_tokens[:8]
    return next_memo


def _numeric_removal_damaged_direct_answer(original: str, cleaned: str) -> bool:
    original_text = str(original or "")
    cleaned_text = str(cleaned or "")
    if not cleaned_text.strip():
        return True
    original_numeric_count = len(_numeric_token_details(original_text))
    cleaned_numeric_count = len(_numeric_token_details(cleaned_text))
    if original_numeric_count and cleaned_numeric_count == 0:
        return True
    dangling_patterns = (
        r"(营业利润|营收|收入|利润|费用|支出|现金流|margin|revenue|income)\s*(为|是|达|达到)\s*(这些|数据|证据|披露|公司|本轮|营收|收入|利润|管理层|成本|费用|。|，|,|;|；|$)",
        r"(为|达到)\s*(这些|数据|证据|披露|管理层|成本|费用|。|，|,|;|；|$)",
    )
    return any(re.search(pattern, cleaned_text, flags=re.IGNORECASE) for pattern in dangling_patterns)


def _remove_unknown_numeric_tokens_from_text(text: str, tokens: set[str]) -> str:
    cleaned = str(text or "")
    for token in sorted(tokens, key=len, reverse=True):
        if not token:
            continue
        compact = re.escape(str(token).replace(" ", ""))
        cleaned = re.sub(rf"\$?\s*{compact}", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+([,.;:，。；：])", r"\1", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"(约|大约|达到|为|增长|下降|高达)\s*([,.;:，。；：])", r"\1", cleaned)
    return cleaned.strip()


def _safe_direct_answer_from_claims(claims: list[dict[str, Any]], fallback: str, *, max_chars: int) -> str:
    texts = [str(item.get("claim") or "").strip() for item in claims if isinstance(item, Mapping) and str(item.get("claim") or "").strip()]
    if texts:
        return _truncate(" ".join(text.rstrip(".") + "." for text in texts[:3]), max_chars)
    return _truncate(str(fallback or ""), max_chars)


def _claim_scope_text(claim: Mapping[str, Any]) -> str:
    return " ".join(
        [
            str(claim.get("claim") or ""),
            " ".join(_string_list(claim.get("caveats"))),
            " ".join(_string_list(claim.get("missing_confirmations"))),
        ]
    )


def _unknown_numeric_tokens(candidate_text: str, source_text: str) -> set[str]:
    source_tokens = _numeric_token_details(source_text)
    source_strings = {item[0] for item in source_tokens}
    unknown: set[str] = set()
    for token, value, unit in _numeric_token_details(candidate_text):
        if token in source_strings:
            continue
        if any(_numeric_values_close(value, unit, source_value, source_unit) for _, source_value, source_unit in source_tokens):
            continue
        unknown.add(token)
    return unknown


def _numeric_token_details(text: str) -> list[tuple[str, float, str]]:
    tokens: list[tuple[str, float, str]] = []
    expanded_text = _expand_numeric_ranges(str(text or ""))
    for match in re.finditer(
        r"(?<![A-Za-z0-9])[-+]?\$?\d+(?:,\d{3})*(?:\.\d+)?\s*(?:percentage\s+points?|个百分点|亿美元|百万美元|万美元|%|x|X|倍|M|B|K|bn|mn|million|billion|ppt)?",
        expanded_text,
    ):
        original = match.group(0).strip()
        token = original.lower().replace("$", "").replace(",", "")
        token = re.sub(r"\s+", " ", token).strip()
        parsed = re.match(r"([-+]?\d+(?:\.\d+)?)\s*(.*)", token)
        if token and parsed:
            value, unit = _normalize_numeric_value_and_unit(float(parsed.group(1)), str(parsed.group(2) or ""))
            tokens.append((token.replace(" ", ""), value, unit))
    return tokens


def _expand_numeric_ranges(text: str) -> str:
    unit_pattern = r"(percentage\s+points?|个百分点|亿美元|百万美元|万美元|%|x|X|倍|M|B|K|bn|mn|million|billion|ppt)"

    def _replace(match: re.Match[str]) -> str:
        left = match.group("left")
        right = match.group("right")
        unit = match.group("unit")
        return f"{left}{unit} {right}{unit}"

    return re.sub(
        rf"(?P<left>\$?\d+(?:,\d{{3}})*(?:\.\d+)?)\s*[-–]\s*(?P<right>\$?\d+(?:,\d{{3}})*(?:\.\d+)?)\s*(?P<unit>{unit_pattern})",
        _replace,
        str(text or ""),
        flags=re.IGNORECASE,
    )


def _normalize_numeric_value_and_unit(value: float, unit: str) -> tuple[float, str]:
    normalized = str(unit or "").strip().lower().replace(" ", "")
    if normalized in {"b", "bn", "billion"}:
        return value, "b"
    if normalized in {"m", "mn", "million"}:
        return value / 1000.0, "b"
    if normalized == "k":
        return value / 1_000_000.0, "b"
    if normalized == "亿美元":
        return value / 10.0, "b"
    if normalized == "百万美元":
        return value / 1000.0, "b"
    if normalized == "万美元":
        return value / 100000.0, "b"
    if normalized in {"x", "倍"}:
        return value, "x"
    if normalized in {"%", "percentagepoint", "percentagepoints", "ppt", "个百分点"}:
        return value, "pp" if normalized != "%" else "%"
    return value, normalized


def _numeric_values_close(left_value: float, left_unit: str, right_value: float, right_unit: str) -> bool:
    if left_unit != right_unit:
        return False
    diff = abs(left_value - right_value)
    return diff <= max(0.5, abs(right_value) * 0.005)


def _is_material_numeric_token(token: str) -> bool:
    parsed = re.match(r"([-+]?\d+(?:\.\d+)?)\s*(.*)", str(token or "").strip().lower())
    if not parsed:
        return False
    value = abs(float(parsed.group(1)))
    _, unit = _normalize_numeric_value_and_unit(value, str(parsed.group(2) or ""))
    if unit in {"%", "pp", "x", "b"}:
        return True
    return False


def build_shared_memo_context(state: Mapping[str, Any]) -> dict[str, Any]:
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    reflection = state.get("multi_agent_reflection_report") if isinstance(state.get("multi_agent_reflection_report"), Mapping) else {}
    sufficiency = state.get("evidence_sufficiency_report") if isinstance(state.get("evidence_sufficiency_report"), Mapping) else {}
    judgment = state.get("verified_judgment_plan") or state.get("judgment_plan") or {}
    claim_stats = judgment.get("claim_card_stats") if isinstance(judgment, Mapping) and isinstance(judgment.get("claim_card_stats"), Mapping) else {}
    route_results = [row for row in state.get("specialist_route_results") or [] if isinstance(row, Mapping)]
    relationship_plan = state.get("universe_relationship_plan") if isinstance(state.get("universe_relationship_plan"), Mapping) else {}
    response_language = _select_response_language(state, activation=activation, query_contract=query_contract)
    context = {
        "schema_version": SHARED_MEMO_CONTEXT_SCHEMA_VERSION,
        "user_query": _truncate(str(state.get("user_query") or ""), 420),
        "response_language": response_language,
        "execution_mode": str(activation.get("execution_mode") or state.get("execution_mode") or ""),
        "focus_tickers": _string_list(activation.get("focus_tickers") or query_contract.get("focus_tickers"))[:12],
        "search_scope_tickers": _string_list(activation.get("search_scope_tickers") or query_contract.get("search_scope_tickers"))[:24],
        "coverage": {
            "sufficiency_level": str(reflection.get("sufficiency_level") or sufficiency.get("sufficiency_level") or ""),
            "missing_requirement_count": len(reflection.get("missing_requirements") or sufficiency.get("missing_requirements") or []),
            "bounded_answer_allowed": bool(reflection.get("bounded_answer_allowed") or sufficiency.get("bounded_answer_allowed") or state.get("bounded_answer_allowed")),
        },
        "source_boundaries": {
            "allowed_source_families": _string_list(activation.get("allowed_source_families"))[:12],
            "context_row_count": len(state.get("context_rows") or []),
            "ledger_row_count": len(state.get("runtime_ledger_rows") or []),
            "market_row_count": len(state.get("market_snapshot_rows") or []),
            "industry_row_count": len(state.get("industry_snapshot_rows") or []),
            "relationship_row_count": len(relationship_plan.get("relationships") or []),
        },
        "specialist_routes": {
            "route_count": len(route_results),
            "passed_agents": [
                str(row.get("agent_id") or "")
                for row in route_results
                if str(row.get("status") or "") == "pass" and str(row.get("agent_id") or "")
            ],
            "failed_agents": [
                str(row.get("agent_id") or "")
                for row in route_results
                if str(row.get("status") or "") not in {"pass", "skipped"} and str(row.get("agent_id") or "")
            ],
        },
        "claim_card_stats": {
            "supported_claim_count": int(claim_stats.get("supported_claim_count") or 0),
            "memo_ready_claim_count": int(claim_stats.get("memo_ready_claim_count") or 0),
            "usable_with_caveat_claim_count": int(claim_stats.get("usable_with_caveat_claim_count") or 0),
            "memo_slot_supported_count": int(claim_stats.get("memo_slot_supported_count") or claim_stats.get("supported_memo_slot_count") or 0),
        },
        "prompt_policy": {
            "shared_context_policy": "scope_coverage_boundary_only_no_raw_rows_v0_1",
            "memo_payload_policy": "write_from_verified_judgment_plan_and_thesis_pack_only",
        },
    }
    profile = _select_memo_profile(state, shared_context=context, judgment=judgment if isinstance(judgment, Mapping) else {})
    context["memo_profile"] = _memo_profile_dict(profile)
    context["context_digest"] = _payload_digest(context)
    return context


def _compact_shared_memo_context_for_prompt(context: Mapping[str, Any]) -> dict[str, Any]:
    response_language = context.get("response_language") if isinstance(context.get("response_language"), Mapping) else {}
    return {
        "schema_version": str(context.get("schema_version") or SHARED_MEMO_CONTEXT_SCHEMA_VERSION),
        "user_query": _truncate(str(context.get("user_query") or ""), 240),
        "response_language": {
            "language": str(response_language.get("language") or ""),
            "user_facing_text_language": str(response_language.get("user_facing_text_language") or ""),
            "preserve_identifiers": _string_list(response_language.get("preserve_identifiers"))[:8],
        },
        "execution_mode": str(context.get("execution_mode") or ""),
        "focus_tickers": _string_list(context.get("focus_tickers"))[:8],
        "search_scope_tickers": _string_list(context.get("search_scope_tickers"))[:12],
        "coverage": dict(context.get("coverage") or {}) if isinstance(context.get("coverage"), Mapping) else {},
        "source_boundaries": dict(context.get("source_boundaries") or {}) if isinstance(context.get("source_boundaries"), Mapping) else {},
        "specialist_routes": dict(context.get("specialist_routes") or {}) if isinstance(context.get("specialist_routes"), Mapping) else {},
        "claim_card_stats": dict(context.get("claim_card_stats") or {}) if isinstance(context.get("claim_card_stats"), Mapping) else {},
        "memo_profile": dict(context.get("memo_profile") or {}) if isinstance(context.get("memo_profile"), Mapping) else {},
        "context_digest": str(context.get("context_digest") or ""),
    }


def _select_response_language(
    state: Mapping[str, Any],
    *,
    activation: Mapping[str, Any],
    query_contract: Mapping[str, Any],
) -> dict[str, Any]:
    candidates = [
        ("state.response_language", state.get("response_language")),
        ("state.output_language", state.get("output_language")),
        ("activation.response_language", activation.get("response_language")),
        ("activation.output_language", activation.get("output_language")),
        ("query_contract.response_language", query_contract.get("response_language")),
        ("query_contract.output_language", query_contract.get("output_language")),
    ]
    multi_agent_context = state.get("multi_agent_context") if isinstance(state.get("multi_agent_context"), Mapping) else {}
    candidates.append(("multi_agent_context.response_language", multi_agent_context.get("response_language")))
    for source, candidate in candidates:
        language = _normalize_response_language(candidate)
        if language:
            return _response_language_dict(language, source=source)
    user_query = str(state.get("user_query") or query_contract.get("raw_query") or "")
    inferred = "zh-CN" if _contains_cjk(user_query) else "en-US"
    return _response_language_dict(inferred, source="inferred_from_user_query")


def _response_language_dict(language: str, *, source: str) -> dict[str, Any]:
    normalized = _normalize_response_language(language) or "en-US"
    return {
        "schema_version": RESPONSE_LANGUAGE_SCHEMA_VERSION,
        "language": normalized,
        "source": str(source or ""),
        "user_facing_text_language": "Simplified Chinese" if normalized == "zh-CN" else "English",
        "preserve_identifiers": ["tickers", "metric_ids", "evidence_refs", "form_names", "numbers", "units"],
        "policy": "explicit_contract_or_user_query_language_v0_1",
    }


def _response_language_from_context(value: Any) -> str:
    if isinstance(value, Mapping):
        return _normalize_response_language(value.get("language")) or "en-US"
    return _normalize_response_language(value) or "en-US"


def _normalize_response_language(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = raw.lower().replace("_", "-")
    if normalized in {"zh", "zh-cn", "zh-hans", "chinese", "simplified-chinese", "simplified chinese", "中文", "简体中文"}:
        return "zh-CN"
    if normalized in {"en", "en-us", "en-gb", "english", "英文"}:
        return "en-US"
    return ""


def _contains_cjk(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", str(value or "")))


def _select_memo_profile(
    state: Mapping[str, Any],
    *,
    shared_context: Mapping[str, Any],
    judgment: Mapping[str, Any],
) -> MemoProfileSpec:
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    execution_mode = str(activation.get("execution_mode") or shared_context.get("execution_mode") or "").strip()
    coverage = shared_context.get("coverage") if isinstance(shared_context.get("coverage"), Mapping) else {}
    stats = shared_context.get("claim_card_stats") if isinstance(shared_context.get("claim_card_stats"), Mapping) else {}
    thesis_pack = judgment.get("memo_thesis_pack") if isinstance(judgment.get("memo_thesis_pack"), Mapping) else {}
    thesis_plan = judgment.get("memo_thesis_plan") if isinstance(judgment.get("memo_thesis_plan"), Mapping) else {}
    supported_claim_count = int(stats.get("supported_claim_count") or len(judgment.get("supported_claims") or []))
    memo_ready_count = int(stats.get("memo_ready_claim_count") or 0)
    supported_slot_count = int(stats.get("memo_slot_supported_count") or stats.get("supported_memo_slot_count") or 0)
    source_family_count = _supported_source_family_count(judgment)
    pack_ready = str(thesis_pack.get("status") or thesis_plan.get("status") or "") == "ready"
    bounded = bool(coverage.get("bounded_answer_allowed") or state.get("bounded_answer_allowed"))
    missing_requirements = int(coverage.get("missing_requirement_count") or 0)

    reason_parts: list[str] = []
    if supported_claim_count < 3 or memo_ready_count < 2:
        reason_parts.append("compact_due_to_sparse_claim_cards")
        return _profile_with_reason("compact", reason_parts)
    if execution_mode in {"deterministic_lookup", "focused_answer"}:
        reason_parts.append(f"compact_for_{execution_mode or 'focused'}")
        return _profile_with_reason("compact", reason_parts)
    if execution_mode == "deep_research":
        if pack_ready and supported_claim_count >= 6 and memo_ready_count >= 4 and supported_slot_count >= 3 and source_family_count >= 2:
            reason_parts.append("deep_research_ready_claim_density_and_source_diversity")
            return _profile_with_reason("deep_research", reason_parts)
        if pack_ready and supported_claim_count >= 4 and source_family_count >= 2:
            reason_parts.append("deep_research_but_evidence_density_supports_expanded")
            return _profile_with_reason("expanded", reason_parts)
        reason_parts.append("deep_research_but_thin_evidence_uses_standard")
        return _profile_with_reason("standard", reason_parts)
    if execution_mode == "standard_memo":
        if pack_ready and supported_claim_count >= 5 and memo_ready_count >= 3 and source_family_count >= 2 and missing_requirements <= 4:
            reason_parts.append("standard_case_with_enough_claim_density_for_expanded")
            return _profile_with_reason("expanded", reason_parts)
        if pack_ready and supported_claim_count >= 3:
            reason_parts.append("standard_case_with_ready_thesis_pack")
            return _profile_with_reason("standard", reason_parts)
    if pack_ready and supported_claim_count >= 4 and source_family_count >= 2:
        reason_parts.append("fallback_standard_ready_thesis_pack")
        return _profile_with_reason("standard", reason_parts)
    reason_parts.append("default_compact")
    return _profile_with_reason("compact", reason_parts)


def _profile_with_reason(profile: str, reason_parts: list[str]) -> MemoProfileSpec:
    spec = MEMO_PROFILE_SPECS.get(profile, MEMO_PROFILE_SPECS["compact"])
    return MemoProfileSpec(**{**spec.__dict__, "profile": spec.profile})


def _memo_profile_spec_from_name(value: Any) -> MemoProfileSpec:
    return MEMO_PROFILE_SPECS.get(str(value or "").strip(), MEMO_PROFILE_SPECS["compact"])


def _memo_profile_dict(spec: MemoProfileSpec) -> dict[str, Any]:
    return {
        "schema_version": MEMO_PROFILE_SCHEMA_VERSION,
        "profile": spec.profile,
        "direct_answer_max_chars": spec.direct_answer_max_chars,
        "direct_answer_min_chars": spec.direct_answer_min_chars,
        "memo_claims_min_when_thesis_ready": spec.memo_claims_min_when_thesis_ready,
        "memo_claims_max": spec.memo_claims_max,
        "memo_claim_max_chars": spec.memo_claim_max_chars,
        "caveats_max": spec.caveats_max,
        "unsupported_claims_excluded_max": spec.unsupported_claims_excluded_max,
        "source_boundary_notes_max": spec.source_boundary_notes_max,
        "supported_claim_cap_with_thesis_pack": spec.supported_claim_cap_with_thesis_pack,
        "rendered_claim_max": spec.rendered_claim_max,
    }


def _supported_source_family_count(judgment: Mapping[str, Any]) -> int:
    families = {
        family
        for claim in judgment.get("supported_claims") or []
        if isinstance(claim, Mapping)
        for family in _string_list(claim.get("source_families") or claim.get("source_family"))
        if family
    }
    return len(families)


def _memo_messages(
    state: Mapping[str, Any],
    *,
    prior_failure: Mapping[str, Any] | None,
    prior_content: str,
) -> list[dict[str, str]]:
    shared_context = build_shared_memo_context(state)
    memo_profile = _memo_profile_spec_from_name(
        ((shared_context.get("memo_profile") or {}) if isinstance(shared_context.get("memo_profile"), Mapping) else {}).get("profile")
    )
    response_language = _response_language_from_context(shared_context.get("response_language"))
    response_language_name = "Simplified Chinese" if response_language == "zh-CN" else "English"
    judgment = _compact_judgment_for_memo(
        state.get("verified_judgment_plan") or state.get("judgment_plan") or {},
        memo_profile=memo_profile,
    )
    contract = _memo_output_contract(memo_profile)
    user_payload = {
        "shared_memo_context": shared_context,
        "user_query": state.get("user_query") or "",
        "verified_judgment_plan": judgment,
        "specialist_verification": _compact_specialist_verification(state.get("specialist_verification") or {}),
        "memo_input_contract": {
            "allowed_views": ["shared_memo_context", "verified_judgment_plan", "specialist_verification"],
            "raw_rows_consumed": False,
            "tool_calls_allowed": False,
            "response_language": response_language,
            "projection_policy": "memo_writer_v0_6_profiled_thesis_led_claim_cards",
        },
        "memo_output_contract": contract,
    }
    user = (
        "Write one MemoDraft JSON object from compact verified ClaimCard inputs only. "
        "Use shared_memo_context only for scope, coverage, Specialist route status, and source-boundary framing, never as factual evidence. "
        f"Set response_language.language exactly to {response_language}; user-facing prose must be {response_language_name}. "
        "For zh-CN, translate/synthesize direct_answer, memo_claims.claim, caveats, source_boundary_notes, investment_implications, what_would_change_view, monitoring_items, and evidence_gaps_but_actionable into Simplified Chinese; keep tickers, metric IDs, form names, numbers, units, claim_id, and evidence_refs unchanged. "
        "For zh-CN, any memo_claim.claim that is mostly English prose is invalid; do not quote English ClaimCard text, do not add 'original text' wrappers, and do not say the English text is preserved for traceability. "
        "Use memo_thesis_pack as the primary writing brief, memo_thesis_plan as the order, and memo_outline only as fallback. "
        "Write a thesis-led memo paragraph, not a row recap or schema recap; do not copy internal phrases such as 'Synthesized thesis', 'ClaimCard', pipe-delimited joined claims, or repeated claim text into direct_answer. "
        "Preserve numeric values exactly as written; do not recalculate, invent, round, or change units. "
        "Do not request tools, consume raw rows, or add facts beyond verified claim cards.\n\n"
        f"Profile caps: memo_profile={memo_profile.profile}; direct_answer should be {memo_profile.direct_answer_min_chars}-{memo_profile.direct_answer_max_chars} characters when supported and direct_answer <= {memo_profile.direct_answer_max_chars} characters; "
        f"memo_claims {memo_profile.memo_claims_min_when_thesis_ready}-{memo_profile.memo_claims_max} when memo_thesis_pack or memo_thesis_plan is ready; each memo_claim.claim <= {memo_profile.memo_claim_max_chars} characters; "
        f"caveats <= {memo_profile.caveats_max}; unsupported_claims_excluded <= {memo_profile.unsupported_claims_excluded_max}; source_boundary_notes <= {memo_profile.source_boundary_notes_max}. "
        "For standard/expanded/deep_research, include non-empty investment_implications, what_would_change_view, and monitoring_items. "
        "Set memo_generation_policy exactly to thesis_led_claim_cards_v0_1. "
        "Emit compact memo_thesis_plan only; do_not_emit_supported_claims=true; do not emit memo_thesis_pack, memo_outline, analysis traces, source tables, or copied judgment_plan. "
        "Emit memo_claims synthesized from supported claims with claim_id and evidence_refs copied exactly. Return JSON only.\n\n"
        f"Input JSON:\n{_json_for_prompt(user_payload)}"
    )
    if prior_failure:
        cleaned_failure = _clean_for_prompt(prior_failure)
        is_length_or_parse_failure = str(prior_failure.get("type") or "") in {"json_parse_failed", "model_output_truncated"}
        repair_payload = _compact_memo_payload_for_repair(user_payload, length_repair=is_length_or_parse_failure)
        if is_length_or_parse_failure:
            user = (
                "Repair the previous MemoDraft response. The prior output was not a complete valid compact JSON object.\n"
                f"Diagnostic:\n{_json_for_prompt(cleaned_failure, sort_keys=True)}\n\n"
                f"Use this compact input JSON only:\n{_json_for_prompt(repair_payload)}\n\n"
                "Return exactly one minimal MemoDraft JSON object. "
                f"memo_profile must stay {memo_profile.profile}. "
                f"response_language.language must stay {response_language}; user-facing prose must be {response_language_name}. "
                f"direct_answer <= {min(memo_profile.direct_answer_max_chars, 700)} characters, "
                f"memo_claims 3-{min(memo_profile.memo_claims_max, MEMO_LENGTH_REPAIR_SUPPORTED_CLAIM_CAP)} when available, "
                "caveats <= 3, unsupported_claims_excluded <= 2, source_boundary_notes <= 3. "
                "Use only claim_id/evidence_refs present in verified_judgment_plan.supported_claims and do not add optional fields beyond the required shape. "
                "Set memo_generation_policy exactly to thesis_led_claim_cards_v0_1. "
                "Preserve numeric values exactly from ClaimCards; do not round or change units. "
                "For zh-CN, translate or synthesize every user-facing claim/section into Simplified Chinese; copy only claim_id, evidence_refs, tickers, metric IDs, numbers, and units. "
                "For zh-CN, do not quote English claim text or wrap it as original/source text; rewrite the investment meaning in Chinese. "
                "Do not copy internal phrases like 'Synthesized thesis' or 'ClaimCards' into direct_answer, do not use pipe-delimited claim concatenation, and do not repeat the same sentence twice. "
                "For standard/expanded/deep_research, include non-empty investment_implications, what_would_change_view, and monitoring_items. "
                "Do not emit supported_claims, memo_thesis_pack, or memo_outline. No markdown, no prose, no row-by-row recap."
            )
        else:
            user = (
                "Repair the previous MemoDraft response using the compact verified judgment only.\n"
                f"Diagnostic:\n{_json_for_prompt(cleaned_failure, sort_keys=True)}\n\n"
                f"Use this compact input JSON only:\n{_json_for_prompt(repair_payload)}\n\n"
                f"Previous output excerpt:\n{_truncate(prior_content, 500)}\n\n"
                "Return one shorter corrected MemoDraft JSON object only. "
                f"memo_profile must stay {memo_profile.profile}. "
                f"response_language.language must stay {response_language}; user-facing prose must be {response_language_name}. "
                "Rewrite direct_answer as a natural user-facing investment paragraph without internal labels or pipe-delimited claim joins. "
                "For zh-CN, translate or synthesize every user-facing claim/section into Simplified Chinese; copy only claim_id, evidence_refs, tickers, metric IDs, numbers, and units. "
                "For zh-CN, do not quote English claim text or wrap it as original/source text; rewrite the investment meaning in Chinese. "
                "Remove repeated sentences, and for standard/expanded/deep_research include non-empty investment_implications, what_would_change_view, and monitoring_items. "
                "Set memo_generation_policy exactly to thesis_led_claim_cards_v0_1, preserve numeric values exactly, and do not emit memo_thesis_pack or memo_outline."
            )
    return [
        {"role": "system", "content": _memo_system_prompt()},
        {"role": "user", "content": user},
    ]


def _memo_output_contract(profile: MemoProfileSpec) -> dict[str, Any]:
    return {
        **_memo_profile_dict(profile),
        "memo_generation_policy": "thesis_led_claim_cards_v0_1",
        "response_language_shape": {
            "schema_version": RESPONSE_LANGUAGE_SCHEMA_VERSION,
            "language": "zh-CN | en-US",
            "source": "memo_writer_context",
        },
        "memo_thesis_plan_shape": [
            "schema_version",
            "status",
            "primary_thesis_claim_id",
            "primary_thesis",
            "thesis_direction",
        ],
        "do_not_emit_supported_claims": True,
        "do_not_emit_memo_thesis_pack": True,
        "do_not_emit_memo_outline": True,
        "must_copy_claim_id_and_evidence_refs_from_input": True,
        "allowed_top_level_fields": [
            "schema_version",
            "answer_status",
            "direct_answer",
            "response_language",
            "memo_profile",
            "memo_claims",
            "investment_implications",
            "what_would_change_view",
            "monitoring_items",
            "evidence_gaps_but_actionable",
            "caveats",
            "unsupported_claims_excluded",
            "source_boundary_notes",
            "memo_thesis_plan",
            "source_boundary",
            "raw_rows_consumed",
            "tool_calls_requested",
            "memo_generation_policy",
        ],
    }


def _compact_judgment_for_memo(value: Any, *, memo_profile: MemoProfileSpec | None = None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    profile = memo_profile or MEMO_PROFILE_SPECS["compact"]
    supported = [_compact_claim_card(item) for item in value.get("supported_claims") or [] if isinstance(item, Mapping)]
    thesis_pack = _compact_memo_thesis_pack(value.get("memo_thesis_pack") or {})
    supported_claim_cap = profile.supported_claim_cap_with_thesis_pack if thesis_pack else MEMO_SUPPORTED_CLAIM_CAP
    memo_outline_cap = 4 if thesis_pack and profile.profile == "compact" else 8
    unsupported = [
        {
            "agent_id": str(item.get("agent_id") or ""),
            "claim": _truncate(str(item.get("claim") or ""), 220),
            "reason": _truncate(str(item.get("reason") or ""), 160),
        }
        for item in value.get("unsupported_claims") or []
        if isinstance(item, Mapping)
    ]
    conflicts = [
        {
            "agent_id": str(item.get("agent_id") or ""),
            "claim": _truncate(str(item.get("claim") or ""), 220),
            "reason": _truncate(str(item.get("reason") or ""), 180),
        }
        for item in value.get("conflicts") or []
        if isinstance(item, Mapping)
    ]
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "status": str(value.get("status") or ""),
        "supported_claims": _select_memo_supported_claims(supported, value.get("memo_outline") or [], max_claims=supported_claim_cap),
        "unsupported_claims": unsupported[:MEMO_UNSUPPORTED_CLAIM_CAP],
        "conflicts": conflicts[:MEMO_CONFLICT_CAP],
        "source_boundary_notes": _compact_source_boundary_notes(value.get("source_boundary_notes") or []),
        "memo_outline": [dict(item) for item in value.get("memo_outline") or [] if isinstance(item, Mapping)][:memo_outline_cap],
        "memo_thesis_plan": _compact_memo_thesis_plan(value.get("memo_thesis_plan") or {}),
        "memo_thesis_pack": thesis_pack,
        "claim_card_stats": dict(value.get("claim_card_stats") or {}),
        "memo_constraints": _compact_memo_constraints(value.get("memo_constraints") or {}),
        "memo_writer_allowed": bool(value.get("memo_writer_allowed", True)),
        "aggregation_policy": str(value.get("aggregation_policy") or ""),
    }


def _compact_memo_payload_for_repair(payload: Mapping[str, Any], *, length_repair: bool = False) -> dict[str, Any]:
    judgment = payload.get("verified_judgment_plan") if isinstance(payload.get("verified_judgment_plan"), Mapping) else {}
    compact_judgment = dict(judgment)
    thesis_pack = _compact_memo_thesis_pack(judgment.get("memo_thesis_pack") or {})
    output_contract = payload.get("memo_output_contract") if isinstance(payload.get("memo_output_contract"), Mapping) else {}
    shared_context = payload.get("shared_memo_context") if isinstance(payload.get("shared_memo_context"), Mapping) else {}
    response_language = (
        dict(shared_context.get("response_language") or {}) if isinstance(shared_context.get("response_language"), Mapping) else {}
    )
    profile = _memo_profile_spec_from_name(output_contract.get("profile"))
    supported_claim_cap = (
        MEMO_LENGTH_REPAIR_SUPPORTED_CLAIM_CAP
        if length_repair
        else profile.supported_claim_cap_with_thesis_pack if thesis_pack else MEMO_SUPPORTED_CLAIM_CAP
    )
    compact_judgment["supported_claims"] = _select_memo_supported_claims(
        [dict(item) for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)],
        judgment.get("memo_outline") or [],
        max_claims=supported_claim_cap,
    )
    compact_judgment["unsupported_claims"] = [
        dict(item) for item in judgment.get("unsupported_claims") or [] if isinstance(item, Mapping)
    ][:MEMO_UNSUPPORTED_CLAIM_CAP]
    compact_judgment["conflicts"] = [dict(item) for item in judgment.get("conflicts") or [] if isinstance(item, Mapping)][:MEMO_CONFLICT_CAP]
    compact_judgment["source_boundary_notes"] = [dict(item) for item in judgment.get("source_boundary_notes") or [] if isinstance(item, Mapping)][:4]
    compact_judgment["memo_thesis_pack"] = {} if length_repair else thesis_pack
    if length_repair:
        compact_judgment["memo_outline"] = [
            dict(item) for item in judgment.get("memo_outline") or [] if isinstance(item, Mapping)
        ][:4]
        compact_judgment["memo_constraints"] = _compact_memo_constraints(judgment.get("memo_constraints") or {})
    return {
        "user_query": _truncate(str(payload.get("user_query") or ""), 240),
        "response_language": response_language,
        "verified_judgment_plan": compact_judgment,
        "specialist_verification": payload.get("specialist_verification") or {},
        "memo_input_contract": payload.get("memo_input_contract") or {},
        "memo_output_contract": output_contract,
        "required_shape": {
            "schema_version": "sec_agent_multi_agent_memo_draft_v0.1",
            "answer_status": "draft | blocked_by_specialist_verification",
            "direct_answer": "compact bounded answer",
            "response_language": response_language or {"language": "zh-CN | en-US"},
            "memo_profile": {"profile": profile.profile},
            "memo_claims": [],
            "investment_implications": [],
            "what_would_change_view": [],
            "monitoring_items": [],
            "evidence_gaps_but_actionable": [],
            "caveats": [],
            "unsupported_claims_excluded": [],
            "source_boundary_notes": [],
            "memo_thesis_plan": {
                "schema_version": "",
                "status": "",
                "primary_thesis_claim_id": "",
                "primary_thesis": "",
                "thesis_direction": "",
            },
            "raw_rows_consumed": False,
            "tool_calls_requested": [],
            "memo_generation_policy": "thesis_led_claim_cards_v0_1",
        },
    }


def _deterministic_memo_salvage(
    judgment: Mapping[str, Any],
    *,
    specialist_verification: Mapping[str, Any],
    memo_profile: MemoProfileSpec,
    response_language: str,
    model_calls: list[dict[str, Any]],
    last_failure: Mapping[str, Any],
) -> dict[str, Any]:
    selected_claims = _select_memo_supported_claims(
        [_compact_claim_card(item) for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)],
        judgment.get("memo_outline") or [],
        max_claims=min(MEMO_SALVAGE_SUPPORTED_CLAIM_CAP, memo_profile.memo_claims_max),
    )
    salvage_judgment = {
        **dict(judgment),
        "supported_claims": selected_claims,
        "unsupported_claims": [dict(item) for item in judgment.get("unsupported_claims") or [] if isinstance(item, Mapping)][
            : memo_profile.unsupported_claims_excluded_max
        ],
        "conflicts": [dict(item) for item in judgment.get("conflicts") or [] if isinstance(item, Mapping)][: memo_profile.caveats_max],
        "source_boundary_notes": [
            dict(item) for item in judgment.get("source_boundary_notes") or [] if isinstance(item, Mapping)
        ][: memo_profile.source_boundary_notes_max],
    }
    draft = build_multi_agent_memo_draft(salvage_judgment, specialist_verification=specialist_verification)
    draft["direct_answer"] = _salvage_direct_answer(salvage_judgment, selected_claims, response_language=response_language)
    draft["memo_claims"] = [
        _salvage_memo_claim_from_supported_claim(item, response_language=response_language)
        for item in selected_claims[: min(MEMO_SALVAGE_SUPPORTED_CLAIM_CAP, memo_profile.memo_claims_max)]
    ]
    draft["investment_implications"] = _salvage_action_items(
        selected_claims,
        response_language=response_language,
        kind="investment_implications",
        max_items=3,
    )
    draft["what_would_change_view"] = _salvage_action_items(
        selected_claims,
        response_language=response_language,
        kind="what_would_change_view",
        max_items=2,
    )
    draft["monitoring_items"] = _salvage_action_items(
        selected_claims,
        response_language=response_language,
        kind="monitoring_items",
        max_items=3,
    )
    draft["evidence_gaps_but_actionable"] = _salvage_action_items(
        selected_claims,
        response_language=response_language,
        kind="evidence_gaps",
        max_items=2,
    )
    draft["memo_generation_policy"] = "thesis_led_claim_cards_v0_1"
    draft["llm_route_source"] = f"{MEMO_ROUTE_SOURCE}+deterministic_salvage"
    normalized = _normalize_memo_llm_output(
        draft,
        salvage_judgment,
        memo_profile=memo_profile,
        response_language=response_language,
    )
    normalized["memo_writer_diagnostics"] = {
        **dict(normalized.get("memo_writer_diagnostics") or {}),
        "deterministic_salvage_used": True,
        "salvage_reason": _format_failure_reason(last_failure),
        "salvage_claim_count": len(normalized.get("memo_claims") or []),
        "salvage_policy": "length_failure_claim_card_salvage_v0_1",
    }
    normalized["model_diagnostics"] = _aggregate_model_calls(model_calls)
    normalized["llm_route_source"] = f"{MEMO_ROUTE_SOURCE}+deterministic_salvage"
    return normalized


def _salvage_memo_claim_from_supported_claim(item: Mapping[str, Any], *, response_language: str) -> dict[str, Any]:
    row = dict(item)
    if response_language == "zh-CN" and _needs_zh_wrapper(row.get("claim")):
        row["claim"] = _zh_salvage_claim_summary(row)
        row["response_language_normalized_user_text"] = True
    return row


def _zh_salvage_claim_summary(item: Mapping[str, Any]) -> str:
    tickers = "、".join(_string_list(item.get("ticker_scope"))[:4]) or "相关公司"
    metrics = "、".join(_string_list(item.get("metric_scope"))[:4])
    slot = _zh_memo_slot_label(str(item.get("memo_slot") or ""))
    direction = _zh_direction_label(str(item.get("direction") or ""))
    materiality = _zh_materiality_label(str(item.get("materiality") or ""))
    numbers = _numeric_snippets_for_zh_summary(str(item.get("claim") or ""))
    parts = [f"{tickers} 的{slot}证据形成一条{direction}{materiality}论据"]
    if metrics:
        parts.append(f"涉及 {metrics}")
    if numbers:
        parts.append(f"关键数值包括 {'、'.join(numbers)}")
    refs = _string_list(item.get("evidence_refs") or item.get("refs"))[:3]
    if refs:
        parts.append(f"证据引用为 {', '.join(refs)}")
    parts.append("该表述仅限已验证 ClaimCard 与引用证据范围，不外推未证实事实")
    return "；".join(parts) + "。"


def _zh_memo_slot_label(value: str) -> str:
    labels = {
        "thesis": "投资主线",
        "fundamentals": "基本面",
        "fundamental": "基本面",
        "industry_relationship": "行业/关系",
        "market_valuation": "市场/估值",
        "risk_counterevidence": "风险/反证",
    }
    return labels.get(str(value or "").strip(), "投资判断")


def _zh_direction_label(value: str) -> str:
    labels = {
        "positive": "正向",
        "negative": "负向",
        "mixed": "多空混合",
        "neutral": "中性",
    }
    return labels.get(str(value or "").strip().lower(), "有边界")


def _zh_materiality_label(value: str) -> str:
    labels = {
        "high": "、高重要性",
        "medium": "、中等重要性",
        "low": "、低重要性",
    }
    return labels.get(str(value or "").strip().lower(), "")


def _numeric_snippets_for_zh_summary(text: str) -> list[str]:
    snippets: list[str] = []
    seen: set[str] = set()
    pattern = re.compile(
        r"(?<![A-Za-z0-9])[-+]?\$?\d[\d,]*(?:\.\d+)?\s*(?:%|B|M|bn|million|billion|亿美元|百万美元)?",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(str(text or "")):
        token = match.group(0).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        snippets.append(token)
        if len(snippets) >= 4:
            break
    return snippets


def _salvage_direct_answer(
    judgment: Mapping[str, Any],
    selected_claims: list[dict[str, Any]],
    *,
    response_language: str,
) -> str:
    plan = judgment.get("memo_thesis_plan") if isinstance(judgment.get("memo_thesis_plan"), Mapping) else {}
    thesis = _clean_internal_thesis_text(str(plan.get("primary_thesis") or "")).strip()
    slots = sorted({str(item.get("memo_slot") or "").strip() for item in selected_claims if str(item.get("memo_slot") or "").strip()})
    slot_text = ", ".join(slots[:4])
    if response_language == "zh-CN":
        if thesis and _contains_cjk(thesis):
            return _truncate(thesis, 900)
        return _truncate(
            "基于已验证证据，当前可以形成一个有边界的投研结论："
            f"{'、'.join(slots[:4]) if slots else '主要投资论据'}已有可引用支撑；"
            "未被引用证据覆盖的外部传导、估值重定价或新增风险不能外推为未验证事实。",
            900,
        )
    if thesis:
        return _truncate(thesis, 900)
    return _truncate(
        "The verified judgment plan supports a bounded investment memo using the selected claim cards. "
        f"The strongest available slots are {slot_text or 'the verified business drivers'}; unverified customer, order, valuation, or risk links remain outside the memo boundary.",
        900,
    )


def _salvage_action_items(
    selected_claims: list[dict[str, Any]],
    *,
    response_language: str,
    kind: str,
    max_items: int,
) -> list[dict[str, Any]]:
    refs = _string_list(selected_claims[0].get("evidence_refs"))[:2] if selected_claims else []
    claim_id = str(selected_claims[0].get("claim_id") or "") if selected_claims else ""
    if response_language == "zh-CN":
        templates = {
            "investment_implications": "把已验证的高权重论据作为当前判断核心，仓位或排序需受证据边界约束。",
            "what_would_change_view": "若后续披露无法验证当前关键驱动，或出现相反的订单、利润率、估值或风险证据，应下调结论强度。",
            "monitoring_items": "继续跟踪下一轮财报、订单/积压、利润率、资本开支、估值和关系图谱中对应节点的证据更新。",
            "evidence_gaps": "当前仍有部分传导链或外部确认缺口，但已有证据足以形成带边界的研究 memo。",
        }
    else:
        templates = {
            "investment_implications": "Use the highest-ranked verified claims as the core view while sizing confidence to the evidence boundary.",
            "what_would_change_view": "Reduce confidence if the next filings or market/industry evidence fail to confirm the key driver, valuation, or risk link.",
            "monitoring_items": "Track the next filing, backlog/order, margin, capex, valuation, and relationship-graph updates tied to the cited claims.",
            "evidence_gaps": "Some transmission links still need external confirmation, but the verified cards support a bounded research memo.",
        }
    items = [{"text": templates.get(kind, templates["investment_implications"]), "claim_id": claim_id, "evidence_refs": refs}]
    for claim in selected_claims[1:max_items]:
        claim_refs = _string_list(claim.get("evidence_refs"))[:2]
        if not claim_refs:
            continue
        if response_language == "zh-CN":
            items.append(
                {
                    "text": "用该补充论据交叉验证核心判断，不把它扩展为未证实的新事实。",
                    "claim_id": str(claim.get("claim_id") or ""),
                    "evidence_refs": claim_refs,
                }
            )
        else:
            items.append(
                {
                    "text": "Use this supporting claim as a cross-check without extending beyond the cited source boundary.",
                    "claim_id": str(claim.get("claim_id") or ""),
                    "evidence_refs": claim_refs,
                }
            )
        if len(items) >= max_items:
            break
    return items[:max_items]


def _clean_internal_thesis_text(value: str) -> str:
    cleaned = str(value or "").replace("Synthesized thesis from bounded ClaimCards: ", "").strip()
    cleaned = cleaned.replace("bounded ClaimCards", "verified evidence").replace("ClaimCards", "claim cards")
    return cleaned.replace(" | ", " ")


def _compact_claim_card(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": str(item.get("claim_id") or ""),
        "agent_id": str(item.get("agent_id") or ""),
        "claim": _truncate(str(item.get("claim") or ""), 150),
        "claim_type": str(item.get("claim_type") or ""),
        "ticker_scope": _string_list(item.get("ticker_scope"))[:6],
        "metric_scope": _string_list(item.get("metric_scope"))[:6],
        "memo_slot": str(item.get("memo_slot") or ""),
        "materiality": str(item.get("materiality") or ""),
        "direction": str(item.get("direction") or ""),
        "evidence_refs": _string_list(item.get("evidence_refs") or item.get("refs"))[:3],
        "source_families": _string_list(item.get("source_families") or item.get("source_family"))[:5],
        "confidence": str(item.get("confidence") or ""),
        "claim_rank_score": int(item.get("claim_rank_score") or 0),
        "claim_rank_bucket": str(item.get("claim_rank_bucket") or ""),
        "caveats": [_truncate(str(part), 100) for part in _string_list(item.get("caveats"))[:1]],
        "missing_confirmations": [_truncate(str(part), 100) for part in _string_list(item.get("missing_confirmations"))[:1]],
    }


def _compact_memo_thesis_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    sections = []
    for row in value.get("section_sequence") or []:
        if not isinstance(row, Mapping):
            continue
        sections.append(
            {
                "memo_slot": str(row.get("memo_slot") or ""),
                "status": str(row.get("status") or ""),
                "objective": _truncate(str(row.get("objective") or ""), 160),
                "claim_ids": _string_list(row.get("claim_ids"))[:3],
                "primary_evidence_refs": _string_list(row.get("primary_evidence_refs"))[:4],
            }
        )
        if len(sections) >= 6:
            break
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "status": str(value.get("status") or ""),
        "primary_thesis_claim_id": str(value.get("primary_thesis_claim_id") or ""),
        "primary_thesis": _truncate(str(value.get("primary_thesis") or ""), 260),
        "thesis_direction": str(value.get("thesis_direction") or ""),
        "supporting_claim_ids": _string_list(value.get("supporting_claim_ids"))[:8],
        "risk_or_counter_claim_ids": _string_list(value.get("risk_or_counter_claim_ids"))[:4],
        "section_sequence": sections,
        "plan_policy": str(value.get("plan_policy") or ""),
    }


def _compact_memo_thesis_pack(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        return {}
    drivers = []
    for row in value.get("supporting_drivers") or []:
        if not isinstance(row, Mapping):
            continue
        driver = row.get("driver") if isinstance(row.get("driver"), Mapping) else {}
        drivers.append(
            {
                "memo_slot": str(row.get("memo_slot") or ""),
                "section_title": _truncate(str(row.get("section_title") or ""), 80),
                "driver": _compact_pack_claim(driver),
                "supporting_claim_count": int(row.get("supporting_claim_count") or 0),
            }
        )
        if len(drivers) >= 3:
            break
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "status": str(value.get("status") or ""),
        "core_thesis": _compact_pack_claim(value.get("core_thesis") if isinstance(value.get("core_thesis"), Mapping) else {}),
        "supporting_drivers": drivers,
        "counterarguments": [
            _compact_pack_claim(item)
            for item in value.get("counterarguments") or []
            if isinstance(item, Mapping)
        ][:2],
        "watch_items": [
            {
                "type": str(item.get("type") or ""),
                "claim_id": str(item.get("claim_id") or ""),
                "text": _truncate(str(item.get("text") or item.get("reason") or ""), 120),
            }
            for item in value.get("watch_items") or []
            if isinstance(item, Mapping)
        ][:4],
        "evidence_strength_map": _compact_string_mapping(value.get("evidence_strength_map") or {}, max_items=4, max_value_chars=70),
        "source_boundary": _truncate(str(value.get("source_boundary") or ""), 160),
        "source_claim_refs": _string_list(value.get("source_claim_refs"))[:6],
        "pack_policy": str(value.get("pack_policy") or ""),
    }


def _compact_pack_claim(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": str(value.get("claim_id") or ""),
        "memo_slot": str(value.get("memo_slot") or ""),
        "claim": _truncate(str(value.get("claim") or ""), 150),
        "claim_type": str(value.get("claim_type") or ""),
        "direction": str(value.get("direction") or ""),
        "materiality": str(value.get("materiality") or ""),
        "ticker_scope": _string_list(value.get("ticker_scope"))[:6],
        "metric_scope": _string_list(value.get("metric_scope"))[:6],
        "evidence_refs": _string_list(value.get("evidence_refs"))[:3],
        "source_families": _string_list(value.get("source_families"))[:4],
        "caveats": [_truncate(str(part), 90) for part in _string_list(value.get("caveats"))[:1]],
        "missing_confirmations": [
            _truncate(str(part), 90) for part in _string_list(value.get("missing_confirmations"))[:1]
        ],
    }


def _compact_string_mapping(value: Any, *, max_items: int, max_value_chars: int) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    clean: dict[str, str] = {}
    for key, item in list(value.items())[:max_items]:
        clean[str(key)] = _truncate(str(item), max_value_chars)
    return clean


def _select_memo_supported_claims(
    claims: list[dict[str, Any]],
    memo_outline: Any,
    *,
    max_claims: int,
) -> list[dict[str, Any]]:
    if max_claims <= 0:
        return []
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(claim: Mapping[str, Any]) -> None:
        if len(selected) >= max_claims:
            return
        claim_id = str(claim.get("claim_id") or claim.get("claim") or "")
        if not claim_id or claim_id in seen:
            return
        selected.append(dict(claim))
        seen.add(claim_id)

    for claim in claims:
        if str(claim.get("claim_type") or "") == "investment_thesis_synthesis":
            add(claim)
            break

    outline_slots = [
        str(item.get("memo_slot") or "").strip()
        for item in memo_outline
        if isinstance(memo_outline, list) and isinstance(item, Mapping) and str(item.get("status") or "") == "supported"
    ]
    for slot in outline_slots:
        for claim in claims:
            if str(claim.get("memo_slot") or "") == slot:
                add(claim)
                break

    for claim in claims:
        add(claim)
    return selected


def _compact_source_boundary_notes(value: Any) -> list[dict[str, Any]]:
    notes = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, Mapping):
            continue
        notes.append(
            {
                "type": str(item.get("type") or ""),
                "agent_id": str(item.get("agent_id") or ""),
                "source_family": str(item.get("source_family") or ""),
                "reason": _truncate(str(item.get("reason") or item.get("note") or ""), 180),
            }
        )
        if len(notes) >= 8:
            break
    return notes


def _compact_memo_constraints(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    missing_items = value.get("missing_evidence") if isinstance(value.get("missing_evidence"), list) else []
    return {
        "memo_writer_allowed": bool(value.get("memo_writer_allowed", True)),
        "blocked_reasons": _string_list(value.get("blocked_reasons"))[:8],
        "missing_evidence": [
            _truncate(str(item.get("reason") or item.get("type") or item), 180) if isinstance(item, Mapping) else _truncate(str(item), 180)
            for item in missing_items[:8]
        ],
        "source_boundary": _truncate(str(value.get("source_boundary") or ""), 240),
    }


def _compact_specialist_verification(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "status": str(value.get("status") or ""),
        "memo_writer_allowed": bool(value.get("memo_writer_allowed", True)),
        "unsupported_claim_count": int(value.get("unsupported_claim_count") or 0),
        "blocked_reasons": _string_list(value.get("blocked_reasons"))[:8],
        "policy": str(value.get("policy") or ""),
    }


def _compact_memo_data_view(value: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(value or {})
    verified = view.get("verified_summary")
    if isinstance(verified, Mapping):
        clean_verified = dict(verified)
        clean_verified["judgment_plan"] = _compact_judgment_for_memo(clean_verified.get("judgment_plan") or {})
        clean_verified["specialist_verification"] = _compact_specialist_verification(clean_verified.get("specialist_verification") or {})
        view["verified_summary"] = clean_verified
    return view


def _compact_judgment_for_verifier(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    supported = [_compact_claim_card_for_verifier(item) for item in value.get("supported_claims") or [] if isinstance(item, Mapping)]
    unsupported = [
        {
            "agent_id": str(item.get("agent_id") or ""),
            "claim": _truncate(str(item.get("claim") or ""), 180),
            "reason": _truncate(str(item.get("reason") or ""), 120),
        }
        for item in value.get("unsupported_claims") or []
        if isinstance(item, Mapping)
    ][:10]
    conflicts = [
        {
            "agent_id": str(item.get("agent_id") or ""),
            "claim": _truncate(str(item.get("claim") or ""), 180),
            "reason": _truncate(str(item.get("reason") or ""), 120),
        }
        for item in value.get("conflicts") or []
        if isinstance(item, Mapping)
    ][:6]
    evidence_refs = sorted(
        {
            ref
            for item in supported
            for ref in _string_list(item.get("evidence_refs"))
            if ref
        }
    )
    return {
        "supported_claims": supported[:14],
        "supported_claim_count": len(value.get("supported_claims") or []),
        "supported_evidence_refs": evidence_refs[:80],
        "unsupported_claims_excluded": unsupported,
        "conflicts": conflicts,
        "memo_outline": _compact_outline_for_verifier(value.get("memo_outline") or []),
        "claim_card_stats": dict(value.get("claim_card_stats") or {}),
        "source_boundary_notes": _compact_source_boundary_notes(value.get("source_boundary_notes") or []),
        "memo_constraints": _compact_memo_constraints(value.get("memo_constraints") or {}),
    }


def _compact_claim_card_for_verifier(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": str(item.get("claim_id") or ""),
        "agent_id": str(item.get("agent_id") or ""),
        "claim": _truncate(str(item.get("claim") or ""), 180),
        "evidence_refs": _string_list(item.get("evidence_refs") or item.get("refs"))[:8],
        "source_families": _string_list(item.get("source_families") or item.get("source_family"))[:6],
    }


def _compact_outline_for_verifier(value: Any) -> list[dict[str, Any]]:
    rows = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "memo_slot": str(item.get("memo_slot") or ""),
                "status": str(item.get("status") or ""),
                "supported_claim_count": int(item.get("supported_claim_count") or 0),
                "missing_reason": _truncate(str(item.get("missing_reason") or ""), 120),
            }
        )
        if len(rows) >= 8:
            break
    return rows


def _compact_memo_for_verifier(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "answer_status": str(value.get("answer_status") or ""),
        "direct_answer": _truncate(str(value.get("direct_answer") or ""), 1200),
        "response_language": dict(value.get("response_language") or {}) if isinstance(value.get("response_language"), Mapping) else {},
        "memo_profile": dict(value.get("memo_profile") or {}) if isinstance(value.get("memo_profile"), Mapping) else {},
        "memo_claims": [_compact_memo_claim_for_verifier(item) for item in value.get("memo_claims") or [] if isinstance(item, Mapping)][:10],
        "supported_claims": [_compact_memo_claim_for_verifier(item) for item in value.get("supported_claims") or [] if isinstance(item, Mapping)][:10],
        "investment_implications": _compact_loose_items_for_verifier(value.get("investment_implications") or [], max_items=8),
        "what_would_change_view": _compact_loose_items_for_verifier(value.get("what_would_change_view") or [], max_items=6),
        "monitoring_items": _compact_loose_items_for_verifier(value.get("monitoring_items") or [], max_items=6),
        "evidence_gaps_but_actionable": _compact_loose_items_for_verifier(value.get("evidence_gaps_but_actionable") or [], max_items=6),
        "caveats": _compact_loose_items_for_verifier(value.get("caveats") or [], max_items=8),
        "unsupported_claims_excluded": _compact_loose_items_for_verifier(value.get("unsupported_claims_excluded") or [], max_items=8),
        "source_boundary_notes": _compact_loose_items_for_verifier(value.get("source_boundary_notes") or [], max_items=8),
        "consumed_input_views": _string_list(value.get("consumed_input_views"))[:6],
        "raw_rows_consumed": bool(value.get("raw_rows_consumed")),
        "tool_calls_requested": list(value.get("tool_calls_requested") or [])[:3] if isinstance(value.get("tool_calls_requested"), list) else [],
    }


def _compact_memo_claim_for_verifier(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": str(item.get("claim_id") or ""),
        "claim": _truncate(str(item.get("claim") or item.get("text") or ""), 200),
        "evidence_refs": _string_list(item.get("evidence_refs") or item.get("refs"))[:8],
        "source_families": _string_list(item.get("source_families") or item.get("source_family"))[:6],
    }


def _verifier_minimal_projection(
    state: Mapping[str, Any],
    *,
    deterministic: Mapping[str, Any],
) -> dict[str, Any]:
    raw_judgment = state.get("verified_judgment_plan") or state.get("judgment_plan") or {}
    judgment = raw_judgment if isinstance(raw_judgment, Mapping) else {}
    raw_memo = state.get("memo_answer") or {}
    memo = raw_memo if isinstance(raw_memo, Mapping) else {}
    compact_memo = _compact_memo_for_verifier(memo)
    memo_claims = [item for item in compact_memo.get("memo_claims") or [] if isinstance(item, Mapping)]
    memo_claim_ids = {str(item.get("claim_id") or "") for item in memo_claims if str(item.get("claim_id") or "")}
    memo_refs = {
        ref
        for item in memo_claims
        for ref in _string_list(item.get("evidence_refs") or item.get("refs"))
        if ref
    }
    memo_source_families = {
        family
        for item in memo_claims
        for family in _string_list(item.get("source_families") or item.get("source_family"))
        if family
    }
    supported_claims = [item for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)]
    projected_claims = _project_claims_for_verifier(supported_claims, memo_claim_ids=memo_claim_ids, memo_refs=memo_refs)
    projected_refs = {
        ref
        for item in projected_claims
        for ref in _string_list(item.get("evidence_refs") or item.get("refs"))
        if ref
    }
    allowed_refs = sorted(memo_refs | projected_refs)
    projected_source_families = {
        family
        for item in projected_claims
        for family in _string_list(item.get("source_families") or item.get("source_family"))
        if family
    }
    source_boundary_families = memo_source_families | projected_source_families
    source_boundary_notes = _project_source_boundary_notes_for_verifier(
        judgment.get("source_boundary_notes") or memo.get("source_boundary_notes") or [],
        source_families=source_boundary_families,
    )
    projection_stats = {
        "schema_version": VERIFIER_PROJECTION_SCHEMA_VERSION,
        "projection_policy": "final_memo_claims_and_referenced_evidence_only",
        "input_supported_claim_count": len(supported_claims),
        "memo_claim_count": len(memo_claims),
        "projected_claim_count": len(projected_claims),
        "projected_evidence_ref_count": len(allowed_refs),
        "source_boundary_note_count": len(source_boundary_notes),
    }
    return {
        "schema_version": VERIFIER_PROJECTION_SCHEMA_VERSION,
        "projection_policy": "final_memo_claims_and_referenced_evidence_only",
        "memo_answer": compact_memo,
        "memo_claim_ref_inventory": projected_claims,
        "allowed_evidence_refs": allowed_refs[:80],
        "unsupported_claims_excluded": compact_memo.get("unsupported_claims_excluded") or [],
        "source_boundary_notes": source_boundary_notes,
        "memo_constraints": _compact_memo_constraints(judgment.get("memo_constraints") or {}),
        "deterministic_verification": _compact_deterministic_verification(deterministic),
        "projection_stats": projection_stats,
    }


def _project_claims_for_verifier(
    claims: list[Mapping[str, Any]],
    *,
    memo_claim_ids: set[str],
    memo_refs: set[str],
) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in claims:
        refs = set(_string_list(item.get("evidence_refs") or item.get("refs")))
        claim_id = str(item.get("claim_id") or "")
        if memo_claim_ids and claim_id in memo_claim_ids:
            should_keep = True
        else:
            should_keep = bool(memo_refs and refs & memo_refs)
        if not should_keep:
            continue
        key = claim_id or "|".join(sorted(refs)) or str(len(projected))
        if key in seen:
            continue
        projected.append(_compact_claim_card_for_verifier(item))
        seen.add(key)
        if len(projected) >= 8:
            break
    return projected


def _project_source_boundary_notes_for_verifier(value: Any, *, source_families: set[str]) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, Mapping):
            continue
        family = str(item.get("source_family") or "")
        note_type = str(item.get("type") or "")
        severity = str(item.get("severity") or "")
        if source_families and family and family not in source_families and severity != "blocking":
            continue
        if not source_families and family and severity != "blocking":
            continue
        notes.append(
            {
                "type": note_type,
                "severity": severity,
                "agent_id": str(item.get("agent_id") or ""),
                "source_family": family,
                "reason": _truncate(str(item.get("reason") or item.get("note") or ""), 180),
            }
        )
        if len(notes) >= 4:
            break
    return notes


def _compact_loose_items_for_verifier(value: Any, *, max_items: int) -> list[Any]:
    rows = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, Mapping):
            rows.append(
                {
                    str(key): _truncate(str(val), 180) if not isinstance(val, (list, dict)) else _sanitize_nested_for_verifier(val)
                    for key, val in item.items()
                    if str(key) not in {"raw_text", "raw_rows", "retrieved_context"}
                }
            )
        else:
            rows.append(_truncate(str(item), 180))
        if len(rows) >= max_items:
            break
    return rows


def _sanitize_nested_for_verifier(value: Any) -> Any:
    if isinstance(value, list):
        return [_truncate(str(item), 120) if not isinstance(item, (dict, list)) else _sanitize_nested_for_verifier(item) for item in value[:6]]
    if isinstance(value, Mapping):
        return {
            str(key): _truncate(str(item), 120) if not isinstance(item, (dict, list)) else _sanitize_nested_for_verifier(item)
            for key, item in list(value.items())[:8]
            if str(key) not in {"raw_text", "raw_rows", "retrieved_context"}
        }
    return _truncate(str(value), 120)


def _compact_deterministic_verification(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": str(value.get("status") or ""),
        "error_types": [str(item.get("type") or "") for item in value.get("errors") or [] if isinstance(item, Mapping)][:12],
        "warning_types": [str(item.get("type") or "") for item in value.get("warnings") or [] if isinstance(item, Mapping)][:12],
        "bounded_answer_allowed": bool(value.get("bounded_answer_allowed")),
        "repair_instruction": _truncate(str(value.get("repair_instruction") or ""), 240),
    }


def _verifier_messages(
    state: Mapping[str, Any],
    *,
    projection: Mapping[str, Any],
) -> list[dict[str, str]]:
    user_payload = {
        "user_query": state.get("user_query") or "",
        "verifier_projection": dict(projection),
        "bounded_block_policy": (
            "If verifier_projection.memo_answer.answer_status starts with blocked_ and "
            "verifier_projection.deterministic_verification.status is pass, "
            "return pass unless the blocked answer itself introduces unsupported new facts, raw rows, tool calls, "
            "or source-boundary misuse. Do not fail only because a full memo was not produced."
        ),
    }
    return [
        {"role": "system", "content": _verifier_system_prompt()},
        {
            "role": "user",
            "content": (
                "Verify the memo against the minimal memo-claim evidence projection and return one JSON object with "
                "status, errors, warnings, repair_instruction, and bounded_answer_allowed. Do not add new facts.\n\n"
                f"Input JSON:\n{_json_for_prompt(user_payload)}"
            ),
        },
    ]


def _memo_system_prompt() -> str:
    return "\n\n".join(
        [
            "You are the Memo Writer Agent for a SEC investment research multi-agent graph.",
            research_skill_prompt("memo_writer", max_chars=1800),
            "Return exactly one JSON object. Do not wrap it in prose. Do not call tools.",
            "Only consume shared_memo_context, compact verified_judgment_plan, and specialist_verification. Do not include raw rows or retrieval requests.",
            "Follow memo_outline when present; make unsupported and missing evidence visible as limitations instead of filling gaps.",
        ]
    )


def _verifier_system_prompt() -> str:
    return "\n\n".join(
        [
            "You are the Verifier Agent for a SEC investment research multi-agent graph.",
            research_skill_prompt("verifier", max_chars=3000),
            "Return exactly one JSON object. Do not wrap it in prose. Do not call tools.",
            "Do not generate new investment views, expand scope, or request retrieval.",
            "A bounded blocked answer is valid when deterministic verification passes and it does not add new factual claims.",
            "Use the compact evidence ref inventory to check boundaries; do not require raw evidence rows.",
        ]
    )


def _json_candidates(text: str) -> list[str]:
    stripped = text.strip()
    candidates: list[str] = []
    if stripped:
        candidates.append(stripped)
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fence:
        candidates.append(fence.group(1).strip())
    balanced = _first_balanced_json_object(stripped)
    if balanced:
        candidates.append(balanced)
    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            result.append(candidate)
            seen.add(candidate)
    return result


def _first_balanced_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _model_call_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": result.get("status"),
        "provider": result.get("provider"),
        "model": result.get("model"),
        "finish_reason": result.get("finish_reason"),
        "latency_ms": result.get("latency_ms"),
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "total_tokens": result.get("total_tokens"),
        "failure_reason": _truncate(str(result.get("failure_reason") or ""), 500),
        "tool_call_count": len(result.get("tool_calls") or []),
        "transport_attempt_count": result.get("transport_attempt_count"),
        "transport_failures": result.get("transport_failures") or [],
    }


def _aggregate_model_calls(calls: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "call_count": len(calls),
        "provider": next((call.get("provider") for call in calls if call.get("provider")), ""),
        "model": next((call.get("model") for call in calls if call.get("model")), ""),
        "latency_ms": _sum_optional_int(calls, "latency_ms"),
        "input_tokens": _sum_optional_int(calls, "input_tokens"),
        "output_tokens": _sum_optional_int(calls, "output_tokens"),
        "total_tokens": _sum_optional_int(calls, "total_tokens"),
        "finish_reasons": [call.get("finish_reason") for call in calls],
        "calls": calls,
        "raw_response_saved": False,
    }


def _sum_optional_int(rows: list[dict[str, Any]], key: str) -> int | None:
    values = [row.get(key) for row in rows if row.get(key) is not None]
    if not values:
        return None
    return sum(int(value) for value in values)


def _format_failure_reason(failure: Mapping[str, Any]) -> str:
    failure_type = str(failure.get("type") or "unknown_failure")
    if "errors" in failure:
        return f"{failure_type}: {json.dumps(failure.get('errors') or [], ensure_ascii=False)[:700]}"
    return f"{failure_type}: {failure.get('reason') or failure.get('detail') or ''}".strip()


def _is_bounded_block_memo(memo: Mapping[str, Any]) -> bool:
    return str(memo.get("answer_status") or "").startswith("blocked_") or bool(memo.get("bounded_answer_allowed"))


def _filter_soft_verifier_errors(
    errors: list[dict[str, Any]],
    *,
    warning_type: str,
    reason: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    hard_markers = (
        "raw",
        "tool",
        "unsupported_claim_entered",
        "new_fact",
        "scope_expansion",
        "source_boundary",
        "relationship_graph_used",
        "context_source_used",
        "market_claim_missing_as_of_date",
    )
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for error in errors:
        marker = json.dumps(error, ensure_ascii=False).lower()
        if any(item in marker for item in hard_markers):
            kept.append(error)
        else:
            dropped.append(
                {
                    "type": warning_type,
                    "original_error": error,
                    "reason": reason,
                }
            )
    return kept, dropped


def _clean_for_prompt(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _payload_digest(value: Mapping[str, Any]) -> str:
    text = json.dumps(_clean_for_prompt(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _string_list(value: Any) -> list[str]:
    if value is None:
        items: list[Any] = []
    elif isinstance(value, str):
        items = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars)].rstrip() + "...[truncated]"


def _int_env(value: str | None, *, default: int) -> int:
    try:
        return int(value) if value not in {None, ""} else default
    except (TypeError, ValueError):
        return default


def _float_env(value: str | None, *, default: float) -> float:
    try:
        return float(value) if value not in {None, ""} else default
    except (TypeError, ValueError):
        return default
