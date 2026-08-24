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

from scripts.research import (  # noqa: E402
    materialize_s3_R16_bounded_writer_successor as r16,
)
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
    "R17_reversal_gate_successor_scope_decision_v1_0"
)
DECISION_STATUS = "approved_owner_bounded_zero_provider_reversal_gate_successor"
PRIVATE_SCHEMA = (
    "fin_ia_s3_current_dynamic_multi_agent_protected_writer_"
    "R17_reversal_gate_successor_full_result_v1_0"
)
PUBLIC_SCHEMA = (
    "fin_ia_s3_current_dynamic_multi_agent_protected_writer_"
    "R17_reversal_gate_successor_public_result_v1_0"
)
RUN_ID = "FIN_0_1_3_S3_DELL_R10_PROTECTED_WRITER_REVERSAL_GATE_R17"
DEFAULT_DECISION = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_R10_protected_writer_"
    "R17_reversal_gate_successor_scope_decision_v1_0.json"
)
_REPLACEMENTS = {
    "sections[5].clauses[5].model_text": (
        "Only order cancellations, impairments, or realized losses that are "
        "material, AI-linked, persistent, and evaluated as breaching a "
        "predeclared threshold would reverse the demand-quality judgment. An "
        "audited product margin would address the product-to-division bridge; "
        "attributed working-capital data would address product attribution; "
        "and cash conversion would still require a reconciled cash-flow "
        "bridge. These gates are separate and none is closed by the reviewed "
        "evidence."
    ),
    "what_would_change[5].model_text": (
        "A demand-quality reversal requires cancellation, impairment, or "
        "realized-loss evidence that is material, AI-linked, persistent, and "
        "evaluated as breaching a predeclared threshold. Audited product "
        "margin, attributed working capital, and a reconciled cash-flow "
        "bridge answer distinct questions and are not interchangeable."
    ),
}
_PERSIST_OR_THRESHOLD = re.compile(
    r"persist\w*\s+or\s+(?:\w+\s+){0,4}(?:breach|threshold)",
    re.IGNORECASE,
)


class R17SuccessorError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise R17SuccessorError(code)


def _implementation_refs() -> list[dict[str, str]]:
    paths = (
        "scripts/research/materialize_s3_R17_reversal_gate_successor.py",
        "scripts/research/materialize_s3_R16_bounded_writer_successor.py",
        "src/sec_agent/research/current_dynamic_writer.py",
        "src/sec_agent/research/multi_agent_report_authority.py",
    )
    return [
        {"ref": path, "sha256": r16._sha(path)}
        for path in paths
    ]


def _validate_implementation_bindings(decision: Mapping[str, Any]) -> None:
    expected = _implementation_refs()
    _require(
        decision.get("implementation_bindings") == expected,
        "R17_implementation_bindings_invalid",
    )


def reversal_gate_is_conjunctive(section_text: str, wwc_text: str) -> bool:
    texts = (section_text, wwc_text)
    if any(_PERSIST_OR_THRESHOLD.search(text) for text in texts):
        return False
    required = (
        "material",
        "AI-linked",
        "persistent",
        "evaluated as breaching a predeclared threshold",
    )
    return all(all(token in text for token in required) for text in texts)


def compile_successor(decision_ref: str | Path = DEFAULT_DECISION) -> dict[str, Any]:
    decision = r16._read_json(decision_ref)
    r16._validate_self_digest(decision, "decision_digest")
    _require(
        decision.get("schema_version") == DECISION_SCHEMA
        and decision.get("status") == DECISION_STATUS
        and decision.get("run_id") == RUN_ID
        and decision.get("case_key") == "DELL",
        "R17_decision_identity_invalid",
    )
    _validate_implementation_bindings(decision)
    budget = decision.get("execution_budget")
    _require(
        isinstance(budget, Mapping)
        and budget
        and all(int(value) == 0 for value in budget.values()),
        "R17_execution_budget_invalid",
    )
    bindings = decision.get("source_bindings")
    _require(isinstance(bindings, Mapping), "R17_source_bindings_invalid")
    values = {name: r16._bound_value(binding) for name, binding in bindings.items()}
    source_full = values["R16_private_full_result"]
    r16._validate_self_digest(source_full, "full_result_digest")
    source_public = values["R16_public_candidate"]
    r16._validate_self_digest(source_public, "result_digest")
    review = values["R16_fresh_independent_review"]
    _require(
        review.get("status") == "fresh_independent_review_failed_material_finding"
        and review.get("review", {}).get("independent_review") is True
        and any(
            finding.get("classification") == "P1_material_reversal_gate"
            for finding in review.get("findings") or []
        ),
        "R17_independent_review_finding_invalid",
    )
    source = deepcopy(source_full["candidate_draft"])
    candidate = deepcopy(source)
    allowed = sorted(
        decision["change_boundary"]["allowed_changed_model_text_paths"]
    )
    _require(sorted(_REPLACEMENTS) == allowed, "R17_replacement_scope_invalid")
    for path, replacement in _REPLACEMENTS.items():
        r16._clause(candidate, path)["model_text"] = replacement

    source_text = r16._text_projection(source)
    candidate_text = r16._text_projection(candidate)
    changed = sorted(
        path for path, value in source_text.items() if candidate_text[path] != value
    )
    _require(changed == allowed, "R17_changed_text_scope_invalid")
    source_refs = r16._reference_projection(source)
    candidate_refs = r16._reference_projection(candidate)
    _require(source_refs == candidate_refs, "R17_reference_inventory_changed")
    _require(
        source.get("remaining_gaps") == candidate.get("remaining_gaps"),
        "R17_remaining_gaps_changed",
    )
    _require(
        r16._topology(source) == r16._topology(candidate),
        "R17_topology_changed",
    )
    section_text = r16._clause(
        candidate, "sections[5].clauses[5].model_text"
    )["model_text"]
    wwc_text = r16._clause(
        candidate, "what_would_change[5].model_text"
    )["model_text"]
    _require(
        reversal_gate_is_conjunctive(section_text, wwc_text),
        "R17_reversal_gate_not_conjunctive",
    )

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
        "R17_protected_contract_invalid",
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
        "reversal_gate_conjunction_proved": True,
        "one_off_threshold_breach_is_insufficient": True,
        "persistent_below_threshold_evidence_is_insufficient": True,
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
        "fresh_independent_post_writer_review_pass": False,
        "qualified_human_review_pass": False,
        "S3_pass": False,
        "product_acceptance": False,
        "publication": False,
        "release_ready": False,
    }
    recorded_at = datetime.now(timezone.utc).astimezone().isoformat(
        timespec="seconds"
    )
    implementation_refs = _implementation_refs()
    private_body = {
        "schema_version": PRIVATE_SCHEMA,
        "status": "R17_local_bounded_candidate_fresh_review_pending",
        "recorded_at": recorded_at,
        "run_id": RUN_ID,
        "case_key": "DELL",
        "decision_ref": str(decision_ref),
        "decision_sha256": r16._sha(decision_ref),
        "decision_digest": decision["decision_digest"],
        "source_bindings": deepcopy(dict(bindings)),
        "implementation_refs": implementation_refs,
        "edit_receipt": edit_receipt,
        "contract_audit": contract_audit,
        "candidate_draft": candidate,
        "trusted_report": trusted,
        "rendered_report": rendered,
        "execution": execution,
        "acceptance": acceptance,
        "known_boundary": (
            "R17 is a zero-provider Codex-authored bounded successor to the "
            "fresh independently failed R16. It is not its own fresh "
            "independent or qualified-human review and grants no S3, product, "
            "publication, or release authority."
        ),
    }
    private = {
        **private_body,
        "full_result_digest": canonical_digest(private_body),
    }
    private_bytes = r16._serialized(private)
    public_body = {
        "schema_version": PUBLIC_SCHEMA,
        "status": "R17_local_bounded_candidate_fresh_review_pending",
        "recorded_at": recorded_at,
        "run_id": RUN_ID,
        "case_key": "DELL",
        "decision_ref": str(decision_ref),
        "decision_sha256": r16._sha(decision_ref),
        "decision_digest": decision["decision_digest"],
        "source_R16_result_digest": source_public["result_digest"],
        "source_R16_fresh_review_status": review["status"],
        "private_full_result_ref": decision["output_contract"][
            "private_full_result_ref"
        ],
        "private_full_result_sha256": hashlib.sha256(private_bytes).hexdigest(),
        "private_full_result_digest": private["full_result_digest"],
        "candidate_draft_digest": trusted["draft_digest"],
        "rendered_report_digest": rendered["rendered_report_digest"],
        "contract_finding_receipt_digest": contract_audit["receipt_digest"],
        "implementation_refs": implementation_refs,
        "edit_receipt": edit_receipt,
        "local_validation": {
            "surface_finding_count": 0,
            "hard_finding_count": 0,
            "quality_finding_count": 0,
            "protected_contract_pass": True,
            "reversal_gate_conjunction_proved": True,
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
    private_path = r16._resolve(output["private_full_result_ref"])
    public_path = r16._resolve(output["public_result_ref"])
    _require(
        not private_path.exists() and not public_path.exists(),
        "R17_output_identity_consumed",
    )
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.write_bytes(r16._serialized(bundle["private"]))
    public_path.write_bytes(r16._serialized(bundle["public"]))
    _require(
        r16._sha(private_path)
        == bundle["public"]["private_full_result_sha256"],
        "R17_private_result_sha_mismatch",
    )
    return bundle["public"]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate or materialize the zero-provider R17 reversal gate."
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
