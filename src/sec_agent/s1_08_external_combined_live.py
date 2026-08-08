from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.official_source_attempt_program import SourceTransport
from sec_agent.s1_08_candidate_generation_runtime import (
    CandidateGenerationInterrupted,
    DiscoveryQuery,
)
from sec_agent.s1_08_candidate_generation_runtime_v4 import (
    load_source_catalog_v4,
    run_candidate_generation_v4,
)
from sec_agent.s1_08_firecrawl_semantic_control import (
    normalize_firecrawl_response,
)
from sec_agent.s1_08_official_discovery_adapter_v4 import (
    ProtectedFetchOfficialDiscoveryAdapterV4,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


POLICY_SCHEMA = "fin_ia_0_1_3_s1_08_external_combined_live_policy_v1_0"
CONTRACT_REF = "fin_0_1_3.S1_08.external_official_firecrawl_shadow_combined:v1"
ZERO_CALL_SCOPE = (
    "S1_08_OFFICIAL_ROUTES_PLUS_FIRECRAWL_SHADOW_COMBINED_LIVE_"
    "ZERO_CALL_IMPLEMENTATION_AND_AUTHORITY_DECISION"
)
EXACT_LIVE_SCOPE = "S1_08_OFFICIAL_ROUTES_PLUS_FIRECRAWL_SHADOW_COMBINED_LIVE"
PLAN_SCHEMA = "fin_ia_0_1_3_s1_08_external_combined_plan_v1_0"
ADMISSION_SCHEMA = "fin_ia_0_1_3_s1_08_external_combined_admission_v1_0"
TERMINAL_SCHEMA = "fin_ia_0_1_3_s1_08_external_combined_terminal_v1_0"
CASES = ("DELL", "MU", "NVDA")


class S108ExternalCombinedError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


FirecrawlCall = Callable[[str, bytes, int], tuple[int, bytes]]
OfficialLaneExecutor = Callable[..., Mapping[str, Any]]


def sha256_utf8_lf(path: str | Path) -> str:
    text = Path(path).read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_external_combined_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    official = (policy.get("lanes") or {}).get("official_primary") or {}
    shadow = (policy.get("lanes") or {}).get("firecrawl_shadow") or {}
    budget = policy.get("combined_budget") or {}
    execution = policy.get("execution_contract") or {}
    boundary = policy.get("authority_boundary") or {}
    valid = (
        policy.get("schema_version") == POLICY_SCHEMA
        and policy.get("contract_ref") == CONTRACT_REF
        and policy.get("zero_call_run_scope") == ZERO_CALL_SCOPE
        and policy.get("exact_live_run_scope") == EXACT_LIVE_SCOPE
        and policy.get("binding_hash_profile")
        == "sha256_utf8_lf_normalized_v1"
        and policy.get("cases") == list(CASES)
        and official.get("case_count") == 3
        and official.get("query_facet_plan_count") == 18
        and official.get("network_call_ceiling_per_case") == 16
        and official.get("network_call_ceiling_total") == 48
        and shadow.get("query_facet_plan_count") == 24
        and shadow.get("network_call_ceiling_total") == 24
        and shadow.get("retry_ceiling") == 0
        and shadow.get("evidence_promotion_allowed") is False
        and shadow.get("financial_fact_authority") is False
        and budget
        == {
            "network_call_ceiling": 72,
            "provider_call_ceiling": 24,
            "model_call_ceiling": 0,
            "embedding_call_ceiling": 0,
            "rerank_call_ceiling": 0,
            "evidence_promotion_ceiling": 0,
            "retry_ceiling": 0,
            "fallback_ceiling": 0,
            "per_call_timeout_seconds": 30,
            "overall_timeout_seconds": 900,
        }
        and all(execution.get(key) is True for key in (
            "shared_exact_once_admission_ledger",
            "capture_safe_request_before_network",
            "capture_raw_response_or_typed_failure_before_parse",
            "terminalize_every_planned_shadow_identity",
            "preserve_completed_lane_results_on_later_failure",
            "systemic_firecrawl_401_402_403_stops_remaining_shadow_network",
            "all_required_external_case_slots_receive_route_opportunity",
            "no_reranker_rescue",
            "no_automatic_replacement_live",
        ))
        and boundary.get("calls_authorized_by_policy_alone") == 0
        and boundary.get("internal_retrieval_not_authorized") is True
    )
    if not valid:
        raise S108ExternalCombinedError("s1_08_external_combined_policy_invalid")
    return policy


def load_bound_inputs(
    *, repo_root: str | Path, policy: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    root = Path(repo_root)
    rows: dict[str, dict[str, Any]] = {}
    bindings = policy.get("immutable_inputs") or {}
    for name in (
        "query_facet_proof",
        "query_atom_result",
        "query_facet_policy",
        "source_catalog",
        "progression_plan",
        "official_clean_proof",
        "firecrawl_scoring",
    ):
        ref = str(bindings.get(f"{name}_ref") or "")
        expected = str(bindings.get(f"{name}_sha256") or "")
        path = root / ref
        if (
            not ref
            or len(expected) != 64
            or not path.is_file()
            or sha256_utf8_lf(path) != expected
        ):
            raise S108ExternalCombinedError(
                f"s1_08_external_combined_{name}_binding_invalid"
            )
        rows[name] = json.loads(path.read_text(encoding="utf-8"))
    return rows


def compile_external_combined_plan(
    *, policy: Mapping[str, Any], bound_inputs: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    facet_proof = bound_inputs["query_facet_proof"]
    atom_result = bound_inputs["query_atom_result"]
    catalog = bound_inputs["source_catalog"]
    progression = bound_inputs["progression_plan"]
    if (
        facet_proof.get("status") != "zero_call_engineering_pass"
        or facet_proof.get("plan_count") != 36
        or atom_result.get("status")
        != "natural_query_atom_canary_terminal_failed_model_variant_rejected"
        or ((atom_result.get("decision") or {}).get("external_query_baseline"))
        != "deterministic_local_compiler_only"
        or ((atom_result.get("natural_observation") or {}).get("accepted_atom_count"))
        != 0
        or progression.get("status")
        not in {
            "query_facet_complete_model_variant_rejected_external_combined_current_internal_backlog_registered",
            "external_combined_zero_call_engineering_pass_clean_authority_pending_internal_backlog_registered",
        }
    ):
        raise S108ExternalCombinedError(
            "s1_08_external_combined_selected_query_variant_invalid"
        )
    if catalog.get("schema_version") != (
        "fin_ia_0_1_3_s1_08_current_source_catalog_protected_fetch_cache_policy_v4_0"
    ):
        raise S108ExternalCombinedError(
            "s1_08_external_combined_catalog_identity_invalid"
        )
    plans = [dict(row) for row in facet_proof.get("plans") or ()]
    if len(plans) != 36 or any(row.get("accepted_model_atoms") for row in plans):
        raise S108ExternalCombinedError(
            "s1_08_external_combined_query_facet_input_invalid"
        )
    official_plans = sorted(
        (
            row
            for row in plans
            if row.get("language") == "en"
            and "external_official_primary" in (row.get("eligible_external_routes") or ())
        ),
        key=_plan_sort_key,
    )
    shadow_plans = sorted(
        (
            row
            for row in plans
            if "external_semantic_shadow" in (row.get("eligible_external_routes") or ())
        ),
        key=_plan_sort_key,
    )
    if len(official_plans) != 18 or len(shadow_plans) != 24:
        raise S108ExternalCombinedError(
            "s1_08_external_combined_lane_plan_count_invalid"
        )
    official_rows = [_official_plan_projection(row) for row in official_plans]
    shadow_rows = [
        _shadow_plan_projection(row, ordinal=index + 1)
        for index, row in enumerate(shadow_plans)
    ]
    opportunity_rows = sorted(
        {
            (str(row["case_key"]), str(row["evidence_slot_id"]))
            for row in official_rows
        }
    )
    if len(opportunity_rows) != 12:
        raise S108ExternalCombinedError(
            "s1_08_external_combined_required_opportunity_invalid"
        )
    body = {
        "schema_version": PLAN_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "query_variant": "deterministic_local_query_facet_only",
        "cases": list(CASES),
        "official_plan_rows": official_rows,
        "shadow_plan_rows": shadow_rows,
        "required_case_slot_opportunities": [
            {"case_key": case_key, "evidence_slot_id": slot_id}
            for case_key, slot_id in opportunity_rows
        ],
        "counts": {
            "official_query_facet_plans": len(official_rows),
            "shadow_query_facet_plans": len(shadow_rows),
            "required_case_slot_opportunities": len(opportunity_rows),
            "accepted_model_atoms": 0,
        },
        "budget": deepcopy(dict(policy["combined_budget"])),
        "authority_boundary": deepcopy(dict(policy["authority_boundary"])),
    }
    return {**body, "plan_digest": canonical_digest(body)}


def issue_external_combined_admission(
    *,
    policy: Mapping[str, Any],
    plan: Mapping[str, Any],
    authority: Mapping[str, Any],
    execution_git_commit: str,
    runner_sha256: str,
    runtime_module_sha256: str,
    policy_sha256: str,
    zero_call_proof_sha256: str,
    issued_at: str,
    expires_at: str,
    run_nonce: str,
) -> dict[str, Any]:
    approval = authority.get("exact_live_authority") or {}
    if (
        authority.get("status") != "approved_one_external_combined_exact_live"
        or approval.get("scope") != EXACT_LIVE_SCOPE
        or approval.get("maximum_admissions") != 1
        or approval.get("maximum_executions") != 1
        or approval.get("network_call_ceiling") != 72
        or approval.get("retry_ceiling") != 0
        or approval.get("model_call_ceiling") != 0
    ):
        raise S108ExternalCombinedError(
            "s1_08_external_combined_authority_invalid"
        )
    for value in (
        execution_git_commit,
        runner_sha256,
        runtime_module_sha256,
        policy_sha256,
        zero_call_proof_sha256,
        authority.get("authority_digest"),
        plan.get("plan_digest"),
    ):
        if not _digest_or_git(value):
            raise S108ExternalCombinedError(
                "s1_08_external_combined_admission_binding_invalid"
            )
    if _time(expires_at) <= _time(issued_at):
        raise S108ExternalCombinedError(
            "s1_08_external_combined_admission_time_invalid"
        )
    run_id = "fin013_s1_08_external_combined_" + canonical_digest(
        {"nonce": run_nonce, "git": execution_git_commit}
    )[:20]
    body = {
        "schema_version": ADMISSION_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "scope": EXACT_LIVE_SCOPE,
        "admission_id": "admission::" + run_id,
        "run_id": run_id,
        "attempt_id": run_id + "::attempt_1",
        "runtime_identity": run_id + "::runtime_1",
        "execution_git_commit": execution_git_commit,
        "runner_sha256": runner_sha256,
        "runtime_module_sha256": runtime_module_sha256,
        "policy_sha256": policy_sha256,
        "zero_call_proof_sha256": zero_call_proof_sha256,
        "authority_digest": authority["authority_digest"],
        "plan_digest": plan["plan_digest"],
        "budget": deepcopy(dict(policy["combined_budget"])),
        "issued_at": issued_at,
        "expires_at": expires_at,
        "run_nonce_digest": canonical_digest(run_nonce),
        "state": "issued_unconsumed",
    }
    return {**body, "admission_digest": canonical_digest(body)}


class FacetBoundOfficialAdapter:
    """Projects governed QueryFacet text into the existing official adapter."""

    def __init__(
        self,
        *,
        delegate: ProtectedFetchOfficialDiscoveryAdapterV4,
        plan_rows: Sequence[Mapping[str, Any]],
    ) -> None:
        self._delegate = delegate
        self._plan_rows = tuple(deepcopy(dict(row)) for row in plan_rows)
        self._bound_by_original_digest: dict[str, DiscoveryQuery] = {}
        self.bound_query_receipts: list[dict[str, Any]] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def prepare_attempt(
        self,
        *,
        query: DiscoveryQuery,
        network_call_allowance: int,
        maximum_document_fetches: int,
        protected_document_fetches: int,
    ) -> None:
        bound = self._bind(query)
        self._delegate.prepare_attempt(
            query=bound,
            network_call_allowance=network_call_allowance,
            maximum_document_fetches=maximum_document_fetches,
            protected_document_fetches=protected_document_fetches,
        )

    def discover(self, query: DiscoveryQuery) -> Sequence[Any]:
        return self._delegate.discover(self._bind(query))

    def persist_candidate_checkpoint(self, snapshot: Mapping[str, Any]) -> None:
        self._delegate.persist_candidate_checkpoint(snapshot)

    def _bind(self, query: DiscoveryQuery) -> DiscoveryQuery:
        prior = self._bound_by_original_digest.get(query.query_digest)
        if prior is not None:
            return prior
        matching = [
            row
            for row in self._plan_rows
            if row["case_key"] == query.case_key
            and row["evidence_slot_id"] == query.evidence_slot_id
            and row["evidence_owner_entity_key"] in query.entity_keys
        ]
        if not matching and query.slot_budget_group == "market_context":
            self._bound_by_original_digest[query.query_digest] = query
            self.bound_query_receipts.append(
                {
                    "original_query_digest": query.query_digest,
                    "bound_query_digest": query.query_digest,
                    "case_key": query.case_key,
                    "evidence_slot_id": query.evidence_slot_id,
                    "revision": query.revision,
                    "query_facet_plan_digests": [],
                    "query_text_digest": canonical_digest(query.query_text),
                    "binding_state": "local_market_context_zero_network_exempt",
                }
            )
            return query
        if not matching:
            raise S108ExternalCombinedError(
                "s1_08_external_combined_official_query_facet_missing"
            )
        fragments: list[str] = []
        plan_digests: list[str] = []
        for row in sorted(matching, key=_plan_sort_key):
            fragments.extend((row["exact_lookup_query"], row["lexical_query"]))
            plan_digests.append(str(row["plan_digest"]))
        if query.revision:
            fragments.append(f"revision {query.revision} {query.prior_reason}")
        text = " | ".join(dict.fromkeys(" ".join(value.split()) for value in fragments))
        provisional = replace(
            query,
            query_text=text,
            prior_reason=query.prior_reason + "|deterministic_query_facet_bound",
            query_digest="",
        )
        body = provisional.as_dict()
        body.pop("query_digest", None)
        bound = replace(provisional, query_digest=canonical_digest(body))
        self._bound_by_original_digest[query.query_digest] = bound
        self.bound_query_receipts.append(
            {
                "original_query_digest": query.query_digest,
                "bound_query_digest": bound.query_digest,
                "case_key": query.case_key,
                "evidence_slot_id": query.evidence_slot_id,
                "revision": query.revision,
                "query_facet_plan_digests": plan_digests,
                "query_text_digest": canonical_digest(text),
                "binding_state": "deterministic_external_query_facet_bound",
            }
        )
        return bound


def run_official_case_lane(
    *,
    case_key: str,
    catalog: Mapping[str, Any],
    plan_rows: Sequence[Mapping[str, Any]],
    runtime_root: Path,
    transport: SourceTransport,
    network_call_ceiling: int,
) -> dict[str, Any]:
    delegate = ProtectedFetchOfficialDiscoveryAdapterV4(
        catalog=catalog,
        case_key=case_key,
        runtime_root=runtime_root,
        transport=transport,
        network_call_ceiling=network_call_ceiling,
        document_ceiling_per_query=1,
    )
    adapter = FacetBoundOfficialAdapter(delegate=delegate, plan_rows=plan_rows)
    status = "completed"
    code = "official_case_candidate_generation_materialized"
    result: dict[str, Any] | None = None
    try:
        result = run_candidate_generation_v4(
            catalog=catalog,
            case_key=case_key,
            research_objective=(
                "Execute only the bound deterministic QueryFacet plan for current "
                "official-source candidate generation."
            ),
            adapter=adapter,
        )
    except CandidateGenerationInterrupted as exc:
        status = "failed_with_partial_result"
        code = exc.code
        result = dict(exc.partial_result)
    except Exception as exc:
        status = "failed"
        code = str(getattr(exc, "code", f"unexpected_project_failure:{type(exc).__name__}"))
    return {
        "case_key": case_key,
        "status": status,
        "terminal_code": code,
        "candidate_result": result,
        "network_calls": int(getattr(delegate, "network_calls", 0)),
        "document_fetches": int(getattr(delegate, "document_fetches", 0)),
        "bound_query_receipts": deepcopy(adapter.bound_query_receipts),
        "capture_namespace": f"official/{case_key.lower()}",
    }


def execute_external_combined(
    *,
    admission: Mapping[str, Any],
    policy: Mapping[str, Any],
    plan: Mapping[str, Any],
    catalog: Mapping[str, Any],
    execution_git_commit: str,
    runner_sha256: str,
    runtime_module_sha256: str,
    policy_sha256: str,
    runtime_root: Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    official_transport: SourceTransport,
    firecrawl_call: FirecrawlCall,
    observed_at: str,
    official_lane_executor: OfficialLaneExecutor = run_official_case_lane,
) -> dict[str, Any]:
    _validate_admission(
        admission=admission,
        policy=policy,
        plan=plan,
        execution_git_commit=execution_git_commit,
        runner_sha256=runner_sha256,
        runtime_module_sha256=runtime_module_sha256,
        policy_sha256=policy_sha256,
        observed_at=observed_at,
    )
    root = runtime_root.resolve()
    ledger_path = shared_ledger.path.resolve()
    if ledger_path == root or root in ledger_path.parents:
        raise S108ExternalCombinedError(
            "s1_08_external_combined_ledger_inside_runtime_root"
        )
    root.mkdir(parents=True, exist_ok=False)
    reservation = shared_ledger.reserve(
        admission_digest=str(admission["admission_digest"]),
        admission_id=str(admission["admission_id"]),
        scope=EXACT_LIVE_SCOPE,
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        runtime_identity=str(admission["runtime_identity"]),
        reserved_at=observed_at,
    )
    started = perf_counter()
    official_results: list[dict[str, Any]] = []
    official_rows = plan["official_plan_rows"]
    for case_key in CASES:
        case_rows = [row for row in official_rows if row["case_key"] == case_key]
        try:
            result = dict(
                official_lane_executor(
                    case_key=case_key,
                    catalog=catalog,
                    plan_rows=case_rows,
                    runtime_root=root / "official" / case_key.lower(),
                    transport=official_transport,
                    network_call_ceiling=16,
                )
            )
        except Exception as exc:
            result = {
                "case_key": case_key,
                "status": "failed",
                "terminal_code": str(
                    getattr(
                        exc,
                        "code",
                        f"unexpected_project_failure:{type(exc).__name__}",
                    )
                ),
                "candidate_result": None,
                "network_calls": 0,
                "document_fetches": 0,
                "bound_query_receipts": [],
            }
        official_results.append(result)
    shadow_results = _execute_shadow_lane(
        rows=plan["shadow_plan_rows"],
        endpoint=str(policy["lanes"]["firecrawl_shadow"]["endpoint"]),
        runtime_root=root / "firecrawl-shadow",
        firecrawl_call=firecrawl_call,
        timeout_seconds=int(policy["combined_budget"]["per_call_timeout_seconds"]),
    )
    official_network = sum(int(row.get("network_calls") or 0) for row in official_results)
    shadow_network = sum(bool(row.get("network_call_attempted")) for row in shadow_results)
    failures = sum(row.get("status") != "completed" for row in official_results) + sum(
        row.get("status") != "completed" for row in shadow_results
    )
    if official_network > 48 or shadow_network > 24:
        raise S108ExternalCombinedError(
            "s1_08_external_combined_network_budget_violated"
        )
    body = {
        "schema_version": TERMINAL_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "admission_digest": admission["admission_digest"],
        "run_id": admission["run_id"],
        "attempt_id": admission["attempt_id"],
        "status": "completed" if failures == 0 else "completed_with_typed_failures",
        "terminal_phase": "external_official_plus_firecrawl_shadow_combined",
        "terminal_code": "s1_08_external_combined_terminal_materialized",
        "plan_digest": plan["plan_digest"],
        "query_variant": "deterministic_local_query_facet_only",
        "official_case_results": official_results,
        "firecrawl_shadow_results": shadow_results,
        "observed_counts": {
            "official_cases_terminalized": len(official_results),
            "shadow_queries_terminalized": len(shadow_results),
            "official_network_calls": official_network,
            "shadow_provider_calls": shadow_network,
            "shadow_network_calls": shadow_network,
            "network_calls": official_network + shadow_network,
            "document_fetches": sum(
                int(row.get("document_fetches") or 0) for row in official_results
            ),
            "model_calls": 0,
            "embedding_calls": 0,
            "rerank_calls": 0,
            "evidence_promotions": 0,
            "retry_calls": 0,
            "fallback_calls": 0,
        },
        "authority_boundary": {
            "firecrawl_candidate_only": True,
            "provider_date_not_financial_authority": True,
            "evidence_gate_executed": False,
            "internal_retrieval_executed": False,
            "ranking_or_reranker_executed": False,
        },
        "elapsed_ms": int(round((perf_counter() - started) * 1000)),
        "observed_at": observed_at,
        "reservation_digest": reservation.reservation_digest,
    }
    terminal = {**body, "terminal_result_digest": canonical_digest(body)}
    _write_json(root / "terminal-result.json", terminal)
    receipt = shared_ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        terminal_status=str(terminal["status"]),
        terminal_phase=str(terminal["terminal_phase"]),
        terminal_code=str(terminal["terminal_code"]),
        terminal_result_digest=str(terminal["terminal_result_digest"]),
        finalized_at=observed_at,
    )
    return {**terminal, "shared_admission_receipt": receipt.as_dict()}


def _execute_shadow_lane(
    *,
    rows: Sequence[Mapping[str, Any]],
    endpoint: str,
    runtime_root: Path,
    firecrawl_call: FirecrawlCall,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    systemic_stop = ""
    for row in rows:
        ordinal = int(row["ordinal"])
        call_root = runtime_root / f"{ordinal:02d}-{str(row['plan_digest'])[:12]}"
        request_body = deepcopy(dict(row["request_body"]))
        safe_request = {
            "provider": "firecrawl_keyless_search",
            "endpoint": endpoint,
            "method": "POST",
            "request_body": request_body,
            "request_payload_digest": canonical_digest(request_body),
            "query_facet_plan_digest": row["plan_digest"],
            "authorization_header_sent": False,
            "cookie_header_sent": False,
        }
        safe_path = call_root / "safe-request.json"
        _write_json(safe_path, safe_request)
        started = perf_counter()
        attempted = False
        http_status = 0
        status = "failed"
        code = "firecrawl_shadow_typed_failure"
        projection: dict[str, Any] = {}
        failure: dict[str, Any] = {}
        refs: dict[str, Any] = {
            "safe_request": _relative(runtime_root, safe_path),
            "safe_request_sha256": sha256_file(safe_path),
        }
        if systemic_stop:
            code = "firecrawl_shadow_not_attempted_after_systemic_stop"
            failure = _safe_failure(code=code, detail=systemic_stop)
        else:
            attempted = True
            request_bytes = json.dumps(
                request_body, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
            try:
                http_status, raw = firecrawl_call(
                    endpoint, request_bytes, timeout_seconds
                )
                raw_path = call_root / "raw-response.bin"
                _write_bytes(raw_path, raw)
                refs.update(
                    {
                        "raw_response": _relative(runtime_root, raw_path),
                        "raw_response_sha256": sha256_file(raw_path),
                    }
                )
                if http_status in {401, 402, 403}:
                    systemic_stop = f"http_{http_status}"
                    code = "firecrawl_shadow_systemic_provider_rejection"
                    failure = _safe_failure(
                        code=code, detail=systemic_stop, http_status=http_status
                    )
                elif not 200 <= http_status < 300:
                    code = "firecrawl_shadow_provider_http_error"
                    failure = _safe_failure(
                        code=code,
                        detail="non_success_http_status",
                        http_status=http_status,
                    )
                else:
                    payload = json.loads(raw.decode("utf-8"))
                    projection = normalize_firecrawl_response(payload)
                    status = "completed"
                    code = "firecrawl_shadow_response_materialized"
            except Exception as exc:
                code = "firecrawl_shadow_transport_or_parse_error"
                failure = _safe_failure(code=code, detail=type(exc).__name__)
                failure_path = call_root / "typed-failure.json"
                _write_json(failure_path, failure)
                refs.update(
                    {
                        "typed_failure": _relative(runtime_root, failure_path),
                        "typed_failure_sha256": sha256_file(failure_path),
                    }
                )
        result = {
            "ordinal": ordinal,
            "plan_id": row["plan_id"],
            "plan_digest": row["plan_digest"],
            "case_key": row["case_key"],
            "evidence_slot_id": row["evidence_slot_id"],
            "evidence_owner_entity_key": row["evidence_owner_entity_key"],
            "language": row["language"],
            "status": status,
            "terminal_code": code,
            "network_call_attempted": attempted,
            "http_status": http_status,
            "provider_projection": projection,
            "failure": failure,
            "elapsed_ms": int(round((perf_counter() - started) * 1000)),
            "capture_refs": refs,
        }
        terminal_path = call_root / "terminal.json"
        _write_json(terminal_path, result)
        result["capture_refs"].update(
            {
                "call_terminal": _relative(runtime_root, terminal_path),
                "call_terminal_sha256": sha256_file(terminal_path),
            }
        )
        results.append(result)
    if len(results) != 24:
        raise S108ExternalCombinedError(
            "s1_08_external_combined_shadow_terminalization_incomplete"
        )
    return results


def _official_plan_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    exact = row.get("exact_lookup_queries") or []
    lexical = row.get("lexical_queries") or []
    if not exact or not lexical:
        raise S108ExternalCombinedError(
            "s1_08_external_combined_official_query_family_missing"
        )
    return {
        "plan_id": row["plan_id"],
        "plan_digest": row["plan_digest"],
        "case_key": row["case_key"],
        "evidence_slot_id": row["evidence_slot_id"],
        "evidence_owner_entity_key": row["evidence_owner_entity_key"],
        "relationship_direction": row["relationship_direction"],
        "language": row["language"],
        "exact_lookup_query": str(exact[0]),
        "lexical_query": str(lexical[0]),
        "preferred_domains": list(row.get("preferred_domains") or ()),
        "route_specific_filters": deepcopy(dict(row["route_specific_filters"])),
    }


def _shadow_plan_projection(
    row: Mapping[str, Any], *, ordinal: int
) -> dict[str, Any]:
    semantic = row.get("semantic_queries") or []
    if not semantic:
        raise S108ExternalCombinedError(
            "s1_08_external_combined_shadow_query_family_missing"
        )
    request = {"query": str(semantic[0]), "limit": 10, "sources": ["web"]}
    return {
        "ordinal": ordinal,
        "plan_id": row["plan_id"],
        "plan_digest": row["plan_digest"],
        "case_key": row["case_key"],
        "evidence_slot_id": row["evidence_slot_id"],
        "evidence_owner_entity_key": row["evidence_owner_entity_key"],
        "relationship_direction": row["relationship_direction"],
        "language": row["language"],
        "request_body": request,
        "request_payload_digest": canonical_digest(request),
        "negative_queries": list(row.get("negative_queries") or ()),
        "route_specific_filters": deepcopy(dict(row["route_specific_filters"])),
    }


def _validate_admission(**values: Any) -> None:
    admission = values["admission"]
    body = {key: deepcopy(value) for key, value in admission.items() if key != "admission_digest"}
    valid = (
        admission.get("schema_version") == ADMISSION_SCHEMA
        and admission.get("contract_ref") == CONTRACT_REF
        and admission.get("scope") == EXACT_LIVE_SCOPE
        and admission.get("state") == "issued_unconsumed"
        and admission.get("admission_digest") == canonical_digest(body)
        and admission.get("execution_git_commit") == values["execution_git_commit"]
        and admission.get("runner_sha256") == values["runner_sha256"]
        and admission.get("runtime_module_sha256") == values["runtime_module_sha256"]
        and admission.get("policy_sha256") == values["policy_sha256"]
        and admission.get("plan_digest") == values["plan"].get("plan_digest")
        and admission.get("budget") == values["policy"].get("combined_budget")
        and _time(values["observed_at"]) <= _time(str(admission.get("expires_at") or ""))
    )
    if not valid:
        raise S108ExternalCombinedError(
            "s1_08_external_combined_admission_invalid"
        )


def _plan_sort_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row["case_key"]),
        str(row["evidence_slot_id"]),
        str(row["evidence_owner_entity_key"]),
        str(row["language"]),
    )


def _safe_failure(*, code: str, detail: str, http_status: int = 0) -> dict[str, Any]:
    return {
        "phase": "provider_transport_or_parse",
        "code": code,
        "detail_class": detail[:200],
        "http_status": int(http_status),
        "retry_allowed": False,
        "credential_or_header_material_included": False,
    }


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _write_bytes(
        path,
        (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise S108ExternalCombinedError("s1_08_external_combined_time_invalid") from exc
    if parsed.tzinfo is None:
        raise S108ExternalCombinedError("s1_08_external_combined_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _digest_or_git(value: Any) -> bool:
    text = str(value or "")
    return len(text) in {40, 64} and all(character in "0123456789abcdef" for character in text)


__all__ = [
    "ADMISSION_SCHEMA",
    "CASES",
    "CONTRACT_REF",
    "EXACT_LIVE_SCOPE",
    "FacetBoundOfficialAdapter",
    "PLAN_SCHEMA",
    "POLICY_SCHEMA",
    "S108ExternalCombinedError",
    "TERMINAL_SCHEMA",
    "ZERO_CALL_SCOPE",
    "compile_external_combined_plan",
    "execute_external_combined",
    "issue_external_combined_admission",
    "load_bound_inputs",
    "load_external_combined_policy",
    "run_official_case_lane",
    "sha256_file",
    "sha256_utf8_lf",
]
