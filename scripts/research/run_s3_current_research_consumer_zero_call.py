from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
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
from sec_agent.research.current_consumer import (  # noqa: E402
    CurrentResearchConsumerError,
    compile_current_research_deliverable,
    compile_current_research_input,
    compile_current_research_messages,
    validate_current_research_output,
)
from sec_agent.research.claim_authority import (  # noqa: E402
    compile_claim_authority_research_input,
)
from sec_agent.research.claim_surface_authority import (  # noqa: E402
    ClaimSurfaceAuthorityError,
    compile_claim_surface_authority_research_input,
)
from sec_agent.research.bounded_finance_loop import (  # noqa: E402
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
from sec_agent.providers import ChatCompletionToolStepResult  # noqa: E402
from retrieval.contracts import load_financial_research_kernel  # noqa: E402
from retrieval.route_compiler import (  # noqa: E402
    load_query_object_fact_route_policy,
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


AUTHORITY_SCHEMA = (
    "fin_ia_current_research_consumer_zero_call_authority_v1_2"
)
RESULT_SCHEMA = "fin_ia_current_research_consumer_zero_call_result_v1_2"
CLAIM_AUTHORITY_SCHEMA = (
    "fin_ia_fixed_pack_claim_authority_zero_call_authority_v1_0"
)
CLAIM_RESULT_SCHEMA = (
    "fin_ia_fixed_pack_claim_authority_zero_call_result_v1_0"
)
CLAIM_SURFACE_AUTHORITY_SCHEMA = (
    "fin_ia_fixed_pack_claim_surface_authority_zero_call_authority_v1_0"
)
CLAIM_SURFACE_RESULT_SCHEMA = (
    "fin_ia_fixed_pack_claim_surface_authority_zero_call_result_v1_0"
)
CLAIM_RELATION_ALIAS_AUTHORITY_SCHEMA = (
    "fin_ia_fixed_pack_claim_relation_alias_zero_call_authority_v1_0"
)
CLAIM_RELATION_ALIAS_RESULT_SCHEMA = (
    "fin_ia_fixed_pack_claim_relation_alias_zero_call_result_v1_0"
)


class CurrentResearchConsumerRunnerError(RuntimeError):
    """The zero-call consumer proof was not exactly authorized."""


def _resolve(ref: str) -> Path:
    relative = PurePosixPath(str(ref or ""))
    if relative.is_absolute() or "\\" in str(ref) or ".." in relative.parts:
        raise CurrentResearchConsumerRunnerError(
            "current_consumer_authority_path_invalid"
        )
    path = ROOT.joinpath(*relative.parts).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise CurrentResearchConsumerRunnerError(
            "current_consumer_authority_path_escape"
        ) from exc
    return path


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CurrentResearchConsumerRunnerError(
            f"current_consumer_json_object_required:{path.name}"
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
        raise CurrentResearchConsumerRunnerError(
            "current_consumer_exact_once_output_exists"
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
        raise CurrentResearchConsumerRunnerError(
            "current_consumer_git_boundary_unavailable"
        )
    return completed.stdout.strip()


def _validate_clean_implementation(
    payload: Mapping[str, Any],
    *,
    authority_path: Path,
) -> None:
    binding = payload.get("clean_implementation")
    if not isinstance(binding, Mapping):
        raise CurrentResearchConsumerRunnerError(
            "current_consumer_clean_implementation_missing"
        )
    commit = str(binding.get("implementation_commit") or "").lower()
    if not (
        dict(binding)
        == {
            "implementation_commit": commit,
            "head_must_equal_implementation_commit": True,
            "upstream_must_equal_implementation_commit": True,
            "tracked_worktree_must_be_clean": True,
            "only_authority_may_be_untracked": True,
        }
        and re.fullmatch(r"[0-9a-f]{40}", commit)
    ):
        raise CurrentResearchConsumerRunnerError(
            "current_consumer_clean_implementation_invalid"
        )
    if _git("rev-parse", "HEAD").lower() != commit:
        raise CurrentResearchConsumerRunnerError(
            "current_consumer_implementation_head_drift"
        )
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise CurrentResearchConsumerRunnerError(
            "current_consumer_implementation_upstream_drift"
        )
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    allowed = f"?? {_relative(authority_path)}"
    if [line for line in status.splitlines() if line] != [allowed]:
        raise CurrentResearchConsumerRunnerError(
            "current_consumer_implementation_worktree_not_clean"
        )


def validate_authority(
    payload: Mapping[str, Any],
    *,
    authority_path: Path | None = None,
) -> tuple[dict[str, Path], str]:
    schema = str(payload.get("schema_version") or "")
    if not (
        schema
        in {
            AUTHORITY_SCHEMA,
            CLAIM_AUTHORITY_SCHEMA,
            CLAIM_SURFACE_AUTHORITY_SCHEMA,
            CLAIM_RELATION_ALIAS_AUTHORITY_SCHEMA,
        }
        and payload.get("status")
        == "fresh_zero_network_zero_model_current_consumer_proof_authorized"
    ):
        raise CurrentResearchConsumerRunnerError(
            "current_consumer_authority_status_invalid"
        )
    budget = payload.get("execution_budget")
    output = payload.get("output_contract")
    bound = payload.get("bound_inputs")
    if not all(isinstance(row, Mapping) for row in (budget, output, bound)):
        raise CurrentResearchConsumerRunnerError(
            "current_consumer_authority_shape_invalid"
        )
    assert isinstance(budget, Mapping)
    assert isinstance(output, Mapping)
    assert isinstance(bound, Mapping)
    if dict(budget) != {
        "network_calls": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "local_embedding_calls": 0,
        "retries": 0,
        "current_product_pointer_mutation": "forbidden",
        "fake_deliverable_publication": "forbidden",
    }:
        raise CurrentResearchConsumerRunnerError(
            "current_consumer_authority_budget_invalid"
        )
    pairs = [
        ("consumer_policy_ref", "consumer_policy_sha256"),
        ("objective_ref", "objective_sha256"),
        ("planner_atoms_ref", "planner_atoms_sha256"),
        ("current_evidence_pack_result_ref", "current_evidence_pack_result_sha256"),
        ("runtime_registry_ref", "runtime_registry_sha256"),
        ("runner_ref", "runner_sha256"),
    ]
    if schema == AUTHORITY_SCHEMA:
        pairs.extend(
            [
                ("fake_output_ref", "fake_output_sha256"),
                ("failed_r1_payload_ref", "failed_r1_payload_sha256"),
                ("failed_r1_audit_ref", "failed_r1_audit_sha256"),
            ]
        )
    elif schema == CLAIM_AUTHORITY_SCHEMA:
        pairs.extend(
            [
                ("claim_authority_policy_ref", "claim_authority_policy_sha256"),
                ("prior_r2_full_result_ref", "prior_r2_full_result_sha256"),
                (
                    "prior_r2_content_assessment_ref",
                    "prior_r2_content_assessment_sha256",
                ),
                ("loop_policy_ref", "loop_policy_sha256"),
                (
                    "claim_authority_fake_output_ref",
                    "claim_authority_fake_output_sha256",
                ),
                (
                    "current_consumer_implementation_ref",
                    "current_consumer_implementation_sha256",
                ),
                (
                    "claim_authority_implementation_ref",
                    "claim_authority_implementation_sha256",
                ),
                (
                    "bounded_loop_implementation_ref",
                    "bounded_loop_implementation_sha256",
                ),
            ]
        )
    elif schema == CLAIM_SURFACE_AUTHORITY_SCHEMA:
        pairs.extend(
            [
                ("claim_authority_policy_ref", "claim_authority_policy_sha256"),
                (
                    "claim_surface_authority_policy_ref",
                    "claim_surface_authority_policy_sha256",
                ),
                (
                    "failed_chat_payload_ref",
                    "failed_chat_payload_sha256",
                ),
                (
                    "corrected_fake_output_ref",
                    "corrected_fake_output_sha256",
                ),
                (
                    "prior_chat_result_ref",
                    "prior_chat_result_sha256",
                ),
                (
                    "prior_chat_assessment_ref",
                    "prior_chat_assessment_sha256",
                ),
                ("loop_policy_ref", "loop_policy_sha256"),
                (
                    "current_consumer_implementation_ref",
                    "current_consumer_implementation_sha256",
                ),
                (
                    "claim_authority_implementation_ref",
                    "claim_authority_implementation_sha256",
                ),
                (
                    "claim_surface_authority_implementation_ref",
                    "claim_surface_authority_implementation_sha256",
                ),
                (
                    "bounded_loop_implementation_ref",
                    "bounded_loop_implementation_sha256",
                ),
            ]
        )
    else:
        pairs.extend(
            [
                ("claim_authority_policy_ref", "claim_authority_policy_sha256"),
                (
                    "claim_surface_authority_policy_ref",
                    "claim_surface_authority_policy_sha256",
                ),
                (
                    "corrected_fake_output_ref",
                    "corrected_fake_output_sha256",
                ),
                (
                    "prior_chat_result_ref",
                    "prior_chat_result_sha256",
                ),
                (
                    "prior_chat_assessment_ref",
                    "prior_chat_assessment_sha256",
                ),
                (
                    "prior_step_two_request_ref",
                    "prior_step_two_request_sha256",
                ),
                (
                    "prior_step_two_response_ref",
                    "prior_step_two_response_sha256",
                ),
                ("loop_policy_ref", "loop_policy_sha256"),
                (
                    "current_consumer_implementation_ref",
                    "current_consumer_implementation_sha256",
                ),
                (
                    "claim_authority_implementation_ref",
                    "claim_authority_implementation_sha256",
                ),
                (
                    "claim_surface_authority_implementation_ref",
                    "claim_surface_authority_implementation_sha256",
                ),
                (
                    "bounded_loop_implementation_ref",
                    "bounded_loop_implementation_sha256",
                ),
                (
                    "finance_tool_contract_implementation_ref",
                    "finance_tool_contract_implementation_sha256",
                ),
            ]
        )
    paths: dict[str, Path] = {}
    for ref_key, digest_key in pairs:
        path = _resolve(str(bound.get(ref_key) or ""))
        if not path.is_file() or _sha(path) != str(bound.get(digest_key) or ""):
            raise CurrentResearchConsumerRunnerError(
                f"current_consumer_bound_input_drift:{ref_key}"
            )
        paths[ref_key] = path
    if not (
        str(output.get("private_output_root_ref") or "")
        and str(output.get("public_result_ref") or "")
        and str(output.get("result_id") or "")
    ):
        raise CurrentResearchConsumerRunnerError(
            "current_consumer_output_contract_invalid"
        )
    if _resolve(str(output["private_output_root_ref"])).exists() or _resolve(
        str(output["public_result_ref"])
    ).exists():
        raise CurrentResearchConsumerRunnerError(
            "current_consumer_exact_once_identity_consumed"
        )
    if authority_path is None:
        raise CurrentResearchConsumerRunnerError(
            "current_consumer_authority_path_required"
        )
    _validate_clean_implementation(
        payload,
        authority_path=authority_path,
    )
    if schema == CLAIM_RELATION_ALIAS_AUTHORITY_SCHEMA:
        result_schema = CLAIM_RELATION_ALIAS_RESULT_SCHEMA
    elif schema == CLAIM_SURFACE_AUTHORITY_SCHEMA:
        result_schema = CLAIM_SURFACE_RESULT_SCHEMA
    elif schema == CLAIM_AUTHORITY_SCHEMA:
        result_schema = CLAIM_RESULT_SCHEMA
    else:
        result_schema = RESULT_SCHEMA
    return paths, result_schema


def _services() -> tuple[ResearchEvidencePackService, ResearchRetrievalService]:
    runtime_paths = resolve_runtime_paths(ROOT)
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
        kernel=read_registered_runtime_json(
            ROOT, "application.config.current_financial_research_kernel"
        ),
        route_policy=read_registered_runtime_json(
            ROOT, "application.config.current_query_object_fact_route_policy"
        ),
        planning_policy=read_registered_runtime_json(
            ROOT, "application.config.current_research_planning_policy"
        ),
        hybrid_candidate_runtime=None,
        company_financial_fact_mart_path=(
            runtime_paths.company_financial_fact_mart_path
        ),
    )
    return evidence, retrieval


def _mutation_codes(
    *,
    research_input: Mapping[str, Any],
    fake: Mapping[str, Any],
) -> list[str]:
    cases = []
    unknown = deepcopy(dict(fake))
    unknown["cells"][0]["evidence_uses"].append(
        {"evidence_ref": "EV::DOESNOTEXIST", "use_role": "support"}
    )
    cases.append(unknown)
    duplicate = deepcopy(dict(fake))
    duplicate["cells"][0]["evidence_uses"].append(
        deepcopy(duplicate["cells"][0]["evidence_uses"][0])
    )
    cases.append(duplicate)
    invented_enum = deepcopy(dict(fake))
    invented_enum["cells"][0]["judgment_status"] = "supported_with_caveats"
    cases.append(invented_enum)
    model_owned_gap = deepcopy(dict(fake))
    model_owned_gap["cells"][2]["remaining_gap_refs"] = []
    cases.append(model_owned_gap)
    free_number = deepcopy(dict(fake))
    free_number["cells"][0]["thesis_atom"] = (
        "戴尔订单增长达到两位数，因此需求已经完全确认。"
    )
    cases.append(free_number)
    cross_cell = deepcopy(dict(fake))
    cross_cell["cells"][0]["numeric_refs"].append(
        "NUM::ADC81E7A547FAB94"
    )
    cases.append(cross_cell)
    method_shortfall = deepcopy(dict(fake))
    method_cell = next(
        row for row in method_shortfall["cells"] if row["method_step_refs"]
    )
    method_cell["method_step_refs"] = method_cell["method_step_refs"][:3]
    cases.append(method_shortfall)
    graph_borrow = deepcopy(dict(fake))
    graph_cell = next(
        row for row in graph_borrow["cells"] if row["graph_edge_refs"]
    )
    graph_cell["graph_edge_refs"] = ["GRAPH::CROSS_CASE_BORROWED"]
    cases.append(graph_borrow)
    output = []
    for mutation in cases:
        try:
            compile_current_research_deliverable(
                research_input=research_input,
                judgment_output=mutation,
            )
        except CurrentResearchConsumerError as exc:
            output.append(exc.code)
        else:
            raise CurrentResearchConsumerRunnerError(
                "current_consumer_mutation_did_not_fail"
            )
    return output


def _replay_failed_r1(
    *,
    research_input: Mapping[str, Any],
    payload: Mapping[str, Any],
    audit: Mapping[str, Any],
) -> dict[str, Any]:
    if not (
        audit.get("schema_version")
        == "fin_ia_current_research_consumer_r1_content_audit_v1_0"
        and audit.get("status") == "rejected_not_salvageable"
        and isinstance(audit.get("content_findings"), list)
        and audit.get("failed_payload_canonical_digest")
        == canonical_digest(payload)
    ):
        raise CurrentResearchConsumerRunnerError(
            "current_consumer_failed_r1_audit_invalid"
        )
    cells = {
        str(row.get("cell_id") or ""): row
        for row in payload.get("cells") or ()
        if isinstance(row, Mapping)
    }
    expected_codes = {
        "demand_durability_overreach",
        "ai_to_group_and_segment_profit_attribution_unproven",
        "unbound_comparative_margin_and_leverage_claim",
        "ai_working_capital_attribution_unproven",
        "supply_easing_unproven",
    }
    observed_codes = set()
    for finding in audit["content_findings"]:
        if not isinstance(finding, Mapping):
            raise CurrentResearchConsumerRunnerError(
                "current_consumer_failed_r1_audit_invalid"
            )
        code = str(finding.get("finding_code") or "")
        cell_id = str(finding.get("cell_id") or "")
        field = str(finding.get("field") or "")
        excerpt = str(finding.get("observed_excerpt") or "")
        if (
            code not in expected_codes
            or cell_id not in cells
            or field not in {"thesis_atom", "mechanism_atom", "counterargument_atom"}
            or not excerpt
            or excerpt not in str(cells[cell_id].get(field) or "")
        ):
            raise CurrentResearchConsumerRunnerError(
                "current_consumer_failed_r1_audit_finding_unbound"
            )
        observed_codes.add(code)
    if observed_codes != expected_codes:
        raise CurrentResearchConsumerRunnerError(
            "current_consumer_failed_r1_audit_incomplete"
        )
    try:
        validate_current_research_output(
            payload,
            research_input=research_input,
        )
    except CurrentResearchConsumerError as exc:
        rejection_code = exc.code
    else:
        raise CurrentResearchConsumerRunnerError(
            "current_consumer_failed_r1_was_silently_accepted"
        )
    overlaps = {
        cell_id: sorted(
            set(row.get("supporting_evidence_refs") or ())
            & set(row.get("counterevidence_refs") or ())
        )
        for cell_id, row in cells.items()
    }
    return {
        "v1_1_rejection_code": rejection_code,
        "invented_judgment_statuses": sorted(
            {str(row.get("judgment_status") or "") for row in cells.values()}
        ),
        "invented_confidence_bases": sorted(
            {str(row.get("confidence_basis") or "") for row in cells.values()}
        ),
        "dual_role_evidence_by_cell": {
            key: value for key, value in overlaps.items() if value
        },
        "qualified_content_audit_finding_codes": sorted(observed_codes),
        "automatic_salvage_or_publication": False,
    }


def _tool_step(
    index: int,
    calls: Sequence[tuple[str, Mapping[str, Any]]],
) -> ChatCompletionToolStepResult:
    return ChatCompletionToolStepResult(
        status="completed_exact_once_tool_step",
        provider_id="fixed_pack_zero_call_fixture",
        model="zero-call-fixture",
        content="",
        reasoning_content=f"transient-zero-call-step-{index}",
        tool_calls=tuple(
            {
                "id": f"call-{index}-{offset}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(
                        dict(arguments),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                },
            }
            for offset, (name, arguments) in enumerate(calls, start=1)
        ),
        finish_reason="tool_calls",
        usage={"total_tokens": 0},
        request_capture_ref=f"zero-call/request-{index}.json",
        response_capture_ref=f"zero-call/response-{index}.json",
        request_digest=f"zero-call-request-{index}",
        response_digest=f"zero-call-response-{index}",
        private_reasoning_fields_redacted=1,
    )


def _claim_authority_mutation_codes(
    *,
    research_input: Mapping[str, Any],
    fake: Mapping[str, Any],
) -> list[str]:
    cases: list[dict[str, Any]] = []
    direct_bridge = deepcopy(dict(fake))
    direct_bridge["cells"][0][
        "causal_bridge_authority"
    ] = "direct_cross_scope_bridge"
    cases.append(direct_bridge)
    wrong_scope = deepcopy(dict(fake))
    wrong_scope["cells"][0]["claim_scope"] = "product"
    wrong_scope["cells"][0]["financial_scope"] = "company_financial"
    cases.append(wrong_scope)
    causal_surface = deepcopy(dict(fake))
    causal_surface["cells"][0]["thesis_atom"] = (
        "Dell is converting the AI server surge into profit through operating leverage."
    )
    cases.append(causal_surface)
    output = []
    for mutation in cases:
        try:
            validate_current_research_output(
                mutation,
                research_input=research_input,
                required_cell_ids=["CELL::value_capture"],
            )
        except CurrentResearchConsumerError as exc:
            output.append(exc.code)
        else:
            raise CurrentResearchConsumerRunnerError(
                "claim_authority_mutation_did_not_fail"
            )
    return output


def _run_claim_authority_proof(
    *,
    authority: Mapping[str, Any],
    authority_path: Path,
    paths: Mapping[str, Path],
    result_schema: str,
    evidence_pack: Mapping[str, Any],
    controlled: Mapping[str, Any],
    base_research_input: Mapping[str, Any],
) -> dict[str, Any]:
    research_input = compile_claim_authority_research_input(
        base_research_input,
        policy=_json(paths["claim_authority_policy_ref"]),
    )
    cell_id = "CELL::value_capture"
    fake = _json(paths["claim_authority_fake_output_ref"])
    deliverable = compile_current_research_deliverable(
        research_input=research_input,
        judgment_output=fake,
        required_cell_ids=[cell_id],
    )
    prior_r2 = _json(paths["prior_r2_full_result_ref"])
    prior_assessment = _json(paths["prior_r2_content_assessment_ref"])
    if not (
        prior_r2.get("status")
        == "completed_contract_valid_content_assessment_pending"
        and prior_assessment.get("l1_financial_truth", {}).get("gate_status")
        == "fail_causal_attribution_unbound"
        and prior_assessment.get("source_result_ref")
        == "configs/research/evals/fin_ia_0_1_3_s3_dell_value_capture_research_context_chat_live_result_v1_1.json"
    ):
        raise CurrentResearchConsumerRunnerError(
            "claim_authority_prior_r2_disposition_invalid"
        )
    prior_judgment = deepcopy(
        prior_r2["loop_result"]["judgment_output"]
    )
    prior_judgment["cells"][0].update(
        {
            "claim_scope": "multi_scope",
            "financial_scope": "multi_scope_financial",
            "causal_bridge_authority": "multi_driver_context_only",
        }
    )
    try:
        validate_current_research_output(
            prior_judgment,
            research_input=research_input,
            required_cell_ids=[cell_id],
        )
    except CurrentResearchConsumerError as exc:
        prior_r2_rejection_code = exc.code
    else:
        raise CurrentResearchConsumerRunnerError(
            "claim_authority_prior_r2_silently_promoted"
        )
    if prior_r2_rejection_code != (
        "claim_authority_cross_scope_causal_language_unbound"
    ):
        raise CurrentResearchConsumerRunnerError(
            "claim_authority_prior_r2_wrong_rejection"
        )
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
    base_policy = load_bounded_finance_loop_policy(
        _json(paths["loop_policy_ref"])
    )
    scoped = scope_bounded_finance_loop_policy(
        base_policy,
        cell_count=1,
        maximum_evidence_requests=0,
    )
    tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        policy=scoped,
        strict=False,
    )
    visible_budget = {
        "maximum_steps": scoped.maximum_steps,
        "maximum_evidence_requests": 0,
        "maximum_reads_per_cell": 1,
        "maximum_parallel_read_tools": 2,
        "maximum_judgments_per_cell": 1,
        "retry_count": 0,
    }
    messages = compile_finance_loop_messages(
        research_input=research_input,
        required_cell_ids=[cell_id],
        execution_budget=visible_budget,
    )
    loop_result = run_bounded_finance_loop(
        policy=scoped,
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
        tools=tools,
        step_executor=lambda _messages, _tools, index: (
            _tool_step(
                index,
                [
                    (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
                    (READ_NUMERIC_FACTS_TOOL, {"cell_id": cell_id}),
                ],
            )
            if index == 1
            else _tool_step(
                index,
                [(SUBMIT_RESEARCH_JUDGMENT_TOOL, fake["cells"][0])],
            )
        ),
        visible_execution_budget=visible_budget,
    )
    mutations = _claim_authority_mutation_codes(
        research_input=research_input,
        fake=fake,
    )
    replay_input = compile_claim_authority_research_input(
        base_research_input,
        policy=_json(paths["claim_authority_policy_ref"]),
    )
    replay_messages = compile_finance_loop_messages(
        research_input=replay_input,
        required_cell_ids=[cell_id],
        execution_budget=visible_budget,
    )
    if not (
        replay_input == research_input
        and replay_messages == messages
        and loop_result.status == "completed_all_required_cells"
        and loop_result.step_count == 2
        and loop_result.tool_call_count == 3
        and loop_result.tool_counts.get("submit_evidence_request", 0) == 0
    ):
        raise CurrentResearchConsumerRunnerError(
            "claim_authority_zero_call_determinism_or_loop_invalid"
        )
    normalized = {
        "base_research_input_digest": base_research_input[
            "research_input_digest"
        ],
        "research_input_digest": research_input["research_input_digest"],
        "finance_loop_messages_digest": canonical_digest(list(messages)),
        "standard_tool_schema_digest": canonical_digest(list(tools)),
        "deliverable_digest": deliverable["deliverable_digest"],
        "saved_r2_negative_replay_code": prior_r2_rejection_code,
        "mutation_failure_codes": mutations,
        "fixed_pack_unit_test_only": True,
        "dynamic_retrieval_executed": False,
        "agentic_research_claimed": False,
        "maximum_model_steps": scoped.maximum_steps,
        "maximum_evidence_requests": 0,
        "fake_loop_steps": loop_result.step_count,
        "fake_loop_tool_calls": loop_result.tool_call_count,
        "fake_loop_evidence_requests": loop_result.tool_counts.get(
            "submit_evidence_request", 0
        ),
        "network_calls": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "local_embedding_calls": 0,
        "retries": 0,
        "deterministic_recompile_equal": True,
    }
    full_body = {
        "schema_version": "fin_ia_fixed_pack_claim_authority_zero_call_full_v1_0",
        "status": "completed_zero_call_fixed_pack_claim_authority_proof",
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "base_research_input": base_research_input,
        "claim_authority_research_input": research_input,
        "model_visible_messages": list(messages),
        "tool_contract": list(tools),
        "fake_judgment_output": fake,
        "fake_loop_result": loop_result.as_dict(),
        "structured_deliverable_preview": deliverable,
        "saved_r2_negative_replay": {
            "source_full_result_digest": prior_r2["full_result_digest"],
            "source_content_gate": prior_assessment["l1_financial_truth"][
                "gate_status"
            ],
            "rejection_code": prior_r2_rejection_code,
            "silently_promoted": False,
        },
        "normalized_proof": normalized,
        "known_boundary": str(authority["known_boundary"]),
    }
    full_digest = canonical_digest(full_body)
    output = authority["output_contract"]
    private_root = _resolve(str(output["private_output_root_ref"]))
    full_path = private_root / f"full_result_{full_digest}.json"
    _write_new(full_path, {**full_body, "result_digest": full_digest})
    summary_body = {
        "schema_version": result_schema,
        "status": "engineering_pass_zero_call_fixed_pack_claim_authority",
        "recorded_at": "2026-08-14",
        "result_id": str(output["result_id"]),
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "full_result_ref": _relative(full_path),
        "full_result_sha256": _sha(full_path),
        "normalized_proof": normalized,
        "acceptance": {
            "base_v1_2_input_immutable": True,
            "model_still_owns_narrative_judgment": True,
            "claim_and_financial_scope_machine_visible": True,
            "unavailable_direct_bridge_not_exposed": True,
            "saved_r2_overclaim_rejected": True,
            "bounded_informative_judgment_passes": True,
            "zero_request_fixed_pack_loop_passes": True,
            "natural_model_quality_proven": False,
            "agentic_research_proven": False,
            "second_layer_authorized": False,
            "s3_product_acceptance": False,
        },
        "next_decision": (
            "Run at most one new DELL value_capture fixed-pack Chat canary only "
            "after a separate exact-once execution authority binds this proof. "
            "Return L1, content and paired results before any dynamic Layer Two."
        ),
        "known_boundary": str(authority["known_boundary"]),
    }
    summary = {**summary_body, "result_digest": canonical_digest(summary_body)}
    _write_new(_resolve(str(output["public_result_ref"])), summary)
    return summary


def _consumer_rejection_code(
    payload: Mapping[str, Any],
    *,
    research_input: Mapping[str, Any],
) -> str:
    try:
        validate_current_research_output(
            payload,
            research_input=research_input,
            required_cell_ids=["CELL::value_capture"],
        )
    except CurrentResearchConsumerError as exc:
        return exc.code
    raise CurrentResearchConsumerRunnerError(
        "claim_surface_replay_or_mutation_did_not_fail"
    )


def _run_claim_relation_alias_proof(
    *,
    authority: Mapping[str, Any],
    authority_path: Path,
    paths: Mapping[str, Path],
    result_schema: str,
    base_research_input: Mapping[str, Any],
    claim_input: Mapping[str, Any],
    surface_input: Mapping[str, Any],
) -> dict[str, Any]:
    cell_id = "CELL::value_capture"
    corrected = _json(paths["corrected_fake_output_ref"])
    validated = validate_current_research_output(
        corrected,
        research_input=surface_input,
        required_cell_ids=[cell_id],
    )
    deliverable = compile_current_research_deliverable(
        research_input=surface_input,
        judgment_output=corrected,
        required_cell_ids=[cell_id],
    )
    expanded_relations = validated["cells"][0]["claim_relations"]
    if not (
        len(expanded_relations) == 3
        and all(
            set(row)
            == {
                "atom_field",
                "claim_relation_ref",
                "claim_subject",
                "claim_outcome",
                "claim_relation",
                "attribution_basis",
                "claim_scope",
                "financial_scope",
                "causal_bridge_authority",
            }
            for row in expanded_relations
        )
        and deliverable["cells"][0]["claim_relations"]
        == expanded_relations
    ):
        raise CurrentResearchConsumerRunnerError(
            "claim_relation_alias_local_expansion_invalid"
        )

    legacy_full = deepcopy(corrected)
    legacy_full["cells"][0]["claim_relations"] = [
        {
            key: value
            for key, value in row.items()
            if key != "claim_relation_ref"
        }
        for row in expanded_relations
    ]
    unknown_alias = deepcopy(corrected)
    unknown_alias["cells"][0]["claim_relations"][0][
        "claim_relation_ref"
    ] = "CR::MU::PRODUCT_TARGET"
    cross_case_fact = deepcopy(corrected)
    cross_case_fact["cells"][0]["qualitative_fact_refs"] = [
        "QF::MU::CROSS_CASE"
    ]
    missing_support = deepcopy(corrected)
    missing_support["cells"][0]["evidence_uses"][0][
        "use_role"
    ] = "context"
    missing_support["cells"][0]["evidence_uses"][3][
        "use_role"
    ] = "support"
    narrative_conflict = deepcopy(corrected)
    narrative_conflict["cells"][0]["mechanism_atom"] = (
        "AI 服务器收入驱动公司利润扩张，但当前材料没有产品到公司的直接桥。"
    )
    mutation_codes = [
        _consumer_rejection_code(legacy_full, research_input=surface_input),
        _consumer_rejection_code(unknown_alias, research_input=surface_input),
        _consumer_rejection_code(cross_case_fact, research_input=surface_input),
        _consumer_rejection_code(missing_support, research_input=surface_input),
        _consumer_rejection_code(
            narrative_conflict,
            research_input=surface_input,
        ),
    ]
    expected_mutations = [
        "claim_surface_claim_relation_invalid",
        "claim_surface_relation_alias_invalid",
        "research_consumer_qualitative_fact_boundary_invalid",
        "claim_surface_required_authority_missing",
        "claim_surface_narrative_relation_conflict",
    ]
    if mutation_codes != expected_mutations:
        raise CurrentResearchConsumerRunnerError(
            "claim_relation_alias_mutation_disposition_invalid"
        )

    policy = _json(paths["claim_surface_authority_policy_ref"])
    source_drift = deepcopy(policy)
    source_drift["source_bound_qualitative_facts"][0][
        "source_evidence_item_digest"
    ] = "0" * 64
    try:
        compile_claim_surface_authority_research_input(
            claim_input,
            policy=source_drift,
        )
    except ClaimSurfaceAuthorityError as exc:
        source_drift_code = exc.code
    else:
        raise CurrentResearchConsumerRunnerError(
            "claim_relation_alias_source_drift_did_not_fail"
        )
    cross_case_codes: list[str] = []
    for case_key in ("MU", "NVDA"):
        contaminated = deepcopy(claim_input)
        contaminated["case_identity"]["case_key"] = case_key
        try:
            compile_claim_surface_authority_research_input(
                contaminated,
                policy=policy,
            )
        except ClaimSurfaceAuthorityError as exc:
            cross_case_codes.append(exc.code)
        else:
            raise CurrentResearchConsumerRunnerError(
                "claim_relation_alias_cross_case_did_not_fail"
            )
    if not (
        source_drift_code == "claim_surface_qualitative_fact_source_drift"
        and cross_case_codes
        == [
            "claim_surface_base_input_not_qualified",
            "claim_surface_base_input_not_qualified",
        ]
    ):
        raise CurrentResearchConsumerRunnerError(
            "claim_relation_alias_source_or_case_isolation_invalid"
        )

    prior_result = _json(paths["prior_chat_result_ref"])
    prior_assessment = _json(paths["prior_chat_assessment_ref"])
    observed = prior_assessment.get("observed", {})
    if not (
        prior_result.get("status") == "terminal_failed_no_retry"
        and prior_result.get("failure_code")
        == "model_gateway_reasoning_budget_exhausted"
        and prior_result.get("execution", {}).get("model_calls_attempted") == 2
        and observed.get("step_two_finish_reason") == "length"
        and observed.get("step_two_reasoning_tokens") == 16000
        and observed.get("step_two_visible_content_chars") == 0
        and prior_assessment.get("acceptance", {}).get(
            "fixed_pack_layer_one_accepted"
        )
        is False
    ):
        raise CurrentResearchConsumerRunnerError(
            "claim_relation_alias_prior_capacity_disposition_invalid"
        )
    prior_request = _json(paths["prior_step_two_request_ref"])
    request_body = prior_request.get("request_body")
    if not isinstance(request_body, Mapping):
        raise CurrentResearchConsumerRunnerError(
            "claim_relation_alias_prior_request_invalid"
        )
    prior_message_chars = len(
        json.dumps(
            request_body.get("messages"),
            ensure_ascii=False,
        )
    )
    prior_tool_chars = len(
        json.dumps(
            request_body.get("tools"),
            ensure_ascii=False,
        )
    )
    if not (
        abs(
            prior_message_chars
            - int(observed["step_two_model_visible_message_chars"])
        )
        <= 64
        and prior_tool_chars == int(observed["step_two_tool_schema_chars"])
    ):
        raise CurrentResearchConsumerRunnerError(
            "claim_relation_alias_prior_capacity_measurement_drift"
        )

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
    base_policy = load_bounded_finance_loop_policy(
        _json(paths["loop_policy_ref"])
    )
    scoped = scope_bounded_finance_loop_policy(
        base_policy,
        cell_count=1,
        maximum_evidence_requests=0,
    )
    tools = compile_finance_loop_tools(
        research_input=surface_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        policy=scoped,
        strict=False,
    )
    tool_names = [str(row["function"]["name"]) for row in tools]
    if tool_names != [
        READ_REVIEWED_EVIDENCE_TOOL,
        READ_NUMERIC_FACTS_TOOL,
        SUBMIT_RESEARCH_JUDGMENT_TOOL,
    ]:
        raise CurrentResearchConsumerRunnerError(
            "claim_relation_alias_zero_budget_tool_surface_invalid"
        )
    visible_budget = {
        "maximum_steps": scoped.maximum_steps,
        "maximum_evidence_requests": 0,
        "maximum_reads_per_cell": 1,
        "maximum_parallel_read_tools": 2,
        "maximum_judgments_per_cell": 1,
        "retry_count": 0,
    }
    initial_messages = compile_finance_loop_messages(
        research_input=surface_input,
        required_cell_ids=[cell_id],
        execution_budget=visible_budget,
    )
    step_two_messages: list[dict[str, Any]] = []

    def execute_step(
        messages: Sequence[Mapping[str, Any]],
        _tools: Sequence[Mapping[str, Any]],
        index: int,
    ) -> ChatCompletionToolStepResult:
        if index == 1:
            return _tool_step(
                index,
                [
                    (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
                    (READ_NUMERIC_FACTS_TOOL, {"cell_id": cell_id}),
                ],
            )
        step_two_messages.extend(deepcopy(list(messages)))
        return _tool_step(
            index,
            [(SUBMIT_RESEARCH_JUDGMENT_TOOL, corrected["cells"][0])],
        )

    loop_result = run_bounded_finance_loop(
        policy=scoped,
        research_input=surface_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
        tools=tools,
        step_executor=execute_step,
        visible_execution_budget=visible_budget,
    )
    current_message_chars = len(
        json.dumps(step_two_messages, ensure_ascii=False)
    )
    current_tool_chars = len(json.dumps(list(tools), ensure_ascii=False))
    tool_results = [
        json.loads(str(row["content"]))
        for row in step_two_messages
        if row.get("role") == "tool"
    ]
    evidence_view = next(
        row
        for row in tool_results
        if row.get("status") == "reviewed_evidence_read"
    )
    numeric_view = next(
        row
        for row in tool_results
        if row.get("status") == "authoritative_numeric_facts_read"
    )
    compact_numeric = numeric_view["numeric_facts"][0]
    private_lineage_retained = any(
        "source_digests" in row
        and "citation_urls" in row
        and "source_observation_ids" in row
        for row in surface_input["numeric_fact_cards"]
    )
    compact_lineage_hidden = all(
        key not in compact_numeric
        for key in (
            "source_digests",
            "citation_urls",
            "source_observation_ids",
        )
    )
    initial_visible = json.loads(initial_messages[1]["content"])
    authority_cards_visible_once = (
        "role_method_pack" not in initial_visible["required_cells"][0]
        and "graph_context_pack" not in initial_visible["required_cells"][0]
        and "role_method_pack" in evidence_view
        and "graph_context_pack" in evidence_view
    )
    if not (
        current_message_chars
        < int(observed["step_two_model_visible_message_chars"]) / 2
        and current_tool_chars
        < int(observed["step_two_tool_schema_chars"]) * 0.55
        and private_lineage_retained
        and compact_lineage_hidden
        and authority_cards_visible_once
        and evidence_view.get("model_view_profile")
        == "claim_relation_alias_compact_v1"
        and numeric_view.get("model_view_profile")
        == "claim_relation_alias_compact_v1"
        and loop_result.status == "completed_all_required_cells"
        and loop_result.step_count == 2
        and loop_result.tool_call_count == 3
        and loop_result.tool_counts.get(SUBMIT_EVIDENCE_REQUEST_TOOL, 0) == 0
    ):
        raise CurrentResearchConsumerRunnerError(
            "claim_relation_alias_capacity_or_fake_loop_invalid"
        )

    replay_claim_input = compile_claim_authority_research_input(
        base_research_input,
        policy=_json(paths["claim_authority_policy_ref"]),
    )
    replay_surface_input = compile_claim_surface_authority_research_input(
        replay_claim_input,
        policy=policy,
    )
    replay_messages = compile_finance_loop_messages(
        research_input=replay_surface_input,
        required_cell_ids=[cell_id],
        execution_budget=visible_budget,
    )
    replay_tools = compile_finance_loop_tools(
        research_input=replay_surface_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        policy=scoped,
        strict=False,
    )
    if not (
        replay_surface_input == surface_input
        and replay_messages == initial_messages
        and replay_tools == tools
    ):
        raise CurrentResearchConsumerRunnerError(
            "claim_relation_alias_deterministic_recompile_invalid"
        )

    normalized = {
        "base_research_input_digest": base_research_input[
            "research_input_digest"
        ],
        "claim_authority_input_digest": claim_input[
            "research_input_digest"
        ],
        "claim_relation_alias_input_digest": surface_input[
            "research_input_digest"
        ],
        "finance_loop_initial_messages_digest": canonical_digest(
            list(initial_messages)
        ),
        "finance_loop_step_two_messages_digest": canonical_digest(
            step_two_messages
        ),
        "standard_tool_schema_digest": canonical_digest(list(tools)),
        "deliverable_digest": deliverable["deliverable_digest"],
        "prior_capacity_failure_code": prior_result["failure_code"],
        "prior_step_two_message_chars": int(
            observed["step_two_model_visible_message_chars"]
        ),
        "current_step_two_message_chars": current_message_chars,
        "current_to_prior_message_ratio": round(
            current_message_chars
            / int(observed["step_two_model_visible_message_chars"]),
            6,
        ),
        "prior_tool_schema_chars": int(
            observed["step_two_tool_schema_chars"]
        ),
        "current_tool_schema_chars": current_tool_chars,
        "current_to_prior_tool_ratio": round(
            current_tool_chars / int(observed["step_two_tool_schema_chars"]),
            6,
        ),
        "wire_tool_names": tool_names,
        "zero_budget_evidence_request_tool_omitted": True,
        "relation_aliases_selected": 3,
        "relations_expanded_locally": 3,
        "full_internal_lineage_retained": private_lineage_retained,
        "compact_model_view_hides_audit_lineage": compact_lineage_hidden,
        "authority_cards_visible_once": authority_cards_visible_once,
        "mutation_failure_codes": mutation_codes,
        "source_digest_drift_code": source_drift_code,
        "cross_case_isolation_codes": cross_case_codes,
        "fake_loop_steps": loop_result.step_count,
        "fake_loop_tool_calls": loop_result.tool_call_count,
        "fake_loop_evidence_requests": 0,
        "network_calls": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "local_embedding_calls": 0,
        "retries": 0,
        "deterministic_recompile_equal": True,
    }
    full_body = {
        "schema_version": (
            "fin_ia_fixed_pack_claim_relation_alias_zero_call_full_v1_0"
        ),
        "status": "completed_zero_call_claim_relation_alias_capacity_proof",
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "base_research_input": base_research_input,
        "claim_authority_input": claim_input,
        "claim_relation_alias_input": surface_input,
        "model_visible_initial_messages": list(initial_messages),
        "model_visible_step_two_messages": step_two_messages,
        "tool_contract": list(tools),
        "corrected_fake_judgment_output": corrected,
        "validated_expanded_judgment_output": validated,
        "fake_loop_result": loop_result.as_dict(),
        "structured_deliverable_preview": deliverable,
        "prior_capacity_failure_binding": {
            "source_result_digest": prior_result["result_digest"],
            "source_assessment_status": prior_assessment["status"],
            "request_capture_sha256": _sha(
                paths["prior_step_two_request_ref"]
            ),
            "response_capture_sha256": _sha(
                paths["prior_step_two_response_ref"]
            ),
            "silently_promoted": False,
        },
        "normalized_proof": normalized,
        "known_boundary": str(authority["known_boundary"]),
    }
    full_digest = canonical_digest(full_body)
    output = authority["output_contract"]
    private_root = _resolve(str(output["private_output_root_ref"]))
    full_path = private_root / f"full_result_{full_digest}.json"
    _write_new(full_path, {**full_body, "result_digest": full_digest})
    summary_body = {
        "schema_version": result_schema,
        "status": "engineering_pass_zero_call_claim_relation_alias_capacity",
        "recorded_at": str(authority["issued_at"]),
        "result_id": str(output["result_id"]),
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "full_result_ref": _relative(full_path),
        "full_result_sha256": _sha(full_path),
        "normalized_proof": normalized,
        "acceptance": {
            "prior_capacity_failure_immutable": True,
            "relation_alias_selection_and_local_expansion_pass": True,
            "authority_cards_visible_once_pass": True,
            "compact_model_view_and_private_lineage_separation_pass": True,
            "zero_budget_tool_removal_pass": True,
            "capacity_reduction_pass": True,
            "fake_loop_and_mutation_pass": True,
            "natural_replacement_live_proven": False,
            "fixed_pack_layer_one_accepted": False,
            "dynamic_layer_two_authorized": False,
            "s3_product_acceptance": False,
        },
        "next_decision": (
            "After a clean synced preflight, a separate exact-once authority may "
            "bind one natural fixed-Pack successor with the same Evidence Pack "
            "and provider profile. Dynamic Layer Two remains blocked until that "
            "run produces an L1- and content-assessable Judgment."
        ),
        "known_boundary": str(authority["known_boundary"]),
    }
    summary = {**summary_body, "result_digest": canonical_digest(summary_body)}
    _write_new(_resolve(str(output["public_result_ref"])), summary)
    return summary


def _run_claim_surface_authority_proof(
    *,
    authority: Mapping[str, Any],
    authority_path: Path,
    paths: Mapping[str, Path],
    result_schema: str,
    base_research_input: Mapping[str, Any],
) -> dict[str, Any]:
    claim_input = compile_claim_authority_research_input(
        base_research_input,
        policy=_json(paths["claim_authority_policy_ref"]),
    )
    surface_input = compile_claim_surface_authority_research_input(
        claim_input,
        policy=_json(paths["claim_surface_authority_policy_ref"]),
    )
    if (
        surface_input.get("claim_surface_authority_contract", {}).get(
            "model_view_mode"
        )
        == "claim_relation_alias_compact_v1"
    ):
        return _run_claim_relation_alias_proof(
            authority=authority,
            authority_path=authority_path,
            paths=paths,
            result_schema=result_schema,
            base_research_input=base_research_input,
            claim_input=claim_input,
            surface_input=surface_input,
        )
    cell_id = "CELL::value_capture"
    failed = _json(paths["failed_chat_payload_ref"])
    failed["cells"][0]["what_would_change"][
        "threshold_numeric_ref"
    ] = None
    corrected = _json(paths["corrected_fake_output_ref"])

    predecessor_schema_code = _consumer_rejection_code(
        failed,
        research_input=surface_input,
    )
    alias_migrated = deepcopy(failed)
    for field in ("claim_relations", "qualitative_fact_refs"):
        alias_migrated["cells"][0][field] = deepcopy(
            corrected["cells"][0][field]
        )
    qualitative_surface_code = _consumer_rejection_code(
        alias_migrated,
        research_input=surface_input,
    )
    alias_migrated["cells"][0]["thesis_atom"] = alias_migrated["cells"][0][
        "thesis_atom"
    ].replace(
        "其中个位数经营利润率目标",
        "所选管理层经营利润率目标",
    )
    alias_migrated["cells"][0]["mechanism_atom"] = alias_migrated["cells"][0][
        "mechanism_atom"
    ].replace(
        "中个位数经营利润率目标",
        "所选管理层经营利润率目标",
    )
    relation_conflict_code = _consumer_rejection_code(
        alias_migrated,
        research_input=surface_input,
    )
    if (
        predecessor_schema_code
        != "research_consumer_output_cell_fields_invalid"
        or qualitative_surface_code
        != "research_consumer_thesis_atom_invalid"
        or relation_conflict_code
        != "claim_surface_narrative_relation_conflict"
    ):
        raise CurrentResearchConsumerRunnerError(
            "claim_surface_failed_live_replay_disposition_invalid"
        )

    validated = validate_current_research_output(
        corrected,
        research_input=surface_input,
        required_cell_ids=[cell_id],
    )
    deliverable = compile_current_research_deliverable(
        research_input=surface_input,
        judgment_output=corrected,
        required_cell_ids=[cell_id],
    )
    surfaces = deliverable["cells"][0][
        "source_bound_qualitative_fact_surfaces"
    ]
    if not (
        len(surfaces) == 1
        and surfaces[0]["display_surface_zh"]
        == "中个位数经营利润率目标"
        and surfaces[0]["point_estimate_generated"] is False
        and validated["cells"][0]["claim_surface_authority_receipt"][
            "structured_claim_relation_primary"
        ]
        is True
    ):
        raise CurrentResearchConsumerRunnerError(
            "claim_surface_deterministic_render_invalid"
        )

    mutation_codes: list[str] = []
    cross_case = deepcopy(corrected)
    cross_case["cells"][0]["qualitative_fact_refs"] = [
        "QF::MU::CROSS_CASE"
    ]
    mutation_codes.append(
        _consumer_rejection_code(cross_case, research_input=surface_input)
    )
    wrong_relation = deepcopy(corrected)
    wrong_relation["cells"][0]["claim_relations"][0][
        "claim_relation"
    ] = "same_scope_numeric_observation"
    mutation_codes.append(
        _consumer_rejection_code(wrong_relation, research_input=surface_input)
    )
    missing_support = deepcopy(corrected)
    missing_support["cells"][0]["evidence_uses"][0]["use_role"] = "context"
    missing_support["cells"][0]["evidence_uses"][3]["use_role"] = "support"
    mutation_codes.append(
        _consumer_rejection_code(missing_support, research_input=surface_input)
    )
    narrative_conflict = deepcopy(corrected)
    narrative_conflict["cells"][0]["mechanism_atom"] = (
        "AI 服务器收入驱动公司利润扩张，但当前材料没有产品到公司的直接桥。"
    )
    mutation_codes.append(
        _consumer_rejection_code(
            narrative_conflict,
            research_input=surface_input,
        )
    )
    if mutation_codes != [
        "research_consumer_qualitative_fact_boundary_invalid",
        "claim_surface_combination_invalid",
        "claim_surface_required_authority_missing",
        "claim_surface_narrative_relation_conflict",
    ]:
        raise CurrentResearchConsumerRunnerError(
            "claim_surface_mutation_disposition_invalid"
        )

    policy = _json(paths["claim_surface_authority_policy_ref"])
    source_drift = deepcopy(policy)
    source_drift["source_bound_qualitative_facts"][0][
        "source_evidence_item_digest"
    ] = "0" * 64
    try:
        compile_claim_surface_authority_research_input(
            claim_input,
            policy=source_drift,
        )
    except ClaimSurfaceAuthorityError as exc:
        source_drift_code = exc.code
    else:
        raise CurrentResearchConsumerRunnerError(
            "claim_surface_source_drift_did_not_fail"
        )
    cross_case_codes: list[str] = []
    for case_key in ("MU", "NVDA"):
        contaminated = deepcopy(claim_input)
        contaminated["case_identity"]["case_key"] = case_key
        try:
            compile_claim_surface_authority_research_input(
                contaminated,
                policy=policy,
            )
        except ClaimSurfaceAuthorityError as exc:
            cross_case_codes.append(exc.code)
        else:
            raise CurrentResearchConsumerRunnerError(
                "claim_surface_cross_case_did_not_fail"
            )
    if not (
        source_drift_code == "claim_surface_qualitative_fact_source_drift"
        and cross_case_codes
        == [
            "claim_surface_base_input_not_qualified",
            "claim_surface_base_input_not_qualified",
        ]
    ):
        raise CurrentResearchConsumerRunnerError(
            "claim_surface_source_or_case_isolation_invalid"
        )

    prior_result = _json(paths["prior_chat_result_ref"])
    prior_assessment = _json(paths["prior_chat_assessment_ref"])
    if not (
        prior_result.get("status") == "terminal_failed_no_retry"
        and prior_result.get("failure_code")
        == "finance_loop_judgment_invalid:research_consumer_thesis_atom_invalid"
        and prior_assessment.get("acceptance", {}).get(
            "fixed_pack_layer_one_accepted"
        )
        is False
        and prior_assessment.get("acceptance", {}).get(
            "dynamic_layer_two_authorized"
        )
        is False
    ):
        raise CurrentResearchConsumerRunnerError(
            "claim_surface_prior_live_disposition_invalid"
        )

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
    base_policy = load_bounded_finance_loop_policy(
        _json(paths["loop_policy_ref"])
    )
    scoped = scope_bounded_finance_loop_policy(
        base_policy,
        cell_count=1,
        maximum_evidence_requests=0,
    )
    tools = compile_finance_loop_tools(
        research_input=surface_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        policy=scoped,
        strict=False,
    )
    visible_budget = {
        "maximum_steps": scoped.maximum_steps,
        "maximum_evidence_requests": 0,
        "maximum_reads_per_cell": 1,
        "maximum_parallel_read_tools": 2,
        "maximum_judgments_per_cell": 1,
        "retry_count": 0,
    }
    messages = compile_finance_loop_messages(
        research_input=surface_input,
        required_cell_ids=[cell_id],
        execution_budget=visible_budget,
    )
    loop_result = run_bounded_finance_loop(
        policy=scoped,
        research_input=surface_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
        tools=tools,
        step_executor=lambda _messages, _tools, index: (
            _tool_step(
                index,
                [
                    (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
                    (READ_NUMERIC_FACTS_TOOL, {"cell_id": cell_id}),
                ],
            )
            if index == 1
            else _tool_step(
                index,
                [(SUBMIT_RESEARCH_JUDGMENT_TOOL, corrected["cells"][0])],
            )
        ),
        visible_execution_budget=visible_budget,
    )
    replay_claim_input = compile_claim_authority_research_input(
        base_research_input,
        policy=_json(paths["claim_authority_policy_ref"]),
    )
    replay_surface_input = compile_claim_surface_authority_research_input(
        replay_claim_input,
        policy=policy,
    )
    replay_messages = compile_finance_loop_messages(
        research_input=replay_surface_input,
        required_cell_ids=[cell_id],
        execution_budget=visible_budget,
    )
    if not (
        replay_surface_input == surface_input
        and replay_messages == messages
        and loop_result.status == "completed_all_required_cells"
        and loop_result.step_count == 2
        and loop_result.tool_call_count == 3
        and loop_result.tool_counts.get("submit_evidence_request", 0) == 0
    ):
        raise CurrentResearchConsumerRunnerError(
            "claim_surface_zero_call_determinism_or_loop_invalid"
        )

    normalized = {
        "base_research_input_digest": base_research_input[
            "research_input_digest"
        ],
        "claim_authority_input_digest": claim_input[
            "research_input_digest"
        ],
        "claim_surface_input_digest": surface_input[
            "research_input_digest"
        ],
        "finance_loop_messages_digest": canonical_digest(list(messages)),
        "standard_tool_schema_digest": canonical_digest(list(tools)),
        "deliverable_digest": deliverable["deliverable_digest"],
        "failed_live_predecessor_schema_replay_code": predecessor_schema_code,
        "failed_live_qualitative_surface_replay_code": qualitative_surface_code,
        "failed_live_relation_replay_code": relation_conflict_code,
        "mutation_failure_codes": mutation_codes,
        "source_digest_drift_code": source_drift_code,
        "cross_case_isolation_codes": cross_case_codes,
        "source_bound_qualitative_surface": surfaces[0][
            "display_surface_zh"
        ],
        "qualitative_band_converted_to_point_estimate": False,
        "structured_claim_relations_per_atom": 3,
        "fixed_pack_unit_test_only": True,
        "dynamic_retrieval_executed": False,
        "agentic_research_claimed": False,
        "fake_loop_steps": loop_result.step_count,
        "fake_loop_tool_calls": loop_result.tool_call_count,
        "fake_loop_evidence_requests": 0,
        "network_calls": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "local_embedding_calls": 0,
        "retries": 0,
        "deterministic_recompile_equal": True,
    }
    full_body = {
        "schema_version": (
            "fin_ia_fixed_pack_claim_surface_authority_zero_call_full_v1_0"
        ),
        "status": "completed_zero_call_claim_surface_authority_proof",
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "base_research_input": base_research_input,
        "claim_authority_input": claim_input,
        "claim_surface_authority_input": surface_input,
        "model_visible_messages": list(messages),
        "tool_contract": list(tools),
        "corrected_fake_judgment_output": corrected,
        "fake_loop_result": loop_result.as_dict(),
        "structured_deliverable_preview": deliverable,
        "failed_live_replay": {
            "source_result_digest": prior_result["result_digest"],
            "source_assessment_status": prior_assessment["status"],
            "predecessor_schema_code": predecessor_schema_code,
            "qualitative_surface_code": qualitative_surface_code,
            "relation_conflict_code": relation_conflict_code,
            "silently_promoted": False,
        },
        "normalized_proof": normalized,
        "known_boundary": str(authority["known_boundary"]),
    }
    full_digest = canonical_digest(full_body)
    output = authority["output_contract"]
    private_root = _resolve(str(output["private_output_root_ref"]))
    full_path = private_root / f"full_result_{full_digest}.json"
    _write_new(full_path, {**full_body, "result_digest": full_digest})
    summary_body = {
        "schema_version": result_schema,
        "status": "engineering_pass_zero_call_claim_surface_authority",
        "recorded_at": str(authority["issued_at"]),
        "result_id": str(output["result_id"]),
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "full_result_ref": _relative(full_path),
        "full_result_sha256": _sha(full_path),
        "normalized_proof": normalized,
        "acceptance": {
            "predecessor_failed_live_immutable": True,
            "source_bound_qualitative_fact_alias_compiled": True,
            "qualitative_band_point_estimate_forbidden": True,
            "three_narrative_atoms_have_structured_relations": True,
            "legacy_lexical_guard_is_secondary_only": True,
            "corrected_zero_call_judgment_passes": True,
            "zero_request_fixed_pack_loop_passes": True,
            "cross_case_isolation_passes": True,
            "natural_replacement_live_proven": False,
            "fixed_pack_layer_one_accepted": False,
            "dynamic_layer_two_authorized": False,
            "s3_product_acceptance": False,
        },
        "next_decision": (
            "Return this zero-call result to Owner. Do not run another model or "
            "enter dynamic Layer Two unless Owner separately authorizes one "
            "replacement fixed-pack live after reviewing the structural result."
        ),
        "known_boundary": str(authority["known_boundary"]),
    }
    summary = {**summary_body, "result_digest": canonical_digest(summary_body)}
    _write_new(_resolve(str(output["public_result_ref"])), summary)
    return summary


def run(authority_path: Path) -> dict[str, Any]:
    authority = _json(authority_path)
    paths, result_schema = validate_authority(
        authority,
        authority_path=authority_path,
    )
    evidence_service, retrieval_service = _services()
    read = frozenset({"current_product:read"})
    evidence_pack = evidence_service.get_case(
        "DELL", ResearchEvidencePackPrincipal("current", read)
    )
    controlled = retrieval_service.execute_controlled_plan(
        "DELL",
        _json(paths["objective_ref"]),
        _json(paths["planner_atoms_ref"]),
        ResearchRetrievalPrincipal("current", read),
    )
    research_input = compile_current_research_input(
        policy=_json(paths["consumer_policy_ref"]),
        evidence_pack=evidence_pack,
        controlled_plan=controlled,
    )
    if "claim_surface_authority_policy_ref" in paths:
        return _run_claim_surface_authority_proof(
            authority=authority,
            authority_path=authority_path,
            paths=paths,
            result_schema=result_schema,
            base_research_input=research_input,
        )
    if "claim_authority_policy_ref" in paths:
        return _run_claim_authority_proof(
            authority=authority,
            authority_path=authority_path,
            paths=paths,
            result_schema=result_schema,
            evidence_pack=evidence_pack,
            controlled=controlled,
            base_research_input=research_input,
        )
    messages = compile_current_research_messages(research_input)
    fake = _json(paths["fake_output_ref"])
    deliverable = compile_current_research_deliverable(
        research_input=research_input,
        judgment_output=fake,
    )
    mutations = _mutation_codes(
        research_input=research_input,
        fake=fake,
    )
    failed_r1_replay = _replay_failed_r1(
        research_input=research_input,
        payload=_json(paths["failed_r1_payload_ref"]),
        audit=_json(paths["failed_r1_audit_ref"]),
    )
    full_body = {
        "schema_version": "fin_ia_current_research_consumer_zero_call_full_v1_1",
        "status": "completed_zero_network_zero_model_current_consumer_proof",
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "evidence_pack_projection": evidence_pack,
        "controlled_plan_projection": controlled,
        "research_input": research_input,
        "model_visible_messages": list(messages),
        "fake_judgment_output": fake,
        "structured_deliverable_preview": deliverable,
        "mutation_failure_codes": mutations,
        "failed_r1_replay": failed_r1_replay,
        "known_boundary": str(authority["known_boundary"]),
    }
    full_digest = canonical_digest(full_body)
    output = authority["output_contract"]
    private_root = _resolve(str(output["private_output_root_ref"]))
    full_path = private_root / f"full_result_{full_digest}.json"
    _write_new(full_path, {**full_body, "result_digest": full_digest})
    source_types = sorted(
        {row["source_type"] for row in research_input["evidence_cards"]}
    )
    context_cells = [
        {
            "cell_id": row["cell_id"],
            "role_method_pack_id": (
                row["role_method_pack"]["pack_id"]
                if row.get("role_method_pack")
                else None
            ),
            "method_step_count": len(
                (row.get("role_method_pack") or {}).get("method_steps", ())
            ),
            "minimum_consumed_method_steps": row[
                "context_consumption_contract"
            ]["minimum_method_step_refs"],
            "graph_node_count": len(row["graph_context_pack"]["nodes"]),
            "graph_edge_count": len(row["graph_context_pack"]["edges"]),
            "archived_graph_rows_used": row["graph_context_pack"]["authority"][
                "archived_graph_rows_used"
            ],
        }
        for row in research_input["cells"]
    ]
    summary_body = {
        "schema_version": result_schema,
        "status": "engineering_pass_zero_call_current_consumer_contract_successor",
        "recorded_at": "2026-08-13",
        "result_id": str(output["result_id"]),
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "full_result_ref": _relative(full_path),
        "full_result_sha256": _sha(full_path),
        "bindings": {
            "case_key": research_input["case_identity"]["case_key"],
            "research_as_of": research_input["case_identity"]["research_as_of"],
            "evidence_pack_artifact_digest": evidence_pack["artifact_digest"],
            "evidence_pack_payload_digest": evidence_pack["pack_payload_digest"],
            "controlled_plan_digest": controlled["compiled_plan"]["plan_digest"],
            "research_input_digest": research_input["research_input_digest"],
            "deliverable_digest": deliverable["deliverable_digest"],
        },
        "observed": {
            "reviewed_pack_evidence_count": len(evidence_pack["evidence_items"]),
            "model_visible_evidence_count": len(research_input["evidence_cards"]),
            "reviewed_transcript_evidence_count": sum(
                row["source_type"] == "EARNINGS_CALL_TRANSCRIPT"
                for row in research_input["evidence_cards"]
            ),
            "source_types": source_types,
            "controlled_plan_numeric_fact_count": controlled["summary"][
                "numeric_fact_count"
            ],
            "semantic_unique_numeric_fact_count": research_input[
                "input_selection_summary"
            ]["semantic_unique_fact_count_before_period_selection"],
            "model_visible_numeric_fact_count": len(
                research_input["numeric_fact_cards"]
            ),
            "model_visible_residual_gap_count": len(
                research_input["residual_gap_cards"]
            ),
            "research_cell_count": len(research_input["cells"]),
            "research_context_cells": context_cells,
            "role_method_pack_count": sum(
                row["role_method_pack_id"] is not None for row in context_cells
            ),
            "graph_context_pack_count": len(context_cells),
            "mutation_failure_codes": mutations,
            "failed_r1_model_visible_user_chars": 48380,
            "successor_model_visible_user_chars": len(messages[1]["content"]),
            "failed_r1_replay": failed_r1_replay,
            "network_calls": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "local_embedding_calls": 0,
        },
        "acceptance": {
            "reviewed_source_policy_separate_from_open_retrieval": True,
            "transcript_automatic_numeric_promotion": False,
            "request_identity_numeric_duplicates_removed": True,
            "model_sees_exact_source_facts_and_numeric_facts": True,
            "model_free_numeric_prose_blocked": True,
            "unknown_and_cross_cell_refs_blocked": True,
            "trusted_envelope_harness_injected": True,
            "exact_model_visible_enums_exposed": True,
            "typed_evidence_use_and_inference_authority": True,
            "all_five_cells_have_role_method_pack": (
                len(context_cells) == 5
                and all(row["role_method_pack_id"] for row in context_cells)
            ),
            "all_graph_context_compiled_from_current_case": all(
                row["archived_graph_rows_used"] is False
                for row in context_cells
            ),
            "all_visible_residual_gaps_preserved": True,
            "failed_r1_not_silently_salvaged": True,
            "harness_generated_research_conclusion": False,
            "fake_deliverable_published_to_product": False,
            "natural_model_quality_proven": False,
            "s3_product_acceptance": False,
        },
        "next_decision": (
            "Make a separate value-cost-risk decision before any replacement "
            "DeepSeek call. If authorized later, test this changed synthesis "
            "contract once; require deterministic L1, absolute content-quality, "
            "paired and qualified-human review before any product publication."
        ),
        "known_boundary": str(authority["known_boundary"]),
    }
    summary = {**summary_body, "result_digest": canonical_digest(summary_body)}
    _write_new(_resolve(str(output["public_result_ref"])), summary)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--authority",
        default=(
            "configs/research/evals/"
            "fin_ia_0_1_3_s3_dell_current_research_consumer_zero_call_authority_v1_2.json"
        ),
    )
    args = parser.parse_args(argv)
    result = run(_resolve(args.authority))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
