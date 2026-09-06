"""Container-side half of the one-shot Dell Q1 paid shadow."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime, timezone
from hashlib import sha256
from itertools import islice
import json
import os
from pathlib import Path
import time
from typing import Any

from langsmith import Client as LangSmithClient
from psycopg_pool import ConnectionPool

from sec_agent.agent_runtime.dell_agent_server_client import (
    DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION,
    DellAgentServerClient,
)
from sec_agent.agent_runtime.dell_agent_server_identity import (
    PostgresDellAgentServerIdentityRepository,
    agent_session_identity_digest,
    research_run_identity_digest,
    run_invocation_identity_digest,
)
from sec_agent.agent_runtime.dell_reference_vertical_contracts import RuntimeReceipt, canonical_sha256
from sec_agent.agent_runtime.dell_lead_research_graph import SubmitResearchHandoffAction
from sec_agent.agent_runtime.dell_workpaper_review_graph import validate_workpaper_state
from sec_agent.agent_runtime.dell_specialist_agentic_composition import (
    open_dell_specialist_receipted_composition,
)
from sec_agent.agent_runtime.dell_specialist_agentic_graph import (
    SpecialistHumanReviewHandoff,
    SpecialistNotebook,
    SubmitWorkpaperAction,
    SubmitReviewAction,
)
from sec_agent.agent_runtime.dell_specialist_paid_shadow import (
    DellQ1SpecialistPaidShadowAuthority,
    file_sha256,
    load_dell_q1_paid_shadow_authority,
    require_data_authority_binding,
    require_runtime_authority_binding,
)
from sec_agent.agent_runtime.dell_zero_model_graph_qualification import (
    PRODUCT_EXECUTION_PROFILE,
)
from sec_agent.canonical_runtime.contracts_v1_2 import (
    create_agent_session_v1_2,
    create_research_run,
    create_run_invocation,
)
from sec_agent.research_foundation.contracts import (
    load_dell_reference_vertical_foundation,
)


ROOT = Path(os.environ.get("FIN_REPO_ROOT", "/deps/FIN_Insight_Agent")).resolve()
FOUNDATION = ROOT / "configs/research/fin_ia_0_1_3_dell_reference_vertical_foundation_v1_0.json"
SERVER_URL = "http://127.0.0.1:8000"
LANGSMITH_PROJECT = "fin-insight-dell-reference-vertical"


class ContainerRunError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError):
        raise ContainerRunError("paid_shadow_non_json_value") from None


def _digest(value: Any) -> str:
    return sha256(_bytes(value)).hexdigest()


def _parse(model: type[Any], value: Any, code: str) -> Any:
    try:
        return model.model_validate_json(_bytes(value))
    except Exception:
        raise ContainerRunError(code) from None


def _write_new(path: Path, value: Any) -> None:
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError:
        raise ContainerRunError("paid_shadow_private_state_exists") from None


def _never_model(_request: Mapping[str, Any]) -> Mapping[str, Any]:
    raise ContainerRunError("paid_shadow_input_composition_executed")


def _contracts_and_input(
    authority: DellQ1SpecialistPaidShadowAuthority,
) -> tuple[Any, Any, Any, dict[str, Any]]:
    with open_dell_specialist_receipted_composition(
        run_id=authority.research_run_id,
        run_invocation_id=authority.run_invocation_id,
        branch_id=authority.branch_id,
        turn_source="provider_model",
        model_turn=_never_model,
        max_model_turns=authority.max_model_turns,
        max_tool_actions=authority.max_tool_actions,
        source_read_enabled=authority.source_read_enabled,
        live_web_read_enabled=authority.live_external_calls_authorized,
    ) as composition:
        require_data_authority_binding(
            authority,
            owner_data_gate_decision_digest=composition.owner_data_gate_decision_digest,
            inventory_snapshot_digest=composition.inventory_snapshot_digest,
            source_route_catalog_digest=composition.source_route_catalog_digest,
        )
        graph_input = composition.graph_input
    if (
        graph_input.agent_id != authority.node_id
        or graph_input.task.branch_id != authority.branch_id
        or graph_input.task.research_as_of != authority.research_as_of
    ):
        raise ContainerRunError("paid_shadow_graph_input_mismatch")
    foundation = load_dell_reference_vertical_foundation(FOUNDATION)
    case_review = authority.case_review_scope is not None
    objective = foundation.case_identity.top_level_question_zh if case_review else graph_input.task.objective
    objective_scope = "case-review" if case_review else "q1-shadow"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    session = create_agent_session_v1_2(
        session_id=authority.agent_session_id,
        thread_id=authority.fin_thread_id,
        case_id=foundation.case_identity.case_id,
        case_version="FIN_0_1_3",
        as_of_date=date.fromisoformat(authority.research_as_of[:10]),
        objective_ref=f"objective://dell/{objective_scope}/{authority.paid_full_chain_execution_id}",
        objective_digest=canonical_sha256(
            {"scope": objective_scope, "objective": objective} if case_review else {"branch_id": authority.branch_id, "objective": objective}
        ),
        data_snapshot_ref=f"snapshot://dell/{graph_input.task.snapshot_id}",
        data_snapshot_digest=authority.owner_data_gate_decision_digest,
        runtime_policy_ref=f"authority://{authority.decision_id}",
        runtime_policy_digest=authority.decision_digest,
        authority_refs=(f"authority://{authority.decision_id}",),
        active_plan_ref=f"plan://dell/q1-shadow/{graph_input.task.plan_digest}",
        active_plan_digest=graph_input.task.plan_digest,
        status="ACTIVE",
        created_at=now,
        updated_at=now,
    )
    research_run = create_research_run(
        run_id=authority.research_run_id,
        session_id=session.session_id,
        parent_run_id=None,
        origin_kind="INITIAL",
        legacy_paid_full_chain_execution_label=None,
        status="RUNNING",
        base_plan_ref=session.active_plan_ref,
        base_plan_digest=session.active_plan_digest,
        current_plan_ref=session.active_plan_ref,
        current_plan_digest=session.active_plan_digest,
        last_session_sequence=0,
        created_at=now,
        terminal_at=None,
    )
    invocation = create_run_invocation(
        invocation_id=authority.run_invocation_id,
        session_id=session.session_id,
        run_id=research_run.run_id,
        ordinal=1,
        invocation_kind="START",
        status="RUNNING",
        trigger_ref=f"qualification://dell/q1-shadow/{authority.paid_full_chain_execution_id}/start",
        lease_ref=f"lease://dell/q1-shadow/{authority.paid_full_chain_execution_id}/1",
        started_at=now,
        finished_at=None,
    )
    if session.thread_id != authority.fin_thread_id:
        raise ContainerRunError("paid_shadow_fin_thread_mismatch")
    return session, research_run, invocation, graph_input.model_dump(mode="json")


def _stream(parts: Iterable[Any]) -> dict[str, Any]:
    rows = []
    for part in parts:
        data = _bytes(part.data)
        rows.append({"id": part.id, "event": part.event, "bytes": len(data), "sha256": sha256(data).hexdigest()})
    if not rows:
        raise ContainerRunError("paid_shadow_stream_empty")
    end_indexes = [index for index, row in enumerate(rows) if row["event"] == "end"]
    if end_indexes and end_indexes != [len(rows) - 1]:
        raise ContainerRunError("paid_shadow_stream_end_not_terminal")
    return {"event_count": len(rows), "sha256": _digest(rows)}


def _terminal(raw: Mapping[str, Any], authority: DellQ1SpecialistPaidShadowAuthority) -> dict[str, Any]:
    if authority.case_review_scope is not None:
        from sec_agent.agent_runtime.dell_case_review_agent import CaseReview
        values = raw.get("values", {})
        scope = authority.case_review_scope
        if (raw.get("next") or raw.get("interrupts") or values.get("run_id") != authority.research_run_id
                or values.get("run_invocation_id") != authority.run_invocation_id
                or values.get("phase") != "case_review_ready_for_convergence"):
            raise ContainerRunError("case_review_incomplete_or_binding_invalid")
        for role in ("counter", "verifier"):
            result = values[role]
            _parse(CaseReview, result.get("review"), "case_review_result_invalid")
            if (result.get("status") != "review_submitted" or not 1 <= result.get("model_calls", 0) <= scope.max_reviewer_model_turns
                    or result.get("tool_calls", 0) > scope.max_reviewer_tool_actions):
                raise ContainerRunError("case_review_result_or_budget_invalid")
        return {"status": "pass", "phase": values["phase"], "model_turn_count": sum(values[r]["model_calls"] for r in ("counter", "verifier")),
            "tool_action_count": sum(values[r]["tool_calls"] for r in ("counter", "verifier")),
            "material_finding_count": values["material_finding_count"], "state_digest": _digest(raw),
            "acceptance_scope": "independent_case_review_handoff_only_not_repaired_report_or_product_pass"}
    if authority.workflow == "lead_research_delegation":
        return _lead_terminal(raw, authority)
    if authority.workflow == "workpaper_review_repair":
        return _review_terminal(raw, authority)
    values = raw.get("values")
    if not isinstance(values, Mapping) or raw.get("interrupts") not in (None, [], ()) or raw.get("next") not in (None, [], ()):
        raise ContainerRunError("paid_shadow_terminal_state_invalid")
    notebook = _parse(SpecialistNotebook, values.get("notebook"), "paid_shadow_notebook_invalid")
    if (
        values.get("run_id") != authority.research_run_id
        or values.get("run_invocation_id") != authority.run_invocation_id
        or notebook.agent_id != authority.node_id
        or not 1 <= notebook.model_turn_count <= authority.max_model_turns
        or notebook.tool_action_count > authority.max_tool_actions
        or any(
            record.turn_source != "provider_model"
            or not record.model_execution_evidence
            or record.runtime_receipt is None
            or record.runtime_receipt.kind != "model"
            or record.runtime_receipt.actor != authority.node_id
            or record.runtime_receipt.transport_attempts != 1
            for record in notebook.model_turn_records
        )
    ):
        raise ContainerRunError("paid_shadow_terminal_binding_invalid")
    phase = values.get("phase")
    if phase == "specialist_submission_accepted":
        output = _parse(SubmitWorkpaperAction, values.get("final_submission"), "paid_shadow_submission_invalid")
        status = "pass"
    elif phase == "specialist_human_review_handoff_emitted":
        output = _parse(SpecialistHumanReviewHandoff, values.get("human_review_handoff"), "paid_shadow_handoff_invalid")
        status = "bounded_handoff"
    else:
        raise ContainerRunError("paid_shadow_terminal_phase_invalid")
    return {
        "status": status,
        "phase": phase,
        "state_digest": _digest(raw),
        "output_digest": canonical_sha256(output),
        "notebook_digest": notebook.notebook_digest,
        "model_turn_count": notebook.model_turn_count,
        "tool_action_count": notebook.tool_action_count,
    }


def _review_terminal(raw: Mapping[str, Any], authority: DellQ1SpecialistPaidShadowAuthority) -> dict[str, Any]:
    values = raw.get("values")
    if not isinstance(values, Mapping) or values.get("phase") not in {"review_cycle_accepted", "review_cycle_needs_attention"}:
        raise ContainerRunError("review_cycle_terminal_missing")
    if values.get("run_id") != authority.research_run_id or values.get("run_invocation_id") != authority.run_invocation_id:
        raise ContainerRunError("review_cycle_identity_mismatch")
    reviews, repairs = values.get("review_results", []), values.get("repair_results", [])
    if len(repairs) > 1 or len(reviews) not in {2, 4}:
        raise ContainerRunError("review_cycle_topology_invalid")
    turns, actions, actors = 0, 0, []
    for row in [*reviews, *repairs]:
        state = row["agent_state"]
        notebook = _parse(SpecialistNotebook, state.get("notebook"), "review_notebook_invalid")
        is_repair = "parent_submission_digest" in row
        limit = authority.max_model_turns if is_repair else authority.review_scope.max_reviewer_model_turns
        tool_limit = authority.max_tool_actions if is_repair else authority.review_scope.max_reviewer_tool_actions
        if (not 1 <= notebook.model_turn_count <= limit or notebook.tool_action_count > tool_limit
            or notebook.run_id != authority.research_run_id or notebook.run_invocation_id != authority.run_invocation_id
            or (is_repair and notebook.agent_id != authority.node_id)
            or (not is_repair and not notebook.agent_id.startswith(row["role"] + ":"))):
            raise ContainerRunError("review_child_budget_or_identity_invalid")
        if any(r.turn_source != "provider_model" or r.runtime_receipt is None
               or r.runtime_receipt.actor != notebook.agent_id or r.runtime_receipt.transport_attempts != 1
               for r in notebook.model_turn_records):
            raise ContainerRunError("review_child_model_proof_invalid")
        if state.get("phase") == "specialist_submission_accepted":
            _parse(SubmitWorkpaperAction if is_repair else SubmitReviewAction, state["final_submission"], "review_child_terminal_invalid")
        else:
            _parse(SpecialistHumanReviewHandoff, state.get("human_review_handoff"), "review_child_handoff_invalid")
        turns += notebook.model_turn_count
        actions += notebook.tool_action_count
        actors.append(notebook.agent_id)
    _parse(SubmitWorkpaperAction, values["final_submission"], "review_workpaper_missing")
    return {"status": "pass" if values["phase"] == "review_cycle_accepted" else "bounded_handoff",
            "phase": values["phase"], "review_stop_reason": values.get("review_stop_reason"),
            "model_turn_count": turns, "tool_action_count": actions,
            "reviewer_executions": len(reviews), "author_revisions": len(repairs), "actors": actors,
            "output_digest": canonical_sha256(values["final_submission"]),
            "acceptance_scope": "Q1_multi_agent_review_cycle_only_not_full_case_or_human_product_acceptance"}


def _lead_terminal(raw: Mapping[str, Any], authority: DellQ1SpecialistPaidShadowAuthority) -> dict[str, Any]:
    values, scope = raw.get("values"), authority.lead_scope
    if (not isinstance(values, Mapping) or raw.get("interrupts") not in (None, [], ())
            or raw.get("next") not in (None, [], ()) or values.get("phase")
            not in {"research_ready_for_review", "research_needs_attention"}):
        raise ContainerRunError("lead_research_terminal_state_invalid")
    if values.get("run_id") != authority.research_run_id or values.get("run_invocation_id") != authority.run_invocation_id:
        raise ContainerRunError("lead_research_identity_invalid")
    lead_turns, tasks, results = values.get("lead_turns", []), values.get("tasks", []), values.get("task_results", [])
    if not 1 <= len(lead_turns) <= scope.max_lead_model_turns or len(tasks) > scope.max_tasks:
        raise ContainerRunError("lead_research_capacity_invalid")
    for turn in lead_turns:
        receipt = _parse(RuntimeReceipt, turn.get("runtime_receipt"), "lead_model_receipt_invalid")
        if (turn.get("turn_source") != "provider_model" or receipt.kind != "model" or receipt.status != "success"
                or receipt.actor != "lead:research-delegation" or receipt.transport_attempts != 1
                or receipt.output_digest != canonical_sha256(turn["action"])):
            raise ContainerRunError("lead_model_proof_invalid")
    registered = {task["task_id"]: task for task in tasks}
    if len(registered) != len(tasks) or len({row["task_id"] for row in results}) != len(results):
        raise ContainerRunError("lead_duplicate_task_result")
    turns, actions, actors, submitted, branches = len(lead_turns), 0, ["lead:research-delegation"], set(), set()
    for row in results:
        state = row["agent_state"]
        notebook = _parse(SpecialistNotebook, state.get("notebook"), "lead_child_notebook_invalid")
        task = registered.get(row["task_id"])
        if (task is None or notebook.task_id != task["task_id"]
                or list(task["coverage_obligation_ids"]) != [notebook.branch_id]
                or notebook.branch_id not in scope.allowed_branch_ids
                or notebook.run_id != authority.research_run_id or notebook.run_invocation_id != authority.run_invocation_id
                or not 1 <= notebook.model_turn_count <= authority.max_model_turns
                or notebook.tool_action_count > authority.max_tool_actions):
            raise ContainerRunError("lead_child_identity_scope_or_budget_invalid")
        if any(r.turn_source != "provider_model" or not r.model_execution_evidence or r.runtime_receipt is None
               or r.runtime_receipt.kind != "model" or r.runtime_receipt.status != "success"
               or r.runtime_receipt.actor != notebook.agent_id or r.runtime_receipt.transport_attempts != 1
               for r in notebook.model_turn_records):
            raise ContainerRunError("lead_child_model_proof_invalid")
        if row["status"] == "submitted":
            validate_workpaper_state(state)
            submitted.add(row["task_id"])
            branches.add(notebook.branch_id)
        elif row["status"] == "needs_attention" and state.get("phase") == "specialist_human_review_handoff_emitted":
            _parse(SpecialistHumanReviewHandoff, state.get("human_review_handoff"), "lead_child_handoff_invalid")
        else:
            raise ContainerRunError("lead_child_outcome_invalid")
        turns += notebook.model_turn_count
        actions += notebook.tool_action_count
        actors.append(notebook.agent_id)
    ready = values["phase"] == "research_ready_for_review"
    handoff = values.get("lead_handoff")
    if handoff is not None:
        parsed = _parse(SubmitResearchHandoffAction, handoff, "lead_handoff_invalid")
        if (set(parsed.acknowledged_incomplete_task_ids) != set(registered) - submitted
                or ready != (parsed.disposition == "ready_for_review")):
            raise ContainerRunError("lead_handoff_completion_mismatch")
    elif ready or values.get("stop_reason") != "lead_turn_ceiling":
        raise ContainerRunError("lead_terminal_handoff_missing")
    # Entry composition independently validates the immutable reviewed Q1 seed;
    # it is reused research, not a newly executed child or newly billed work.
    seeded_branches = {"Q1_ISSUER_TRUTH"}
    if ready and (set(registered) != submitted or not set(scope.allowed_branch_ids).issubset(branches | seeded_branches)):
        raise ContainerRunError("lead_required_workpapers_not_completed")
    return {"status": "pass" if ready else "bounded_handoff", "phase": values["phase"],
            "stop_reason": values.get("stop_reason"), "model_turn_count": turns, "tool_action_count": actions,
            "lead_model_turn_count": len(lead_turns), "specialist_executions": len(results),
            "submitted_task_ids": sorted(submitted), "actors": actors,
            "state_digest": _digest(raw), "output_digest": canonical_sha256(handoff),
            "required_branch_ids": list(scope.allowed_branch_ids), "reused_seed_branch_ids": sorted(seeded_branches),
            "acceptance_scope": "Lead_research_handoff_only_not_independent_review_final_report_or_product_acceptance"}


def _audit(authority: DellQ1SpecialistPaidShadowAuthority, turns: int) -> dict[str, Any]:
    path = Path(authority.artifact_root_container) / authority.model_audit_filename
    try:
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ContainerRunError("paid_shadow_model_audit_invalid") from None
    outcomes = [row for row in records if row.get("event") == "outcome" and row.get("status") == "success"]
    if len(records) != 2 * turns or len(outcomes) != turns or any(
        row.get("paid_execution_id") != authority.paid_full_chain_execution_id
        or row.get("authority_decision_digest") != authority.decision_digest
        for row in records
    ):
        raise ContainerRunError("paid_shadow_model_audit_mismatch")
    return {
        "filename": authority.model_audit_filename,
        "sha256": file_sha256(path),
        "model_call_count": turns,
        "input_tokens": sum(int(row.get("input_tokens") or 0) for row in outcomes),
        "output_tokens": sum(int(row.get("output_tokens") or 0) for row in outcomes),
        "total_tokens": sum(int(row.get("total_tokens") or 0) for row in outcomes),
        "elapsed_ms": sum(float(row.get("elapsed_ms") or 0) for row in outcomes),
    }


def _trace(server_run_id: str, session: Any, run: Any, invocation: Any) -> dict[str, Any]:
    root = None
    client = LangSmithClient(auto_batch_tracing=False)
    # Read-only ingestion polling; it never repeats the run or a model call.
    for delay in (0, 2, 5, 10, 15):
        if delay:
            time.sleep(delay)
        try:
            rows = list(islice(client.list_runs(
                project_name=LANGSMITH_PROJECT,
                is_root=True,
                run_ids=[server_run_id],
                select=("id", "trace_id", "parent_run_id", "end_time", "error", "inputs", "outputs", "extra"),
            ), 2))
        except Exception:
            raise ContainerRunError("paid_shadow_langsmith_query_failed") from None
        if len(rows) == 1 and rows[0].end_time is not None:
            root = rows[0]
            break
    if (
        root is None
        or str(root.id) != server_run_id
        or str(root.trace_id) != server_run_id
        or root.parent_run_id is not None
        or root.error is not None
        or root.inputs not in ({}, None)
        or root.outputs not in ({}, None)
    ):
        raise ContainerRunError("paid_shadow_langsmith_root_invalid")
    extra = root.extra if isinstance(root.extra, Mapping) else {}
    metadata = extra.get("metadata") if isinstance(extra.get("metadata"), Mapping) else {}
    expected = {
        "fin_client_schema_version": DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION,
        "execution_profile": PRODUCT_EXECUTION_PROFILE,
        "agent_session_id": session.session_id,
        "research_run_id": run.run_id,
        "run_invocation_id": invocation.invocation_id,
        "session_identity_digest": agent_session_identity_digest(session),
        "research_run_identity_digest": research_run_identity_digest(run),
        "run_invocation_identity_digest": run_invocation_identity_digest(invocation),
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ContainerRunError("paid_shadow_langsmith_metadata_invalid")
    return {"project": LANGSMITH_PROJECT, "trace_id": server_run_id, "root_run_id": server_run_id, "inputs_outputs_hidden": True}


def main() -> None:
    try:
        authority = load_dell_q1_paid_shadow_authority(
            os.environ.get("FINSIGHT_DELL_PAID_SHADOW_AUTHORITY_PATH", "")
        )
        require_runtime_authority_binding(
            authority,
            agent_session_id=authority.agent_session_id,
            research_run_id=authority.research_run_id,
            run_invocation_id=authority.run_invocation_id,
            implementation_commit=os.environ.get("FINSIGHT_DELL_IMPLEMENTATION_COMMIT", ""),
        )
        session, research_run, invocation, graph_input = _contracts_and_input(authority)
        runtime_uri = os.environ.get("FIN_RUNTIME_POSTGRES_URI", "")
        if not runtime_uri:
            raise ContainerRunError("paid_shadow_fin_runtime_uri_missing")
        with ConnectionPool(runtime_uri, min_size=1, max_size=2, open=True, timeout=10) as pool:
            pool.wait(timeout=10)
            repository = PostgresDellAgentServerIdentityRepository(pool)
            with DellAgentServerClient.connect(
                url=SERVER_URL,
                identity_repository=repository,
                execution_profile=PRODUCT_EXECUTION_PROFILE,
            ) as client:
                session_binding = client.create_agent_session(agent_session=session)
                run_binding = client.start_specialist_run(
                    session=session_binding,
                    research_run=research_run,
                    run_invocation=invocation,
                    graph_input=graph_input,
                )
                stream = _stream(client.join_updates(run_binding, last_event_id="-1"))
                state = client.get_state(session_binding)
        private_path = Path(authority.artifact_root_container) / "specialist-final-state.private.json"
        # Keep completed sibling/revision evidence even if another child failed.
        # Archiving an error checkpoint never changes its acceptance state.
        _write_new(private_path, state)
        terminal = _terminal(state, authority)
        result = {
            "status": terminal["status"],
            "paid_execution_id": authority.paid_full_chain_execution_id,
            "agent_session_id": session.session_id,
            "fin_thread_id": session.thread_id,
            "research_run_id": research_run.run_id,
            "run_invocation_id": invocation.invocation_id,
            "server_thread_id": session_binding.server_thread_id,
            "server_run_id": run_binding.server_run_id,
            "graph_input_digest": _digest(graph_input),
            "stream": stream,
            "terminal": terminal,
            "private_state": {"filename": private_path.name, "sha256": file_sha256(private_path)},
            "model_audit": _audit(authority, terminal["model_turn_count"]),
            "langsmith": _trace(run_binding.server_run_id, session, research_run, invocation),
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    except Exception as exc:
        print(json.dumps({
            "status": "failed",
            "failure_code": str(getattr(exc, "code", "paid_shadow_container_failed")),
        }, sort_keys=True), flush=True)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
