from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_08_query_facet_plan import (
    ModelQueryAtomCandidate,
    QueryFacetPlan,
    compile_query_facet_plans,
)
from sec_agent.s1_08_search_intent_compiler import SearchIntent
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


POLICY_SCHEMA = "fin_ia_0_1_3_s1_08_deepseek_query_atom_canary_policy_v1_0"
CONTRACT_REF = "fin_0_1_3.S1_08.deepseek_query_atom_canary:v1"
RUN_SCOPE = "S1_08_QUERY_FACET_DEEPSEEK_ATOM_CANARY_EXACT_LIVE_EXECUTION"
REQUEST_SCHEMA = "fin_ia_0_1_3_s1_08_deepseek_query_atom_request_v1_0"
OUTPUT_SCHEMA = "fin_ia_0_1_3_s1_08_deepseek_query_atom_output_v1_0"
ADMISSION_SCHEMA = "fin_ia_0_1_3_s1_08_deepseek_query_atom_admission_v1_0"
CAPTURE_SCHEMA = "fin_ia_0_1_3_s1_08_deepseek_query_atom_capture_v1_0"
TERMINAL_SCHEMA = "fin_ia_0_1_3_s1_08_deepseek_query_atom_terminal_v1_0"
MODEL_VARIANT = "deepseek_query_atoms_plus_deterministic_local_compiler"
GOLD_MARKERS = (
    "SRC_",
    "DELL_E",
    "MU_E",
    "NVDA_E",
    "DELL_T",
    "MU_T",
    "NVDA_T",
    "http://",
    "https://",
)


class S108QueryAtomCanaryError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


ProviderCall = Callable[..., Mapping[str, Any]]


def load_query_atom_canary_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or policy.get("run_scope") != RUN_SCOPE
        or policy.get("binding_hash_profile")
        != "sha256_utf8_lf_normalized_v1"
    ):
        raise S108QueryAtomCanaryError(
            "s1_08_query_atom_canary_policy_identity_invalid"
        )
    provider = policy.get("provider") or {}
    if provider != {
        "backend": "deepseek",
        "model": "deepseek-v4-pro",
        "base_url": "https://api.deepseek.com/beta",
        "chat_completions_path": "/chat/completions",
        "api_key_env": "DEEPSEEK_API_KEY",
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
        "thinking_enabled": False,
    }:
        raise S108QueryAtomCanaryError(
            "s1_08_query_atom_canary_provider_invalid"
        )
    selection = policy.get("selection_contract") or {}
    if (
        selection.get("language") != "en"
        or selection.get("expected_plan_count") != 18
        or selection.get("maximum_atoms") != 18
        or selection.get("maximum_atoms_per_plan") != 1
        or selection.get("allowed_atom_kinds")
        != ["metric", "product", "mechanism", "synonym"]
        or selection.get("maximum_characters_per_atom") != 64
        or selection.get("empty_atom_set_allowed") is not True
        or selection.get("model_may_emit_final_query") is not False
        or selection.get(
            "model_may_emit_identity_period_relationship_domain_route_url_gold_or_hidden_qrel"
        )
        is not False
    ):
        raise S108QueryAtomCanaryError(
            "s1_08_query_atom_canary_selection_contract_invalid"
        )
    budget = policy.get("execution_budget") or {}
    if budget != {
        "maximum_provider_calls": 1,
        "maximum_transport_attempts": 1,
        "retry_count": 0,
        "fallback_count": 0,
        "maximum_output_tokens": 2200,
        "timeout_seconds": 180,
        "document_fetches": 0,
        "evidence_promotions": 0,
        "retrieval_calls": 0,
        "embedding_calls": 0,
        "rerank_calls": 0,
    }:
        raise S108QueryAtomCanaryError(
            "s1_08_query_atom_canary_budget_invalid"
        )
    if any((policy.get("calls_authorized_by_policy_alone") or {}).values()):
        raise S108QueryAtomCanaryError(
            "s1_08_query_atom_canary_policy_self_authorized_call"
        )
    capture = policy.get("capture_contract") or {}
    if (
        capture.get("full_model_visible_request_saved_before_validation")
        is not True
        or capture.get(
            "full_assistant_content_and_gateway_result_saved_before_validation"
        )
        is not True
        or capture.get("api_key_authorization_cookie_saved") is not False
        or capture.get("provider_private_reasoning_required_or_saved") is not False
        or capture.get("capture_is_business_evidence") is not False
    ):
        raise S108QueryAtomCanaryError(
            "s1_08_query_atom_canary_capture_contract_invalid"
        )
    return policy


def compile_query_atom_request(
    *,
    policy: Mapping[str, Any],
    query_facet_plans: Sequence[Mapping[str, Any]],
    research_objectives: Mapping[str, str],
) -> dict[str, Any]:
    selected = sorted(
        (
            dict(row)
            for row in query_facet_plans
            if row.get("language") == policy["selection_contract"]["language"]
        ),
        key=lambda row: (
            row["case_key"],
            row["evidence_slot_id"],
            row["evidence_owner_entity_key"],
        ),
    )
    if (
        len(selected) != policy["selection_contract"]["expected_plan_count"]
        or set(research_objectives) != {"DELL", "MU", "NVDA"}
    ):
        raise S108QueryAtomCanaryError(
            "s1_08_query_atom_canary_request_input_invalid"
        )
    plan_rows = []
    for row in selected:
        plan_key = _plan_key(row)
        plan_rows.append(
            {
                "plan_key": list(plan_key),
                "plan_key_digest": canonical_digest(list(plan_key)),
                "case_research_objective": research_objectives[row["case_key"]],
                "case_key": row["case_key"],
                "evidence_slot_id": row["evidence_slot_id"],
                "evidence_owner_entity_key": row["evidence_owner_entity_key"],
                "evidence_owner_role": row["evidence_owner_role"],
                "relationship_direction": row["relationship_direction"],
                "existing_document_types": list(row["document_types"]),
                "existing_metric_facets": list(row["metric_facets"]),
                "existing_product_facets": list(row["product_facets"]),
                "existing_mechanism_facets": list(row["mechanism_facets"]),
                "maximum_new_atoms": 1,
            }
        )
    body = {
        "schema_version": REQUEST_SCHEMA,
        "task": (
            "For each typed plan, either propose one genuinely incremental English "
            "query atom or abstain. Do not repeat an existing facet."
        ),
        "output_contract": {
            "schema_version": OUTPUT_SCHEMA,
            "top_level_keys_exactly": ["schema_version", "atoms"],
            "atom_keys_exactly": [
                "case_key",
                "evidence_slot_id",
                "evidence_owner_entity_key",
                "language",
                "atom_kind",
                "value",
            ],
            "allowed_atom_kinds": list(
                policy["selection_contract"]["allowed_atom_kinds"]
            ),
            "maximum_atoms": policy["selection_contract"]["maximum_atoms"],
            "maximum_atoms_per_plan": policy["selection_contract"][
                "maximum_atoms_per_plan"
            ],
            "language": "en",
            "empty_atoms_allowed": True,
        },
        "forbidden": [
            "final query strings",
            "URLs or domains",
            "company identity or alias additions",
            "periods, dates or as-of changes",
            "relationship, source family, provider, route, filter or budget changes",
            "Gold IDs, hidden qrels, expected sources or answers",
            "financial conclusions, facts, numbers or citations",
        ],
        "plans": plan_rows,
        "visibility_boundary": deepcopy(dict(policy["visibility_contract"])),
    }
    serialized = json.dumps(body, ensure_ascii=False)
    if any(marker in serialized for marker in GOLD_MARKERS):
        raise S108QueryAtomCanaryError(
            "s1_08_query_atom_canary_hidden_target_or_URL_leak"
        )
    return {**body, "request_digest": canonical_digest(body)}


def validate_and_compile_query_atom_output(
    *,
    output: Mapping[str, Any],
    request: Mapping[str, Any],
    policy: Mapping[str, Any],
    intents: Sequence[SearchIntent],
    query_facet_policy: Mapping[str, Any],
) -> tuple[list[dict[str, str]], tuple[QueryFacetPlan, ...]]:
    if set(output) != {"schema_version", "atoms"} or output.get(
        "schema_version"
    ) != OUTPUT_SCHEMA:
        raise S108QueryAtomCanaryError(
            "s1_08_query_atom_canary_output_envelope_invalid"
        )
    atoms = output.get("atoms")
    if not isinstance(atoms, list) or len(atoms) > int(
        policy["selection_contract"]["maximum_atoms"]
    ):
        raise S108QueryAtomCanaryError(
            "s1_08_query_atom_canary_output_atom_count_invalid"
        )
    allowed_keys = {
        tuple(str(value) for value in row["plan_key"])
        for row in request["plans"]
    }
    seen: set[tuple[str, str, str, str]] = set()
    candidates: list[ModelQueryAtomCandidate] = []
    normalized_rows: list[dict[str, str]] = []
    expected_fields = {
        "case_key",
        "evidence_slot_id",
        "evidence_owner_entity_key",
        "language",
        "atom_kind",
        "value",
    }
    for raw in atoms:
        if not isinstance(raw, Mapping) or set(raw) != expected_fields:
            raise S108QueryAtomCanaryError(
                "s1_08_query_atom_canary_output_atom_shape_invalid"
            )
        key = (
            str(raw["case_key"]),
            str(raw["evidence_slot_id"]),
            str(raw["evidence_owner_entity_key"]),
            str(raw["language"]),
        )
        if key not in allowed_keys or key in seen:
            raise S108QueryAtomCanaryError(
                "s1_08_query_atom_canary_output_plan_binding_invalid"
            )
        seen.add(key)
        candidate = ModelQueryAtomCandidate(
            case_key=key[0],
            evidence_slot_id=key[1],
            evidence_owner_entity_key=key[2],
            language=key[3],
            atom_kind=str(raw["atom_kind"]),
            value=str(raw["value"]),
        )
        candidates.append(candidate)
        normalized_rows.append(candidate.as_dict())
    try:
        plans = compile_query_facet_plans(
            intents=intents,
            policy=query_facet_policy,
            model_atoms=tuple(candidates),
        )
    except Exception as exc:
        code = str(getattr(exc, "code", type(exc).__name__))
        raise S108QueryAtomCanaryError(
            "s1_08_query_atom_canary_local_atom_validation_failed:" + code
        ) from exc
    return normalized_rows, plans


def issue_query_atom_canary_admission(
    *,
    execution_git_commit: str,
    runner_sha256: str,
    runtime_module_sha256: str,
    policy_sha256: str,
    authority_decision_digest: str,
    request: Mapping[str, Any],
    issued_at: str,
    expires_at: str,
    run_nonce: str,
    credential_present: bool,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    for value in (
        execution_git_commit,
        runner_sha256,
        runtime_module_sha256,
        policy_sha256,
        authority_decision_digest,
        request.get("request_digest"),
    ):
        if not _digest_or_git(value):
            raise S108QueryAtomCanaryError(
                "s1_08_query_atom_canary_admission_binding_invalid"
            )
    if credential_present is not True or _time(expires_at) <= _time(issued_at):
        raise S108QueryAtomCanaryError(
            "s1_08_query_atom_canary_admission_credential_or_time_invalid"
        )
    run_id = "fin013_s1_08_query_atom_canary_" + canonical_digest(
        {"nonce": run_nonce, "git": execution_git_commit}
    )[:20]
    body = {
        "schema_version": ADMISSION_SCHEMA,
        "admission_id": "admission::" + run_id,
        "scope": RUN_SCOPE,
        "contract_ref": CONTRACT_REF,
        "run_id": run_id,
        "attempt_id": run_id + "::attempt_1",
        "runtime_identity": run_id + "::runtime_1",
        "execution_git_commit": execution_git_commit,
        "runner_sha256": runner_sha256,
        "runtime_module_sha256": runtime_module_sha256,
        "policy_sha256": policy_sha256,
        "authority_decision_digest": authority_decision_digest,
        "request_digest": request["request_digest"],
        "provider": deepcopy(dict(policy["provider"])),
        "budget": deepcopy(dict(policy["execution_budget"])),
        "credential_present": True,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "run_nonce_digest": canonical_digest(run_nonce),
        "state": "issued_unconsumed",
    }
    return {**body, "admission_digest": canonical_digest(body)}


def execute_query_atom_canary(
    *,
    admission: Mapping[str, Any],
    request: Mapping[str, Any],
    policy: Mapping[str, Any],
    intents: Sequence[SearchIntent],
    query_facet_policy: Mapping[str, Any],
    execution_git_commit: str,
    runner_sha256: str,
    runtime_module_sha256: str,
    policy_sha256: str,
    runtime_root: Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    provider_call: ProviderCall,
    observed_at: str,
) -> dict[str, Any]:
    _validate_admission(
        admission=admission,
        request=request,
        policy=policy,
        execution_git_commit=execution_git_commit,
        runner_sha256=runner_sha256,
        runtime_module_sha256=runtime_module_sha256,
        policy_sha256=policy_sha256,
        observed_at=observed_at,
    )
    root = runtime_root.resolve()
    ledger_path = shared_ledger.path.resolve()
    if ledger_path == root or root in ledger_path.parents:
        raise S108QueryAtomCanaryError(
            "s1_08_query_atom_canary_ledger_inside_runtime_root"
        )
    root.mkdir(parents=True, exist_ok=False)
    (root / "captures").mkdir()
    reservation = shared_ledger.reserve(
        admission_digest=str(admission["admission_digest"]),
        admission_id=str(admission["admission_id"]),
        scope=RUN_SCOPE,
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        runtime_identity=str(admission["runtime_identity"]),
        reserved_at=observed_at,
    )
    kwargs = _provider_kwargs(request=request, admission=admission)
    try:
        gateway_result = dict(provider_call(**kwargs))
    except Exception as exc:
        gateway_result = {
            "status": "gateway_exception",
            "content": "",
            "finish_reason": "",
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "transport_attempt_count": 1,
            "exception_type": type(exc).__name__,
        }
    safe_gateway_result = _strip_private_reasoning(gateway_result)
    capture_body = {
        "schema_version": CAPTURE_SCHEMA,
        "request_digest": request["request_digest"],
        "model_visible_request": deepcopy(dict(request)),
        "provider_request": {
            key: deepcopy(value)
            for key, value in kwargs.items()
            if key != "api_key_env"
        },
        "gateway_result": safe_gateway_result,
        "credential_or_authorization_value_saved": False,
        "provider_private_reasoning_saved": False,
        "business_evidence_or_fact_authority": False,
    }
    capture_digest = canonical_digest(capture_body)
    capture_ref = f"captures/01_{capture_digest}.json"
    _write(root / capture_ref, capture_body)
    failure: str | None = None
    parsed_output: dict[str, Any] | None = None
    accepted_atoms: list[dict[str, str]] = []
    assisted_plans: tuple[QueryFacetPlan, ...] = ()
    if gateway_result.get("status") != "ok":
        failure = "s1_08_query_atom_canary_provider_transport_or_status_failure"
    else:
        try:
            candidate = json.loads(str(gateway_result.get("content") or ""))
            if not isinstance(candidate, Mapping):
                raise ValueError("output_not_object")
            parsed_output = dict(candidate)
            accepted_atoms, assisted_plans = validate_and_compile_query_atom_output(
                output=parsed_output,
                request=request,
                policy=policy,
                intents=intents,
                query_facet_policy=query_facet_policy,
            )
        except S108QueryAtomCanaryError as exc:
            failure = exc.code
        except (json.JSONDecodeError, ValueError):
            failure = "s1_08_query_atom_canary_output_json_invalid"
    status = (
        "terminal_succeeded_exact_once"
        if failure is None
        else "terminal_failed_no_retry"
    )
    terminal_body = {
        "schema_version": TERMINAL_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "admission_digest": admission["admission_digest"],
        "run_id": admission["run_id"],
        "attempt_id": admission["attempt_id"],
        "status": status,
        "terminal_phase": "deepseek_query_atom_single_batch_canary",
        "terminal_code": failure or "s1_08_query_atom_canary_output_accepted",
        "request_digest": request["request_digest"],
        "capture_digest": capture_digest,
        "capture_ref": capture_ref,
        "gateway_status": gateway_result.get("status"),
        "finish_reason": gateway_result.get("finish_reason"),
        "usage": {
            "input_tokens": int(gateway_result.get("input_tokens") or 0),
            "output_tokens": int(gateway_result.get("output_tokens") or 0),
            "total_tokens": int(gateway_result.get("total_tokens") or 0),
            "transport_attempt_count": int(
                gateway_result.get("transport_attempt_count") or 0
            ),
            "latency_ms": int(gateway_result.get("latency_ms") or 0),
        },
        "provider_output": parsed_output,
        "provider_output_digest": (
            canonical_digest(parsed_output) if parsed_output is not None else None
        ),
        "accepted_atoms": accepted_atoms,
        "accepted_atom_count": len(accepted_atoms),
        "assisted_plan_set_digest": (
            canonical_digest([row.as_dict() for row in assisted_plans])
            if assisted_plans
            else None
        ),
        "completed_calls": 1,
        "retry_count": 0,
        "fallback_count": 0,
        "document_fetches": 0,
        "evidence_promotions": 0,
        "retrieval_calls": 0,
        "embedding_calls": 0,
        "rerank_calls": 0,
        "business_artifact_promotions": 0,
        "runtime_activation": False,
        "observed_at": observed_at,
        "reservation_digest": reservation.reservation_digest,
    }
    terminal = {
        **terminal_body,
        "terminal_result_digest": canonical_digest(terminal_body),
    }
    _write(root / "terminal_result.json", terminal)
    final_receipt = shared_ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        terminal_status=status,
        terminal_phase=str(terminal["terminal_phase"]),
        terminal_code=str(terminal["terminal_code"]),
        terminal_result_digest=str(terminal["terminal_result_digest"]),
        finalized_at=observed_at,
    )
    return {**terminal, "shared_admission_receipt": final_receipt.as_dict()}


def _validate_admission(**values: Any) -> None:
    admission = values["admission"]
    body = {
        key: deepcopy(value)
        for key, value in admission.items()
        if key != "admission_digest"
    }
    if (
        admission.get("schema_version") != ADMISSION_SCHEMA
        or admission.get("scope") != RUN_SCOPE
        or admission.get("contract_ref") != CONTRACT_REF
        or admission.get("state") != "issued_unconsumed"
        or admission.get("admission_digest") != canonical_digest(body)
        or admission.get("request_digest")
        != values["request"].get("request_digest")
        or admission.get("execution_git_commit")
        != values["execution_git_commit"]
        or admission.get("runner_sha256") != values["runner_sha256"]
        or admission.get("runtime_module_sha256")
        != values["runtime_module_sha256"]
        or admission.get("policy_sha256") != values["policy_sha256"]
    ):
        raise S108QueryAtomCanaryError(
            "s1_08_query_atom_canary_admission_invalid"
        )
    if _time(values["observed_at"]) > _time(str(admission.get("expires_at") or "")):
        raise S108QueryAtomCanaryError(
            "s1_08_query_atom_canary_admission_expired"
        )
    if (
        admission.get("credential_present") is not True
        or admission.get("provider") != values["policy"]["provider"]
        or admission.get("budget") != values["policy"]["execution_budget"]
    ):
        raise S108QueryAtomCanaryError(
            "s1_08_query_atom_canary_admission_provider_or_budget_invalid"
        )


def _provider_kwargs(
    *, request: Mapping[str, Any], admission: Mapping[str, Any]
) -> dict[str, Any]:
    provider = admission["provider"]
    budget = admission["budget"]
    return {
        "llm_backend": provider["backend"],
        "base_url": provider["base_url"],
        "chat_completions_path": provider["chat_completions_path"],
        "model": provider["model"],
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a bounded financial-search query facet assistant. "
                    "Return one JSON object only. You may propose at most one genuinely "
                    "incremental English atom per typed plan, or abstain. Never output "
                    "final queries, URLs, identities, periods, relationships, routes, "
                    "sources, facts, numbers, citations, Gold identifiers or prose."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    request,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
        ],
        "response_format": deepcopy(provider["response_format"]),
        "api_key_env": provider["api_key_env"],
        "temperature": provider["temperature"],
        "max_tokens": int(budget["maximum_output_tokens"]),
        "timeout_s": int(budget["timeout_seconds"]),
        "stream": False,
        "enable_thinking": provider["thinking_enabled"],
        "role": "fin013_s1_08_query_atom_canary",
        "profile": "three_case_18_plan_english_atom_batch",
        "trace_tags": {
            "run_id": admission["run_id"],
            "request_digest": request["request_digest"],
        },
        "max_transport_attempts": 1,
    }


def _strip_private_reasoning(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _strip_private_reasoning(item)
            for key, item in value.items()
            if str(key).casefold()
            not in {"reasoning_content", "reasoning_details", "private_reasoning"}
        }
    if isinstance(value, list):
        return [_strip_private_reasoning(item) for item in value]
    return deepcopy(value)


def _plan_key(plan: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(plan["case_key"]),
        str(plan["evidence_slot_id"]),
        str(plan["evidence_owner_entity_key"]),
        str(plan["language"]),
    )


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(
            (
                json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n"
            ).encode("utf-8")
        )


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise S108QueryAtomCanaryError(
            "s1_08_query_atom_canary_time_invalid"
        ) from exc
    if parsed.tzinfo is None:
        raise S108QueryAtomCanaryError(
            "s1_08_query_atom_canary_timezone_missing"
        )
    return parsed.astimezone(timezone.utc)


def _digest_or_git(value: Any) -> bool:
    text = str(value or "")
    return len(text) in {40, 64} and all(
        character in "0123456789abcdef" for character in text
    )


__all__ = [
    "S108QueryAtomCanaryError",
    "compile_query_atom_request",
    "execute_query_atom_canary",
    "issue_query_atom_canary_admission",
    "load_query_atom_canary_policy",
    "validate_and_compile_query_atom_output",
]
