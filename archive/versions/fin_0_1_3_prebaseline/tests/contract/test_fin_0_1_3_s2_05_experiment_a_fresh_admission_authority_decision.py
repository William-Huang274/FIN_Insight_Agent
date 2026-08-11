from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess

import pytest

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / "configs/releases" / (
    "fin_ia_0_1_3_s2_05_experiment_a_"
    "fresh_admission_authority_decision_v1_0.json"
)
_DIGEST = re.compile(r"[0-9a-f]{64}")
_GIT_ID = re.compile(r"[0-9a-f]{40}")


def _load() -> dict:
    return json.loads(DECISION.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate(decision: dict) -> None:
    body = {
        key: deepcopy(value)
        for key, value in decision.items()
        if key != "decision_digest"
    }
    if decision.get("decision_digest") != canonical_digest(body):
        raise ValueError("experiment_a_fresh_authority_digest_invalid")
    repository = decision.get("audited_repository_state") or {}
    if (
        not _GIT_ID.fullmatch(str(repository.get("head") or ""))
        or repository.get("ahead") != 0
        or repository.get("behind") != 0
        or repository.get("tracked_worktree_clean") is not True
        or repository.get("untracked_worktree_clean") is not True
    ):
        raise ValueError("experiment_a_fresh_authority_repository_state_invalid")
    authority = decision.get("authority") or {}
    if (
        authority.get("decision")
        != "proceed_to_one_DELL_admission_issuance_only"
        or authority.get("admission_issuance_authorized") is not True
        or authority.get("admission_consumption_authorized") is not False
        or authority.get("exact_live_execution_authorized") is not False
        or authority.get("maximum_new_admissions") != 1
        or authority.get("authorized_case") != "DELL"
        or authority.get("MU_admission_authorized") is not False
        or authority.get("NVDA_admission_authorized") is not False
        or authority.get("automatic_next_case_authorized") is not False
    ):
        raise ValueError("experiment_a_fresh_authority_scope_invalid")
    if any(
        authority.get(key) != 0
        for key in (
            "model_calls_authorized",
            "provider_calls_authorized",
            "network_calls_authorized",
            "mcp_calls_authorized",
        )
    ):
        raise ValueError("experiment_a_fresh_authority_external_call_invalid")
    provider = decision.get("provider_qualification") or {}
    if (
        provider.get("credential_present") is not True
        or provider.get("credential_value_read_or_persisted") is not False
        or provider.get("provider_probe_performed") is not False
        or provider.get("runtime_explicit_max_transport_attempts") != 1
        or provider.get("implicit_transport_retry_possible") is not False
    ):
        raise ValueError("experiment_a_fresh_authority_provider_boundary_invalid")
    storage = decision.get("admission_storage_boundary") or {}
    if (
        storage.get("tracked_config_or_source_write_forbidden") is not True
        or storage.get("required_root")
        != ".codex_runtime/fin013_s2_05/authorities/DELL"
        or storage.get("git_ignore_rule") != "/.codex_runtime/"
        or storage.get("plaintext_secret_storage_forbidden") is not True
    ):
        raise ValueError("experiment_a_fresh_authority_storage_boundary_invalid")
    if decision.get("material_blockers") != []:
        raise ValueError("experiment_a_fresh_authority_material_blocker_present")


def test_fresh_authority_is_Dell_issuance_only_and_zero_call() -> None:
    decision = _load()
    _validate(decision)
    assert decision["status"].startswith("DELL_admission_issuance_authorized")
    assert decision["preflight_evidence"]["admissions_issued"] == 0
    assert decision["preflight_evidence"]["admissions_consumed"] == 0
    assert decision["next_action"].endswith("DELL-FRESH-EXACT-ADMISSION-ISSUANCE")


def test_frozen_bindings_remain_valid_historical_identifiers_after_successor() -> None:
    decision = _load()
    for binding in decision["frozen_bindings"].values():
        assert _DIGEST.fullmatch(binding["sha256"])
        assert (ROOT / binding["ref"]).is_file()
    implementation = json.loads(
        (
            ROOT
            / decision["frozen_bindings"]["zero_call_implementation"]["ref"]
        ).read_text(encoding="utf-8")
    )
    assert (
        implementation["implementation_digest"]
        == decision["frozen_bindings"]["zero_call_implementation"][
            "implementation_digest"
        ]
    )


def test_authority_storage_is_git_ignored_and_not_a_tracked_admission() -> None:
    decision = _load()
    storage = decision["admission_storage_boundary"]["required_root"]
    probe = storage + "/probe.json"
    result = subprocess.run(
        ["git", "check-ignore", "-q", probe],
        cwd=ROOT,
        check=False,
    )
    assert result.returncode == 0
    assert not list(
        (ROOT / "configs/releases").glob(
            "fin_ia_0_1_3_s2_05_experiment_a_dell_fresh_exact_admission*.json"
        )
    )


def test_decision_contains_no_credential_value_or_hidden_gold_authority() -> None:
    text = DECISION.read_text(encoding="utf-8")
    assert "sk-" not in text
    assert "Authorization" not in text
    assert "hidden_gold_read_authorized" not in text
    assert _load()["provider_qualification"]["provider_probe_performed"] is False


@pytest.mark.parametrize(
    ("mutator", "expected"),
    [
        (
            lambda value: value["authority"].update(
                admission_consumption_authorized=True
            ),
            "experiment_a_fresh_authority_scope_invalid",
        ),
        (
            lambda value: value["authority"].update(
                model_calls_authorized=1
            ),
            "experiment_a_fresh_authority_external_call_invalid",
        ),
        (
            lambda value: value["admission_storage_boundary"].update(
                required_root="configs/releases"
            ),
            "experiment_a_fresh_authority_storage_boundary_invalid",
        ),
    ],
)
def test_authority_scope_mutations_fail_closed(mutator, expected: str) -> None:
    decision = _load()
    mutator(decision)
    body = {
        key: deepcopy(value)
        for key, value in decision.items()
        if key != "decision_digest"
    }
    decision["decision_digest"] = canonical_digest(body)
    with pytest.raises(ValueError, match=expected):
        _validate(decision)


def test_digest_mutation_fails_closed() -> None:
    decision = _load()
    decision["authority"]["authorized_case"] = "MU"
    with pytest.raises(ValueError, match="fresh_authority_digest_invalid"):
        _validate(decision)
