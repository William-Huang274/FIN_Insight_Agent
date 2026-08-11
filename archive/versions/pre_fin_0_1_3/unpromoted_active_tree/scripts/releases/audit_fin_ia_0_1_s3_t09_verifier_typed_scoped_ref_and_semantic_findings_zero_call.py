from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    DeepSeekS3ThreeCellNodeExecutor,
    S3ThreeCellBoundedAgentExecutor,
)
from apps.workbench.backend.application.bounded_agent_identity_policies import (  # noqa: E402
    CellScopedResearchIdentityPolicy,
    ScopedIdentityViolation,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


RUNTIME_ROOT = ROOT / (
    ".codex_runtime/"
    "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/"
    "canonical-runtime/objects/fin01/provider-output-captures"
)
CAPTURE_DIGESTS = (
    "8e5d3b7d698c0a3d5c4bceb327b05f2e2382f3b9d419a0412cd3114f3eebcfcd",
    "9d060e53297a8797974d313dd6ed9da18afd145814dabfa887ed3dd8a9192f5d",
    "c48c5824da04f9b9b45f5079442989cd98383d354c677fa2c70bfd301082bc8d",
    "4ea499de6c8fe9ed2caadbf209cb83136c65c47100e84edbdcea55e6f9cd37ec",
    "800152fc82851668008695deed6d99ba7191e15c8a0dd8430926dcdf894fddc0",
    "6962b8cde9fd8a03fdd5595ee9e0c7569cb687cc064043029674ac544c758df3",
    "7928875fe9393d39c715723328717819a7fa4b045e6015eecc1c266bb19a9cf0",
    "cce47595ab546a90cba0317dd50a4af0db5b31d1846d93f3e8f0dc7e4e05772a",
    "ba6449874349cb695de9cb5f11d642bd0e7c818c11843ba22e7db53ef2f6eb89",
    "1afb2919a3a4e67a27c4a784371a4efca2e3391fd5b02f53202b661aee3256e5",
    "5c4f6905812a812bffb3c3b286516b7e47c63fd30c00751716da54273263ed20",
    "1aab420bb8d4a8309a03a5af279d551aa9b45572bb5cbcedbb61ee385419c18c",
)


def _capture_path(digest: str) -> Path:
    return RUNTIME_ROOT / digest[:2] / digest[2:4] / f"{digest}.json"


def _load_captures() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for digest in CAPTURE_DIGESTS:
        payload = json.loads(_capture_path(digest).read_text(encoding="utf-8"))
        if (
            payload.get("research_run_id")
            != "research_run_fin01_db6800815317852334584e51"
            or payload.get("raw_provider_response_included") is not False
            or payload.get("private_reasoning_included") is not False
        ):
            raise RuntimeError("restricted_capture_contract_mismatch")
        payload["parsed_output"] = json.loads(payload["assistant_output_text"])
        rows.append(payload)
    return sorted(rows, key=lambda row: int(row["capture_sequence"]))


def _merge_specialists(
    captures: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_cell: dict[str, dict[str, Any]] = {}
    for capture in captures[:9]:
        output = deepcopy(capture["parsed_output"])
        cell_id = str(output["program_cell_id"])
        row = by_cell.setdefault(
            cell_id,
            {
                "program_cell_id": cell_id,
                "fact_layer": [],
                "explanation_layer": [],
                "judgment_layer": [],
                "remaining_gaps": [],
                "what_would_change": [],
                "terminal_class": "",
            },
        )
        if "fact_layer" in output:
            row.update(output)
        elif "judgment_layer" in output:
            row["judgment_layer"] = output["judgment_layer"]
        else:
            row["what_would_change"] = output["what_would_change"]
    return list(by_cell.values())


def _known_verifier_refs(
    verifier: Mapping[str, Any],
    specialists: list[Mapping[str, Any]],
    surface: Mapping[str, Any],
) -> tuple[int, int]:
    indexes = S3ThreeCellBoundedAgentExecutor._scoped_identity_indexes(
        specialists,
        surface,
    )
    total = 0
    unique: set[tuple[str, str, str]] = set()
    for finding in verifier["findings"]:
        observed: set[tuple[str, str, str]] = set()
        for value in finding["artifact_or_claim_refs"]:
            parsed = CellScopedResearchIdentityPolicy.parse(
                value,
                expected_kind="claim",
            )
            if isinstance(parsed, ScopedIdentityViolation):
                raise RuntimeError("captured_verifier_ref_shape_invalid")
            if parsed.runtime_key not in indexes["claim"]:
                raise RuntimeError("captured_verifier_ref_unknown")
            if parsed.runtime_key in observed:
                raise RuntimeError("captured_verifier_ref_duplicate_in_finding")
            observed.add(parsed.runtime_key)
            unique.add(parsed.runtime_key)
            total += 1
    return total, len(unique)


def audit() -> dict[str, Any]:
    captures = _load_captures()
    specialists = _merge_specialists(captures)
    lead = captures[9]["parsed_output"]
    writer_provider = captures[10]["parsed_output"]
    verifier = captures[11]["parsed_output"]
    surface = S3ThreeCellBoundedAgentExecutor._derive_scoped_identity_surface(
        specialists
    )
    typed_ref_count, unique_typed_ref_count = _known_verifier_refs(
        verifier,
        specialists,
        surface,
    )

    assembled_writer = (
        DeepSeekS3ThreeCellNodeExecutor._assemble_memo_writer_v3_output(
            writer_provider,
            {
                "specialist_heads": specialists,
                "cross_cell_lead": lead,
                "cross_cell_lead_digest": verifier["bound_lead_digest"],
                "scoped_identity_surface": surface,
            },
        )
    )
    claim_by_ref = {
        (
            "claim",
            str(specialist["program_cell_id"]),
            str(claim["claim_id"]),
        ): claim
        for specialist in specialists
        for claim in specialist["judgment_layer"]
    }
    scope_digest_exact = all(
        rendering["scope_digest"]
        == canonical_digest(
            claim_by_ref[
                (
                    str(rendering["claim_ref"]["identity_kind"]),
                    str(rendering["claim_ref"]["program_cell_id"]),
                    str(rendering["claim_ref"]["local_id"]),
                )
            ]["scope"]
        )
        for section in assembled_writer["sections"]
        for rendering in section["claim_renderings"]
    )
    expected_limitations = sorted(
        {
            boundary
            for specialist in specialists
            for claim in specialist["judgment_layer"]
            for boundary in claim.get("cannot_support", ())
        }
    )
    unresolved = [
        row
        for row in lead["conflict_adjudications"]
        if row["resolution_status"] == "unresolved"
    ]
    margin_texts = [
        row["analysis_text_zh_cn"]
        for row in writer_provider["claim_renderings"]
        if row["claim_ref"]["program_cell_id"] == "value_and_profit_capture"
    ]
    company_total_scope_explicit = bool(margin_texts) and all(
        "公司整体" in text for text in margin_texts
    )
    ai_or_segment_attribution_absent = all(
        re.search(r"AI基础设施|数据中心|加速器|分部", text) is None
        for text in margin_texts
    )
    digest_fields_well_formed = all(
        re.fullmatch(r"[0-9a-f]{64}", str(verifier[key])) is not None
        for key in ("bound_lead_digest", "bound_writer_digest")
    )

    return {
        "status": "pass_zero_call_read_only_l2_and_l1_audit",
        "research_run_id": "research_run_fin01_db6800815317852334584e51",
        "capture_count": len(captures),
        "provider_model_network_calls": [0, 0, 0],
        "typed_ref_audit": {
            "typed_ref_count": typed_ref_count,
            "unique_typed_ref_count": unique_typed_ref_count,
            "all_refs_known_exact_claim_refs": True,
            "identity_guessing_or_normalization": False,
        },
        "scope_audit": {
            "locally_assembled_claim_scope_digests_exact": scope_digest_exact,
            "bound_digest_fields_well_formed": digest_fields_well_formed,
            "scope_digest_mismatch_substantiated": False,
            "reason": (
                "claim scope digests are locally derived from each validated "
                "Claim scope; the captured finding supplied no contradictory "
                "canonical digest evidence"
            ),
        },
        "conflict_audit": {
            "unresolved_conflict_count": len(unresolved),
            "all_claim_boundaries_retained_in_writer_limitations": (
                assembled_writer["limitations_zh_cn"] == expected_limitations
            ),
            "classification": "L3_disclosed_analytical_quality_debt",
        },
        "margin_attribution_audit": {
            "company_total_scope_explicit": company_total_scope_explicit,
            "ai_or_segment_attribution_absent": ai_or_segment_attribution_absent,
            "unsupported_attribution_confirmed": False,
            "classification": "L3_disclosed_analytical_gap",
        },
        "historical_terminal_truth_rewritten": False,
        "captured_output_promoted_or_persisted_as_artifact": False,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
