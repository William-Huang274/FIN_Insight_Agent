from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from retrieval.contracts import FinancialResearchKernel
from retrieval.route_compiler import QueryObjectFactRoutePolicy

from sec_agent.providers import (
    ChatCompletionResult,
    ChatCompletionToolStepResult,
    ModelGatewayError,
    execute_chat_completion_exact_once,
    execute_chat_completion_tool_step_exact_once,
)

from .bounded_finance_loop import (
    SUBMIT_RESEARCH_JUDGMENT_TOOL,
    compile_finance_loop_tools,
)
from .current_consumer import (
    CurrentResearchConsumerError,
    compile_current_research_deliverable,
    compile_current_research_messages,
    parse_current_research_output,
)
from .reviewed_evidence_pack import canonical_digest


class PairedSubmissionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PairedResearchSubmission:
    json_messages: tuple[dict[str, str], ...]
    strict_messages: tuple[dict[str, str], ...]
    strict_tool: Mapping[str, Any]
    business_payload_digest: str


CaptureRefFormatter = Callable[[str], str]
LaneRecorder = Callable[[str, Mapping[str, Any]], None]


def _business_payload_digest(
    json_messages: Sequence[Mapping[str, str]],
    strict_messages: Sequence[Mapping[str, str]],
) -> str:
    def normalized(messages: Sequence[Mapping[str, str]]) -> dict[str, Any]:
        user = json.loads(str(messages[1]["content"]))
        contract = dict(user.pop("output_contract"))
        contract.pop("submission_transport", None)
        raw_shape = dict(contract.pop("payload_shape"))
        cell_shape = dict(
            raw_shape["cells"][0]
            if "cells" in raw_shape
            else raw_shape["submit_research_judgment_arguments"]
        )
        wwc = dict(cell_shape["what_would_change"])
        wwc["threshold_numeric_ref"] = "transport-specific-empty-value"
        cell_shape["what_would_change"] = wwc
        contract["normalized_cell_payload_shape"] = cell_shape
        rules = list(user["rules"])
        rules[0] = "transport-specific-final-submission"
        user["rules"] = rules
        return {
            "system": messages[0]["content"],
            "business_payload": user,
            "normalized_output_contract": contract,
        }

    json_payload = normalized(json_messages)
    strict_payload = normalized(strict_messages)
    if json_payload != strict_payload:
        raise PairedSubmissionError("paired_submission_business_payload_drift")
    return canonical_digest(json_payload)


def compile_paired_research_submission(
    *,
    research_input: Mapping[str, Any],
    kernel: FinancialResearchKernel,
    route_policy: QueryObjectFactRoutePolicy,
    cell_id: str,
) -> PairedResearchSubmission:
    json_messages = compile_current_research_messages(
        research_input,
        required_cell_ids=[cell_id],
        submission_transport="json",
    )
    strict_messages = compile_current_research_messages(
        research_input,
        required_cell_ids=[cell_id],
        submission_transport="final_tool",
    )
    strict_tool = next(
        row
        for row in compile_finance_loop_tools(
            research_input=research_input,
            required_cell_ids=[cell_id],
            kernel=kernel,
            route_policy=route_policy,
            strict=True,
        )
        if row["function"]["name"] == SUBMIT_RESEARCH_JUDGMENT_TOOL
    )
    return PairedResearchSubmission(
        json_messages=json_messages,
        strict_messages=strict_messages,
        strict_tool=strict_tool,
        business_payload_digest=_business_payload_digest(
            json_messages, strict_messages
        ),
    )


def _provider_public(
    result: object | None,
    *,
    capture_ref_formatter: CaptureRefFormatter,
) -> dict[str, Any]:
    if result is None:
        return {}
    payload = result.as_dict()
    output = {
        key: payload.get(key)
        for key in (
            "status",
            "provider_id",
            "model",
            "finish_reason",
            "usage",
            "request_digest",
            "response_digest",
            "private_reasoning_fields_redacted",
            "reasoning_content_persisted",
        )
        if key in payload
    }
    for key in ("request_capture_ref", "response_capture_ref"):
        if payload.get(key):
            output[key] = capture_ref_formatter(str(payload[key]))
    return output


def _failure_captures(
    exc: ModelGatewayError,
    *,
    capture_ref_formatter: CaptureRefFormatter,
) -> tuple[str, str]:
    if not exc.capture_ref:
        return "", ""
    response = Path(exc.capture_ref)
    request = response.with_name("model_visible_request.json")
    return (
        capture_ref_formatter(str(request)) if request.is_file() else "",
        capture_ref_formatter(str(response)) if response.is_file() else "",
    )


def shared_provider_failure(code: str) -> bool:
    if code in {
        "model_gateway_credential_absent",
        "model_gateway_transport_error",
    }:
        return True
    return any(
        code == f"model_gateway_http_error:{status}"
        for status in (401, 402, 403, 408, 409, 429, 500, 502, 503, 504)
    )


def _lane(
    *,
    lane: str,
    provider_result: object | None,
    judgment: Mapping[str, Any] | None,
    deliverable: Mapping[str, Any] | None,
    failure_phase: str,
    failure_code: str,
    failure_request_capture_ref: str,
    failure_response_capture_ref: str,
    capture_ref_formatter: CaptureRefFormatter,
) -> dict[str, Any]:
    return {
        "lane": lane,
        "status": (
            "contract_valid"
            if not failure_code and deliverable is not None
            else "terminal_failed_no_retry"
        ),
        "failure_phase": failure_phase,
        "failure_code": failure_code,
        "failure_request_capture_ref": failure_request_capture_ref,
        "failure_response_capture_ref": failure_response_capture_ref,
        "provider": _provider_public(
            provider_result,
            capture_ref_formatter=capture_ref_formatter,
        ),
        "judgment": dict(judgment or {}),
        "structured_deliverable": dict(deliverable or {}),
        "deliverable_digest": (
            str(deliverable.get("deliverable_digest") or "")
            if deliverable
            else ""
        ),
    }


def _normalize_strict_judgment(arguments: str) -> dict[str, Any]:
    try:
        value = json.loads(arguments)
    except json.JSONDecodeError as exc:
        raise PairedSubmissionError(
            "paired_submission_strict_arguments_json_invalid"
        ) from exc
    if not isinstance(value, dict):
        raise PairedSubmissionError(
            "paired_submission_strict_arguments_not_object"
        )
    wwc = value.get("what_would_change")
    if isinstance(wwc, Mapping) and wwc.get("threshold_numeric_ref") == "":
        value["what_would_change"] = dict(wwc)
        value["what_would_change"]["threshold_numeric_ref"] = None
    return {"cells": [value]}


def run_paired_research_submission(
    *,
    research_input: Mapping[str, Any],
    submission: PairedResearchSubmission,
    json_profile: Any,
    strict_profile: Any,
    capture_root: Path,
    run_id: str,
    json_attempt_id: str,
    strict_attempt_id: str,
    cell_id: str,
    capture_ref_formatter: CaptureRefFormatter,
    lane_recorder: LaneRecorder | None = None,
    json_executor: Callable[..., ChatCompletionResult] = (
        execute_chat_completion_exact_once
    ),
    strict_executor: Callable[..., ChatCompletionToolStepResult] = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> dict[str, Any]:
    if submission.business_payload_digest != _business_payload_digest(
        submission.json_messages,
        submission.strict_messages,
    ):
        raise PairedSubmissionError("paired_submission_business_digest_drift")
    json_provider: ChatCompletionResult | None = None
    json_judgment: Mapping[str, Any] | None = None
    json_deliverable: Mapping[str, Any] | None = None
    json_phase = ""
    json_code = ""
    json_request_capture = ""
    json_response_capture = ""
    json_transport_failed = False
    try:
        json_provider = json_executor(
            profile=json_profile,
            messages=submission.json_messages,
            capture_root=capture_root,
            run_id=run_id,
            attempt_id=json_attempt_id,
        )
        if json_provider.finish_reason != "stop":
            raise PairedSubmissionError(
                "paired_submission_json_finish_reason_invalid"
            )
        json_judgment = parse_current_research_output(json_provider.content)
        json_deliverable = compile_current_research_deliverable(
            research_input=research_input,
            judgment_output=json_judgment,
            required_cell_ids=[cell_id],
        )
    except ModelGatewayError as exc:
        json_phase, json_code = "provider_transport_or_response", exc.code
        json_transport_failed = shared_provider_failure(exc.code)
        json_request_capture, json_response_capture = _failure_captures(
            exc,
            capture_ref_formatter=capture_ref_formatter,
        )
    except CurrentResearchConsumerError as exc:
        json_phase, json_code = "json_local_contract", exc.code
    except PairedSubmissionError as exc:
        json_phase, json_code = "json_terminal_validation", exc.code
    json_lane = _lane(
        lane="json_control",
        provider_result=json_provider,
        judgment=json_judgment,
        deliverable=json_deliverable,
        failure_phase=json_phase,
        failure_code=json_code,
        failure_request_capture_ref=json_request_capture,
        failure_response_capture_ref=json_response_capture,
        capture_ref_formatter=capture_ref_formatter,
    )
    if lane_recorder is not None:
        lane_recorder("json_lane", json_lane)

    strict_provider: ChatCompletionToolStepResult | None = None
    strict_judgment: Mapping[str, Any] | None = None
    strict_deliverable: Mapping[str, Any] | None = None
    strict_phase = ""
    strict_code = ""
    strict_request_capture = ""
    strict_response_capture = ""
    if not json_transport_failed:
        try:
            strict_provider = strict_executor(
                profile=strict_profile,
                messages=submission.strict_messages,
                tools=[submission.strict_tool],
                capture_root=capture_root,
                run_id=run_id,
                attempt_id=strict_attempt_id,
                tool_choice=None,
            )
            if strict_provider.finish_reason != "tool_calls":
                raise PairedSubmissionError(
                    "paired_submission_strict_finish_reason_invalid"
                )
            if len(strict_provider.tool_calls) != 1:
                raise PairedSubmissionError(
                    "paired_submission_strict_single_call_required"
                )
            call = strict_provider.tool_calls[0]
            if call["function"]["name"] != SUBMIT_RESEARCH_JUDGMENT_TOOL:
                raise PairedSubmissionError(
                    "paired_submission_strict_tool_invalid"
                )
            strict_judgment = _normalize_strict_judgment(
                str(call["function"]["arguments"])
            )
            strict_deliverable = compile_current_research_deliverable(
                research_input=research_input,
                judgment_output=strict_judgment,
                required_cell_ids=[cell_id],
            )
        except ModelGatewayError as exc:
            strict_phase, strict_code = (
                "provider_transport_or_response",
                exc.code,
            )
            strict_request_capture, strict_response_capture = _failure_captures(
                exc,
                capture_ref_formatter=capture_ref_formatter,
            )
        except CurrentResearchConsumerError as exc:
            strict_phase, strict_code = "strict_local_contract", exc.code
        except PairedSubmissionError as exc:
            strict_phase, strict_code = "strict_terminal_validation", exc.code
    else:
        strict_phase = "not_attempted_after_json_transport_failure"
        strict_code = "paired_submission_strict_skipped"
    strict_lane = _lane(
        lane="strict_final_tool",
        provider_result=strict_provider,
        judgment=strict_judgment,
        deliverable=strict_deliverable,
        failure_phase=strict_phase,
        failure_code=strict_code,
        failure_request_capture_ref=strict_request_capture,
        failure_response_capture_ref=strict_response_capture,
        capture_ref_formatter=capture_ref_formatter,
    )
    if lane_recorder is not None:
        lane_recorder("strict_lane", strict_lane)
    return {
        "json_lane": json_lane,
        "strict_lane": strict_lane,
        "strict_skipped": json_transport_failed,
        "tool_choice_sent": False,
        "product_publication": False,
    }


__all__ = [
    "PairedResearchSubmission",
    "PairedSubmissionError",
    "compile_paired_research_submission",
    "run_paired_research_submission",
    "shared_provider_failure",
]
