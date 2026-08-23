from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sec_agent.canonical_runtime import canonical_digest  # noqa: E402
from sec_agent.research.current_dynamic_writer import (  # noqa: E402
    find_r10_protected_writer_surface_findings,
    validate_r10_protected_writer_draft,
)
from sec_agent.research.multi_agent_report_authority import (  # noqa: E402
    audit_protected_report_draft,
    render_protected_report,
)


DECISION_SCHEMA_VERSION = (
    "fin_ia_s3_current_dynamic_multi_agent_protected_writer_"
    "independent_takeover_scope_decision_v1_0"
)
DECISION_STATUS = "approved_user_authorized_zero_provider_writer_takeover"
MANIFEST_SCHEMA_VERSION = (
    "fin_ia_s3_current_dynamic_multi_agent_protected_writer_"
    "independent_takeover_edit_manifest_v1_0"
)
MANIFEST_STATUS = "private_user_authorized_codex_writer_edit_manifest"
PRIVATE_RESULT_SCHEMA_VERSION = (
    "fin_ia_s3_current_dynamic_multi_agent_protected_writer_"
    "independent_takeover_full_result_v1_0"
)
PUBLIC_RESULT_SCHEMA_VERSION = (
    "fin_ia_s3_current_dynamic_multi_agent_protected_writer_"
    "independent_takeover_public_result_v1_0"
)
RUN_ID = "FIN_0_1_3_S3_DELL_R10_PROTECTED_WRITER_INDEPENDENT_TAKEOVER_R15"

_REQUIRED_SOURCE_BINDINGS = {
    "R14_authority",
    "R14_public_result",
    "R14_failure_assessment",
    "R14_response_capture",
    "R10_writer_authority_catalog",
    "R10_writer_protection_contract",
    "private_edit_manifest",
}
_REF_FIELDS = (
    "source_workpaper_agent_ids",
    "source_claim_refs",
    "evidence_refs",
    "authority_refs",
    "gap_refs",
)
_EXECUTIVE_PATH = re.compile(r"^executive_thesis\[(\d+)\]$")
_SECTION_PATH = re.compile(r"^sections\[(\d+)\]\.clauses\[(\d+)\]$")
_WWC_PATH = re.compile(r"^what_would_change\[(\d+)\]$")


class IndependentWriterTakeoverError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise IndependentWriterTakeoverError(code)


def _resolve(ref: str | Path) -> Path:
    path = Path(ref)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _read_json(ref: str | Path) -> dict[str, Any]:
    value = json.loads(_resolve(ref).read_text(encoding="utf-8"))
    _require(isinstance(value, Mapping), "independent_writer_json_identity_invalid")
    return deepcopy(dict(value))


def _sha(ref: str | Path) -> str:
    return hashlib.sha256(_resolve(ref).read_bytes()).hexdigest()


def _serialized_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _serialized_sha(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_serialized_bytes(value)).hexdigest()


def _write_new(ref: str | Path, value: Mapping[str, Any]) -> None:
    path = _resolve(ref)
    _require(not path.exists(), "independent_writer_output_identity_consumed")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_serialized_bytes(value))


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _validate_self_digest(
    value: Mapping[str, Any], *, field: str, code: str
) -> None:
    unsigned = {key: item for key, item in value.items() if key != field}
    _require(
        value.get(field) == canonical_digest(unsigned),
        code,
    )


def _validate_binding(binding: Mapping[str, Any]) -> dict[str, Any]:
    ref = str(binding.get("ref") or "")
    expected_sha = str(binding.get("sha256") or "")
    _require(bool(ref and expected_sha), "independent_writer_binding_identity_invalid")
    _require(_sha(ref) == expected_sha, "independent_writer_binding_sha_invalid")
    value = _read_json(ref)
    digest = binding.get("digest")
    if digest is not None:
        digest_field = str(binding.get("digest_field") or "")
        _require(
            bool(digest_field) and value.get(digest_field) == digest,
            "independent_writer_binding_digest_invalid",
        )
    return value


def _validate_decision(value: Mapping[str, Any]) -> dict[str, Any]:
    decision = deepcopy(dict(value))
    _validate_self_digest(
        decision,
        field="decision_digest",
        code="independent_writer_decision_digest_invalid",
    )
    _require(
        decision.get("schema_version") == DECISION_SCHEMA_VERSION
        and decision.get("status") == DECISION_STATUS
        and decision.get("run_id") == RUN_ID
        and decision.get("case_key") == "DELL"
        and isinstance(decision.get("implementation_commit"), str)
        and len(decision["implementation_commit"]) == 40,
        "independent_writer_decision_identity_invalid",
    )
    implementation_bindings = decision.get("implementation_bindings") or []
    _require(
        isinstance(implementation_bindings, list)
        and bool(implementation_bindings)
        and all(
            isinstance(binding, Mapping)
            and bool(binding.get("ref"))
            and _sha(str(binding["ref"])) == binding.get("sha256")
            for binding in implementation_bindings
        ),
        "independent_writer_implementation_binding_invalid",
    )
    user_authorization = decision.get("user_authorization") or {}
    token_budget_basis = decision.get("token_budget_basis") or {}
    _require(
        user_authorization.get("independent_writer_takeover_authorized") is True
        and token_budget_basis.get("model_node_created") is False
        and token_budget_basis.get("paid_call_authority_created") is False
        and token_budget_basis.get("provider_token_budget") == 0,
        "independent_writer_authorization_boundary_invalid",
    )
    budget = decision.get("execution_budget") or {}
    _require(
        set(budget)
        == {
            "model_calls",
            "provider_calls",
            "network_calls",
            "new_evidence_items",
            "candidate_promotions",
        }
        and all(int(value or 0) == 0 for value in budget.values()),
        "independent_writer_decision_budget_invalid",
    )
    bindings = decision.get("source_bindings") or {}
    _require(
        isinstance(bindings, Mapping)
        and set(bindings) == _REQUIRED_SOURCE_BINDINGS,
        "independent_writer_decision_bindings_invalid",
    )
    boundary = decision.get("change_boundary") or {}
    _require(
        boundary.get("new_evidence_authority_or_gap_ids_allowed") is False
        and boundary.get("remaining_gap_ref_union_must_be_preserved") is True
        and isinstance(boundary.get("allowed_changed_model_text_paths"), list)
        and isinstance(boundary.get("expected_reference_after"), Mapping)
        and isinstance(boundary.get("allowed_catalog_claim_refs_added"), list),
        "independent_writer_decision_change_boundary_invalid",
    )
    acceptance = decision.get("acceptance_boundary") or {}
    _require(
        acceptance.get("independent_post_writer_review_pass") is False
        and acceptance.get("S3_pass") is False
        and acceptance.get("product_publication") is False
        and acceptance.get("release_ready") is False,
        "independent_writer_decision_acceptance_boundary_invalid",
    )
    output = decision.get("output_contract") or {}
    _require(
        bool(output.get("private_full_result_ref"))
        and bool(output.get("public_result_ref")),
        "independent_writer_decision_output_invalid",
    )
    return decision


def _validate_manifest(value: Mapping[str, Any]) -> dict[str, Any]:
    manifest = deepcopy(dict(value))
    _validate_self_digest(
        manifest,
        field="manifest_digest",
        code="independent_writer_manifest_digest_invalid",
    )
    _require(
        manifest.get("schema_version") == MANIFEST_SCHEMA_VERSION
        and manifest.get("status") == MANIFEST_STATUS
        and manifest.get("run_id") == RUN_ID
        and manifest.get("case_key") == "DELL"
        and isinstance(manifest.get("model_text_replacements"), Mapping)
        and isinstance(manifest.get("reference_replacements"), Mapping)
        and isinstance(manifest.get("remaining_gaps_replacement"), list),
        "independent_writer_manifest_identity_invalid",
    )
    return manifest


def _clause_at_path(report: Mapping[str, Any], path: str) -> dict[str, Any]:
    if path == "confidence":
        clause = report.get("confidence")
    elif match := _EXECUTIVE_PATH.fullmatch(path):
        rows = report.get("executive_thesis")
        index = int(match.group(1))
        _require(
            isinstance(rows, list) and 0 <= index < len(rows),
            "independent_writer_edit_path_invalid",
        )
        clause = rows[index]
    elif match := _SECTION_PATH.fullmatch(path):
        sections = report.get("sections")
        section_index = int(match.group(1))
        clause_index = int(match.group(2))
        _require(
            isinstance(sections, list)
            and 0 <= section_index < len(sections)
            and isinstance(sections[section_index], Mapping)
            and isinstance(sections[section_index].get("clauses"), list)
            and 0 <= clause_index < len(sections[section_index]["clauses"]),
            "independent_writer_edit_path_invalid",
        )
        clause = sections[section_index]["clauses"][clause_index]
    elif match := _WWC_PATH.fullmatch(path):
        rows = report.get("what_would_change")
        index = int(match.group(1))
        _require(
            isinstance(rows, list) and 0 <= index < len(rows),
            "independent_writer_edit_path_invalid",
        )
        clause = rows[index]
    else:
        raise IndependentWriterTakeoverError("independent_writer_edit_path_invalid")
    _require(isinstance(clause, Mapping), "independent_writer_edit_clause_invalid")
    return clause  # type: ignore[return-value]


def _iter_clauses(report: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    rows: list[tuple[str, Mapping[str, Any]]] = []
    rows.extend(
        (f"executive_thesis[{index}]", row)
        for index, row in enumerate(report.get("executive_thesis") or ())
        if isinstance(row, Mapping)
    )
    for section_index, section in enumerate(report.get("sections") or ()):
        if not isinstance(section, Mapping):
            continue
        rows.extend(
            (f"sections[{section_index}].clauses[{clause_index}]", row)
            for clause_index, row in enumerate(section.get("clauses") or ())
            if isinstance(row, Mapping)
        )
    rows.extend(
        (f"remaining_gaps[{index}]", row)
        for index, row in enumerate(report.get("remaining_gaps") or ())
        if isinstance(row, Mapping)
    )
    rows.extend(
        (f"what_would_change[{index}]", row)
        for index, row in enumerate(report.get("what_would_change") or ())
        if isinstance(row, Mapping)
    )
    confidence = report.get("confidence")
    if isinstance(confidence, Mapping):
        rows.append(("confidence", confidence))
    return rows


def _inventory(report: Mapping[str, Any]) -> dict[str, list[str]]:
    return {
        field: sorted(
            {
                str(ref)
                for _, clause in _iter_clauses(report)
                for ref in clause.get(field) or ()
            }
        )
        for field in _REF_FIELDS
    }


def _remaining_gap_inventory(report: Mapping[str, Any]) -> dict[str, list[str]]:
    projection = {"remaining_gaps": report.get("remaining_gaps") or []}
    return {
        field: sorted(
            {
                str(ref)
                for row in projection["remaining_gaps"]
                if isinstance(row, Mapping)
                for ref in row.get(field) or ()
            }
        )
        for field in _REF_FIELDS
    }


def _model_text_projection(
    report: Mapping[str, Any], *, include_remaining_gaps: bool
) -> dict[str, str]:
    return {
        f"{path}.model_text": str(clause.get("model_text") or "")
        for path, clause in _iter_clauses(report)
        if include_remaining_gaps or not path.startswith("remaining_gaps[")
    }


def _reference_projection(
    report: Mapping[str, Any], *, include_remaining_gaps: bool
) -> dict[str, list[str]]:
    return {
        f"{path}.{field}": [str(value) for value in clause.get(field) or ()]
        for path, clause in _iter_clauses(report)
        if include_remaining_gaps or not path.startswith("remaining_gaps[")
        for field in _REF_FIELDS
    }


def _apply_manifest(
    source: Mapping[str, Any], manifest: Mapping[str, Any]
) -> dict[str, Any]:
    candidate = deepcopy(dict(source))
    for field_path, replacement in manifest["model_text_replacements"].items():
        _require(
            isinstance(field_path, str)
            and field_path.endswith(".model_text")
            and isinstance(replacement, str),
            "independent_writer_model_text_replacement_invalid",
        )
        clause = _clause_at_path(candidate, field_path[: -len(".model_text")])
        clause["model_text"] = replacement
    for field_path, replacement in manifest["reference_replacements"].items():
        _require(
            isinstance(field_path, str)
            and isinstance(replacement, list)
            and all(isinstance(value, str) for value in replacement),
            "independent_writer_reference_replacement_invalid",
        )
        clause_path, separator, field = field_path.rpartition(".")
        _require(
            separator == "." and field in _REF_FIELDS,
            "independent_writer_reference_replacement_invalid",
        )
        _clause_at_path(candidate, clause_path)[field] = deepcopy(replacement)
    candidate["remaining_gaps"] = deepcopy(
        manifest["remaining_gaps_replacement"]
    )
    return candidate


def _validate_topology(
    source: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    target_gap_rows: int,
) -> dict[str, Any]:
    source_sections = source.get("sections") or []
    candidate_sections = candidate.get("sections") or []
    checks = {
        "schema_version_unchanged": candidate.get("schema_version")
        == source.get("schema_version"),
        "report_topic_unchanged": candidate.get("report_topic")
        == source.get("report_topic"),
        "executive_clause_count_unchanged": len(
            candidate.get("executive_thesis") or []
        )
        == len(source.get("executive_thesis") or []),
        "section_count_unchanged": len(candidate_sections) == len(source_sections),
        "section_headings_unchanged": [
            row.get("heading") for row in candidate_sections
        ]
        == [row.get("heading") for row in source_sections],
        "section_clause_counts_unchanged": [
            len(row.get("clauses") or []) for row in candidate_sections
        ]
        == [len(row.get("clauses") or []) for row in source_sections],
        "what_would_change_count_unchanged": len(
            candidate.get("what_would_change") or []
        )
        == len(source.get("what_would_change") or []),
        "remaining_gap_rows_target_met": len(
            candidate.get("remaining_gaps") or []
        )
        == target_gap_rows,
    }
    _require(all(checks.values()), "independent_writer_topology_invalid")
    return checks


def _validate_change_boundary(
    source: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    decision: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    boundary = decision["change_boundary"]
    allowed_text_paths = sorted(boundary["allowed_changed_model_text_paths"])
    expected_reference_after = {
        str(path): [str(value) for value in refs]
        for path, refs in boundary["expected_reference_after"].items()
    }
    _require(
        sorted(manifest["model_text_replacements"]) == allowed_text_paths,
        "independent_writer_manifest_text_scope_invalid",
    )
    _require(
        {
            str(path): [str(value) for value in refs]
            for path, refs in manifest["reference_replacements"].items()
        }
        == expected_reference_after,
        "independent_writer_manifest_reference_scope_invalid",
    )
    source_text = _model_text_projection(source, include_remaining_gaps=False)
    candidate_text = _model_text_projection(candidate, include_remaining_gaps=False)
    changed_text = sorted(
        path for path, value in source_text.items() if candidate_text.get(path) != value
    )
    _require(
        changed_text == allowed_text_paths,
        "independent_writer_changed_text_scope_invalid",
    )
    source_refs = _reference_projection(source, include_remaining_gaps=False)
    candidate_refs = _reference_projection(candidate, include_remaining_gaps=False)
    changed_refs = sorted(
        path for path, value in source_refs.items() if candidate_refs.get(path) != value
    )
    _require(
        changed_refs == sorted(expected_reference_after)
        and all(
            candidate_refs.get(path) == expected
            for path, expected in expected_reference_after.items()
        ),
        "independent_writer_changed_reference_scope_invalid",
    )
    source_inventory = _inventory(source)
    candidate_inventory = _inventory(candidate)
    allowed_claim_additions = set(boundary["allowed_catalog_claim_refs_added"])
    _require(
        set(candidate_inventory["source_claim_refs"])
        - set(source_inventory["source_claim_refs"])
        <= allowed_claim_additions,
        "independent_writer_claim_authority_expansion_invalid",
    )
    for field in ("evidence_refs", "authority_refs", "gap_refs"):
        _require(
            set(candidate_inventory[field]).issubset(source_inventory[field]),
            "independent_writer_reference_authority_expansion_invalid",
        )
    _require(
        set(candidate_inventory["gap_refs"]) == set(source_inventory["gap_refs"]),
        "independent_writer_gap_union_not_preserved",
    )
    source_gap_inventory = _remaining_gap_inventory(source)
    candidate_gap_inventory = _remaining_gap_inventory(candidate)
    _require(
        source_gap_inventory == candidate_gap_inventory,
        "independent_writer_gap_register_authority_changed",
    )
    body = {
        "changed_model_text_paths": changed_text,
        "changed_reference_paths": changed_refs,
        "source_inventory_digest": canonical_digest(source_inventory),
        "candidate_inventory_digest": canonical_digest(candidate_inventory),
        "source_remaining_gap_inventory_digest": canonical_digest(
            source_gap_inventory
        ),
        "candidate_remaining_gap_inventory_digest": canonical_digest(
            candidate_gap_inventory
        ),
        "new_evidence_authority_or_gap_ids_added": False,
        "remaining_gap_ref_union_preserved": True,
        "remaining_gap_semantic_authority_inventory_preserved": True,
    }
    return {**body, "edit_receipt_digest": canonical_digest(body)}


def _extract_source_report(
    *,
    response: Mapping[str, Any],
    assessment: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        choices = response["response_body"]["choices"]
        call = choices[0]["message"]["tool_calls"][0]
        raw_arguments = call["function"]["arguments"]
        outer = json.loads(raw_arguments)
        nested_text = outer["arguments"]
        source = json.loads(nested_text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise IndependentWriterTakeoverError(
            "independent_writer_R14_capture_shape_invalid"
        ) from exc
    _require(
        len(choices) == 1
        and isinstance(raw_arguments, str)
        and isinstance(outer, Mapping)
        and set(outer) == {"arguments"}
        and isinstance(nested_text, str)
        and isinstance(source, Mapping),
        "independent_writer_R14_capture_identity_invalid",
    )
    inner = assessment.get("inner_nonpromotable_diagnostic") or {}
    expected = decision.get("expected_R14_failure_frontier") or {}
    nested_sha = hashlib.sha256(nested_text.encode("utf-8")).hexdigest()
    _require(
        nested_sha == inner.get("nested_sha256")
        and len(nested_text) == inner.get("nested_characters")
        and inner.get("hard_finding_count") == expected.get("hard_finding_count")
        and inner.get("quality_finding_count")
        == expected.get("quality_finding_count")
        and len(inner.get("surface_findings") or [])
        == expected.get("surface_finding_count")
        and find_r10_protected_writer_surface_findings(source)
        == expected.get("surface_findings"),
        "independent_writer_R14_failure_frontier_invalid",
    )
    receipt = {
        "outer_top_level_keys": sorted(outer),
        "nested_characters": len(nested_text),
        "nested_sha256": nested_sha,
        "nested_payload_digest": canonical_digest(source),
        "source_promoted": False,
    }
    return deepcopy(dict(source)), receipt


def compile_takeover(decision_ref: str | Path) -> dict[str, Any]:
    decision = _validate_decision(_read_json(decision_ref))
    values = {
        name: _validate_binding(binding)
        for name, binding in decision["source_bindings"].items()
    }
    assessment = values["R14_failure_assessment"]
    manifest = _validate_manifest(values["private_edit_manifest"])
    source, source_receipt = _extract_source_report(
        response=values["R14_response_capture"],
        assessment=assessment,
        decision=decision,
    )
    _require(
        manifest.get("source_nested_sha256") == source_receipt["nested_sha256"]
        and manifest.get("source_nested_payload_digest")
        == source_receipt["nested_payload_digest"],
        "independent_writer_manifest_source_binding_invalid",
    )
    candidate = _apply_manifest(source, manifest)
    topology = _validate_topology(
        source,
        candidate,
        target_gap_rows=int(decision["change_boundary"]["target_gap_rows"]),
    )
    edit_receipt = _validate_change_boundary(
        source,
        candidate,
        decision=decision,
        manifest=manifest,
    )
    surface_findings = find_r10_protected_writer_surface_findings(candidate)
    contract_audit = audit_protected_report_draft(
        candidate,
        authority_catalog=values["R10_writer_authority_catalog"],
    )
    _require(
        not surface_findings
        and contract_audit["hard_finding_count"] == 0
        and contract_audit["quality_finding_count"] == 0
        and contract_audit["contract_valid"] is True,
        "independent_writer_candidate_contract_audit_invalid",
    )
    trusted = validate_r10_protected_writer_draft(
        candidate,
        authority_catalog=values["R10_writer_authority_catalog"],
        protection=values["R10_writer_protection_contract"],
    )
    rendered = render_protected_report(
        trusted,
        authority_catalog=values["R10_writer_authority_catalog"],
    )
    execution = {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "new_evidence_items": 0,
        "candidate_promotions": 0,
    }
    acceptance = {
        "local_protected_contract_pass": True,
        "local_R10_protection_pass": True,
        "recommended_narrative_density_pass": True,
        "independent_post_writer_review_pass": False,
        "qualified_human_review_pass": False,
        "S3_pass": False,
        "product_acceptance": False,
        "publication": False,
        "release_ready": False,
    }
    recorded_at = _now()
    private_body = {
        "schema_version": PRIVATE_RESULT_SCHEMA_VERSION,
        "status": "locally_valid_candidate_post_writer_review_pending",
        "recorded_at": recorded_at,
        "case_key": "DELL",
        "run_id": RUN_ID,
        "decision_ref": str(decision_ref),
        "decision_sha256": _sha(decision_ref),
        "decision_digest": decision["decision_digest"],
        "source_receipt": source_receipt,
        "edit_manifest_binding": deepcopy(
            decision["source_bindings"]["private_edit_manifest"]
        ),
        "topology_receipt": topology,
        "edit_receipt": edit_receipt,
        "contract_audit": contract_audit,
        "candidate_draft": candidate,
        "trusted_report": trusted,
        "rendered_report": rendered,
        "execution": execution,
        "acceptance": acceptance,
        "known_boundary": (
            "This is a user-authorized Codex-authored local Writer candidate, "
            "not an independent or qualified-human review. It is not promoted, "
            "published, product-accepted, S3-accepted, or release-ready."
        ),
    }
    private = {
        **private_body,
        "full_result_digest": canonical_digest(private_body),
    }
    output = decision["output_contract"]
    private_ref = str(output["private_full_result_ref"])
    public_body = {
        "schema_version": PUBLIC_RESULT_SCHEMA_VERSION,
        "status": "locally_valid_candidate_post_writer_review_pending",
        "recorded_at": recorded_at,
        "case_key": "DELL",
        "run_id": RUN_ID,
        "implementation_commit": decision["implementation_commit"],
        "decision_ref": str(decision_ref),
        "decision_sha256": _sha(decision_ref),
        "decision_digest": decision["decision_digest"],
        "private_full_result_ref": private_ref,
        "private_full_result_sha256": _serialized_sha(private),
        "private_full_result_digest": private["full_result_digest"],
        "source_R14_public_result_digest": values["R14_public_result"][
            "result_digest"
        ],
        "source_R14_failure_assessment_digest": assessment[
            "assessment_digest"
        ],
        "source_nested_sha256": source_receipt["nested_sha256"],
        "edit_manifest_sha256": decision["source_bindings"][
            "private_edit_manifest"
        ]["sha256"],
        "edit_manifest_digest": manifest["manifest_digest"],
        "candidate_draft_digest": trusted["draft_digest"],
        "contract_finding_receipt_digest": contract_audit["receipt_digest"],
        "rendered_report_digest": rendered["rendered_report_digest"],
        "edit_receipt": edit_receipt,
        "topology_receipt": topology,
        "local_validation": {
            "surface_finding_count": 0,
            "hard_finding_count": 0,
            "quality_finding_count": 0,
            "protected_contract_pass": True,
            "R10_conditional_protection_pass": True,
        },
        "execution": execution,
        "acceptance": acceptance,
        "known_boundary": private_body["known_boundary"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    return {
        "decision": decision,
        "manifest": manifest,
        "source": source,
        "candidate": candidate,
        "private": private,
        "public": public,
    }


def materialize_takeover(decision_ref: str | Path) -> dict[str, Any]:
    bundle = compile_takeover(decision_ref)
    output = bundle["decision"]["output_contract"]
    private_ref = str(output["private_full_result_ref"])
    public_ref = str(output["public_result_ref"])
    _require(
        not _resolve(private_ref).exists() and not _resolve(public_ref).exists(),
        "independent_writer_output_identity_consumed",
    )
    _write_new(private_ref, bundle["private"])
    _write_new(public_ref, bundle["public"])
    _require(
        _sha(private_ref) == bundle["public"]["private_full_result_sha256"],
        "independent_writer_private_result_sha_invalid",
    )
    return bundle["public"]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the zero-provider R14-bound independent Writer takeover."
        )
    )
    parser.add_argument("command", choices=("validate", "materialize"))
    parser.add_argument("--decision-ref", required=True)
    args = parser.parse_args(argv)
    if args.command == "validate":
        result = compile_takeover(args.decision_ref)["public"]
    else:
        result = materialize_takeover(args.decision_ref)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
