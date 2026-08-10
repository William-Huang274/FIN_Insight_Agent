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
from sec_agent.s2_fixed_pack_capture_reuse_successor import (  # noqa: E402
    SUCCESSOR_NODE_ORDER,
    compile_successor_case_input,
    load_predecessor_import_bundle,
    load_successor_contract,
)
from sec_agent.s2_fixed_pack_capture_reuse_successor_runtime import (  # noqa: E402
    execute_successor_case,
    issue_successor_admission,
)
from sec_agent.s2_fixed_pack_research import (  # noqa: E402
    compile_six_case_model_inputs,
    load_fixed_pack_contract,
    load_fixed_pack_profile,
    load_frozen_local_packs,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
)


PROOF_SCHEMA = (
    "fin_ia_0_1_3_s2_dell_capture_reuse_successor_clean_independent_proof_v1_0"
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
RUNTIME_PATH = ROOT / "src/sec_agent/s2_fixed_pack_capture_reuse_successor_runtime.py"
RUNNER_PATH = Path(__file__).resolve()
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_dell_capture_reuse_successor_clean_independent_proof_v1_0.json"
)
OBSERVED_AT = "2026-08-10T09:00:00Z"
EXPIRES_AT = "2026-08-10T13:00:00Z"


def _fixture_report() -> dict[str, Any]:
    return {
        "sections": [
            {
                "section_id": "executive_thesis",
                "points": [
                    {
                        "text": (
                            "AI服务器收入为161.32亿美元，占ISG收入55.6%，"
                            "但仍有证据缺口。"
                        ),
                        "epistemic_status": "bounded_inference",
                        "evidence_aliases": ["E002"],
                        "gap_aliases": ["G001"],
                        "numeric_refs": [
                            "PRES:DELL:FY2027_Q1:AI_SERVER_REVENUE:ZH_YI_USD",
                            "FORM:DELL:FY2027_Q1:AI_SERVER_REVENUE_SHARE_OF_ISG",
                        ],
                    }
                ],
            }
        ],
        "overall_confidence": "medium",
        "limitations": ["仍需独立需求和客户集中度证据。"],
    }


def _fixture_content(node_key: str) -> dict[str, Any]:
    if node_key.startswith("specialist::"):
        return {
            "family": node_key.split("::", 1)[1],
            "findings": [
                {
                    "text": "冻结证据支持有边界的公司判断。",
                    "epistemic_status": "bounded_inference",
                    "evidence_aliases": ["E002"],
                    "gap_aliases": ["G001"],
                    "numeric_refs": [],
                    "counterevidence": "缺口仍可能改变判断。",
                    "confidence": "medium",
                }
            ],
            "unresolved": ["需要补源。"],
        }
    if node_key == "cross_unit_synthesis":
        return {
            "cross_mechanism_findings": [
                {
                    "text": "需求与利润传导只能形成有限结论。",
                    "epistemic_status": "bounded_inference",
                    "evidence_aliases": ["E002"],
                    "gap_aliases": ["G001"],
                    "numeric_refs": [],
                }
            ],
            "thesis": "有限支持",
            "antithesis": "利润归属和客户集中仍未闭合",
            "unresolved_conflicts": [],
        }
    if node_key in {"draft_writer", "final_writer"}:
        return _fixture_report()
    if node_key == "red_team_critic":
        return {
            "issues": [],
            "missing_counter_thesis": [],
            "rewrite_instructions": ["保留缺口。"],
        }
    if node_key == "verifier":
        return {
            "claim_checks": [
                {
                    "text": "有限判断",
                    "status": "bounded",
                    "evidence_aliases": ["E002"],
                    "numeric_refs": [],
                    "reason": "事实与公式引用受控。",
                }
            ],
            "identity_period_unit_findings": [],
            "unknown_aliases": [],
            "verdict": "pass_with_findings",
        }
    raise RuntimeError("unknown_successor_fixture_node:" + node_key)


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
    raise RuntimeError("fixed_pack_capture_reuse_clean_proof_socket_forbidden")


def _load_material() -> dict[str, Any]:
    base_contract = load_fixed_pack_contract(BASE_CONTRACT_PATH, repo_root=ROOT)
    profile = load_fixed_pack_profile(PROFILE_PATH)
    packs = load_frozen_local_packs(contract=base_contract, repo_root=ROOT)
    inputs, _compilation = compile_six_case_model_inputs(
        contract=base_contract,
        profile=profile,
        packs=packs,
    )
    base_case_input = next(row for row in inputs if row["case_key"] == "DELL")
    successor_contract = load_successor_contract(
        SUCCESSOR_CONTRACT_PATH, repo_root=ROOT
    )
    successor_case_input = compile_successor_case_input(
        base_case_input=base_case_input,
        contract=successor_contract,
        profile=profile,
    )
    predecessor_bundle = load_predecessor_import_bundle(
        contract=successor_contract,
        repo_root=ROOT,
    )
    return {
        "profile": profile,
        "base_case_input": base_case_input,
        "successor_case_input": successor_case_input,
        "predecessor_bundle": predecessor_bundle,
    }


def run_worker(*, execution_git_commit: str) -> dict[str, Any]:
    original_socket = socket.socket
    socket.socket = _block_socket  # type: ignore[assignment]
    try:
        material = _load_material()
        profile = material["profile"]
        successor_input = material["successor_case_input"]
        predecessor = material["predecessor_bundle"]
        runtime_sha = file_sha256(RUNTIME_PATH)
        runner_sha = file_sha256(RUNNER_PATH)
        successor_contract_sha = file_sha256(SUCCESSOR_CONTRACT_PATH)
        base_contract_sha = file_sha256(BASE_CONTRACT_PATH)
        profile_sha = file_sha256(PROFILE_PATH)
        admission = issue_successor_admission(
            case_input=successor_input,
            predecessor_bundle=predecessor,
            profile=profile,
            execution_git_commit=execution_git_commit,
            runtime_sha256=runtime_sha,
            runner_sha256=runner_sha,
            successor_contract_sha256=successor_contract_sha,
            base_contract_sha256=base_contract_sha,
            profile_sha256=profile_sha,
            issued_at=OBSERVED_AT,
            expires_at=EXPIRES_AT,
            run_nonce="clean-fixture-dell-capture-reuse-successor",
            credential_present=False,
            execution_mode="fixture",
        )
        with tempfile.TemporaryDirectory(
            prefix="fin013_s2_dell_capture_reuse_proof_"
        ) as temp:
            temp_root = Path(temp)
            attempt_root = temp_root / "attempt"
            terminal = execute_successor_case(
                admission=admission,
                case_input=successor_input,
                predecessor_bundle=predecessor,
                profile=profile,
                execution_git_commit=execution_git_commit,
                runtime_sha256=runtime_sha,
                runner_sha256=runner_sha,
                successor_contract_sha256=successor_contract_sha,
                base_contract_sha256=base_contract_sha,
                profile_sha256=profile_sha,
                runtime_root=attempt_root,
                shared_ledger=SharedAdmissionConsumptionLedger(
                    temp_root / "ledger.sqlite"
                ),
                provider_call=fixture_provider,
                observed_at=OBSERVED_AT,
            )
            request_count = len(
                list(attempt_root.glob("raw_model_only/calls/*/request.json"))
            )
            capture_count = len(
                list(attempt_root.glob("raw_model_only/calls/*/capture.json"))
            )
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
    body = {
        "execution_git_commit": execution_git_commit,
        "runtime_sha256": runtime_sha,
        "runner_sha256": runner_sha,
        "successor_contract_sha256": successor_contract_sha,
        "base_contract_sha256": base_contract_sha,
        "profile_sha256": profile_sha,
        "base_case_input_digest": successor_input["base_model_visible_digest"],
        "successor_case_input_digest": successor_input["model_visible_digest"],
        "numeric_authority_digest": successor_input["numeric_authority"][
            "numeric_authority_digest"
        ],
        "predecessor_terminal_digest": predecessor[
            "predecessor_terminal_digest"
        ],
        "predecessor_import_bundle_digest": predecessor["import_bundle_digest"],
        "predecessor_imported_nodes": [
            {
                "node_key": row["node_key"],
                "output_digest": row["output_digest"],
                "capture_digest": row["capture_digest"],
                "capture_file_sha256": row["capture_file_sha256"],
            }
            for row in predecessor["imported_outputs"]
        ],
        "failed_predecessor_node": deepcopy(
            dict(predecessor["failed_attempt_evidence"])
        ),
        "terminal": {
            "status": terminal["status"],
            "terminal_code": terminal["terminal_code"],
            "terminal_digest": terminal["terminal_digest"],
            "observed_counts": deepcopy(dict(terminal["observed_counts"])),
            "logical_node_indices": [
                row["logical_node_index"]
                for row in terminal["successor_call_receipts"]
            ],
            "same_evidence_pack_proven": terminal["same_evidence_pack_proven"],
            "same_input_pair_proven": terminal["same_input_pair_proven"],
            "business_artifact_promoted": terminal[
                "business_artifact_promoted"
            ],
        },
        "request_captures": request_count,
        "response_captures": capture_count,
        "real_provider_calls": 0,
        "model_calls": 0,
        "network_calls": 0,
    }
    return {**body, "worker_digest": canonical_digest(body)}


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
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
            str(RUNNER_PATH),
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
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError(
            "fixed_pack_capture_reuse_clean_proof_requires_clean_worktree"
        )
    execution_git_commit = _git("rev-parse", "HEAD")
    ahead_behind = _git("rev-list", "--left-right", "--count", "HEAD...@{u}")
    if ahead_behind.split() != ["0", "0"]:
        raise RuntimeError(
            "fixed_pack_capture_reuse_clean_proof_requires_synced_branch"
        )
    with tempfile.TemporaryDirectory(
        prefix="fin013_s2_dell_capture_reuse_fresh_"
    ) as temp:
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
        raise RuntimeError(
            "fixed_pack_capture_reuse_clean_proof_fresh_worker_mismatch"
        )
    terminal = worker_a["terminal"]
    if not (
        terminal["status"] == "completed"
        and terminal["observed_counts"]["imported_usable_nodes"] == 5
        and terminal["observed_counts"]["successor_provider_calls"] == 8
        and terminal["observed_counts"]["combined_provider_attempts"] == 14
        and terminal["observed_counts"]["logical_outputs_present"] == 13
        and terminal["logical_node_indices"] == list(range(6, 14))
        and worker_a["request_captures"] == 8
        and worker_a["response_captures"] == 8
        and worker_a["failed_predecessor_node"]["promoted_as_usable_output"]
        is False
    ):
        raise RuntimeError(
            "fixed_pack_capture_reuse_clean_proof_terminal_invalid"
        )
    body = {
        "schema_version": PROOF_SCHEMA,
        "product_version": "FIN_0_1_3",
        "owner_stage": "S2",
        "status": (
            "clean_independent_dell_capture_reuse_successor_zero_call_proof_passed"
        ),
        "execution_git_commit": execution_git_commit,
        "fresh_worker_count": 2,
        "credential_environment_scrubbed": True,
        "socket_blocked_in_workers": True,
        "workers_byte_equivalent": True,
        "worker_digest": worker_a["worker_digest"],
        "runtime_sha256": worker_a["runtime_sha256"],
        "runner_sha256": worker_a["runner_sha256"],
        "successor_contract_sha256": worker_a["successor_contract_sha256"],
        "base_contract_sha256": worker_a["base_contract_sha256"],
        "profile_sha256": worker_a["profile_sha256"],
        "base_case_input_digest": worker_a["base_case_input_digest"],
        "successor_case_input_digest": worker_a["successor_case_input_digest"],
        "numeric_authority_digest": worker_a["numeric_authority_digest"],
        "predecessor_terminal_digest": worker_a["predecessor_terminal_digest"],
        "predecessor_import_bundle_digest": worker_a[
            "predecessor_import_bundle_digest"
        ],
        "predecessor_imported_nodes": deepcopy(
            worker_a["predecessor_imported_nodes"]
        ),
        "failed_predecessor_node": deepcopy(worker_a["failed_predecessor_node"]),
        "terminal": deepcopy(terminal),
        "observed_counts_across_workers": {
            "predecessor_imports_read_only": 10,
            "fixture_provider_calls": 16,
            "request_captures": 16,
            "response_captures": 16,
            "real_provider_calls": 0,
            "model_calls": 0,
            "network_calls": 0,
            "retries": 0,
            "fallbacks": 0,
        },
        "acceptance": {
            "five_usable_predecessor_outputs_digest_bound": True,
            "failed_predecessor_capture_not_promoted": True,
            "only_eight_successor_nodes_executed": True,
            "logical_thirteen_node_chain_materialized": True,
            "numeric_display_aliases_and_formula_traces_bound": True,
            "cumulative_predecessor_and_successor_budget_accounted": True,
            "business_promotion_forbidden": True,
        },
        "known_boundary": (
            "This proves deterministic capture reuse, numeric authority, exact-once "
            "successor wiring and eight-node fixture completion. It makes no claim "
            "about DeepSeek output quality. The imported direct baseline did not see "
            "the successor numeric authority, so strict same-input paired acceptance "
            "remains pending a separate baseline call after this bounded live."
        ),
        "current_next": (
            "ONE_DELL_EIGHT_NODE_CAPTURE_REUSE_SUCCESSOR_AUTHORITY_DECISION"
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
