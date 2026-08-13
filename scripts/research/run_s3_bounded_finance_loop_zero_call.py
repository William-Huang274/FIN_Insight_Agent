from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "src"):
    value = str(candidate)
    if value not in sys.path:
        sys.path.insert(0, value)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from apps.workbench.backend.application.research_evidence_pack_service import (  # noqa: E402
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from apps.workbench.backend.application.research_retrieval_service import (  # noqa: E402
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from retrieval.contracts import load_financial_research_kernel  # noqa: E402
from retrieval.route_compiler import load_query_object_fact_route_policy  # noqa: E402
from sec_agent.providers import (  # noqa: E402
    ChatCompletionToolStepResult,
    load_chat_completion_profile,
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
    validate_deepseek_ga_json_profile,
    validate_deepseek_ga_profile,
)
from sec_agent.research.current_consumer import (  # noqa: E402
    compile_current_research_input,
)
from sec_agent.research.planning import (  # noqa: E402
    load_research_planning_policy,
)
from sec_agent.research.reviewed_evidence_pack import (  # noqa: E402
    canonical_digest,
)
from sec_agent.runtime_bridge.paths import resolve_runtime_paths  # noqa: E402
from sec_agent.runtime_resource_registry import (  # noqa: E402
    read_registered_runtime_json,
)


AUTHORITY_SCHEMA = "fin_ia_bounded_finance_loop_zero_call_authority_v1_0"
RESULT_SCHEMA = "fin_ia_bounded_finance_loop_zero_call_result_v1_0"


class BoundedFinanceLoopProofError(RuntimeError):
    """The zero-call loop proof was not exactly authorized or reproducible."""


def _resolve(ref: str) -> Path:
    relative = PurePosixPath(str(ref or ""))
    if relative.is_absolute() or "\\" in str(ref) or ".." in relative.parts:
        raise BoundedFinanceLoopProofError("finance_loop_proof_path_invalid")
    path = ROOT.joinpath(*relative.parts).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise BoundedFinanceLoopProofError("finance_loop_proof_path_escape") from exc
    return path


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BoundedFinanceLoopProofError(
            f"finance_loop_proof_json_object_required:{path.name}"
        )
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    except FileExistsError as exc:
        raise BoundedFinanceLoopProofError(
            "finance_loop_proof_exact_once_output_exists"
        ) from exc


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
        raise BoundedFinanceLoopProofError("finance_loop_proof_git_unavailable")
    return completed.stdout.strip()


def _validate_authority(
    payload: Mapping[str, Any],
    *,
    authority_path: Path,
) -> tuple[dict[str, Path], Mapping[str, Any]]:
    if not (
        payload.get("schema_version") == AUTHORITY_SCHEMA
        and payload.get("status")
        == "fresh_zero_network_zero_model_bounded_finance_loop_proof_authorized"
    ):
        raise BoundedFinanceLoopProofError(
            "finance_loop_proof_authority_status_invalid"
        )
    clean = payload.get("clean_implementation")
    budget = payload.get("execution_budget")
    bound = payload.get("bound_inputs")
    output = payload.get("output_contract")
    if not all(isinstance(row, Mapping) for row in (clean, budget, bound, output)):
        raise BoundedFinanceLoopProofError("finance_loop_proof_authority_shape_invalid")
    assert isinstance(clean, Mapping)
    assert isinstance(budget, Mapping)
    assert isinstance(bound, Mapping)
    assert isinstance(output, Mapping)
    commit = str(clean.get("implementation_commit") or "").lower()
    if dict(clean) != {
        "implementation_commit": commit,
        "head_must_equal_implementation_commit": True,
        "upstream_must_equal_implementation_commit": True,
        "tracked_worktree_must_be_clean": True,
        "only_authority_may_be_untracked": True,
    }:
        raise BoundedFinanceLoopProofError("finance_loop_proof_clean_binding_invalid")
    if _git("rev-parse", "HEAD").lower() != commit:
        raise BoundedFinanceLoopProofError("finance_loop_proof_head_drift")
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise BoundedFinanceLoopProofError("finance_loop_proof_upstream_drift")
    expected_status = f"?? {_relative(authority_path)}"
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    if [row for row in status.splitlines() if row] != [expected_status]:
        raise BoundedFinanceLoopProofError("finance_loop_proof_worktree_not_clean")
    if dict(budget) != {
        "network_calls": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "embedding_calls": 0,
        "retries": 0,
        "current_product_pointer_mutation": "forbidden",
        "fake_deliverable_publication": "forbidden",
    }:
        raise BoundedFinanceLoopProofError("finance_loop_proof_budget_invalid")
    paths: dict[str, Path] = {}
    ref_keys = [key for key in bound if key.endswith("_ref")]
    if not ref_keys:
        raise BoundedFinanceLoopProofError(
            "finance_loop_proof_bound_inputs_missing"
        )
    expected_keys = {
        value
        for key in ref_keys
        for value in (key, key[:-4] + "_sha256")
    }
    if set(bound) != expected_keys:
        raise BoundedFinanceLoopProofError(
            "finance_loop_proof_bound_inputs_invalid"
        )
    for key in ref_keys:
        value = bound[key]
        digest_key = key[:-4] + "_sha256"
        path = _resolve(str(value))
        if not path.is_file() or _sha(path) != str(bound.get(digest_key) or ""):
            raise BoundedFinanceLoopProofError(
                f"finance_loop_proof_bound_input_drift:{key}"
            )
        paths[key] = path
    private = _resolve(str(output.get("private_output_ref") or ""))
    public = _resolve(str(output.get("public_result_ref") or ""))
    if private.exists() or public.exists():
        raise BoundedFinanceLoopProofError(
            "finance_loop_proof_exact_once_identity_consumed"
        )
    return paths, output


def _contracts_and_input(paths: Mapping[str, Path]):
    runtime_paths = resolve_runtime_paths(ROOT)
    kernel_payload = read_registered_runtime_json(
        ROOT, "application.config.current_financial_research_kernel"
    )
    route_payload = read_registered_runtime_json(
        ROOT, "application.config.current_query_object_fact_route_policy"
    )
    planning_payload = read_registered_runtime_json(
        ROOT, "application.config.current_research_planning_policy"
    )
    kernel = load_financial_research_kernel(kernel_payload)
    route = load_query_object_fact_route_policy(route_payload, kernel)
    planning = load_research_planning_policy(planning_payload, route)
    evidence_config = read_registered_runtime_json(
        ROOT, "application.config.current_research_evidence_pack_projection"
    )
    evidence = ResearchEvidencePackService(
        config=evidence_config,
        result=read_registered_runtime_json(
            ROOT, str(evidence_config["source_result_resource_id"])
        ),
        private_object_root=(
            runtime_paths.reviewed_evidence_root
            / str(evidence_config["private_object_root_relative"])
        ),
        private_root_base=runtime_paths.reviewed_evidence_root,
    )
    retrieval = ResearchRetrievalService(
        snapshot=read_registered_runtime_json(
            ROOT, "application.result.current_research_retrieval_snapshot"
        ),
        ranking_comparison=read_registered_runtime_json(
            ROOT, "application.result.current_s1c_ranking_comparison_projection"
        ),
        kernel=kernel_payload,
        route_policy=route_payload,
        planning_policy=planning_payload,
        hybrid_candidate_runtime=None,
        company_financial_fact_mart_path=runtime_paths.company_financial_fact_mart_path,
    )
    evidence_pack = evidence.get_case(
        "DELL", ResearchEvidencePackPrincipal("current", frozenset({"current_product:read"}))
    )
    controlled = retrieval.execute_controlled_plan(
        "DELL",
        _json(paths["objective_ref"]),
        _json(paths["planner_atoms_ref"]),
        ResearchRetrievalPrincipal("current", frozenset({"current_product:read"})),
    )
    research_input = compile_current_research_input(
        policy=_json(paths["consumer_policy_ref"]),
        evidence_pack=evidence_pack,
        controlled_plan=controlled,
    )
    return research_input, kernel, route, planning


def _step(index: int, name: str, arguments: Mapping[str, Any]):
    return ChatCompletionToolStepResult(
        status="completed_exact_once_tool_step",
        provider_id="zero_call_fixture_provider",
        model="zero-call-fixture",
        content="",
        reasoning_content=f"private-not-persisted-{index}",
        tool_calls=(
            {
                "id": f"fixture-call-{index}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            },
        ),
        finish_reason="tool_calls",
        usage={"total_tokens": 0},
        request_capture_ref=f"zero-call/request-{index}.json",
        response_capture_ref=f"zero-call/response-{index}.json",
        request_digest=hashlib.sha256(f"request-{index}".encode()).hexdigest(),
        response_digest=hashlib.sha256(f"response-{index}".encode()).hexdigest(),
        private_reasoning_fields_redacted=1,
    )


def _fake_judgment(fake: Mapping[str, Any], cell_id: str) -> dict[str, Any]:
    return deepcopy(next(row for row in fake["cells"] if row["cell_id"] == cell_id))


def _run_fake_matrix(
    *,
    research_input: Mapping[str, Any],
    kernel: Any,
    route: Any,
    planning: Any,
    policy: Any,
    fake: Mapping[str, Any],
) -> dict[str, Any]:
    cell_ids = [str(row["cell_id"]) for row in research_input["cells"]]
    single_id = "CELL::demand_quality"
    strict_tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[single_id],
        kernel=kernel,
        route_policy=route,
        strict=True,
    )
    single_standard_tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[single_id],
        kernel=kernel,
        route_policy=route,
        strict=False,
    )
    single_policy = scope_bounded_finance_loop_policy(
        policy,
        cell_count=1,
        maximum_evidence_requests=3,
    )
    demand_gap = next(
        row["visible_gap_refs"][0]
        for row in research_input["cells"]
        if row["cell_id"] == single_id
    )
    single_sequence = [
        (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": single_id}),
        (READ_NUMERIC_FACTS_TOOL, {"cell_id": single_id}),
        (
            SUBMIT_EVIDENCE_REQUEST_TOOL,
            {
                "cell_id": single_id,
                "gap_ref": demand_gap,
                "target_entity": "DELL",
                "requested_facet_id": "conversion_and_durability",
                "metric_intents": ["orders"],
                "product_intents": ["order digestion and cancellation evidence"],
            },
        ),
        (SUBMIT_RESEARCH_JUDGMENT_TOOL, _fake_judgment(fake, single_id)),
    ]
    single = run_bounded_finance_loop(
        policy=single_policy,
        research_input=research_input,
        required_cell_ids=[single_id],
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
        tools=single_standard_tools,
        step_executor=lambda _messages, _tools, index: _step(
            index, *single_sequence[index - 1]
        ),
        visible_execution_budget={
            "maximum_steps": single_policy.maximum_steps,
            "maximum_evidence_requests": 3,
            "maximum_reads_per_cell": 1,
            "maximum_judgments_per_cell": 1,
            "retry_count": 0,
        },
    ).as_dict()
    standard_tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=cell_ids,
        kernel=kernel,
        route_policy=route,
        strict=False,
    )
    full_sequence = [
        entry
        for cell_id in cell_ids
        for entry in (
            (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
            (READ_NUMERIC_FACTS_TOOL, {"cell_id": cell_id}),
            (SUBMIT_RESEARCH_JUDGMENT_TOOL, _fake_judgment(fake, cell_id)),
        )
    ]
    full_policy = scope_bounded_finance_loop_policy(
        policy,
        cell_count=len(cell_ids),
        maximum_evidence_requests=9,
    )
    full = run_bounded_finance_loop(
        policy=full_policy,
        research_input=research_input,
        required_cell_ids=cell_ids,
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
        tools=standard_tools,
        step_executor=lambda _messages, _tools, index: _step(
            index, *full_sequence[index - 1]
        ),
        visible_execution_budget={
            "maximum_steps": full_policy.maximum_steps,
            "maximum_evidence_requests": 9,
            "maximum_reads_per_cell": 1,
            "maximum_judgments_per_cell": 1,
            "retry_count": 0,
        },
    ).as_dict()
    return {
        "single_cell": single,
        "five_cell": full,
        "single_cell_initial_message_chars": len(
            compile_finance_loop_messages(
                research_input=research_input,
                required_cell_ids=[single_id],
                execution_budget={
                    "maximum_steps": single_policy.maximum_steps,
                    "maximum_evidence_requests": 3,
                    "maximum_reads_per_cell": 1,
                    "maximum_judgments_per_cell": 1,
                    "retry_count": 0,
                },
            )[1]["content"]
        ),
        "strict_tools": strict_tools,
        "single_standard_tools": single_standard_tools,
        "standard_tools": standard_tools,
    }


def _mutation_codes(
    *,
    research_input: Mapping[str, Any],
    kernel: Any,
    route: Any,
    planning: Any,
    policy: Any,
    fake: Mapping[str, Any],
) -> list[str]:
    cell_id = "CELL::demand_quality"
    tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        strict=False,
    )
    scoped_policy = scope_bounded_finance_loop_policy(
        policy,
        cell_count=1,
        maximum_evidence_requests=3,
    )
    cases: list[list[tuple[str, dict[str, Any]]]] = [
        [
            (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
            (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
            (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
        ],
        [("unknown_tool", {"cell_id": cell_id})],
        [
            (
                SUBMIT_RESEARCH_JUDGMENT_TOOL,
                _fake_judgment(fake, "CELL::operating_performance"),
            )
        ],
        [
            (
                SUBMIT_RESEARCH_JUDGMENT_TOOL,
                _fake_judgment(fake, cell_id),
            )
        ],
    ]
    codes = []
    for sequence in cases:
        try:
            run_bounded_finance_loop(
                policy=scoped_policy,
                research_input=research_input,
                required_cell_ids=[cell_id],
                kernel=kernel,
                route_policy=route,
                planning_policy=planning,
                tools=tools,
                step_executor=lambda _messages, _tools, index, seq=sequence: _step(
                    index, *seq[min(index - 1, len(seq) - 1)]
                ),
                visible_execution_budget={
                    "maximum_steps": scoped_policy.maximum_steps,
                    "maximum_evidence_requests": 3,
                    "maximum_reads_per_cell": 1,
                    "maximum_judgments_per_cell": 1,
                    "retry_count": 0,
                },
            )
        except BoundedFinanceLoopError as exc:
            codes.append(exc.code)
        else:
            raise BoundedFinanceLoopProofError(
                "finance_loop_proof_mutation_did_not_fail"
            )
    return codes


def _fresh_process_probe(
    *,
    authority: Path,
    normalized: Path,
) -> dict[str, Any]:
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--authority",
            str(authority),
            "--fresh-probe-output",
            str(normalized),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode:
        raise BoundedFinanceLoopProofError(
            f"finance_loop_proof_fresh_process_failed:{completed.stderr}"
        )
    return _json(normalized)


def _execute(
    authority_path: Path,
    *,
    probe_only: bool,
) -> dict[str, Any]:
    authority = _json(authority_path)
    if probe_only:
        bound = authority.get("bound_inputs")
        if not isinstance(bound, Mapping):
            raise BoundedFinanceLoopProofError(
                "finance_loop_proof_authority_shape_invalid"
            )
        paths = {}
        for key, value in bound.items():
            if not key.endswith("_ref"):
                continue
            path = _resolve(str(value))
            if not path.is_file() or _sha(path) != str(
                bound.get(key[:-4] + "_sha256") or ""
            ):
                raise BoundedFinanceLoopProofError(
                    f"finance_loop_proof_bound_input_drift:{key}"
                )
            paths[key] = path
        output: Mapping[str, Any] = {}
    else:
        paths, output = _validate_authority(
            authority,
            authority_path=authority_path,
        )
    research_input, kernel, route, planning = _contracts_and_input(paths)
    policy = load_bounded_finance_loop_policy(_json(paths["loop_policy_ref"]))
    fake = _json(paths["fake_output_ref"])
    standard_profile = load_chat_completion_profile(
        _json(paths["ga_agent_profile_ref"])
    )
    strict_profile = load_chat_completion_profile(
        _json(paths["ga_strict_profile_ref"])
    )
    json_profile = load_chat_completion_profile(
        _json(paths["ga_json_profile_ref"])
    )
    validate_deepseek_ga_profile(standard_profile, strict_tools=False)
    validate_deepseek_ga_profile(strict_profile, strict_tools=True)
    validate_deepseek_ga_json_profile(json_profile)
    matrix = _run_fake_matrix(
        research_input=research_input,
        kernel=kernel,
        route=route,
        planning=planning,
        policy=policy,
        fake=fake,
    )
    normalized = {
        "research_input_digest": research_input["research_input_digest"],
        "single_cell_result_digest": matrix["single_cell"]["result_digest"],
        "five_cell_result_digest": matrix["five_cell"]["result_digest"],
        "single_cell_steps": matrix["single_cell"]["step_count"],
        "five_cell_steps": matrix["five_cell"]["step_count"],
        "single_cell_initial_message_chars": matrix[
            "single_cell_initial_message_chars"
        ],
        "strict_tool_schema_digest": canonical_digest(matrix["strict_tools"]),
        "standard_tool_schema_digest": canonical_digest(matrix["standard_tools"]),
        "single_standard_tool_schema_digest": canonical_digest(
            matrix["single_standard_tools"]
        ),
        "single_cell_maximum_steps": 6,
        "standard_profile_max_tokens": int(
            standard_profile.request_defaults["max_tokens"]
        ),
        "mutation_failure_codes": _mutation_codes(
            research_input=research_input,
            kernel=kernel,
            route=route,
            planning=planning,
            policy=policy,
            fake=fake,
        ),
        "network_calls": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "embedding_calls": 0,
    }
    if probe_only:
        return normalized
    with tempfile.TemporaryDirectory(prefix="fin013-s3-loop-proof-") as directory:
        first_path = Path(directory) / "fresh-1.json"
        second_path = Path(directory) / "fresh-2.json"
        first = _fresh_process_probe(authority=authority_path, normalized=first_path)
        second = _fresh_process_probe(authority=authority_path, normalized=second_path)
    if first != second or first != normalized:
        raise BoundedFinanceLoopProofError(
            "finance_loop_proof_fresh_process_drift"
        )
    result = {
        "schema_version": RESULT_SCHEMA,
        "status": "zero_call_engineering_and_fresh_process_proof_pass",
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "normalized_proof": normalized,
        "fresh_process_count": 2,
        "fresh_process_results_byte_equivalent": True,
        "single_cell_proposal_boundary": {
            "gap_status": matrix["single_cell"]["proposed_evidence_requests"][0][
                "gap_status"
            ],
            "retrieval_executed": False,
            "candidate_promoted_to_evidence": False,
        },
        "profile_qualification": {
            "standard_ga_endpoint": standard_profile.base_url,
            "standard_ga_max_tokens": int(
                standard_profile.request_defaults["max_tokens"]
            ),
            "strict_beta_endpoint": strict_profile.base_url,
            "thinking": {"type": "enabled"},
            "reasoning_effort": "max",
            "ineffective_sampling_parameters_present": [],
            "strict_tool_live_provider_qualified": False,
        },
        "known_boundary": (
            "This proves provider-neutral loop behavior, local finance authority, "
            "DeepSeek GA profile shape, strict schema shape, no-progress stopping "
            "and fresh-process determinism only. It performs no provider call, "
            "does not prove natural judgment quality and does not authorize a live canary."
        ),
    }
    result["result_digest"] = canonical_digest(result)
    private_path = _resolve(str(output["private_output_ref"]))
    public_path = _resolve(str(output["public_result_ref"]))
    _write_new(private_path, {**result, "fake_matrix": matrix})
    _write_new(public_path, result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", required=True)
    parser.add_argument("--fresh-probe-output")
    args = parser.parse_args(argv)
    result = _execute(
        Path(args.authority).resolve(),
        probe_only=bool(args.fresh_probe_output),
    )
    if args.fresh_probe_output:
        _write_new(Path(args.fresh_probe_output).resolve(), result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
