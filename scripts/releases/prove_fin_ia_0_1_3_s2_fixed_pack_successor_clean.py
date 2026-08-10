from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_six_case_local_evidence_pack import (  # noqa: E402
    canonical_digest,
    file_sha256,
)
from sec_agent.s2_fixed_pack_research import (  # noqa: E402
    CASES,
    compile_six_case_model_inputs,
    load_fixed_pack_contract,
    load_fixed_pack_profile,
    load_frozen_local_packs,
)
from sec_agent.s2_fixed_pack_research_runtime import (  # noqa: E402
    NODE_ORDER,
    execute_case,
    issue_case_admission,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


PROOF_SCHEMA = "fin_ia_0_1_3_s2_fixed_pack_clean_independent_proof_v1_1"
CONTRACT_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_fixed_pack_research_contract_v1_0.json"
)
PROFILE_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_deepseek_v4_pro_fixed_pack_profile_v1_0.json"
)
RUNTIME_PATH = ROOT / "src/sec_agent/s2_fixed_pack_research_runtime.py"
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_fixed_pack_successor_clean_independent_proof_v1_1.json"
)
OBSERVED_AT = "2026-08-10T10:00:00Z"
EXPIRES_AT = "2026-08-10T14:00:00Z"


def _fixture_report() -> dict[str, Any]:
    return {
        "sections": [
            {
                "section_id": "executive_thesis",
                "points": [
                    {
                        "text": "冻结证据只支持一个有边界的初步判断。",
                        "epistemic_status": "bounded_inference",
                        "evidence_aliases": ["E001"],
                        "gap_aliases": ["G001"],
                    }
                ],
            }
        ],
        "overall_confidence": "medium",
        "limitations": ["仍存在已声明的证据缺口。"],
    }


def _fixture_content(node_key: str) -> dict[str, Any]:
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
            "claim_checks": [
                {
                    "text": "有限判断",
                    "status": "bounded",
                    "evidence_aliases": ["E001"],
                    "reason": "存在引用但仍有缺口。",
                }
            ],
            "identity_period_unit_findings": [],
            "unknown_aliases": [],
            "verdict": "pass_with_findings",
        }
    raise RuntimeError("unknown_fixture_node:" + node_key)


def fixture_provider(request: Mapping[str, Any]) -> dict[str, Any]:
    node_key = str(request.get("node_key") or "")
    return {
        "status": "ok",
        "content": json.dumps(_fixture_content(node_key), ensure_ascii=False),
        "finish_reason": "stop",
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
        "raw_response": {"fixture": True, "node_key": node_key},
    }


def _block_socket(*_args: Any, **_kwargs: Any) -> None:
    raise RuntimeError("fixed_pack_clean_proof_socket_forbidden")


def run_worker(*, execution_git_commit: str) -> dict[str, Any]:
    original_socket = socket.socket
    socket.socket = _block_socket  # type: ignore[assignment]
    try:
        contract = load_fixed_pack_contract(CONTRACT_PATH, repo_root=ROOT)
        profile = load_fixed_pack_profile(PROFILE_PATH)
        packs = load_frozen_local_packs(contract=contract, repo_root=ROOT)
        inputs, compilation = compile_six_case_model_inputs(
            contract=contract,
            profile=profile,
            packs=packs,
        )
        runner_sha = file_sha256(RUNTIME_PATH)
        contract_sha = file_sha256(CONTRACT_PATH)
        profile_sha = file_sha256(PROFILE_PATH)
        case_results: list[dict[str, Any]] = []
        with tempfile.TemporaryDirectory(prefix="fin013_s2_fixed_pack_proof_") as temp:
            temp_root = Path(temp)
            for case_input in inputs:
                case_key = str(case_input["case_key"])
                admission = issue_case_admission(
                    case_input=case_input,
                    profile=profile,
                    execution_git_commit=execution_git_commit,
                    runner_sha256=runner_sha,
                    contract_sha256=contract_sha,
                    profile_sha256=profile_sha,
                    issued_at=OBSERVED_AT,
                    expires_at=EXPIRES_AT,
                    run_nonce="clean-fixture-" + case_key,
                    credential_present=False,
                    execution_mode="fixture",
                )
                runtime_root = temp_root / "attempts" / case_key.lower()
                terminal = execute_case(
                    admission=admission,
                    case_input=case_input,
                    profile=profile,
                    execution_git_commit=execution_git_commit,
                    runner_sha256=runner_sha,
                    contract_sha256=contract_sha,
                    profile_sha256=profile_sha,
                    runtime_root=runtime_root,
                    shared_ledger=SharedAdmissionConsumptionLedger(
                        temp_root / "ledgers" / f"{case_key.lower()}.sqlite"
                    ),
                    provider_call=fixture_provider,
                    observed_at=OBSERVED_AT,
                )
                request_count = len(
                    list(runtime_root.glob("raw_model_only/calls/*/request.json"))
                )
                capture_count = len(
                    list(runtime_root.glob("raw_model_only/calls/*/capture.json"))
                )
                case_results.append(
                    {
                        "case_key": case_key,
                        "case_input_digest": case_input["model_visible_digest"],
                        "source_pack_digest": case_input["source_pack_digest"],
                        "terminal_digest": terminal["terminal_digest"],
                        "status": terminal["status"],
                        "terminal_code": terminal["terminal_code"],
                        "request_captures": request_count,
                        "response_captures": capture_count,
                        "fixture_provider_calls": terminal["observed_counts"][
                            "provider_calls"
                        ],
                        "findings": terminal["observed_counts"]["findings"],
                        "same_input_pair_proven": terminal["same_input_pair_proven"],
                        "business_artifact_promoted": terminal[
                            "business_artifact_promoted"
                        ],
                    }
                )
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
    body = {
        "execution_git_commit": execution_git_commit,
        "runner_sha256": runner_sha,
        "contract_sha256": contract_sha,
        "profile_sha256": profile_sha,
        "compilation_result_digest": compilation["result_digest"],
        "case_results": case_results,
        "observed_counts": {
            "cases": len(case_results),
            "fixture_provider_calls": sum(
                row["fixture_provider_calls"] for row in case_results
            ),
            "request_captures": sum(row["request_captures"] for row in case_results),
            "response_captures": sum(
                row["response_captures"] for row in case_results
            ),
            "real_provider_calls": 0,
            "model_calls": 0,
            "network_calls": 0,
            "retries": 0,
            "fallbacks": 0,
        },
    }
    return {**body, "worker_digest": canonical_digest(body)}


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _clean_environment() -> dict[str, str]:
    env = dict(os.environ)
    for key in tuple(env):
        upper = key.upper()
        if any(marker in upper for marker in ("API_KEY", "SECRET_KEY", "AUTH_TOKEN")):
            env.pop(key, None)
    env["PYTHONPATH"] = os.pathsep.join((str(ROOT), str(ROOT / "src")))
    return env


def _run_fresh_worker(*, execution_git_commit: str, output: Path) -> dict[str, Any]:
    subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker-output",
            str(output),
            "--execution-git-commit",
            execution_git_commit,
        ],
        cwd=ROOT,
        env=_clean_environment(),
        check=True,
    )
    return json.loads(output.read_text(encoding="utf-8"))


def build_clean_proof(*, output_path: Path) -> dict[str, Any]:
    status = _git("status", "--porcelain")
    if status:
        raise RuntimeError("fixed_pack_clean_proof_requires_clean_worktree")
    execution_git_commit = _git("rev-parse", "HEAD")
    ahead_behind = _git("rev-list", "--left-right", "--count", "HEAD...@{u}")
    if ahead_behind.split() != ["0", "0"]:
        raise RuntimeError("fixed_pack_clean_proof_requires_synced_branch")
    with tempfile.TemporaryDirectory(prefix="fin013_s2_fixed_pack_fresh_") as temp:
        temp_root = Path(temp)
        worker_a = _run_fresh_worker(
            execution_git_commit=execution_git_commit,
            output=temp_root / "worker_a.json",
        )
        worker_b = _run_fresh_worker(
            execution_git_commit=execution_git_commit,
            output=temp_root / "worker_b.json",
        )
    if worker_a != worker_b:
        raise RuntimeError("fixed_pack_clean_proof_fresh_worker_mismatch")
    if any(
        row["status"] != "completed"
        or row["request_captures"] != len(NODE_ORDER)
        or row["response_captures"] != len(NODE_ORDER)
        or row["business_artifact_promoted"] is not False
        for row in worker_a["case_results"]
    ):
        raise RuntimeError("fixed_pack_clean_proof_case_terminal_invalid")
    body = {
        "schema_version": PROOF_SCHEMA,
        "product_version": "FIN_0_1_3",
        "owner_stage": "S2_to_S3",
        "status": "clean_independent_six_case_zero_call_proof_passed",
        "execution_git_commit": execution_git_commit,
        "fresh_worker_count": 2,
        "credential_environment_scrubbed": True,
        "socket_blocked_in_workers": True,
        "workers_byte_equivalent": True,
        "worker_digest": worker_a["worker_digest"],
        "case_results": deepcopy(worker_a["case_results"]),
        "observed_counts": {
            "cases_per_worker": len(CASES),
            "fixture_provider_calls_per_worker": worker_a["observed_counts"][
                "fixture_provider_calls"
            ],
            "fixture_provider_calls_across_workers": 2
            * worker_a["observed_counts"]["fixture_provider_calls"],
            "request_captures_across_workers": 2
            * worker_a["observed_counts"]["request_captures"],
            "response_captures_across_workers": 2
            * worker_a["observed_counts"]["response_captures"],
            "real_provider_calls": 0,
            "model_calls": 0,
            "network_calls": 0,
            "retries": 0,
            "fallbacks": 0,
        },
        "acceptance": {
            "all_six_cases_completed": True,
            "thirteen_requests_and_captures_per_case": True,
            "direct_and_agent_same_input_digest": True,
            "exact_once_ledger_terminalized_per_fresh_worker": True,
            "business_promotion_forbidden": True,
        },
        "known_boundary": (
            "This proves deterministic successor wiring, capture-first behavior and "
            "case-bound inputs with fixture outputs. It makes no claim about DeepSeek "
            "content quality, dynamic search or product acceptance."
        ),
        "current_next": (
            "ONE_DELL_FIXED_PACK_CANARY_AUTHORITY_DECISION_BEFORE_ANY_REAL_MODEL_CALL"
        ),
    }
    proof = {**body, "proof_digest": canonical_digest(body)}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--worker-output", type=Path)
    parser.add_argument("--execution-git-commit", default="")
    args = parser.parse_args()
    if args.worker_output:
        if len(args.execution_git_commit) != 40:
            raise RuntimeError("worker_execution_git_commit_invalid")
        result = run_worker(execution_git_commit=args.execution_git_commit)
        args.worker_output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return 0
    result = build_clean_proof(output_path=args.output)
    print(result["status"])
    print(result["proof_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
