"""One paid next-action comparison on archived agent input, no tools executed.

Diagnostic only: this is not an Agent Server research run or a passed full case.
Uses the existing ChatDeepSeek SDK and native review schemas, not a new harness.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage, messages_from_dict
from langchain_core.tracers.langchain import wait_for_all_tracers
from langsmith import tracing_context
from pydantic import SecretStr, ValidationError

from sec_agent.agent_runtime.deepseek_structured_agents import (
    ReasoningPreservingChatDeepSeek, _NATIVE_REVIEW_TOOLS, _provider_function_schema, _native_function_schema,
    _bind_native_call_context, _usage_audit_fields,
)
from sec_agent.agent_runtime.dell_lead_research_graph import LEAD_RESEARCH_TOOLS, LEAD_RESEARCH_SYSTEM_PROMPT
from sec_agent.agent_runtime.dell_specialist_agentic_graph import (
    SubmitWorkpaperAction, ReviseWorkpaperAction, apply_workpaper_edits, _submission_errors, canonical_sha256,
)
from scripts.qualification.dell_q1_specialist_paid_shadow.run_once import _dotenv, _write_new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", choices=("deepseek-v4-pro", "deepseek-v4-flash"), required=True)
    parser.add_argument("--effort", choices=("low", "high"), required=True)
    parser.add_argument("--task", choices=("review", "lead", "submission", "submission-edit"), default="review")
    parser.add_argument("--budget-basis", type=Path)
    parser.add_argument("--prepare-only", action="store_true", help="Write the exact input locally without loading credentials or calling a model.")
    parser.add_argument("--additional-source-ids", type=Path, help="Submission diagnostic only: explicit IDs already present in the original observations.")
    parser.add_argument("--source-turn", type=int, default=1)
    parser.add_argument("--thinking", choices=("enabled", "disabled"), default="enabled")
    parser.add_argument("--force-repair-tool", action="store_true", help="Non-thinking submission-edit diagnostic only: require the named native repair tool.")
    parser.add_argument("--repair-feedback-from", type=Path, help="Continue a rejected same-candidate repair with the original AI tool call and standard error feedback; no automatic retry.")
    parser.add_argument("--max-output-tokens", type=int, default=32000)
    args = parser.parse_args()
    is_submission = args.task in {"submission", "submission-edit"}
    if args.force_repair_tool and (args.task != "submission-edit" or args.thinking != "disabled"):
        raise ValueError("forced_repair_requires_non_thinking_submission_edit")
    if args.repair_feedback_from and args.task != "submission-edit":
        raise ValueError("repair_feedback_requires_submission_edit")
    tool_choice = {"type": "function", "function": {"name": "ReviseWorkpaperAction"}} if args.force_repair_tool else "auto"
    # Exclusive directory is just ordinary file safety, not another execution protocol.
    args.output_dir.mkdir(exist_ok=False)
    sources = [json.loads(line) for line in args.source_audit.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not 1 <= args.source_turn <= len(sources) or not 1000 <= args.max_output_tokens <= 32000:
        raise ValueError("comparison_source_turn_or_output_limit_invalid")
    source = sources[args.source_turn - 1]
    if is_submission and not args.budget_basis:
        raise ValueError("submission_diagnostic_requires_task_specific_budget_basis")
    if args.task == "review" and (not source["actor"].startswith("verifier:") or
            [m["type"] for m in source["messages"]] != ["system", "human"]):
        raise ValueError("comparison_requires_first_verifier_turn_without_private_reasoning_history")
    if args.task == "lead" and source["actor"] != "lead:research-delegation":
        raise ValueError("lead_comparison_requires_same_actor_source")
    native_tools = LEAD_RESEARCH_TOOLS if args.task == "lead" else _NATIVE_REVIEW_TOOLS
    messages = messages_from_dict([{"type": m["type"], "data": m} for m in source["messages"]])
    if args.task == "lead":
        # Known-input diagnostic of the corrected instruction. Own past model
        # response/reasoning and actual failed tool feedback remain verbatim.
        messages[0].content = LEAD_RESEARCH_SYSTEM_PROMPT
    if is_submission:
        if not source["actor"].startswith("specialist:"):
            raise ValueError("submission_diagnostic_requires_specialist_source")
        original = [call for call in source["raw_response"]["tool_calls"] if call["name"] == "SubmitWorkpaperAction"]
        if len(original) != 1:
            raise ValueError("submission_diagnostic_requires_one_original_submission")
        candidate = original[0]["args"]
        progress = source["semantic_input"]["progress"]
        cited = {ref for claim in candidate["claims"] for key in ("evidence_ids", "fact_ids") for ref in claim.get(key, [])}
        if args.additional_source_ids:
            additional = json.loads(args.additional_source_ids.read_text(encoding="utf-8"))
            observed_ids = {ref["ref_id"] for obs in progress["observations"] for ref in obs["references"]}
            if not isinstance(additional, list) or any(not isinstance(ref, str) or ref not in observed_ids for ref in additional):
                raise ValueError("additional_source_must_be_observed_in_original_attempt")
            cited.update(additional)
        # Select exact recorded observations; do not summarize passages or
        # fabricate a full notebook/receipt. Acceptance below checks ALL original
        # observations, including identity conflicts outside the selected input.
        items = [item for obs in progress["observations"] for item in obs["content"]]
        for item in items:
            if item.get("calculation_id") in cited:
                # Preserve operand provenance alongside the canonical result.
                operands = item.get("operands", {})
                for operand in operands.values() if isinstance(operands, dict) else operands:
                    if isinstance(operand, dict) and isinstance(operand.get("source_id"), str):
                        cited.add(operand["source_id"])
        selected, seen_references, seen_items = [], set(), set()
        for obs in progress["observations"]:
            references, content = [], []
            for ref in obs["references"]:
                identity = json.dumps(ref, sort_keys=True, ensure_ascii=False)
                if ref["ref_id"] in cited and identity not in seen_references:
                    references.append(ref)
                    seen_references.add(identity)
            for item in obs["content"]:
                identity = json.dumps(item, sort_keys=True, ensure_ascii=False)
                if any(item.get(key) in cited for key in ("passage_id", "calculation_id", "fact_id", "evidence_id")) and identity not in seen_items:
                    content.append(item)
                    seen_items.add(identity)
            if references or content:
                selected.append({**obs, "references": references, "content": content})
        diagnostic_binding = sha256(json.dumps(candidate, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        native_tools = {"SubmitWorkpaperAction": SubmitWorkpaperAction}
        messages = [SystemMessage(content=(
            "Repair the supplied rejected workpaper against the tool schema and exact recorded sources. "
            "Retain every required finding, limitation and calculation. A disclosed number quoted from an original "
            "passage is reported_fact; numeric_fact requires an authoritative structured financial observation. "
            "Use exact observed references and contiguous quotes; calculations cite the recorded CALC receipts. "
            "Do not fetch new evidence, invent facts, silently remove difficult claims, or claim full research passed. "
            "Keep all original claim_id values exactly; correct each claim in place, without adding, merging or dropping claims. "
            "Read all supplied observations before declaring missing information. Correct unsupported inferences (including "
            "overstated financing or dilution conclusions); exact quote matching alone does not establish semantic support. "
            "Return one complete SubmitWorkpaperAction. This is a bounded repair diagnostic, not a resumed research run.")),
            HumanMessage(content=json.dumps({"original_candidate": candidate,
                "observations": selected, "original_task": source["semantic_input"].get("task_context"),
                "diagnostic_context_digest": diagnostic_binding}, ensure_ascii=False))]
        if args.task == "submission-edit":
            native_tools = {"ReviseWorkpaperAction": ReviseWorkpaperAction}
            messages[0].content = messages[0].content.replace("Return one complete SubmitWorkpaperAction.",
                "Return one ReviseWorkpaperAction containing only necessary JSON Pointer replacements with exact old_value/new_value. "
                "The full updated workpaper must still satisfy the provided SubmitWorkpaperAction schema. "
                "Prefer replacing individual claim fields and citation dictionaries. Preserve unchanged narrative unless its meaning requires correction.")
            packet = json.loads(messages[1].content)
            packet.update(base_submission_digest=canonical_sha256(candidate),
                required_submission_schema=SubmitWorkpaperAction.model_json_schema())
            try:
                SubmitWorkpaperAction.model_validate_json(json.dumps(candidate))
            except ValidationError as exc:
                packet["candidate_validation_errors"] = exc.errors(include_input=False, include_context=False, include_url=False)
            messages[1].content = json.dumps(packet, ensure_ascii=False)
            if args.repair_feedback_from:
                prior_messages = json.loads((args.repair_feedback_from / "messages.private.json").read_text(encoding="utf-8"))
                prior_packet = json.loads(prior_messages[1]["content"])
                if canonical_sha256(prior_packet["original_candidate"]) != canonical_sha256(candidate):
                    raise ValueError("repair_feedback_candidate_mismatch")
                prior = AIMessage.model_validate(json.loads((args.repair_feedback_from / "response.private.json").read_text(encoding="utf-8")))
                if prior.invalid_tool_calls or len(prior.tool_calls) != 1 or prior.tool_calls[0]["name"] != "ReviseWorkpaperAction":
                    raise ValueError("repair_feedback_requires_one_parsed_repair")
                call = prior.tool_calls[0]
                try:
                    edit = ReviseWorkpaperAction.model_validate_json(json.dumps({**call["args"], "context_digest": diagnostic_binding}))
                    apply_workpaper_edits(candidate, edit)
                except ValueError:
                    messages.extend([prior, ToolMessage(tool_call_id=call["id"], name=call["name"], status="error",
                        content=json.dumps({"accepted": False, "error": "workpaper_edit_old_value_or_path_mismatch",
                            "message": "No edits were applied. Use zero-based numeric array indices, e.g. /claims/0/kind; copy exact current old_value. Correct the candidate_validation_errors as well. The original candidate and base digest remain unchanged."}))])
                else:
                    raise ValueError("repair_feedback_requires_rejected_patch")
    if args.prepare_only:
        _write_new(args.output_dir / "messages.private.json", [m.model_dump(mode="json") for m in messages])
        print(json.dumps({"status": "prepared_no_model_call", "input_characters": sum(len(m.content) for m in messages),
            "source_call_id": source["call_id"], "task": args.task}))
        return
    secrets = _dotenv()
    for name, value in secrets.items():
        if name.startswith("LANGSMITH_") or name in {"LANGCHAIN_API_KEY", "LANGCHAIN_TRACING_V2", "LANGCHAIN_PROJECT"}:
            os.environ[name] = value
    project = secrets.get("LANGSMITH_PROJECT", "fin-insight-dell-reference-vertical")
    manifest = {"purpose": f"known-input {args.task} next-action model/thinking diagnostic; no tool execution or research admission",
        "source_call_id": source["call_id"], "source_actor": source["actor"], "model": args.model,
        "reasoning_effort": args.effort if args.thinking == "enabled" else None,
        "thinking": args.thinking, "max_output_tokens": args.max_output_tokens,
        "tool_choice": tool_choice,
        "input_characters": sum(len(m.content) for m in messages),
        "timeout_seconds": 480, "transport_attempts_allowed": 1, "retry": False,
        "TokenBudgetBasis": args.budget_basis.read_text(encoding="utf-8") if args.budget_basis else "docs/worklog/fin_0_1_3_s3/190_dell_cost_external_and_interactive_delivery.md",
        "langsmith_project": project, "recorded_at": datetime.now(timezone.utc).isoformat()}
    _write_new(args.output_dir / "request.json", manifest)
    _write_new(args.output_dir / "messages.private.json", [m.model_dump(mode="json") for m in messages])
    model = ReasoningPreservingChatDeepSeek(model=args.model,
        **({"reasoning_effort": args.effort} if args.thinking == "enabled" else {}),
        api_key=SecretStr(secrets["DEEPSEEK_API_KEY"]), base_url="https://api.deepseek.com",
        max_tokens=args.max_output_tokens, timeout=480, max_retries=0, streaming=False, use_responses_api=False,
        extra_body={"thinking": {"type": args.thinking}})
    runnable = model.bind_tools([_native_function_schema(tool, runtime_context_binding=True) if is_submission
                                else _provider_function_schema(tool, strict=False) for tool in native_tools.values()],
                               tool_choice=tool_choice, strict=False)
    started = perf_counter()
    raw = None
    try:
        with tracing_context(enabled=True, project_name=project):
            raw = runnable.invoke(messages, config={"run_name": args.output_dir.name,
                "tags": ["cost-model-comparison", "diagnostic-only", "no-tool-execution"]})
        _write_new(args.output_dir / "response.private.json", raw.model_dump(mode="json"))
        valid = not raw.invalid_tool_calls and bool(raw.tool_calls)
        reference_errors = None
        for call in raw.tool_calls:
            if call["name"] not in native_tools:
                valid = False
            else:
                arguments = call["args"]
                if is_submission:
                    # The provider-facing schema omits host-owned context_digest.
                    arguments = _bind_native_call_context(call, diagnostic_binding)["args"]
                    if arguments.get("context_digest") != diagnostic_binding:
                        raise ValueError("diagnostic_context_digest_mismatch")
                validated = native_tools[call["name"]].model_validate_json(json.dumps(arguments))
                if args.task == "submission-edit":
                    repaired = apply_workpaper_edits(candidate, validated)
                    _write_new(args.output_dir / "repaired-submission.private.json", repaired)
                    validated = SubmitWorkpaperAction.model_validate_json(json.dumps(repaired, ensure_ascii=False))
                if is_submission:
                    observed = SimpleNamespace(observations=[SimpleNamespace(
                        references=[SimpleNamespace(**ref) for ref in obs["references"]],
                        content=obs["content"]) for obs in progress["observations"]],
                        required_route_obligation_ids=progress["required_route_obligation_ids"],
                        satisfied_route_obligation_ids=progress["satisfied_route_obligation_ids"])
                    reference_errors = list(_submission_errors(validated, observed, enforce_case_route_requirements=False))
                    original_claims = {claim["claim_id"] for claim in candidate["claims"]}
                    if {claim.claim_id for claim in validated.claims} != original_claims:
                        reference_errors.append("diagnostic_claim_set_changed_requires_review")
                    valid = valid and not reference_errors and len(raw.tool_calls) == 1
        lead_binding_valid = None
        if args.task == "lead":
            lead_binding_valid = (len(raw.tool_calls) == 1 and
                raw.tool_calls[0]["args"].get("context_digest") == source["semantic_input"]["context_digest"] and
                all(len(task["coverage_obligation_ids"]) == 1 and
                    set(task["coverage_obligation_ids"]).issubset(source["semantic_input"]["required_branch_ids"])
                    for call in raw.tool_calls for task in call["args"].get("tasks", [])))
            valid = valid and lead_binding_valid
        result = {"status": ("provider_output_truncated" if raw.response_metadata.get("finish_reason") == "length"
                             else "next_action_schema_valid" if valid else "next_action_invalid"),
                  "finish_reason": raw.response_metadata.get("finish_reason"),
                  "actions": [call["name"] for call in raw.tool_calls],
                  "lead_context_and_coverage_binding_valid": lead_binding_valid,
                  "submission_reference_errors": reference_errors,
                  "archive_receipts_verified": False if is_submission else None,
                  "full_task_passed": False, "elapsed_seconds": round(perf_counter() - started, 3),
                  **_usage_audit_fields(raw)}
    except Exception as exc:
        # Only expose project-defined rejection codes, never arbitrary provider
        # exceptions (which can contain request bodies or credentials).
        code = str(exc)
        known_code = code if code.startswith(("workpaper_edit_", "diagnostic_", "repair_feedback_")) and code.replace("_", "").isalnum() else None
        result = {"status": "failed", "error_type": type(exc).__name__, "error_code": known_code, "http_status_code": getattr(exc, "status_code", None),
                  "validation_errors": exc.errors(include_input=False, include_context=False, include_url=False) if isinstance(exc, ValidationError) else None,
                  "full_task_passed": False, "elapsed_seconds": round(perf_counter() - started, 3),
                  **(_usage_audit_fields(raw) if raw is not None else {"usage_reported": False})}
    finally:
        wait_for_all_tracers()
    _write_new(args.output_dir / "outcome.json", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
