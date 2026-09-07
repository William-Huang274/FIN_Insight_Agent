from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
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
from sec_agent.providers import (  # noqa: E402
    CHAT_COMPLETIONS_WIRE,
    RESPONSES_WIRE,
    canonicalize_tool_definitions,
    load_agent_transport_profile,
    validate_deepseek_ga_live_transport,
)
from sec_agent.research.bounded_finance_loop import (  # noqa: E402
    compile_finance_loop_messages,
    compile_finance_loop_tools,
    load_bounded_finance_loop_policy,
    scope_bounded_finance_loop_policy,
)
from sec_agent.research.live_transport_lane import (  # noqa: E402
    execute_finance_loop_transport_lane,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest  # noqa: E402


AUTHORITY_SCHEMA = "fin_ia_s3_deepseek_ga_transport_paired_authority_v1_0"
RESULT_SCHEMA = "fin_ia_s3_deepseek_ga_transport_paired_result_v1_0"
FULL_SCHEMA = "fin_ia_s3_deepseek_ga_transport_paired_full_v1_0"


class TransportPairedCanaryError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _resolve(ref: str) -> Path:
    relative = PurePosixPath(str(ref or ""))
    if relative.is_absolute() or "\\" in str(ref) or ".." in relative.parts:
        raise TransportPairedCanaryError("transport_paired_path_invalid")
    path = ROOT.joinpath(*relative.parts).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise TransportPairedCanaryError("transport_paired_path_escape") from exc
    return path


def _relative(path: str | Path) -> str:
    return Path(path).resolve().relative_to(ROOT).as_posix()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TransportPairedCanaryError("transport_paired_json_object_required")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
        raise TransportPairedCanaryError("transport_paired_git_unavailable")
    return completed.stdout.strip()


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    except FileExistsError as exc:
        raise TransportPairedCanaryError(
            "transport_paired_exact_once_output_exists"
        ) from exc


def _validate_authority(
    payload: Mapping[str, Any], *, authority_path: Path
) -> tuple[dict[str, Path], dict[str, Any]]:
    if not (
        payload.get("schema_version") == AUTHORITY_SCHEMA
        and payload.get("status")
        == "signed_exact_once_DELL_single_cell_chat_responses_paired_canary"
        and payload.get("case_key") == "DELL"
        and payload.get("required_cell_ids") == ["CELL::value_capture"]
    ):
        raise TransportPairedCanaryError("transport_paired_authority_invalid")
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise TransportPairedCanaryError("transport_paired_commit_invalid")
    if _git("rev-parse", "HEAD").lower() != commit:
        raise TransportPairedCanaryError("transport_paired_head_drift")
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise TransportPairedCanaryError("transport_paired_upstream_drift")
    status = [
        row
        for row in _git(
            "status", "--porcelain=v1", "--untracked-files=all"
        ).splitlines()
        if row
    ]
    if status != [f"?? {_relative(authority_path)}"]:
        raise TransportPairedCanaryError("transport_paired_worktree_not_clean")
    if payload.get("execution_budget") != {
        "maximum_lanes": 2,
        "maximum_model_calls_per_lane": 6,
        "maximum_model_calls_total": 12,
        "maximum_transport_attempts_total": 12,
        "maximum_evidence_requests_per_lane": 3,
        "retries": 0,
        "fallbacks": 0,
        "planner_calls": 0,
        "external_retrieval_calls": 0,
        "embedding_calls": 0,
        "current_product_pointer_mutations": 0,
    }:
        raise TransportPairedCanaryError("transport_paired_budget_invalid")
    bound = payload.get("bound_inputs")
    output = payload.get("output_contract")
    if not isinstance(bound, Mapping) or not isinstance(output, Mapping):
        raise TransportPairedCanaryError("transport_paired_shape_invalid")
    required_refs = {
        "consumer_policy_ref",
        "objective_ref",
        "planner_atoms_ref",
        "current_evidence_pack_result_ref",
        "runtime_registry_ref",
        "clean_transport_proof_ref",
        "loop_policy_ref",
        "chat_profile_ref",
        "responses_profile_ref",
        "runner_ref",
        "runtime_input_compiler_ref",
        "live_lane_implementation_ref",
        "finance_loop_implementation_ref",
        "tool_contract_implementation_ref",
        "protocol_implementation_ref",
        "dispatch_implementation_ref",
        "chat_transport_ref",
        "responses_transport_ref",
    }
    runtime_digests = {
        "research_input_digest",
        "finance_loop_messages_digest",
        "chat_tool_contract_digest",
    }
    ref_keys = {str(key) for key in bound if str(key).endswith("_ref")}
    expected_keys = {
        value
        for key in ref_keys
        for value in (key, key[:-4] + "_sha256")
    } | runtime_digests
    if ref_keys != required_refs or set(bound) != expected_keys:
        raise TransportPairedCanaryError("transport_paired_bindings_invalid")
    paths: dict[str, Path] = {}
    for key in ref_keys:
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(bound[key[:-4] + "_sha256"]):
            raise TransportPairedCanaryError(
                f"transport_paired_bound_input_drift:{key}"
            )
        paths[key] = path
    required_output = {
        "capture_root_ref",
        "private_output_root_ref",
        "public_result_ref",
        "run_id",
        "chat_attempt_prefix",
        "responses_attempt_prefix",
        "product_publication",
    }
    if not (
        set(output) == required_output
        and output.get("product_publication") == "forbidden"
        and all(str(output.get(key) or "") for key in required_output)
    ):
        raise TransportPairedCanaryError("transport_paired_output_invalid")
    capture_root = _resolve(str(output["capture_root_ref"]))
    run_id = str(output["run_id"])
    if any(
        path.exists()
        for path in (
            capture_root / f"{run_id}-CHAT",
            capture_root / f"{run_id}-RESPONSES",
            _resolve(str(output["private_output_root_ref"])),
            _resolve(str(output["public_result_ref"])),
        )
    ):
        raise TransportPairedCanaryError(
            "transport_paired_exact_once_identity_consumed"
        )
    return paths, deepcopy(dict(output))


def _relative_captures(value: Any) -> Any:
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).endswith("capture_ref") and str(item or ""):
                output[str(key)] = _relative(str(item))
            else:
                output[str(key)] = _relative_captures(item)
        return output
    if isinstance(value, list):
        return [_relative_captures(item) for item in value]
    return value


def _lane_public(value: Mapping[str, Any]) -> dict[str, Any]:
    loop = value.get("loop_result") if isinstance(value.get("loop_result"), Mapping) else {}
    return {
        "lane": value["lane"],
        "wire_api": value["wire_api"],
        "status": value["status"],
        "model_calls_attempted": value["model_calls_attempted"],
        "tool_counts": dict(loop.get("tool_counts") or {}),
        "step_count": int(loop.get("step_count") or 0),
        "deliverable_digest": str(
            (loop.get("structured_deliverable") or {}).get("deliverable_digest") or ""
        ),
        "failure_phase": value["failure_phase"],
        "failure_code": value["failure_code"],
        "failure_capture_ref": value["failure_capture_ref"],
        "content_assessment_pending": value["status"]
        == "completed_contract_valid_content_assessment_pending",
    }


def run(authority_path: Path) -> dict[str, Any]:
    authority = _json(authority_path)
    paths, output = _validate_authority(authority, authority_path=authority_path)
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
    visible_budget = {
        "maximum_steps": policy.maximum_steps,
        "maximum_evidence_requests": 3,
        "maximum_reads_per_cell": 1,
        "maximum_parallel_read_tools": 2,
        "maximum_judgments_per_cell": 1,
        "retry_count": 0,
    }
    tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=["CELL::value_capture"],
        kernel=kernel,
        route_policy=route,
        policy=policy,
        strict=False,
    )
    messages = compile_finance_loop_messages(
        research_input=research_input,
        required_cell_ids=["CELL::value_capture"],
        execution_budget=visible_budget,
    )
    actual = {
        "research_input_digest": research_input["research_input_digest"],
        "finance_loop_messages_digest": canonical_digest(list(messages)),
        "chat_tool_contract_digest": canonical_digest(list(tools)),
    }
    if any(str(authority["bound_inputs"][key]) != str(value) for key, value in actual.items()):
        raise TransportPairedCanaryError("transport_paired_runtime_binding_drift")
    clean = _json(paths["clean_transport_proof_ref"])
    if not (
        clean.get("status") == "zero_call_tool_contract_and_transport_replay_pass"
        and clean.get("normalized_proof", {}).get("research_input_digest")
        == research_input["research_input_digest"]
        and clean.get("normalized_proof", {}).get("current_tool_contract_digest")
        == canonical_digest(
            list(
                canonicalize_tool_definitions(
                    tools,
                    wire_api=CHAT_COMPLETIONS_WIRE,
                )
            )
        )
    ):
        raise TransportPairedCanaryError("transport_paired_clean_proof_drift")
    chat = load_agent_transport_profile(_json(paths["chat_profile_ref"]))
    responses = load_agent_transport_profile(_json(paths["responses_profile_ref"]))
    validate_deepseek_ga_live_transport(chat)
    validate_deepseek_ga_live_transport(responses)
    if not (
        chat.wire_api == CHAT_COMPLETIONS_WIRE
        and responses.wire_api == RESPONSES_WIRE
    ):
        raise TransportPairedCanaryError("transport_paired_profile_wire_drift")
    capture_root = _resolve(str(output["capture_root_ref"]))
    run_id = str(output["run_id"])
    chat_lane = execute_finance_loop_transport_lane(
        lane="chat_control",
        profile=chat,
        policy=policy,
        research_input=research_input,
        required_cell_ids=["CELL::value_capture"],
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
        visible_execution_budget=visible_budget,
        capture_root=capture_root,
        run_id=f"{run_id}-CHAT",
        attempt_prefix=str(output["chat_attempt_prefix"]),
    ).as_dict()
    responses_lane = execute_finance_loop_transport_lane(
        lane="responses_candidate",
        profile=responses,
        policy=policy,
        research_input=research_input,
        required_cell_ids=["CELL::value_capture"],
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
        visible_execution_budget=visible_budget,
        capture_root=capture_root,
        run_id=f"{run_id}-RESPONSES",
        attempt_prefix=str(output["responses_attempt_prefix"]),
    ).as_dict()
    total_calls = int(chat_lane["model_calls_attempted"]) + int(
        responses_lane["model_calls_attempted"]
    )
    if total_calls > 12:
        raise TransportPairedCanaryError("transport_paired_call_budget_exceeded")
    lanes = [_relative_captures(chat_lane), _relative_captures(responses_lane)]
    both = all(
        row["status"] == "completed_contract_valid_content_assessment_pending"
        for row in lanes
    )
    full_body = {
        "schema_version": FULL_SCHEMA,
        "status": (
            "paired_contract_valid_content_assessment_pending"
            if both
            else "paired_terminal_mixed_or_failed_no_retry"
        ),
        "recorded_at": _now(),
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "required_cell_ids": ["CELL::value_capture"],
        "research_input_digest": research_input["research_input_digest"],
        "same_research_input": True,
        "same_finance_tool_contract": True,
        "lanes": lanes,
        "execution": {
            "model_calls_attempted": total_calls,
            "maximum_model_calls": 12,
            "retries": 0,
            "fallbacks": 0,
            "external_retrieval_calls": 0,
            "embedding_calls": 0,
            "product_publication": False,
        },
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    private_root = _resolve(str(output["private_output_root_ref"]))
    full_path = private_root / "full_result.json"
    _write_new(full_path, full)
    public_body = {
        "schema_version": RESULT_SCHEMA,
        "status": full["status"],
        "recorded_at": full["recorded_at"],
        "authority_ref": full["authority_ref"],
        "authority_sha256": full["authority_sha256"],
        "implementation_commit": full["implementation_commit"],
        "case_key": "DELL",
        "required_cell_ids": ["CELL::value_capture"],
        "research_input_digest": research_input["research_input_digest"],
        "same_research_input": True,
        "same_finance_tool_contract": True,
        "lanes": [_lane_public(row) for row in lanes],
        "execution": full["execution"],
        "full_result_ref": _relative(full_path),
        "full_result_sha256": _sha(full_path),
        "acceptance": {
            "both_transport_contracts_pass": both,
            "paired_content_assessment_pending": both,
            "five_cell_live_authorized": False,
            "s3_product_acceptance": False,
            "qualified_human_acceptance": False,
            "release_ready": False,
        },
        "known_boundary": (
            "This is a same-input DELL value-capture transport comparison only. "
            "It does not authorize Anthropic live, five-cell execution, S3 acceptance "
            "or release; natural content must be assessed after capture preservation."
        ),
    }
    result = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new(_resolve(str(output["public_result_ref"])), result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", required=True)
    args = parser.parse_args(argv)
    result = run(_resolve(args.authority))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "paired_contract_valid_content_assessment_pending" else 2


if __name__ == "__main__":
    raise SystemExit(main())
