from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_six_case_local_evidence_pack import (  # noqa: E402
    canonical_digest,
    file_sha256,
)
from sec_agent.s2_fixed_pack_capture_reuse_successor import (  # noqa: E402
    compile_repaired_successor_case_input,
    compile_successor_case_input,
    load_numeric_verifier_repair_policy,
    load_successor_contract,
)
from sec_agent.s2_fixed_pack_research import (  # noqa: E402
    compile_six_case_model_inputs,
    load_fixed_pack_contract,
    load_fixed_pack_profile,
    load_frozen_local_packs,
)
from sec_agent.s2_fixed_pack_research_runtime import (  # noqa: E402
    COMPACT_VERIFIER_OUTPUT_SCHEMA,
    build_compact_verifier_projection,
    build_node_request,
    evaluate_final_output,
    resolve_final_output_numeric_surfaces,
    validate_compact_verifier_output,
)


BASE_CONTRACT_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_fixed_pack_research_contract_v1_0.json"
)
SUCCESSOR_CONTRACT_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_dell_fixed_pack_capture_reuse_successor_contract_v1_0.json"
)
PROFILE_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_deepseek_v4_pro_fixed_pack_profile_v1_0.json"
)
POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_dell_numeric_presentation_compact_verifier_repair_policy_v1_0.json"
)
PRIVATE_ATTEMPT_ROOT = ROOT / (
    "data/workbench_private/fin_0_1_3_s2_fixed_pack_capture_reuse_successor/"
    "live/attempts/fin013_s2_fixed_pack_dell_successor_f63f66ff0998aa146c7a"
)
PRIVATE_TERMINAL_PATH = PRIVATE_ATTEMPT_ROOT / "terminal_with_receipt.json"
OUTPUT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_numeric_presentation_compact_verifier_"
    "zero_call_replay_proof_v1_0.json"
)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected_object:{path.as_posix()}")
    return value


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temp.replace(path)


def _finding_summary(findings: list[dict[str, Any]]) -> dict[str, Any]:
    levels = Counter(str(row.get("level") or "") for row in findings)
    codes = Counter(str(row.get("code") or "") for row in findings)
    return {
        "total": len(findings),
        "levels": dict(sorted(levels.items())),
        "codes": dict(sorted(codes.items())),
    }


def main() -> int:
    base_contract = load_fixed_pack_contract(BASE_CONTRACT_PATH, repo_root=ROOT)
    profile = load_fixed_pack_profile(PROFILE_PATH)
    packs = load_frozen_local_packs(contract=base_contract, repo_root=ROOT)
    inputs, _compilation = compile_six_case_model_inputs(
        contract=base_contract,
        profile=profile,
        packs=packs,
    )
    base = next(row for row in inputs if row["case_key"] == "DELL")
    successor_contract = load_successor_contract(
        SUCCESSOR_CONTRACT_PATH,
        repo_root=ROOT,
    )
    legacy = compile_successor_case_input(
        base_case_input=base,
        contract=successor_contract,
        profile=profile,
    )
    policy = load_numeric_verifier_repair_policy(POLICY_PATH, repo_root=ROOT)
    repaired = compile_repaired_successor_case_input(
        successor_case_input=legacy,
        repair_policy=policy,
        profile=profile,
    )

    terminal = _read_json(PRIVATE_TERMINAL_PATH)
    if terminal.get("terminal_digest") != (
        "9b9815ac73a060549c084e3f97125f4447cecd622ab1f04fb8b8891eb0aa900c"
    ):
        raise RuntimeError("historical_terminal_digest_drift")
    final_report = deepcopy(dict(terminal.get("raw_outputs", {}).get("final_writer") or {}))
    if not final_report:
        raise RuntimeError("historical_final_writer_missing")
    legacy_findings = evaluate_final_output(
        final_output=final_report,
        case_input=legacy,
    )
    repaired_findings = evaluate_final_output(
        final_output=final_report,
        case_input=repaired,
    )
    repaired_numeric_codes = {
        str(row.get("code") or "")
        for row in repaired_findings
        if str(row.get("code") or "").startswith("final_report_material_numeric")
        or str(row.get("code") or "").startswith("final_report_numeric_surface")
    }
    if repaired_numeric_codes:
        raise RuntimeError(
            "repaired_numeric_surface_findings_remain:"
            + ",".join(sorted(repaired_numeric_codes))
        )

    projection = build_compact_verifier_projection(
        case_input=repaired,
        final_report=final_report,
    )
    verifier_fixture = {
        "schema_version": COMPACT_VERIFIER_OUTPUT_SCHEMA,
        "claim_checks": [
            {
                "claim_id": claim_id,
                "status": "bounded",
                "finding_codes": [],
                "reason": "证据与边界已逐项核对。",
            }
            for claim_id in projection["expected_claim_ids"]
        ],
        "global_finding_codes": [],
        "verdict": "pass_with_findings",
    }
    verifier_fixture_findings = validate_compact_verifier_output(
        verifier_output=verifier_fixture,
        projection=projection,
    )
    if verifier_fixture_findings:
        raise RuntimeError("compact_verifier_fixture_not_shape_complete")
    compact_request = build_node_request(
        node_key="verifier",
        case_input=repaired,
        prior_outputs={"final_writer": final_report},
        profile=profile,
    )
    old_verifier_receipt = next(
        row
        for row in terminal.get("successor_call_receipts") or ()
        if row.get("node_key") == "verifier"
    )
    old_capture_path = PRIVATE_ATTEMPT_ROOT / str(old_verifier_receipt["capture_ref"])
    old_capture = _read_json(old_capture_path)
    old_request = dict(old_capture.get("request") or {})
    numeric_receipts = resolve_final_output_numeric_surfaces(
        final_output=final_report,
        case_input=repaired,
    )
    tsmc_receipts = [
        row
        for row in numeric_receipts
        if row.get("numeric_token") == "77%"
    ]
    if len(tsmc_receipts) != 1 or tsmc_receipts[0].get("status") != "deterministically_bound":
        raise RuntimeError("tsmc_77_surface_not_deterministically_bound")
    if any(row.get("numeric_token") == "7" for row in numeric_receipts):
        raise RuntimeError("fiscal_year_token_false_positive_remains")

    body = {
        "schema_version": (
            "fin_ia_0_1_3_s2_numeric_presentation_compact_verifier_"
            "zero_call_replay_proof_v1_0"
        ),
        "status": "zero_call_replay_passed",
        "owner_stage": "S2",
        "recorded_at": "2026-08-10",
        "inputs": {
            "base_contract": {
                "ref": BASE_CONTRACT_PATH.relative_to(ROOT).as_posix(),
                "sha256": file_sha256(BASE_CONTRACT_PATH),
            },
            "successor_contract": {
                "ref": SUCCESSOR_CONTRACT_PATH.relative_to(ROOT).as_posix(),
                "sha256": file_sha256(SUCCESSOR_CONTRACT_PATH),
            },
            "repair_policy": {
                "ref": POLICY_PATH.relative_to(ROOT).as_posix(),
                "sha256": file_sha256(POLICY_PATH),
            },
            "historical_private_terminal": {
                "ref": PRIVATE_TERMINAL_PATH.relative_to(ROOT).as_posix(),
                "sha256": file_sha256(PRIVATE_TERMINAL_PATH),
                "terminal_digest": terminal["terminal_digest"],
            },
        },
        "numeric_replay": {
            "legacy": _finding_summary(legacy_findings),
            "repaired": _finding_summary(repaired_findings),
            "legacy_numeric_fact_count": len(
                legacy["numeric_authority"]["source_numeric_facts"]
            ),
            "repaired_numeric_fact_count": len(
                repaired["numeric_authority"]["source_numeric_facts"]
            ),
            "material_surface_receipt_count": len(numeric_receipts),
            "deterministically_bound_surface_count": sum(
                row.get("status") == "deterministically_bound"
                for row in numeric_receipts
            ),
            "tsmc_77_binding": tsmc_receipts[0],
            "fiscal_year_7_false_positive_count": 0,
        },
        "compact_verifier": {
            "claim_count": len(projection["expected_claim_ids"]),
            "selected_evidence_count": len(projection["selected_evidence"]),
            "selected_source_material_count": len(
                projection["selected_source_materials"]
            ),
            "selected_gap_count": len(projection["selected_gaps"]),
            "selected_numeric_fact_count": len(
                projection["selected_numeric_authority"]["source_numeric_facts"]
            ),
            "selected_formula_count": len(
                projection["selected_numeric_authority"]["formula_traces"]
            ),
            "selection_diagnostics": projection["selection_diagnostics"],
            "old_request_characters": len(
                json.dumps(old_request, ensure_ascii=False, separators=(",", ":"))
            ),
            "compact_request_characters": len(
                json.dumps(
                    compact_request,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            ),
            "shape_complete_fixture_characters": len(
                json.dumps(
                    verifier_fixture,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            ),
            "shape_complete_fixture_findings": 0,
            "historical_finish_reason": old_verifier_receipt["finish_reason"],
            "historical_terminal_classification": (
                "verification_incomplete_finish_reason_length"
            ),
        },
        "observed_counts": {
            "provider_calls": 0,
            "model_calls": 0,
            "network_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "business_promotions": 0,
        },
        "stage_boundaries": {
            "source_coverage_remains_S1": True,
            "numeric_and_verifier_structure_repaired_in_S2": True,
            "causal_wwc_and_density_remain_S3": True,
            "new_exact_live_authorized": False,
        },
    }
    result = {**body, "proof_digest": canonical_digest(body)}
    _atomic_json(OUTPUT_PATH, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
