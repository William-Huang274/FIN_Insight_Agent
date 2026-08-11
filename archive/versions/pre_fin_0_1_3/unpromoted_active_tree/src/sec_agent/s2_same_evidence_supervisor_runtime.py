from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s2_same_evidence_experiment_runtime import (
    SECTION_IDS,
    S2SameEvidenceExperimentError,
    _case_identity,
    _compile_specialist_context,
    _evidence_index,
    _provider_kwargs,
    _validate_case_input,
    _validate_lead,
    _validate_specialist,
    _validate_synthesis,
    _validate_verifier,
    _validate_writer,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


SUPERVISOR_PLAN_SCHEMA = "fin_ia_0_1_3_s2_06_supervisor_plan_v1_1"
CORRECTED_CAPTURE_SCHEMA = "fin_ia_0_1_3_s2_06_corrected_capture_v1_1"
CORRECTED_CANDIDATE_SCHEMA = "fin_ia_0_1_3_s2_06_corrected_candidate_v1_1"
CORRECTED_TERMINAL_SCHEMA = "fin_ia_0_1_3_s2_06_corrected_terminal_v1_1"
CORRECTED_ADMISSION_SCHEMA = "fin_ia_0_1_3_s2_06_corrected_admission_v1_1"
CORRECTED_NODE_ENVELOPE_SCHEMA = "fin_ia_0_1_3_s2_06_corrected_node_envelope_v1_0"
CORRECTION_CLOSURE_RECEIPT_SCHEMA = "fin_ia_0_1_3_s2_06_correction_closure_receipt_v1_0"
CORRECTED_SCOPE = "FIN_0_1_3_S2_06_CASE_ISOLATED_CORRECTED_CANDIDATE_V1_1_EXACT_ONCE"
ProviderCall = Callable[..., Mapping[str, Any]]

_ACTION_CODES = {
    "return_to_originating_node",
    "return_to_verifier",
    "deterministic_source_bound_deletion",
    "retain_typed_nonfactual_request",
}
_NODE_ORDER = {
    "lead": 0,
    "specialist": 1,
    "synthesis": 2,
    "writer": 3,
    "verifier": 4,
}
_PATH_PART = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?")
_NUMERIC_PLACEHOLDER = re.compile(r"\[NUM:([^\]]+)\]")
_RAW_NARRATIVE_NUMERIC = re.compile(
    r"(?:[$€£]\s*\d+(?:[.,]\d+)*)|"
    r"(?:\d+(?:[.,]\d+)+\s*%?)|"
    r"(?:\d+\s*%)|"
    r"(?:\d+(?:\.\d+)?\s*(?:USD|CNY|EUR|JPY|billion|million|trillion|bps)\b)",
    flags=re.IGNORECASE,
)
_CASE_AUTHORITY_ALIAS_FIELDS = ("evidence_ids", "gap_ids")
_CASE_AUTHORITY_PROMPT_RULE = (
    "Every node directive, including Verifier, must select at least one supplied "
    "Evidence or Gap alias; Numeric aliases alone are insufficient. "
)

_CORRECTION_OBJECTIVE_RULES: dict[str, dict[str, str]] = {
    "explicit_counterevidence_surface_empty": {
        "required_resolution": (
            "Select at least one supplied counterevidence ID, or explicitly mark the "
            "objective typed_unresolved with a supplied Gap ID."
        ),
        "closure_rule": "counterevidence_nonempty_or_typed_unresolved_with_gap",
        "unresolved_policy": "typed_unresolved_requires_selected_gap",
    },
    "unbound_material_numeric_surface": {
        "required_resolution": (
            "Remove the unsupported numeric surface or express an exact supplied value "
            "with a [NUM:<numeric_alias>] protected reference."
        ),
        "closure_rule": "no_unprotected_numeric_narrative_and_no_unknown_placeholder",
        "unresolved_policy": "typed_unresolved_requires_selected_gap",
    },
    "directional_margin_sharpened_to_unsupported_range": {
        "required_resolution": (
            "Preserve the exact directional source phrase; do not convert it to a numeric point or range."
        ),
        "closure_rule": "offending_tokens_absent_and_no_unprotected_numeric_narrative",
        "unresolved_policy": "typed_unresolved_requires_selected_gap",
    },
    "specialist_assigned_pack_coverage_incomplete": {
        "required_resolution": "Consume every assigned Evidence and Gap ID in the corrected specialist output.",
        "closure_rule": "existing_specialist_pack_coverage_validator_passes",
        "unresolved_policy": "typed_unresolved_not_allowed",
    },
    "writer_case_pack_coverage_incomplete": {
        "required_resolution": "Cover every case Evidence and Gap ID across the corrected writer sections.",
        "closure_rule": "existing_writer_pack_coverage_validator_passes",
        "unresolved_policy": "typed_unresolved_not_allowed",
    },
    "verifier_missed_material_failure": {
        "required_resolution": "Recheck the corrected graph and return every remaining material finding.",
        "closure_rule": "existing_verifier_validator_and_post_graph_evaluator_pass",
        "unresolved_policy": "typed_unresolved_not_allowed",
    },
    "hypothetical_planning_threshold": {
        "required_resolution": "Keep the threshold explicitly hypothetical and nonfactual, or remove it.",
        "closure_rule": "retained_nonfactual_request_not_promoted_as_fact",
        "unresolved_policy": "typed_unresolved_requires_selected_gap",
    },
}


class S2SupervisorRuntimeError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def compile_case_aliases(case_input: Mapping[str, Any]) -> dict[str, list[str]]:
    """Compile opaque case-local aliases without adding financial content."""

    _validate_case_input(case_input)
    evidence_ids = [str(row["evidence_id"]) for row in case_input["evidence_items"]]
    gap_ids = [str(row["gap_id"]) for row in case_input["explicit_gaps"]]
    numeric_aliases: list[str] = []
    for row in case_input["derived_numeric"]:
        numeric_aliases.append("derived::" + str(row["metric"]))
    for evidence in case_input["evidence_items"]:
        for numeric in evidence.get("numeric_facts", []):
            numeric_aliases.append(
                "evidence::" + str(evidence["evidence_id"]) + "::" + str(numeric["metric"])
            )
    if len(numeric_aliases) != len(set(numeric_aliases)):
        raise S2SupervisorRuntimeError("s2_06_numeric_alias_collision")
    return {
        "evidence_ids": evidence_ids,
        "numeric_aliases": numeric_aliases,
        "gap_ids": gap_ids,
    }


def compile_numeric_fact_views(case_input: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Expose exact, semantic facts for reasoning without granting prose authority."""

    _validate_case_input(case_input)
    rows: list[dict[str, Any]] = []
    for numeric in case_input["derived_numeric"]:
        alias = "derived::" + str(numeric["metric"])
        rows.append(
            {
                "numeric_alias": alias,
                "semantic_name": str(numeric["metric"]),
                "exact_value": str(numeric["value"]),
                "unit": str(numeric["unit"]),
                "formula": str(numeric.get("formula") or ""),
                "source_evidence_id": None,
                "display_surface": f"{numeric['value']} {numeric['unit']}",
                "authority": "derived_numeric_program",
            }
        )
    for evidence in case_input["evidence_items"]:
        for numeric in evidence.get("numeric_facts", []):
            alias = "evidence::" + str(evidence["evidence_id"]) + "::" + str(numeric["metric"])
            rows.append(
                {
                    "numeric_alias": alias,
                    "semantic_name": str(numeric["metric"]),
                    "exact_value": str(numeric["value"]),
                    "unit": str(numeric["unit"]),
                    "formula": None,
                    "source_evidence_id": str(evidence["evidence_id"]),
                    "display_surface": f"{numeric['value']} {numeric['unit']}",
                    "authority": "source_bound_numeric_fact",
                }
            )
    aliases = [str(row["numeric_alias"]) for row in rows]
    if len(aliases) != len(set(aliases)):
        raise S2SupervisorRuntimeError("s2_06_numeric_fact_view_alias_collision")
    return rows


def compile_correction_objectives(spec: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Compile complete, model-visible objectives from the same finding source."""

    objectives: dict[str, dict[str, Any]] = {}
    for finding in spec["visible_findings"]:
        code = str(finding["code"])
        rule = _CORRECTION_OBJECTIVE_RULES.get(
            code,
            {
                "required_resolution": (
                    "Resolve the visible finding without inventing facts, numeric precision or authority."
                ),
                "closure_rule": "post_graph_finding_absent_after_revalidation",
                "unresolved_policy": "typed_unresolved_requires_selected_gap",
            },
        )
        correction_id = str(finding["correction_id"])
        objectives[correction_id] = {
            "correction_id": correction_id,
            "finding_code": code,
            "severity": str(finding["severity"]),
            "target_node_ref": str(finding["node_ref"]),
            "target_path": str(finding.get("path") or ""),
            "offending_tokens": list(finding.get("tokens") or []),
            "action_code": str(finding["action_code"]),
            "required_resolution": rule["required_resolution"],
            "closure_rule": rule["closure_rule"],
            "unresolved_policy": rule["unresolved_policy"],
        }
    return objectives


def _case_authority_output_schema() -> dict[str, Any]:
    """Compile the same non-empty authority invariant used by local validation."""

    return {
        "anyOf": [
            {"properties": {field: {"minItems": 1}}}
            for field in _CASE_AUTHORITY_ALIAS_FIELDS
        ]
    }


def _has_case_authority(directive: Mapping[str, Any]) -> bool:
    return any(bool(directive.get(field)) for field in _CASE_AUTHORITY_ALIAS_FIELDS)


def compile_supervisor_plan_spec(
    *,
    boundary: Mapping[str, Any],
    case_input: Mapping[str, Any],
    raw_outputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Create the one source used by prompt, schema, validator and fixtures."""

    case_key = str(case_input.get("case_key") or "")
    _validate_case_input(case_input)
    _validate_boundary_identity(boundary, case_key)
    _validate_raw_output_identity(raw_outputs, case_key)
    encoded_raw = json.dumps(raw_outputs, ensure_ascii=False, sort_keys=True)
    for match in re.finditer(r"\b(DELL|MU|NVDA)_(?:E|G)\d+\b", encoded_raw):
        if match.group(1) != case_key:
            raise S2SupervisorRuntimeError("s2_06_cross_case_raw_alias_forbidden")
    aliases = compile_case_aliases(case_input)
    corrections = boundary.get("corrections")
    if not isinstance(corrections, list) or not corrections:
        raise S2SupervisorRuntimeError("s2_06_boundary_corrections_required")

    grouped: dict[str, dict[str, Any]] = {}
    deterministic_ids: list[str] = []
    retained_ids: list[str] = []
    visible_findings: list[dict[str, Any]] = []
    for row in corrections:
        if not isinstance(row, Mapping):
            raise S2SupervisorRuntimeError("s2_06_boundary_correction_invalid")
        correction_id = str(row.get("correction_id") or "")
        if not correction_id.startswith(case_key + "-CORR-"):
            raise S2SupervisorRuntimeError("s2_06_correction_id_not_case_qualified")
        finding = row.get("source_finding")
        if not isinstance(finding, Mapping):
            raise S2SupervisorRuntimeError("s2_06_source_finding_invalid")
        action_code = str(row.get("action_code") or "")
        if action_code not in _ACTION_CODES:
            raise S2SupervisorRuntimeError("s2_06_action_code_unexecutable")
        node_ref = _canonical_node_ref(str(finding.get("node_ref") or ""), raw_outputs)
        visible_findings.append(
            {
                "correction_id": correction_id,
                "severity": str(finding.get("severity") or ""),
                "code": str(finding.get("code") or ""),
                "node_ref": node_ref,
                "path": str(finding.get("path") or ""),
                "tokens": [str(value) for value in finding.get("tokens", [])],
                "action_code": action_code,
            }
        )
        if action_code == "deterministic_source_bound_deletion":
            deterministic_ids.append(correction_id)
            continue
        if action_code == "retain_typed_nonfactual_request":
            retained_ids.append(correction_id)
            continue
        group = grouped.setdefault(
            node_ref,
            {"node_ref": node_ref, "correction_ids": [], "action_codes": []},
        )
        group["correction_ids"].append(correction_id)
        if action_code not in group["action_codes"]:
            group["action_codes"].append(action_code)

    directive_requirements = sorted(grouped.values(), key=lambda row: _node_sort_key(row["node_ref"]))
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version", "case_key", "raw_run_id", "node_directives",
            "deterministic_correction_ids", "retained_nonfactual_request_ids",
        ],
        "properties": {
            "schema_version": {"type": "string", "const": SUPERVISOR_PLAN_SCHEMA},
            "case_key": {"type": "string", "const": case_key},
            "raw_run_id": {
                "type": "string",
                "const": str(boundary["raw_binding"]["run_id"]),
            },
            "node_directives": {
                "type": "array",
                "minItems": len(directive_requirements),
                "maxItems": len(directive_requirements),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    **_case_authority_output_schema(),
                    "required": [
                        "node_ref", "correction_ids", "action_codes",
                        "evidence_ids", "numeric_aliases", "gap_ids",
                    ],
                    "properties": {
                        "node_ref": {"type": "string"},
                        "correction_ids": {"type": "array", "items": {"type": "string"}},
                        "action_codes": {"type": "array", "items": {"type": "string"}},
                        "evidence_ids": {"type": "array", "items": {"type": "string"}},
                        "numeric_aliases": {"type": "array", "items": {"type": "string"}},
                        "gap_ids": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "deterministic_correction_ids": {"type": "array", "items": {"type": "string"}},
            "retained_nonfactual_request_ids": {"type": "array", "items": {"type": "string"}},
        },
    }
    return {
        "schema_version": "fin_ia_0_1_3_s2_06_supervisor_plan_spec_v1_2",
        "case_key": case_key,
        "raw_binding": {
            "run_id": boundary["raw_binding"]["run_id"],
            "terminal_digest": boundary["raw_binding"]["terminal_digest"],
        },
        "visible_findings": visible_findings,
        "directive_requirements": directive_requirements,
        "deterministic_correction_ids": deterministic_ids,
        "retained_nonfactual_request_ids": retained_ids,
        "case_aliases": aliases,
        "numeric_fact_views": compile_numeric_fact_views(case_input),
        "output_schema": schema,
    }


def compile_supervisor_request(
    *,
    spec: Mapping[str, Any],
    raw_outputs: Mapping[str, Any],
    policy: Mapping[str, Any],
    corrected_run_id: str,
) -> dict[str, Any]:
    """Compile a provider request containing visible, case-local inputs only."""

    provider = policy["provider"]
    payload = {
        "case_key": spec["case_key"],
        "raw_binding": deepcopy(spec["raw_binding"]),
        "visible_findings": deepcopy(spec["visible_findings"]),
        "directive_requirements": deepcopy(spec["directive_requirements"]),
        "case_aliases": deepcopy(spec["case_aliases"]),
        "raw_outputs": deepcopy(dict(raw_outputs)),
        "required_output_contract": deepcopy(spec["output_schema"]),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    lowered = encoded.lower()
    for forbidden in ("expected_thesis", "strongest_counter_thesis", "codex_gold", "evaluator_only"):
        if forbidden in lowered:
            raise S2SupervisorRuntimeError("s2_06_forbidden_hidden_surface_in_request")
    maximum_chars = int(policy["capacity"]["maximum_input_characters_per_call"])
    if len(encoded) > maximum_chars:
        raise S2SupervisorRuntimeError("s2_06_supervisor_input_capacity_exceeded")
    return {
        "llm_backend": provider["backend"],
        "base_url": provider["base_url"],
        "chat_completions_path": provider["chat_completions_path"],
        "model": provider["model"],
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a case-isolated correction planner. Return one JSON object only. "
                    "Do not write a report, corrected prose, financial facts, target thesis or score. "
                    "For each required node, select only supplied case-local Evidence, Numeric and Gap aliases. "
                    + _CASE_AUTHORITY_PROMPT_RULE
                    + "Preserve the exact node, correction and action identifiers."
                ),
            },
            {"role": "user", "content": encoded},
        ],
        "response_format": {"type": "json_object"},
        "api_key_env": provider["api_key_env"],
        "temperature": 0.0,
        "max_tokens": 6000,
        "timeout_s": int(policy["capacity"]["timeout_seconds_per_call"]),
        "stream": False,
        "enable_thinking": False,
        "role": "fin013_s2_06_supervisor_plan",
        "profile": str(spec["case_key"]) + "::supervisor",
        "trace_tags": {
            "corrected_run_id": corrected_run_id,
            "case_key": spec["case_key"],
            "node_type": "supervisor_plan",
        },
        "max_transport_attempts": 1,
    }


def compile_fixture_supervisor_plan(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Generate the positive full-fake output from the same compiled spec."""

    aliases = spec["case_aliases"]
    return {
        "schema_version": SUPERVISOR_PLAN_SCHEMA,
        "case_key": spec["case_key"],
        "raw_run_id": spec["raw_binding"]["run_id"],
        "node_directives": [
            {
                **deepcopy(row),
                "evidence_ids": list(aliases["evidence_ids"]),
                "numeric_aliases": list(aliases["numeric_aliases"]),
                "gap_ids": list(aliases["gap_ids"]),
            }
            for row in spec["directive_requirements"]
        ],
        "deterministic_correction_ids": list(spec["deterministic_correction_ids"]),
        "retained_nonfactual_request_ids": list(spec["retained_nonfactual_request_ids"]),
    }


def validate_supervisor_plan(plan: Mapping[str, Any], spec: Mapping[str, Any]) -> None:
    expected_keys = {
        "schema_version", "case_key", "raw_run_id", "node_directives",
        "deterministic_correction_ids", "retained_nonfactual_request_ids",
    }
    if set(plan) != expected_keys:
        raise S2SupervisorRuntimeError("s2_06_supervisor_plan_keys_invalid")
    if (
        plan.get("schema_version") != SUPERVISOR_PLAN_SCHEMA
        or plan.get("case_key") != spec["case_key"]
        or plan.get("raw_run_id") != spec["raw_binding"]["run_id"]
    ):
        raise S2SupervisorRuntimeError("s2_06_supervisor_plan_identity_invalid")
    if plan.get("deterministic_correction_ids") != spec["deterministic_correction_ids"]:
        raise S2SupervisorRuntimeError("s2_06_supervisor_deterministic_partition_invalid")
    if plan.get("retained_nonfactual_request_ids") != spec["retained_nonfactual_request_ids"]:
        raise S2SupervisorRuntimeError("s2_06_supervisor_retained_partition_invalid")
    directives = plan.get("node_directives")
    requirements = spec["directive_requirements"]
    if not isinstance(directives, list) or len(directives) != len(requirements):
        raise S2SupervisorRuntimeError("s2_06_supervisor_directive_count_invalid")
    allowed = spec["case_aliases"]
    allowed_evidence = set(allowed["evidence_ids"])
    allowed_numeric = set(allowed["numeric_aliases"])
    allowed_gaps = set(allowed["gap_ids"])
    for directive, requirement in zip(directives, requirements):
        if not isinstance(directive, Mapping) or set(directive) != {
            "node_ref", "correction_ids", "action_codes", "evidence_ids",
            "numeric_aliases", "gap_ids",
        }:
            raise S2SupervisorRuntimeError("s2_06_supervisor_directive_shape_invalid")
        for key in ("node_ref", "correction_ids", "action_codes"):
            if directive.get(key) != requirement[key]:
                raise S2SupervisorRuntimeError("s2_06_supervisor_directive_binding_invalid")
        evidence = _unique_string_list(directive.get("evidence_ids"), "evidence")
        numeric = _unique_string_list(directive.get("numeric_aliases"), "numeric")
        gaps = _unique_string_list(directive.get("gap_ids"), "gap")
        if not set(evidence) <= allowed_evidence or not set(numeric) <= allowed_numeric or not set(gaps) <= allowed_gaps:
            raise S2SupervisorRuntimeError("s2_06_supervisor_cross_case_or_unknown_alias")
        if not _has_case_authority(
            {"evidence_ids": evidence, "gap_ids": gaps}
        ):
            raise S2SupervisorRuntimeError("s2_06_supervisor_empty_case_authority")


def compile_affected_node_closure(
    *,
    plan: Mapping[str, Any],
    spec: Mapping[str, Any],
    raw_outputs: Mapping[str, Any],
) -> list[str]:
    """Return the exact graph nodes that must be called again, in graph order."""

    validate_supervisor_plan(plan, spec)
    specialists = ["specialist:" + str(row["unit_id"]) for row in raw_outputs["specialists"]]
    selected: set[str] = set()
    for directive in plan["node_directives"]:
        origin = str(directive["node_ref"])
        selected.update(_downstream_closure(origin, specialists, include_origin=True))
    finding_by_id = {row["correction_id"]: row for row in spec["visible_findings"]}
    for correction_id in plan["deterministic_correction_ids"]:
        origin = str(finding_by_id[correction_id]["node_ref"])
        selected.update(_downstream_closure(origin, specialists, include_origin=False))
    return sorted(selected, key=_node_sort_key)


def compile_capacity_proof(
    *,
    plan: Mapping[str, Any],
    spec: Mapping[str, Any],
    raw_outputs: Mapping[str, Any],
) -> dict[str, Any]:
    closure = compile_affected_node_closure(plan=plan, spec=spec, raw_outputs=raw_outputs)
    corrected_graph_calls = len(closure)
    provider_calls = corrected_graph_calls + 1
    return {
        "schema_version": "fin_ia_0_1_3_s2_06_capacity_proof_v1_0",
        "case_key": spec["case_key"],
        "supervisor_planner_calls": 1,
        "corrected_graph_calls": corrected_graph_calls,
        "provider_calls": provider_calls,
        "corrected_graph_ceiling": 10,
        "provider_call_ceiling": 11,
        "pass": corrected_graph_calls <= 10 and provider_calls <= 11,
        "affected_nodes": closure,
    }


def compile_corrected_admission_candidate(
    *,
    spec: Mapping[str, Any],
    raw_outputs: Mapping[str, Any],
    corrected_run_id: str,
    corrected_attempt_id: str,
    admission_id: str,
    issued_at: str,
    expires_at: str,
    credential_present: bool,
    provider_execution_authorized: bool,
) -> dict[str, Any]:
    """Compile a candidate envelope; calling this does not grant authority."""

    if not all((corrected_run_id, corrected_attempt_id, admission_id)):
        raise S2SupervisorRuntimeError("s2_06_corrected_admission_identity_required")
    if corrected_run_id == spec["raw_binding"]["run_id"]:
        raise S2SupervisorRuntimeError("s2_06_fresh_corrected_identity_required")
    fixture_plan = compile_fixture_supervisor_plan(spec)
    capacity = compile_capacity_proof(
        plan=fixture_plan, spec=spec, raw_outputs=raw_outputs
    )
    if not capacity["pass"]:
        raise S2SupervisorRuntimeError("s2_06_corrected_call_capacity_exceeded")
    body = {
        "schema_version": CORRECTED_ADMISSION_SCHEMA,
        "admission_id": admission_id,
        "scope": CORRECTED_SCOPE,
        "case_key": spec["case_key"],
        "raw_binding": deepcopy(spec["raw_binding"]),
        "corrected_run_id": corrected_run_id,
        "corrected_attempt_id": corrected_attempt_id,
        "runtime_identity": corrected_run_id + "::" + corrected_attempt_id,
        "capacity_proof": capacity,
        "retry_count": 0,
        "fallback_count": 0,
        "credential_present": credential_present,
        "provider_execution_authorized": provider_execution_authorized,
        "issued_at": issued_at,
        "expires_at": expires_at,
    }
    return {**body, "admission_digest": canonical_digest(body)}


def execute_corrected_candidate(
    *,
    admission: Mapping[str, Any],
    boundary: Mapping[str, Any],
    case_input: Mapping[str, Any],
    raw_outputs: Mapping[str, Any],
    policy: Mapping[str, Any],
    corrected_run_id: str,
    corrected_attempt_id: str,
    runtime_root: Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    provider_call: ProviderCall,
    observed_at: str,
) -> dict[str, Any]:
    """Execute one capture-first, no-retry, case-isolated corrected candidate."""

    spec = compile_supervisor_plan_spec(
        boundary=boundary, case_input=case_input, raw_outputs=raw_outputs
    )
    correction_objectives = compile_correction_objectives(spec)
    _validate_corrected_admission(
        admission,
        spec=spec,
        raw_outputs=raw_outputs,
        corrected_run_id=corrected_run_id,
        corrected_attempt_id=corrected_attempt_id,
        observed_at=observed_at,
    )
    root = runtime_root.resolve()
    ledger_path = shared_ledger.path.resolve()
    if ledger_path == root or root in ledger_path.parents:
        raise S2SupervisorRuntimeError("s2_06_shared_ledger_inside_runtime_root")
    root.mkdir(parents=True, exist_ok=False)
    supervisor_captures = root / "supervisor_augmented" / "captures"
    corrected_captures = root / "corrected_candidate" / "captures"
    supervisor_captures.mkdir(parents=True)
    corrected_captures.mkdir(parents=True)
    reservation = shared_ledger.reserve(
        admission_digest=str(admission["admission_digest"]),
        admission_id=str(admission["admission_id"]),
        scope=str(admission["scope"]),
        run_id=corrected_run_id,
        attempt_id=corrected_attempt_id,
        runtime_identity=str(admission["runtime_identity"]),
        reserved_at=observed_at,
    )
    calls: list[dict[str, Any]] = []
    outputs = deepcopy(dict(raw_outputs))
    terminal_code = "s2_06_corrected_candidate_incomplete"
    terminal_phase = "supervisor_plan"
    candidate: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    capacity_proof: dict[str, Any] | None = None
    closure_receipts: list[dict[str, Any]] = []
    try:
        kwargs = compile_supervisor_request(
            spec=spec,
            raw_outputs=raw_outputs,
            policy=policy,
            corrected_run_id=corrected_run_id,
        )
        row, parsed = _capture_provider_call(
            kwargs=kwargs,
            provider_call=provider_call,
            captures_dir=supervisor_captures,
            capture_track="supervisor_augmented",
            case_key=str(case_input["case_key"]),
            node_type="supervisor_plan",
            node_id="supervisor",
            call_index=1,
        )
        calls.append(row)
        plan = parsed
        validate_supervisor_plan(plan, spec)
        capacity_proof = compile_capacity_proof(plan=plan, spec=spec, raw_outputs=raw_outputs)
        if not capacity_proof["pass"]:
            raise S2SupervisorRuntimeError("s2_06_corrected_call_capacity_exceeded")

        _apply_deterministic_corrections(outputs, plan=plan, spec=spec)
        for correction_id in plan["deterministic_correction_ids"]:
            objective = correction_objectives[correction_id]
            closure_receipts.append(
                {
                    "schema_version": CORRECTION_CLOSURE_RECEIPT_SCHEMA,
                    "correction_id": correction_id,
                    "node_ref": objective["target_node_ref"],
                    "status": "closed",
                    "evidence_ids": [],
                    "gap_ids": [],
                    "resolution_summary": "Local source-bound deletion applied to the corrected copy only.",
                    "closure_rule": objective["closure_rule"],
                    "validation_status": "deterministic_correction_applied",
                }
            )
        for correction_id in plan["retained_nonfactual_request_ids"]:
            objective = correction_objectives[correction_id]
            closure_receipts.append(
                {
                    "schema_version": CORRECTION_CLOSURE_RECEIPT_SCHEMA,
                    "correction_id": correction_id,
                    "node_ref": objective["target_node_ref"],
                    "status": "closed",
                    "evidence_ids": [],
                    "gap_ids": [],
                    "resolution_summary": "Typed nonfactual request retained outside financial fact authority.",
                    "closure_rule": objective["closure_rule"],
                    "validation_status": "nonfactual_request_not_promoted",
                }
            )
        affected = list(capacity_proof["affected_nodes"])
        directives = {str(row["node_ref"]): deepcopy(dict(row)) for row in plan["node_directives"]}
        for node_ref in affected:
            terminal_phase = node_ref
            node_type, node_id, context = _compile_corrected_node_context(
                node_ref=node_ref,
                outputs=outputs,
                raw_outputs=raw_outputs,
                case_input=case_input,
                directive=directives.get(node_ref),
                correction_objectives=correction_objectives,
                numeric_fact_views=spec["numeric_fact_views"],
            )
            kwargs = _corrected_node_kwargs(
                node_type=node_type,
                node_id=node_id,
                context=context,
                case_input=case_input,
                policy=policy,
                corrected_run_id=corrected_run_id,
            )
            row, parsed = _capture_provider_call(
                kwargs=kwargs,
                provider_call=provider_call,
                captures_dir=corrected_captures,
                capture_track="corrected_candidate",
                case_key=str(case_input["case_key"]),
                node_type=node_type,
                node_id=node_id,
                call_index=len(calls) + 1,
            )
            calls.append(row)
            _validate_and_store_node(
                node_ref=node_ref,
                parsed=parsed,
                outputs=outputs,
                case_input=case_input,
                policy=policy,
                correction_contract=context,
                closure_receipts=closure_receipts,
            )

        from sec_agent.s2_same_evidence_layered_evaluation import evaluate_raw_chain

        evaluation = evaluate_raw_chain(
            outputs, case_input=case_input, policy=policy, section_ids=SECTION_IDS
        )
        if evaluation.get("material_failure") is not False:
            raise S2SupervisorRuntimeError("s2_06_corrected_candidate_material_findings_remain")
        unresolved_ids = {
            str(row["correction_id"])
            for row in closure_receipts
            if row["status"] not in {"closed", "typed_unresolved"}
        }
        expected_receipt_ids = {str(row["correction_id"]) for row in correction_objectives.values()}
        observed_receipt_ids = {str(row["correction_id"]) for row in closure_receipts}
        if unresolved_ids or observed_receipt_ids != expected_receipt_ids:
            raise S2SupervisorRuntimeError("s2_06_correction_closure_incomplete")
        candidate_body = {
            "schema_version": CORRECTED_CANDIDATE_SCHEMA,
            "case_key": case_input["case_key"],
            "corrected_run_id": corrected_run_id,
            "corrected_attempt_id": corrected_attempt_id,
            "raw_binding": deepcopy(spec["raw_binding"]),
            "supervisor_plan_digest": canonical_digest(plan),
            "outputs": outputs,
            "evaluation": evaluation,
            "correction_closure_receipts": deepcopy(closure_receipts),
            "business_promotable": False,
            "observed_at": observed_at,
        }
        candidate = {**candidate_body, "candidate_digest": canonical_digest(candidate_body)}
        _write_exclusive(root / "corrected_candidate" / "candidate.json", candidate)
        terminal_phase = "candidate_frozen"
        terminal_code = (
            "s2_06_corrected_candidate_frozen_quality_pass"
            if evaluation.get("material_failure") is False
            else "s2_06_corrected_candidate_frozen_with_material_findings"
        )
    except (S2SupervisorRuntimeError, S2SameEvidenceExperimentError) as exc:
        terminal_code = getattr(exc, "code", str(exc))

    captured_calls = _captured_call_rows(root)
    closure_artifact = {
        "schema_version": "fin_ia_0_1_3_s2_06_correction_closure_ledger_v1_0",
        "case_key": case_input["case_key"],
        "corrected_run_id": corrected_run_id,
        "receipts": deepcopy(closure_receipts),
    }
    _write_exclusive(root / "corrected_candidate" / "correction_closure_receipts.json", closure_artifact)
    usage = _usage(captured_calls, policy)
    if usage["estimated_cost_usd"] > 0.18:
        terminal_code = "s2_06_corrected_cost_ceiling_exceeded"
        candidate = None
    terminal_body = {
        "schema_version": CORRECTED_TERMINAL_SCHEMA,
        "case_key": case_input["case_key"],
        "corrected_run_id": corrected_run_id,
        "corrected_attempt_id": corrected_attempt_id,
        "raw_binding": deepcopy(spec["raw_binding"]),
        "status": "terminal_completed" if candidate is not None else "terminal_failed_no_retry",
        "terminal_phase": terminal_phase,
        "terminal_code": terminal_code,
        "candidate_frozen": candidate is not None,
        "candidate_digest": candidate.get("candidate_digest") if candidate else None,
        "supervisor_plan_digest": canonical_digest(plan) if plan else None,
        "capacity_proof": capacity_proof,
        "correction_closure_receipts": deepcopy(closure_receipts),
        "call_results": captured_calls,
        "completed_calls": len(captured_calls),
        "usage": usage,
        "retry_count": 0,
        "fallback_count": 0,
        "raw_mutations": 0,
        "hidden_scoring_executed": False,
        "business_promotable": False,
        "observed_at": observed_at,
        "reservation_digest": reservation.reservation_digest,
    }
    terminal = {**terminal_body, "terminal_result_digest": canonical_digest(terminal_body)}
    _write_exclusive(root / "corrected_candidate" / "terminal_result.json", terminal)
    receipt = shared_ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=corrected_run_id,
        attempt_id=corrected_attempt_id,
        terminal_status=str(terminal["status"]),
        terminal_phase=str(terminal["terminal_phase"]),
        terminal_code=str(terminal["terminal_code"]),
        terminal_result_digest=str(terminal["terminal_result_digest"]),
        finalized_at=observed_at,
    )
    return {**terminal, "shared_admission_receipt": receipt.as_dict()}


def assert_hidden_scoring_allowed(runtime_root: Path) -> dict[str, Any]:
    """Fail closed unless an immutable candidate was frozen before scoring."""

    root = runtime_root.resolve()
    terminal = _read_json(root / "corrected_candidate" / "terminal_result.json")
    candidate = _read_json(root / "corrected_candidate" / "candidate.json")
    terminal_body = {key: deepcopy(value) for key, value in terminal.items() if key != "terminal_result_digest"}
    candidate_body = {key: deepcopy(value) for key, value in candidate.items() if key != "candidate_digest"}
    if terminal.get("terminal_result_digest") != canonical_digest(terminal_body):
        raise S2SupervisorRuntimeError("s2_06_terminal_digest_invalid")
    if candidate.get("candidate_digest") != canonical_digest(candidate_body):
        raise S2SupervisorRuntimeError("s2_06_candidate_digest_invalid")
    if not terminal.get("candidate_frozen") or terminal.get("candidate_digest") != candidate.get("candidate_digest"):
        raise S2SupervisorRuntimeError("s2_06_hidden_scoring_before_freeze_forbidden")
    return {
        "case_key": terminal["case_key"],
        "corrected_run_id": terminal["corrected_run_id"],
        "candidate_digest": terminal["candidate_digest"],
        "scoring_allowed": True,
    }


def _validate_boundary_identity(boundary: Mapping[str, Any], case_key: str) -> None:
    raw = boundary.get("raw_binding")
    if (
        boundary.get("case_key") != case_key
        or not isinstance(raw, Mapping)
        or raw.get("case_key") != case_key
        or not raw.get("run_id")
        or not raw.get("terminal_digest")
        or raw.get("raw_model_only_immutable") is not True
    ):
        raise S2SupervisorRuntimeError("s2_06_boundary_identity_invalid")


def _validate_corrected_admission(
    admission: Mapping[str, Any],
    *,
    spec: Mapping[str, Any],
    raw_outputs: Mapping[str, Any],
    corrected_run_id: str,
    corrected_attempt_id: str,
    observed_at: str,
) -> None:
    body = {key: deepcopy(value) for key, value in admission.items() if key != "admission_digest"}
    if admission.get("admission_digest") != canonical_digest(body):
        raise S2SupervisorRuntimeError("s2_06_corrected_admission_digest_invalid")
    if (
        admission.get("schema_version") != CORRECTED_ADMISSION_SCHEMA
        or admission.get("scope") != CORRECTED_SCOPE
        or admission.get("case_key") != spec["case_key"]
        or admission.get("raw_binding") != spec["raw_binding"]
        or admission.get("corrected_run_id") != corrected_run_id
        or admission.get("corrected_attempt_id") != corrected_attempt_id
        or admission.get("runtime_identity") != corrected_run_id + "::" + corrected_attempt_id
    ):
        raise S2SupervisorRuntimeError("s2_06_corrected_admission_binding_invalid")
    if (
        admission.get("provider_execution_authorized") is not True
        or admission.get("credential_present") is not True
        or admission.get("retry_count") != 0
        or admission.get("fallback_count") != 0
    ):
        raise S2SupervisorRuntimeError("s2_06_corrected_execution_not_authorized")
    expected_capacity = compile_capacity_proof(
        plan=compile_fixture_supervisor_plan(spec),
        spec=spec,
        raw_outputs=raw_outputs,
    )
    if admission.get("capacity_proof") != expected_capacity or not expected_capacity["pass"]:
        raise S2SupervisorRuntimeError("s2_06_corrected_admission_capacity_invalid")
    now = _parse_time(observed_at)
    issued = _parse_time(str(admission.get("issued_at") or ""))
    expires = _parse_time(str(admission.get("expires_at") or ""))
    if issued > now or now >= expires:
        raise S2SupervisorRuntimeError("s2_06_corrected_admission_not_current")


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise S2SupervisorRuntimeError("s2_06_corrected_admission_time_invalid") from exc
    if parsed.tzinfo is None:
        raise S2SupervisorRuntimeError("s2_06_corrected_admission_time_invalid")
    return parsed.astimezone(timezone.utc)


def _validate_raw_output_identity(raw_outputs: Mapping[str, Any], case_key: str) -> None:
    required = {"lead", "specialists", "synthesis", "writer", "verifier"}
    if set(raw_outputs) != required or not isinstance(raw_outputs.get("specialists"), list):
        raise S2SupervisorRuntimeError("s2_06_raw_outputs_shape_invalid")
    rows: list[Any] = [raw_outputs["lead"], *raw_outputs["specialists"], raw_outputs["synthesis"], raw_outputs["writer"], raw_outputs["verifier"]]
    if any(not isinstance(row, Mapping) or row.get("case_key") != case_key for row in rows):
        raise S2SupervisorRuntimeError("s2_06_cross_case_raw_output_forbidden")


def _canonical_node_ref(node_ref: str, raw_outputs: Mapping[str, Any]) -> str:
    if node_ref in {"lead", "lead_planning"}:
        return "lead"
    if node_ref in {"synthesis", "cross_cell_synthesis"}:
        return "synthesis"
    if node_ref in {"writer", "verifier"}:
        return node_ref
    match = re.fullmatch(r"specialist\[(\d+)\]", node_ref)
    if match:
        index = int(match.group(1))
        specialists = raw_outputs.get("specialists", [])
        if index >= len(specialists):
            raise S2SupervisorRuntimeError("s2_06_specialist_node_ref_invalid")
        return "specialist:" + str(specialists[index]["unit_id"])
    if node_ref.startswith("specialist:"):
        unit_id = node_ref.split(":", 1)[1]
        if unit_id not in {str(row["unit_id"]) for row in raw_outputs.get("specialists", [])}:
            raise S2SupervisorRuntimeError("s2_06_specialist_node_ref_invalid")
        return node_ref
    raise S2SupervisorRuntimeError("s2_06_node_ref_invalid")


def _node_sort_key(node_ref: str) -> tuple[int, str]:
    kind = node_ref.split(":", 1)[0]
    return (_NODE_ORDER.get(kind, 99), node_ref)


def _downstream_closure(origin: str, specialists: Sequence[str], *, include_origin: bool) -> set[str]:
    if origin == "lead":
        rows = {"lead", *specialists, "synthesis", "writer", "verifier"}
    elif origin.startswith("specialist:"):
        rows = {origin, "synthesis", "writer", "verifier"}
    elif origin == "synthesis":
        rows = {"synthesis", "writer", "verifier"}
    elif origin == "writer":
        rows = {"writer", "verifier"}
    elif origin == "verifier":
        rows = {"verifier"}
    else:
        raise S2SupervisorRuntimeError("s2_06_node_ref_invalid")
    if not include_origin:
        rows.discard(origin)
    return rows


def _unique_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(row, str) or not row for row in value):
        raise S2SupervisorRuntimeError(f"s2_06_supervisor_{label}_aliases_invalid")
    if len(value) != len(set(value)):
        raise S2SupervisorRuntimeError(f"s2_06_supervisor_{label}_aliases_duplicate")
    return list(value)


def _capture_provider_call(
    *,
    kwargs: Mapping[str, Any],
    provider_call: ProviderCall,
    captures_dir: Path,
    capture_track: str,
    case_key: str,
    node_type: str,
    node_id: str,
    call_index: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    safe_kwargs = deepcopy(dict(kwargs))
    try:
        result = deepcopy(dict(provider_call(**safe_kwargs)))
    except Exception as exc:
        result = {
            "status": "gateway_exception", "content": "", "finish_reason": "",
            "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
            "transport_attempt_count": 1, "exception_type": type(exc).__name__,
            "exception_message": str(exc)[:1000],
        }
    capture = {
        "schema_version": CORRECTED_CAPTURE_SCHEMA,
        "capture_track": capture_track,
        "case_key": case_key,
        "call_index": call_index,
        "node_type": node_type,
        "node_id": node_id,
        "provider_visible_request": {key: value for key, value in safe_kwargs.items() if key != "api_key_env"},
        "gateway_result": result,
    }
    digest = canonical_digest(capture)
    path = captures_dir / f"{call_index:02d}_{node_type}_{digest}.json"
    _write_exclusive(path, capture)
    row = {
        "call_index": call_index,
        "capture_track": capture_track,
        "node_type": node_type,
        "node_id": node_id,
        "capture_ref": str(path.relative_to(captures_dir.parent.parent)).replace("\\", "/"),
        "capture_digest": digest,
        "gateway_status": result.get("status"),
        "finish_reason": result.get("finish_reason"),
        "usage": {
            "input_tokens": int(result.get("input_tokens") or 0),
            "output_tokens": int(result.get("output_tokens") or 0),
            "total_tokens": int(result.get("total_tokens") or 0),
            "transport_attempt_count": int(result.get("transport_attempt_count") or 0),
        },
    }
    if result.get("status") != "ok" or result.get("finish_reason") not in {"stop", None}:
        raise S2SupervisorRuntimeError("s2_06_provider_transport_or_finish_failure")
    try:
        parsed = json.loads(str(result.get("content") or ""))
    except json.JSONDecodeError as exc:
        raise S2SupervisorRuntimeError("s2_06_provider_json_invalid") from exc
    if not isinstance(parsed, dict):
        raise S2SupervisorRuntimeError("s2_06_provider_output_not_object")
    return row, parsed


def _captured_call_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for track in ("supervisor_augmented", "corrected_candidate"):
        captures_dir = root / track / "captures"
        for path in captures_dir.glob("*.json"):
            capture = _read_json(path)
            result = capture.get("gateway_result")
            if not isinstance(result, Mapping):
                raise S2SupervisorRuntimeError("s2_06_capture_result_invalid")
            rows.append(
                {
                    "call_index": int(capture["call_index"]),
                    "capture_track": track,
                    "node_type": capture["node_type"],
                    "node_id": capture["node_id"],
                    "capture_ref": str(path.relative_to(root)).replace("\\", "/"),
                    "capture_digest": canonical_digest(capture),
                    "gateway_status": result.get("status"),
                    "finish_reason": result.get("finish_reason"),
                    "usage": {
                        "input_tokens": int(result.get("input_tokens") or 0),
                        "output_tokens": int(result.get("output_tokens") or 0),
                        "total_tokens": int(result.get("total_tokens") or 0),
                        "transport_attempt_count": int(result.get("transport_attempt_count") or 0),
                    },
                }
            )
    return sorted(rows, key=lambda row: int(row["call_index"]))


def _corrected_node_kwargs(
    *,
    node_type: str,
    node_id: str,
    context: Mapping[str, Any],
    case_input: Mapping[str, Any],
    policy: Mapping[str, Any],
    corrected_run_id: str,
) -> dict[str, Any]:
    kwargs = _provider_kwargs(
        node_type=node_type,
        node_id=node_id,
        context=context,
        case_input=case_input,
        admission={"run_id": corrected_run_id},
        policy=policy,
    )
    request_payload = json.loads(str(kwargs["messages"][1]["content"]))
    objectives = list(context.get("correction_objectives") or [])
    request_payload["required_output_contract"] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "node_output", "correction_resolutions"],
        "properties": {
            "schema_version": {"type": "string", "const": CORRECTED_NODE_ENVELOPE_SCHEMA},
            "node_output": request_payload["required_output_contract"],
            "correction_resolutions": {
                "type": "array",
                "minItems": len(objectives),
                "maxItems": len(objectives),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "correction_id", "status", "evidence_ids", "gap_ids", "resolution_summary",
                    ],
                    "properties": {
                        "correction_id": {"type": "string"},
                        "status": {"type": "string", "enum": ["closed", "typed_unresolved"]},
                        "evidence_ids": {"type": "array", "items": {"type": "string"}},
                        "gap_ids": {"type": "array", "items": {"type": "string"}},
                        "resolution_summary": {"type": "string"},
                    },
                },
            },
        },
    }
    kwargs["messages"][1]["content"] = json.dumps(
        request_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    kwargs["messages"][0]["content"] = (
        "You are recomputing one node in a case-isolated corrected financial research graph. "
        "Return exactly one corrected-node envelope JSON object containing node_output and one "
        "correction resolution for every supplied objective. Use only the supplied case-local context "
        "and aliases. Address each objective's finding code, target, required resolution and closure rule. "
        "Use typed_unresolved only when its policy allows it and cite a selected Gap. Preserve unsupported "
        "gaps and do not infer hidden targets. In narrative fields, never write numeric digits directly; "
        "use [NUM:<numeric_alias>] for an exact supplied value. Do not create analyst thresholds. "
        "Node type: " + node_type
    )
    kwargs["role"] = "fin013_s2_06_corrected_" + node_type
    kwargs["trace_tags"] = {
        "corrected_run_id": corrected_run_id,
        "case_key": case_input["case_key"],
        "node_type": node_type,
        "node_id": node_id,
    }
    return kwargs


def _compile_corrected_node_context(
    *,
    node_ref: str,
    outputs: Mapping[str, Any],
    raw_outputs: Mapping[str, Any],
    case_input: Mapping[str, Any],
    directive: Mapping[str, Any] | None,
    correction_objectives: Mapping[str, Mapping[str, Any]],
    numeric_fact_views: Sequence[Mapping[str, Any]],
) -> tuple[str, str, dict[str, Any]]:
    correction = deepcopy(dict(directive)) if directive else {
        "node_ref": node_ref,
        "correction_ids": [],
        "action_codes": ["downstream_dependency_recomputation"],
        "evidence_ids": [],
        "numeric_aliases": [],
        "gap_ids": [],
    }
    selected_objectives = [
        deepcopy(dict(correction_objectives[correction_id]))
        for correction_id in correction["correction_ids"]
    ]
    selected_numeric = [
        deepcopy(dict(row))
        for row in numeric_fact_views
        if row["numeric_alias"] in set(correction["numeric_aliases"])
    ]
    correction_contract = {
        "visible_correction_directive": correction,
        "correction_objectives": selected_objectives,
        "numeric_fact_views": selected_numeric,
        "protected_narrative_rule": (
            "Write exact supplied values as [NUM:<numeric_alias>]; the Harness renders only that span."
        ),
    }
    if node_ref == "lead":
        return "lead_planning", "lead", {
            "case_input": deepcopy(dict(case_input)),
            **correction_contract,
        }
    if node_ref.startswith("specialist:"):
        unit_id = node_ref.split(":", 1)[1]
        unit = next(row for row in outputs["lead"]["research_units"] if row["unit_id"] == unit_id)
        context = _compile_specialist_context(case_input, unit)
        context.update(correction_contract)
        return "specialist_judgment", unit_id, context
    synthesis_context = {
        "case_identity": _case_identity(case_input),
        "evidence_index": _evidence_index(case_input),
        "derived_numeric": deepcopy(case_input["derived_numeric"]),
        "explicit_gaps": deepcopy(case_input["explicit_gaps"]),
        "lead_plan": deepcopy(outputs["lead"]),
        "specialist_outputs": deepcopy(outputs["specialists"]),
        **correction_contract,
    }
    if node_ref == "synthesis":
        return "cross_cell_synthesis", "synthesis", synthesis_context
    writer_context = {
        "case_identity": _case_identity(case_input),
        "evidence_index": _evidence_index(case_input),
        "derived_numeric": deepcopy(case_input["derived_numeric"]),
        "explicit_gaps": deepcopy(case_input["explicit_gaps"]),
        "specialist_outputs": deepcopy(outputs["specialists"]),
        "synthesis": deepcopy(outputs["synthesis"]),
        "required_section_ids": list(SECTION_IDS),
        **correction_contract,
    }
    if node_ref == "writer":
        return "writer", "writer", writer_context
    if node_ref == "verifier":
        verifier_context = {
            **synthesis_context,
            "synthesis": deepcopy(outputs["synthesis"]),
            "writer": deepcopy(outputs["writer"]),
            "visible_correction_directive": correction,
            "verifier_scope": "corrected candidate substance and visible finding classes only",
        }
        return "verifier", "verifier", verifier_context
    raise S2SupervisorRuntimeError("s2_06_node_ref_invalid")


def _validate_and_store_node(
    *,
    node_ref: str,
    parsed: Mapping[str, Any],
    outputs: dict[str, Any],
    case_input: Mapping[str, Any],
    policy: Mapping[str, Any],
    correction_contract: Mapping[str, Any],
    closure_receipts: list[dict[str, Any]],
) -> None:
    objectives = list(correction_contract.get("correction_objectives") or [])
    try:
        node_output, resolutions = _validate_corrected_node_envelope(
            parsed,
            node_ref=node_ref,
            correction_contract=correction_contract,
        )
        rendered_output = _render_protected_numeric_narrative(
            node_output,
            node_type=node_ref.split(":", 1)[0],
            numeric_fact_views=correction_contract.get("numeric_fact_views") or [],
        )
        if node_ref == "lead":
            _validate_lead(rendered_output, case_input=case_input, policy=policy)
            old_ids = [str(row["unit_id"]) for row in outputs["lead"]["research_units"]]
            new_ids = [str(row["unit_id"]) for row in rendered_output["research_units"]]
            if new_ids != old_ids:
                raise S2SupervisorRuntimeError("s2_06_corrected_lead_topology_changed")
            outputs["lead"] = deepcopy(dict(rendered_output))
        elif node_ref.startswith("specialist:"):
            unit_id = node_ref.split(":", 1)[1]
            unit = next(row for row in outputs["lead"]["research_units"] if row["unit_id"] == unit_id)
            _validate_specialist(rendered_output, case_input=case_input, unit=unit, policy=policy)
            index = next(index for index, row in enumerate(outputs["specialists"]) if row["unit_id"] == unit_id)
            outputs["specialists"][index] = deepcopy(dict(rendered_output))
        elif node_ref == "synthesis":
            _validate_synthesis(rendered_output, case_input=case_input, specialists=outputs["specialists"])
            outputs["synthesis"] = deepcopy(dict(rendered_output))
        elif node_ref == "writer":
            _validate_writer(rendered_output, case_input=case_input, specialists=outputs["specialists"])
            outputs["writer"] = deepcopy(dict(rendered_output))
        elif node_ref == "verifier":
            _validate_verifier(
                rendered_output,
                case_input=case_input,
                specialists=outputs["specialists"],
                writer=outputs["writer"],
            )
            outputs["verifier"] = deepcopy(dict(rendered_output))
        else:
            raise S2SupervisorRuntimeError("s2_06_node_ref_invalid")
        closure_receipts.extend(
            _compile_closure_receipts(
                objectives=objectives,
                resolutions=resolutions,
                node_ref=node_ref,
                node_output=rendered_output,
                validation_status="node_contract_pass",
            )
        )
    except (S2SupervisorRuntimeError, S2SameEvidenceExperimentError) as exc:
        failure_code = getattr(exc, "code", str(exc))
        for objective in objectives:
            closure_receipts.append(
                {
                    "schema_version": CORRECTION_CLOSURE_RECEIPT_SCHEMA,
                    "correction_id": objective["correction_id"],
                    "node_ref": node_ref,
                    "status": "rejected_new_violation",
                    "evidence_ids": [],
                    "gap_ids": [],
                    "resolution_summary": "Corrected node rejected before acceptance.",
                    "closure_rule": objective["closure_rule"],
                    "validation_status": failure_code,
                }
            )
        raise


def _validate_corrected_node_envelope(
    parsed: Mapping[str, Any],
    *,
    node_ref: str,
    correction_contract: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if set(parsed) != {"schema_version", "node_output", "correction_resolutions"}:
        raise S2SupervisorRuntimeError("s2_06_corrected_node_envelope_shape_invalid")
    if parsed.get("schema_version") != CORRECTED_NODE_ENVELOPE_SCHEMA:
        raise S2SupervisorRuntimeError("s2_06_corrected_node_envelope_schema_invalid")
    node_output = parsed.get("node_output")
    resolutions = parsed.get("correction_resolutions")
    if not isinstance(node_output, Mapping) or not isinstance(resolutions, list):
        raise S2SupervisorRuntimeError("s2_06_corrected_node_envelope_content_invalid")
    objectives = list(correction_contract.get("correction_objectives") or [])
    expected_ids = [str(row["correction_id"]) for row in objectives]
    if len(resolutions) != len(expected_ids):
        raise S2SupervisorRuntimeError("s2_06_correction_resolution_count_invalid")
    directive = correction_contract["visible_correction_directive"]
    allowed_evidence = set(directive["evidence_ids"])
    allowed_gaps = set(directive["gap_ids"])
    by_id: dict[str, dict[str, Any]] = {}
    for row in resolutions:
        if not isinstance(row, Mapping) or set(row) != {
            "correction_id", "status", "evidence_ids", "gap_ids", "resolution_summary",
        }:
            raise S2SupervisorRuntimeError("s2_06_correction_resolution_shape_invalid")
        correction_id = str(row.get("correction_id") or "")
        if correction_id in by_id or correction_id not in expected_ids:
            raise S2SupervisorRuntimeError("s2_06_correction_resolution_binding_invalid")
        evidence_ids = _unique_string_list(row.get("evidence_ids"), "resolution_evidence")
        gap_ids = _unique_string_list(row.get("gap_ids"), "resolution_gap")
        if not set(evidence_ids) <= allowed_evidence or not set(gap_ids) <= allowed_gaps:
            raise S2SupervisorRuntimeError("s2_06_correction_resolution_unknown_authority")
        status = str(row.get("status") or "")
        if status not in {"closed", "typed_unresolved"}:
            raise S2SupervisorRuntimeError("s2_06_correction_resolution_status_invalid")
        summary = str(row.get("resolution_summary") or "").strip()
        if not summary:
            raise S2SupervisorRuntimeError("s2_06_correction_resolution_summary_required")
        by_id[correction_id] = {
            "correction_id": correction_id,
            "status": status,
            "evidence_ids": evidence_ids,
            "gap_ids": gap_ids,
            "resolution_summary": summary,
        }
    ordered = [by_id[correction_id] for correction_id in expected_ids]
    for objective, resolution in zip(objectives, ordered):
        if resolution["status"] == "typed_unresolved":
            if objective["unresolved_policy"] == "typed_unresolved_not_allowed":
                raise S2SupervisorRuntimeError("s2_06_typed_unresolved_not_allowed")
            if not resolution["gap_ids"]:
                raise S2SupervisorRuntimeError("s2_06_typed_unresolved_gap_required")
        elif not resolution["evidence_ids"] and not resolution["gap_ids"]:
            raise S2SupervisorRuntimeError("s2_06_closed_resolution_authority_required")
        if (
            objective["closure_rule"] == "counterevidence_nonempty_or_typed_unresolved_with_gap"
            and resolution["status"] == "closed"
            and not list(node_output.get("counterevidence_ids") or [])
        ):
            raise S2SupervisorRuntimeError("s2_06_counterevidence_objective_not_closed")
    return deepcopy(dict(node_output)), ordered


def _narrative_locations(node_output: dict[str, Any], node_type: str) -> list[tuple[dict[str, Any], str]]:
    rows: list[tuple[dict[str, Any], str]] = []
    if node_type == "lead":
        for unit in node_output.get("research_units", []):
            rows.extend((unit, field) for field in ("question", "why_material", "stop_condition") if field in unit)
    elif node_type == "specialist":
        rows.extend(
            (node_output, field)
            for field in ("judgment", "mechanism", "financial_or_valuation_link", "what_would_change")
            if field in node_output
        )
    elif node_type == "synthesis":
        rows.extend(
            (node_output, field)
            for field in ("thesis", "confidence", "counter_thesis", "what_would_change")
            if field in node_output
        )
    elif node_type == "writer":
        rows.extend((node_output, field) for field in ("title", "overall_boundary") if field in node_output)
        for section in node_output.get("sections", []):
            rows.extend((section, field) for field in ("heading", "narrative") if field in section)
    elif node_type == "verifier":
        for finding in node_output.get("findings", []):
            if "explanation" in finding:
                rows.append((finding, "explanation"))
    return rows


def _render_protected_numeric_narrative(
    node_output: Mapping[str, Any],
    *,
    node_type: str,
    numeric_fact_views: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    rendered = deepcopy(dict(node_output))
    views = {str(row["numeric_alias"]): row for row in numeric_fact_views}
    for parent, key in _narrative_locations(rendered, node_type):
        text = str(parent[key])
        without_placeholders = _NUMERIC_PLACEHOLDER.sub("", text)
        if _RAW_NARRATIVE_NUMERIC.search(without_placeholders):
            raise S2SupervisorRuntimeError("s2_06_unprotected_numeric_narrative")

        def replace(match: re.Match[str]) -> str:
            alias = match.group(1)
            if alias not in views:
                raise S2SupervisorRuntimeError("s2_06_unknown_or_unselected_numeric_placeholder")
            return str(views[alias]["display_surface"])

        parent[key] = _NUMERIC_PLACEHOLDER.sub(replace, text)
        if "[NUM:" in str(parent[key]):
            raise S2SupervisorRuntimeError("s2_06_numeric_placeholder_residue")
    return rendered


def _compile_closure_receipts(
    *,
    objectives: Sequence[Mapping[str, Any]],
    resolutions: Sequence[Mapping[str, Any]],
    node_ref: str,
    node_output: Mapping[str, Any],
    validation_status: str,
) -> list[dict[str, Any]]:
    output_digest = canonical_digest(node_output)
    return [
        {
            "schema_version": CORRECTION_CLOSURE_RECEIPT_SCHEMA,
            "correction_id": objective["correction_id"],
            "node_ref": node_ref,
            "status": resolution["status"],
            "evidence_ids": list(resolution["evidence_ids"]),
            "gap_ids": list(resolution["gap_ids"]),
            "resolution_summary": resolution["resolution_summary"],
            "closure_rule": objective["closure_rule"],
            "validation_status": validation_status,
            "node_output_digest": output_digest,
        }
        for objective, resolution in zip(objectives, resolutions)
    ]


def _apply_deterministic_corrections(
    outputs: dict[str, Any], *, plan: Mapping[str, Any], spec: Mapping[str, Any]
) -> None:
    finding_by_id = {row["correction_id"]: row for row in spec["visible_findings"]}
    for correction_id in plan["deterministic_correction_ids"]:
        finding = finding_by_id[correction_id]
        target = _node_output(outputs, finding["node_ref"])
        path = str(finding.get("path") or "")
        tokens = list(finding.get("tokens") or [])
        if not path or not tokens:
            raise S2SupervisorRuntimeError("s2_06_deterministic_deletion_authority_missing")
        parent, key = _resolve_parent(target, path)
        value = parent[key]
        if not isinstance(value, str):
            raise S2SupervisorRuntimeError("s2_06_deterministic_deletion_target_invalid")
        repaired = value
        for token in tokens:
            escaped = re.escape(str(token))
            repaired = re.sub(
                rf"(?<![A-Za-z0-9_.]){escaped}(?![A-Za-z0-9_.%])",
                "",
                repaired,
                flags=re.IGNORECASE,
            )
        repaired = re.sub(r"\s+", " ", repaired).strip(" ,;:-")
        if not repaired or repaired == value:
            raise S2SupervisorRuntimeError("s2_06_deterministic_deletion_no_effect")
        parent[key] = repaired


def _node_output(outputs: Mapping[str, Any], node_ref: str) -> dict[str, Any]:
    if node_ref == "lead":
        return outputs["lead"]
    if node_ref.startswith("specialist:"):
        unit_id = node_ref.split(":", 1)[1]
        return next(row for row in outputs["specialists"] if row["unit_id"] == unit_id)
    if node_ref in {"synthesis", "writer", "verifier"}:
        return outputs[node_ref]
    raise S2SupervisorRuntimeError("s2_06_node_ref_invalid")


def _resolve_parent(root: dict[str, Any], path: str) -> tuple[Any, Any]:
    if not path.startswith("$."):
        raise S2SupervisorRuntimeError("s2_06_deterministic_path_invalid")
    parts = path[2:].split(".")
    current: Any = root
    for position, part in enumerate(parts):
        match = _PATH_PART.fullmatch(part)
        if not match:
            raise S2SupervisorRuntimeError("s2_06_deterministic_path_invalid")
        key, index = match.groups()
        final = position == len(parts) - 1
        if final and index is None:
            if not isinstance(current, dict) or key not in current:
                raise S2SupervisorRuntimeError("s2_06_deterministic_path_missing")
            return current, key
        if not isinstance(current, dict) or key not in current:
            raise S2SupervisorRuntimeError("s2_06_deterministic_path_missing")
        current = current[key]
        if index is not None:
            if not isinstance(current, list) or int(index) >= len(current):
                raise S2SupervisorRuntimeError("s2_06_deterministic_path_missing")
            if final:
                return current, int(index)
            current = current[int(index)]
    raise S2SupervisorRuntimeError("s2_06_deterministic_path_invalid")


def _usage(rows: Sequence[Mapping[str, Any]], policy: Mapping[str, Any]) -> dict[str, Any]:
    input_tokens = sum(int(row["usage"]["input_tokens"]) for row in rows)
    output_tokens = sum(int(row["usage"]["output_tokens"]) for row in rows)
    rates = policy["capacity"]["cost_ceiling"]
    cost = (
        input_tokens * float(rates["input_usd_per_million_tokens"])
        + output_tokens * float(rates["output_usd_per_million_tokens"])
    ) / 1_000_000
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "estimated_cost_usd": round(cost, 8),
        "cost_method": "policy_ceiling_rates_not_provider_invoice",
    }


def _write_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        handle.write("\n")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise S2SupervisorRuntimeError("s2_06_freeze_artifact_invalid") from exc
    if not isinstance(value, dict):
        raise S2SupervisorRuntimeError("s2_06_freeze_artifact_invalid")
    return value
