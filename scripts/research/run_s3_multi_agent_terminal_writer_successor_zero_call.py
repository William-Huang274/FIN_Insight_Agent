from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sec_agent.canonical_runtime import canonical_digest  # noqa: E402
from sec_agent.providers import (  # noqa: E402
    ChatCompletionResult,
    ChatCompletionToolStepResult,
    load_chat_completion_profile,
)
from sec_agent.research.bounded_finance_loop import (  # noqa: E402
    validate_deepseek_ga_node_profile,
)
from sec_agent.research.multi_agent_preview import (  # noqa: E402
    MULTI_AGENT_REPORT_DRAFT_SCHEMA_VERSION,
    SPECIALIST_AGENT_IDS,
    WRITER_AGENT_ID,
    compile_analysis_completion_checkpoint,
    compile_analysis_fragment_checkpoint,
    compile_cross_role_evaluation_checkpoint,
    compile_token_budget_basis,
    merge_analysis_draft_fragments,
    report_draft_tool,
    validate_analysis_completion_checkpoint,
    validate_analysis_continuation_completion,
    validate_analysis_fragment_checkpoint,
    validate_cross_role_evaluation_checkpoint,
    validate_report_draft,
)
from sec_agent.research.multi_agent_preview_runtime import (  # noqa: E402
    MultiAgentPreviewRuntimeError,
    execute_analyzed_preview_node,
    execute_checkpointed_preview_submission,
    start_preview_agent_session,
)
from sec_agent.research.multi_agent_successor import (  # noqa: E402
    compile_terminal_submission_successor_execution_frontier,
    compile_terminal_submission_successor_zero_call_proof,
    compile_terminal_successor_execution_frontier,
    compile_terminal_successor_zero_call_proof,
    validate_successor_execution_frontier,
    validate_terminal_submission_successor_zero_call_proof,
    validate_terminal_successor_zero_call_proof,
)
from sec_agent.project_os_preflight import (  # noqa: E402
    MULTI_AGENT_PREVIEW_GENERIC_SUCCESSOR_DECISION_SCHEMA,
    MULTI_AGENT_PREVIEW_GENERIC_SUCCESSOR_DECISION_STATUS,
    MULTI_AGENT_PREVIEW_GENERIC_SUCCESSOR_SCOPE,
    validate_multi_agent_preview_generic_successor_scope_decision,
)


EVAL_DIR = ROOT / "configs/research/evals"
CURRENT_AUTHORITY = EVAL_DIR / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "cross_role_onward_live_authority_v1_0.json"
)
CURRENT_RESULT = EVAL_DIR / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "cross_role_onward_live_result_v1_0.json"
)
PREDECESSOR_SCOPE = EVAL_DIR / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "compiled_successor_scope_decision_v1_5.json"
)
PREDECESSOR_FRONTIER = EVAL_DIR / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "compiled_successor_frontier_v1_5.json"
)
ROLE_CHECKPOINT = EVAL_DIR / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "role_evaluation_progress_checkpoint_v1_1.json"
)
ANALYSIS_PROFILE = ROOT / (
    "configs/providers/"
    "fin_ia_0_1_3_deepseek_v4_pro_ga_agent_profile_v1_1.json"
)
SUBMISSION_PROFILE = ROOT / (
    "configs/providers/"
    "fin_ia_0_1_3_deepseek_v4_pro_ga_"
    "contract_submission_non_thinking_profile_v1_0.json"
)
WRITER_PROFILE = ROOT / (
    "configs/providers/"
    "fin_ia_0_1_3_deepseek_v4_pro_ga_"
    "writer_continuation_nonthinking_profile_v1_0.json"
)
CROSS_CHECKPOINT = EVAL_DIR / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "cross_role_evaluation_checkpoint_v1_0.json"
)
WRITER_CHECKPOINT = EVAL_DIR / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "writer_analysis_fragment_checkpoint_v1_0.json"
)
TERMINAL_FRONTIER = EVAL_DIR / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "compiled_successor_frontier_v1_6.json"
)
ZERO_PROOF = EVAL_DIR / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "writer_terminal_successor_zero_call_result_v1_0.json"
)
SCOPE_DECISION = EVAL_DIR / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "compiled_successor_scope_decision_v1_6.json"
)
TERMINAL_LIVE_AUTHORITY = EVAL_DIR / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "writer_terminal_successor_live_authority_v1_0.json"
)
TERMINAL_LIVE_RESULT = EVAL_DIR / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "writer_terminal_successor_live_result_v1_0.json"
)
WRITER_COMPLETION_CHECKPOINT = EVAL_DIR / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "writer_analysis_completion_checkpoint_v1_0.json"
)
TERMINAL_SUBMISSION_FRONTIER = EVAL_DIR / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "compiled_successor_frontier_v1_7.json"
)
TERMINAL_SUBMISSION_ZERO_PROOF = EVAL_DIR / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "writer_terminal_submission_successor_zero_call_result_v1_0.json"
)
TERMINAL_SUBMISSION_SCOPE = EVAL_DIR / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "compiled_successor_scope_decision_v1_7.json"
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ref(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _path(value: str) -> Path:
    candidate = Path(str(value))
    return candidate if candidate.is_absolute() else ROOT / candidate


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        )


def _capture_file(
    capture_root: Path, *, node_fragment: str, filename: str
) -> Path:
    matches = [
        path
        for path in capture_root.rglob(filename)
        if node_fragment in path.as_posix()
    ]
    if len(matches) != 1:
        raise RuntimeError(f"capture_identity_invalid:{node_fragment}:{filename}")
    return matches[0]


def _writer_inputs(
    request: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    messages = request.get("request_body", {}).get("messages") or []
    user_envelope = json.loads(str(messages[1]["content"]))
    task_context = user_envelope["task_context"]
    visible = json.loads(str(task_context[0]["content"]))
    workpapers = [deepcopy(dict(row)) for row in visible["validated_workpapers"]]
    if [row["agent_id"] for row in workpapers] != list(SPECIALIST_AGENT_IDS):
        raise RuntimeError("writer_workpaper_order_invalid")
    return workpapers, deepcopy(dict(visible["independent_evaluation"]))


def _report_payload(workpapers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    for workpaper in workpapers:
        claims = list(workpaper["sourced_claims"])
        body = (
            str(workpaper["thesis"]).strip()
            + "\n\n机制边界："
            + str(workpaper["mechanism"]).strip()
        )[:3900]
        evidence_refs = list(
            dict.fromkeys(
                str(ref)
                for claim in claims
                for ref in claim.get("evidence_refs") or ()
            )
        )
        numeric_refs = list(
            dict.fromkeys(
                str(ref)
                for claim in claims
                for ref in claim.get("numeric_refs") or ()
            )
        )
        sections.append(
            {
                "heading": str(workpaper["agent_id"]).split("::")[-1],
                "body": body,
                "source_workpaper_agent_ids": [str(workpaper["agent_id"])],
                "evidence_refs": evidence_refs,
                "numeric_refs": numeric_refs,
            }
        )
    gaps = list(
        dict.fromkeys(
            str(ref)
            for row in workpapers
            for ref in row.get("remaining_gap_refs") or ()
        )
    )[:12]
    changes = list(
        dict.fromkeys(
            str(item)
            for row in workpapers
            for item in row.get("what_would_change") or ()
        )
    )[:12]
    payload = {
        "schema_version": MULTI_AGENT_REPORT_DRAFT_SCHEMA_VERSION,
        "report_title": "Dell Q1 FY27 AI 服务器需求、价值捕获与兑现边界研究",
        "executive_thesis": (
            str(workpapers[0]["thesis"]).strip()
            + "\n\n"
            + str(workpapers[2]["thesis"]).strip()
        )[:2300],
        "sections": sections,
        "remaining_gaps": gaps or ["GAP::NO_AUTHORIZED_PUBLIC_BRIDGE"],
        "what_would_change": changes[:12]
        or [
            "出现同口径的 AI 服务器收入、利润和现金转换桥接。",
            "出现可核验的订单取消、交付时点或供应分配披露。",
        ],
        "confidence_statement": (
            "对公司整体业绩与已披露 AI 服务器收入为中高置信；对 AI 特定利润、"
            "现金转换和 Dell 特定上游分配保持低至中等置信，所有剩余边界继续显式保留。"
        ),
    }
    return validate_report_draft(payload, workpapers=workpapers)


def _fake_execution(
    *,
    checkpoint: Mapping[str, Any],
    partial_draft: str,
    original_messages: Sequence[Mapping[str, Any]],
    workpapers: Sequence[Mapping[str, Any]],
    semantic_incomplete: bool = False,
) -> tuple[dict[str, Any] | None, int, int, str | None]:
    continuation_calls = 0
    submission_calls = 0
    report = _report_payload(workpapers)
    continuation = (
        "并继续按角色底稿保留发生事实、管理层口径与条件推断的区别。\n"
        "OUTPUT::remaining_gaps\n"
        "保留订单到收入、收入到利润、利润到现金的未闭合桥接，并保留 Dell 特定供应分配缺口。\n"
        "OUTPUT::what_would_change\n"
        "新增同口径 AI 收入、利润和现金桥接会改变价值捕获判断；新增交付、取消率和分配披露会改变需求与供给判断。\n"
        "OUTPUT::confidence_statement\n"
        "公司整体已发生业绩证据较强，AI 特定利润、现金与供应归因仍需保持条件化。\n"
        "COMPLETED_OUTPUTS::sections|remaining_gaps|what_would_change|confidence_statement"
    )
    if semantic_incomplete:
        continuation = "只补一句但不提供剩余字段或完成回执。"

    def fake_continuation(**_kwargs: Any) -> ChatCompletionResult:
        nonlocal continuation_calls
        continuation_calls += 1
        return ChatCompletionResult(
            status="completed_exact_once",
            provider_id="fake",
            model="zero-call",
            content=continuation,
            finish_reason="stop",
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            request_capture_ref="zero-call://writer-continuation-request",
            response_capture_ref="zero-call://writer-continuation-response",
            request_digest="1" * 64,
            response_digest="2" * 64,
            private_reasoning_fields_redacted=0,
        )

    def fake_submission(**_kwargs: Any) -> ChatCompletionToolStepResult:
        nonlocal submission_calls
        submission_calls += 1
        arguments = {
            key: value
            for key, value in report.items()
            if key not in {"workpaper_digests", "report_digest"}
        }
        return ChatCompletionToolStepResult(
            status="completed_exact_once",
            provider_id="fake",
            model="zero-call",
            content="",
            reasoning_content="",
            tool_calls=(
                {
                    "id": "call_writer_zero",
                    "type": "function",
                    "function": {
                        "name": "submit_report_draft",
                        "arguments": json.dumps(
                            arguments, ensure_ascii=False, sort_keys=True
                        ),
                    },
                },
            ),
            finish_reason="tool_calls",
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            request_capture_ref="zero-call://writer-submission-request",
            response_capture_ref="zero-call://writer-submission-response",
            request_digest="3" * 64,
            response_digest="4" * 64,
            private_reasoning_fields_redacted=0,
        )

    try:
        execution = execute_analyzed_preview_node(
            analysis_profile=load_chat_completion_profile(_json(ANALYSIS_PROFILE)),
            submission_profile=load_chat_completion_profile(
                _json(SUBMISSION_PROFILE)
            ),
            analysis_continuation_profile=load_chat_completion_profile(
                _json(WRITER_PROFILE)
            ),
            session_state=start_preview_agent_session(
                agent_id=WRITER_AGENT_ID,
                run_id="ZERO-CALL-WRITER-TERMINAL-SUCCESSOR",
                objective_ref="objective://dell/multi-agent-preview",
                active_plan_ref="plan://dell/report",
            ),
            messages=original_messages,
            tool=report_draft_tool(workpapers=workpapers),
            validator=lambda payload: validate_report_draft(
                payload, workpapers=workpapers
            ),
            capture_root=ROOT / "data/captures/zero_call_not_written",
            run_id="ZERO-CALL-WRITER-TERMINAL-SUCCESSOR",
            node_id="AGENT::WRITER::REPORT_DRAFT",
            purpose="只续写保存的 Writer 报告片段并映射正式报告合同。",
            input_reference_count=0,
            required_outputs=(
                "report_title",
                "executive_thesis",
                "sections",
                "remaining_gaps",
                "what_would_change",
                "confidence_statement",
            ),
            schema_burden="existing strict multi-agent report contract",
            materiality_quality_risk=(
                "Writer must preserve reviewed facts, boundaries and counterevidence"
            ),
            comparable_run_evidence=(
                "DELL cross-role-onward Writer length failure 2026-08-21",
            ),
            analysis_output_token_ceiling=12000,
            submission_output_token_ceiling=9000,
            maximum_submission_successor_attempts=1,
            analysis_checkpoint=checkpoint,
            analysis_checkpoint_draft=partial_draft,
            analysis_checkpoint_original_messages=original_messages,
            analysis_transport=fake_continuation,
            submission_transport=fake_submission,
        )
        return (
            deepcopy(dict(execution.validated_payload)),
            continuation_calls,
            submission_calls,
            None,
        )
    except MultiAgentPreviewRuntimeError as exc:
        return None, continuation_calls, submission_calls, exc.code


def _response_content(response: Mapping[str, Any]) -> str:
    try:
        return str(
            response["response_body"]["choices"][0]["message"]["content"]
        ).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("writer_visible_content_missing") from exc


def _fake_completed_writer_submission(
    *,
    completion_checkpoint: Mapping[str, Any],
    merged_draft: str,
    workpapers: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], int]:
    submission_calls = 0
    report = _report_payload(workpapers)

    def fake_submission(**_kwargs: Any) -> ChatCompletionToolStepResult:
        nonlocal submission_calls
        submission_calls += 1
        arguments = {
            key: value
            for key, value in report.items()
            if key not in {"workpaper_digests", "report_digest"}
        }
        return ChatCompletionToolStepResult(
            status="completed_exact_once",
            provider_id="fake",
            model="zero-call",
            content="",
            reasoning_content="",
            tool_calls=(
                {
                    "id": "call_writer_submission_successor_zero",
                    "type": "function",
                    "function": {
                        "name": "submit_report_draft",
                        "arguments": json.dumps(
                            arguments, ensure_ascii=False, sort_keys=True
                        ),
                    },
                },
            ),
            finish_reason="tool_calls",
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            request_capture_ref="zero-call://writer-submission-request",
            response_capture_ref="zero-call://writer-submission-response",
            request_digest="3" * 64,
            response_digest="4" * 64,
            private_reasoning_fields_redacted=0,
        )

    execution = execute_checkpointed_preview_submission(
        completed_analysis_checkpoint=completion_checkpoint,
        merged_analysis_draft=merged_draft,
        submission_profile=load_chat_completion_profile(_json(SUBMISSION_PROFILE)),
        session_state=start_preview_agent_session(
            agent_id=WRITER_AGENT_ID,
            run_id="ZERO-CALL-WRITER-TERMINAL-SUBMISSION-SUCCESSOR",
            objective_ref="objective://dell/multi-agent-preview",
            active_plan_ref="plan://dell/report",
        ),
        tool=report_draft_tool(workpapers=workpapers),
        validator=lambda payload: validate_report_draft(
            payload, workpapers=workpapers
        ),
        capture_root=ROOT / "data/captures/zero_call_not_written",
        run_id="ZERO-CALL-WRITER-TERMINAL-SUBMISSION-SUCCESSOR",
        node_id="AGENT::WRITER::REPORT_DRAFT",
        purpose="复用内容完整的 Writer 分析并只映射正式报告合同。",
        required_outputs=(
            "report_title",
            "executive_thesis",
            "sections",
            "remaining_gaps",
            "what_would_change",
            "confidence_statement",
        ),
        schema_burden="existing strict multi-agent report contract",
        materiality_quality_risk=(
            "Writer submission must preserve reviewed facts, boundaries and "
            "counterevidence without adding research content"
        ),
        comparable_run_evidence=(
            "DELL terminal Writer content-complete heading mismatch 2026-08-21",
        ),
        submission_output_token_ceiling=9000,
        maximum_submission_successor_attempts=1,
        submission_transport=fake_submission,
    )
    return deepcopy(dict(execution.validated_payload)), submission_calls


def run() -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    authority = _json(CURRENT_AUTHORITY)
    result = _json(CURRENT_RESULT)
    terminal_path = ROOT / authority["outputs"]["private_output_root_ref"] / "terminal_failure.json"
    terminal = _json(terminal_path)
    capture_root = ROOT / authority["outputs"]["capture_root_ref"]
    writer_request_path = _capture_file(
        capture_root,
        node_fragment="AGENT-WRITER-REPORT_DRAFT-ANALYSIS-ATTEMPT-01",
        filename="model_visible_request.json",
    )
    writer_response_path = _capture_file(
        capture_root,
        node_fragment="AGENT-WRITER-REPORT_DRAFT-ANALYSIS-ATTEMPT-01",
        filename="provider_response.json",
    )
    cross_request_path = _capture_file(
        capture_root,
        node_fragment="EVAL-CROSS_ROLE-CONSISTENCY_AUDIT_R1-SUBMISSION-ATTEMPT-01",
        filename="model_visible_request.json",
    )
    cross_response_path = _capture_file(
        capture_root,
        node_fragment="EVAL-CROSS_ROLE-CONSISTENCY_AUDIT_R1-SUBMISSION-ATTEMPT-01",
        filename="provider_response.json",
    )
    writer_request = _json(writer_request_path)
    writer_response = _json(writer_response_path)
    cross_request = _json(cross_request_path)
    cross_response = _json(cross_response_path)
    workpapers, final_evaluation = _writer_inputs(writer_request)
    cross_node = _json(
        ROOT
        / authority["outputs"]["private_output_root_ref"]
        / "node_01_CONSISTENCY_AUDIT_R1.json"
    )
    model_evaluation = deepcopy(dict(cross_node["validated_payload"]))
    role_checkpoint = _json(ROLE_CHECKPOINT)
    if not (
        result.get("failure_code")
        == "multi_agent_preview_analysis_finish_reason_invalid:length"
        and terminal.get("failure_code") == result.get("failure_code")
        and writer_response.get("response_body_complete") is True
        and writer_response["response_body"]["choices"][0]["finish_reason"]
        == "length"
        and len(
            str(writer_response["response_body"]["choices"][0]["message"]["content"])
        )
        == 2328
        and final_evaluation.get("report_may_proceed") is True
    ):
        raise RuntimeError("writer_terminal_source_binding_invalid")

    cross_checkpoint = compile_cross_role_evaluation_checkpoint(
        case_key="DELL",
        source_run_id=str(authority["outputs"]["run_id"]),
        source_authority_ref=_ref(CURRENT_AUTHORITY),
        source_authority_sha256=_sha(CURRENT_AUTHORITY),
        source_public_result_ref=_ref(CURRENT_RESULT),
        source_public_result_sha256=_sha(CURRENT_RESULT),
        source_public_result_digest=str(result["result_digest"]),
        source_terminal_result_ref=_ref(terminal_path),
        source_terminal_result_sha256=_sha(terminal_path),
        source_terminal_result_digest=str(terminal["full_result_digest"]),
        role_evaluation_checkpoint_ref=_ref(ROLE_CHECKPOINT),
        role_evaluation_checkpoint_sha256=_sha(ROLE_CHECKPOINT),
        role_evaluation_checkpoint_digest=str(role_checkpoint["checkpoint_digest"]),
        request_capture_ref=_ref(cross_request_path),
        request_capture_sha256=_sha(cross_request_path),
        request_digest=str(cross_request["request_digest"]),
        response_capture_ref=_ref(cross_response_path),
        response_capture_sha256=_sha(cross_response_path),
        response_digest=str(cross_response["response_digest"]),
        workpapers=workpapers,
        model_evaluation=model_evaluation,
        final_evaluation=final_evaluation,
        usage={
            "analysis": cross_node["attempts"][0].get("usage") or {},
            "submission": cross_node["attempts"][1].get("usage") or {},
        },
        recorded_at=now,
    )
    validate_cross_role_evaluation_checkpoint(
        cross_checkpoint, workpapers=workpapers
    )
    partial_draft = str(
        writer_response["response_body"]["choices"][0]["message"]["content"]
    ).strip()
    writer_checkpoint = compile_analysis_fragment_checkpoint(
        case_key="DELL",
        run_id=str(authority["outputs"]["run_id"]),
        node_id="AGENT::WRITER::REPORT_DRAFT",
        source_authority_ref=_ref(CURRENT_AUTHORITY),
        source_authority_sha256=_sha(CURRENT_AUTHORITY),
        source_public_result_ref=_ref(CURRENT_RESULT),
        source_public_result_sha256=_sha(CURRENT_RESULT),
        source_public_result_digest=str(result["result_digest"]),
        request_capture_ref=_ref(writer_request_path),
        request_capture_sha256=_sha(writer_request_path),
        request_digest=str(writer_request["request_digest"]),
        response_capture_ref=_ref(writer_response_path),
        response_capture_sha256=_sha(writer_response_path),
        response_digest=str(writer_response["response_digest"]),
        partial_draft=partial_draft,
        required_outputs=(
            "report_title",
            "executive_thesis",
            "sections",
            "remaining_gaps",
            "what_would_change",
            "confidence_statement",
        ),
        completed_required_outputs=("report_title", "executive_thesis"),
        partial_required_outputs=("sections",),
        missing_required_outputs=(
            "remaining_gaps",
            "what_would_change",
            "confidence_statement",
        ),
        usage=writer_response["response_body"].get("usage") or {},
        recorded_at=now,
    )
    validate_analysis_fragment_checkpoint(writer_checkpoint)
    predecessor_frontier = validate_successor_execution_frontier(
        _json(PREDECESSOR_FRONTIER)
    )
    predecessor_failure = {
        "authority_ref": _ref(CURRENT_AUTHORITY),
        "authority_sha256": _sha(CURRENT_AUTHORITY),
        "public_result_ref": _ref(CURRENT_RESULT),
        "public_result_sha256": _sha(CURRENT_RESULT),
        "public_result_digest": str(result["result_digest"]),
        "terminal_result_ref": _ref(terminal_path),
        "terminal_result_sha256": _sha(terminal_path),
        "terminal_result_digest": str(terminal["full_result_digest"]),
        "failure_code": str(result["failure_code"]),
        "provider_attempt_count": int(
            result["execution"]["provider_attempts_preserved"]
        ),
    }
    terminal_frontier = compile_terminal_successor_execution_frontier(
        predecessor_frontier=predecessor_frontier,
        predecessor_failure=predecessor_failure,
        cross_role_evaluation_checkpoint_digest=str(
            cross_checkpoint["checkpoint_digest"]
        ),
        writer_analysis_fragment_checkpoint_digest=str(
            writer_checkpoint["checkpoint_digest"]
        ),
    )

    fake_report, continuation_calls, submission_calls, fake_error = _fake_execution(
        checkpoint=writer_checkpoint,
        partial_draft=partial_draft,
        original_messages=writer_request["request_body"]["messages"],
        workpapers=workpapers,
    )
    if fake_error or fake_report is None:
        raise RuntimeError("writer_terminal_fake_execution_failed:" + str(fake_error))
    mutation_checks: dict[str, bool] = {}
    mutated_cross = deepcopy(cross_checkpoint)
    mutated_cross["checkpoint_digest"] = "0" * 64
    try:
        validate_cross_role_evaluation_checkpoint(
            mutated_cross, workpapers=workpapers
        )
        mutation_checks["cross_role_checkpoint_digest_mutation_rejected"] = False
    except (ValueError, RuntimeError):
        mutation_checks["cross_role_checkpoint_digest_mutation_rejected"] = True
    mutated_writer = deepcopy(writer_checkpoint)
    mutated_writer["checkpoint_digest"] = "0" * 64
    try:
        validate_analysis_fragment_checkpoint(mutated_writer)
        mutation_checks["writer_fragment_digest_mutation_rejected"] = False
    except (ValueError, RuntimeError):
        mutation_checks["writer_fragment_digest_mutation_rejected"] = True
    promoted_writer = deepcopy(writer_checkpoint)
    promoted_writer["continuation_policy"]["partial_draft_business_promotion"] = True
    promoted_body = {
        key: value
        for key, value in promoted_writer.items()
        if key != "checkpoint_digest"
    }
    promoted_writer["checkpoint_digest"] = canonical_digest(promoted_body)
    try:
        validate_analysis_fragment_checkpoint(promoted_writer)
        mutation_checks["writer_partial_business_promotion_rejected"] = False
    except (ValueError, RuntimeError):
        mutation_checks["writer_partial_business_promotion_rejected"] = True
    mutated_frontier = deepcopy(terminal_frontier)
    mutated_frontier["execution_limits"]["maximum_new_lead_plan_model_calls"] = 1
    mutated_frontier["result_digest"] = canonical_digest(
        {key: value for key, value in mutated_frontier.items() if key != "result_digest"}
    )
    try:
        validate_successor_execution_frontier(mutated_frontier)
        mutation_checks["upstream_rerun_budget_mutation_rejected"] = False
    except (ValueError, RuntimeError):
        mutation_checks["upstream_rerun_budget_mutation_rejected"] = True
    thinking_profile = deepcopy(_json(WRITER_PROFILE))
    thinking_profile["request_defaults"]["thinking"] = {"type": "enabled"}
    thinking_profile["request_defaults"]["reasoning_effort"] = "low"
    try:
        validate_deepseek_ga_node_profile(
            load_chat_completion_profile(thinking_profile),
            node_class="writer_continuation_non_thinking",
        )
        mutation_checks["thinking_enabled_writer_profile_rejected"] = False
    except (ValueError, RuntimeError):
        mutation_checks["thinking_enabled_writer_profile_rejected"] = True
    _, _, _, incomplete_error = _fake_execution(
        checkpoint=writer_checkpoint,
        partial_draft=partial_draft,
        original_messages=writer_request["request_body"]["messages"],
        workpapers=workpapers,
        semantic_incomplete=True,
    )
    mutation_checks["semantic_incompletion_rejected"] = (
        incomplete_error
        == "multi_agent_analysis_continuation_semantically_incomplete"
    )

    _write_new(CROSS_CHECKPOINT, cross_checkpoint)
    _write_new(WRITER_CHECKPOINT, writer_checkpoint)
    _write_new(TERMINAL_FRONTIER, terminal_frontier)
    proof = compile_terminal_successor_zero_call_proof(
        predecessor_frontier_ref=_ref(PREDECESSOR_FRONTIER),
        predecessor_frontier_sha256=_sha(PREDECESSOR_FRONTIER),
        predecessor_frontier=predecessor_frontier,
        terminal_frontier_ref=_ref(TERMINAL_FRONTIER),
        terminal_frontier_sha256=_sha(TERMINAL_FRONTIER),
        terminal_frontier=terminal_frontier,
        cross_role_checkpoint_ref=_ref(CROSS_CHECKPOINT),
        cross_role_checkpoint_sha256=_sha(CROSS_CHECKPOINT),
        cross_role_checkpoint_digest=str(cross_checkpoint["checkpoint_digest"]),
        writer_fragment_checkpoint_ref=_ref(WRITER_CHECKPOINT),
        writer_fragment_checkpoint_sha256=_sha(WRITER_CHECKPOINT),
        writer_fragment_checkpoint_digest=str(writer_checkpoint["checkpoint_digest"]),
        writer_continuation_profile_ref=_ref(WRITER_PROFILE),
        writer_continuation_profile_sha256=_sha(WRITER_PROFILE),
        writer_continuation_profile=_json(WRITER_PROFILE),
        fake_execution_receipt={
            "new_model_nodes": 1,
            "analysis_continuation_calls": continuation_calls,
            "strict_submission_calls": submission_calls,
            "role_evaluation_calls": 0,
            "cross_role_evaluation_calls": 0,
            "role_repair_calls": 0,
            "validated_report_contract": True,
            "analysis_draft_business_promoted": False,
            "external_source_network_calls": 0,
            "candidate_promotions": 0,
        },
        mutation_checks=mutation_checks,
    )
    validate_terminal_successor_zero_call_proof(
        proof,
        predecessor_frontier=predecessor_frontier,
        terminal_frontier=terminal_frontier,
        writer_continuation_profile=_json(WRITER_PROFILE),
    )
    _write_new(ZERO_PROOF, proof)

    predecessor_scope = _json(PREDECESSOR_SCOPE)
    scope = deepcopy(predecessor_scope)
    for field in (
        "hierarchical_evaluator_zero_call_proof_ref",
        "hierarchical_evaluator_zero_call_proof_sha256",
        "hierarchical_evaluator_zero_call_proof_result_digest",
    ):
        scope.pop(field, None)
    scope.update(
        {
            "schema_version": MULTI_AGENT_PREVIEW_GENERIC_SUCCESSOR_DECISION_SCHEMA,
            "status": MULTI_AGENT_PREVIEW_GENERIC_SUCCESSOR_DECISION_STATUS,
            "run_scope_id": MULTI_AGENT_PREVIEW_GENERIC_SUCCESSOR_SCOPE,
            "next_authorized_scope": (
                "one_bounded_DELL_multi_agent_preview_writer_checkpoint_successor"
            ),
            "predecessor_scope_decision_ref": _ref(PREDECESSOR_SCOPE),
            "predecessor_scope_decision_sha256": _sha(PREDECESSOR_SCOPE),
            "predecessor_live_authority_ref": _ref(CURRENT_AUTHORITY),
            "predecessor_live_authority_sha256": _sha(CURRENT_AUTHORITY),
            "predecessor_live_result_ref": _ref(CURRENT_RESULT),
            "predecessor_live_result_sha256": _sha(CURRENT_RESULT),
            "successor_execution_frontier_ref": _ref(TERMINAL_FRONTIER),
            "successor_execution_frontier_sha256": _sha(TERMINAL_FRONTIER),
            "successor_execution_frontier_result_digest": terminal_frontier[
                "result_digest"
            ],
            "cross_role_evaluation_checkpoint_ref": _ref(CROSS_CHECKPOINT),
            "cross_role_evaluation_checkpoint_sha256": _sha(CROSS_CHECKPOINT),
            "cross_role_evaluation_checkpoint_digest": cross_checkpoint[
                "checkpoint_digest"
            ],
            "writer_analysis_fragment_checkpoint_ref": _ref(WRITER_CHECKPOINT),
            "writer_analysis_fragment_checkpoint_sha256": _sha(WRITER_CHECKPOINT),
            "writer_analysis_fragment_checkpoint_digest": writer_checkpoint[
                "checkpoint_digest"
            ],
            "writer_continuation_profile_ref": _ref(WRITER_PROFILE),
            "writer_continuation_profile_sha256": _sha(WRITER_PROFILE),
            "writer_terminal_successor_zero_call_proof_ref": _ref(ZERO_PROOF),
            "writer_terminal_successor_zero_call_proof_sha256": _sha(ZERO_PROOF),
            "writer_terminal_successor_zero_call_proof_result_digest": proof[
                "result_digest"
            ],
            "execution_limits": terminal_frontier["execution_limits"],
            "successor_constraints": {
                **predecessor_scope["successor_constraints"],
                "cross_role_evaluation_rerun_forbidden": True,
                "writer_partial_draft_business_promotion_forbidden": True,
                "only_writer_checkpoint_continuation_authorized": True,
            },
            "token_budget_basis_policy": {
                **predecessor_scope["token_budget_basis_policy"],
                "reused_cross_role_evaluation_has_no_new_token_budget": True,
                "writer_continuation_basis_is_separate_from_submission_basis": True,
                "writer_continuation_uses_checkpoint_not_research_restart": True,
            },
            "authority_statement": (
                "Preserve the current Writer length failure and every earlier run as immutable evidence. "
                "Reuse six specialist plans, Lead plan, six workpapers, Lead coordination, three role repairs, "
                "six role evaluations and the completed cross-role evaluation by exact checkpoint lineage. "
                "Authorize only one non-thinking continuation of the saved Writer fragment and its strict report "
                "submission. No upstream model node, evaluator, network route, candidate promotion, S1/S3 "
                "acceptance, publication, generalization or release is authorized."
            ),
        }
    )
    validate_multi_agent_preview_generic_successor_scope_decision(
        root=ROOT, decision=scope
    )
    _write_new(SCOPE_DECISION, scope)
    return {
        "status": proof["status"],
        "scope_decision_ref": _ref(SCOPE_DECISION),
        "terminal_frontier_ref": _ref(TERMINAL_FRONTIER),
        "writer_partial_characters": len(partial_draft),
        "fake_report_digest": fake_report["report_digest"],
        "mutation_checks": mutation_checks,
        "provider_model_calls": 0,
        "network_calls": 0,
    }


def run_submission_successor() -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    authority = _json(TERMINAL_LIVE_AUTHORITY)
    public_result = _json(TERMINAL_LIVE_RESULT)
    terminal_path = (
        ROOT / authority["outputs"]["private_output_root_ref"] / "terminal_failure.json"
    )
    terminal = _json(terminal_path)
    attempts = list(terminal.get("terminal_node_attempts") or ())
    if len(attempts) != 1:
        raise RuntimeError("writer_terminal_submission_attempt_count_invalid")
    attempt = attempts[0]
    request_path = _path(str(attempt["request_capture_ref"]))
    response_path = _path(str(attempt["response_capture_ref"]))
    request = _json(request_path)
    response = _json(response_path)
    fragment = validate_analysis_fragment_checkpoint(_json(WRITER_CHECKPOINT))
    fragment_request = _json(_path(str(fragment["request_capture_ref"])))
    fragment_response = _json(_path(str(fragment["response_capture_ref"])))
    partial_draft = _response_content(fragment_response)
    raw_continuation = _response_content(response)
    normalized_continuation = validate_analysis_continuation_completion(
        checkpoint=fragment,
        continuation_draft=raw_continuation,
    )
    changed_lines = [
        (raw.strip(), normalized.strip())
        for raw, normalized in zip(
            raw_continuation.splitlines(),
            normalized_continuation.splitlines(),
        )
        if raw != normalized
    ]
    expected_changed_lines = [
        ("**remaining_gaps:**", "OUTPUT::remaining_gaps"),
        ("**what_would_change:**", "OUTPUT::what_would_change"),
        ("**confidence_statement:**", "OUTPUT::confidence_statement"),
    ]
    if changed_lines != expected_changed_lines:
        raise RuntimeError("writer_heading_normalization_scope_invalid")

    workpapers, final_evaluation = _writer_inputs(fragment_request)
    if final_evaluation.get("report_may_proceed") is not True:
        raise RuntimeError("writer_submission_cross_role_gate_invalid")
    request_messages = list(request["request_body"]["messages"])
    original_messages = list(fragment_request["request_body"]["messages"])
    input_reference_count = sum(
        "".join(str(row.get("content") or "") for row in original_messages).count(
            prefix
        )
        for prefix in ("EV::", "NUM::", "REL::", "GAP::")
    )
    analysis_basis = compile_token_budget_basis(
        node_id="AGENT::WRITER::REPORT_DRAFT::ANALYSIS_CONTINUATION",
        purpose=(
            "把已验收的多角色底稿编成可伸缩研报，不增加事实、数字、引用或因果关系。 "
            "本阶段只续写 checkpoint 标明的未完成内容，不重做已完成分析、"
            "不提交合同、不晋升业务事实。"
        ),
        input_characters=sum(
            len(str(row.get("content") or "")) for row in request_messages
        ),
        input_reference_count=input_reference_count,
        required_outputs=(
            "visible_analysis_continuation",
            "sections",
            "remaining_gaps",
            "what_would_change",
            "confidence_statement",
        ),
        schema_burden="analysis-only projection; no tool or JSON submission",
        materiality_quality_risk=(
            "writer synthesis can reintroduce a false fact or erase material "
            "counterevidence"
        ),
        comparable_run_evidence=(
            "DELL dynamic five-cell R7 content assessment",
            "DELL multi-agent zero-call preview v1.2",
            "DELL hierarchical Demand audit high-reasoning length failure 2026-08-21",
            "DELL fragment analysis/submission FAS-R1",
            "DELL multi-agent preview R3 Lead capacity failure",
        ),
        reasoning_profile=(
            "deepseek-v4-pro thinking=disabled visible analysis_continuation"
        ),
        output_token_ceiling=12000,
        stop_truncation_behavior=(
            "require one non-empty continuation and finish_reason=stop; merge "
            "with the immutable partial draft; no second continuation or restart"
        ),
    )
    writer_events = terminal["sessions"][WRITER_AGENT_ID]["events"]
    budget_refs = [
        str(ref)
        for event in writer_events
        if event.get("event_type") == "provider_attempt_requested"
        and event.get("attempt_id") == attempt["attempt_id"]
        for ref in event.get("input_refs") or ()
        if str(ref).startswith("token-budget://")
    ]
    if budget_refs != [
        "token-budget://" + analysis_basis["token_budget_basis_digest"]
    ]:
        raise RuntimeError("writer_analysis_token_budget_reconstruction_invalid")

    completion_checkpoint = compile_analysis_completion_checkpoint(
        fragment_checkpoint=fragment,
        fragment_checkpoint_ref=_ref(WRITER_CHECKPOINT),
        fragment_checkpoint_sha256=_sha(WRITER_CHECKPOINT),
        partial_draft=partial_draft,
        source_continuation_run_id=str(authority["outputs"]["run_id"]),
        source_continuation_authority_ref=_ref(TERMINAL_LIVE_AUTHORITY),
        source_continuation_authority_sha256=_sha(TERMINAL_LIVE_AUTHORITY),
        source_continuation_result_ref=_ref(TERMINAL_LIVE_RESULT),
        source_continuation_result_sha256=_sha(TERMINAL_LIVE_RESULT),
        source_continuation_result_digest=str(public_result["result_digest"]),
        continuation_request_capture_ref=_ref(request_path),
        continuation_request_capture_sha256=_sha(request_path),
        continuation_request_digest=str(request["request_digest"]),
        continuation_response_capture_ref=_ref(response_path),
        continuation_response_capture_sha256=_sha(response_path),
        continuation_response_digest=str(response["response_digest"]),
        continuation_messages_digest=canonical_digest(request_messages),
        continuation_draft=raw_continuation,
        finish_reason=str(attempt["finish_reason"]),
        usage=deepcopy(dict(attempt.get("usage") or {})),
        source_analysis_token_budget_basis=analysis_basis,
        recorded_at=now,
    )
    validate_analysis_completion_checkpoint(completion_checkpoint)
    merged_draft = merge_analysis_draft_fragments(
        checkpoint=fragment,
        partial_draft=partial_draft,
        continuation_draft=raw_continuation,
    )
    _write_new(WRITER_COMPLETION_CHECKPOINT, completion_checkpoint)

    predecessor_frontier = validate_successor_execution_frontier(
        _json(TERMINAL_FRONTIER)
    )
    failure_binding = {
        "authority_ref": _ref(TERMINAL_LIVE_AUTHORITY),
        "authority_sha256": _sha(TERMINAL_LIVE_AUTHORITY),
        "public_result_ref": _ref(TERMINAL_LIVE_RESULT),
        "public_result_sha256": _sha(TERMINAL_LIVE_RESULT),
        "public_result_digest": str(public_result["result_digest"]),
        "terminal_result_ref": _ref(terminal_path),
        "terminal_result_sha256": _sha(terminal_path),
        "terminal_result_digest": str(terminal["full_result_digest"]),
        "failure_code": str(public_result["failure_code"]),
        "provider_attempt_count": int(
            public_result["execution"]["provider_attempts_preserved"]
        ),
    }
    submission_frontier = (
        compile_terminal_submission_successor_execution_frontier(
            predecessor_frontier=predecessor_frontier,
            writer_continuation_failure=failure_binding,
            writer_analysis_completion_checkpoint_digest=str(
                completion_checkpoint["checkpoint_digest"]
            ),
        )
    )
    _write_new(TERMINAL_SUBMISSION_FRONTIER, submission_frontier)

    fake_report, submission_calls = _fake_completed_writer_submission(
        completion_checkpoint=completion_checkpoint,
        merged_draft=merged_draft,
        workpapers=workpapers,
    )

    def rejected(action: Any) -> bool:
        try:
            action()
        except (TypeError, ValueError, RuntimeError):
            return True
        return False

    duplicate_alias = raw_continuation.replace(
        "**remaining_gaps:**  ",
        "**remaining_gaps:**  \nOUTPUT::remaining_gaps",
        1,
    )
    wrong_alias = raw_continuation.replace(
        "**remaining_gaps:**  ", "**evidence_gaps:**  ", 1
    )
    wrong_receipt = raw_continuation.rsplit("COMPLETED_OUTPUTS::", 1)[0] + (
        "COMPLETED_OUTPUTS::sections|remaining_gaps|confidence_statement"
    )
    mutated_completion_checkpoint = deepcopy(completion_checkpoint)
    mutated_completion_checkpoint["checkpoint_digest"] = "0" * 64
    budget_mutation = deepcopy(submission_frontier)
    budget_mutation["execution_limits"][
        "maximum_resumed_writer_analysis_continuations"
    ] = 1
    budget_mutation["result_digest"] = canonical_digest(
        {k: v for k, v in budget_mutation.items() if k != "result_digest"}
    )
    thinking_profile = deepcopy(_json(SUBMISSION_PROFILE))
    thinking_profile["request_defaults"]["thinking"] = {"type": "enabled"}
    mutation_checks = {
        "completion_checkpoint_digest_mutation_rejected": rejected(
            lambda: validate_analysis_completion_checkpoint(
                mutated_completion_checkpoint
            )
        ),
        "duplicate_heading_alias_rejected": rejected(
            lambda: validate_analysis_continuation_completion(
                checkpoint=fragment, continuation_draft=duplicate_alias
            )
        ),
        "wrong_heading_alias_rejected": rejected(
            lambda: validate_analysis_continuation_completion(
                checkpoint=fragment, continuation_draft=wrong_alias
            )
        ),
        "completion_receipt_mutation_rejected": rejected(
            lambda: validate_analysis_continuation_completion(
                checkpoint=fragment, continuation_draft=wrong_receipt
            )
        ),
        "analysis_continuation_budget_mutation_rejected": rejected(
            lambda: validate_successor_execution_frontier(budget_mutation)
        ),
        "thinking_enabled_submission_profile_rejected": rejected(
            lambda: validate_deepseek_ga_node_profile(
                load_chat_completion_profile(thinking_profile),
                node_class="contract_submission_non_thinking",
            )
        ),
    }
    heading_receipt = {
        "source_failure_code": str(public_result["failure_code"]),
        "raw_continuation_digest": canonical_digest(raw_continuation),
        "normalized_continuation_digest": canonical_digest(
            normalized_continuation
        ),
        "normalized_heading_fields": [
            "remaining_gaps",
            "what_would_change",
            "confidence_statement",
        ],
        "research_content_changed": False,
        "completion_receipt_preserved": (
            raw_continuation.splitlines()[-1]
            == normalized_continuation.splitlines()[-1]
        ),
        "normalized_continuation_valid": True,
    }
    proof = compile_terminal_submission_successor_zero_call_proof(
        predecessor_frontier_ref=_ref(TERMINAL_FRONTIER),
        predecessor_frontier_sha256=_sha(TERMINAL_FRONTIER),
        predecessor_frontier=predecessor_frontier,
        submission_frontier_ref=_ref(TERMINAL_SUBMISSION_FRONTIER),
        submission_frontier_sha256=_sha(TERMINAL_SUBMISSION_FRONTIER),
        submission_frontier=submission_frontier,
        writer_completion_checkpoint_ref=_ref(WRITER_COMPLETION_CHECKPOINT),
        writer_completion_checkpoint_sha256=_sha(WRITER_COMPLETION_CHECKPOINT),
        writer_completion_checkpoint=completion_checkpoint,
        writer_submission_profile_ref=_ref(SUBMISSION_PROFILE),
        writer_submission_profile_sha256=_sha(SUBMISSION_PROFILE),
        writer_submission_profile=_json(SUBMISSION_PROFILE),
        heading_normalization_receipt=heading_receipt,
        fake_execution_receipt={
            "new_model_nodes": 1,
            "analysis_calls": 0,
            "analysis_continuation_calls": 0,
            "strict_submission_calls": submission_calls,
            "role_evaluation_calls": 0,
            "cross_role_evaluation_calls": 0,
            "role_repair_calls": 0,
            "validated_report_contract": bool(fake_report["report_digest"]),
            "analysis_draft_business_promoted": False,
            "external_source_network_calls": 0,
            "candidate_promotions": 0,
        },
        mutation_checks=mutation_checks,
    )
    validate_terminal_submission_successor_zero_call_proof(
        proof,
        predecessor_frontier=predecessor_frontier,
        submission_frontier=submission_frontier,
        writer_completion_checkpoint=completion_checkpoint,
        writer_submission_profile=_json(SUBMISSION_PROFILE),
    )
    _write_new(TERMINAL_SUBMISSION_ZERO_PROOF, proof)

    predecessor_scope = _json(SCOPE_DECISION)
    scope = deepcopy(predecessor_scope)
    for field in (
        "writer_analysis_fragment_checkpoint_ref",
        "writer_analysis_fragment_checkpoint_sha256",
        "writer_analysis_fragment_checkpoint_digest",
        "writer_continuation_profile_ref",
        "writer_continuation_profile_sha256",
        "writer_terminal_successor_zero_call_proof_ref",
        "writer_terminal_successor_zero_call_proof_sha256",
        "writer_terminal_successor_zero_call_proof_result_digest",
    ):
        scope.pop(field, None)
    scope.update(
        {
            "next_authorized_scope": (
                "one_bounded_DELL_multi_agent_preview_writer_strict_submission_successor"
            ),
            "predecessor_scope_decision_ref": _ref(SCOPE_DECISION),
            "predecessor_scope_decision_sha256": _sha(SCOPE_DECISION),
            "predecessor_live_authority_ref": _ref(TERMINAL_LIVE_AUTHORITY),
            "predecessor_live_authority_sha256": _sha(TERMINAL_LIVE_AUTHORITY),
            "predecessor_live_result_ref": _ref(TERMINAL_LIVE_RESULT),
            "predecessor_live_result_sha256": _sha(TERMINAL_LIVE_RESULT),
            "successor_execution_frontier_ref": _ref(
                TERMINAL_SUBMISSION_FRONTIER
            ),
            "successor_execution_frontier_sha256": _sha(
                TERMINAL_SUBMISSION_FRONTIER
            ),
            "successor_execution_frontier_result_digest": submission_frontier[
                "result_digest"
            ],
            "writer_analysis_completion_checkpoint_ref": _ref(
                WRITER_COMPLETION_CHECKPOINT
            ),
            "writer_analysis_completion_checkpoint_sha256": _sha(
                WRITER_COMPLETION_CHECKPOINT
            ),
            "writer_analysis_completion_checkpoint_digest": (
                completion_checkpoint["checkpoint_digest"]
            ),
            "writer_terminal_submission_successor_zero_call_proof_ref": _ref(
                TERMINAL_SUBMISSION_ZERO_PROOF
            ),
            "writer_terminal_submission_successor_zero_call_proof_sha256": _sha(
                TERMINAL_SUBMISSION_ZERO_PROOF
            ),
            "writer_terminal_submission_successor_zero_call_proof_result_digest": (
                proof["result_digest"]
            ),
            "execution_limits": submission_frontier["execution_limits"],
            "successor_constraints": {
                "historical_failures_remain_immutable": True,
                "frontier_is_compiled_from_capture_bound_lineage": True,
                "exact_reuse_requires_digest_identity": True,
                "derived_rebind_changes_only_local_digests": True,
                "business_payload_changes_require_fresh_rerun": True,
                "completed_node_model_reruns_forbidden": True,
                "research_inputs_unchanged": True,
                "cross_role_evaluation_rerun_forbidden": True,
                "writer_analysis_rerun_forbidden": True,
                "writer_analysis_continuation_rerun_forbidden": True,
                "only_writer_strict_submission_authorized": True,
                "writer_completed_analysis_business_promotion_forbidden": True,
                "deterministic_heading_normalization_only": True,
            },
            "token_budget_basis_policy": {
                key: value
                for key, value in predecessor_scope[
                    "token_budget_basis_policy"
                ].items()
                if key
                not in {
                    "writer_continuation_basis_is_separate_from_submission_basis",
                    "writer_continuation_uses_checkpoint_not_research_restart",
                }
            },
            "authority_statement": (
                "Preserve the Writer continuation failure and every earlier run as immutable evidence. "
                "The saved continuation is content-complete; normalize only three unambiguous Markdown "
                "field headings to canonical OUTPUT markers, reuse the completed analysis checkpoint, and "
                "authorize only one strict Writer report submission. No analysis, continuation, upstream "
                "Agent, repair, evaluator, network route, candidate promotion, S1/S3 acceptance, "
                "publication, generalization or release is authorized."
            ),
        }
    )
    scope["token_budget_basis_policy"][
        "writer_completed_analysis_reuse_has_no_new_token_budget"
    ] = True
    validate_multi_agent_preview_generic_successor_scope_decision(
        root=ROOT, decision=scope
    )
    _write_new(TERMINAL_SUBMISSION_SCOPE, scope)
    return {
        "status": proof["status"],
        "scope_decision_ref": _ref(TERMINAL_SUBMISSION_SCOPE),
        "submission_frontier_ref": _ref(TERMINAL_SUBMISSION_FRONTIER),
        "writer_completion_checkpoint_ref": _ref(
            WRITER_COMPLETION_CHECKPOINT
        ),
        "raw_continuation_characters": len(raw_continuation),
        "normalized_heading_count": len(changed_lines),
        "fake_report_digest": fake_report["report_digest"],
        "mutation_checks": mutation_checks,
        "provider_model_calls": 0,
        "network_calls": 0,
    }


if __name__ == "__main__":
    action = run_submission_successor if "--submission-successor" in sys.argv else run
    print(json.dumps(action(), ensure_ascii=False, indent=2, sort_keys=True))
