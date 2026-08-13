from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "src"):
    value = str(candidate)
    if value not in sys.path:
        sys.path.insert(0, value)

from apps.workbench.backend.application.research_evidence_pack_service import (  # noqa: E402
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from apps.workbench.backend.application.research_workspace_service import (  # noqa: E402
    ResearchWorkspacePrincipal,
    ResearchWorkspaceService,
)
from sec_agent.runtime_resource_registry import read_registered_runtime_json  # noqa: E402


EXPECTED_IDENTITIES = {
    "DELL": ("Dell Technologies Inc.", "0001571996", "NYSE"),
    "MU": ("Micron Technology, Inc.", "0000723125", "NASDAQ"),
    "NVDA": ("NVIDIA Corporation", "0001045810", "NASDAQ"),
}
EXPECTED_AS_OF = "2026-08-06"
REQUIRED_GAP_FACETS = {"valuation_basis", "scenario_or_sensitivity"}


def _load_services(data_root: Path) -> tuple[ResearchWorkspaceService, ResearchEvidencePackService]:
    evidence_config = read_registered_runtime_json(
        ROOT, "application.config.current_research_evidence_pack_projection"
    )
    result = read_registered_runtime_json(
        ROOT, str(evidence_config["source_result_resource_id"])
    )
    evidence = ResearchEvidencePackService(
        config=evidence_config,
        result=result,
        private_object_root=(
            data_root
            / "workbench_private"
            / str(evidence_config["private_object_root_relative"])
        ),
        private_root_base=data_root / "workbench_private",
    )
    workspace_config = read_registered_runtime_json(
        ROOT, "application.config.current_research_workspace_catalog"
    )
    return (
        ResearchWorkspaceService(
            config=workspace_config,
            evidence_packs=evidence,
        ),
        evidence,
    )


def build_report(data_root: Path) -> dict[str, object]:
    workspace, evidence_service = _load_services(data_root.resolve())
    workspace_principal = ResearchWorkspacePrincipal(
        mode="current", permissions=frozenset({"current_product:read"})
    )
    evidence_principal = ResearchEvidencePackPrincipal(
        mode="current", permissions=frozenset({"current_product:read"})
    )
    readiness = evidence_service.readiness()
    violations: list[str] = []
    cases: list[dict[str, object]] = []
    listed = workspace.list_cases(workspace_principal)
    if [row["case_key"] for row in listed["items"]] != list(EXPECTED_IDENTITIES):
        violations.append("case_partition_drift")
    if not readiness["all_ready"]:
        violations.append("reviewed_evidence_object_mount_incomplete")

    for summary in listed["items"]:
        case_key = str(summary["case_key"])
        expected_name, expected_issuer, expected_exchange = EXPECTED_IDENTITIES[case_key]
        subject = dict(summary["subject"])
        if (
            subject.get("legal_name"),
            subject.get("issuer_id"),
            subject.get("exchange"),
        ) != (expected_name, expected_issuer, expected_exchange):
            violations.append(f"{case_key}:issuer_identity_drift")
        if summary.get("research_as_of") != EXPECTED_AS_OF:
            violations.append(f"{case_key}:research_as_of_drift")

        try:
            evidence = workspace.get_evidence(
                str(summary["case_id"]), workspace_principal
            )
        except Exception as exc:  # typed service error is summarized, never leaked
            violations.append(f"{case_key}:evidence_unavailable:{type(exc).__name__}")
            continue

        items = list(evidence["evidence_items"])
        gaps = list(evidence["residual_gaps"])
        source_domains: set[str] = set()
        slots: set[str] = set()
        owner_tickers: set[str] = set()
        cross_case_items = 0
        structured_numeric_items = 0
        for item in items:
            source = dict(item["source"])
            owner = str(source.get("evidence_owner_ticker") or "")
            owner_tickers.add(owner)
            domain = urlparse(str(source.get("source_url") or "")).hostname or ""
            source_domains.add(domain.lower())
            if not domain or not str(source.get("source_url") or "").startswith("https://"):
                violations.append(f"{case_key}:invalid_source_url")
            as_of = str(item.get("research_as_of") or "")
            publication = str(item.get("publication_date") or "")
            if as_of != EXPECTED_AS_OF:
                violations.append(f"{case_key}:evidence_as_of_drift")
            if publication and date.fromisoformat(publication) > date.fromisoformat(EXPECTED_AS_OF):
                violations.append(f"{case_key}:future_dated_evidence")
            slot_rows = list(item.get("slot_bindings") or ())
            if not slot_rows:
                violations.append(f"{case_key}:evidence_without_slot")
            slots.update(str(row.get("slot_id") or "") for row in slot_rows)
            if item.get("structured_metric"):
                structured_numeric_items += 1
            if owner != case_key:
                cross_case_items += 1
                if (
                    item.get("evidence_role")
                    != "counterparty_or_ecosystem_readthrough"
                    or not item.get("relationship_directions")
                    or item.get("causal_attribution_authorized") is not False
                ):
                    violations.append(
                        f"{case_key}:cross_company_evidence_boundary_missing"
                    )

        gap_facets = {str(row.get("facet_id") or "") for row in gaps}
        if not REQUIRED_GAP_FACETS.issubset(gap_facets):
            violations.append(f"{case_key}:required_valuation_gap_not_visible")
        if case_key not in owner_tickers:
            violations.append(f"{case_key}:no_issuer_owned_evidence")
        cases.append(
            {
                "case_key": case_key,
                "legal_name": subject["legal_name"],
                "issuer_id": subject["issuer_id"],
                "research_as_of": summary["research_as_of"],
                "binding_state": summary["pack_binding"]["binding_state"],
                "accepted_evidence_items": len(items),
                "cross_company_readthrough_items": cross_case_items,
                "structured_numeric_items": structured_numeric_items,
                "residual_gaps": len(gaps),
                "slot_coverage": sorted(slot for slot in slots if slot),
                "evidence_owner_tickers": sorted(owner_tickers),
                "source_domains": sorted(source_domains),
            }
        )

    return {
        "schema_version": "fin_ia_0_1_3_three_case_business_acceptance_v1_0",
        "recorded_at": "2026-08-12",
        "status": "pass" if not violations else "fail",
        "scope": "identity_bound_reviewed_evidence_workspace_not_full_research_report",
        "cases": cases,
        "violations": sorted(set(violations)),
        "bounded_findings": [
            "All current source domains are SEC filings; source diversity remains a later S1/S3 product task.",
            "The reviewed packs currently expose zero structured numeric items; numeric fact surfaces are not claimed by this baseline.",
            "Valuation, scenario sensitivity and commercial allocation remain visible typed gaps rather than inferred facts.",
        ],
        "safety": {
            "model_calls": 0,
            "provider_calls": 0,
            "live_network_calls": 0,
            "source_text_in_report": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(args.data_root)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output = output.resolve()
        output.relative_to(ROOT)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
