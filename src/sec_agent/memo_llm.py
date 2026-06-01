from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from sec_agent.llm_gateway import chat_completion
from sec_agent.multi_agent_contracts import build_multi_agent_memo_draft, verify_multi_agent_memo_draft
from sec_agent.research_skills import research_skill_prompt


MEMO_ROUTE_SCHEMA_VERSION = "sec_agent_memo_llm_route_v0.1"
VERIFIER_ROUTE_SCHEMA_VERSION = "sec_agent_verifier_llm_route_v0.1"
MEMO_ROUTE_SOURCE = "memo_writer_llm_v0.1"
VERIFIER_ROUTE_SOURCE = "verifier_llm_v0.1"
MEMO_ROUTER_ENV = "SEC_AGENT_MULTI_AGENT_MEMO_ROUTER"
MEMO_SUPPORTED_CLAIM_CAP = 5
MEMO_UNSUPPORTED_CLAIM_CAP = 2
MEMO_CONFLICT_CAP = 2

ChatCompletionFunc = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class MemoLLMConfig:
    llm_backend: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    chat_completions_path: str = "/chat/completions"
    model: str = "deepseek-v4-pro"
    api_key_env: str = "DEEPSEEK_API_KEY"
    temperature: float = 0.0
    memo_max_tokens: int = 2600
    verifier_max_tokens: int = 1000
    timeout_s: int = 180
    max_repair_attempts: int = 2


def memo_llm_config_from_env(env: Mapping[str, str] | None = None) -> MemoLLMConfig:
    values = dict(os.environ if env is None else env)
    return MemoLLMConfig(
        llm_backend=values.get("LLM_BACKEND", "deepseek"),
        base_url=values.get("BASE_URL", "https://api.deepseek.com"),
        chat_completions_path=values.get("CHAT_COMPLETIONS_PATH", "/chat/completions"),
        model=values.get("MODEL_NAME", "deepseek-v4-pro"),
        api_key_env=values.get("API_KEY_ENV", "DEEPSEEK_API_KEY"),
        temperature=_float_env(values.get("MEMO_TEMPERATURE"), default=0.0),
        memo_max_tokens=_int_env(values.get("MEMO_MAX_TOKENS"), default=2600),
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
    specialist_verification = state.get("specialist_verification") if isinstance(state.get("specialist_verification"), Mapping) else {}
    if specialist_verification.get("memo_writer_allowed") is False or (isinstance(judgment, Mapping) and judgment.get("memo_writer_allowed") is False):
        return {"memo_answer": build_multi_agent_memo_draft(judgment, specialist_verification=specialist_verification)}

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
        memo = _normalize_memo_llm_output(parsed, judgment)
        hard_check = verify_multi_agent_memo_draft(memo, judgment)
        if hard_check.get("status") == "pass":
            memo["model_diagnostics"] = _aggregate_model_calls(model_calls)
            memo["schema_version"] = memo.get("schema_version") or "sec_agent_multi_agent_memo_draft_v0.1"
            memo["llm_route_source"] = MEMO_ROUTE_SOURCE
            diagnostics = _aggregate_model_calls(model_calls)
            return {
                "memo_answer": memo,
                "memo_route_result": {
                    "status": "pass",
                    "attempt_count": len(model_calls),
                    "repair_attempts": max(0, len(model_calls) - 1),
                    "finish_reasons": diagnostics.get("finish_reasons") or [],
                    "total_tokens": diagnostics.get("total_tokens"),
                },
            }
        last_failure = {"type": "deterministic_memo_gate_failed", "errors": hard_check.get("errors") or []}

    fallback = build_multi_agent_memo_draft(judgment, specialist_verification=specialist_verification)
    fallback["llm_route_source"] = f"{MEMO_ROUTE_SOURCE}+deterministic_fallback"
    fallback["model_diagnostics"] = _aggregate_model_calls(model_calls)
    return {
        "memo_answer": fallback,
        "memo_route_result": {
            "status": "fallback",
            "failure_reason": _format_failure_reason(last_failure),
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

    messages = _verifier_messages(state, deterministic=deterministic)
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
        trace_tags={"route_source": VERIFIER_ROUTE_SOURCE},
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
        "llm_verifier_policy": "cannot_override_deterministic_gate",
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


def _normalize_memo_llm_output(payload: Mapping[str, Any], judgment: Any) -> dict[str, Any]:
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
    memo.setdefault("source_boundary_notes", base.get("source_boundary_notes") or [])
    memo.setdefault("evidence_strength", base.get("evidence_strength") or {})
    memo.setdefault("counterevidence", base.get("counterevidence") or [])
    memo.setdefault("missing_evidence", base.get("missing_evidence") or [])
    memo.setdefault("unsupported_claims_excluded", base.get("unsupported_claims_excluded") or [])
    memo.setdefault("memo_constraints", base.get("memo_constraints") or {})
    memo.setdefault("memo_outline", base.get("memo_outline") or [])
    memo.setdefault("memo_thesis_plan", base.get("memo_thesis_plan") or {})
    memo.setdefault("memo_thesis_pack", base.get("memo_thesis_pack") or {})
    memo.setdefault("claim_card_stats", base.get("claim_card_stats") or {})
    memo.setdefault("bounded_answer_allowed", False)
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
    return memo


def _memo_messages(
    state: Mapping[str, Any],
    *,
    prior_failure: Mapping[str, Any] | None,
    prior_content: str,
) -> list[dict[str, str]]:
    judgment = _compact_judgment_for_memo(state.get("verified_judgment_plan") or state.get("judgment_plan") or {})
    user_payload = {
        "user_query": state.get("user_query") or "",
        "verified_judgment_plan": judgment,
        "specialist_verification": _compact_specialist_verification(state.get("specialist_verification") or {}),
        "memo_input_contract": {
            "allowed_views": ["verified_judgment_plan", "specialist_verification"],
            "raw_rows_consumed": False,
            "tool_calls_allowed": False,
            "projection_policy": "memo_writer_v0_4_thesis_led_claim_cards_no_duplicate_data_view",
        },
        "memo_output_contract": {
            "direct_answer_max_chars": 420,
            "memo_claims_max": 5,
            "memo_claim_max_chars": 220,
            "caveats_max": 3,
            "unsupported_claims_excluded_max": 2,
            "source_boundary_notes_max": 3,
            "do_not_emit_supported_claims": True,
            "must_copy_claim_id_and_evidence_refs_from_input": True,
            "allowed_top_level_fields": [
                "schema_version",
                "answer_status",
                "direct_answer",
                "memo_claims",
                "caveats",
                "unsupported_claims_excluded",
                "source_boundary_notes",
                "memo_thesis_plan",
                "source_boundary",
                "raw_rows_consumed",
                "tool_calls_requested",
                "memo_generation_policy",
            ],
        },
    }
    user = (
        "Write one MemoDraft JSON object from the compact verified judgment plan only. "
        "Use memo_thesis_pack as the primary writing brief and memo_thesis_plan as the lead structure: "
        "start direct_answer from core_thesis or primary_thesis when present, then follow section_sequence. "
        "Use memo_outline only as a fallback section inventory and convert supported ClaimCard observations into memo_claims. "
        "Prefer claim_rank_bucket=memo_ready and higher claim_rank_score when choosing scarce memo_claim slots. "
        "Preserve materiality, direction, ticker_scope, metric_scope, evidence_refs, caveats, and missing_confirmations where provided. "
        "Do not request tools or use raw rows. Do not add facts beyond the verified claim cards.\n\n"
        "Keep output compact: direct_answer <= 420 characters, memo_claims <= 5, each memo_claim.claim <= 220 characters, "
        "caveats <= 3, unsupported_claims_excluded <= 2, and source_boundary_notes <= 3. "
        "Do not emit supported_claims; only emit memo_claims copied from or synthesized from input ClaimCards with claim_id and evidence_refs. "
        "Emit only the allowed top-level fields listed in memo_output_contract; do not emit analysis traces, copied judgment_plan, source tables, or full supported_claims. "
        "Do not narrate every source row; synthesize only the strongest supported investment claims and boundaries. "
        "Return JSON only; no markdown, no explanatory preface.\n\n"
        f"Input JSON:\n{_json_for_prompt(user_payload)}"
    )
    if prior_failure:
        cleaned_failure = _clean_for_prompt(prior_failure)
        repair_payload = _compact_memo_payload_for_repair(user_payload)
        if str(prior_failure.get("type") or "") in {"json_parse_failed", "model_output_truncated"}:
            user = (
                "Repair the previous MemoDraft response. The prior output was not a complete valid compact JSON object.\n"
                f"Diagnostic:\n{_json_for_prompt(cleaned_failure, sort_keys=True)}\n\n"
                f"Use this compact input JSON only:\n{_json_for_prompt(repair_payload)}\n\n"
                "Return exactly one minimal MemoDraft JSON object. "
                "direct_answer <= 360 characters, memo_claims <= 4, caveats <= 3, unsupported_claims_excluded <= 2, source_boundary_notes <= 3. "
                "Do not emit supported_claims. No markdown, no prose, no row-by-row recap."
            )
        else:
            user = (
                "Repair the previous MemoDraft response using the compact verified judgment only.\n"
                f"Diagnostic:\n{_json_for_prompt(cleaned_failure, sort_keys=True)}\n\n"
                f"Use this compact input JSON only:\n{_json_for_prompt(repair_payload)}\n\n"
                f"Previous output excerpt:\n{_truncate(prior_content, 500)}\n\n"
                "Return one shorter corrected MemoDraft JSON object only."
            )
    return [
        {"role": "system", "content": _memo_system_prompt()},
        {"role": "user", "content": user},
    ]


def _compact_judgment_for_memo(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    supported = [_compact_claim_card(item) for item in value.get("supported_claims") or [] if isinstance(item, Mapping)]
    thesis_pack = _compact_memo_thesis_pack(value.get("memo_thesis_pack") or {})
    supported_claim_cap = 0 if thesis_pack else MEMO_SUPPORTED_CLAIM_CAP
    memo_outline_cap = 4 if thesis_pack else 8
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
        "supported_claims": _select_memo_supported_claims(
            supported,
            value.get("memo_outline") or [],
            max_claims=supported_claim_cap,
        ),
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


def _compact_memo_payload_for_repair(payload: Mapping[str, Any]) -> dict[str, Any]:
    judgment = payload.get("verified_judgment_plan") if isinstance(payload.get("verified_judgment_plan"), Mapping) else {}
    compact_judgment = dict(judgment)
    thesis_pack = _compact_memo_thesis_pack(judgment.get("memo_thesis_pack") or {})
    compact_judgment["supported_claims"] = _select_memo_supported_claims(
        [dict(item) for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)],
        judgment.get("memo_outline") or [],
        max_claims=0 if thesis_pack else 5,
    )
    compact_judgment["unsupported_claims"] = [
        dict(item) for item in judgment.get("unsupported_claims") or [] if isinstance(item, Mapping)
    ][:MEMO_UNSUPPORTED_CLAIM_CAP]
    compact_judgment["conflicts"] = [dict(item) for item in judgment.get("conflicts") or [] if isinstance(item, Mapping)][:MEMO_CONFLICT_CAP]
    compact_judgment["source_boundary_notes"] = [dict(item) for item in judgment.get("source_boundary_notes") or [] if isinstance(item, Mapping)][:4]
    compact_judgment["memo_thesis_pack"] = thesis_pack
    return {
        "user_query": _truncate(str(payload.get("user_query") or ""), 240),
        "verified_judgment_plan": compact_judgment,
        "specialist_verification": payload.get("specialist_verification") or {},
        "memo_input_contract": payload.get("memo_input_contract") or {},
        "memo_output_contract": payload.get("memo_output_contract") or {},
        "required_shape": {
            "schema_version": "sec_agent_multi_agent_memo_draft_v0.1",
            "answer_status": "draft | blocked_by_specialist_verification",
            "direct_answer": "compact bounded answer",
            "memo_claims": [],
            "caveats": [],
            "unsupported_claims_excluded": [],
            "source_boundary_notes": [],
            "raw_rows_consumed": False,
            "tool_calls_requested": [],
        },
    }


def _compact_claim_card(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": str(item.get("claim_id") or ""),
        "agent_id": str(item.get("agent_id") or ""),
        "claim": _truncate(str(item.get("claim") or ""), 180),
        "claim_type": str(item.get("claim_type") or ""),
        "ticker_scope": _string_list(item.get("ticker_scope"))[:6],
        "metric_scope": _string_list(item.get("metric_scope"))[:6],
        "memo_slot": str(item.get("memo_slot") or ""),
        "materiality": str(item.get("materiality") or ""),
        "direction": str(item.get("direction") or ""),
        "evidence_refs": _string_list(item.get("evidence_refs") or item.get("refs"))[:4],
        "source_families": _string_list(item.get("source_families") or item.get("source_family"))[:5],
        "confidence": str(item.get("confidence") or ""),
        "claim_rank_score": int(item.get("claim_rank_score") or 0),
        "claim_rank_bucket": str(item.get("claim_rank_bucket") or ""),
        "caveats": [_truncate(str(part), 120) for part in _string_list(item.get("caveats"))[:2]],
        "missing_confirmations": [_truncate(str(part), 120) for part in _string_list(item.get("missing_confirmations"))[:2]],
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
        "evidence_strength_map": dict(value.get("evidence_strength_map") or {}) if isinstance(value.get("evidence_strength_map"), Mapping) else {},
        "source_boundary": _truncate(str(value.get("source_boundary") or ""), 160),
        "source_claim_refs": _string_list(value.get("source_claim_refs"))[:8],
        "pack_policy": str(value.get("pack_policy") or ""),
    }


def _compact_pack_claim(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": str(value.get("claim_id") or ""),
        "memo_slot": str(value.get("memo_slot") or ""),
        "claim": _truncate(str(value.get("claim") or ""), 180),
        "claim_type": str(value.get("claim_type") or ""),
        "direction": str(value.get("direction") or ""),
        "materiality": str(value.get("materiality") or ""),
        "ticker_scope": _string_list(value.get("ticker_scope"))[:6],
        "metric_scope": _string_list(value.get("metric_scope"))[:6],
        "evidence_refs": _string_list(value.get("evidence_refs"))[:4],
        "source_families": _string_list(value.get("source_families"))[:4],
        "caveats": [_truncate(str(part), 90) for part in _string_list(value.get("caveats"))[:1]],
        "missing_confirmations": [
            _truncate(str(part), 90) for part in _string_list(value.get("missing_confirmations"))[:1]
        ],
    }


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
        "memo_claims": [_compact_memo_claim_for_verifier(item) for item in value.get("memo_claims") or [] if isinstance(item, Mapping)][:10],
        "supported_claims": [_compact_memo_claim_for_verifier(item) for item in value.get("supported_claims") or [] if isinstance(item, Mapping)][:10],
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
    deterministic: Mapping[str, Any],
) -> list[dict[str, str]]:
    judgment = _compact_judgment_for_verifier(state.get("verified_judgment_plan") or state.get("judgment_plan") or {})
    user_payload = {
        "user_query": state.get("user_query") or "",
        "memo_answer": _compact_memo_for_verifier(state.get("memo_answer") or {}),
        "verified_judgment_inventory": judgment,
        "deterministic_verification": _compact_deterministic_verification(deterministic),
        "bounded_block_policy": (
            "If memo_answer.answer_status starts with blocked_ and deterministic_verification.status is pass, "
            "return pass unless the blocked answer itself introduces unsupported new facts, raw rows, tool calls, "
            "or source-boundary misuse. Do not fail only because a full memo was not produced."
        ),
    }
    return [
        {"role": "system", "content": _verifier_system_prompt()},
        {
            "role": "user",
            "content": (
                "Verify the memo against the compact verified judgment inventory and return one JSON object with "
                "status, errors, warnings, repair_instruction, and bounded_answer_allowed. Do not add new facts.\n\n"
                f"Input JSON:\n{json.dumps(user_payload, ensure_ascii=False, indent=2)}"
            ),
        },
    ]


def _memo_system_prompt() -> str:
    return "\n\n".join(
        [
            "You are the Memo Writer Agent for a SEC investment research multi-agent graph.",
            research_skill_prompt("memo_writer", max_chars=1800),
            "Return exactly one JSON object. Do not wrap it in prose. Do not call tools.",
            "Only consume the compact verified_judgment_plan and specialist_verification. Do not include raw rows or retrieval requests.",
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
