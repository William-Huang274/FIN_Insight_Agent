from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.research.run_s3_current_research_consumer_canary import (  # noqa: E402
    _compile_runtime_input,
    _tool_loop_contracts,
)
from sec_agent.providers.agent_protocol import (  # noqa: E402
    ANTHROPIC_MESSAGES_WIRE,
    CHAT_COMPLETIONS_WIRE,
    RESPONSES_WIRE,
    canonicalize_tool_definitions,
    compile_agent_request_projection,
    load_agent_transport_profile,
    project_tool_definitions,
)
from sec_agent.research.bounded_finance_loop import (  # noqa: E402
    BoundedFinanceLoopError,
    READ_NUMERIC_FACTS_TOOL,
    READ_REVIEWED_EVIDENCE_TOOL,
    SUBMIT_EVIDENCE_REQUEST_TOOL,
    SUBMIT_RESEARCH_JUDGMENT_TOOL,
    compile_finance_loop_messages,
    compile_finance_loop_tools,
    load_bounded_finance_loop_policy,
    run_bounded_finance_loop,
    scope_bounded_finance_loop_policy,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest  # noqa: E402


AUTHORITY_SCHEMA = "fin_ia_s3_tool_contract_transport_zero_call_authority_v1_0"
RESULT_SCHEMA = "fin_ia_s3_tool_contract_transport_zero_call_result_v1_0"
WIRES = (
    CHAT_COMPLETIONS_WIRE,
    RESPONSES_WIRE,
    ANTHROPIC_MESSAGES_WIRE,
)


class ToolContractTransportProofError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _resolve(ref: str) -> Path:
    relative = PurePosixPath(str(ref or ""))
    if relative.is_absolute() or "\\" in str(ref) or ".." in relative.parts:
        raise ToolContractTransportProofError("transport_proof_path_invalid")
    path = ROOT.joinpath(*relative.parts).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise ToolContractTransportProofError("transport_proof_path_escape") from exc
    return path


def _relative(path: str | Path) -> str:
    return Path(path).resolve().relative_to(ROOT).as_posix()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ToolContractTransportProofError("transport_proof_json_object_required")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode:
        raise ToolContractTransportProofError("transport_proof_git_unavailable")
    return completed.stdout.strip()


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    except FileExistsError as exc:
        raise ToolContractTransportProofError(
            "transport_proof_exact_once_output_exists"
        ) from exc


def _validate_authority(
    payload: Mapping[str, Any], *, authority_path: Path
) -> tuple[dict[str, Path], dict[str, Path]]:
    if not (
        payload.get("schema_version") == AUTHORITY_SCHEMA
        and payload.get("status")
        == "signed_zero_network_zero_model_tool_contract_transport_replay"
    ):
        raise ToolContractTransportProofError("transport_proof_authority_invalid")
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ToolContractTransportProofError("transport_proof_commit_invalid")
    if _git("rev-parse", "HEAD").lower() != commit:
        raise ToolContractTransportProofError("transport_proof_head_drift")
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise ToolContractTransportProofError("transport_proof_upstream_drift")
    status = [
        row
        for row in _git(
            "status", "--porcelain=v1", "--untracked-files=all"
        ).splitlines()
        if row
    ]
    if status != [f"?? {_relative(authority_path)}"]:
        raise ToolContractTransportProofError("transport_proof_worktree_not_clean")
    if payload.get("execution_budget") != {
        "network_calls": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "embedding_calls": 0,
        "retries": 0,
        "product_pointer_mutations": 0,
    }:
        raise ToolContractTransportProofError("transport_proof_budget_invalid")
    bound = payload.get("bound_inputs")
    output = payload.get("output_contract")
    if not isinstance(bound, Mapping) or not isinstance(output, Mapping):
        raise ToolContractTransportProofError("transport_proof_shape_invalid")
    required_refs = {
        "consumer_policy_ref",
        "objective_ref",
        "planner_atoms_ref",
        "loop_policy_ref",
        "fake_judgment_ref",
        "r2_request_capture_ref",
        "r2_response_capture_ref",
        "r2_live_result_ref",
        "chat_profile_ref",
        "responses_profile_ref",
        "anthropic_profile_ref",
        "runtime_input_compiler_ref",
        "finance_loop_implementation_ref",
        "tool_contract_implementation_ref",
        "protocol_implementation_ref",
        "dispatch_implementation_ref",
        "proof_runner_ref",
    }
    ref_keys = {str(key) for key in bound if str(key).endswith("_ref")}
    expected_keys = {
        value
        for key in ref_keys
        for value in (key, key[:-4] + "_sha256")
    }
    if ref_keys != required_refs or set(bound) != expected_keys:
        raise ToolContractTransportProofError("transport_proof_bindings_invalid")
    paths: dict[str, Path] = {}
    for key in ref_keys:
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(bound[key[:-4] + "_sha256"]):
            raise ToolContractTransportProofError(
                f"transport_proof_bound_input_drift:{key}"
            )
        paths[key] = path
    if set(output) != {"private_result_ref", "public_result_ref"}:
        raise ToolContractTransportProofError("transport_proof_output_invalid")
    outputs = {key: _resolve(str(value)) for key, value in output.items()}
    if any(path.exists() for path in outputs.values()):
        raise ToolContractTransportProofError(
            "transport_proof_exact_once_identity_consumed"
        )
    return paths, outputs


@dataclass(frozen=True)
class _ReplayStep:
    index: int
    tool_calls: tuple[Mapping[str, Any], ...]

    provider_id: str = "immutable_capture_replay"
    model: str = "deepseek-v4-pro"

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model": self.model,
            "tool_calls": [deepcopy(dict(row)) for row in self.tool_calls],
            "finish_reason": "tool_calls",
            "usage": {"total_tokens": 0},
            "request_capture_ref": f"zero-call/request-{self.index}.json",
            "response_capture_ref": f"zero-call/response-{self.index}.json",
            "request_digest": canonical_digest({"step": self.index, "side": "request"}),
            "response_digest": canonical_digest({"step": self.index, "side": "response"}),
            "reasoning_content_persisted": False,
        }

    def continuation_assistant_message(self) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [deepcopy(dict(row)) for row in self.tool_calls],
        }


def _step(index: int, calls: Sequence[tuple[str, Mapping[str, Any]]]) -> _ReplayStep:
    return _ReplayStep(
        index=index,
        tool_calls=tuple(
            {
                "id": f"replay-call-{index}-{offset}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            }
            for offset, (name, arguments) in enumerate(calls)
        ),
    )


def _captured_call(capture: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    try:
        raw = capture["response_body"]["choices"][0]["message"]["tool_calls"][0]
        name = str(raw["function"]["name"])
        arguments = json.loads(str(raw["function"]["arguments"]))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ToolContractTransportProofError(
            "transport_proof_r2_response_shape_invalid"
        ) from exc
    if not isinstance(arguments, dict):
        raise ToolContractTransportProofError(
            "transport_proof_r2_arguments_invalid"
        )
    return name, arguments


def _proposal_schema(canonical_tools: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    return next(
        row["input_schema"]
        for row in canonical_tools
        if row["name"] == SUBMIT_EVIDENCE_REQUEST_TOOL
    )


def _execute(paths: Mapping[str, Path]) -> dict[str, Any]:
    _, research_input, _ = _compile_runtime_input(
        paths,
        case_key="DELL",
        required_cell_ids=["CELL::value_capture"],
    )
    kernel, route, planning = _tool_loop_contracts(paths)
    base_policy = load_bounded_finance_loop_policy(_json(paths["loop_policy_ref"]))
    policy = scope_bounded_finance_loop_policy(
        base_policy, cell_count=1, maximum_evidence_requests=3
    )
    cell_id = "CELL::value_capture"
    tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        policy=policy,
        strict=False,
    )
    messages = compile_finance_loop_messages(
        research_input=research_input,
        required_cell_ids=[cell_id],
        execution_budget={
            "maximum_steps": policy.maximum_steps,
            "maximum_evidence_requests": 3,
            "maximum_reads_per_cell": 1,
            "maximum_parallel_read_tools": 2,
            "maximum_judgments_per_cell": 1,
            "retry_count": 0,
        },
    )
    canonical_tools = canonicalize_tool_definitions(
        tools, wire_api=CHAT_COMPLETIONS_WIRE
    )

    profiles = [
        load_agent_transport_profile(_json(paths[f"{name}_profile_ref"]))
        for name in ("chat", "responses", "anthropic")
    ]
    if tuple(row.wire_api for row in profiles) != WIRES:
        raise ToolContractTransportProofError("transport_proof_profile_wire_drift")

    current_projection_digests: dict[str, str] = {}
    for wire in WIRES:
        projected_tools = project_tool_definitions(canonical_tools, wire_api=wire)
        if canonicalize_tool_definitions(projected_tools, wire_api=wire) != canonical_tools:
            raise ToolContractTransportProofError(
                "transport_proof_current_tool_roundtrip_drift"
            )
        projection = compile_agent_request_projection(
            messages=messages,
            canonical_tools=canonical_tools,
            wire_api=wire,
        )
        current_projection_digests[wire] = canonical_digest(projection)

    r2_request = _json(paths["r2_request_capture_ref"])
    old_body = r2_request.get("request_body")
    if not isinstance(old_body, Mapping):
        raise ToolContractTransportProofError("transport_proof_r2_request_shape_invalid")
    old_tools = old_body.get("tools")
    old_messages = old_body.get("messages")
    if not isinstance(old_tools, list) or not isinstance(old_messages, list):
        raise ToolContractTransportProofError("transport_proof_r2_request_shape_invalid")
    old_canonical = canonicalize_tool_definitions(
        old_tools, wire_api=CHAT_COMPLETIONS_WIRE
    )
    old_projection_digests: dict[str, str] = {}
    for wire in WIRES:
        projected_tools = project_tool_definitions(old_canonical, wire_api=wire)
        if canonicalize_tool_definitions(projected_tools, wire_api=wire) != old_canonical:
            raise ToolContractTransportProofError(
                "transport_proof_r2_tool_roundtrip_drift"
            )
        old_projection_digests[wire] = canonical_digest(
            compile_agent_request_projection(
                messages=old_messages,
                canonical_tools=old_canonical,
                wire_api=wire,
            )
        )

    r2_name, r2_arguments = _captured_call(
        _json(paths["r2_response_capture_ref"])
    )
    if r2_name != SUBMIT_EVIDENCE_REQUEST_TOOL:
        raise ToolContractTransportProofError("transport_proof_r2_tool_name_invalid")
    gap_ref = str(r2_arguments["gap_ref"])
    valid_repair = {
        "cell_id": cell_id,
        "gap_ref": gap_ref,
        "target_entity": "DELL",
        "requested_facet_id": "pricing_and_mix",
        "metric_intents": ["average_selling_price"],
        "product_intents": ["server mix and gross margin evidence"],
    }
    fake = _json(paths["fake_judgment_ref"])
    judgment = deepcopy(
        next(row for row in fake["cells"] if row["cell_id"] == cell_id)
    )
    receipts: list[dict[str, Any]] = []
    sequence = (
        _step(
            1,
            (
                (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
                (READ_NUMERIC_FACTS_TOOL, {"cell_id": cell_id}),
            ),
        ),
        _step(2, ((r2_name, r2_arguments),)),
        _step(3, ((SUBMIT_EVIDENCE_REQUEST_TOOL, valid_repair),)),
        _step(4, ((SUBMIT_RESEARCH_JUDGMENT_TOOL, judgment),)),
    )
    result = run_bounded_finance_loop(
        policy=policy,
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
        tools=tools,
        step_executor=lambda _messages, _tools, index: sequence[index - 1],
        receipt_recorder=lambda row: receipts.append(dict(row)),
        visible_execution_budget={
            "maximum_steps": policy.maximum_steps,
            "maximum_evidence_requests": 3,
            "maximum_reads_per_cell": 1,
            "maximum_parallel_read_tools": 2,
            "maximum_judgments_per_cell": 1,
            "retry_count": 0,
        },
    ).as_dict()
    r2_receipt = receipts[2]
    # The receipt intentionally stores only a digest. The actual rejection is
    # visible to the next model step, and the resulting path is proven by the
    # accepted repair plus the absence of an R2 proposal in the final result.
    if len(result["proposed_evidence_requests"]) != 1:
        raise ToolContractTransportProofError("transport_proof_r2_repair_path_invalid")
    prior_live = _json(paths["r2_live_result_ref"])
    if not (
        prior_live.get("status") == "terminal_failed_no_retry"
        and prior_live.get("failure_code")
        == "finance_loop_evidence_request_intents_invalid"
        and prior_live.get("execution", {}).get("model_calls_attempted") == 2
    ):
        raise ToolContractTransportProofError(
            "transport_proof_r2_prior_result_drift"
        )

    cross_case_failures: dict[str, str] = {}
    subjects = {"DELL": "DELL", "MU": "MU", "NVDA": "NVDA"}
    contaminants = {"DELL": "MU", "MU": "NVDA", "NVDA": "DELL"}
    for case_key, subject in subjects.items():
        case_input = deepcopy(research_input)
        case_input["case_identity"]["case_key"] = case_key
        case_input["case_identity"]["subject_ticker"] = subject
        case_tools = compile_finance_loop_tools(
            research_input=case_input,
            required_cell_ids=[cell_id],
            kernel=kernel,
            route_policy=route,
            policy=policy,
            strict=False,
        )
        case_canonical = canonicalize_tool_definitions(
            case_tools, wire_api=CHAT_COMPLETIONS_WIRE
        )
        pricing_branch = next(
            branch
            for branch in _proposal_schema(case_canonical)["oneOf"]
            if branch["properties"]["requested_facet_id"].get("const")
            == "pricing_and_mix"
        )
        if pricing_branch["properties"]["target_entity"]["enum"] != [subject]:
            raise ToolContractTransportProofError(
                "transport_proof_case_identity_contract_drift"
            )
        invalid = deepcopy(valid_repair)
        invalid["target_entity"] = contaminants[case_key]
        try:
            run_bounded_finance_loop(
                policy=policy,
                research_input=case_input,
                required_cell_ids=[cell_id],
                kernel=kernel,
                route_policy=route,
                planning_policy=planning,
                tools=case_tools,
                step_executor=lambda _m, _t, index, bad=invalid: (
                    _step(
                        1,
                        (
                            (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
                            (READ_NUMERIC_FACTS_TOOL, {"cell_id": cell_id}),
                        ),
                    )
                    if index == 1
                    else _step(2, ((SUBMIT_EVIDENCE_REQUEST_TOOL, bad),))
                ),
            )
        except BoundedFinanceLoopError as exc:
            cross_case_failures[case_key] = exc.code
        else:
            raise ToolContractTransportProofError(
                "transport_proof_cross_case_mutation_did_not_fail"
            )

    return {
        "research_input_digest": research_input["research_input_digest"],
        "current_tool_contract_digest": canonical_digest(list(canonical_tools)),
        "r2_old_tool_contract_digest": canonical_digest(list(old_canonical)),
        "current_projection_digests": current_projection_digests,
        "r2_projection_digests": old_projection_digests,
        "r2_failure_code_before_fix": prior_live["failure_code"],
        "r2_replay_status_after_fix": "rejected_not_executed_then_repaired",
        "r2_rejected_request_promoted": False,
        "r2_valid_repair_request_count": len(result["proposed_evidence_requests"]),
        "r2_replay_completed": result["status"] == "completed_all_required_cells",
        "r2_replay_step_count": result["step_count"],
        "r2_replay_receipt_count": len(receipts),
        "r2_rejected_receipt_digest": r2_receipt["tool_result_digest"],
        "cross_case_mutation_failures": cross_case_failures,
        "anthropic_live_qualified": False,
        "network_calls": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "embedding_calls": 0,
    }


def run(authority_path: Path) -> dict[str, Any]:
    authority = _json(authority_path)
    paths, outputs = _validate_authority(authority, authority_path=authority_path)
    normalized = _execute(paths)
    expected_cross_case = {
        case: "finance_loop_evidence_request_target_out_of_scope"
        for case in ("DELL", "MU", "NVDA")
    }
    if not (
        normalized["r2_replay_completed"] is True
        and normalized["r2_rejected_request_promoted"] is False
        and normalized["r2_valid_repair_request_count"] == 1
        and normalized["cross_case_mutation_failures"] == expected_cross_case
    ):
        raise ToolContractTransportProofError("transport_proof_acceptance_failed")
    body = {
        "schema_version": RESULT_SCHEMA,
        "status": "zero_call_tool_contract_and_transport_replay_pass",
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "normalized_proof": normalized,
        "known_boundary": (
            "This proves deterministic contract repair, three-wire projection, "
            "three-case identity isolation and R2 capture replay with zero provider "
            "calls. It does not qualify Anthropic live, natural model behavior, "
            "five-cell research quality, S3 acceptance or release."
        ),
    }
    result = {**body, "result_digest": canonical_digest(body)}
    _write_new(outputs["private_result_ref"], result)
    _write_new(outputs["public_result_ref"], result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", required=True)
    args = parser.parse_args(argv)
    result = run(_resolve(args.authority))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
