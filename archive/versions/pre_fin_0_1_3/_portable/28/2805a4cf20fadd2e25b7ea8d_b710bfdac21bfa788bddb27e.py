from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    StrictTruthKernelPolicy,
)


DECISION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_"
    "fresh_engineering_proof_and_provider_capability_binding_decision_v1_0.json"
)
IMPLEMENTATION_TEST = ROOT / (
    "tests/contract/"
    "test_fin_0_1_s4_t06_entry_shared_runtime_blocker_"
    "minimum_zero_call_implementation.py"
)


def _load_implementation_test_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "s4_t06_minimum_implementation_test",
        IMPLEMENTATION_TEST,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_keyword(value: Any, keyword: str, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            nested_path = f"{path}.{key}"
            if key == keyword:
                found.append(nested_path)
            found.extend(_find_keyword(nested, keyword, nested_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found.extend(
                _find_keyword(nested, keyword, f"{path}[{index}]")
            )
    return found


def test_fresh_proof_decision_preserves_frozen_code_bindings() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    assert decision["decision_label"] == "block_before_canary"
    assert decision["fresh_engineering_proof"]["frozen_code_bindings_match"]
    assert len(
        decision["fresh_engineering_proof"]["exact_code_bindings"]
    ) == 5
    assert _sha256(
        ROOT / decision["source_implementation"]["ref"]
    ) == decision["source_implementation"]["sha256"]


def test_all_three_case_schema_digests_record_the_documented_subset_gap() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    expected = decision["fresh_engineering_proof"][
        "case_schema_recomputation"
    ]
    expected_path = decision["fresh_engineering_proof"][
        "schema_common_blocker"
    ]["path"]

    assert set(expected) == {"DELL", "MU", "NVDA"}
    assert expected_path.endswith(
        ".counterevidence_aliases.uniqueItems"
    )
    assert all(
        len(expected[case]["projection_digest"]) == 64
        and len(expected[case]["schema_sha256"]) == 64
        for case in expected
    )


def test_provider_candidate_is_not_promoted_to_live_binding_or_canary() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    binding = decision["prospective_exact_provider_binding"]
    assert binding["provider"] == "openai"
    assert binding["model"] == "gpt-5.6-sol"
    assert binding["model_level_capability_established_by_official_docs"]
    assert not binding["credential_presence_or_access_established"]
    assert not binding["request_schema_subset_compatibility_established"]
    assert not binding["exact_live_capability_binding_admissible"]
    assert not binding["provider_capability_ref_live_bound"]
    assert decision["program_disposition"]["single_node_canary"] == (
        "not_authorized_and_not_admissible"
    )
    assert decision["observed_counts"]["actual_model_calls"] == 0
    assert decision["observed_counts"]["actual_provider_calls"] == 0
    assert decision["observed_counts"]["credential_reads_or_probes"] == 0
    assert decision["next_action"] == (
        "S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-POST-PROOF-"
        "PROGRAM-SCOPE-REPLACE-OR-STOP-DECISION"
    )
