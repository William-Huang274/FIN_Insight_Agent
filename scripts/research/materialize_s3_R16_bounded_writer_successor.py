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


DECISION_SCHEMA = (
    "fin_ia_s3_current_dynamic_multi_agent_protected_writer_"
    "R16_bounded_successor_scope_decision_v1_0"
)
DECISION_STATUS = "approved_owner_bounded_zero_provider_text_successor"
PRIVATE_SCHEMA = (
    "fin_ia_s3_current_dynamic_multi_agent_protected_writer_"
    "R16_bounded_successor_full_result_v1_0"
)
PUBLIC_SCHEMA = (
    "fin_ia_s3_current_dynamic_multi_agent_protected_writer_"
    "R16_bounded_successor_public_result_v1_0"
)
RUN_ID = "FIN_0_1_3_S3_DELL_R10_PROTECTED_WRITER_BOUNDED_SUCCESSOR_R16"
DEFAULT_DECISION = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_R10_protected_writer_"
    "R16_bounded_successor_scope_decision_v1_0.json"
)
_SECTION_PATH = re.compile(r"^sections\[(\d+)\]\.clauses\[(\d+)\]\.model_text$")
_WWC_PATH = re.compile(r"^what_would_change\[(\d+)\]\.model_text$")
_REF_FIELDS = (
    "source_workpaper_agent_ids",
    "source_claim_refs",
    "evidence_refs",
    "authority_refs",
    "gap_refs",
)
_REPLACEMENTS = {
    "sections[1].clauses[0].model_text": (
        "At the consolidated level, revenue, operating profit, and net profit "
        "all increased against the comparable prior-year quarter, with profit "
        "increasing faster than revenue. This proves same-company, same-period "
        "co-growth; it does not establish an order or product-revenue cohort "
        "converting into profit, and it carries no AI product attribution."
    ),
    "sections[3].clauses[0].model_text": (
        "On a consolidated basis the quarter's operating cash flow rose year "
        "over year, operating cash flow exceeded net income, and free cash "
        "flow moved in the same direction. Free cash flow here is the "
        "deterministic non-GAAP derivation of operating cash flow less capital "
        "expenditures, not a GAAP line item. These are positive company-level "
        "coverage signals, but they carry no product-line attribution and "
        "cannot be described as AI cash conversion."
    ),
    "sections[4].clauses[4].model_text": (
        "The period-end inventory balance is company-level context only. "
        "Without product attribution, turnover, impairment, or causal "
        "reconciliation, the absolute balance neither corroborates nor "
        "quantifies AI stocking risk. No realized order cancellation, inventory "
        "impairment, or quantified loss is present in the reviewed evidence, so "
        "the counterevidence remains a risk disclosure rather than a realized "
        "loss."
    ),
    "sections[5].clauses[1].model_text": (
        "Order behavior after supply is released would help distinguish the "
        "competing explanations: a persistent decline in AI orders supported "
        "only by the existing backlog would favor the supply-queueing and "
        "pull-forward reading, while continued high order growth after supply "
        "normalization would support durable demand. It would not uniquely "
        "identify causality by itself."
    ),
    "sections[5].clauses[5].model_text": (
        "Only material, AI-linked order cancellations, impairments, or realized "
        "losses that persist or breach a predeclared threshold would reverse "
        "the demand-quality judgment. An audited product margin would address "
        "the product-to-division bridge; attributed working-capital data would "
        "address product attribution; and cash conversion would still require "
        "a reconciled cash-flow bridge. These gates are separate and none is "
        "closed by the reviewed evidence."
    ),
    "what_would_change[1].model_text": (
        "Post-supply-release order behavior would help distinguish the "
        "competing reads: sustained order decline relying on existing backlog "
        "favors queueing and pull-forward explanations, while continued order "
        "strength after supply normalization supports durable demand; neither "
        "path uniquely identifies causality by itself."
    ),
    "what_would_change[5].model_text": (
        "A demand-quality reversal requires material, AI-linked and persistent "
        "cancellation, impairment, or realized-loss evidence evaluated against "
        "a predeclared threshold. Audited product margin, attributed working "
        "capital, and a reconciled cash-flow bridge answer distinct "
        "questions and are not interchangeable."
    ),
}


class R16SuccessorError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise R16SuccessorError(code)


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(value: str | Path) -> dict[str, Any]:
    payload = json.loads(_resolve(value).read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), "R16_json_object_required")
    return payload


def _sha(value: str | Path) -> str:
    return hashlib.sha256(_resolve(value).read_bytes()).hexdigest()


def _serialized(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _validate_self_digest(value: Mapping[str, Any], field: str) -> None:
    unsigned = {key: item for key, item in value.items() if key != field}
    _require(value.get(field) == canonical_digest(unsigned), f"R16_{field}_invalid")


def _bound_value(binding: Mapping[str, Any]) -> dict[str, Any]:
    ref = binding.get("ref")
    expected_sha = binding.get("sha256")
    _require(isinstance(ref, str) and isinstance(expected_sha, str), "R16_binding_invalid")
    _require(_sha(ref) == expected_sha, "R16_binding_sha_mismatch")
    value = _read_json(ref)
    if binding.get("digest") is not None:
        field = binding.get("digest_field")
        _require(
            isinstance(field, str) and value.get(field) == binding.get("digest"),
            "R16_binding_digest_mismatch",
        )
    return value


def _clause(report: Mapping[str, Any], path: str) -> dict[str, Any]:
    if match := _SECTION_PATH.fullmatch(path):
        section_index, clause_index = (int(value) for value in match.groups())
        sections = report.get("sections")
        _require(isinstance(sections, list), "R16_edit_path_invalid")
        value = sections[section_index]["clauses"][clause_index]
    elif match := _WWC_PATH.fullmatch(path):
        rows = report.get("what_would_change")
        _require(isinstance(rows, list), "R16_edit_path_invalid")
        value = rows[int(match.group(1))]
    else:
        raise R16SuccessorError("R16_edit_path_invalid")
    _require(isinstance(value, dict), "R16_edit_clause_invalid")
    return value


def _iter_clauses(report: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    output: list[tuple[str, Mapping[str, Any]]] = []
    output.extend(
        (f"executive_thesis[{index}]", row)
        for index, row in enumerate(report.get("executive_thesis") or [])
    )
    for section_index, section in enumerate(report.get("sections") or []):
        output.extend(
            (f"sections[{section_index}].clauses[{index}]", row)
            for index, row in enumerate(section.get("clauses") or [])
        )
    output.extend(
        (f"remaining_gaps[{index}]", row)
        for index, row in enumerate(report.get("remaining_gaps") or [])
    )
    output.extend(
        (f"what_would_change[{index}]", row)
        for index, row in enumerate(report.get("what_would_change") or [])
    )
    if isinstance(report.get("confidence"), Mapping):
        output.append(("confidence", report["confidence"]))
    return output


def _text_projection(report: Mapping[str, Any]) -> dict[str, str]:
    return {
        f"{path}.model_text": str(row.get("model_text") or "")
        for path, row in _iter_clauses(report)
    }


def _reference_projection(report: Mapping[str, Any]) -> dict[str, list[str]]:
    return {
        f"{path}.{field}": [str(value) for value in row.get(field) or []]
        for path, row in _iter_clauses(report)
        for field in _REF_FIELDS
    }


def _topology(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report.get("schema_version"),
        "report_topic": report.get("report_topic"),
        "executive_count": len(report.get("executive_thesis") or []),
        "section_headings": [
            section.get("heading") for section in report.get("sections") or []
        ],
        "section_clause_counts": [
            len(section.get("clauses") or [])
            for section in report.get("sections") or []
        ],
        "remaining_gap_count": len(report.get("remaining_gaps") or []),
        "what_would_change_count": len(report.get("what_would_change") or []),
    }


def compile_successor(decision_ref: str | Path = DEFAULT_DECISION) -> dict[str, Any]:
    decision = _read_json(decision_ref)
    _validate_self_digest(decision, "decision_digest")
    _require(
        decision.get("schema_version") == DECISION_SCHEMA
        and decision.get("status") == DECISION_STATUS
        and decision.get("run_id") == RUN_ID
        and decision.get("case_key") == "DELL",
        "R16_decision_identity_invalid",
    )
    budget = decision.get("execution_budget")
    _require(
        isinstance(budget, Mapping)
        and budget
        and all(int(value) == 0 for value in budget.values()),
        "R16_execution_budget_invalid",
    )
    bindings = decision.get("source_bindings")
    _require(isinstance(bindings, Mapping), "R16_source_bindings_invalid")
    values = {name: _bound_value(binding) for name, binding in bindings.items()}
    source_full = values["R15_private_full_result"]
    _validate_self_digest(source_full, "full_result_digest")
    review = values["R15_independent_review"]
    _require(
        review.get("status")
        == "independent_post_writer_review_failed_material_finding"
        and review.get("material_finding", {}).get("classification")
        == "P1_material"
        and review.get("acceptance", {}).get(
            "independent_post_writer_review_pass"
        )
        is False,
        "R16_independent_review_finding_invalid",
    )
    source = deepcopy(source_full["candidate_draft"])
    candidate = deepcopy(source)
    allowed = sorted(
        decision["change_boundary"]["allowed_changed_model_text_paths"]
    )
    _require(sorted(_REPLACEMENTS) == allowed, "R16_replacement_scope_invalid")
    for path, replacement in _REPLACEMENTS.items():
        _clause(candidate, path)["model_text"] = replacement

    source_text = _text_projection(source)
    candidate_text = _text_projection(candidate)
    changed = sorted(
        path for path, value in source_text.items() if candidate_text[path] != value
    )
    _require(changed == allowed, "R16_changed_text_scope_invalid")
    source_refs = _reference_projection(source)
    candidate_refs = _reference_projection(candidate)
    _require(source_refs == candidate_refs, "R16_reference_inventory_changed")
    _require(
        source.get("remaining_gaps") == candidate.get("remaining_gaps"),
        "R16_remaining_gaps_changed",
    )
    _require(_topology(source) == _topology(candidate), "R16_topology_changed")

    surface_findings = find_r10_protected_writer_surface_findings(candidate)
    contract_audit = audit_protected_report_draft(
        candidate,
        authority_catalog=values["R10_authority_catalog"],
    )
    _require(
        not surface_findings
        and contract_audit["hard_finding_count"] == 0
        and contract_audit["quality_finding_count"] == 0
        and contract_audit["contract_valid"] is True,
        "R16_protected_contract_invalid",
    )
    trusted = validate_r10_protected_writer_draft(
        candidate,
        authority_catalog=values["R10_authority_catalog"],
        protection=values["R10_protection_contract"],
    )
    rendered = render_protected_report(
        trusted,
        authority_catalog=values["R10_authority_catalog"],
    )
    edit_receipt_body = {
        "changed_model_text_paths": changed,
        "reference_projection_unchanged": True,
        "remaining_gaps_unchanged": True,
        "topology_unchanged": True,
        "source_text_projection_digest": canonical_digest(source_text),
        "candidate_text_projection_digest": canonical_digest(candidate_text),
        "reference_projection_digest": canonical_digest(source_refs),
    }
    edit_receipt = {
        **edit_receipt_body,
        "edit_receipt_digest": canonical_digest(edit_receipt_body),
    }
    execution = dict(budget)
    acceptance = {
        "local_protected_contract_pass": True,
        "independent_post_writer_review_pass": False,
        "qualified_human_review_pass": False,
        "S3_pass": False,
        "product_acceptance": False,
        "publication": False,
        "release_ready": False,
    }
    recorded_at = datetime.now(timezone.utc).astimezone().isoformat(
        timespec="seconds"
    )
    private_body = {
        "schema_version": PRIVATE_SCHEMA,
        "status": "R16_local_bounded_candidate_independent_review_pending",
        "recorded_at": recorded_at,
        "run_id": RUN_ID,
        "case_key": "DELL",
        "decision_ref": str(decision_ref),
        "decision_sha256": _sha(decision_ref),
        "decision_digest": decision["decision_digest"],
        "source_bindings": deepcopy(dict(bindings)),
        "edit_receipt": edit_receipt,
        "contract_audit": contract_audit,
        "candidate_draft": candidate,
        "trusted_report": trusted,
        "rendered_report": rendered,
        "execution": execution,
        "acceptance": acceptance,
        "known_boundary": (
            "R16 is a zero-provider Codex-authored bounded successor to an "
            "immutable independently failed R15. It is not its own independent "
            "or qualified-human review and grants no S3, product, publication, "
            "or release authority."
        ),
    }
    private = {
        **private_body,
        "full_result_digest": canonical_digest(private_body),
    }
    private_bytes = _serialized(private)
    public_body = {
        "schema_version": PUBLIC_SCHEMA,
        "status": "R16_local_bounded_candidate_independent_review_pending",
        "recorded_at": recorded_at,
        "run_id": RUN_ID,
        "case_key": "DELL",
        "decision_ref": str(decision_ref),
        "decision_sha256": _sha(decision_ref),
        "decision_digest": decision["decision_digest"],
        "source_R15_result_digest": values["R15_public_candidate"][
            "result_digest"
        ],
        "source_R15_independent_review_status": review["status"],
        "private_full_result_ref": decision["output_contract"][
            "private_full_result_ref"
        ],
        "private_full_result_sha256": hashlib.sha256(private_bytes).hexdigest(),
        "private_full_result_digest": private["full_result_digest"],
        "candidate_draft_digest": trusted["draft_digest"],
        "rendered_report_digest": rendered["rendered_report_digest"],
        "contract_finding_receipt_digest": contract_audit["receipt_digest"],
        "edit_receipt": edit_receipt,
        "local_validation": {
            "surface_finding_count": 0,
            "hard_finding_count": 0,
            "quality_finding_count": 0,
            "protected_contract_pass": True,
        },
        "execution": execution,
        "acceptance": acceptance,
        "known_boundary": private_body["known_boundary"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    return {"decision": decision, "private": private, "public": public}


def materialize_successor(
    decision_ref: str | Path = DEFAULT_DECISION,
) -> dict[str, Any]:
    bundle = compile_successor(decision_ref)
    output = bundle["decision"]["output_contract"]
    private_path = _resolve(output["private_full_result_ref"])
    public_path = _resolve(output["public_result_ref"])
    _require(
        not private_path.exists() and not public_path.exists(),
        "R16_output_identity_consumed",
    )
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.write_bytes(_serialized(bundle["private"]))
    public_path.write_bytes(_serialized(bundle["public"]))
    _require(
        _sha(private_path)
        == bundle["public"]["private_full_result_sha256"],
        "R16_private_result_sha_mismatch",
    )
    return bundle["public"]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate or materialize the zero-provider R16 bounded successor."
    )
    parser.add_argument("command", choices=("validate", "materialize"))
    parser.add_argument("--decision-ref", default=DEFAULT_DECISION)
    args = parser.parse_args(argv)
    result = (
        compile_successor(args.decision_ref)["public"]
        if args.command == "validate"
        else materialize_successor(args.decision_ref)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
