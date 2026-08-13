from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.data_retrieval.run_s1d_official_pdf_successor import (  # noqa: E402
    OfficialPdfSuccessorRunnerError,
    validate_authority,
)


RUNNER_REF = "scripts/data_retrieval/run_s1d_official_pdf_successor.py"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    repo = tmp_path / "repo"
    refs = {
        "source_intake_result_ref": "configs/source_result.json",
        "attempt_manifest_ref": "data/private/attempt.json",
        "evidence_gate_policy_ref": "configs/gate.json",
        "predecessor_pack_ref": "data/private/pack.json",
        "s2_result_ref": "configs/s2.json",
        "runner_ref": RUNNER_REF,
        "zero_call_proof_ref": "configs/proof.json",
    }
    for ref in refs.values():
        target = repo / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        if ref == RUNNER_REF:
            shutil.copy2(ROOT / ref, target)
        else:
            target.write_text(json.dumps({"fixture": ref}), encoding="utf-8")
    bound: dict[str, object] = {"raw_pdf_sha256": "3e21fe2dc69a4b95ebaf3e2e9a037ff5d704c5729e1eb7eff1554d03bdfea453"}
    for key, ref in refs.items():
        bound[key] = ref
        bound[key.removesuffix("_ref") + "_sha256"] = _digest(repo / ref)
    authority: dict[str, object] = {
        "schema_version": "fin_ia_s1d_official_pdf_successor_execution_authority_v1_0",
        "status": "fresh_zero_network_official_pdf_successor_authorized",
        "clean_implementation": {
            "branch": "codex/test",
            "git_commit": "a" * 40,
            "working_tree_required_clean_before_execution": True,
            "pushed_head_required": True,
        },
        "bound_inputs": bound,
        "source_contract": {
            "route_id": "TSM_Q2_2026_EARNINGS_CALL_TRANSCRIPT",
            "ticker": "TSM",
            "consumer_case_key": "DELL",
            "company": "Taiwan Semiconductor Manufacturing Company Limited",
            "source_type": "EARNINGS_CALL_TRANSCRIPT",
            "source_tier": "official_hosted_management_call_transcript",
            "publication_date": "2026-07-16",
            "period_end": "2026-06-30",
            "fiscal_year": 2026,
            "source_url": "https://investor.tsmc.com/test.pdf",
            "license_scope": "official_hosted_third_party_transcript_private_research_use",
            "redistributable": False,
        },
        "execution_budget": {
            "network_calls": 0,
            "model_calls": 0,
            "retries": 0,
            "current_product_pointer_mutation": "forbidden",
            "raw_source_publication": "forbidden",
        },
        "output_contract": {
            "private_output_root_ref": "data/private/output-r1",
            "public_result_ref": "configs/result.json",
            "result_id": "TEST",
        },
    }
    return repo, authority


def test_authority_binds_all_inputs_and_zero_call_boundary(tmp_path: Path) -> None:
    repo, authority = _fixture(tmp_path)
    validated = validate_authority(authority, repository_root=repo)
    assert validated["execution_budget"]["network_calls"] == 0
    assert validated["execution_budget"]["model_calls"] == 0


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("network", "budget_or_source_invalid"),
        ("pointer", "budget_or_source_invalid"),
        ("digest", "input_digest_mismatch"),
        ("raw", "raw_digest_invalid"),
        ("output", "output_already_exists"),
    ],
)
def test_authority_mutations_fail_closed(
    tmp_path: Path, mutation: str, error: str
) -> None:
    repo, authority = _fixture(tmp_path)
    if mutation == "network":
        authority["execution_budget"]["network_calls"] = 1
    elif mutation == "pointer":
        authority["execution_budget"]["current_product_pointer_mutation"] = "allowed"
    elif mutation == "digest":
        authority["bound_inputs"]["runner_sha256"] = "0" * 64
    elif mutation == "raw":
        authority["bound_inputs"]["raw_pdf_sha256"] = "0" * 64
    else:
        (repo / authority["output_contract"]["public_result_ref"]).write_text(
            "{}", encoding="utf-8"
        )
    with pytest.raises(OfficialPdfSuccessorRunnerError, match=error):
        validate_authority(authority, repository_root=repo)
