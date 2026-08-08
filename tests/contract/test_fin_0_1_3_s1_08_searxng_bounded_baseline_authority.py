from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest


AUTHORITY = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_searxng_bounded_diagnostic_baseline_authority_v1_0.json"
POLICY = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_searxng_diagnostic_provider_policy_v1_0.json"
PROOF = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_searxng_diagnostic_adapter_zero_call_proof_v1_1.json"
RUNNER = ROOT / "scripts/releases/run_fin_ia_0_1_3_s1_08_searxng_bounded_diagnostic_baseline.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _runner_module():
    spec = importlib.util.spec_from_file_location("searxng_bounded_baseline_runner", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_authority_is_digest_bound_to_passed_adapter_policy_and_runner() -> None:
    module = _runner_module()
    authority = module.load_authority(AUTHORITY)
    proof = json.loads(PROOF.read_text(encoding="utf-8"))
    policy = json.loads(POLICY.read_text(encoding="utf-8"))

    assert authority["adapter_proof_digest"] == proof["proof_digest"]
    assert authority["adapter_proof_file_sha256"] == _sha256(PROOF)
    assert authority["policy_digest"] == canonical_digest(policy)
    assert authority["policy_file_sha256"] == _sha256(POLICY)
    assert authority["runner_sha256"] == _sha256(RUNNER)
    assert proof["acceptance"]["adapter_zero_call_engineering_pass"] is True


def test_authority_is_exactly_three_cases_zero_retry_and_non_promotable() -> None:
    authority = _runner_module().load_authority(AUTHORITY)
    assert [row["case_key"] for row in authority["queries"]] == ["DELL", "MU", "NVDA"]
    assert len({row["query_id"] for row in authority["queries"]}) == 3
    contract = authority["execution_contract"]
    assert contract["fin_to_searxng_query_call_ceiling"] == 3
    assert contract["configured_engine_ceiling_per_query"] == 4
    assert contract["retry_ceiling"] == 0
    assert contract["model_call_ceiling"] == 0
    assert contract["public_instance_fallback_allowed"] is False
    assert contract["downstream_document_fetch_allowed"] is False
    assert contract["evidence_promotion_allowed"] is False
    assert contract["writer_consumption_allowed"] is False
    assert contract["production_capability_claim_allowed"] is False
