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
    ModelGatewayError,
    load_chat_completion_profile,
    normalize_chat_completion_tool_calls,
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
    CurrentResearchConsumerError,
    compile_current_research_input,
    validate_current_research_output,
)
from sec_agent.research.planning import (  # noqa: E402
    compile_research_objective,
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


def _runtime_components():
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
    return kernel, route, planning, evidence, retrieval


def _contracts_and_input(paths: Mapping[str, Path]):
    kernel, route, planning, evidence, retrieval = _runtime_components()
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


def _parallel_read_step(index: int, cell_id: str):
    return _parallel_step(
        index,
        [
            (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
            (READ_NUMERIC_FACTS_TOOL, {"cell_id": cell_id}),
        ],
    )


def _parallel_step(
    index: int,
    calls: Sequence[tuple[str, Mapping[str, Any]]],
):
    return ChatCompletionToolStepResult(
        status="completed_exact_once_tool_step",
        provider_id="zero_call_fixture_provider",
        model="zero-call-fixture",
        content="",
        reasoning_content=f"private-not-persisted-{index}",
        tool_calls=tuple(
            {
                "id": f"fixture-call-{index}-{offset}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            }
            for offset, (name, arguments) in enumerate(calls)
        ),
        finish_reason="tool_calls",
        usage={"total_tokens": 0},
        request_capture_ref=f"zero-call/request-{index}.json",
        response_capture_ref=f"zero-call/response-{index}.json",
        request_digest=hashlib.sha256(
            f"request-{index}".encode()
        ).hexdigest(),
        response_digest=hashlib.sha256(
            f"response-{index}".encode()
        ).hexdigest(),
        private_reasoning_fields_redacted=1,
    )


def _fake_judgment(fake: Mapping[str, Any], cell_id: str) -> dict[str, Any]:
    return deepcopy(next(row for row in fake["cells"] if row["cell_id"] == cell_id))


def _case_specific_plan(
    *,
    paths: Mapping[str, Path],
    case_key: str,
    kernel: Any,
    planning: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    objective = _json(paths["objective_ref"])
    objective["case_key"] = case_key
    objective["raw_question"] = (
        f"{case_key} 的核心需求、利润和现金转换是否可持续，"
        "哪些供应约束和反方证据会改变判断？"
    )
    compiled = compile_research_objective(
        objective,
        kernel=kernel,
        policy=planning,
    )
    atoms = _json(paths["planner_atoms_ref"])
    atoms["objective_id"] = compiled.objective_id
    subject = kernel.cases[case_key].subject_ticker
    product_intents = {
        "orders_and_backlog": [
            f"{subject} demand signals",
            "backlog composition",
            "customer concentration",
        ],
        "conversion_and_durability": [
            "order conversion",
            "channel inventory risk",
            "demand durability",
        ],
        "reported_results": [
            "current product revenue contribution",
            "segment profitability",
            "earnings contribution",
        ],
        "guidance_and_outlook": [
            "margin guidance",
            "supply constraint outlook",
        ],
        "pricing_and_mix": ["pricing trend", "product mix shift"],
        "margin_and_incremental_profit": [
            "incremental product margin",
            "operating leverage",
        ],
        "cash_generation": ["cash conversion", "capacity investment"],
        "working_capital_risk": [
            "component inventory buildup",
            "customer receivable risk",
        ],
        "issuer_counterevidence": [
            "management demand caution",
            "inventory impairment risk",
        ],
        "upstream_or_demand_counterevidence": [
            "upstream supply constraints",
            "end demand slowdown",
        ],
    }
    for atom in atoms["atoms"]:
        atom["target_entity"] = subject
        atom["product_intents"] = product_intents[atom["facet_id"]]
    return objective, atoms


def _synthetic_context_judgment(
    research_input: Mapping[str, Any],
    cell_id: str,
) -> dict[str, Any]:
    cell = next(row for row in research_input["cells"] if row["cell_id"] == cell_id)
    evidence_refs = list(cell["allowed_evidence_refs"])
    gap_refs = list(cell["visible_gap_refs"])
    if not evidence_refs and not gap_refs:
        raise BoundedFinanceLoopProofError(
            "finance_loop_proof_cell_without_evidence_or_gap"
        )
    if evidence_refs and gap_refs:
        status, inference, confidence = (
            "mixed",
            "bounded_inference",
            "mixed_source_strength",
        )
    elif evidence_refs:
        status, inference, confidence = (
            "supported",
            "directly_supported",
            "direct_source_only",
        )
    else:
        status, inference, confidence = (
            "insufficient_evidence",
            "not_inferable",
            "gap_dominated",
        )
    method_pack = cell.get("role_method_pack") or {}
    method_minimum = int(
        cell["context_consumption_contract"]["minimum_method_step_refs"]
    )
    graph_minimum = int(
        cell["context_consumption_contract"]["minimum_graph_edge_refs"]
    )
    return {
        "cell_id": cell_id,
        "judgment_status": status,
        "confidence_basis": confidence,
        "inference_authority": inference,
        "evidence_uses": (
            [{"evidence_ref": evidence_refs[0], "use_role": "support"}]
            if evidence_refs
            else []
        ),
        "numeric_refs": [],
        "numeric_relation_refs": [],
        "method_step_refs": [
            row["method_step_ref"]
            for row in method_pack.get("method_steps", [])[:method_minimum]
        ],
        "graph_edge_refs": [
            row["graph_edge_ref"]
            for row in cell["graph_context_pack"]["edges"][:graph_minimum]
        ],
        "thesis_atom": "当前研究单元有已审资料支持，但结论仍受已登记证据边界约束。",
        "mechanism_atom": "经营表现、产品组合与供需条件共同作用，单一现象不能独立证明因果。",
        "counterargument_atom": "替代业务、时点差异与尚未补齐的资料可能解释当前观察。",
        "what_would_change": {
            "observable": "后续正式披露补齐当前关键证据缺口",
            "direction": "resolve_gap" if gap_refs else "persist",
            "time_horizon": "后续连续披露期",
            "evidence_route": "公司正式披露与已审证据复核",
            "threshold_numeric_ref": None,
        },
    }


def _three_case_context_matrix(
    *,
    paths: Mapping[str, Path],
    base_policy: Any,
) -> dict[str, Any]:
    kernel, route, planning, evidence, retrieval = _runtime_components()
    read = frozenset({"current_product:read"})
    cases: dict[str, Any] = {}
    value_graph_refs: dict[str, set[str]] = {}
    for case_key in ("DELL", "MU", "NVDA"):
        objective, atoms = _case_specific_plan(
            paths=paths,
            case_key=case_key,
            kernel=kernel,
            planning=planning,
        )
        evidence_pack = evidence.get_case(
            case_key,
            ResearchEvidencePackPrincipal("current", read),
        )
        controlled = retrieval.execute_controlled_plan(
            case_key,
            objective,
            atoms,
            ResearchRetrievalPrincipal("current", read),
        )
        research_input = compile_current_research_input(
            policy=_json(paths["consumer_policy_ref"]),
            evidence_pack=evidence_pack,
            controlled_plan=controlled,
        )
        subject = kernel.cases[case_key].subject_ticker
        if (
            research_input["case_identity"]["case_key"] != case_key
            or research_input["case_identity"]["subject_ticker"] != subject
            or any(
                row["ticker"] != subject
                for row in research_input["numeric_relation_cards"]
            )
        ):
            raise BoundedFinanceLoopProofError(
                "finance_loop_proof_three_case_identity_pollution"
            )
        receipts = research_input["research_context_receipts"]
        if receipts["compression"] != {
            "method_steps_omitted_after_selection": 0,
            "archived_skill_or_graph_rows_loaded": 0,
            "only_cell_local_current_context_retained": True,
        }:
            raise BoundedFinanceLoopProofError(
                "finance_loop_proof_context_compression_invalid"
            )
        value_cell = next(
            row
            for row in research_input["cells"]
            if row["cell_id"] == "CELL::value_capture"
        )
        if (
            value_cell["role_method_pack"]["pack_id"]
            != "ROLE_METHOD::VALUE_CAPTURE::V1"
            or value_cell["graph_context_pack"]["case_key"] != case_key
            or {
                row["entity_id"]
                for row in value_cell["graph_context_pack"]["nodes"]
            }
            != {subject}
            or value_cell["graph_context_pack"]["authority"][
                "archived_graph_rows_used"
            ]
            is not False
        ):
            raise BoundedFinanceLoopProofError(
                "finance_loop_proof_three_case_context_pollution"
            )
        if any(
            route_row["source_class"] == "commercial_or_industry_data"
            for decision in research_input["evidence_request_route_catalog"][
                "gap_route_decisions"
            ]
            for route_row in decision["available_source_routes"]
        ):
            raise BoundedFinanceLoopProofError(
                "finance_loop_proof_unavailable_route_exposed"
            )
        value_graph_refs[case_key] = {
            row["graph_edge_ref"]
            for row in value_cell["graph_context_pack"]["edges"]
        }
        cell_ids = [str(row["cell_id"]) for row in research_input["cells"]]
        scoped = scope_bounded_finance_loop_policy(
            base_policy,
            cell_count=len(cell_ids),
            maximum_evidence_requests=0,
        )
        tools = compile_finance_loop_tools(
            research_input=research_input,
            required_cell_ids=cell_ids,
            kernel=kernel,
            route_policy=route,
            policy=scoped,
            strict=False,
        )
        result = run_bounded_finance_loop(
            policy=scoped,
            research_input=research_input,
            required_cell_ids=cell_ids,
            kernel=kernel,
            route_policy=route,
            planning_policy=planning,
            tools=tools,
            step_executor=lambda _messages, _tools, index: (
                _parallel_read_step(index, cell_ids[(index - 1) // 2])
                if index % 2 == 1
                else _step(
                    index,
                    SUBMIT_RESEARCH_JUDGMENT_TOOL,
                    _synthetic_context_judgment(
                        research_input,
                        cell_ids[(index - 1) // 2],
                    ),
                )
            ),
        )
        if (
            result.status != "completed_all_required_cells"
            or result.tool_call_count != 15
        ):
            raise BoundedFinanceLoopProofError(
                "finance_loop_proof_three_case_full_fake_failed"
            )
        cases[case_key] = {
            "subject_ticker": subject,
            "research_input_digest": research_input["research_input_digest"],
            "reviewed_evidence_count": len(research_input["evidence_cards"]),
            "numeric_fact_count": len(research_input["numeric_fact_cards"]),
            "same_basis_relation_count": len(
                research_input["numeric_relation_cards"]
            ),
            "route_catalog_digest": research_input[
                "evidence_request_route_catalog"
            ]["route_catalog_digest"],
            "context_receipt_digest": receipts["context_receipt_digest"],
            "value_role_method_pack_digest": value_cell["role_method_pack"][
                "pack_digest"
            ],
            "value_graph_context_digest": value_cell["graph_context_pack"][
                "graph_context_digest"
            ],
            "full_fake_result_digest": result.as_dict()["result_digest"],
            "full_fake_tool_calls": result.tool_call_count,
        }
    if any(
        not value_graph_refs[left].isdisjoint(value_graph_refs[right])
        for left, right in (("DELL", "MU"), ("DELL", "NVDA"), ("MU", "NVDA"))
    ):
        raise BoundedFinanceLoopProofError(
            "finance_loop_proof_three_case_graph_ref_collision"
        )
    return {
        "cases": cases,
        "case_identity_pollution_count": 0,
        "graph_context_pollution_count": 0,
        "archived_skill_or_graph_rows_loaded": 0,
        "unavailable_route_exposed_count": 0,
        "all_three_full_fake_pass": True,
    }


def _immutable_paired_r1_content_replay(
    *,
    research_input: Mapping[str, Any],
    prior_result: Mapping[str, Any],
) -> dict[str, Any]:
    lanes = prior_result.get("lanes")
    if not (
        prior_result.get("status") == "paired_contract_valid_content_assessment_pending"
        and isinstance(lanes, list)
        and {str(row.get("lane") or "") for row in lanes if isinstance(row, Mapping)}
        == {"chat_control", "responses_candidate"}
    ):
        raise BoundedFinanceLoopProofError(
            "finance_loop_proof_prior_paired_result_invalid"
        )
    replay: dict[str, Any] = {}
    allowed_failures = {
        "research_consumer_output_cell_fields_invalid",
        "research_consumer_numeric_relation_consumption_invalid",
        "research_consumer_method_consumption_invalid",
        "research_consumer_graph_consumption_invalid",
    }
    for raw in lanes:
        lane = str(raw["lane"])
        loop_result = raw.get("loop_result")
        payload = (
            loop_result.get("judgment_output")
            if isinstance(loop_result, Mapping)
            else None
        )
        if not isinstance(payload, Mapping):
            raise BoundedFinanceLoopProofError(
                "finance_loop_proof_prior_paired_payload_missing"
            )
        try:
            validate_current_research_output(
                payload,
                research_input=research_input,
                required_cell_ids=["CELL::value_capture"],
            )
        except CurrentResearchConsumerError as exc:
            if exc.code not in allowed_failures:
                raise BoundedFinanceLoopProofError(
                    "finance_loop_proof_prior_paired_unexpected_failure:"
                    + exc.code
                ) from exc
            replay[lane] = {
                "old_loop_result_digest": str(loop_result.get("result_digest") or ""),
                "rejected_by_current_contract": True,
                "failure_code": exc.code,
            }
        else:
            raise BoundedFinanceLoopProofError(
                "finance_loop_proof_prior_paired_silently_promoted"
            )
    body = {
        "prior_full_result_digest": str(prior_result.get("full_result_digest") or ""),
        "lanes": replay,
        "old_failed_content_was_not_silently_promoted": True,
    }
    return {**body, "replay_digest": canonical_digest(body)}


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
    single_id = "CELL::value_capture"
    strict_tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[single_id],
        kernel=kernel,
        route_policy=route,
        policy=policy,
        strict=True,
    )
    single_standard_tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[single_id],
        kernel=kernel,
        route_policy=route,
        policy=policy,
        strict=False,
    )
    single_policy = scope_bounded_finance_loop_policy(
        policy,
        cell_count=1,
        maximum_evidence_requests=3,
    )
    request_gap = next(
        row["gap_ref"]
        for row in research_input["residual_gap_cards"]
        if row["facet_id"] == "price_or_asp"
    )
    single_sequence = [
        (
            SUBMIT_EVIDENCE_REQUEST_TOOL,
            {
                "cell_id": single_id,
                "gap_ref": request_gap,
                "target_entity": research_input["case_identity"]["subject_ticker"],
                "requested_facet_id": "pricing_and_mix",
                "requested_source_class": "official_company_disclosure",
                "metric_intents": ["average_selling_price"],
                "product_intents": ["price and configuration mix evidence"],
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
        step_executor=lambda _messages, _tools, index: (
            _parallel_read_step(index, single_id)
            if index == 1
            else _step(index, *single_sequence[index - 2])
        ),
        visible_execution_budget={
            "maximum_steps": single_policy.maximum_steps,
            "maximum_evidence_requests": 3,
            "maximum_reads_per_cell": 1,
            "maximum_parallel_read_tools": 2,
            "maximum_judgments_per_cell": 1,
            "retry_count": 0,
        },
    ).as_dict()
    standard_tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=cell_ids,
        kernel=kernel,
        route_policy=route,
        policy=policy,
        strict=False,
    )
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
        step_executor=lambda _messages, _tools, index: (
            _parallel_read_step(index, cell_ids[(index - 1) // 2])
            if index % 2 == 1
            else _step(
                index,
                SUBMIT_RESEARCH_JUDGMENT_TOOL,
                _fake_judgment(fake, cell_ids[(index - 1) // 2]),
            )
        ),
        visible_execution_budget={
            "maximum_steps": full_policy.maximum_steps,
            "maximum_evidence_requests": 9,
            "maximum_reads_per_cell": 1,
            "maximum_parallel_read_tools": 2,
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
                    "maximum_parallel_read_tools": 2,
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
        policy=policy,
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
                    "maximum_parallel_read_tools": 2,
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
    parallel_mutations = [
        (
            [
                (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
                (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
            ],
            "finance_loop_parallel_tool_set_invalid",
        ),
        (
            [
                (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
                (
                    SUBMIT_RESEARCH_JUDGMENT_TOOL,
                    _fake_judgment(fake, cell_id),
                ),
            ],
            "finance_loop_parallel_tool_set_invalid",
        ),
    ]
    for calls, expected in parallel_mutations:
        try:
            run_bounded_finance_loop(
                policy=scoped_policy,
                research_input=research_input,
                required_cell_ids=[cell_id],
                kernel=kernel,
                route_policy=route,
                planning_policy=planning,
                tools=tools,
                step_executor=lambda _messages, _tools, index, rows=calls: (
                    _parallel_step(index, rows)
                ),
                visible_execution_budget={
                    "maximum_steps": scoped_policy.maximum_steps,
                    "maximum_evidence_requests": 3,
                    "maximum_reads_per_cell": 1,
                    "maximum_parallel_read_tools": 2,
                    "maximum_judgments_per_cell": 1,
                    "retry_count": 0,
                },
            )
        except BoundedFinanceLoopError as exc:
            if exc.code != expected:
                raise
            codes.append(exc.code)
        else:
            raise BoundedFinanceLoopProofError(
                "finance_loop_proof_parallel_mutation_did_not_fail"
            )
    return codes


def _wire_index_replay(
    capture: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    raw: object = [
        {
            "id": "call-evidence",
            "index": 0,
            "type": "function",
            "function": {
                "name": READ_REVIEWED_EVIDENCE_TOOL,
                "arguments": '{"cell_id":"CELL::value_capture"}',
            },
        },
        {
            "id": "call-numeric",
            "index": 1,
            "type": "function",
            "function": {
                "name": READ_NUMERIC_FACTS_TOOL,
                "arguments": '{"cell_id":"CELL::value_capture"}',
            },
        },
    ]
    source_sha256 = "portable_fixture"
    if capture is not None:
        try:
            raw = capture["response_body"]["choices"][0]["message"][
                "tool_calls"
            ]
            source_sha256 = str(capture["response_digest"])
        except (KeyError, IndexError, TypeError) as exc:
            raise BoundedFinanceLoopProofError(
                "finance_loop_proof_R1_capture_shape_invalid"
            ) from exc
    normalized = normalize_chat_completion_tool_calls(raw)
    if any("index" in row for row in normalized):
        raise BoundedFinanceLoopProofError(
            "finance_loop_proof_wire_index_not_stripped"
        )
    mutation_codes = []
    mutations = [
        [{**raw[0], "index": -1}, raw[1]],
        [raw[0], {key: value for key, value in raw[1].items() if key != "index"}],
        [{**raw[0], "index": 1}, {**raw[1], "index": 0}],
    ]
    for mutation in mutations:
        try:
            normalize_chat_completion_tool_calls(mutation)
        except ModelGatewayError as exc:
            mutation_codes.append(exc.code)
        else:
            raise BoundedFinanceLoopProofError(
                "finance_loop_proof_wire_index_mutation_did_not_fail"
            )
    return {
        "wire_tool_call_index_stripped": True,
        "wire_replay_source_digest": source_sha256,
        "normalized_tool_names": [
            str(row["function"]["name"]) for row in normalized
        ],
        "wire_mutation_failure_codes": mutation_codes,
    }


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
    three_case_context = _three_case_context_matrix(
        paths=paths,
        base_policy=policy,
    )
    paired_content_replay = _immutable_paired_r1_content_replay(
        research_input=research_input,
        prior_result=_json(paths["prior_paired_result_ref"]),
    )
    replay_capture = (
        _json(paths["prior_standard_r1_response_capture_ref"])
        if "prior_standard_r1_response_capture_ref" in paths
        else None
    )
    wire_replay = _wire_index_replay(replay_capture)
    normalized = {
        "research_input_digest": research_input["research_input_digest"],
        "single_cell_result_digest": matrix["single_cell"]["result_digest"],
        "five_cell_result_digest": matrix["five_cell"]["result_digest"],
        "single_cell_steps": matrix["single_cell"]["step_count"],
        "five_cell_steps": matrix["five_cell"]["step_count"],
        "single_cell_tool_calls": matrix["single_cell"]["tool_call_count"],
        "five_cell_tool_calls": matrix["five_cell"]["tool_call_count"],
        "safe_parallel_read_pair_pass": (
            matrix["single_cell"]["step_count"] == 3
            and matrix["single_cell"]["tool_call_count"] == 4
            and matrix["five_cell"]["step_count"] == 10
            and matrix["five_cell"]["tool_call_count"] == 15
        ),
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
        "three_case_context_digest": canonical_digest(three_case_context),
        "three_case_context_all_pass": three_case_context[
            "all_three_full_fake_pass"
        ],
        "three_case_identity_pollution_count": three_case_context[
            "case_identity_pollution_count"
        ],
        "three_case_graph_context_pollution_count": three_case_context[
            "graph_context_pollution_count"
        ],
        "three_case_archived_context_rows_loaded": three_case_context[
            "archived_skill_or_graph_rows_loaded"
        ],
        "three_case_unavailable_route_exposed_count": three_case_context[
            "unavailable_route_exposed_count"
        ],
        "prior_paired_content_replay_digest": paired_content_replay[
            "replay_digest"
        ],
        "prior_paired_content_rejected_by_current_contract": all(
            row["rejected_by_current_contract"]
            for row in paired_content_replay["lanes"].values()
        ),
        **wire_replay,
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
        "three_case_context_qualification": three_case_context,
        "immutable_paired_r1_content_replay": paired_content_replay,
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
    _write_new(
        private_path,
        {
            **result,
            "fake_matrix": matrix,
            "three_case_context_matrix": three_case_context,
            "immutable_paired_r1_content_replay": paired_content_replay,
        },
    )
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
