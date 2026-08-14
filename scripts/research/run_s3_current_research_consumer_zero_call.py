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
from sec_agent.research.bounded_finance_loop import (  # noqa: E402
    READ_NUMERIC_FACTS_TOOL,
    READ_REVIEWED_EVIDENCE_TOOL,
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
        schema in {AUTHORITY_SCHEMA, CLAIM_AUTHORITY_SCHEMA}
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
    else:
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
    return paths, (
        CLAIM_RESULT_SCHEMA if schema == CLAIM_AUTHORITY_SCHEMA else RESULT_SCHEMA
    )


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
