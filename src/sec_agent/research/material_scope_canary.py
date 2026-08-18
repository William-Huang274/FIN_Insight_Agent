from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence

from retrieval.contracts import load_evidence_request, load_financial_research_kernel
from sec_agent.providers.chat_completions import (
    ChatCompletionResult,
    ModelGatewayError,
    execute_chat_completion_exact_once,
    load_chat_completion_profile,
)
from sec_agent.research.material_scope import (
    ResearchMaterialScopeError,
    compile_research_material_scope,
    parse_research_material_scope_output,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest


MATERIAL_SCOPE_CANARY_INPUT_SCHEMA = (
    "fin_ia_s3_material_scope_canary_input_v1_0"
)
MATERIAL_SCOPE_CANARY_AUTHORITY_SCHEMA = (
    "fin_ia_s3_material_scope_canary_authority_v1_0"
)
MATERIAL_SCOPE_CANARY_RESULT_SCHEMA = (
    "fin_ia_s3_material_scope_canary_result_v1_0"
)
MATERIAL_SCOPE_CANARY_RUN_SCOPE = (
    "one_DELL_candidate_blind_natural_material_scope_canary"
)
MATERIAL_SCOPE_CANARY_AUTHORITY_STATUS = (
    "signed_one_DELL_candidate_blind_material_scope_canary_exact_once"
)

_FORBIDDEN_MODEL_VISIBLE_KEYS = frozenset(
    {
        "candidate_id",
        "candidate_ids",
        "object_id",
        "object_ids",
        "qrel",
        "qrels",
        "reference",
        "references",
        "source_url",
        "url",
        "answer_url",
        "rank",
        "score",
    }
)


class MaterialScopeCanaryError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise MaterialScopeCanaryError(code)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "material_scope_canary_json_object_required")
    return value


def repo_path(root: Path, ref: str) -> Path:
    _require(bool(ref) and not Path(ref).is_absolute(), "material_scope_canary_ref_invalid")
    path = (root / ref).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise MaterialScopeCanaryError(
            "material_scope_canary_ref_outside_repository"
        ) from exc
    _require(path.is_file(), f"material_scope_canary_ref_missing:{ref}")
    return path


def relative_ref(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise MaterialScopeCanaryError(
            "material_scope_canary_output_outside_repository"
        ) from exc


def write_new_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
    except FileExistsError as exc:
        raise MaterialScopeCanaryError(
            "material_scope_canary_exact_once_output_consumed"
        ) from exc


def _contains_forbidden_model_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key).casefold() in _FORBIDDEN_MODEL_VISIBLE_KEYS
            or _contains_forbidden_model_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_model_key(item) for item in value)
    return False


def build_material_scope_canary_input(
    *,
    case_key: str,
    product_projection: Mapping[str, Any],
    model_visible_messages: Sequence[Mapping[str, str]],
    source_bindings: Mapping[str, Mapping[str, Any]],
    prepared_from_commit: str,
) -> dict[str, Any]:
    """Freeze one candidate-blind scope input from the current product seam."""

    _require(case_key == "DELL", "material_scope_canary_case_invalid")
    material_scope = product_projection.get("material_scope")
    compiled_plan = product_projection.get("compiled_plan")
    summary = product_projection.get("summary")
    _require(
        isinstance(material_scope, Mapping)
        and isinstance(compiled_plan, Mapping)
        and isinstance(summary, Mapping),
        "material_scope_canary_product_projection_invalid",
    )
    required_ids = list(material_scope.get("required_request_ids") or ())
    requests = list(compiled_plan.get("evidence_requests") or ())
    request_ids = [str(row.get("request_id") or "") for row in requests]
    _require(
        material_scope.get("mode") == "explicit_scope_required"
        and bool(required_ids)
        and set(required_ids).issubset(request_ids)
        and len(required_ids) == int(summary.get("material_scope_required_request_count") or 0),
        "material_scope_canary_scope_not_required",
    )
    normalized_messages = [
        {"role": str(row.get("role") or ""), "content": str(row.get("content") or "")}
        for row in model_visible_messages
    ]
    _require(
        len(normalized_messages) == 2
        and [row["role"] for row in normalized_messages] == ["system", "user"]
        and all(row["content"] for row in normalized_messages),
        "material_scope_canary_messages_invalid",
    )
    visible = json.loads(normalized_messages[1]["content"])
    _require(
        isinstance(visible, Mapping)
        and not _contains_forbidden_model_key(visible)
        and visible.get("research_plan_digest") == compiled_plan.get("plan_digest")
        and [row.get("request_id") for row in visible.get("requests") or ()]
        == required_ids,
        "material_scope_canary_model_view_invalid",
    )
    _require(
        bool(re.fullmatch(r"[0-9a-f]{40}", prepared_from_commit)),
        "material_scope_canary_prepared_commit_invalid",
    )
    _require(
        bool(source_bindings)
        and all(
            isinstance(row, Mapping)
            and set(row) == {"ref", "sha256"}
            and bool(row.get("ref"))
            and bool(re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256") or "")))
            for row in source_bindings.values()
        ),
        "material_scope_canary_source_bindings_invalid",
    )
    request_diagnostics = []
    for result in product_projection.get("request_results") or ():
        hybrid = result.get("hybrid_object_retrieval") or {}
        hybrid_summary = hybrid.get("summary") or {}
        request_row = result.get("request") or {}
        request_diagnostics.append(
            {
                "request_id": (
                    result.get("request_id") or request_row.get("request_id")
                ),
                "hybrid_selected_candidate_count": hybrid_summary.get(
                    "selected_count", 0
                ),
                "material_scope_ready": hybrid_summary.get(
                    "material_scope_ready", False
                ),
                "material_set_complete": hybrid_summary.get(
                    "material_set_complete", False
                ),
                "hard_reserved_material_candidate_count": hybrid_summary.get(
                    "reserved_material_candidate_count", 0
                ),
                "material_review_order_candidate_count": hybrid_summary.get(
                    "material_review_order_candidate_count", 0
                ),
            }
        )
    body = {
        "schema_version": MATERIAL_SCOPE_CANARY_INPUT_SCHEMA,
        "status": "zero_call_current_product_material_scope_input_ready",
        "recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "prepared_from_commit": prepared_from_commit,
        "case_key": case_key,
        "research_plan_digest": compiled_plan["plan_digest"],
        "product_projection_digest": product_projection["projection_digest"],
        "required_request_ids": required_ids,
        "evidence_requests": requests,
        "model_visible_messages": normalized_messages,
        "model_visible_messages_digest": canonical_digest(normalized_messages),
        "product_diagnostic": {
            "proposed_atom_count": summary.get("proposed_atom_count"),
            "selected_atom_count": summary.get("selected_atom_count"),
            "deferred_atom_count": summary.get("deferred_atom_count"),
            "evidence_request_count": summary.get("evidence_request_count"),
            "nonempty_lane_count": summary.get("nonempty_lane_count"),
            "typed_fact_request_count": summary.get("typed_fact_request_count"),
            "typed_fact_resolved_count": summary.get("typed_fact_resolved_count"),
            "typed_fact_gap_count": summary.get("typed_fact_gap_count"),
            "numeric_fact_count": summary.get("numeric_fact_count"),
            "hybrid_selected_candidate_count": summary.get(
                "hybrid_selected_candidate_count"
            ),
            "material_scope_required_request_count": summary.get(
                "material_scope_required_request_count"
            ),
            "material_scope_ready_request_count": summary.get(
                "material_scope_ready_request_count"
            ),
            "local_embedding_inference_batches": summary.get(
                "local_embedding_inference_batches"
            ),
            "network_calls": summary.get("network_calls"),
            "model_calls": summary.get("model_calls"),
            "request_diagnostics": request_diagnostics,
        },
        "source_bindings": {
            str(name): dict(row) for name, row in source_bindings.items()
        },
        "authority": {
            "candidate_or_reference_inputs_read": False,
            "qrel_or_hidden_inputs_read": False,
            "network_calls": 0,
            "generation_model_calls": 0,
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
            "s1_qualification_claimed": False,
        },
        "known_boundary": (
            "This input freezes only the request-visible natural material-scope "
            "node. Product candidate diagnostics are retained for audit but are "
            "not included in the two model-visible messages."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def validate_material_scope_canary_input(payload: Mapping[str, Any]) -> None:
    expected = {
        "schema_version",
        "status",
        "recorded_at",
        "prepared_from_commit",
        "case_key",
        "research_plan_digest",
        "product_projection_digest",
        "required_request_ids",
        "evidence_requests",
        "model_visible_messages",
        "model_visible_messages_digest",
        "product_diagnostic",
        "source_bindings",
        "authority",
        "known_boundary",
        "result_digest",
    }
    _require(
        set(payload) == expected
        and payload.get("schema_version") == MATERIAL_SCOPE_CANARY_INPUT_SCHEMA
        and payload.get("status")
        == "zero_call_current_product_material_scope_input_ready"
        and payload.get("case_key") == "DELL",
        "material_scope_canary_input_contract_invalid",
    )
    body = {key: value for key, value in payload.items() if key != "result_digest"}
    _require(
        payload.get("result_digest") == canonical_digest(body),
        "material_scope_canary_input_digest_invalid",
    )
    messages = payload.get("model_visible_messages")
    _require(
        isinstance(messages, list)
        and payload.get("model_visible_messages_digest") == canonical_digest(messages),
        "material_scope_canary_messages_digest_invalid",
    )
    visible = json.loads(messages[1]["content"])
    required_ids = list(payload.get("required_request_ids") or ())
    request_ids = [
        str(row.get("request_id") or "")
        for row in payload.get("evidence_requests") or ()
    ]
    authority = payload.get("authority") or {}
    _require(
        visible.get("research_plan_digest") == payload.get("research_plan_digest")
        and [row.get("request_id") for row in visible.get("requests") or ()]
        == required_ids
        and set(required_ids).issubset(request_ids)
        and not _contains_forbidden_model_key(visible)
        and authority.get("candidate_or_reference_inputs_read") is False
        and authority.get("qrel_or_hidden_inputs_read") is False
        and authority.get("network_calls") == 0
        and authority.get("generation_model_calls") == 0
        and authority.get("candidate_is_not_evidence") is True
        and authority.get("numeric_authority") is False
        and authority.get("s1_qualification_claimed") is False,
        "material_scope_canary_input_authority_invalid",
    )


def _bound_json(
    root: Path,
    bound: Mapping[str, Any],
    ref_field: str,
    sha_field: str,
) -> tuple[Path, dict[str, Any]]:
    path = repo_path(root, str(bound.get(ref_field) or ""))
    _require(
        file_sha256(path) == bound.get(sha_field),
        f"material_scope_canary_bound_sha_drift:{ref_field}",
    )
    return path, load_json(path)


def validate_material_scope_canary_authority(
    authority: Mapping[str, Any], *, root: Path
) -> dict[str, Any]:
    expected_fields = {
        "schema_version",
        "authority_id",
        "status",
        "issued_at",
        "implementation_commit",
        "case_key",
        "cell_id",
        "run_scope_id",
        "evidence_mode",
        "credential_presence_required",
        "chat_live_authorized",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_network_authorized",
        "candidate_or_reference_visibility_authorized",
        "candidate_promotion_authorized",
        "numeric_authority_authorized",
        "product_publication_authorized",
        "s1_acceptance_authorized",
        "bound_inputs",
        "execution_budget",
        "output_contract",
        "known_boundary",
    }
    _require(
        set(authority) == expected_fields
        and authority.get("schema_version") == MATERIAL_SCOPE_CANARY_AUTHORITY_SCHEMA
        and authority.get("status") == MATERIAL_SCOPE_CANARY_AUTHORITY_STATUS
        and authority.get("case_key") == "DELL"
        and authority.get("cell_id") == "MATERIAL_SCOPE"
        and authority.get("run_scope_id") == MATERIAL_SCOPE_CANARY_RUN_SCOPE
        and authority.get("evidence_mode")
        == "request_visible_scope_only_no_candidates_no_evidence"
        and authority.get("credential_presence_required") is True
        and authority.get("chat_live_authorized") is True
        and all(
            authority.get(field) is False
            for field in (
                "responses_live_authorized",
                "anthropic_live_authorized",
                "external_network_authorized",
                "candidate_or_reference_visibility_authorized",
                "candidate_promotion_authorized",
                "numeric_authority_authorized",
                "product_publication_authorized",
                "s1_acceptance_authorized",
            )
        ),
        "material_scope_canary_authority_contract_invalid",
    )
    _require(
        bool(re.fullmatch(r"[0-9a-f]{40}", str(authority.get("implementation_commit") or ""))),
        "material_scope_canary_implementation_commit_invalid",
    )
    expected_budget = {
        "maximum_model_calls": 1,
        "maximum_transport_attempts": 1,
        "retries": 0,
        "fallbacks": 0,
        "protocol_switches": 0,
        "external_source_network_calls": 0,
        "retrieval_calls": 0,
        "embedding_calls": 0,
        "candidate_reads": 0,
        "qrel_reference_or_hidden_reads": 0,
        "product_pointer_mutations": 0,
    }
    _require(
        authority.get("execution_budget") == expected_budget,
        "material_scope_canary_execution_budget_invalid",
    )
    bound = authority.get("bound_inputs")
    _require(isinstance(bound, Mapping), "material_scope_canary_bound_inputs_invalid")
    expected_bound_fields = {
        "input_result_ref",
        "input_result_sha256",
        "input_result_digest",
        "material_scope_policy_ref",
        "material_scope_policy_sha256",
        "material_runtime_policy_ref",
        "material_runtime_policy_sha256",
        "intent_ontology_ref",
        "intent_ontology_sha256",
        "kernel_ref",
        "kernel_sha256",
        "provider_profile_ref",
        "provider_profile_sha256",
        "runner_ref",
        "runner_sha256",
        "implementation_ref",
        "implementation_sha256",
        "model_visible_messages_digest",
    }
    _require(
        set(bound) == expected_bound_fields,
        "material_scope_canary_bound_input_fields_invalid",
    )
    input_path, input_payload = _bound_json(
        root, bound, "input_result_ref", "input_result_sha256"
    )
    validate_material_scope_canary_input(input_payload)
    _require(
        input_payload["result_digest"] == bound.get("input_result_digest")
        and input_payload["model_visible_messages_digest"]
        == bound.get("model_visible_messages_digest"),
        "material_scope_canary_input_binding_invalid",
    )
    policy_path, policy = _bound_json(
        root, bound, "material_scope_policy_ref", "material_scope_policy_sha256"
    )
    runtime_policy_path, runtime_policy = _bound_json(
        root, bound, "material_runtime_policy_ref", "material_runtime_policy_sha256"
    )
    ontology_path, ontology = _bound_json(
        root, bound, "intent_ontology_ref", "intent_ontology_sha256"
    )
    kernel_path, kernel = _bound_json(root, bound, "kernel_ref", "kernel_sha256")
    profile_path, profile_payload = _bound_json(
        root, bound, "provider_profile_ref", "provider_profile_sha256"
    )
    profile = load_chat_completion_profile(profile_payload)
    defaults = profile_payload.get("request_defaults") or {}
    _require(
        profile.provider_id == "deepseek"
        and profile.model == "deepseek-v4-pro"
        and profile.api_key_env == "DEEPSEEK_API_KEY"
        and defaults.get("max_tokens") == 12000
        and defaults.get("response_format") == {"type": "json_object"}
        and defaults.get("thinking") == {"type": "enabled"}
        and defaults.get("reasoning_effort") == "max",
        "material_scope_canary_provider_profile_invalid",
    )
    for ref_field, sha_field in (
        ("runner_ref", "runner_sha256"),
        ("implementation_ref", "implementation_sha256"),
    ):
        path = repo_path(root, str(bound.get(ref_field) or ""))
        _require(
            file_sha256(path) == bound.get(sha_field),
            f"material_scope_canary_source_sha_drift:{ref_field}",
        )
    output = authority.get("output_contract")
    _require(
        isinstance(output, Mapping)
        and set(output)
        == {
            "capture_root_ref",
            "private_result_ref",
            "public_result_ref",
            "run_id",
            "attempt_id",
            "product_publication",
        }
        and output.get("product_publication") == "forbidden"
        and all(
            isinstance(output.get(key), str) and bool(output.get(key))
            for key in (
                "capture_root_ref",
                "private_result_ref",
                "public_result_ref",
                "run_id",
                "attempt_id",
            )
        ),
        "material_scope_canary_output_contract_invalid",
    )
    return {
        "input_path": input_path,
        "input": input_payload,
        "policy_path": policy_path,
        "policy": policy,
        "runtime_policy_path": runtime_policy_path,
        "runtime_policy": runtime_policy,
        "ontology_path": ontology_path,
        "ontology": ontology,
        "kernel_path": kernel_path,
        "kernel": kernel,
        "profile_path": profile_path,
        "profile": profile,
        "api_key_env": profile.api_key_env,
    }


def _terminal_summary(
    *,
    root: Path,
    authority_path: Path,
    authority: Mapping[str, Any],
    input_payload: Mapping[str, Any],
    status: str,
    failure_phase: str,
    failure_code: str,
    model_call_attempted: bool,
    transport_attempted: bool,
    provider_result: ChatCompletionResult | None = None,
    full_result_path: Path | None = None,
    compilation: Mapping[str, Any] | None = None,
    request_capture_ref: str = "",
    response_capture_ref: str = "",
) -> dict[str, Any]:
    provider = provider_result.as_dict() if provider_result is not None else {}
    body = {
        "schema_version": MATERIAL_SCOPE_CANARY_RESULT_SCHEMA,
        "status": status,
        "recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "case_key": "DELL",
        "cell_id": "MATERIAL_SCOPE",
        "authority_ref": relative_ref(root, authority_path),
        "authority_sha256": file_sha256(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "input_result_ref": authority["bound_inputs"]["input_result_ref"],
        "input_result_digest": input_payload["result_digest"],
        "research_plan_digest": input_payload["research_plan_digest"],
        "model_visible_messages_digest": input_payload[
            "model_visible_messages_digest"
        ],
        "execution": {
            "model_calls_attempted": int(model_call_attempted),
            "transport_attempts": int(transport_attempted),
            "retries": 0,
            "fallbacks": 0,
            "external_source_network_calls": 0,
            "retrieval_calls": 0,
            "candidate_reads": 0,
            "qrel_reference_or_hidden_reads": 0,
        },
        "provider": {
            "provider_id": provider.get("provider_id", "deepseek"),
            "model": provider.get("model", "deepseek-v4-pro"),
            "finish_reason": provider.get("finish_reason", ""),
            "usage": provider.get("usage", {}),
            "request_capture_ref": (
                relative_ref(root, Path(provider["request_capture_ref"]))
                if provider.get("request_capture_ref")
                else request_capture_ref
            ),
            "response_capture_ref": (
                relative_ref(root, Path(provider["response_capture_ref"]))
                if provider.get("response_capture_ref")
                else response_capture_ref
            ),
            "request_digest": provider.get("request_digest", ""),
            "response_digest": provider.get("response_digest", ""),
            "private_reasoning_fields_redacted": provider.get(
                "private_reasoning_fields_redacted", 0
            ),
        },
        "scope_summary": dict(compilation.get("summary") or {})
        if compilation is not None
        else {},
        "scope_compilation_digest": (
            compilation.get("compilation_digest", "")
            if compilation is not None
            else ""
        ),
        "full_result_ref": (
            relative_ref(root, full_result_path) if full_result_path else ""
        ),
        "full_result_sha256": (
            file_sha256(full_result_path) if full_result_path else ""
        ),
        "failure_phase": failure_phase,
        "failure_code": failure_code,
        "candidate_or_reference_inputs_read": False,
        "candidate_is_not_evidence": True,
        "numeric_authority": False,
        "product_publication": False,
        "s1_qualification_claimed": False,
        "known_boundary": authority["known_boundary"],
    }
    return {**body, "result_digest": canonical_digest(body)}


def run_material_scope_canary(
    authority_path: Path,
    *,
    root: Path,
    executor: Callable[..., ChatCompletionResult] = execute_chat_completion_exact_once,
) -> dict[str, Any]:
    authority = load_json(authority_path)
    bound = validate_material_scope_canary_authority(authority, root=root)
    input_payload = bound["input"]
    output = authority["output_contract"]
    private_path = (root / output["private_result_ref"]).resolve()
    public_path = (root / output["public_result_ref"]).resolve()
    capture_root = (root / output["capture_root_ref"]).resolve()
    for path in (private_path, public_path, capture_root):
        try:
            path.relative_to(root.resolve())
        except ValueError as exc:
            raise MaterialScopeCanaryError(
                "material_scope_canary_output_outside_repository"
            ) from exc
    provider_result: ChatCompletionResult | None = None
    model_call_attempted = False
    transport_attempted = False
    request_capture_ref = ""
    response_capture_ref = ""
    try:
        model_call_attempted = True
        transport_attempted = True
        provider_result = executor(
            profile=bound["profile"],
            messages=input_payload["model_visible_messages"],
            capture_root=capture_root,
            run_id=output["run_id"],
            attempt_id=output["attempt_id"],
        )
        _require(
            provider_result.finish_reason == "stop",
            "material_scope_canary_finish_reason_invalid",
        )
        parsed = parse_research_material_scope_output(provider_result.content)
        kernel = load_financial_research_kernel(bound["kernel"])
        requests = [
            load_evidence_request(row, kernel)
            for row in input_payload["evidence_requests"]
        ]
        compilation = compile_research_material_scope(
            parsed,
            research_plan_digest=input_payload["research_plan_digest"],
            requests=requests,
            required_request_ids=input_payload["required_request_ids"],
            policy=bound["policy"],
            material_runtime_policy=bound["runtime_policy"],
            intent_ontology=bound["ontology"],
        )
        full_body = {
            "schema_version": MATERIAL_SCOPE_CANARY_RESULT_SCHEMA,
            "status": "completed_contract_valid",
            "authority_ref": relative_ref(root, authority_path),
            "authority_sha256": file_sha256(authority_path),
            "input_result_ref": authority["bound_inputs"]["input_result_ref"],
            "input_result_digest": input_payload["result_digest"],
            "provider_result": provider_result.as_dict(),
            "scope_payload": parsed,
            "scope_compilation": compilation,
            "candidate_or_reference_inputs_read": False,
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
            "product_publication": False,
        }
        write_new_json(
            private_path,
            {**full_body, "result_digest": canonical_digest(full_body)},
        )
        summary = _terminal_summary(
            root=root,
            authority_path=authority_path,
            authority=authority,
            input_payload=input_payload,
            status="completed_contract_valid",
            failure_phase="",
            failure_code="",
            model_call_attempted=model_call_attempted,
            transport_attempted=transport_attempted,
            provider_result=provider_result,
            full_result_path=private_path,
            compilation=compilation,
        )
    except (ModelGatewayError, ResearchMaterialScopeError, MaterialScopeCanaryError) as exc:
        if isinstance(exc, ModelGatewayError):
            phase = "provider_transport_or_response"
            code = exc.code
            if exc.capture_ref:
                response_path = Path(exc.capture_ref)
                response_capture_ref = relative_ref(root, response_path)
                request_path = response_path.with_name("model_visible_request.json")
                if request_path.is_file():
                    request_capture_ref = relative_ref(root, request_path)
        elif isinstance(exc, ResearchMaterialScopeError):
            phase = "scope_output_parse_or_contract"
            code = str(exc)
        else:
            phase = "post_provider_terminal_validation"
            code = exc.code
        summary = _terminal_summary(
            root=root,
            authority_path=authority_path,
            authority=authority,
            input_payload=input_payload,
            status="terminal_failed_no_retry",
            failure_phase=phase,
            failure_code=code,
            model_call_attempted=model_call_attempted,
            transport_attempted=transport_attempted,
            provider_result=provider_result,
            request_capture_ref=request_capture_ref,
            response_capture_ref=response_capture_ref,
        )
    write_new_json(public_path, summary)
    return summary


__all__ = [
    "MATERIAL_SCOPE_CANARY_AUTHORITY_SCHEMA",
    "MATERIAL_SCOPE_CANARY_AUTHORITY_STATUS",
    "MATERIAL_SCOPE_CANARY_INPUT_SCHEMA",
    "MATERIAL_SCOPE_CANARY_RESULT_SCHEMA",
    "MATERIAL_SCOPE_CANARY_RUN_SCOPE",
    "MaterialScopeCanaryError",
    "build_material_scope_canary_input",
    "file_sha256",
    "load_json",
    "run_material_scope_canary",
    "validate_material_scope_canary_authority",
    "validate_material_scope_canary_input",
    "write_new_json",
]
