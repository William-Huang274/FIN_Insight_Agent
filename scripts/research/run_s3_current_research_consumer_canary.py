from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence


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
from retrieval.route_compiler import (  # noqa: E402
    load_query_object_fact_route_policy,
)
from sec_agent.providers.chat_completions import (  # noqa: E402
    ChatCompletionProfile,
    ChatCompletionResult,
    ChatCompletionToolStepResult,
    ModelGatewayError,
    execute_chat_completion_exact_once,
    execute_chat_completion_tool_step_exact_once,
    load_chat_completion_profile,
)
from sec_agent.research.bounded_finance_loop import (  # noqa: E402
    BoundedFinanceLoopError,
    MICRO_JUDGMENT_TOOL_NAMES,
    READ_NUMERIC_FACTS_TOOL,
    READ_REVIEWED_EVIDENCE_TOOL,
    SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL,
    SUBMIT_RESEARCH_MECHANISM_TOOL,
    SUBMIT_RESEARCH_THESIS_TOOL,
    compile_finance_micro_fragment_analysis_messages,
    compile_finance_micro_fragment_context,
    compile_finance_micro_fragment_submission_successor,
    compile_finance_micro_fragment_validation_repair_successor,
    compile_finance_micro_fragment_submission_messages,
    compile_finance_micro_judgment_fragments,
    compile_finance_micro_judgment_tools,
    compile_finance_loop_messages,
    compile_finance_loop_tools,
    load_bounded_finance_loop_policy,
    load_fixed_pack_micro_judgment_policy,
    run_bounded_finance_loop,
    scope_bounded_finance_micro_judgment_policy,
    scope_bounded_finance_loop_policy,
    validate_deepseek_ga_json_profile,
    validate_deepseek_ga_node_profile,
    validate_deepseek_ga_profile,
    validate_finance_micro_judgment_fragment,
)
from sec_agent.research.current_consumer import (  # noqa: E402
    CurrentResearchConsumerError,
    compile_current_research_deliverable,
    compile_current_research_input,
    compile_current_research_messages,
    parse_current_research_output,
)
from sec_agent.research.claim_authority import (  # noqa: E402
    compile_claim_authority_research_input,
)
from sec_agent.research.claim_surface_authority import (  # noqa: E402
    compile_claim_surface_authority_research_input,
)
from sec_agent.research.reviewed_evidence_pack import (  # noqa: E402
    canonical_digest,
)
from sec_agent.research.paired_submission import (  # noqa: E402
    PairedResearchSubmission,
    compile_paired_research_submission,
    run_paired_research_submission,
)
from sec_agent.research.planning import (  # noqa: E402
    load_research_planning_policy,
)
from sec_agent.runtime_bridge.paths import resolve_runtime_paths  # noqa: E402
from sec_agent.runtime_resource_registry import (  # noqa: E402
    read_registered_runtime_json,
)


AUTHORITY_SCHEMA = "fin_ia_current_research_consumer_canary_authority_v1_1"
PRE_VS4_EVIDENCE_PACK_RESULT = ROOT / (
    "configs/runtime/fin_ia_current_research_evidence_pack_result_v1_1.json"
)
PRE_VS4_REVIEWED_ANCHOR_CATALOG = ROOT / (
    "configs/runtime/fin_ia_0_1_3_current_reviewed_claim_anchor_catalog_v1_0.json"
)
RESULT_SCHEMA = "fin_ia_current_research_consumer_canary_result_v1_1"
FULL_SCHEMA = "fin_ia_current_research_consumer_canary_full_v1_1"
PAIRED_AUTHORITY_SCHEMA = (
    "fin_ia_s3_deepseek_ga_single_cell_paired_authority_v1_0"
)
PAIRED_RESULT_SCHEMA = "fin_ia_s3_deepseek_ga_single_cell_paired_result_v1_0"
PAIRED_FULL_SCHEMA = "fin_ia_s3_deepseek_ga_single_cell_paired_full_v1_0"
TOOL_LOOP_AUTHORITY_SCHEMA = (
    "fin_ia_s3_bounded_finance_loop_live_authority_v1_0"
)
TOOL_LOOP_RESULT_SCHEMA = "fin_ia_s3_bounded_finance_loop_live_result_v1_0"
TOOL_LOOP_FULL_SCHEMA = "fin_ia_s3_bounded_finance_loop_live_full_v1_0"
MICRO_TOOL_LOOP_AUTHORITY_SCHEMA = (
    "fin_ia_s3_fixed_pack_micro_judgment_live_authority_v1_0"
)
MICRO_TOOL_LOOP_AUTHORITY_STATUS = (
    "signed_exact_once_fixed_pack_micro_judgment_chat_live"
)
FRAGMENT_ANALYSIS_SUBMISSION_AUTHORITY_SCHEMA = (
    "fin_ia_s3_fixed_pack_fragment_analysis_submission_live_authority_v1_0"
)
FRAGMENT_ANALYSIS_SUBMISSION_AUTHORITY_STATUS = (
    "signed_exact_once_fixed_pack_single_thesis_analysis_submission_chat_live"
)
FRAGMENT_ANALYSIS_SUBMISSION_RESULT_SCHEMA = (
    "fin_ia_s3_fixed_pack_fragment_analysis_submission_live_result_v1_0"
)
FULL_FRAGMENT_JUDGMENT_AUTHORITY_SCHEMA = (
    "fin_ia_s3_fixed_pack_full_fragment_judgment_live_authority_v1_2"
)
FULL_FRAGMENT_CLAIM_LOCAL_AUTHORITY_SCHEMA = (
    "fin_ia_s3_fixed_pack_full_fragment_judgment_live_authority_v1_3"
)
FULL_FRAGMENT_CAUSAL_POLARITY_AUTHORITY_SCHEMA = (
    "fin_ia_s3_fixed_pack_full_fragment_judgment_live_authority_v1_4"
)
FULL_FRAGMENT_WWC_ROUTE_IDENTIFIER_AUTHORITY_SCHEMA = (
    "fin_ia_s3_fixed_pack_full_fragment_judgment_live_authority_v1_5"
)
FULL_FRAGMENT_JUDGMENT_AUTHORITY_STATUS = (
    "signed_exact_once_fixed_pack_full_three_fragment_analysis_submission_chat_live"
)
FULL_FRAGMENT_JUDGMENT_RESULT_SCHEMA = (
    "fin_ia_s3_fixed_pack_full_fragment_judgment_live_result_v1_0"
)
FRAGMENT_SUBMISSION_SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_fixed_pack_failed_fragment_submission_successor_"
    "live_authority_v1_0"
)
FRAGMENT_SUBMISSION_SUCCESSOR_AUTHORITY_STATUS = (
    "signed_exact_once_failed_counter_submission_successor_chat_live"
)
FRAGMENT_SUBMISSION_SUCCESSOR_RESULT_SCHEMA = (
    "fin_ia_s3_fixed_pack_failed_fragment_submission_successor_"
    "live_result_v1_0"
)
FRAGMENT_VALIDATION_REPAIR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_fixed_pack_failed_fragment_validation_repair_"
    "live_authority_v1_0"
)
FRAGMENT_VALIDATION_REPAIR_AUTHORITY_STATUS = (
    "signed_exact_once_failed_counter_validation_repair_chat_live"
)
FRAGMENT_VALIDATION_REPAIR_RESULT_SCHEMA = (
    "fin_ia_s3_fixed_pack_failed_fragment_validation_repair_live_result_v1_0"
)


class CurrentResearchConsumerCanaryError(RuntimeError):
    """The natural synthesis canary was not exactly authorized."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _resolve(ref: str) -> Path:
    relative = PurePosixPath(str(ref or ""))
    if relative.is_absolute() or "\\" in str(ref) or ".." in relative.parts:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_path_invalid"
        )
    path = ROOT.joinpath(*relative.parts).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_path_escape"
        ) from exc
    return path


def _relative(path: str | Path) -> str:
    return Path(path).resolve().relative_to(ROOT).as_posix()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CurrentResearchConsumerCanaryError(
            f"research_consumer_canary_json_object_required:{path.name}"
        )
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    except FileExistsError as exc:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_exact_once_output_exists"
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
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_git_boundary_unavailable"
        )
    return completed.stdout.strip()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def validate_authority(
    payload: Mapping[str, Any],
    *,
    authority_path: Path,
) -> dict[str, Path]:
    if not (
        payload.get("schema_version") == AUTHORITY_SCHEMA
        and payload.get("status") == "signed_exact_once_research_synthesis_authority"
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_authority_status_invalid"
        )
    case_key = str(payload.get("case_key") or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9.-]{1,16}", case_key):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_case_key_invalid"
        )
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_implementation_commit_invalid"
        )
    if _git("rev-parse", "HEAD").lower() != commit:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_implementation_head_drift"
        )
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_implementation_upstream_drift"
        )
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    allowed = f"?? {_relative(authority_path)}"
    if [line for line in status.splitlines() if line] != [allowed]:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_worktree_not_clean"
        )
    budget = payload.get("budget")
    if not (
        isinstance(budget, Mapping)
        and dict(budget)
        == {
            "model_calls": 1,
            "transport_attempts": 1,
            "retries": 0,
            "fallbacks": 0,
            "external_retrieval_calls": 0,
            "planner_calls": 0,
            "current_product_pointer_mutations": 0,
        }
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_budget_invalid"
        )
    bound = payload.get("bound_inputs")
    output = payload.get("output_contract")
    if not isinstance(bound, Mapping) or not isinstance(output, Mapping):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_authority_shape_invalid"
        )
    pairs = (
        ("consumer_policy_ref", "consumer_policy_sha256"),
        ("objective_ref", "objective_sha256"),
        ("planner_atoms_ref", "planner_atoms_sha256"),
        ("current_evidence_pack_result_ref", "current_evidence_pack_result_sha256"),
        ("runtime_registry_ref", "runtime_registry_sha256"),
        ("clean_zero_call_result_ref", "clean_zero_call_result_sha256"),
        ("provider_profile_ref", "provider_profile_sha256"),
        ("runner_ref", "runner_sha256"),
    )
    paths: dict[str, Path] = {}
    for ref_key, digest_key in pairs:
        path = _resolve(str(bound.get(ref_key) or ""))
        if not path.is_file() or _sha(path) != str(bound.get(digest_key) or ""):
            raise CurrentResearchConsumerCanaryError(
                f"research_consumer_canary_bound_input_drift:{ref_key}"
            )
        paths[ref_key] = path
    expected_message_digest = str(
        bound.get("model_visible_messages_sha256") or ""
    )
    if not re.fullmatch(r"[0-9a-f]{64}", expected_message_digest):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_message_digest_invalid"
        )
    required_output = {
        "capture_root_ref",
        "private_output_root_ref",
        "public_result_ref",
        "result_id",
        "run_id",
        "attempt_id",
        "product_publication",
    }
    if not (
        set(output) == required_output
        and output.get("product_publication") == "forbidden"
        and str(output.get("result_id") or "")
        and str(output.get("run_id") or "")
        and str(output.get("attempt_id") or "")
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_output_contract_invalid"
        )
    capture_dir = (
        _resolve(str(output["capture_root_ref"]))
        / str(output["run_id"])
        / str(output["attempt_id"])
    )
    if (
        capture_dir.exists()
        or _resolve(str(output["private_output_root_ref"])).exists()
        or _resolve(str(output["public_result_ref"])).exists()
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_exact_once_identity_consumed"
        )
    return paths


def _services(
    *,
    evidence_projection_version: str = "current",
    evidence_result_path: Path | None = None,
) -> tuple[ResearchEvidencePackService, ResearchRetrievalService]:
    runtime_paths = resolve_runtime_paths(ROOT)
    evidence_config = read_registered_runtime_json(
        ROOT, "application.config.current_research_evidence_pack_projection"
    )
    reviewed_anchor_catalog: Mapping[str, Any] | None
    if evidence_projection_version == "current":
        if evidence_result_path is None:
            evidence_result = read_registered_runtime_json(
                ROOT, str(evidence_config["source_result_resource_id"])
            )
            reviewed_anchor_catalog = read_registered_runtime_json(
                ROOT,
                str(evidence_config["reviewed_anchor_catalog_resource_id"]),
            )
        else:
            evidence_result = _json(evidence_result_path)
            reviewed_anchor_catalog = _json(PRE_VS4_REVIEWED_ANCHOR_CATALOG)
    elif evidence_projection_version == "legacy_v1_0":
        if (
            evidence_config.get("schema_version")
            != "fin_ia_current_research_evidence_pack_projection_config_v1_1"
        ):
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_legacy_projection_source_invalid"
            )
        evidence_config = dict(evidence_config)
        evidence_config["schema_version"] = (
            "fin_ia_current_research_evidence_pack_projection_config_v1_0"
        )
        evidence_config.pop("reviewed_anchor_catalog_resource_id", None)
        reviewed_anchor_catalog = None
        evidence_result = _json(
            evidence_result_path or PRE_VS4_EVIDENCE_PACK_RESULT
        )
    else:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_evidence_projection_version_invalid"
        )
    evidence = ResearchEvidencePackService(
        config=evidence_config,
        result=evidence_result,
        private_object_root=(
            runtime_paths.reviewed_evidence_root
            / str(evidence_config["private_object_root_relative"])
        ),
        private_root_base=runtime_paths.reviewed_evidence_root,
        reviewed_anchor_catalog=reviewed_anchor_catalog,
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


def _compile_runtime_input(
    paths: Mapping[str, Path],
    *,
    case_key: str,
    required_cell_ids: Sequence[str] | None = None,
    submission_transport: str = "json",
) -> tuple[dict[str, Any], dict[str, Any], tuple[dict[str, str], ...]]:
    read = frozenset({"current_product:read"})
    objective = _json(paths["objective_ref"])
    if str(objective.get("case_key") or "").strip().upper() != case_key:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_objective_case_drift"
        )
    claim_policy = (
        _json(paths["claim_authority_policy_ref"])
        if "claim_authority_policy_ref" in paths
        else None
    )
    required_base_digest = str(
        ((claim_policy or {}).get("qualified_scope") or {}).get(
            "base_research_input_digest"
        )
        or ""
    )

    def compile_base(
        evidence_projection_version: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        evidence_service, retrieval_service = _services(
            evidence_projection_version=evidence_projection_version,
            evidence_result_path=paths.get("current_evidence_pack_result_ref"),
        )
        evidence_pack = evidence_service.get_case(
            case_key, ResearchEvidencePackPrincipal("current", read)
        )
        controlled = retrieval_service.execute_controlled_plan(
            case_key,
            objective,
            _json(paths["planner_atoms_ref"]),
            ResearchRetrievalPrincipal("current", read),
        )
        research_input = compile_current_research_input(
            policy=_json(paths["consumer_policy_ref"]),
            evidence_pack=evidence_pack,
            controlled_plan=controlled,
        )
        return evidence_pack, research_input

    evidence_pack, research_input = compile_base("current")
    if (
        required_base_digest
        and research_input.get("research_input_digest") != required_base_digest
    ):
        legacy_evidence_pack, legacy_research_input = compile_base("legacy_v1_0")
        if (
            legacy_research_input.get("research_input_digest")
            == required_base_digest
        ):
            evidence_pack = legacy_evidence_pack
            research_input = legacy_research_input
    if "claim_authority_policy_ref" in paths:
        research_input = compile_claim_authority_research_input(
            research_input,
            policy=claim_policy or {},
        )
    if "claim_surface_authority_policy_ref" in paths:
        if "claim_authority_policy_ref" not in paths:
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_claim_surface_base_authority_missing"
            )
        research_input = compile_claim_surface_authority_research_input(
            research_input,
            policy=_json(paths["claim_surface_authority_policy_ref"]),
        )
    return (
        evidence_pack,
        research_input,
        compile_current_research_messages(
            research_input,
            required_cell_ids=required_cell_ids,
            submission_transport=submission_transport,
        ),
    )


def _terminal_summary(
    *,
    authority: Mapping[str, Any],
    authority_path: Path,
    research_input: Mapping[str, Any],
    provider_result: ChatCompletionResult | None,
    status: str,
    failure_phase: str,
    failure_code: str,
    model_call_attempted: bool,
    transport_attempted: bool,
    provider_identity: Mapping[str, Any] | None = None,
    request_capture_ref: str = "",
    response_capture_ref: str = "",
    full_result_ref: str = "",
    full_result_sha256: str = "",
    deliverable_digest: str = "",
) -> dict[str, Any]:
    output = authority["output_contract"]
    provider = provider_result.as_dict() if provider_result is not None else {}
    identity = provider_identity or {}
    summary_body = {
        "schema_version": RESULT_SCHEMA,
        "status": status,
        "recorded_at": _now(),
        "result_id": str(output["result_id"]),
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": str(authority["implementation_commit"]),
        "bindings": {
            "case_key": research_input["case_identity"]["case_key"],
            "research_as_of": research_input["case_identity"]["research_as_of"],
            "research_input_digest": research_input["research_input_digest"],
            "evidence_pack_artifact_digest": research_input[
                "evidence_pack_binding"
            ]["artifact_digest"],
            "evidence_pack_payload_digest": research_input[
                "evidence_pack_binding"
            ]["pack_payload_digest"],
            "deliverable_digest": deliverable_digest,
        },
        "provider": {
            "provider_id": provider.get(
                "provider_id", identity.get("provider_id", "")
            ),
            "model": provider.get("model", identity.get("model", "")),
            "finish_reason": provider.get("finish_reason", ""),
            "usage": provider.get("usage", {}),
            "request_capture_ref": (
                _relative(provider["request_capture_ref"])
                if provider.get("request_capture_ref")
                else request_capture_ref
            ),
            "response_capture_ref": (
                _relative(provider["response_capture_ref"])
                if provider.get("response_capture_ref")
                else response_capture_ref
            ),
            "request_digest": provider.get("request_digest", ""),
            "response_digest": provider.get("response_digest", ""),
            "private_reasoning_fields_redacted": provider.get(
                "private_reasoning_fields_redacted", 0
            ),
        },
        "terminal": {
            "failure_phase": failure_phase,
            "failure_code": failure_code,
            "model_calls": int(model_call_attempted),
            "transport_attempts": int(transport_attempted),
            "retries": 0,
            "fallbacks": 0,
            "external_retrieval_calls": 0,
            "planner_calls": 0,
            "product_publication": False,
        },
        "full_result_ref": full_result_ref,
        "full_result_sha256": full_result_sha256,
        "acceptance": {
            "deterministic_contract_pass": status == "completed_contract_valid",
            "natural_research_quality_proven": False,
            "qualified_human_acceptance": False,
            "s3_product_acceptance": False,
            "workbench_publication": False,
            "release_ready": False,
        },
        "known_boundary": str(authority["known_boundary"]),
    }
    return {**summary_body, "result_digest": canonical_digest(summary_body)}


def run(
    authority_path: Path,
    *,
    executor: Callable[..., ChatCompletionResult] = execute_chat_completion_exact_once,
) -> dict[str, Any]:
    authority = _json(authority_path)
    paths = validate_authority(authority, authority_path=authority_path)
    case_key = str(authority["case_key"]).strip().upper()
    _, research_input, messages = _compile_runtime_input(
        paths,
        case_key=case_key,
    )
    clean_zero = _json(paths["clean_zero_call_result_ref"])
    if not (
        clean_zero.get("status")
        == "engineering_pass_zero_call_current_consumer_contract_successor"
        and clean_zero.get("bindings", {}).get("research_input_digest")
        == research_input["research_input_digest"]
        and clean_zero.get("bindings", {}).get("evidence_pack_artifact_digest")
        == research_input["evidence_pack_binding"]["artifact_digest"]
        and clean_zero.get("bindings", {}).get("evidence_pack_payload_digest")
        == research_input["evidence_pack_binding"]["pack_payload_digest"]
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_clean_zero_binding_drift"
        )
    message_digest = canonical_digest(list(messages))
    if message_digest != authority["bound_inputs"][
        "model_visible_messages_sha256"
    ]:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_canary_model_message_drift"
        )
    output = authority["output_contract"]
    provider_result: ChatCompletionResult | None = None
    provider_identity: dict[str, str] = {}
    model_call_attempted = False
    transport_attempted = False
    request_capture_ref = ""
    response_capture_ref = ""
    try:
        profile = load_chat_completion_profile(
            _json(paths["provider_profile_ref"])
        )
        provider_identity = {
            "provider_id": profile.provider_id,
            "model": profile.model,
        }
        model_call_attempted = True
        transport_attempted = True
        provider_result = executor(
            profile=profile,
            messages=messages,
            capture_root=_resolve(str(output["capture_root_ref"])),
            run_id=str(output["run_id"]),
            attempt_id=str(output["attempt_id"]),
        )
        if provider_result.finish_reason != "stop":
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_canary_finish_reason_invalid"
            )
        judgment = parse_current_research_output(provider_result.content)
        deliverable = compile_current_research_deliverable(
            research_input=research_input,
            judgment_output=judgment,
        )
        full_body = {
            "schema_version": FULL_SCHEMA,
            "status": "completed_contract_valid",
            "authority_ref": _relative(authority_path),
            "authority_sha256": _sha(authority_path),
            "research_input": research_input,
            "model_visible_messages_sha256": message_digest,
            "provider_result": provider_result.as_dict(),
            "judgment_output": judgment,
            "structured_deliverable": deliverable,
            "product_publication": False,
        }
        full_digest = canonical_digest(full_body)
        private_root = _resolve(str(output["private_output_root_ref"]))
        full_path = private_root / f"full_result_{full_digest}.json"
        _write_new(full_path, {**full_body, "result_digest": full_digest})
        summary = _terminal_summary(
            authority=authority,
            authority_path=authority_path,
            research_input=research_input,
            provider_result=provider_result,
            status="completed_contract_valid",
            failure_phase="",
            failure_code="",
            model_call_attempted=model_call_attempted,
            transport_attempted=transport_attempted,
            provider_identity=provider_identity,
            full_result_ref=_relative(full_path),
            full_result_sha256=_sha(full_path),
            deliverable_digest=str(deliverable["deliverable_digest"]),
        )
    except (ModelGatewayError, CurrentResearchConsumerError, CurrentResearchConsumerCanaryError) as exc:
        if isinstance(exc, ModelGatewayError):
            phase = "provider_transport_or_response"
            code = exc.code
            response_capture_ref = (
                _relative(exc.capture_ref) if exc.capture_ref else ""
            )
            if exc.capture_ref:
                request_path = Path(exc.capture_ref).with_name(
                    "model_visible_request.json"
                )
                if request_path.is_file():
                    request_capture_ref = _relative(request_path)
        elif isinstance(exc, CurrentResearchConsumerError):
            phase = "research_output_parse_or_contract"
            code = exc.code
        else:
            phase = "post_provider_terminal_validation"
            code = exc.code
        summary = _terminal_summary(
            authority=authority,
            authority_path=authority_path,
            research_input=research_input,
            provider_result=provider_result,
            status="terminal_failed_no_retry",
            failure_phase=phase,
            failure_code=code,
            model_call_attempted=model_call_attempted,
            transport_attempted=transport_attempted,
            provider_identity=provider_identity,
            request_capture_ref=request_capture_ref,
            response_capture_ref=response_capture_ref,
        )
    _write_new(_resolve(str(output["public_result_ref"])), summary)
    return summary


def validate_paired_authority(
    payload: Mapping[str, Any],
    *,
    authority_path: Path,
) -> dict[str, Path]:
    if not (
        payload.get("schema_version") == PAIRED_AUTHORITY_SCHEMA
        and payload.get("status")
        == "signed_exact_once_deepseek_ga_single_cell_paired_canary"
        and payload.get("case_key") == "DELL"
        and payload.get("cell_id") == "CELL::value_capture"
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_authority_invalid"
        )
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_commit_invalid"
        )
    if _git("rev-parse", "HEAD").lower() != commit:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_head_drift"
        )
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_upstream_drift"
        )
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    allowed = f"?? {_relative(authority_path)}"
    if [line for line in status.splitlines() if line] != [allowed]:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_worktree_not_clean"
        )
    budget = payload.get("execution_budget")
    if not (
        isinstance(budget, Mapping)
        and dict(budget)
        == {
            "maximum_model_calls": 2,
            "maximum_transport_attempts": 2,
            "maximum_calls_per_lane": 1,
            "retries": 0,
            "fallbacks": 0,
            "planner_calls": 0,
            "external_retrieval_calls": 0,
            "tool_executions": 0,
            "current_product_pointer_mutations": 0,
        }
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_budget_invalid"
        )
    bound = payload.get("bound_inputs")
    output = payload.get("output_contract")
    if not isinstance(bound, Mapping) or not isinstance(output, Mapping):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_shape_invalid"
        )
    required_ref_keys = {
        "consumer_policy_ref",
        "objective_ref",
        "planner_atoms_ref",
        "current_evidence_pack_result_ref",
        "runtime_registry_ref",
        "clean_zero_call_result_ref",
        "json_profile_ref",
        "strict_profile_ref",
        "runner_ref",
        "paired_submission_ref",
    }
    ref_keys = [key for key in bound if key.endswith("_ref")]
    digest_keys = {
        "research_input_digest",
        "json_messages_digest",
        "strict_messages_digest",
        "business_payload_digest",
        "strict_tool_schema_digest",
    }
    expected = {
        value
        for key in ref_keys
        for value in (key, key[:-4] + "_sha256")
    } | digest_keys
    if set(ref_keys) != required_ref_keys or set(bound) != expected:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_bindings_invalid"
        )
    paths: dict[str, Path] = {}
    for key in ref_keys:
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(
            bound.get(key[:-4] + "_sha256") or ""
        ):
            raise CurrentResearchConsumerCanaryError(
                f"research_consumer_paired_bound_input_drift:{key}"
            )
        paths[key] = path
    required_output = {
        "capture_root_ref",
        "private_output_root_ref",
        "public_result_ref",
        "run_id",
        "json_attempt_id",
        "strict_attempt_id",
        "product_publication",
    }
    if not (
        set(output) == required_output
        and output.get("product_publication") == "forbidden"
        and all(
            str(output.get(key) or "")
            for key in required_output - {"product_publication"}
        )
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_output_invalid"
        )
    capture_run = (
        _resolve(str(output["capture_root_ref"])) / str(output["run_id"])
    )
    if (
        capture_run.exists()
        or _resolve(str(output["private_output_root_ref"])).exists()
        or _resolve(str(output["public_result_ref"])).exists()
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_identity_consumed"
        )
    return paths


def _compile_paired_inputs(
    paths: Mapping[str, Path],
    *,
    case_key: str,
    cell_id: str,
) -> tuple[
    dict[str, Any],
    tuple[dict[str, str], ...],
    tuple[dict[str, str], ...],
    dict[str, Any],
    str,
]:
    _, research_input, _ = _compile_runtime_input(
        paths,
        case_key=case_key,
        required_cell_ids=[cell_id],
        submission_transport="json",
    )
    kernel_payload = read_registered_runtime_json(
        ROOT, "application.config.current_financial_research_kernel"
    )
    kernel = load_financial_research_kernel(kernel_payload)
    route = load_query_object_fact_route_policy(
        read_registered_runtime_json(
            ROOT, "application.config.current_query_object_fact_route_policy"
        ),
        kernel,
    )
    paired = compile_paired_research_submission(
        research_input=research_input,
        kernel=kernel,
        route_policy=route,
        cell_id=cell_id,
    )
    return (
        research_input,
        paired.json_messages,
        paired.strict_messages,
        dict(paired.strict_tool),
        paired.business_payload_digest,
    )


def _paired_lane_public(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value[key]
        for key in (
            "lane",
            "status",
            "failure_phase",
            "failure_code",
            "provider",
            "deliverable_digest",
            "failure_request_capture_ref",
            "failure_response_capture_ref",
        )
    }


def run_paired(
    authority_path: Path,
    *,
    json_executor: Callable[..., ChatCompletionResult] = (
        execute_chat_completion_exact_once
    ),
    strict_executor: Callable[..., ChatCompletionToolStepResult] = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> dict[str, Any]:
    authority = _json(authority_path)
    paths = validate_paired_authority(
        authority, authority_path=authority_path
    )
    cell_id = str(authority["cell_id"])
    (
        research_input,
        json_messages,
        strict_messages,
        strict_tool,
        business_payload_digest,
    ) = _compile_paired_inputs(
        paths,
        case_key=str(authority["case_key"]),
        cell_id=cell_id,
    )
    actual = {
        "research_input_digest": research_input["research_input_digest"],
        "json_messages_digest": canonical_digest(list(json_messages)),
        "strict_messages_digest": canonical_digest(list(strict_messages)),
        "business_payload_digest": business_payload_digest,
        "strict_tool_schema_digest": canonical_digest(strict_tool),
    }
    bound = authority["bound_inputs"]
    if any(str(bound[key]) != str(value) for key, value in actual.items()):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_runtime_binding_drift"
        )
    clean = _json(paths["clean_zero_call_result_ref"])
    if not (
        clean.get("status")
        == "zero_call_engineering_and_fresh_process_proof_pass"
        and clean.get("normalized_proof", {}).get("research_input_digest")
        == research_input["research_input_digest"]
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_paired_clean_proof_drift"
        )
    json_profile = load_chat_completion_profile(
        _json(paths["json_profile_ref"])
    )
    strict_profile = load_chat_completion_profile(
        _json(paths["strict_profile_ref"])
    )
    validate_deepseek_ga_json_profile(json_profile)
    validate_deepseek_ga_profile(strict_profile, strict_tools=True)
    output = authority["output_contract"]
    private_root = _resolve(str(output["private_output_root_ref"]))
    paired_submission = PairedResearchSubmission(
        json_messages=json_messages,
        strict_messages=strict_messages,
        strict_tool=strict_tool,
        business_payload_digest=business_payload_digest,
    )
    full_core = run_paired_research_submission(
        research_input=research_input,
        submission=paired_submission,
        json_profile=json_profile,
        strict_profile=strict_profile,
        capture_root=_resolve(str(output["capture_root_ref"])),
        run_id=str(output["run_id"]),
        json_attempt_id=str(output["json_attempt_id"]),
        strict_attempt_id=str(output["strict_attempt_id"]),
        cell_id=cell_id,
        capture_ref_formatter=_relative,
        lane_recorder=lambda lane, value: _write_new(
            private_root / f"{lane}.json", value
        ),
        json_executor=json_executor,
        strict_executor=strict_executor,
    )
    full_body = {
        "schema_version": PAIRED_FULL_SCHEMA,
        "recorded_at": _now(),
        "research_input_digest": research_input["research_input_digest"],
        "business_payload_digest": business_payload_digest,
        **full_core,
    }
    full = {
        **full_body,
        "full_result_digest": canonical_digest(full_body),
    }
    _write_new(private_root / "full_result.json", full)
    json_lane = full["json_lane"]
    strict_lane = full["strict_lane"]
    both = (
        json_lane["status"] == "contract_valid"
        and strict_lane["status"] == "contract_valid"
    )
    body = {
        "schema_version": PAIRED_RESULT_SCHEMA,
        "status": (
            "paired_contract_valid_content_assessment_pending"
            if both
            else "paired_terminal_mixed_or_failed_no_retry"
        ),
        "recorded_at": _now(),
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": authority["case_key"],
        "cell_id": cell_id,
        "research_input_digest": research_input["research_input_digest"],
        "business_payload_digest": business_payload_digest,
        "same_business_payload": True,
        "json_lane": _paired_lane_public(json_lane),
        "strict_lane": _paired_lane_public(strict_lane),
        "execution": {
            "model_calls": 1 + int(not full["strict_skipped"]),
            "transport_attempts": 1 + int(not full["strict_skipped"]),
            "retries": 0,
            "fallbacks": 0,
            "planner_calls": 0,
            "external_retrieval_calls": 0,
            "tool_executions": 0,
            "tool_choice_sent": False,
            "product_publication": False,
        },
        "full_result_ref": _relative(private_root / "full_result.json"),
        "full_result_sha256": _sha(private_root / "full_result.json"),
        "acceptance": {
            "json_transport_and_contract_pass": (
                json_lane["status"] == "contract_valid"
            ),
            "strict_beta_transport_and_contract_pass": (
                strict_lane["status"] == "contract_valid"
            ),
            "paired_content_assessment_pending": both,
            "five_cell_live_authorized": False,
            "s3_product_acceptance": False,
            "qualified_human_acceptance": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    summary = {**body, "result_digest": canonical_digest(body)}
    _write_new(_resolve(str(output["public_result_ref"])), summary)
    return summary


def validate_tool_loop_authority(
    payload: Mapping[str, Any],
    *,
    authority_path: Path,
) -> dict[str, Path]:
    micro_mode = (
        payload.get("schema_version") == MICRO_TOOL_LOOP_AUTHORITY_SCHEMA
    )
    standard_mode = (
        payload.get("schema_version") == TOOL_LOOP_AUTHORITY_SCHEMA
    )
    if not (
        (
            standard_mode
            and payload.get("status")
            == "signed_exact_once_standard_API_bounded_finance_loop_live"
        )
        or (
            micro_mode
            and payload.get("status") == MICRO_TOOL_LOOP_AUTHORITY_STATUS
        )
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_authority_invalid"
        )
    case_key = str(payload.get("case_key") or "").strip().upper()
    cell_ids = payload.get("required_cell_ids")
    if not (
        re.fullmatch(r"[A-Z0-9.-]{1,16}", case_key)
        and isinstance(cell_ids, list)
        and len(cell_ids) in {1, 5}
        and len(cell_ids) == len(set(cell_ids))
        and all(str(value).startswith("CELL::") for value in cell_ids)
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_scope_invalid"
        )
    if len(cell_ids) == 1 and not (
        case_key == "DELL" and cell_ids == ["CELL::value_capture"]
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_single_cell_scope_invalid"
        )
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_commit_invalid"
        )
    if _git("rev-parse", "HEAD").lower() != commit:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_head_drift"
        )
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_upstream_drift"
        )
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    allowed = f"?? {_relative(authority_path)}"
    if [line for line in status.splitlines() if line] != [allowed]:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_worktree_not_clean"
        )
    bound_input_keys = payload.get("bound_inputs", {})
    claim_authority_mode = "claim_authority_policy_ref" in bound_input_keys
    claim_surface_authority_mode = (
        "claim_surface_authority_policy_ref" in bound_input_keys
    )
    if claim_surface_authority_mode and not claim_authority_mode:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_claim_surface_base_missing"
        )
    if micro_mode and not (
        case_key == "DELL"
        and cell_ids == ["CELL::value_capture"]
        and claim_authority_mode
        and claim_surface_authority_mode
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_micro_tool_loop_scope_invalid"
        )
    maximum_requests = (
        0
        if micro_mode or claim_authority_mode
        else (3 if len(cell_ids) == 1 else 9)
    )
    maximum_steps = (
        4 if micro_mode else len(cell_ids) * 3 + maximum_requests
    )
    expected_budget = {
        "maximum_model_calls": maximum_steps,
        "maximum_transport_attempts": maximum_steps,
        "maximum_evidence_requests": maximum_requests,
        "retries": 0,
        "fallbacks": 0,
        "planner_calls": 0,
        "external_retrieval_calls": 0,
        "embedding_calls": 0,
        "current_product_pointer_mutations": 0,
    }
    if micro_mode:
        expected_budget["maximum_tool_calls"] = 5
    budget = payload.get("execution_budget")
    if not (
        isinstance(budget, Mapping)
        and dict(budget) == expected_budget
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_budget_invalid"
        )
    bound = payload.get("bound_inputs")
    output = payload.get("output_contract")
    if not isinstance(bound, Mapping) or not isinstance(output, Mapping):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_shape_invalid"
        )
    common_required_refs = {
        "consumer_policy_ref",
        "objective_ref",
        "planner_atoms_ref",
        "current_evidence_pack_result_ref",
        "runtime_registry_ref",
        "clean_zero_call_result_ref",
        "loop_policy_ref",
        "runner_ref",
        "loop_implementation_ref",
        "provider_transport_ref",
        "prior_scope_decision_ref",
    }
    required_refs = set(common_required_refs)
    if micro_mode:
        required_refs.update(
            {
                "micro_policy_ref",
                "micro_read_profile_ref",
                "micro_judgment_profile_ref",
                "micro_zero_call_authority_ref",
                "prior_live_result_ref",
                "prior_capacity_assessment_ref",
            }
        )
    else:
        required_refs.add("provider_profile_ref")
    if claim_authority_mode:
        required_refs.add("claim_authority_policy_ref")
    if claim_surface_authority_mode:
        required_refs.add("claim_surface_authority_policy_ref")
    ref_keys = {key for key in bound if key.endswith("_ref")}
    runtime_digest_keys = {
        "research_input_digest",
        "finance_loop_messages_digest",
        (
            "micro_tool_schema_digest"
            if micro_mode
            else "standard_tool_schema_digest"
        ),
    }
    expected = {
        value
        for key in ref_keys
        for value in (key, key[:-4] + "_sha256")
    } | runtime_digest_keys
    if ref_keys != required_refs or set(bound) != expected:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_bindings_invalid"
        )
    paths: dict[str, Path] = {}
    for key in ref_keys:
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(
            bound.get(key[:-4] + "_sha256") or ""
        ):
            raise CurrentResearchConsumerCanaryError(
                f"research_consumer_tool_loop_bound_input_drift:{key}"
            )
        paths[key] = path
    required_output = {
        "capture_root_ref",
        "private_output_root_ref",
        "public_result_ref",
        "run_id",
        "step_attempt_prefix",
        "product_publication",
    }
    if not (
        set(output) == required_output
        and output.get("product_publication") == "forbidden"
        and all(
            str(output.get(key) or "")
            for key in required_output - {"product_publication"}
        )
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_output_invalid"
        )
    capture_run = (
        _resolve(str(output["capture_root_ref"])) / str(output["run_id"])
    )
    if (
        capture_run.exists()
        or _resolve(str(output["private_output_root_ref"])).exists()
        or _resolve(str(output["public_result_ref"])).exists()
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_identity_consumed"
        )
    return paths


def _fragment_analysis_submission_artifacts(paths: Mapping[str, Path]):
    _, research_input, _ = _compile_runtime_input(
        paths,
        case_key="DELL",
        required_cell_ids=["CELL::value_capture"],
    )
    context = compile_finance_micro_fragment_context(
        research_input=research_input,
        cell_id="CELL::value_capture",
        tool_name=SUBMIT_RESEARCH_THESIS_TOOL,
    )
    analysis_messages = compile_finance_micro_fragment_analysis_messages(context)
    kernel, route, _ = _tool_loop_contracts(paths)
    base_policy = load_bounded_finance_loop_policy(_json(paths["loop_policy_ref"]))
    scoped_policy = scope_bounded_finance_micro_judgment_policy(
        base_policy,
        micro_policy=load_fixed_pack_micro_judgment_policy(
            _json(paths["micro_policy_ref"])
        ),
        cell_count=1,
        maximum_evidence_requests=0,
    )
    thesis_tool = next(
        row
        for row in compile_finance_micro_judgment_tools(
            research_input=research_input,
            required_cell_ids=["CELL::value_capture"],
            kernel=kernel,
            route_policy=route,
            policy=scoped_policy,
            strict=False,
        )
        if row["function"]["name"] == SUBMIT_RESEARCH_THESIS_TOOL
    )
    return research_input, context, analysis_messages, thesis_tool


def validate_fragment_analysis_submission_authority(
    payload: Mapping[str, Any],
    *,
    authority_path: Path,
) -> dict[str, Path]:
    if not (
        payload.get("schema_version")
        == FRAGMENT_ANALYSIS_SUBMISSION_AUTHORITY_SCHEMA
        and payload.get("status")
        == FRAGMENT_ANALYSIS_SUBMISSION_AUTHORITY_STATUS
        and payload.get("case_key") == "DELL"
        and payload.get("cell_id") == "CELL::value_capture"
        and payload.get("fragment_tool") == SUBMIT_RESEARCH_THESIS_TOOL
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_fragment_authority_invalid"
        )
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_fragment_commit_invalid"
        )
    if _git("rev-parse", "HEAD").lower() != commit:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_fragment_head_drift"
        )
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_fragment_upstream_drift"
        )
    allowed = f"?? {_relative(authority_path)}"
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    if [line for line in status.splitlines() if line] != [allowed]:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_fragment_worktree_not_clean"
        )
    expected_budget = {
        "maximum_model_calls": 2,
        "maximum_transport_attempts": 2,
        "maximum_tool_calls": 1,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
        "planner_calls": 0,
        "external_retrieval_calls": 0,
        "embedding_calls": 0,
        "protocol_switches": 0,
        "current_product_pointer_mutations": 0,
    }
    if payload.get("execution_budget") != expected_budget:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_fragment_budget_invalid"
        )
    bound = payload.get("bound_inputs")
    output = payload.get("output_contract")
    if not isinstance(bound, Mapping) or not isinstance(output, Mapping):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_fragment_shape_invalid"
        )
    required_refs = {
        "consumer_policy_ref",
        "objective_ref",
        "planner_atoms_ref",
        "current_evidence_pack_result_ref",
        "runtime_registry_ref",
        "claim_authority_policy_ref",
        "claim_surface_authority_policy_ref",
        "loop_policy_ref",
        "micro_policy_ref",
        "analysis_profile_ref",
        "submission_profile_ref",
        "runner_ref",
        "loop_implementation_ref",
        "provider_transport_ref",
        "zero_call_result_ref",
        "prior_live_result_ref",
        "prior_capacity_assessment_ref",
        "disposition_decision_ref",
    }
    ref_keys = {key for key in bound if key.endswith("_ref")}
    digest_keys = {
        "research_input_digest",
        "fragment_context_digest",
        "analysis_messages_digest",
        "submission_tool_schema_digest",
    }
    expected_keys = {
        value
        for key in ref_keys
        for value in (key, key[:-4] + "_sha256")
    } | digest_keys
    if ref_keys != required_refs or set(bound) != expected_keys:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_fragment_bindings_invalid"
        )
    paths: dict[str, Path] = {}
    for key in ref_keys:
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(
            bound.get(key[:-4] + "_sha256") or ""
        ):
            raise CurrentResearchConsumerCanaryError(
                f"research_consumer_fragment_bound_input_drift:{key}"
            )
        paths[key] = path
    zero_call = _json(paths["zero_call_result_ref"])
    prior_live = _json(paths["prior_live_result_ref"])
    disposition = _json(paths["disposition_decision_ref"])
    if not (
        zero_call.get("status")
        == "zero_call_fragment_projection_analysis_submission_pass"
        and zero_call.get("model_calls") == 0
        and zero_call.get("network_calls") == 0
        and zero_call.get("projection_selects_answer") is False
        and zero_call.get("all_legal_relation_options_preserved") is True
        and zero_call.get("cross_case_mutation_fail_closed") is True
        and zero_call.get("missing_authority_mutation_fail_closed") is True
        and zero_call.get("analysis_draft_business_promotion") is False
        and prior_live.get("status") == "terminal_failed_no_retry"
        and prior_live.get("failure_code")
        == "model_gateway_reasoning_budget_exhausted"
        and disposition.get("status")
        == "approved_fragment_projection_and_analysis_submission_test_only"
        and disposition.get("live_scope") == "one_DELL_value_capture_thesis"
        and disposition.get("protocol_switch_authorized") is False
        and disposition.get("dynamic_agentic_research_authorized") is False
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_fragment_disposition_invalid"
        )
    research_input, context, analysis_messages, thesis_tool = (
        _fragment_analysis_submission_artifacts(paths)
    )
    if not (
        bound["research_input_digest"] == research_input["research_input_digest"]
        and bound["fragment_context_digest"] == context["projection_digest"]
        and bound["analysis_messages_digest"]
        == canonical_digest(list(analysis_messages))
        and bound["submission_tool_schema_digest"]
        == canonical_digest(thesis_tool)
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_fragment_runtime_digest_drift"
        )
    required_output = {
        "capture_root_ref",
        "private_output_root_ref",
        "public_result_ref",
        "run_id",
        "analysis_attempt_id",
        "submission_attempt_id",
        "product_publication",
    }
    if not (
        set(output) == required_output
        and output.get("product_publication") == "forbidden"
        and all(
            str(output.get(key) or "")
            for key in required_output - {"product_publication"}
        )
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_fragment_output_invalid"
        )
    capture_run = _resolve(str(output["capture_root_ref"])) / str(
        output["run_id"]
    )
    if (
        capture_run.exists()
        or _resolve(str(output["private_output_root_ref"])).exists()
        or _resolve(str(output["public_result_ref"])).exists()
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_fragment_identity_consumed"
        )
    return paths


def _full_fragment_judgment_artifacts(paths: Mapping[str, Path]):
    _, research_input, _ = _compile_runtime_input(
        paths,
        case_key="DELL",
        required_cell_ids=["CELL::value_capture"],
    )
    kernel, route, _ = _tool_loop_contracts(paths)
    base_policy = load_bounded_finance_loop_policy(_json(paths["loop_policy_ref"]))
    scoped_policy = scope_bounded_finance_micro_judgment_policy(
        base_policy,
        micro_policy=load_fixed_pack_micro_judgment_policy(
            _json(paths["micro_policy_ref"])
        ),
        cell_count=1,
        maximum_evidence_requests=0,
    )
    tools = compile_finance_micro_judgment_tools(
        research_input=research_input,
        required_cell_ids=["CELL::value_capture"],
        kernel=kernel,
        route_policy=route,
        policy=scoped_policy,
        strict=False,
    )
    tool_by_name = {
        str(row["function"]["name"]): row
        for row in tools
        if str(row["function"]["name"]) in MICRO_JUDGMENT_TOOL_NAMES
    }
    if set(tool_by_name) != set(MICRO_JUDGMENT_TOOL_NAMES):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_full_fragment_tool_set_invalid"
        )
    initial_context = compile_finance_micro_fragment_context(
        research_input=research_input,
        cell_id="CELL::value_capture",
        tool_name=SUBMIT_RESEARCH_THESIS_TOOL,
    )
    cell = next(
        row
        for row in research_input["cells"]
        if row["cell_id"] == "CELL::value_capture"
    )
    return research_input, cell, tool_by_name, initial_context


def validate_full_fragment_judgment_authority(
    payload: Mapping[str, Any],
    *,
    authority_path: Path,
) -> dict[str, Path]:
    claim_local_successor = (
        payload.get("schema_version")
        == FULL_FRAGMENT_CLAIM_LOCAL_AUTHORITY_SCHEMA
    )
    route_identifier_successor = (
        payload.get("schema_version")
        == FULL_FRAGMENT_WWC_ROUTE_IDENTIFIER_AUTHORITY_SCHEMA
    )
    causal_polarity_successor = payload.get("schema_version") in {
        FULL_FRAGMENT_CAUSAL_POLARITY_AUTHORITY_SCHEMA,
        FULL_FRAGMENT_WWC_ROUTE_IDENTIFIER_AUTHORITY_SCHEMA,
    }
    if not (
        payload.get("schema_version")
        in {
            FULL_FRAGMENT_JUDGMENT_AUTHORITY_SCHEMA,
            FULL_FRAGMENT_CLAIM_LOCAL_AUTHORITY_SCHEMA,
            FULL_FRAGMENT_CAUSAL_POLARITY_AUTHORITY_SCHEMA,
            FULL_FRAGMENT_WWC_ROUTE_IDENTIFIER_AUTHORITY_SCHEMA,
        }
        and payload.get("status")
        == FULL_FRAGMENT_JUDGMENT_AUTHORITY_STATUS
        and payload.get("case_key") == "DELL"
        and payload.get("cell_id") == "CELL::value_capture"
        and payload.get("ordered_fragment_tools")
        == list(MICRO_JUDGMENT_TOOL_NAMES)
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_full_fragment_authority_invalid"
        )
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_full_fragment_commit_invalid"
        )
    if _git("rev-parse", "HEAD").lower() != commit:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_full_fragment_head_drift"
        )
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_full_fragment_upstream_drift"
        )
    allowed = f"?? {_relative(authority_path)}"
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    if [line for line in status.splitlines() if line] != [allowed]:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_full_fragment_worktree_not_clean"
        )
    expected_budget = {
        "maximum_model_calls": 6,
        "maximum_transport_attempts": 6,
        "maximum_tool_calls": 3,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
        "planner_calls": 0,
        "external_retrieval_calls": 0,
        "embedding_calls": 0,
        "protocol_switches": 0,
        "current_product_pointer_mutations": 0,
    }
    if payload.get("execution_budget") != expected_budget:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_full_fragment_budget_invalid"
        )
    bound = payload.get("bound_inputs")
    output = payload.get("output_contract")
    if not isinstance(bound, Mapping) or not isinstance(output, Mapping):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_full_fragment_shape_invalid"
        )
    required_refs = {
        "consumer_policy_ref",
        "objective_ref",
        "planner_atoms_ref",
        "current_evidence_pack_result_ref",
        "runtime_registry_ref",
        "claim_authority_policy_ref",
        "claim_surface_authority_policy_ref",
        "loop_policy_ref",
        "micro_policy_ref",
        "analysis_profile_ref",
        "submission_profile_ref",
        "runner_ref",
        "loop_implementation_ref",
        "provider_transport_ref",
        "full_fragment_zero_call_result_ref",
        "full_fragment_disposition_ref",
        "prior_fragment_result_ref",
        "prior_fragment_assessment_ref",
        "prior_full_fragment_result_ref",
        "prior_full_fragment_failure_assessment_ref",
    }
    ref_keys = {key for key in bound if key.endswith("_ref")}
    digest_keys = {
        "research_input_digest",
        "initial_fragment_context_digest",
        "fragment_tool_schema_digests",
    }
    expected_keys = {
        value
        for key in ref_keys
        for value in (key, key[:-4] + "_sha256")
    } | digest_keys
    if ref_keys != required_refs or set(bound) != expected_keys:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_full_fragment_bindings_invalid"
        )
    paths: dict[str, Path] = {}
    for key in ref_keys:
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(
            bound.get(key[:-4] + "_sha256") or ""
        ):
            raise CurrentResearchConsumerCanaryError(
                f"research_consumer_full_fragment_bound_input_drift:{key}"
            )
        paths[key] = path
    zero_call = _json(paths["full_fragment_zero_call_result_ref"])
    disposition = _json(paths["full_fragment_disposition_ref"])
    prior_result = _json(paths["prior_fragment_result_ref"])
    prior_assessment = _json(paths["prior_fragment_assessment_ref"])
    prior_full_result = _json(paths["prior_full_fragment_result_ref"])
    prior_full_assessment = _json(
        paths["prior_full_fragment_failure_assessment_ref"]
    )
    common_predecessor_valid = (
        prior_result.get("status")
        == "completed_fragment_contract_valid_content_assessment_pending"
        and prior_assessment.get("status")
        == "single_thesis_L1_pass_content_materially_improved_two_hypotheses_qualified_no_automatic_expansion"
    )
    if causal_polarity_successor:
        normalized_proof = zero_call.get("normalized_proof") or {}
        r3_replay = normalized_proof.get(
            "saved_r3_claim_local_boundary_replay"
        ) or {}
        r4_replay = normalized_proof.get(
            "saved_r4_causal_polarity_replay"
        ) or {}
        r5_replay = normalized_proof.get(
            "saved_r5_wwc_route_identifier_replay"
        ) or {}
        expected_disposition_status = (
            "approved_fresh_full_three_fragment_analysis_submission_Chat_R6"
            if route_identifier_successor
            else "approved_fresh_full_three_fragment_analysis_submission_Chat_R5"
        )
        expected_predecessor_failure = (
            "research_consumer_wwc_evidence_route_invalid"
            if route_identifier_successor
            else "claim_surface_narrative_relation_conflict"
        )
        expected_assessment_status = (
            "terminal_contract_failure_wwc_document_identifier_numeric_"
            "surface_false_positive_new_attempt_required"
            if route_identifier_successor
            else "terminal_contract_failure_clause_and_negation_blind_lexical_"
            "guard_false_positive_new_attempt_required"
        )
        route_identifier_valid = (
            not route_identifier_successor
            or (
                r5_replay.get("predecessor_failure_code")
                == "research_consumer_wwc_evidence_route_invalid"
                and r5_replay.get("qualified_document_identifier") == "10-Q"
                and r5_replay.get("qualified_route_preserved_exactly") is True
                and r5_replay.get("field_scoped_numeric_surface_guard") is True
                and r5_replay.get("unregistered_numeric_surface_fail_closed")
                is True
                and r5_replay.get("model_narratives_preserved_exactly") is True
                and r5_replay.get("harness_generated_research_judgment")
                is False
                and set((r5_replay.get("mutation_failure_codes") or {}))
                == {
                    "percentage_after_qualified_identifier",
                    "year_after_qualified_identifier",
                    "unknown_digit_identifier",
                    "url_with_qualified_identifier",
                    "document_identifier_in_narrative",
                }
            )
        )
        successor_valid = (
            zero_call.get("status")
            == "zero_call_micro_judgment_fresh_process_proof_pass"
            and zero_call.get("fresh_process_results_byte_equivalent") is True
            and r3_replay.get("claim_local_roles_preserved") is True
            and r3_replay.get("report_level_summary_deterministic") is True
            and r4_replay.get("predecessor_failure_code")
            == "claim_surface_narrative_relation_conflict"
            and r4_replay.get("judgment_status") == "bounded_support"
            and r4_replay.get("inference_authority") == "bounded_inference"
            and r4_replay.get("claim_scope") == "multi_scope"
            and r4_replay.get("financial_scope") == "multi_scope_financial"
            and r4_replay.get("causal_bridge_authority")
            == "multi_driver_context_only"
            and r4_replay.get("clause_scoped_guard") is True
            and r4_replay.get(
                "negated_or_unsupported_causal_surface_pass"
            )
            is True
            and r4_replay.get(
                "single_character_cjk_substring_not_authoritative"
            )
            is True
            and r4_replay.get(
                "positive_cross_scope_causal_surface_fail_closed"
            )
            is True
            and set(r4_replay.get("boundary_authority_sources") or ())
            == {
                "typed_bridge_gap_relation",
                "typed_same_scope_counter_relation",
            }
            and r4_replay.get("model_narratives_preserved_exactly") is True
            and r4_replay.get("harness_generated_research_judgment") is False
            and (r4_replay.get("mutation_failure_codes") or {}).get(
                "positive_cross_scope_causal_zh"
            )
            == "claim_surface_narrative_relation_conflict"
            and (r4_replay.get("mutation_failure_codes") or {}).get(
                "positive_cross_scope_causal_en"
            )
            == "claim_surface_narrative_relation_conflict"
            and route_identifier_valid
            and disposition.get("status") == expected_disposition_status
            and disposition.get("execution_budget") == expected_budget
            and disposition.get("claim_local_evidence_roles_required") is True
            and disposition.get("typed_bridge_gap_boundary_required") is True
            and disposition.get("typed_same_scope_counter_boundary_required")
            is True
            and disposition.get("clause_scoped_causal_guard_required") is True
            and disposition.get(
                "negated_or_unsupported_causal_surface_allowed"
            )
            is True
            and disposition.get(
                "ambiguous_single_character_cjk_term_forbidden"
            )
            is True
            and disposition.get(
                "positive_cross_scope_causal_surface_fail_closed"
            )
            is True
            and (
                not route_identifier_successor
                or (
                    disposition.get(
                        "registered_document_identifier_only_in_wwc_route_required"
                    )
                    is True
                    and disposition.get(
                        "unregistered_or_financial_numeric_surface_fail_closed"
                    )
                    is True
                    and disposition.get(
                        "document_identifier_in_narrative_fail_closed"
                    )
                    is True
                )
            )
            and disposition.get("prior_failed_attempt_reused") is False
            and prior_full_result.get("status") == "terminal_failed_no_retry"
            and prior_full_result.get("failure_code")
            == expected_predecessor_failure
            and prior_full_result.get("failure_fragment_tool")
            == SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL
            and prior_full_result.get("execution", {}).get(
                "model_calls_attempted"
            )
            == 6
            and prior_full_result.get("execution", {}).get(
                "tool_calls_accepted"
            )
            == 3
            and prior_full_result.get("execution", {}).get("retries") == 0
            and prior_full_assessment.get("status")
            == expected_assessment_status
            and prior_full_assessment.get("disposition", {}).get(
                "immutable_R5_preserved"
                if route_identifier_successor
                else "immutable_R4_preserved"
            )
            is True
            and (
                route_identifier_successor
                or prior_full_assessment.get("disposition", {}).get(
                    "positive_cross_scope_causal_assertion_must_still_fail_closed"
                )
                is True
            )
        )
    elif claim_local_successor:
        replay = (zero_call.get("normalized_proof") or {}).get(
            "saved_r3_claim_local_boundary_replay"
        ) or {}
        successor_valid = (
            zero_call.get("status")
            == "zero_call_micro_judgment_fresh_process_proof_pass"
            and zero_call.get("fresh_process_results_byte_equivalent") is True
            and (zero_call.get("acceptance") or {}).get(
                "saved_r3_terminal_replay_pass"
            )
            is True
            and replay.get("claim_local_roles_preserved") is True
            and replay.get("report_level_summary_deterministic") is True
            and set(replay.get("boundary_authority_sources") or ())
            == {
                "typed_bridge_gap_relation",
                "typed_same_scope_counter_relation",
            }
            and (replay.get("mutation_failure_codes") or {}).get(
                "global_support_laundering"
            )
            == "claim_surface_required_authority_missing"
            and disposition.get("status")
            == "approved_fresh_full_three_fragment_analysis_submission_Chat_R4"
            and disposition.get("execution_budget") == expected_budget
            and disposition.get("claim_local_evidence_roles_required") is True
            and disposition.get("typed_bridge_gap_boundary_required") is True
            and disposition.get("typed_same_scope_counter_boundary_required")
            is True
            and disposition.get("prior_failed_attempt_reused") is False
            and prior_full_result.get("status") == "terminal_failed_no_retry"
            and prior_full_result.get("failure_code")
            == "finance_loop_micro_evidence_role_conflict"
            and prior_full_result.get("failure_fragment_tool")
            == SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL
            and prior_full_result.get("execution", {}).get(
                "model_calls_attempted"
            )
            == 6
            and prior_full_result.get("execution", {}).get(
                "tool_calls_accepted"
            )
            == 3
            and prior_full_result.get("execution", {}).get("retries") == 0
            and prior_full_assessment.get("status")
            == "terminal_contract_failure_claim_local_evidence_role_and_typed_boundary_aggregation_defect_new_attempt_required"
            and prior_full_assessment.get("disposition", {}).get(
                "immutable_R3_preserved"
            )
            is True
        )
    else:
        successor_valid = (
            zero_call.get("status")
            == "zero_call_relation_support_and_fragment_local_disposition_pass"
            and zero_call.get("execution", {}).get("model_calls") == 0
            and zero_call.get("immutable_predecessor", {}).get(
                "reuse_in_full_judgment_authorized"
            )
            is False
            and disposition.get("status")
            == "approved_fresh_full_three_fragment_analysis_submission_Chat_R3"
            and disposition.get("execution_budget") == expected_budget
        and prior_full_result.get("status") == "terminal_failed_no_retry"
        and prior_full_result.get("failure_code")
        == "finance_loop_micro_required_authority_missing"
        and prior_full_result.get("failure_fragment_tool")
        == SUBMIT_RESEARCH_MECHANISM_TOOL
        and prior_full_result.get("execution", {}).get(
            "model_calls_attempted"
        )
        == 4
        and prior_full_result.get("execution", {}).get(
            "tool_calls_accepted"
        )
        == 1
        and prior_full_result.get("execution", {}).get("retries") == 0
        and prior_full_assessment.get("status")
        == "terminal_contract_failure_relation_evidence_role_and_fragment_disposition_compilation_defect_new_attempt_required"
        and prior_full_assessment.get("disposition", {}).get(
            "immutable_R2_preserved"
        )
        is True
        and prior_full_assessment.get("disposition", {}).get(
            "same_attempt_retry_forbidden"
        )
        is True
        and prior_full_assessment.get("disposition", {}).get("repair_scope")
        == "provider_neutral_relation_support_set_and_fragment_local_disposition_v1_2"
        and zero_call.get("relation_role_contract", {}).get(
            "saved_R2_thesis_replay_pass"
        )
        is True
        and zero_call.get("relation_role_contract", {}).get(
            "saved_R2_mechanism_replay_pass"
        )
        is True
        and zero_call.get("relation_role_contract", {}).get(
            "saved_R2_context_role_preserved"
        )
        is True
        and zero_call.get("relation_role_contract", {}).get(
            "context_only_required_support_mutation_failure"
        )
        == "finance_loop_micro_required_authority_missing"
        and zero_call.get("terminal_compilation", {}).get(
            "judgment_status"
        )
        == "bounded_support"
        and zero_call.get("terminal_compilation", {}).get(
            "inference_authority"
        )
        == "bounded_inference"
        and zero_call.get("fresh_process_results_byte_equivalent") is True
        and disposition.get("relation_support_set_v1_2_required") is True
        and disposition.get("prior_failed_attempt_reused") is False
        )
    if not (common_predecessor_valid and successor_valid):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_full_fragment_disposition_invalid"
        )
    research_input, _, tool_by_name, initial_context = (
        _full_fragment_judgment_artifacts(paths)
    )
    expected_tool_digests = {
        name: canonical_digest(tool_by_name[name])
        for name in MICRO_JUDGMENT_TOOL_NAMES
    }
    if not (
        bound["research_input_digest"] == research_input["research_input_digest"]
        and bound["initial_fragment_context_digest"]
        == initial_context["projection_digest"]
        and bound["fragment_tool_schema_digests"] == expected_tool_digests
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_full_fragment_runtime_digest_drift"
        )
    required_output = {
        "capture_root_ref",
        "private_output_root_ref",
        "public_result_ref",
        "run_id",
        "fragment_attempt_ids",
        "product_publication",
    }
    attempt_ids = output.get("fragment_attempt_ids")
    if not (
        set(output) == required_output
        and output.get("product_publication") == "forbidden"
        and all(
            str(output.get(key) or "")
            for key in required_output
            - {"product_publication", "fragment_attempt_ids"}
        )
        and isinstance(attempt_ids, Mapping)
        and set(attempt_ids) == set(MICRO_JUDGMENT_TOOL_NAMES)
        and all(
            isinstance(value, Mapping)
            and set(value) == {"analysis_attempt_id", "submission_attempt_id"}
            and all(str(item or "") for item in value.values())
            for value in attempt_ids.values()
        )
        and len(
            {
                str(item)
                for value in attempt_ids.values()
                for item in value.values()
            }
        )
        == 6
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_full_fragment_output_invalid"
        )
    capture_run = _resolve(str(output["capture_root_ref"])) / str(
        output["run_id"]
    )
    if (
        capture_run.exists()
        or _resolve(str(output["private_output_root_ref"])).exists()
        or _resolve(str(output["public_result_ref"])).exists()
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_full_fragment_identity_consumed"
        )
    return paths


def _failed_fragment_submission_successor_artifacts(
    paths: Mapping[str, Path],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, dict[str, Any]],
    dict[str, Any],
    tuple[dict[str, str], ...],
    dict[str, Any],
]:
    research_input, cell, tool_by_name, _ = _full_fragment_judgment_artifacts(
        paths
    )
    fixture = _json(paths["submission_successor_fixture_ref"])
    if not (
        fixture.get("schema_version")
        == "fin_ia_s3_full_fragment_submission_successor_fixture_v1_0"
        and fixture.get("case_key") == "DELL"
        and fixture.get("cell_id") == "CELL::value_capture"
        and fixture.get("failed_fragment_tool")
        == SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL
        and fixture.get("research_input_digest")
        == research_input.get("research_input_digest")
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_submission_successor_fixture_invalid"
        )
    raw_fragments = fixture.get("accepted_fragments")
    if not isinstance(raw_fragments, Mapping) or set(raw_fragments) != {
        SUBMIT_RESEARCH_THESIS_TOOL,
        SUBMIT_RESEARCH_MECHANISM_TOOL,
    }:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_submission_successor_predecessor_shape_invalid"
        )
    successor = compile_finance_micro_fragment_submission_successor(
        research_input=research_input,
        cell_id="CELL::value_capture",
        pending_tool_name=SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL,
        accepted_fragments=raw_fragments,
        analysis_draft=str(fixture.get("counter_analysis_content") or ""),
    )
    if successor.get("accepted_prefix_fragment_digests") != fixture.get(
        "accepted_fragment_digests"
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_submission_successor_fragment_drift"
        )
    context = successor["fragment_context"]
    if successor.get("fragment_context_digest") != fixture.get(
        "counter_context_digest"
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_submission_successor_context_drift"
        )
    if successor.get("analysis_draft_digest") != fixture.get(
        "counter_analysis_content_digest"
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_submission_successor_analysis_drift"
        )
    if successor.get("submission_messages_digest") != fixture.get(
        "counter_submission_messages_digest"
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_submission_successor_messages_drift"
        )
    return (
        research_input,
        cell,
        tool_by_name[SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL],
        successor["accepted_prefix_fragments"],
        context,
        tuple(successor["submission_messages"]),
        fixture,
    )


def _failed_fragment_validation_repair_artifacts(
    paths: Mapping[str, Path],
):
    (
        research_input,
        cell,
        counter_tool,
        accepted_prefix,
        _,
        _,
        prefix_fixture,
    ) = _failed_fragment_submission_successor_artifacts(paths)
    rejected_fixture = _json(paths["rejected_fragment_fixture_ref"])
    repair = compile_finance_micro_fragment_validation_repair_successor(
        research_input=research_input,
        cell_id="CELL::value_capture",
        rejected_tool_name=SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL,
        accepted_prefix_fragments=accepted_prefix,
        rejected_fragment=rejected_fixture["rejected_fragment"],
        terminal_failure_code=rejected_fixture["terminal_failure_code"],
    )
    return (
        research_input,
        cell,
        counter_tool,
        repair["accepted_prefix_fragments"],
        repair,
        prefix_fixture,
        rejected_fixture,
    )


def validate_failed_fragment_submission_successor_authority(
    payload: Mapping[str, Any],
    *,
    authority_path: Path,
) -> dict[str, Path]:
    if not (
        payload.get("schema_version")
        == FRAGMENT_SUBMISSION_SUCCESSOR_AUTHORITY_SCHEMA
        and payload.get("status")
        == FRAGMENT_SUBMISSION_SUCCESSOR_AUTHORITY_STATUS
        and payload.get("case_key") == "DELL"
        and payload.get("cell_id") == "CELL::value_capture"
        and payload.get("failed_fragment_tool")
        == SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_submission_successor_authority_invalid"
        )
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_submission_successor_commit_invalid"
        )
    if _git("rev-parse", "HEAD").lower() != commit:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_submission_successor_head_drift"
        )
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_submission_successor_upstream_drift"
        )
    allowed = f"?? {_relative(authority_path)}"
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    if [line for line in status.splitlines() if line] != [allowed]:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_submission_successor_worktree_not_clean"
        )
    expected_budget = {
        "maximum_model_calls": 1,
        "maximum_transport_attempts": 1,
        "maximum_tool_calls": 1,
        "successful_predecessor_model_calls_reused": 5,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
        "planner_calls": 0,
        "external_retrieval_calls": 0,
        "embedding_calls": 0,
        "protocol_switches": 0,
        "current_product_pointer_mutations": 0,
    }
    if payload.get("execution_budget") != expected_budget:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_submission_successor_budget_invalid"
        )
    bound = payload.get("bound_inputs")
    output = payload.get("output_contract")
    if not isinstance(bound, Mapping) or not isinstance(output, Mapping):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_submission_successor_shape_invalid"
        )
    required_refs = {
        "consumer_policy_ref",
        "objective_ref",
        "planner_atoms_ref",
        "current_evidence_pack_result_ref",
        "runtime_registry_ref",
        "claim_authority_policy_ref",
        "claim_surface_authority_policy_ref",
        "loop_policy_ref",
        "micro_policy_ref",
        "submission_profile_ref",
        "runner_ref",
        "loop_implementation_ref",
        "provider_transport_ref",
        "scope_decision_ref",
        "zero_call_result_ref",
        "prior_full_fragment_result_ref",
        "prior_full_fragment_failure_assessment_ref",
        "submission_successor_fixture_ref",
    }
    ref_keys = {key for key in bound if key.endswith("_ref")}
    digest_keys = {
        "research_input_digest",
        "counter_fragment_context_digest",
        "counter_submission_messages_digest",
        "counter_tool_schema_digest",
        "accepted_predecessor_fragment_digests",
    }
    expected_keys = {
        value
        for key in ref_keys
        for value in (key, key[:-4] + "_sha256")
    } | digest_keys
    if ref_keys != required_refs or set(bound) != expected_keys:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_submission_successor_bindings_invalid"
        )
    paths: dict[str, Path] = {}
    for key in ref_keys:
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(
            bound.get(key[:-4] + "_sha256") or ""
        ):
            raise CurrentResearchConsumerCanaryError(
                f"research_consumer_submission_successor_bound_input_drift:{key}"
            )
        paths[key] = path
    prior = _json(paths["prior_full_fragment_result_ref"])
    assessment = _json(paths["prior_full_fragment_failure_assessment_ref"])
    fixture = _json(paths["submission_successor_fixture_ref"])
    zero_call = _json(paths["zero_call_result_ref"])
    scope_decision = _json(paths["scope_decision_ref"])
    replay = (zero_call.get("normalized_proof") or {}).get(
        "saved_r6_non_thinking_submission_successor_replay"
    ) or {}
    profile = load_chat_completion_profile(_json(paths["submission_profile_ref"]))
    validate_deepseek_ga_node_profile(
        profile,
        node_class="contract_submission_non_thinking",
    )
    if not (
        scope_decision.get("schema_version")
        == (
            "fin_ia_s3_fixed_pack_failed_fragment_submission_successor_"
            "live_scope_decision_v1_6"
        )
        and scope_decision.get("status")
        == (
            "failed_fragment_zero_call_pass_one_non_thinking_submission_"
            "successor_authorized"
        )
        and scope_decision.get("maximum_fresh_model_calls") == 1
        and scope_decision.get("successful_predecessor_model_calls_reused")
        == 5
        and scope_decision.get("failed_node_only_execution_required") is True
        and scope_decision.get("successful_predecessor_nodes_rerun") is False
        and scope_decision.get("analysis_node_rerun") is False
        and scope_decision.get("clean_zero_call_result_sha256")
        == _sha(paths["zero_call_result_ref"])
        and scope_decision.get("clean_zero_call_result_digest")
        == zero_call.get("result_digest")
        and scope_decision.get("immutable_failed_result_sha256")
        == _sha(paths["prior_full_fragment_result_ref"])
        and scope_decision.get("immutable_failed_result_digest")
        == prior.get("result_digest")
        and scope_decision.get("submission_successor_fixture_sha256")
        == _sha(paths["submission_successor_fixture_ref"])
        and scope_decision.get("submission_profile_sha256")
        == _sha(paths["submission_profile_ref"])
        and prior.get("status") == "terminal_failed_no_retry"
        and prior.get("failure_code")
        == "model_gateway_reasoning_budget_exhausted"
        and prior.get("failure_fragment_tool")
        == SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL
        and prior.get("execution", {}).get("model_calls_attempted") == 6
        and prior.get("execution", {}).get("tool_calls_accepted") == 2
        and assessment.get("root_cause", {}).get("owner_layer")
        == "S3_replaceable_DeepSeek_contract_submission_profile"
        and fixture.get("source_result_sha256")
        == _sha(paths["prior_full_fragment_result_ref"])
        and fixture.get("source_result_digest") == prior.get("result_digest")
        and zero_call.get("status")
        == "zero_call_micro_judgment_fresh_process_proof_pass"
        and zero_call.get("fresh_process_results_byte_equivalent") is True
        and (zero_call.get("acceptance") or {}).get(
            "saved_r6_submission_successor_replay_pass"
        )
        is True
        and replay.get("predecessor_result_digest") == prior.get("result_digest")
        and replay.get("successful_predecessor_model_calls_reused") == 5
        and replay.get("fresh_model_calls_in_successor") == 1
        and replay.get("reasoning_effort_omitted") is True
        and replay.get("fake_only_not_business_promotion") is True
        and replay.get("harness_generated_research_judgment") is False
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_submission_successor_disposition_invalid"
        )
    (
        research_input,
        _,
        counter_tool,
        accepted,
        context,
        submission_messages,
        _,
    ) = _failed_fragment_submission_successor_artifacts(paths)
    expected_fragment_digests = {
        name: canonical_digest(fragment)
        for name, fragment in accepted.items()
    }
    if not (
        bound.get("research_input_digest")
        == research_input.get("research_input_digest")
        and bound.get("counter_fragment_context_digest")
        == context.get("projection_digest")
        and bound.get("counter_submission_messages_digest")
        == canonical_digest(list(submission_messages))
        and bound.get("counter_tool_schema_digest")
        == canonical_digest(counter_tool)
        and bound.get("accepted_predecessor_fragment_digests")
        == expected_fragment_digests
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_submission_successor_runtime_digest_drift"
        )
    required_output = {
        "capture_root_ref",
        "private_output_root_ref",
        "public_result_ref",
        "run_id",
        "attempt_id",
        "product_publication",
    }
    if not (
        set(output) == required_output
        and output.get("product_publication") == "forbidden"
        and all(str(output.get(key) or "") for key in required_output - {"product_publication"})
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_submission_successor_output_invalid"
        )
    capture_attempt = (
        _resolve(str(output["capture_root_ref"]))
        / str(output["run_id"])
        / str(output["attempt_id"])
    )
    if (
        capture_attempt.exists()
        or _resolve(str(output["private_output_root_ref"])).exists()
        or _resolve(str(output["public_result_ref"])).exists()
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_submission_successor_identity_consumed"
        )
    return paths


def validate_failed_fragment_validation_repair_authority(
    payload: Mapping[str, Any],
    *,
    authority_path: Path,
) -> dict[str, Path]:
    if not (
        payload.get("schema_version")
        == FRAGMENT_VALIDATION_REPAIR_AUTHORITY_SCHEMA
        and payload.get("status")
        == FRAGMENT_VALIDATION_REPAIR_AUTHORITY_STATUS
        and payload.get("case_key") == "DELL"
        and payload.get("cell_id") == "CELL::value_capture"
        and payload.get("rejected_fragment_tool")
        == SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL
        and payload.get("terminal_failure_code")
        == "claim_surface_narrative_relation_conflict"
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_validation_repair_authority_invalid"
        )
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_validation_repair_commit_invalid"
        )
    if _git("rev-parse", "HEAD").lower() != commit:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_validation_repair_head_drift"
        )
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_validation_repair_upstream_drift"
        )
    allowed = f"?? {_relative(authority_path)}"
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    if [line for line in status.splitlines() if line] != [allowed]:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_validation_repair_worktree_not_clean"
        )
    expected_budget = {
        "maximum_model_calls": 1,
        "maximum_transport_attempts": 1,
        "maximum_tool_calls": 1,
        "successful_predecessor_model_calls_reused": 6,
        "maximum_repair_turns": 1,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
        "planner_calls": 0,
        "external_retrieval_calls": 0,
        "embedding_calls": 0,
        "protocol_switches": 0,
        "current_product_pointer_mutations": 0,
    }
    if payload.get("execution_budget") != expected_budget:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_validation_repair_budget_invalid"
        )
    bound = payload.get("bound_inputs")
    output = payload.get("output_contract")
    if not isinstance(bound, Mapping) or not isinstance(output, Mapping):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_validation_repair_shape_invalid"
        )
    required_refs = {
        "consumer_policy_ref",
        "objective_ref",
        "planner_atoms_ref",
        "current_evidence_pack_result_ref",
        "runtime_registry_ref",
        "claim_authority_policy_ref",
        "claim_surface_authority_policy_ref",
        "loop_policy_ref",
        "micro_policy_ref",
        "submission_profile_ref",
        "runner_ref",
        "loop_implementation_ref",
        "provider_transport_ref",
        "scope_decision_ref",
        "zero_call_result_ref",
        "prior_live_result_ref",
        "prior_failure_assessment_ref",
        "submission_successor_fixture_ref",
        "rejected_fragment_fixture_ref",
    }
    ref_keys = {key for key in bound if key.endswith("_ref")}
    digest_keys = {
        "research_input_digest",
        "fragment_context_digest",
        "rejected_fragment_digest",
        "repair_feedback_digest",
        "repair_messages_digest",
        "counter_tool_schema_digest",
        "accepted_predecessor_fragment_digests",
    }
    expected_keys = {
        value
        for key in ref_keys
        for value in (key, key[:-4] + "_sha256")
    } | digest_keys
    if ref_keys != required_refs or set(bound) != expected_keys:
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_validation_repair_bindings_invalid"
        )
    paths: dict[str, Path] = {}
    for key in ref_keys:
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(
            bound.get(key[:-4] + "_sha256") or ""
        ):
            raise CurrentResearchConsumerCanaryError(
                f"research_consumer_validation_repair_bound_input_drift:{key}"
            )
        paths[key] = path
    profile = load_chat_completion_profile(_json(paths["submission_profile_ref"]))
    validate_deepseek_ga_node_profile(
        profile,
        node_class="contract_submission_non_thinking",
    )
    prior = _json(paths["prior_live_result_ref"])
    assessment = _json(paths["prior_failure_assessment_ref"])
    rejected_fixture = _json(paths["rejected_fragment_fixture_ref"])
    zero_call = _json(paths["zero_call_result_ref"])
    scope_decision = _json(paths["scope_decision_ref"])
    replay = (zero_call.get("normalized_proof") or {}).get(
        "saved_r7_validation_repair_successor_replay"
    ) or {}
    if not (
        prior.get("status") == "terminal_failed_no_retry"
        and prior.get("failure_code")
        == "claim_surface_narrative_relation_conflict"
        and prior.get("failure_phase") == "local_terminal_judgment_validation"
        and assessment.get("root_cause", {}).get(
            "local_validator_false_positive"
        )
        is False
        and assessment.get("root_cause", {}).get("financial_L1_observed")
        is True
        and rejected_fixture.get("source_result_sha256")
        == _sha(paths["prior_live_result_ref"])
        and rejected_fixture.get("source_result_digest")
        == prior.get("result_digest")
        and zero_call.get("status")
        == "zero_call_micro_judgment_fresh_process_proof_pass"
        and zero_call.get("fresh_process_results_byte_equivalent") is True
        and (zero_call.get("acceptance") or {}).get(
            "saved_r7_validation_repair_successor_replay_pass"
        )
        is True
        and replay.get("predecessor_result_digest") == prior.get("result_digest")
        and replay.get("maximum_repair_turns") == 1
        and replay.get("local_causal_guard_preserved") is True
        and replay.get("rejected_fragment_promoted_to_business_truth") is False
        and scope_decision.get("schema_version")
        == (
            "fin_ia_s3_fixed_pack_fragment_validation_repair_"
            "live_scope_decision_v1_8"
        )
        and scope_decision.get("status")
        == "zero_call_pass_one_validation_repair_authorized"
        and scope_decision.get("maximum_fresh_model_calls") == 1
        and scope_decision.get("maximum_repair_turns") == 1
        and scope_decision.get("causal_guard_relaxation") is False
        and scope_decision.get("manual_text_rewrite") is False
        and scope_decision.get("clean_zero_call_result_sha256")
        == _sha(paths["zero_call_result_ref"])
        and scope_decision.get("clean_zero_call_result_digest")
        == zero_call.get("result_digest")
        and scope_decision.get("immutable_failed_result_sha256")
        == _sha(paths["prior_live_result_ref"])
        and scope_decision.get("immutable_failed_result_digest")
        == prior.get("result_digest")
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_validation_repair_disposition_invalid"
        )
    (
        research_input,
        _,
        counter_tool,
        _,
        repair,
        _,
        _,
    ) = _failed_fragment_validation_repair_artifacts(paths)
    if not (
        bound.get("research_input_digest")
        == research_input.get("research_input_digest")
        and bound.get("fragment_context_digest")
        == repair.get("fragment_context_digest")
        and bound.get("rejected_fragment_digest")
        == repair.get("rejected_fragment_digest")
        and bound.get("repair_feedback_digest")
        == repair.get("repair_feedback_digest")
        and bound.get("repair_messages_digest")
        == repair.get("repair_messages_digest")
        and bound.get("counter_tool_schema_digest")
        == canonical_digest(counter_tool)
        and bound.get("accepted_predecessor_fragment_digests")
        == repair.get("accepted_prefix_fragment_digests")
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_validation_repair_runtime_digest_drift"
        )
    required_output = {
        "capture_root_ref",
        "private_output_root_ref",
        "public_result_ref",
        "run_id",
        "attempt_id",
        "product_publication",
    }
    if not (
        set(output) == required_output
        and output.get("product_publication") == "forbidden"
        and all(
            str(output.get(key) or "")
            for key in required_output - {"product_publication"}
        )
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_validation_repair_output_invalid"
        )
    capture_attempt = (
        _resolve(str(output["capture_root_ref"]))
        / str(output["run_id"])
        / str(output["attempt_id"])
    )
    if (
        capture_attempt.exists()
        or _resolve(str(output["private_output_root_ref"])).exists()
        or _resolve(str(output["public_result_ref"])).exists()
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_validation_repair_identity_consumed"
        )
    return paths


def _tool_loop_contracts(paths: Mapping[str, Path]):
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
    return kernel, route, planning


def _public_tool_steps(
    attempted_steps: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "step_index": index,
            "finish_reason": row["finish_reason"],
            "tool_names": [
                str(call.get("function", {}).get("name") or "")
                for call in row["tool_calls"]
            ],
            "usage": dict(row["usage"]),
            "request_capture_ref": _relative(row["request_capture_ref"]),
            "response_capture_ref": _relative(row["response_capture_ref"]),
            "request_digest": row["request_digest"],
            "response_digest": row["response_digest"],
            "reasoning_content_persisted": False,
        }
        for index, row in enumerate(attempted_steps, start=1)
    ]


def _incomplete_read_replacement_scope_authorized(
    decision: Mapping[str, Any],
    *,
    cell_ids: Sequence[str],
    clean_zero_call_result: Mapping[str, Any],
) -> bool:
    status = (
        "incomplete_read_capture_replay_pass_"
        "one_chat_replacement_authorized"
    )
    if decision.get("status") != status:
        return False
    boundary = decision.get("replacement_boundary")
    if not isinstance(boundary, Mapping):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_replacement_boundary_invalid"
        )
    proof_path = _resolve(str(boundary.get("transport_capture_proof_ref") or ""))
    r1_result_path = _resolve(str(boundary.get("immutable_r1_result_ref") or ""))
    if not (
        proof_path.is_file()
        and r1_result_path.is_file()
        and _sha(proof_path)
        == str(boundary.get("transport_capture_proof_sha256") or "")
        and _sha(r1_result_path)
        == str(boundary.get("immutable_r1_result_sha256") or "")
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_replacement_evidence_drift"
        )
    proof = _json(proof_path)
    normalized = proof.get("normalized_proof")
    r1_result = _json(r1_result_path)
    if not isinstance(normalized, Mapping):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_replacement_proof_invalid"
        )
    valid_partial = normalized.get("valid_json_partial_mutation")
    malformed_partial = normalized.get("malformed_partial_mutation")
    proof_valid = (
        proof.get("status") == "zero_call_incomplete_read_capture_replay_pass"
        and proof.get("result_digest")
        == boundary.get("transport_capture_proof_result_digest")
        and normalized.get("provider_neutral_shared_terminal_capture_path") is True
        and normalized.get("ordinary_chat_and_tool_calls_both_covered") is True
        and normalized.get("model_calls") == 0
        and normalized.get("network_calls") == 0
        and normalized.get("provider_calls") == 0
        and normalized.get("retries") == 0
        and isinstance(valid_partial, Mapping)
        and valid_partial.get("transport_attempts") == 1
        and valid_partial.get("eligible_for_contract_parse") is False
        and valid_partial.get("eligible_for_business_promotion") is False
        and isinstance(malformed_partial, Mapping)
        and malformed_partial.get("transport_attempts") == 1
        and malformed_partial.get("partial_plaintext_persisted") is False
        and malformed_partial.get("private_reasoning_leaked") is False
        and malformed_partial.get("eligible_for_contract_parse") is False
        and malformed_partial.get("eligible_for_business_promotion") is False
    )
    predecessor_valid = (
        r1_result.get("status") == "terminal_failed_no_retry"
        and r1_result.get("failure_code") == "model_gateway_transport_error"
        and r1_result.get("authority_ref")
        == boundary.get("immutable_r1_authority_ref")
        and r1_result.get("execution", {}).get("retries") == 0
        and r1_result.get("execution", {}).get("fallbacks") == 0
    )
    scope_valid = (
        list(cell_ids) == ["CELL::value_capture"]
        and decision.get("case_key") == "DELL"
        and decision.get("cell_id") == "CELL::value_capture"
        and decision.get("next_authorized_scope")
        == (
            "one_Chat_DELL_value_capture_replacement_after_"
            "incomplete_read_capture_replay"
        )
        and decision.get("research_context_zero_call_result_digest")
        == clean_zero_call_result.get("result_digest")
        and decision.get("chat_live_authorized") is True
        and decision.get("responses_live_authorized") is False
        and decision.get("anthropic_live_authorized") is False
        and decision.get("five_cell_live_authorized") is False
        and decision.get("other_role_method_pack_migration_authorized") is False
        and decision.get("external_retrieval_authorized") is False
        and decision.get("product_publication_authorized") is False
        and decision.get("retries") == 0
        and decision.get("fallbacks") == 0
        and boundary.get("replacement_is_new_attempt_not_retry") is True
        and boundary.get("historical_partial_recovery_claimed") is False
    )
    if not (proof_valid and predecessor_valid and scope_valid):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_replacement_disposition_invalid"
        )
    return True


def _fixed_pack_claim_surface_replacement_scope_authorized(
    decision: Mapping[str, Any],
    *,
    cell_ids: Sequence[str],
    clean_zero_call_result: Mapping[str, Any],
) -> bool:
    expected_status = (
        "fixed_pack_claim_surface_authority_zero_call_pass_"
        "one_chat_replacement_authorized"
    )
    if decision.get("status") != expected_status:
        return False
    predecessor_path = _resolve(
        str(decision.get("immutable_predecessor_result_ref") or "")
    )
    if not (
        predecessor_path.is_file()
        and _sha(predecessor_path)
        == str(decision.get("immutable_predecessor_result_sha256") or "")
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_claim_surface_predecessor_drift"
        )
    predecessor = _json(predecessor_path)
    predecessor_valid = (
        predecessor.get("status") == "terminal_failed_no_retry"
        and predecessor.get("failure_code")
        == "finance_loop_judgment_invalid:research_consumer_thesis_atom_invalid"
        and predecessor.get("result_digest")
        == decision.get("immutable_predecessor_result_digest")
        and predecessor.get("execution", {}).get("retries") == 0
        and predecessor.get("execution", {}).get("fallbacks") == 0
    )
    scope_valid = (
        list(cell_ids) == ["CELL::value_capture"]
        and decision.get("case_key") == "DELL"
        and decision.get("cell_id") == "CELL::value_capture"
        and decision.get("next_authorized_scope")
        == "one_DELL_value_capture_fixed_pack_claim_surface_Chat_replacement"
        and decision.get("clean_zero_call_result_digest")
        == clean_zero_call_result.get("result_digest")
        and decision.get("maximum_evidence_requests") == 0
        and decision.get("chat_live_authorized") is True
        and decision.get("responses_live_authorized") is False
        and decision.get("anthropic_live_authorized") is False
        and decision.get("dynamic_layer_two_authorized") is False
        and decision.get("five_cell_live_authorized") is False
        and decision.get("product_publication_authorized") is False
        and decision.get("retries") == 0
        and decision.get("fallbacks") == 0
        and decision.get("replacement_is_new_attempt_not_retry") is True
        and decision.get("historical_failure_promoted") is False
    )
    if not (predecessor_valid and scope_valid):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_claim_surface_replacement_disposition_invalid"
        )
    return True


def _fixed_pack_claim_relation_alias_replacement_scope_authorized(
    decision: Mapping[str, Any],
    *,
    cell_ids: Sequence[str],
    clean_zero_call_result: Mapping[str, Any],
) -> bool:
    expected_status = (
        "fixed_pack_claim_relation_alias_capacity_zero_call_pass_"
        "one_chat_successor_authorized"
    )
    if decision.get("status") != expected_status:
        return False
    predecessor_path = _resolve(
        str(decision.get("immutable_predecessor_result_ref") or "")
    )
    if not (
        predecessor_path.is_file()
        and _sha(predecessor_path)
        == str(decision.get("immutable_predecessor_result_sha256") or "")
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_claim_relation_alias_predecessor_drift"
        )
    predecessor = _json(predecessor_path)
    predecessor_valid = (
        predecessor.get("status") == "terminal_failed_no_retry"
        and predecessor.get("failure_code")
        == "model_gateway_reasoning_budget_exhausted"
        and predecessor.get("result_digest")
        == decision.get("immutable_predecessor_result_digest")
        and predecessor.get("execution", {}).get("retries") == 0
        and predecessor.get("execution", {}).get("fallbacks") == 0
    )
    scope_valid = (
        list(cell_ids) == ["CELL::value_capture"]
        and decision.get("case_key") == "DELL"
        and decision.get("cell_id") == "CELL::value_capture"
        and decision.get("next_authorized_scope")
        == "one_DELL_value_capture_fixed_pack_claim_relation_alias_Chat_successor"
        and decision.get("clean_zero_call_result_digest")
        == clean_zero_call_result.get("result_digest")
        and decision.get("maximum_evidence_requests") == 0
        and decision.get("chat_live_authorized") is True
        and decision.get("responses_live_authorized") is False
        and decision.get("anthropic_live_authorized") is False
        and decision.get("dynamic_layer_two_authorized") is False
        and decision.get("five_cell_live_authorized") is False
        and decision.get("product_publication_authorized") is False
        and decision.get("same_evidence_pack_and_provider_profile") is True
        and decision.get("reasoning_or_token_limit_increase") is False
        and decision.get("retries") == 0
        and decision.get("fallbacks") == 0
        and decision.get("replacement_is_new_attempt_not_retry") is True
        and decision.get("historical_failure_promoted") is False
    )
    if not (predecessor_valid and scope_valid):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_claim_relation_alias_replacement_disposition_invalid"
        )
    return True


def _fixed_pack_micro_judgment_scope_authorized(
    decision: Mapping[str, Any],
    *,
    cell_ids: Sequence[str],
    clean_zero_call_result: Mapping[str, Any],
    clean_zero_call_authority: Mapping[str, Any],
    prior_live_result: Mapping[str, Any],
    prior_capacity_assessment: Mapping[str, Any],
) -> bool:
    """Qualify one natural micro successor without relabeling R2.

    Every evidence object is separately hash-bound by the live authority.  This
    check joins their semantic identities and keeps the permission narrower
    than dynamic research, five-cell execution, protocol switching or retry.
    """

    expected_status = (
        "micro_judgment_formal_zero_call_pass_"
        "canonical_live_gate_required_one_chat_successor_authorized"
    )
    if not (
        decision.get("schema_version")
        == "fin_ia_s3_fixed_pack_micro_judgment_live_scope_decision_v1_0"
        and decision.get("decision_id")
        == (
            "FIN-0.1.3-S3-DELL-VALUE-CAPTURE-FIXED-PACK-"
            "MICRO-JUDGMENT-LIVE-SCOPE-DECISION-V1.0"
        )
        and decision.get("status") == expected_status
    ):
        return False
    observed = prior_capacity_assessment.get("observed")
    acceptance = prior_capacity_assessment.get("acceptance")
    clean_normalized = clean_zero_call_result.get("normalized_proof")
    predecessor_valid = (
        prior_live_result.get("status") == "terminal_failed_no_retry"
        and prior_live_result.get("failure_code")
        == "model_gateway_reasoning_budget_exhausted"
        and prior_live_result.get("result_digest")
        == decision.get("immutable_predecessor_result_digest")
        and prior_live_result.get("execution", {}).get("retries") == 0
        and prior_live_result.get("execution", {}).get("fallbacks") == 0
        and prior_capacity_assessment.get("status")
        == (
            "terminal_capacity_failure_preserved_"
            "monolithic_judgment_successor_required"
        )
        and prior_capacity_assessment.get("result_digest")
        == prior_live_result.get("result_digest")
        and isinstance(observed, Mapping)
        and observed.get("judgment_materialized") is False
        and observed.get("retries") == 0
        and observed.get("fallbacks") == 0
        and isinstance(acceptance, Mapping)
        and acceptance.get("fixed_pack_layer_one_accepted") is False
    )
    clean_valid = (
        clean_zero_call_authority.get("authority_id")
        == decision.get("formal_zero_call_authority_id")
        and clean_zero_call_result.get("status")
        == "zero_call_micro_judgment_fresh_process_proof_pass"
        and clean_zero_call_result.get("result_digest")
        == decision.get("formal_zero_call_result_digest")
        and clean_zero_call_result.get("fresh_process_results_byte_equivalent")
        is True
        and isinstance(clean_normalized, Mapping)
        and clean_normalized.get("step_count") == 4
        and clean_normalized.get("tool_call_count") == 5
        and clean_normalized.get("network_calls") == 0
        and clean_normalized.get("model_calls") == 0
        and clean_normalized.get("provider_calls") == 0
        and clean_normalized.get("retries") == 0
    )
    scope_valid = (
        list(cell_ids) == ["CELL::value_capture"]
        and decision.get("case_key") == "DELL"
        and decision.get("cell_id") == "CELL::value_capture"
        and decision.get("next_authorized_scope")
        == "one_DELL_value_capture_fixed_pack_micro_judgment_Chat_successor"
        and decision.get("maximum_model_calls") == 4
        and decision.get("maximum_tool_calls") == 5
        and decision.get("maximum_evidence_requests") == 0
        and decision.get("chat_live_authorized") is True
        and decision.get("responses_live_authorized") is False
        and decision.get("anthropic_live_authorized") is False
        and decision.get("dynamic_layer_two_authorized") is False
        and decision.get("five_cell_live_authorized") is False
        and decision.get("product_publication_authorized") is False
        and decision.get("canonical_live_gate_required") is True
        and decision.get("reasoning_or_token_limit_increase") is False
        and decision.get("retries") == 0
        and decision.get("fallbacks") == 0
        and decision.get("replacement_is_new_attempt_not_retry") is True
        and decision.get("historical_failure_promoted") is False
    )
    if not (predecessor_valid and clean_valid and scope_valid):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_micro_judgment_disposition_invalid"
        )
    return True


def _select_micro_node_profile(
    step_tools: Sequence[Mapping[str, Any]],
    *,
    read_profile: ChatCompletionProfile,
    judgment_profile: ChatCompletionProfile,
) -> tuple[ChatCompletionProfile, str]:
    names = tuple(
        str(row.get("function", {}).get("name") or "")
        for row in step_tools
    )
    if set(names) == {
        READ_REVIEWED_EVIDENCE_TOOL,
        READ_NUMERIC_FACTS_TOOL,
    } and len(names) == 2:
        return read_profile, "tool_routing"
    if len(names) == 1 and names[0] in MICRO_JUDGMENT_TOOL_NAMES:
        return judgment_profile, "bounded_financial_judgment"
    raise CurrentResearchConsumerCanaryError(
        "research_consumer_micro_active_tool_set_invalid"
    )


def run_tool_loop(
    authority_path: Path,
    *,
    step_executor: Callable[..., ChatCompletionToolStepResult] = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> dict[str, Any]:
    authority = _json(authority_path)
    micro_mode = (
        authority.get("schema_version") == MICRO_TOOL_LOOP_AUTHORITY_SCHEMA
    )
    paths = validate_tool_loop_authority(
        authority, authority_path=authority_path
    )
    case_key = str(authority["case_key"])
    cell_ids = tuple(str(value) for value in authority["required_cell_ids"])
    _, research_input, _ = _compile_runtime_input(
        paths,
        case_key=case_key,
        required_cell_ids=cell_ids,
    )
    if len(cell_ids) == 5 and cell_ids != tuple(
        str(row["cell_id"]) for row in research_input["cells"]
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_five_cell_scope_invalid"
        )
    kernel, route, planning = _tool_loop_contracts(paths)
    base_policy = load_bounded_finance_loop_policy(
        _json(paths["loop_policy_ref"])
    )
    maximum_evidence_requests = int(
        authority["execution_budget"]["maximum_evidence_requests"]
    )
    if micro_mode:
        micro_policy = load_fixed_pack_micro_judgment_policy(
            _json(paths["micro_policy_ref"])
        )
        scoped_policy = scope_bounded_finance_micro_judgment_policy(
            base_policy,
            micro_policy=micro_policy,
            cell_count=len(cell_ids),
            maximum_evidence_requests=maximum_evidence_requests,
        )
        tools = compile_finance_micro_judgment_tools(
            research_input=research_input,
            required_cell_ids=cell_ids,
            kernel=kernel,
            route_policy=route,
            policy=scoped_policy,
            strict=False,
        )
    else:
        scoped_policy = scope_bounded_finance_loop_policy(
            base_policy,
            cell_count=len(cell_ids),
            maximum_evidence_requests=maximum_evidence_requests,
        )
        tools = compile_finance_loop_tools(
            research_input=research_input,
            required_cell_ids=cell_ids,
            kernel=kernel,
            route_policy=route,
            policy=scoped_policy,
            strict=False,
        )
    visible_execution_budget = {
        "maximum_steps": scoped_policy.maximum_steps,
        "maximum_evidence_requests": maximum_evidence_requests,
        "maximum_reads_per_cell": 1,
        "maximum_parallel_read_tools": 2,
        "maximum_judgments_per_cell": 1,
        "retry_count": 0,
    }
    messages = compile_finance_loop_messages(
        research_input=research_input,
        required_cell_ids=cell_ids,
        execution_budget=visible_execution_budget,
        micro_judgment_mode=micro_mode,
    )
    actual = {
        "research_input_digest": research_input["research_input_digest"],
        "finance_loop_messages_digest": canonical_digest(list(messages)),
        (
            "micro_tool_schema_digest"
            if micro_mode
            else "standard_tool_schema_digest"
        ): canonical_digest(list(tools)),
    }
    bound = authority["bound_inputs"]
    if any(str(bound[key]) != str(value) for key, value in actual.items()):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_runtime_binding_drift"
        )
    clean = _json(paths["clean_zero_call_result_ref"])
    normalized = clean.get("normalized_proof", {})
    claim_authority_mode = "claim_authority_policy_ref" in paths
    claim_surface_authority_mode = (
        "claim_surface_authority_policy_ref" in paths
    )
    ordinary_clean = (
        clean.get("status")
        == "zero_call_engineering_and_fresh_process_proof_pass"
        and normalized.get("research_input_digest")
        == research_input["research_input_digest"]
        and normalized.get("single_cell_maximum_steps") == 6
        and normalized.get("safe_parallel_read_pair_pass") is True
        and normalized.get("wire_tool_call_index_stripped") is True
        and normalized.get("standard_profile_max_tokens") == 16000
        and "finance_loop_parallel_tool_set_invalid"
        in normalized.get("mutation_failure_codes", [])
        and "finance_loop_required_cell_reads_incomplete"
        in normalized.get("mutation_failure_codes", [])
    )
    claim_clean = (
        clean.get("status")
        == "engineering_pass_zero_call_fixed_pack_claim_authority"
        and normalized.get("research_input_digest")
        == research_input["research_input_digest"]
        and normalized.get("maximum_model_steps") == 3
        and normalized.get("maximum_evidence_requests") == 0
        and normalized.get("fake_loop_steps") == 2
        and normalized.get("fake_loop_tool_calls") == 3
        and normalized.get("fake_loop_evidence_requests") == 0
        and normalized.get("saved_r2_negative_replay_code")
        == "claim_authority_cross_scope_causal_language_unbound"
        and normalized.get("fixed_pack_unit_test_only") is True
        and normalized.get("agentic_research_claimed") is False
        and normalized.get("model_calls") == 0
        and normalized.get("network_calls") == 0
    )
    claim_surface_clean = (
        clean.get("status")
        == "engineering_pass_zero_call_claim_surface_authority"
        and normalized.get("claim_surface_input_digest")
        == research_input["research_input_digest"]
        and normalized.get("finance_loop_messages_digest")
        == actual["finance_loop_messages_digest"]
        and normalized.get("standard_tool_schema_digest")
        == actual["standard_tool_schema_digest"]
        and normalized.get("structured_claim_relations_per_atom") == 3
        and normalized.get("qualitative_band_converted_to_point_estimate")
        is False
        and normalized.get("fake_loop_steps") == 2
        and normalized.get("fake_loop_tool_calls") == 3
        and normalized.get("fake_loop_evidence_requests") == 0
        and normalized.get("agentic_research_claimed") is False
        and normalized.get("model_calls") == 0
        and normalized.get("network_calls") == 0
        and normalized.get("retries") == 0
    )
    claim_relation_alias_clean = (
        clean.get("status")
        == "engineering_pass_zero_call_claim_relation_alias_capacity"
        and normalized.get("claim_relation_alias_input_digest")
        == research_input["research_input_digest"]
        and normalized.get("finance_loop_initial_messages_digest")
        == actual["finance_loop_messages_digest"]
        and normalized.get("standard_tool_schema_digest")
        == actual["standard_tool_schema_digest"]
        and normalized.get("relation_aliases_selected") == 3
        and normalized.get("relations_expanded_locally") == 3
        and normalized.get("full_internal_lineage_retained") is True
        and normalized.get("compact_model_view_hides_audit_lineage") is True
        and normalized.get("authority_cards_visible_once") is True
        and normalized.get("zero_budget_evidence_request_tool_omitted") is True
        and normalized.get("current_to_prior_message_ratio", 1) < 0.5
        and normalized.get("current_to_prior_tool_ratio", 1) < 0.55
        and normalized.get("fake_loop_steps") == 2
        and normalized.get("fake_loop_tool_calls") == 3
        and normalized.get("fake_loop_evidence_requests") == 0
        and normalized.get("model_calls") == 0
        and normalized.get("network_calls") == 0
        and normalized.get("retries") == 0
    )
    micro_clean = (
        micro_mode
        and clean.get("status")
        == "zero_call_micro_judgment_fresh_process_proof_pass"
        and normalized.get("research_input_digest")
        == research_input["research_input_digest"]
        and normalized.get("step_count") == 4
        and normalized.get("tool_call_count") == 5
        and normalized.get("ordered_model_owned_phases")
        == list(MICRO_JUDGMENT_TOOL_NAMES)
        and normalized.get("model_authored_narratives_preserved_exactly")
        is True
        and normalized.get("harness_generated_missing_claim_or_fragment")
        is False
        and normalized.get("three_case_context_all_pass") is True
        and normalized.get("three_case_identity_pollution_count") == 0
        and normalized.get("three_case_graph_context_pollution_count") == 0
        and clean.get("fresh_process_results_byte_equivalent") is True
        and normalized.get("model_calls") == 0
        and normalized.get("network_calls") == 0
        and normalized.get("provider_calls") == 0
        and normalized.get("retries") == 0
    )
    if not (
        micro_clean
        or (
            claim_surface_authority_mode
            and claim_authority_mode
            and (claim_surface_clean or claim_relation_alias_clean)
        )
        or (
            claim_authority_mode
            and not claim_surface_authority_mode
            and claim_clean
        )
        or (not claim_authority_mode and ordinary_clean)
    ):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_clean_proof_drift"
        )
    prior_scope_decision = _json(paths["prior_scope_decision_ref"])
    micro_zero_call_authority = (
        _json(paths["micro_zero_call_authority_ref"])
        if micro_mode
        else {}
    )
    prior_live_result = (
        _json(paths["prior_live_result_ref"]) if micro_mode else {}
    )
    prior_capacity_assessment = (
        _json(paths["prior_capacity_assessment_ref"])
        if micro_mode
        else {}
    )
    research_context_revalidation_authorized = (
        len(cell_ids) == 1
        and prior_scope_decision.get("status")
        == "research_context_closure_zero_call_pass_one_chat_revalidation_authorized"
        and prior_scope_decision.get("case_key") == "DELL"
        and prior_scope_decision.get("cell_id") == "CELL::value_capture"
        and prior_scope_decision.get("next_authorized_scope")
        == "one_Chat_DELL_value_capture_revalidation_after_research_context_closure"
        and prior_scope_decision.get("clean_zero_call_result_digest")
        == clean.get("result_digest")
        and prior_scope_decision.get("chat_live_authorized") is True
        and prior_scope_decision.get("responses_live_authorized") is False
        and prior_scope_decision.get("five_cell_live_authorized") is False
        and prior_scope_decision.get("other_role_method_pack_migration_authorized")
        is False
    )
    incomplete_read_replacement_authorized = (
        _incomplete_read_replacement_scope_authorized(
            prior_scope_decision,
            cell_ids=cell_ids,
            clean_zero_call_result=clean,
        )
    )
    fixed_pack_claim_authority_authorized = (
        claim_authority_mode
        and not claim_surface_authority_mode
        and len(cell_ids) == 1
        and prior_scope_decision.get("status")
        == "fixed_pack_claim_authority_zero_call_pass_one_chat_canary_authorized"
        and prior_scope_decision.get("case_key") == "DELL"
        and prior_scope_decision.get("cell_id") == "CELL::value_capture"
        and prior_scope_decision.get("clean_zero_call_result_digest")
        == clean.get("result_digest")
        and prior_scope_decision.get("next_authorized_scope")
        == "one_DELL_value_capture_fixed_pack_Chat_canary"
        and prior_scope_decision.get("maximum_evidence_requests") == 0
        and prior_scope_decision.get("chat_live_authorized") is True
        and prior_scope_decision.get("dynamic_layer_two_authorized") is False
        and prior_scope_decision.get("five_cell_live_authorized") is False
        and prior_scope_decision.get("product_publication_authorized") is False
    )
    fixed_pack_claim_surface_authority_authorized = (
        not micro_mode
        and claim_surface_authority_mode
        and claim_authority_mode
        and (
            _fixed_pack_claim_surface_replacement_scope_authorized(
                prior_scope_decision,
                cell_ids=cell_ids,
                clean_zero_call_result=clean,
            )
            or _fixed_pack_claim_relation_alias_replacement_scope_authorized(
                prior_scope_decision,
                cell_ids=cell_ids,
                clean_zero_call_result=clean,
            )
        )
    )
    fixed_pack_micro_judgment_authorized = (
        micro_mode
        and claim_surface_authority_mode
        and claim_authority_mode
        and _fixed_pack_micro_judgment_scope_authorized(
            prior_scope_decision,
            cell_ids=cell_ids,
            clean_zero_call_result=clean,
            clean_zero_call_authority=micro_zero_call_authority,
            prior_live_result=prior_live_result,
            prior_capacity_assessment=prior_capacity_assessment,
        )
    )
    single_scope_authorized = (
        len(cell_ids) == 1
        and (
            fixed_pack_micro_judgment_authorized
            or research_context_revalidation_authorized
            or incomplete_read_replacement_authorized
            or fixed_pack_claim_authority_authorized
            or fixed_pack_claim_surface_authority_authorized
            or (
                prior_scope_decision.get("status")
                == "json_node_pass_strict_transport_unqualified_full_report_not_scored"
                and prior_scope_decision.get("next_authorized_scope")
                == "one_standard_API_four_tool_single_cell_live_on_the_same_DELL_value_capture_input_after_clean_implementation_and_authority"
                and prior_scope_decision.get("five_cell_live_authorized") is False
            )
            or (
                prior_scope_decision.get("status")
                == "terminal_failed_project_wire_and_safe_parallel_read_compatibility"
                and prior_scope_decision.get("replacement_boundary", {}).get(
                    "replacement_single_cell_live_allowed_after_clean_proof"
                )
                is True
                and prior_scope_decision.get("replacement_boundary", {}).get(
                    "five_cell_live_authorized"
                )
                is False
            )
        )
    )
    five_scope_authorized = (
        len(cell_ids) == 5
        and prior_scope_decision.get("status")
        == "standard_tool_single_cell_pass_five_cell_authorized"
        and prior_scope_decision.get("next_authorized_scope")
        == "one_DELL_five_cell_standard_API_bounded_finance_loop_live_after_clean_authority"
        and prior_scope_decision.get("five_cell_live_authorized") is True
    )
    if not (single_scope_authorized or five_scope_authorized):
        raise CurrentResearchConsumerCanaryError(
            "research_consumer_tool_loop_prior_disposition_invalid"
        )
    if micro_mode:
        read_profile = load_chat_completion_profile(
            _json(paths["micro_read_profile_ref"])
        )
        judgment_profile = load_chat_completion_profile(
            _json(paths["micro_judgment_profile_ref"])
        )
        validate_deepseek_ga_node_profile(
            read_profile, node_class="tool_routing"
        )
        validate_deepseek_ga_node_profile(
            judgment_profile, node_class="bounded_financial_judgment"
        )
        profile = None
    else:
        profile = load_chat_completion_profile(
            _json(paths["provider_profile_ref"])
        )
        validate_deepseek_ga_profile(profile, strict_tools=False)
        if profile.request_defaults.get("max_tokens") != 16000:
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_tool_loop_profile_capacity_invalid"
            )
    output = authority["output_contract"]
    private_root = _resolve(str(output["private_output_root_ref"]))
    capture_root = _resolve(str(output["capture_root_ref"]))
    run_id = str(output["run_id"])
    prefix = str(output["step_attempt_prefix"])
    state: dict[str, Any] = {
        "model_calls_attempted": 0,
        "attempted_steps": [],
        "node_profile_selections": [],
        "last_attempt_id": "",
        "failure_capture_ref": "",
    }
    receipt_refs: list[str] = []

    def record_receipt(receipt: Mapping[str, Any]) -> None:
        step_index = int(receipt["step_index"])
        sequence = int(receipt["receipt_sequence"])
        path = private_root / (
            f"receipt-{sequence:02d}-step-{step_index:02d}.json"
        )
        _write_new(path, receipt)
        receipt_refs.append(_relative(path))

    def execute_step(
        step_messages: Sequence[Mapping[str, Any]],
        step_tools: Sequence[Mapping[str, Any]],
        step_index: int,
    ) -> ChatCompletionToolStepResult:
        if micro_mode:
            selected_profile, node_class = _select_micro_node_profile(
                step_tools,
                read_profile=read_profile,
                judgment_profile=judgment_profile,
            )
            profile_ref = (
                paths["micro_read_profile_ref"]
                if node_class == "tool_routing"
                else paths["micro_judgment_profile_ref"]
            )
        else:
            if profile is None:
                raise CurrentResearchConsumerCanaryError(
                    "research_consumer_tool_loop_profile_missing"
                )
            selected_profile = profile
            node_class = "legacy_bounded_finance_loop"
            profile_ref = paths["provider_profile_ref"]
        attempt_id = f"{prefix}-{step_index:02d}-ATTEMPT-01"
        state["model_calls_attempted"] += 1
        state["last_attempt_id"] = attempt_id
        state["node_profile_selections"].append(
            {
                "step_index": step_index,
                "node_class": node_class,
                "profile_ref": _relative(profile_ref),
                "profile_sha256": _sha(profile_ref),
                "reasoning_effort": selected_profile.request_defaults.get(
                    "reasoning_effort"
                ),
                "max_tokens": selected_profile.request_defaults.get(
                    "max_tokens"
                ),
                "active_tool_names": [
                    str(row.get("function", {}).get("name") or "")
                    for row in step_tools
                ],
            }
        )
        try:
            step = step_executor(
                profile=selected_profile,
                messages=step_messages,
                tools=step_tools,
                capture_root=capture_root,
                run_id=run_id,
                attempt_id=attempt_id,
                tool_choice=None,
            )
        except ModelGatewayError as exc:
            state["failure_capture_ref"] = exc.capture_ref
            raise
        state["attempted_steps"].append(step.as_dict())
        return step

    loop_result = None
    failure_phase = ""
    failure_code = ""
    try:
        loop_result = run_bounded_finance_loop(
            policy=scoped_policy,
            research_input=research_input,
            required_cell_ids=cell_ids,
            kernel=kernel,
            route_policy=route,
            planning_policy=planning,
            tools=tools,
            step_executor=execute_step,
            receipt_recorder=record_receipt,
            visible_execution_budget=visible_execution_budget,
        )
    except ModelGatewayError as exc:
        failure_phase = "provider_transport_or_response"
        failure_code = exc.code
    except BoundedFinanceLoopError as exc:
        failure_phase = "local_finance_loop_validation"
        failure_code = exc.code
        if state["attempted_steps"]:
            state["failure_capture_ref"] = state["attempted_steps"][-1][
                "response_capture_ref"
            ]
    except CurrentResearchConsumerCanaryError as exc:
        failure_phase = "local_live_runner_validation"
        failure_code = exc.code
    status = (
        "completed_contract_valid_content_assessment_pending"
        if loop_result is not None
        else "terminal_failed_no_retry"
    )
    full_body: dict[str, Any] = {
        "schema_version": TOOL_LOOP_FULL_SCHEMA,
        "status": status,
        "recorded_at": _now(),
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": case_key,
        "required_cell_ids": list(cell_ids),
        "research_input_digest": research_input["research_input_digest"],
        "scoped_budget": {
            "maximum_steps": scoped_policy.maximum_steps,
            "maximum_tool_calls": scoped_policy.maximum_tool_calls,
            "maximum_calls_by_tool": dict(
                scoped_policy.maximum_calls_by_tool
            ),
        },
        "model_calls_attempted": state["model_calls_attempted"],
        "attempted_provider_steps": state["attempted_steps"],
        "node_profile_selections": state["node_profile_selections"],
        "receipt_refs": receipt_refs,
        "failure_phase": failure_phase,
        "failure_code": failure_code,
        "failure_capture_ref": (
            _relative(state["failure_capture_ref"])
            if state["failure_capture_ref"]
            else ""
        ),
        "loop_result": loop_result.as_dict() if loop_result is not None else {},
        "retries": 0,
        "fallbacks": 0,
        "external_retrieval_calls": 0,
        "embedding_calls": 0,
        "product_publication": False,
        "private_reasoning_persisted": False,
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    full_path = private_root / "full_result.json"
    _write_new(full_path, full)
    public_body = {
        "schema_version": TOOL_LOOP_RESULT_SCHEMA,
        "status": status,
        "recorded_at": full["recorded_at"],
        "authority_ref": full["authority_ref"],
        "authority_sha256": full["authority_sha256"],
        "implementation_commit": full["implementation_commit"],
        "case_key": case_key,
        "required_cell_ids": list(cell_ids),
        "research_input_digest": research_input["research_input_digest"],
        "execution": {
            "model_calls_attempted": state["model_calls_attempted"],
            "maximum_model_calls": scoped_policy.maximum_steps,
            "retries": 0,
            "fallbacks": 0,
            "planner_calls": 0,
            "external_retrieval_calls": 0,
            "embedding_calls": 0,
            "tool_choice_sent": False,
            "product_publication": False,
        },
        "provider_steps": _public_tool_steps(state["attempted_steps"]),
        "node_profile_selections": state["node_profile_selections"],
        "accepted_receipt_count": len(receipt_refs),
        "accepted_receipt_refs": receipt_refs,
        "tool_counts": (
            dict(loop_result.tool_counts) if loop_result is not None else {}
        ),
        "deliverable_digest": (
            loop_result.as_dict()["structured_deliverable"][
                "deliverable_digest"
            ]
            if loop_result is not None
            else ""
        ),
        "failure_phase": failure_phase,
        "failure_code": failure_code,
        "failure_capture_ref": full["failure_capture_ref"],
        "full_result_ref": _relative(full_path),
        "full_result_sha256": _sha(full_path),
        "acceptance": {
            "standard_tool_transport_and_local_contract_pass": (
                loop_result is not None
            ),
            "required_evidence_and_numeric_reads_enforced": True,
            "content_assessment_pending": loop_result is not None,
            "five_cell_live_authorized": False,
            "s3_product_acceptance": False,
            "qualified_human_acceptance": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    summary = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new(_resolve(str(output["public_result_ref"])), summary)
    return summary


def run_fragment_analysis_submission(authority_path: Path) -> dict[str, Any]:
    authority = _json(authority_path)
    paths = validate_fragment_analysis_submission_authority(
        authority,
        authority_path=authority_path,
    )
    research_input, context, analysis_messages, thesis_tool = (
        _fragment_analysis_submission_artifacts(paths)
    )
    analysis_profile = load_chat_completion_profile(
        _json(paths["analysis_profile_ref"])
    )
    submission_profile = load_chat_completion_profile(
        _json(paths["submission_profile_ref"])
    )
    validate_deepseek_ga_node_profile(
        analysis_profile,
        node_class="bounded_financial_analysis",
    )
    validate_deepseek_ga_node_profile(
        submission_profile,
        node_class="contract_submission",
    )
    output = authority["output_contract"]
    capture_root = _resolve(str(output["capture_root_ref"]))
    private_root = _resolve(str(output["private_output_root_ref"]))
    run_id = str(output["run_id"])
    analysis: ChatCompletionResult | None = None
    submission: ChatCompletionToolStepResult | None = None
    validated_fragment: dict[str, Any] = {}
    failure_phase = ""
    failure_code = ""
    failure_capture_ref = ""
    model_calls_attempted = 0
    submission_messages: tuple[dict[str, str], ...] = ()
    try:
        model_calls_attempted += 1
        analysis = execute_chat_completion_exact_once(
            profile=analysis_profile,
            messages=analysis_messages,
            capture_root=capture_root,
            run_id=run_id,
            attempt_id=str(output["analysis_attempt_id"]),
        )
        if analysis.finish_reason == "length":
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_fragment_analysis_length_stop"
            )
        submission_messages = compile_finance_micro_fragment_submission_messages(
            fragment_context=context,
            analysis_draft=analysis.content,
        )
        model_calls_attempted += 1
        submission = execute_chat_completion_tool_step_exact_once(
            profile=submission_profile,
            messages=submission_messages,
            tools=[thesis_tool],
            capture_root=capture_root,
            run_id=run_id,
            attempt_id=str(output["submission_attempt_id"]),
            tool_choice=None,
        )
        if submission.finish_reason == "length":
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_fragment_submission_length_stop"
            )
        if len(submission.tool_calls) != 1:
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_fragment_tool_call_count_invalid"
            )
        call = submission.tool_calls[0]
        function = call.get("function")
        if not (
            isinstance(function, Mapping)
            and function.get("name") == SUBMIT_RESEARCH_THESIS_TOOL
        ):
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_fragment_tool_name_invalid"
            )
        try:
            arguments = json.loads(str(function.get("arguments") or ""))
        except json.JSONDecodeError as exc:
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_fragment_tool_arguments_invalid_json"
            ) from exc
        if not isinstance(arguments, Mapping):
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_fragment_tool_arguments_invalid"
            )
        validated_fragment = validate_finance_micro_judgment_fragment(
            tool_name=SUBMIT_RESEARCH_THESIS_TOOL,
            arguments=arguments,
            research_input=research_input,
            cell_id="CELL::value_capture",
        )
    except ModelGatewayError as exc:
        failure_phase = "provider_transport_or_response"
        failure_code = exc.code
        failure_capture_ref = exc.capture_ref
    except BoundedFinanceLoopError as exc:
        failure_phase = "local_finance_fragment_validation"
        failure_code = exc.code
        if submission is not None:
            failure_capture_ref = submission.response_capture_ref
    except CurrentResearchConsumerCanaryError as exc:
        failure_phase = "local_fragment_canary_validation"
        failure_code = exc.code
        if submission is not None:
            failure_capture_ref = submission.response_capture_ref
        elif analysis is not None:
            failure_capture_ref = analysis.response_capture_ref

    succeeded = bool(validated_fragment)
    status = (
        "completed_fragment_contract_valid_content_assessment_pending"
        if succeeded
        else "terminal_failed_no_retry"
    )
    full_body: dict[str, Any] = {
        "schema_version": FRAGMENT_ANALYSIS_SUBMISSION_RESULT_SCHEMA,
        "status": status,
        "recorded_at": _now(),
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "fragment_tool": SUBMIT_RESEARCH_THESIS_TOOL,
        "research_input_digest": research_input["research_input_digest"],
        "fragment_context": context,
        "analysis_messages_digest": canonical_digest(list(analysis_messages)),
        "submission_messages_digest": (
            canonical_digest(list(submission_messages))
            if submission_messages
            else ""
        ),
        "analysis_step": analysis.as_dict() if analysis is not None else {},
        "submission_step": (
            submission.as_dict() if submission is not None else {}
        ),
        "validated_fragment": validated_fragment,
        "failure_phase": failure_phase,
        "failure_code": failure_code,
        "failure_capture_ref": (
            _relative(failure_capture_ref) if failure_capture_ref else ""
        ),
        "execution": {
            "model_calls_attempted": model_calls_attempted,
            "maximum_model_calls": 2,
            "tool_calls_accepted": 1 if succeeded else 0,
            "retries": 0,
            "fallbacks": 0,
            "external_retrieval_calls": 0,
            "embedding_calls": 0,
            "protocol_switches": 0,
            "product_publication": False,
        },
        "authorship": {
            "analysis_draft_model_owned": analysis is not None,
            "submitted_fragment_model_owned": succeeded,
            "harness_generated_research_judgment": False,
            "harness_validated_and_bound_authority": succeeded,
            "analysis_draft_promoted_to_business_truth": False,
            "private_reasoning_persisted": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    full_path = private_root / "full_result.json"
    _write_new(full_path, full)
    public_body: dict[str, Any] = {
        "schema_version": FRAGMENT_ANALYSIS_SUBMISSION_RESULT_SCHEMA,
        "status": status,
        "recorded_at": full["recorded_at"],
        "authority_ref": full["authority_ref"],
        "authority_sha256": full["authority_sha256"],
        "implementation_commit": full["implementation_commit"],
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "fragment_tool": SUBMIT_RESEARCH_THESIS_TOOL,
        "research_input_digest": research_input["research_input_digest"],
        "fragment_context_digest": context["projection_digest"],
        "fragment_context_counts": {
            "claim_relation_options": len(context["claim_relation_options"]),
            "reviewed_evidence": len(context["reviewed_evidence"]),
            "numeric_facts": len(context["authoritative_numeric_facts"]),
            "numeric_relations": len(context["same_basis_numeric_relations"]),
            "qualitative_facts": len(
                context["source_bound_qualitative_facts"]
            ),
            "typed_gaps": len(context["typed_residual_gaps"]),
        },
        "analysis": {
            "attempted": analysis is not None,
            "finish_reason": analysis.finish_reason if analysis else "",
            "visible_chars": len(analysis.content) if analysis else 0,
            "content_digest": (
                canonical_digest({"content": analysis.content})
                if analysis
                else ""
            ),
            "usage": dict(analysis.usage) if analysis else {},
            "request_capture_ref": (
                _relative(analysis.request_capture_ref) if analysis else ""
            ),
            "response_capture_ref": (
                _relative(analysis.response_capture_ref) if analysis else ""
            ),
        },
        "submission": {
            "attempted": submission is not None,
            "finish_reason": submission.finish_reason if submission else "",
            "tool_call_count": len(submission.tool_calls) if submission else 0,
            "usage": dict(submission.usage) if submission else {},
            "request_capture_ref": (
                _relative(submission.request_capture_ref) if submission else ""
            ),
            "response_capture_ref": (
                _relative(submission.response_capture_ref) if submission else ""
            ),
        },
        "validated_fragment_digest": (
            canonical_digest(validated_fragment) if validated_fragment else ""
        ),
        "failure_phase": failure_phase,
        "failure_code": failure_code,
        "failure_capture_ref": full["failure_capture_ref"],
        "full_result_ref": _relative(full_path),
        "full_result_sha256": _sha(full_path),
        "execution": full["execution"],
        "acceptance": {
            "fragment_projection_contract_pass": True,
            "analysis_visible_output_pass": bool(analysis and analysis.content),
            "submission_tool_contract_pass": succeeded,
            "content_assessment_pending": succeeded,
            "fixed_pack_layer_one_acceptance": False,
            "dynamic_agentic_research_acceptance": False,
            "five_cell_live_authorized": False,
            "s3_product_acceptance": False,
            "qualified_human_acceptance": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    summary = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new(_resolve(str(output["public_result_ref"])), summary)
    return summary


def run_full_fragment_judgment(authority_path: Path) -> dict[str, Any]:
    authority = _json(authority_path)
    paths = validate_full_fragment_judgment_authority(
        authority,
        authority_path=authority_path,
    )
    research_input, cell, tool_by_name, _ = _full_fragment_judgment_artifacts(
        paths
    )
    analysis_profile = load_chat_completion_profile(
        _json(paths["analysis_profile_ref"])
    )
    submission_profile = load_chat_completion_profile(
        _json(paths["submission_profile_ref"])
    )
    validate_deepseek_ga_node_profile(
        analysis_profile,
        node_class="bounded_financial_analysis",
    )
    validate_deepseek_ga_node_profile(
        submission_profile,
        node_class="contract_submission",
    )
    output = authority["output_contract"]
    capture_root = _resolve(str(output["capture_root_ref"]))
    private_root = _resolve(str(output["private_output_root_ref"]))
    run_id = str(output["run_id"])
    accepted_fragments: dict[str, dict[str, Any]] = {}
    fragment_steps: list[dict[str, Any]] = []
    model_calls_attempted = 0
    failure_phase = ""
    failure_code = ""
    failure_fragment_tool = ""
    failure_capture_ref = ""
    judgment_output: dict[str, Any] = {}
    structured_deliverable: dict[str, Any] = {}

    try:
        for fragment_tool in MICRO_JUDGMENT_TOOL_NAMES:
            failure_fragment_tool = fragment_tool
            context = compile_finance_micro_fragment_context(
                research_input=research_input,
                cell_id="CELL::value_capture",
                tool_name=fragment_tool,
                accepted_fragments=accepted_fragments,
            )
            analysis_messages = compile_finance_micro_fragment_analysis_messages(
                context
            )
            attempt_ids = output["fragment_attempt_ids"][fragment_tool]
            step_record: dict[str, Any] = {
                "fragment_tool": fragment_tool,
                "fragment_context": context,
                "analysis_messages_digest": canonical_digest(
                    list(analysis_messages)
                ),
                "submission_messages_digest": "",
                "analysis_step": {},
                "submission_step": {},
                "validated_fragment": {},
                "validated_fragment_digest": "",
            }
            fragment_steps.append(step_record)
            model_calls_attempted += 1
            analysis = execute_chat_completion_exact_once(
                profile=analysis_profile,
                messages=analysis_messages,
                capture_root=capture_root,
                run_id=run_id,
                attempt_id=str(attempt_ids["analysis_attempt_id"]),
            )
            step_record["analysis_step"] = analysis.as_dict()
            if analysis.finish_reason == "length":
                raise CurrentResearchConsumerCanaryError(
                    "research_consumer_full_fragment_analysis_length_stop"
                )
            submission_messages = (
                compile_finance_micro_fragment_submission_messages(
                    fragment_context=context,
                    analysis_draft=analysis.content,
                )
            )
            step_record["submission_messages_digest"] = canonical_digest(
                list(submission_messages)
            )
            model_calls_attempted += 1
            submission = execute_chat_completion_tool_step_exact_once(
                profile=submission_profile,
                messages=submission_messages,
                tools=[tool_by_name[fragment_tool]],
                capture_root=capture_root,
                run_id=run_id,
                attempt_id=str(attempt_ids["submission_attempt_id"]),
                tool_choice=None,
            )
            step_record["submission_step"] = submission.as_dict()
            if submission.finish_reason == "length":
                raise CurrentResearchConsumerCanaryError(
                    "research_consumer_full_fragment_submission_length_stop"
                )
            if len(submission.tool_calls) != 1:
                raise CurrentResearchConsumerCanaryError(
                    "research_consumer_full_fragment_tool_call_count_invalid"
                )
            call = submission.tool_calls[0]
            function = call.get("function")
            if not (
                isinstance(function, Mapping)
                and function.get("name") == fragment_tool
            ):
                raise CurrentResearchConsumerCanaryError(
                    "research_consumer_full_fragment_tool_name_invalid"
                )
            try:
                arguments = json.loads(str(function.get("arguments") or ""))
            except json.JSONDecodeError as exc:
                raise CurrentResearchConsumerCanaryError(
                    "research_consumer_full_fragment_tool_arguments_invalid_json"
                ) from exc
            if not isinstance(arguments, Mapping):
                raise CurrentResearchConsumerCanaryError(
                    "research_consumer_full_fragment_tool_arguments_invalid"
                )
            validated_fragment = validate_finance_micro_judgment_fragment(
                tool_name=fragment_tool,
                arguments=arguments,
                research_input=research_input,
                cell_id="CELL::value_capture",
                thesis_fragment=accepted_fragments.get(
                    SUBMIT_RESEARCH_THESIS_TOOL
                ),
            )
            accepted_fragments[fragment_tool] = validated_fragment
            step_record["validated_fragment"] = validated_fragment
            step_record["validated_fragment_digest"] = canonical_digest(
                validated_fragment
            )
        normalized = compile_finance_micro_judgment_fragments(
            accepted_fragments,
            cell=cell,
        )
        judgment_output = {"cells": [normalized]}
        structured_deliverable = compile_current_research_deliverable(
            research_input=research_input,
            judgment_output=judgment_output,
            required_cell_ids=["CELL::value_capture"],
        )
        failure_fragment_tool = ""
    except ModelGatewayError as exc:
        failure_phase = "provider_transport_or_response"
        failure_code = exc.code
        failure_capture_ref = exc.capture_ref
    except BoundedFinanceLoopError as exc:
        failure_phase = "local_finance_fragment_or_terminal_validation"
        failure_code = exc.code
    except CurrentResearchConsumerError as exc:
        failure_phase = "local_terminal_judgment_validation"
        failure_code = exc.code
    except CurrentResearchConsumerCanaryError as exc:
        failure_phase = "local_full_fragment_canary_validation"
        failure_code = exc.code

    if failure_code and not failure_capture_ref and fragment_steps:
        latest_step = fragment_steps[-1]
        for step_key in ("submission_step", "analysis_step"):
            capture_ref = str(
                latest_step.get(step_key, {}).get("response_capture_ref") or ""
            )
            if capture_ref:
                failure_capture_ref = capture_ref
                break

    succeeded = bool(structured_deliverable)
    status = (
        "completed_full_fragment_judgment_contract_valid_content_assessment_pending"
        if succeeded
        else "terminal_failed_no_retry"
    )
    full_body: dict[str, Any] = {
        "schema_version": FULL_FRAGMENT_JUDGMENT_RESULT_SCHEMA,
        "status": status,
        "recorded_at": _now(),
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "ordered_fragment_tools": list(MICRO_JUDGMENT_TOOL_NAMES),
        "research_input_digest": research_input["research_input_digest"],
        "fragment_steps": fragment_steps,
        "accepted_fragments": accepted_fragments,
        "judgment_output": judgment_output,
        "structured_deliverable": structured_deliverable,
        "failure_phase": failure_phase,
        "failure_code": failure_code,
        "failure_fragment_tool": failure_fragment_tool,
        "failure_capture_ref": (
            _relative(failure_capture_ref) if failure_capture_ref else ""
        ),
        "execution": {
            "model_calls_attempted": model_calls_attempted,
            "maximum_model_calls": 6,
            "tool_calls_accepted": len(accepted_fragments),
            "retries": 0,
            "fallbacks": 0,
            "external_retrieval_calls": 0,
            "embedding_calls": 0,
            "protocol_switches": 0,
            "product_publication": False,
        },
        "authorship": {
            "all_analysis_drafts_model_owned": bool(fragment_steps),
            "all_submitted_fragments_model_owned": succeeded,
            "harness_generated_research_judgment": False,
            "harness_validated_and_aggregated_authority": succeeded,
            "analysis_draft_promoted_to_business_truth": False,
            "private_reasoning_persisted": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    full_path = private_root / "full_result.json"
    _write_new(full_path, full)
    public_steps = []
    for row in fragment_steps:
        analysis_step = row["analysis_step"]
        submission_step = row["submission_step"]
        public_steps.append(
            {
                "fragment_tool": row["fragment_tool"],
                "fragment_context_digest": row["fragment_context"][
                    "projection_digest"
                ],
                "analysis_messages_digest": row["analysis_messages_digest"],
                "submission_messages_digest": row[
                    "submission_messages_digest"
                ],
                "analysis": {
                    "attempted": bool(analysis_step),
                    "finish_reason": analysis_step.get("finish_reason", ""),
                    "visible_chars": len(analysis_step.get("content", "")),
                    "content_digest": (
                        canonical_digest(
                            {"content": analysis_step.get("content", "")}
                        )
                        if analysis_step
                        else ""
                    ),
                    "usage": analysis_step.get("usage", {}),
                    "request_capture_ref": (
                        _relative(analysis_step["request_capture_ref"])
                        if analysis_step
                        else ""
                    ),
                    "response_capture_ref": (
                        _relative(analysis_step["response_capture_ref"])
                        if analysis_step
                        else ""
                    ),
                },
                "submission": {
                    "attempted": bool(submission_step),
                    "finish_reason": submission_step.get("finish_reason", ""),
                    "tool_call_count": len(
                        submission_step.get("tool_calls", ())
                    ),
                    "usage": submission_step.get("usage", {}),
                    "request_capture_ref": (
                        _relative(submission_step["request_capture_ref"])
                        if submission_step
                        else ""
                    ),
                    "response_capture_ref": (
                        _relative(submission_step["response_capture_ref"])
                        if submission_step
                        else ""
                    ),
                },
                "validated_fragment_digest": row[
                    "validated_fragment_digest"
                ],
            }
        )
    public_body: dict[str, Any] = {
        "schema_version": FULL_FRAGMENT_JUDGMENT_RESULT_SCHEMA,
        "status": status,
        "recorded_at": full["recorded_at"],
        "authority_ref": full["authority_ref"],
        "authority_sha256": full["authority_sha256"],
        "implementation_commit": full["implementation_commit"],
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "ordered_fragment_tools": list(MICRO_JUDGMENT_TOOL_NAMES),
        "research_input_digest": research_input["research_input_digest"],
        "fragment_steps": public_steps,
        "judgment_output_digest": (
            canonical_digest(judgment_output) if judgment_output else ""
        ),
        "deliverable_digest": (
            str(structured_deliverable.get("deliverable_digest") or "")
        ),
        "failure_phase": failure_phase,
        "failure_code": failure_code,
        "failure_fragment_tool": failure_fragment_tool,
        "failure_capture_ref": full["failure_capture_ref"],
        "full_result_ref": _relative(full_path),
        "full_result_sha256": _sha(full_path),
        "execution": full["execution"],
        "acceptance": {
            "full_three_fragment_contract_pass": succeeded,
            "terminal_judgment_contract_pass": succeeded,
            "content_assessment_pending": succeeded,
            "fixed_pack_layer_one_acceptance": False,
            "dynamic_agentic_research_acceptance": False,
            "five_cell_live_authorized": False,
            "s3_product_acceptance": False,
            "qualified_human_acceptance": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    summary = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new(_resolve(str(output["public_result_ref"])), summary)
    return summary


def run_failed_fragment_submission_successor(
    authority_path: Path,
) -> dict[str, Any]:
    authority = _json(authority_path)
    paths = validate_failed_fragment_submission_successor_authority(
        authority,
        authority_path=authority_path,
    )
    (
        research_input,
        cell,
        counter_tool,
        accepted_fragments,
        context,
        submission_messages,
        fixture,
    ) = _failed_fragment_submission_successor_artifacts(paths)
    submission_profile = load_chat_completion_profile(
        _json(paths["submission_profile_ref"])
    )
    validate_deepseek_ga_node_profile(
        submission_profile,
        node_class="contract_submission_non_thinking",
    )
    output = authority["output_contract"]
    capture_root = _resolve(str(output["capture_root_ref"]))
    private_root = _resolve(str(output["private_output_root_ref"]))
    run_id = str(output["run_id"])
    attempt_id = str(output["attempt_id"])
    submission_step: dict[str, Any] = {}
    validated_counter: dict[str, Any] = {}
    judgment_output: dict[str, Any] = {}
    structured_deliverable: dict[str, Any] = {}
    failure_phase = ""
    failure_code = ""
    failure_capture_ref = ""
    model_call_attempted = False

    try:
        model_call_attempted = True
        submission = execute_chat_completion_tool_step_exact_once(
            profile=submission_profile,
            messages=submission_messages,
            tools=[counter_tool],
            capture_root=capture_root,
            run_id=run_id,
            attempt_id=attempt_id,
            tool_choice=None,
        )
        submission_step = submission.as_dict()
        if submission.finish_reason == "length":
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_submission_successor_length_stop"
            )
        if len(submission.tool_calls) != 1:
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_submission_successor_tool_call_count_invalid"
            )
        call = submission.tool_calls[0]
        function = call.get("function")
        if not (
            isinstance(function, Mapping)
            and function.get("name")
            == SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL
        ):
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_submission_successor_tool_name_invalid"
            )
        try:
            arguments = json.loads(str(function.get("arguments") or ""))
        except json.JSONDecodeError as exc:
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_submission_successor_arguments_invalid_json"
            ) from exc
        if not isinstance(arguments, Mapping):
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_submission_successor_arguments_invalid"
            )
        validated_counter = validate_finance_micro_judgment_fragment(
            tool_name=SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL,
            arguments=arguments,
            research_input=research_input,
            cell_id="CELL::value_capture",
            thesis_fragment=accepted_fragments[SUBMIT_RESEARCH_THESIS_TOOL],
        )
        accepted_fragments[SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL] = (
            validated_counter
        )
        normalized = compile_finance_micro_judgment_fragments(
            accepted_fragments,
            cell=cell,
        )
        judgment_output = {"cells": [normalized]}
        structured_deliverable = compile_current_research_deliverable(
            research_input=research_input,
            judgment_output=judgment_output,
            required_cell_ids=["CELL::value_capture"],
        )
    except ModelGatewayError as exc:
        failure_phase = "provider_transport_or_response"
        failure_code = exc.code
        failure_capture_ref = exc.capture_ref
    except BoundedFinanceLoopError as exc:
        failure_phase = "local_finance_fragment_or_terminal_validation"
        failure_code = exc.code
    except CurrentResearchConsumerError as exc:
        failure_phase = "local_terminal_judgment_validation"
        failure_code = exc.code
    except CurrentResearchConsumerCanaryError as exc:
        failure_phase = "local_failed_fragment_successor_validation"
        failure_code = exc.code

    if failure_code and not failure_capture_ref and submission_step:
        failure_capture_ref = str(
            submission_step.get("response_capture_ref") or ""
        )
    succeeded = bool(structured_deliverable)
    status = (
        "completed_failed_fragment_submission_successor_contract_valid_"
        "content_assessment_pending"
        if succeeded
        else "terminal_failed_no_retry"
    )
    predecessor_result = _json(paths["prior_full_fragment_result_ref"])
    full_body: dict[str, Any] = {
        "schema_version": FRAGMENT_SUBMISSION_SUCCESSOR_RESULT_SCHEMA,
        "status": status,
        "recorded_at": _now(),
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "failed_fragment_tool": SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL,
        "research_input_digest": research_input["research_input_digest"],
        "counter_fragment_context": context,
        "counter_submission_messages_digest": canonical_digest(
            list(submission_messages)
        ),
        "predecessor": {
            "result_ref": _relative(paths["prior_full_fragment_result_ref"]),
            "result_sha256": _sha(paths["prior_full_fragment_result_ref"]),
            "result_digest": predecessor_result["result_digest"],
            "run_id": fixture["source_run_id"],
            "successful_model_calls_reused": 5,
            "accepted_fragment_digests": fixture[
                "accepted_fragment_digests"
            ],
            "counter_analysis_content_digest": fixture[
                "counter_analysis_content_digest"
            ],
        },
        "successor_submission_step": submission_step,
        "validated_counter_fragment": validated_counter,
        "validated_counter_fragment_digest": (
            canonical_digest(validated_counter) if validated_counter else ""
        ),
        "accepted_fragments": accepted_fragments,
        "judgment_output": judgment_output,
        "structured_deliverable": structured_deliverable,
        "failure_phase": failure_phase,
        "failure_code": failure_code,
        "failure_capture_ref": (
            _relative(failure_capture_ref) if failure_capture_ref else ""
        ),
        "execution": {
            "fresh_model_calls_attempted": int(model_call_attempted),
            "maximum_fresh_model_calls": 1,
            "successful_predecessor_model_calls_reused": 5,
            "logical_chain_model_calls": 6 if model_call_attempted else 5,
            "fresh_tool_calls_accepted": int(bool(validated_counter)),
            "total_fragments_accepted": len(accepted_fragments),
            "retries": 0,
            "fallbacks": 0,
            "external_retrieval_calls": 0,
            "embedding_calls": 0,
            "protocol_switches": 0,
            "product_publication": False,
        },
        "authorship": {
            "predecessor_fragments_model_owned": True,
            "counter_analysis_draft_model_owned": True,
            "counter_submission_model_owned": succeeded,
            "harness_generated_research_judgment": False,
            "harness_validated_and_aggregated_authority": succeeded,
            "analysis_draft_promoted_to_business_truth": False,
            "private_reasoning_persisted": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    full_path = private_root / "full_result.json"
    _write_new(full_path, full)
    public_submission = {
        "attempted": bool(submission_step),
        "finish_reason": submission_step.get("finish_reason", ""),
        "tool_call_count": len(submission_step.get("tool_calls", ())),
        "visible_chars": len(submission_step.get("content", "")),
        "usage": submission_step.get("usage", {}),
        "request_capture_ref": (
            _relative(submission_step["request_capture_ref"])
            if submission_step
            else ""
        ),
        "response_capture_ref": (
            _relative(submission_step["response_capture_ref"])
            if submission_step
            else ""
        ),
    }
    public_body: dict[str, Any] = {
        "schema_version": FRAGMENT_SUBMISSION_SUCCESSOR_RESULT_SCHEMA,
        "status": status,
        "recorded_at": full["recorded_at"],
        "authority_ref": full["authority_ref"],
        "authority_sha256": full["authority_sha256"],
        "implementation_commit": full["implementation_commit"],
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "failed_fragment_tool": SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL,
        "research_input_digest": research_input["research_input_digest"],
        "predecessor_result_digest": predecessor_result["result_digest"],
        "counter_fragment_context_digest": context["projection_digest"],
        "counter_submission_messages_digest": full[
            "counter_submission_messages_digest"
        ],
        "successor_submission": public_submission,
        "validated_counter_fragment_digest": full[
            "validated_counter_fragment_digest"
        ],
        "judgment_output_digest": (
            canonical_digest(judgment_output) if judgment_output else ""
        ),
        "deliverable_digest": str(
            structured_deliverable.get("deliverable_digest") or ""
        ),
        "failure_phase": failure_phase,
        "failure_code": failure_code,
        "failure_capture_ref": full["failure_capture_ref"],
        "full_result_ref": _relative(full_path),
        "full_result_sha256": _sha(full_path),
        "execution": full["execution"],
        "acceptance": {
            "failed_node_only_successor_pass": succeeded,
            "predecessor_successful_nodes_reused": True,
            "full_three_fragment_contract_pass": succeeded,
            "terminal_judgment_contract_pass": succeeded,
            "content_assessment_pending": succeeded,
            "fixed_pack_layer_one_acceptance": False,
            "dynamic_agentic_research_acceptance": False,
            "five_cell_live_authorized": False,
            "s3_product_acceptance": False,
            "qualified_human_acceptance": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    summary = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new(_resolve(str(output["public_result_ref"])), summary)
    return summary


def run_failed_fragment_validation_repair(
    authority_path: Path,
) -> dict[str, Any]:
    authority = _json(authority_path)
    paths = validate_failed_fragment_validation_repair_authority(
        authority,
        authority_path=authority_path,
    )
    (
        research_input,
        cell,
        counter_tool,
        accepted_fragments,
        repair,
        _,
        rejected_fixture,
    ) = _failed_fragment_validation_repair_artifacts(paths)
    profile = load_chat_completion_profile(_json(paths["submission_profile_ref"]))
    validate_deepseek_ga_node_profile(
        profile,
        node_class="contract_submission_non_thinking",
    )
    output = authority["output_contract"]
    capture_root = _resolve(str(output["capture_root_ref"]))
    private_root = _resolve(str(output["private_output_root_ref"]))
    run_id = str(output["run_id"])
    attempt_id = str(output["attempt_id"])
    repair_step: dict[str, Any] = {}
    validated_repair: dict[str, Any] = {}
    judgment_output: dict[str, Any] = {}
    structured_deliverable: dict[str, Any] = {}
    failure_phase = ""
    failure_code = ""
    failure_capture_ref = ""
    model_call_attempted = False

    try:
        model_call_attempted = True
        submission = execute_chat_completion_tool_step_exact_once(
            profile=profile,
            messages=repair["repair_messages"],
            tools=[counter_tool],
            capture_root=capture_root,
            run_id=run_id,
            attempt_id=attempt_id,
            tool_choice=None,
        )
        repair_step = submission.as_dict()
        if submission.finish_reason == "length":
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_validation_repair_length_stop"
            )
        if len(submission.tool_calls) != 1:
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_validation_repair_tool_call_count_invalid"
            )
        call = submission.tool_calls[0]
        function = call.get("function")
        if not (
            isinstance(function, Mapping)
            and function.get("name")
            == SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL
        ):
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_validation_repair_tool_name_invalid"
            )
        try:
            arguments = json.loads(str(function.get("arguments") or ""))
        except json.JSONDecodeError as exc:
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_validation_repair_arguments_invalid_json"
            ) from exc
        if not isinstance(arguments, Mapping):
            raise CurrentResearchConsumerCanaryError(
                "research_consumer_validation_repair_arguments_invalid"
            )
        validated_repair = validate_finance_micro_judgment_fragment(
            tool_name=SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL,
            arguments=arguments,
            research_input=research_input,
            cell_id="CELL::value_capture",
            thesis_fragment=accepted_fragments[SUBMIT_RESEARCH_THESIS_TOOL],
        )
        accepted_fragments[SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL] = (
            validated_repair
        )
        terminal = compile_finance_micro_judgment_fragments(
            accepted_fragments,
            cell=cell,
        )
        judgment_output = {"cells": [terminal]}
        structured_deliverable = compile_current_research_deliverable(
            research_input=research_input,
            judgment_output=judgment_output,
            required_cell_ids=["CELL::value_capture"],
        )
    except ModelGatewayError as exc:
        failure_phase = "provider_transport_or_response"
        failure_code = exc.code
        failure_capture_ref = exc.capture_ref
    except BoundedFinanceLoopError as exc:
        failure_phase = "local_finance_fragment_or_terminal_validation"
        failure_code = exc.code
    except CurrentResearchConsumerError as exc:
        failure_phase = "local_terminal_judgment_validation"
        failure_code = exc.code
    except CurrentResearchConsumerCanaryError as exc:
        failure_phase = "local_failed_fragment_validation_repair"
        failure_code = exc.code

    if failure_code and not failure_capture_ref and repair_step:
        failure_capture_ref = str(repair_step.get("response_capture_ref") or "")
    succeeded = bool(structured_deliverable)
    status = (
        "completed_failed_fragment_validation_repair_contract_valid_"
        "content_assessment_pending"
        if succeeded
        else "terminal_failed_no_retry"
    )
    prior_result = _json(paths["prior_live_result_ref"])
    full_body: dict[str, Any] = {
        "schema_version": FRAGMENT_VALIDATION_REPAIR_RESULT_SCHEMA,
        "status": status,
        "recorded_at": _now(),
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "repaired_fragment_tool": SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL,
        "research_input_digest": research_input["research_input_digest"],
        "predecessor": {
            "result_ref": _relative(paths["prior_live_result_ref"]),
            "result_sha256": _sha(paths["prior_live_result_ref"]),
            "result_digest": prior_result["result_digest"],
            "terminal_failure_code": prior_result["failure_code"],
            "rejected_fragment_digest": rejected_fixture[
                "rejected_fragment_digest"
            ],
            "successful_model_calls_reused": 6,
        },
        "repair_feedback": repair["repair_feedback"],
        "repair_messages_digest": repair["repair_messages_digest"],
        "repair_step": repair_step,
        "validated_repair_fragment": validated_repair,
        "validated_repair_fragment_digest": (
            canonical_digest(validated_repair) if validated_repair else ""
        ),
        "accepted_fragments": accepted_fragments,
        "judgment_output": judgment_output,
        "structured_deliverable": structured_deliverable,
        "failure_phase": failure_phase,
        "failure_code": failure_code,
        "failure_capture_ref": (
            _relative(failure_capture_ref) if failure_capture_ref else ""
        ),
        "execution": {
            "fresh_model_calls_attempted": int(model_call_attempted),
            "maximum_fresh_model_calls": 1,
            "successful_predecessor_model_calls_reused": 6,
            "logical_chain_model_calls": 7 if model_call_attempted else 6,
            "fresh_tool_calls_accepted": int(bool(validated_repair)),
            "total_fragments_accepted": len(accepted_fragments),
            "repair_turns_used": int(model_call_attempted),
            "maximum_repair_turns": 1,
            "retries": 0,
            "fallbacks": 0,
            "external_retrieval_calls": 0,
            "embedding_calls": 0,
            "protocol_switches": 0,
            "product_publication": False,
        },
        "authorship": {
            "predecessor_fragments_model_owned": True,
            "rejected_fragment_model_owned_but_not_promoted": True,
            "repair_fragment_model_owned": succeeded,
            "harness_generated_research_judgment": False,
            "harness_validated_and_aggregated_authority": succeeded,
            "private_reasoning_persisted": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    full_path = private_root / "full_result.json"
    _write_new(full_path, full)
    public_step = {
        "attempted": bool(repair_step),
        "finish_reason": repair_step.get("finish_reason", ""),
        "tool_call_count": len(repair_step.get("tool_calls", ())),
        "visible_chars": len(repair_step.get("content", "")),
        "usage": repair_step.get("usage", {}),
        "request_capture_ref": (
            _relative(repair_step["request_capture_ref"])
            if repair_step
            else ""
        ),
        "response_capture_ref": (
            _relative(repair_step["response_capture_ref"])
            if repair_step
            else ""
        ),
    }
    public_body: dict[str, Any] = {
        "schema_version": FRAGMENT_VALIDATION_REPAIR_RESULT_SCHEMA,
        "status": status,
        "recorded_at": full["recorded_at"],
        "authority_ref": full["authority_ref"],
        "authority_sha256": full["authority_sha256"],
        "implementation_commit": full["implementation_commit"],
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "repaired_fragment_tool": SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL,
        "research_input_digest": research_input["research_input_digest"],
        "predecessor_result_digest": prior_result["result_digest"],
        "rejected_fragment_digest": rejected_fixture[
            "rejected_fragment_digest"
        ],
        "repair_feedback_digest": repair["repair_feedback_digest"],
        "repair_messages_digest": repair["repair_messages_digest"],
        "repair_submission": public_step,
        "validated_repair_fragment_digest": full[
            "validated_repair_fragment_digest"
        ],
        "judgment_output_digest": (
            canonical_digest(judgment_output) if judgment_output else ""
        ),
        "deliverable_digest": str(
            structured_deliverable.get("deliverable_digest") or ""
        ),
        "failure_phase": failure_phase,
        "failure_code": failure_code,
        "failure_capture_ref": full["failure_capture_ref"],
        "full_result_ref": _relative(full_path),
        "full_result_sha256": _sha(full_path),
        "execution": full["execution"],
        "acceptance": {
            "typed_validation_feedback_repair_pass": succeeded,
            "predecessor_successful_nodes_reused": True,
            "rejected_fragment_not_promoted": True,
            "causal_guard_preserved": True,
            "full_three_fragment_contract_pass": succeeded,
            "terminal_judgment_contract_pass": succeeded,
            "content_assessment_pending": succeeded,
            "fixed_pack_layer_one_acceptance": False,
            "dynamic_agentic_research_acceptance": False,
            "five_cell_live_authorized": False,
            "s3_product_acceptance": False,
            "qualified_human_acceptance": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    summary = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new(_resolve(str(output["public_result_ref"])), summary)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", required=True)
    args = parser.parse_args(argv)
    authority_path = _resolve(args.authority)
    authority = _json(authority_path)
    if authority.get("schema_version") == FRAGMENT_VALIDATION_REPAIR_AUTHORITY_SCHEMA:
        result = run_failed_fragment_validation_repair(authority_path)
    elif (
        authority.get("schema_version")
        == FRAGMENT_SUBMISSION_SUCCESSOR_AUTHORITY_SCHEMA
    ):
        result = run_failed_fragment_submission_successor(authority_path)
    elif authority.get("schema_version") in {
        FULL_FRAGMENT_JUDGMENT_AUTHORITY_SCHEMA,
        FULL_FRAGMENT_CLAIM_LOCAL_AUTHORITY_SCHEMA,
        FULL_FRAGMENT_CAUSAL_POLARITY_AUTHORITY_SCHEMA,
        FULL_FRAGMENT_WWC_ROUTE_IDENTIFIER_AUTHORITY_SCHEMA,
    }:
        result = run_full_fragment_judgment(authority_path)
    elif (
        authority.get("schema_version")
        == FRAGMENT_ANALYSIS_SUBMISSION_AUTHORITY_SCHEMA
    ):
        result = run_fragment_analysis_submission(authority_path)
    elif authority.get("schema_version") == PAIRED_AUTHORITY_SCHEMA:
        result = run_paired(authority_path)
    elif authority.get("schema_version") in {
        TOOL_LOOP_AUTHORITY_SCHEMA,
        MICRO_TOOL_LOOP_AUTHORITY_SCHEMA,
    }:
        result = run_tool_loop(authority_path)
    else:
        result = run(authority_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return (
        0
        if result["status"]
        in {
            "completed_contract_valid",
            "paired_contract_valid_content_assessment_pending",
            "completed_contract_valid_content_assessment_pending",
            "completed_fragment_contract_valid_content_assessment_pending",
            "completed_full_fragment_judgment_contract_valid_content_assessment_pending",
            "completed_failed_fragment_submission_successor_contract_valid_content_assessment_pending",
            "completed_failed_fragment_validation_repair_contract_valid_content_assessment_pending",
        }
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
