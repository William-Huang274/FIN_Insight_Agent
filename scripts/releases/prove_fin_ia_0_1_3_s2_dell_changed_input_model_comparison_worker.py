from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_six_case_local_evidence_pack import (  # noqa: E402
    canonical_digest,
    file_sha256,
)
from sec_agent.s2_dell_changed_input_model_comparison import (  # noqa: E402
    compile_changed_input_case,
    load_changed_input_comparison_contract,
)
from sec_agent.s2_fixed_pack_research_runtime import (  # noqa: E402
    COMPACT_VERIFIER_OUTPUT_SCHEMA,
    NODE_ORDER,
    execute_case,
    issue_case_admission,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


CONTRACT_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s2_dell_changed_input_model_comparison_contract_v1_0.json"
)
RUNTIME_PATH = ROOT / "src/sec_agent/s2_fixed_pack_research_runtime.py"
OBSERVED_AT = "2026-08-10T22:00:00Z"
EXPIRES_AT = "2026-08-11T02:00:00Z"


def _fixture_report() -> dict[str, Any]:
    return {
        "sections": [
            {
                "section_id": "executive_thesis",
                "points": [
                    {
                        "text": "冻结证据支持有边界的研究判断。",
                        "epistemic_status": "bounded_inference",
                        "evidence_aliases": ["E001"],
                        "gap_aliases": ["G001"],
                        "numeric_refs": [],
                    }
                ],
            }
        ],
        "overall_confidence": "medium",
        "limitations": ["仍有已声明的证据缺口。"],
    }


def _fixture_content(node_key: str, case_key: str) -> dict[str, Any]:
    if node_key in {"direct_baseline", "draft_writer", "final_writer"}:
        return _fixture_report()
    if node_key == "research_lead":
        return {
            "thesis_hypotheses": ["检验证据是否支持持续性。"],
            "research_units": [
                {
                    "family": node.split("::", 1)[1],
                    "question": "该研究家族的事实、机制和反证是什么？",
                    "evidence_aliases": ["E001"],
                    "gap_aliases": ["G001"],
                    "counter_thesis": "缺口可能改变判断。",
                }
                for node in NODE_ORDER
                if node.startswith("specialist::")
            ],
        }
    if node_key.startswith("specialist::"):
        return {
            "family": node_key.split("::", 1)[1],
            "findings": [
                {
                    "text": "该研究家族形成有限证据支持。",
                    "epistemic_status": "bounded_inference",
                    "evidence_aliases": ["E001"],
                    "gap_aliases": ["G001"],
                    "numeric_refs": [],
                    "counterevidence": "证据缺口仍然存在。",
                    "confidence": "medium",
                }
            ],
            "unresolved": ["需要补源。"],
        }
    if node_key == "cross_unit_synthesis":
        return {
            "cross_mechanism_findings": [
                {
                    "text": "需求与财务传导只能形成有边界的综合判断。",
                    "epistemic_status": "bounded_inference",
                    "evidence_aliases": ["E001"],
                    "gap_aliases": ["G001"],
                    "numeric_refs": [],
                }
            ],
            "thesis": "有限支持",
            "antithesis": "关键缺口可能改变判断",
            "unresolved_conflicts": [],
        }
    if node_key == "red_team_critic":
        return {
            "issues": [],
            "missing_counter_thesis": [],
            "rewrite_instructions": ["保留缺口边界。"],
        }
    if node_key == "verifier":
        return {
            "schema_version": COMPACT_VERIFIER_OUTPUT_SCHEMA,
            "claim_checks": [
                {
                    "claim_id": f"CLM:{case_key}:001",
                    "status": "bounded",
                    "finding_codes": [],
                    "reason": "引用有效且保留缺口。",
                }
            ],
            "global_finding_codes": [],
            "verdict": "pass_with_findings",
        }
    raise RuntimeError("changed_input_fixture_node_unknown:" + node_key)


def _fixture_provider(request: Mapping[str, Any]) -> dict[str, Any]:
    node_key = str(request.get("node_key") or "")
    case_key = str(request.get("case_key") or "")
    return {
        "status": "ok",
        "content": json.dumps(
            _fixture_content(node_key, case_key), ensure_ascii=False
        ),
        "finish_reason": "stop",
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
        "raw_response": {"fixture": True, "node_key": node_key},
    }


def _network_forbidden(*_args: Any, **_kwargs: Any) -> None:
    raise RuntimeError("changed_input_clean_proof_network_forbidden")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--implementation-commit", required=True)
    args = parser.parse_args()

    original_socket = socket.socket
    original_create_connection = socket.create_connection
    original_getaddrinfo = socket.getaddrinfo
    socket.socket = _network_forbidden  # type: ignore[assignment]
    socket.create_connection = _network_forbidden  # type: ignore[assignment]
    socket.getaddrinfo = _network_forbidden  # type: ignore[assignment]
    try:
        contract = load_changed_input_comparison_contract(
            CONTRACT_PATH, repo_root=ROOT
        )
        material = compile_changed_input_case(contract=contract, repo_root=ROOT)
        case_input = material["case_input"]
        profile = material["profile"]
        profile_path = ROOT / contract["immutable_bindings"]["provider_profile"][
            "ref"
        ]
        admission = issue_case_admission(
            case_input=case_input,
            profile=profile,
            execution_git_commit=args.implementation_commit,
            runner_sha256=file_sha256(RUNTIME_PATH),
            contract_sha256=file_sha256(CONTRACT_PATH),
            profile_sha256=file_sha256(profile_path),
            issued_at=OBSERVED_AT,
            expires_at=EXPIRES_AT,
            run_nonce="clean-changed-input-dell-v1",
            credential_present=False,
            execution_mode="fixture",
        )
        terminal = execute_case(
            admission=admission,
            case_input=case_input,
            profile=profile,
            execution_git_commit=args.implementation_commit,
            runner_sha256=file_sha256(RUNTIME_PATH),
            contract_sha256=file_sha256(CONTRACT_PATH),
            profile_sha256=file_sha256(profile_path),
            runtime_root=args.runtime_root / "attempt",
            shared_ledger=SharedAdmissionConsumptionLedger(
                args.runtime_root / "shared" / "admission.sqlite"
            ),
            provider_call=_fixture_provider,
            observed_at=OBSERVED_AT,
        )
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
        socket.create_connection = original_create_connection  # type: ignore[assignment]
        socket.getaddrinfo = original_getaddrinfo  # type: ignore[assignment]

    request_paths = sorted(
        (args.runtime_root / "attempt").glob("raw_model_only/calls/*/request.json")
    )
    capture_paths = sorted(
        (args.runtime_root / "attempt").glob("raw_model_only/calls/*/capture.json")
    )
    request_envelopes = [
        json.loads(path.read_text(encoding="utf-8")) for path in request_paths
    ]
    requests = [dict(row["request"]) for row in request_envelopes]
    request_chars = {
        str(row["node_key"]): len(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        )
        for row in requests
    }
    serialized_requests = json.dumps(requests, ensure_ascii=False)
    supplement_tokens = (
        "SUPPLEMENT::DELL::ISSUER::Q1FY27::DEMAND_BACKLOG_SUPPLY",
        "SUPPLEMENT::DELL::SUPPLIER::MU::SUPPLY_TIGHT_BEYOND_2027",
    )
    non_verifier_requests = [
        row for row in requests if row.get("node_key") != "verifier"
    ]
    mutations = {
        "all_thirteen_nodes_use_corrected_input_digest": (
            len(requests) == len(NODE_ORDER)
            and all(
                row.get("case_input_digest") == case_input["model_visible_digest"]
                for row in requests
            )
        ),
        "historical_model_input_digest_absent": (
            material["historical_case_input_digest"] not in serialized_requests
        ),
        "information_increment_visible_before_verifier": all(
            all(token in json.dumps(row, ensure_ascii=False) for token in supplement_tokens)
            for row in non_verifier_requests
        ),
        "all_request_sizes_within_profile_capacity": (
            bool(request_chars)
            and max(request_chars.values())
            <= int(profile["maximum_input_characters_per_call"])
        ),
        "numeric_authority_rebound_to_current_aliases": (
            len(case_input["numeric_authority"]["source_numeric_facts"]) == 15
            and all(
                dict(row.get("stable_binding") or {})
                for row in case_input["numeric_authority"]["source_numeric_facts"][:-1]
            )
        ),
        "terminal_preserves_no_promotion_boundary": (
            terminal["business_artifact_promoted"] is False
            and terminal["same_input_pair_proven"] is True
        ),
    }
    if not all(mutations.values()):
        raise RuntimeError("changed_input_clean_worker_mutation_failed")
    body = {
        "status": "pass",
        "case_input_digest": case_input["model_visible_digest"],
        "historical_case_input_digest": material["historical_case_input_digest"],
        "source_pack_digest": case_input["source_pack_digest"],
        "numeric_authority_digest": case_input["numeric_authority"][
            "numeric_authority_digest"
        ],
        "terminal_digest": terminal["terminal_digest"],
        "terminal_status": terminal["status"],
        "terminal_code": terminal["terminal_code"],
        "request_characters": request_chars,
        "maximum_request_characters": max(request_chars.values()),
        "observed_counts": {
            "fixture_provider_calls": terminal["observed_counts"]["provider_calls"],
            "request_captures": len(request_paths),
            "response_captures": len(capture_paths),
            "real_provider_calls": 0,
            "model_calls": 0,
            "network_calls": 0,
            "retries": 0,
            "fallbacks": 0,
        },
        "mutations": mutations,
    }
    output = {**body, "worker_digest": canonical_digest(body)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
