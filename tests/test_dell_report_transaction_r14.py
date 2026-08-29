from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from retrieval.dell_report_r14_common import DellReportR14ContractError
from retrieval.dell_report_r14_common import (
    TARGET_IDS,
    canonical_digest,
    canonical_json_bytes,
    domain_rows_digest,
    with_result_digest,
)
from retrieval.dell_report_transaction_r14 import (
    FormalTransactionAuthorityR14,
    R14_FORMAL_POLICY_PATH,
    R14_PREFORMAL_AUDIT_PATH,
    R14_PREFORMAL_COMMITMENT_PATH,
    TransactionDurabilityCapabilityR14,
    TransactionArtifactR14,
    mint_formal_transaction_authority_r14,
    probe_transaction_durability_r14,
    publish_atomic_attempt_r14,
    read_committed_attempt_r14,
)
from retrieval.dell_report_reconciliation_r14 import (
    PRIVATE_PROGRAM_ARTIFACT_SCHEMA,
    PUBLIC_PROGRAM_ARTIFACT_SCHEMA,
    formal_compare_contract_r14,
    recompute_program_artifact_semantic_root_r14,
)
from retrieval.dell_report_runner_r14 import (
    replay_full_program_exact_r14,
)


ATTEMPT_ID = "dell-rsq-03b-internal-chain-r14-test"
COMMITMENT_PATH = R14_PREFORMAL_COMMITMENT_PATH
AUDIT_PATH = R14_PREFORMAL_AUDIT_PATH
POLICY_PATH = R14_FORMAL_POLICY_PATH


def _run_git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-m", message)
    return _run_git(repo, "rev-parse", "HEAD")


def _git_blob_bytes(repo: Path, commit: str, path: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=False,
    )
    return completed.stdout


@pytest.fixture(scope="module")
def authority_repo(tmp_path_factory) -> dict[str, object]:
    repo = tmp_path_factory.mktemp("r14-authority-repo")
    _run_git(repo, "init", "-b", "test")
    _run_git(repo, "config", "user.email", "r14-test@example.invalid")
    _run_git(repo, "config", "user.name", "R14 Test")
    (repo / "governance.txt").write_text("G\n", encoding="utf-8")
    implementation_parent = _commit(repo, "G")
    (repo / "implementation.txt").write_text("I\n", encoding="utf-8")
    implementation_commit = _commit(repo, "I")
    implementation_tree = _run_git(repo, "rev-parse", "HEAD^{tree}")
    implementation_paths = tuple(
        sorted(
            _run_git(
                repo,
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                implementation_commit,
            ).splitlines()
        )
    )
    durability_probe_digest = probe_transaction_durability_r14(
        attempt_root=repo
    ).probe_receipt_digest

    artifacts = _artifacts()
    planned_rows = [
        {
            "relative_path": path,
            "exact_bytes": len(artifact.payload),
            "sha256": hashlib.sha256(artifact.payload).hexdigest(),
            "semantic_root": artifact.semantic_root,
        }
        for path, artifact in sorted(artifacts.items())
    ]
    vector_bindings = sorted(
        [
        {
            "target_id": target_id,
            "lane": lane,
            "vector_root": "3" * 64,
            "detail_root": "4" * 64,
            "outcome_counts": {"C": 0, "P": 0, "N": 1, "E": 0},
            "receipt_result_digest": "5" * 64,
        }
        for target_id in TARGET_IDS
        for lane in ("source", "compiled")
        ],
        key=lambda row: (row["target_id"], row["lane"]),
    )
    commitment = with_result_digest(
        {
            "schema_version": "fin_ia_dell_03B_R14_preformal_decision_commitment_v1_0",
            "implementation_commit": implementation_commit,
            "implementation_tree": implementation_tree,
            "implementation_parent": implementation_parent,
            "population_manifest_result_digest": "6" * 64,
            "population_manifest_root": "7" * 64,
            "population_commitment_result_digest": "8" * 64,
            "parser_version": "parser_v1",
            "target_topology_digest": "9" * 64,
            "transformation_version": "transformation_v1",
            "vector_bindings": vector_bindings,
            "receipt_binding_root": "a" * 64,
            "reconciliation_result_digest": "b" * 64,
            "program_receipt_result_digest": "0" * 64,
            "package_root": "1" * 64,
            "event_root": "2" * 64,
            "coverage_root": "3" * 64,
            "family_root": "4" * 64,
            "rank_root": "5" * 64,
            "aggregate_outcome_counts": {"C": 0, "P": 0, "N": 12, "E": 0},
            "aggregate_candidate_ceiling": 0,
            "transformation_root": "c" * 64,
            "route_registry_digest": "d" * 64,
            "r13_delta_receipt_result_digest": "6" * 64,
            "r13_delta_root": "7" * 64,
            "performance_receipt_result_digest": "8" * 64,
            "performance_status": "PASS",
            "peak_memory_bytes": 1,
            "elapsed_ms": 1,
            "performance_warning_limit_ms": 600000,
            "performance_hard_limit_ms": 1800000,
            "performance_hard_memory_limit_bytes": 4 * 1024**3,
            "resource_gate_receipt_result_digest": "9" * 64,
            "resource_gate_status": "PASS",
            "required_free_bytes": 512 * 1024 * 1024,
            "observed_free_bytes": 3 * 1024**3,
            "durability_probe_receipt_digest": durability_probe_digest,
            "resource_planned_artifact_root": "b" * 64,
            "resource_stage_bytes": sum(
                row["exact_bytes"] for row in planned_rows
            ),
            "canonical_serializer_identity": "canonical_json_v1",
            "planned_artifacts": planned_rows,
            "planned_artifact_bytes": {
                row["relative_path"]: row["exact_bytes"] for row in planned_rows
            },
            "planned_artifact_total_bytes": sum(
                row["exact_bytes"] for row in planned_rows
            ),
            "private_artifact_contract_root": domain_rows_digest(
                b"FIN_IA_R14_PRIVATE_ARTIFACT_CONTRACT_V1\0",
                (
                    canonical_json_bytes(row)
                    for row in planned_rows
                    if not row["relative_path"].startswith("public/")
                ),
            ),
            "public_artifact_contract_root": domain_rows_digest(
                b"FIN_IA_R14_PUBLIC_ARTIFACT_CONTRACT_V1\0",
                (
                    canonical_json_bytes(row)
                    for row in planned_rows
                    if row["relative_path"].startswith("public/")
                ),
            ),
            "critical_mutation_manifest_sha256": "a" * 64,
            "critical_mutation_manifest_root": "b" * 64,
            "critical_mutation_kill_receipt_sha256": "c" * 64,
            "critical_mutation_execution_root": "d" * 64,
            "critical_mutation_observation_root": "e" * 64,
            "critical_mutation_status": "PASS_100_PERCENT_KILLED",
            "property_manifest_sha256": "f" * 64,
            "property_operator_version": "property_operator_v1",
            "property_seed": "property_seed_v1",
            "property_matrix_root": "0" * 64,
            "property_receipt_sha256": "1" * 64,
            "property_result_root": "2" * 64,
            "property_status": "PASS",
            "formal_compare_contract": list(formal_compare_contract_r14()),
            "preview_output_is_compiler_input": False,
            "model_provider_calls": 0,
        }
    )
    commitment_file = repo / COMMITMENT_PATH
    commitment_file.parent.mkdir(parents=True)
    commitment_file.write_bytes(canonical_json_bytes(commitment))
    bundle_commit = _commit(repo, "B")
    bundle_tree = _run_git(repo, "rev-parse", "HEAD^{tree}")
    bundle_paths = tuple(
        sorted(_run_git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", bundle_commit).splitlines())
    )

    audit = with_result_digest(
        {
            "schema_version": "fin_ia_dell_03B_R14_preformal_audit_receipt_v1_0",
            "review_task_id": "R14-TEST-FRESH-AUDIT",
            "reviewer_identity": "R14-TEST-REVIEWER",
            "author_identity": "R14-TEST-AUTHOR",
            "author_separated": True,
            "reviewed_implementation_commit": implementation_commit,
            "reviewed_implementation_tree": implementation_tree,
            "reviewed_implementation_parent": implementation_parent,
            "reviewed_implementation_changed_paths": list(implementation_paths),
            "reviewed_bundle_commit": bundle_commit,
            "reviewed_bundle_tree": bundle_tree,
            "reviewed_bundle_parent": implementation_commit,
            "reviewed_bundle_changed_paths": list(bundle_paths),
            "commitment_path": COMMITMENT_PATH,
            "commitment_sha256": hashlib.sha256(canonical_json_bytes(commitment)).hexdigest(),
            "commitment_result_digest": commitment["result_digest"],
            "mutation_execution_root": commitment["critical_mutation_execution_root"],
            "property_result_root": commitment["property_result_root"],
            "fresh_holdout_root": "3" * 64,
            "findings": {"P0": 0, "P1": 0, "P2": 0, "P3": 0},
            "verdict": "PREFORMAL_PASS",
            "lifecycle_state": "PREFORMAL_PASS",
            "reviewer_fresh_no_fork": True,
            "reviewer_read_only": True,
            "prohibited_action_counts": {
                "writes": 0,
                "model_calls": 0,
                "formal_runs": 0,
            },
        }
    )
    audit_file = repo / AUDIT_PATH
    audit_file.parent.mkdir(parents=True)
    audit_file.write_bytes(canonical_json_bytes(audit))
    audit_commit = _commit(repo, "A")

    policy = with_result_digest(
        {
            "schema_version": "fin_ia_dell_03B_R14_formal_policy_v1_0",
            "implementation_commit": implementation_commit,
            "bundle_commit": bundle_commit,
            "audit_commit": audit_commit,
            "commitment_result_digest": commitment["result_digest"],
            "preformal_audit_result_digest": audit["result_digest"],
            "expected_artifact_paths": [row["relative_path"] for row in planned_rows],
            "minimum_free_bytes": 512 * 1024 * 1024,
            "lifecycle_state": "POLICY_BOUND",
            "model_provider_calls": 0,
        }
    )
    policy_file = repo / POLICY_PATH
    policy_file.parent.mkdir(parents=True, exist_ok=True)
    policy_file.write_bytes(canonical_json_bytes(policy))
    policy_commit = _commit(repo, "P")
    import retrieval.dell_report_transaction_r14 as transaction_module

    saved = (
        transaction_module.R14_GOVERNANCE_COMMIT,
        transaction_module.R14_IMPLEMENTATION_EXACT_PATHS,
        transaction_module.R14_BUNDLE_EXACT_PATHS,
        transaction_module._validate_r14_governance_from_implementation,
    )
    transaction_module.R14_GOVERNANCE_COMMIT = implementation_parent
    transaction_module.R14_IMPLEMENTATION_EXACT_PATHS = ("implementation.txt",)
    transaction_module.R14_BUNDLE_EXACT_PATHS = (COMMITMENT_PATH,)
    transaction_module._validate_r14_governance_from_implementation = (
        lambda **_: None
    )
    evidence = {
        "repository_root": repo,
        "governance_commit": implementation_parent,
        "implementation_commit": implementation_commit,
        "bundle_commit": bundle_commit,
        "audit_commit": audit_commit,
        "policy_commit": policy_commit,
        "commitment_path": COMMITMENT_PATH,
        "preformal_audit_path": AUDIT_PATH,
        "policy_path": POLICY_PATH,
    }
    try:
        yield evidence
    finally:
        (
            transaction_module.R14_GOVERNANCE_COMMIT,
            transaction_module.R14_IMPLEMENTATION_EXACT_PATHS,
            transaction_module.R14_BUNDLE_EXACT_PATHS,
            transaction_module._validate_r14_governance_from_implementation,
        ) = saved


def _authority(evidence: dict[str, object]) -> FormalTransactionAuthorityR14:
    return mint_formal_transaction_authority_r14(**evidence)


def _artifacts() -> dict[str, TransactionArtifactR14]:
    private_material = {
        "schema_version": "fin_ia_dell_03B_R14_full_program_private_material_v1_0",
        "test_fixture": True,
    }
    private = with_result_digest(
        {
            "schema_version": PRIVATE_PROGRAM_ARTIFACT_SCHEMA,
            "program_receipt_result_digest": "0" * 64,
            "private_material": private_material,
            "private_material_root": canonical_digest(private_material),
            "model_provider_calls": 0,
        }
    )
    public = with_result_digest(
        {
            "schema_version": PUBLIC_PROGRAM_ARTIFACT_SCHEMA,
            "program_receipt_result_digest": "0" * 64,
            "aggregate_outcome_counts": {"C": 0, "P": 0, "N": 12, "E": 0},
            "aggregate_candidate_ceiling": 0,
            "privacy_contract": {
                "contains_raw_text": False,
                "contains_model_text": False,
                "contains_private_locator": False,
                "contains_source_or_object_ID_rows": False,
                "contains_decision_details": False,
                "creates_reader_citation": False,
            },
            "model_provider_calls": 0,
        }
    )
    private_payload = canonical_json_bytes(private)
    public_payload = canonical_json_bytes(public)
    return {
        "private/result.json": TransactionArtifactR14(
            payload=private_payload,
            semantic_root=recompute_program_artifact_semantic_root_r14(
                relative_path="private/result.json", payload=private_payload
            ),
        ),
        "public/result.json": TransactionArtifactR14(
            payload=public_payload,
            semantic_root=recompute_program_artifact_semantic_root_r14(
                relative_path="public/result.json", payload=public_payload
            ),
        ),
    }


def test_r14_transaction_authority_and_capability_cannot_be_naked_constructed() -> None:
    with pytest.raises(TypeError, match="minted only"):
        FormalTransactionAuthorityR14()
    with pytest.raises(TypeError, match="minted only"):
        TransactionDurabilityCapabilityR14()


def test_r14_transaction_authority_rejects_wrong_governance_or_pathset(
    authority_repo,
) -> None:
    forged = dict(authority_repo)
    forged["governance_commit"] = str(authority_repo["implementation_commit"])
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_transaction_authority_topology_invalid",
    ):
        mint_formal_transaction_authority_r14(**forged)


@pytest.mark.parametrize(
    ("field", "error"),
    (
        ("preformal_audit_path", "R14_transaction_audit_path_not_fixed"),
        ("policy_path", "R14_transaction_policy_path_not_fixed"),
    ),
)
def test_r14_transaction_rejects_caller_pointing_A_or_P_at_implementation(
    authority_repo, field: str, error: str
) -> None:
    forged = dict(authority_repo)
    forged[field] = "implementation.txt"
    with pytest.raises(DellReportR14ContractError, match=error):
        mint_formal_transaction_authority_r14(**forged)


def test_r14_transaction_rejects_A_tree_overwriting_frozen_I_blob(
    tmp_path: Path, authority_repo
) -> None:
    source_repo = Path(authority_repo["repository_root"])
    repo = tmp_path / "A-overwrites-I"
    subprocess.run(
        ["git", "clone", "--quiet", str(source_repo), str(repo)],
        check=True,
        capture_output=True,
    )
    _run_git(repo, "config", "user.email", "r14-test@example.invalid")
    _run_git(repo, "config", "user.name", "R14 Test")
    _run_git(repo, "checkout", "--detach", str(authority_repo["bundle_commit"]))
    audit_file = repo / AUDIT_PATH
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    audit_file.write_bytes(
        _git_blob_bytes(
            source_repo, str(authority_repo["audit_commit"]), AUDIT_PATH
        )
    )
    (repo / "implementation.txt").write_text(
        "A illegally replaced I\n", encoding="utf-8"
    )
    malicious_a = _commit(repo, "A overwrites frozen I")
    policy = json.loads(
        _git_blob_bytes(
            source_repo, str(authority_repo["policy_commit"]), POLICY_PATH
        ).decode("utf-8")
    )
    policy["audit_commit"] = malicious_a
    policy = with_result_digest(policy)
    policy_file = repo / POLICY_PATH
    policy_file.parent.mkdir(parents=True, exist_ok=True)
    policy_file.write_bytes(canonical_json_bytes(policy))
    malicious_p = _commit(repo, "P after malicious A")
    evidence = {
        **authority_repo,
        "repository_root": repo,
        "audit_commit": malicious_a,
        "policy_commit": malicious_p,
    }
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_transaction_I_frozen_blob_changed_in_B_A_or_P",
    ):
        mint_formal_transaction_authority_r14(**evidence)


def test_r14_transaction_rejects_P_tree_overwriting_frozen_B_blob(
    tmp_path: Path, authority_repo
) -> None:
    source_repo = Path(authority_repo["repository_root"])
    repo = tmp_path / "P-overwrites-B"
    subprocess.run(
        ["git", "clone", "--quiet", str(source_repo), str(repo)],
        check=True,
        capture_output=True,
    )
    _run_git(repo, "config", "user.email", "r14-test@example.invalid")
    _run_git(repo, "config", "user.name", "R14 Test")
    _run_git(repo, "checkout", "--detach", str(authority_repo["audit_commit"]))
    policy_file = repo / POLICY_PATH
    policy_file.parent.mkdir(parents=True, exist_ok=True)
    policy_file.write_bytes(
        _git_blob_bytes(
            source_repo, str(authority_repo["policy_commit"]), POLICY_PATH
        )
    )
    (repo / COMMITMENT_PATH).write_bytes(b"P illegally replaced B\n")
    malicious_p = _commit(repo, "P overwrites frozen B")
    evidence = {
        **authority_repo,
        "repository_root": repo,
        "policy_commit": malicious_p,
    }
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_transaction_B_frozen_blob_changed_in_A_or_P",
    ):
        mint_formal_transaction_authority_r14(**evidence)


@pytest.fixture(autouse=True)
def ample_disk(monkeypatch):
    monkeypatch.setattr(
        "retrieval.dell_report_transaction_r14.shutil.disk_usage",
        lambda _: SimpleNamespace(
            total=4 * 1024**3, used=1024**3, free=3 * 1024**3
        ),
    )


def test_r14_transaction_publishes_one_exact_visible_bundle(
    tmp_path: Path, authority_repo
) -> None:
    capability = probe_transaction_durability_r14(attempt_root=tmp_path)
    committed = publish_atomic_attempt_r14(
        attempt_root=tmp_path,
        attempt_id=ATTEMPT_ID,
        nonce="success",
        authority=_authority(authority_repo),
        durability_capability=capability,
        artifacts=_artifacts(),
    )
    reopened = read_committed_attempt_r14(
        attempt_root=tmp_path, attempt_id=ATTEMPT_ID
    )

    assert committed.final_path == reopened.final_path
    assert reopened.transaction_manifest["artifact_count"] == 2
    assert reopened.committed_marker["lifecycle_state"] == "ATTEMPT_CONSUMED"
    assert not list(tmp_path.glob(f".{ATTEMPT_ID}.incomplete.*"))

    with pytest.raises(
        DellReportR14ContractError, match="R14_transaction_target_already_exists"
    ):
        publish_atomic_attempt_r14(
            attempt_root=tmp_path,
            attempt_id=ATTEMPT_ID,
            nonce="collision",
            authority=_authority(authority_repo),
            durability_capability=capability,
            artifacts=_artifacts(),
        )


def test_r14_exact_replay_binds_committed_sidecars_policy_authority_and_runs_once(
    tmp_path: Path, authority_repo, monkeypatch
) -> None:
    authority = _authority(authority_repo)
    capability = probe_transaction_durability_r14(attempt_root=tmp_path)
    committed = publish_atomic_attempt_r14(
        attempt_root=tmp_path,
        attempt_id=ATTEMPT_ID,
        nonce="replay",
        authority=authority,
        durability_capability=capability,
        artifacts=_artifacts(),
    )
    formal_policy = json.loads(
        (Path(authority_repo["repository_root"]) / POLICY_PATH).read_text(
            encoding="utf-8"
        )
    )
    import retrieval.dell_report_runner_r14 as runner_module

    calls = 0
    frozen_manifest = {"result_digest": "f" * 64}
    frozen_sources = [{"frozen_source": True}]
    frozen_objects = [{"frozen_object": True}]
    frozen_routes = {"TEST": "03C_AFTER_R14"}
    artifact_payloads = {
        path: artifact.payload for path, artifact in _artifacts().items()
    }
    private_material = json.loads(
        artifact_payloads["private/result.json"].decode("utf-8")
    )["private_material"]
    recomputed = SimpleNamespace(
        program_receipt={"result_digest": "0" * 64},
        reconciliation={
            "aggregate_outcome_counts": {"C": 0, "P": 0, "N": 12, "E": 0},
            "aggregate_candidate_ceiling": 0,
        },
        model_provider_calls=0,
    )

    def counted_builder(**kwargs):
        nonlocal calls
        calls += 1
        assert kwargs == {
            "manifest": frozen_manifest,
            "source_rows": frozen_sources,
            "object_rows": frozen_objects,
            "bundle": "FROZEN-BUNDLE",
            "route_registry": frozen_routes,
        }
        return recomputed

    monkeypatch.setattr(runner_module, "build_full_program_r14", counted_builder)
    monkeypatch.setattr(
        runner_module,
        "full_program_private_material_r14",
        lambda _: private_material,
    )
    monkeypatch.setattr(
        runner_module,
        "build_program_artifact_payloads_r14",
        lambda _: artifact_payloads,
    )
    replay = replay_full_program_exact_r14(
        repository_root=Path(authority_repo["repository_root"]),
        committed_attempt=committed,
        formal_authority=authority,
        formal_policy=formal_policy,
        manifest=frozen_manifest,
        source_rows=frozen_sources,
        object_rows=frozen_objects,
        bundle="FROZEN-BUNDLE",
        route_registry=frozen_routes,
    )

    assert calls == 1
    assert replay["recomputed_program_count"] == 1
    assert replay["committed_attempt_id"] == ATTEMPT_ID
    assert replay["policy_commit"] == authority.policy_commit
    assert replay["authority_evidence_digest"] == authority.authority_evidence_digest
    assert replay["exact_bytes_equal"] is True


def test_r14_exact_replay_rejects_replaced_published_public_artifact(
    tmp_path: Path, authority_repo
) -> None:
    authority = _authority(authority_repo)
    capability = probe_transaction_durability_r14(attempt_root=tmp_path)
    committed = publish_atomic_attempt_r14(
        attempt_root=tmp_path,
        attempt_id=ATTEMPT_ID,
        nonce="replaced-public",
        authority=authority,
        durability_capability=capability,
        artifacts=_artifacts(),
    )
    public_path = committed.final_path / "public" / "result.json"
    replaced = json.loads(public_path.read_text(encoding="utf-8"))
    replaced["aggregate_candidate_ceiling"] += 1
    public_path.write_bytes(canonical_json_bytes(with_result_digest(replaced)))
    formal_policy = json.loads(
        (Path(authority_repo["repository_root"]) / POLICY_PATH).read_text(
            encoding="utf-8"
        )
    )

    with pytest.raises(
        DellReportR14ContractError,
        match="R14_transaction_artifact_reopen_mismatch",
    ):
        replay_full_program_exact_r14(
            repository_root=Path(authority_repo["repository_root"]),
            committed_attempt=committed,
            formal_authority=authority,
            formal_policy=formal_policy,
            manifest={},
            source_rows=[],
            object_rows=[],
            bundle="UNREACHED",
            route_registry={},
        )


@pytest.mark.parametrize(
    "boundary",
    [
        "before_reservation",
        "after_reservation_flush",
        "after_staging_create",
        "after_artifact_flush:0",
        "after_artifact_rename:0",
        "after_artifact_flush:1",
        "after_artifact_rename:1",
        "after_manifest_flush",
        "after_manifest_rename",
        "after_marker_flush",
        "after_marker_rename",
        "before_publish_rename",
        "after_publish_rename",
    ],
)
def test_r14_transaction_boundary_failure_never_exposes_partial_final(
    tmp_path: Path, boundary: str, authority_repo
) -> None:
    def stop(selected: str, _paths) -> None:
        if selected == boundary:
            raise RuntimeError(f"injected:{selected}")

    capability = probe_transaction_durability_r14(attempt_root=tmp_path)
    with pytest.raises(RuntimeError, match="injected"):
        publish_atomic_attempt_r14(
            attempt_root=tmp_path,
            attempt_id=ATTEMPT_ID,
            nonce="crash",
            authority=_authority(authority_repo),
            durability_capability=capability,
            artifacts=_artifacts(),
            boundary_hook=stop,
        )

    final_path = tmp_path / ATTEMPT_ID
    reservation = tmp_path / "attempt_reservations" / f"{ATTEMPT_ID}.json"
    if boundary == "before_reservation":
        assert not reservation.exists()
        assert not final_path.exists()
    elif boundary == "after_publish_rename":
        assert reservation.is_file()
        assert read_committed_attempt_r14(
            attempt_root=tmp_path, attempt_id=ATTEMPT_ID
        ).final_path == final_path
    else:
        assert reservation.is_file()
        assert not final_path.exists()
        with pytest.raises(
            DellReportR14ContractError,
            match="R14_transaction_final_attempt_not_visible",
        ):
            read_committed_attempt_r14(
                attempt_root=tmp_path, attempt_id=ATTEMPT_ID
            )


def test_r14_transaction_reader_rejects_extra_or_changed_artifact(
    tmp_path: Path, authority_repo
) -> None:
    capability = probe_transaction_durability_r14(attempt_root=tmp_path)
    committed = publish_atomic_attempt_r14(
        attempt_root=tmp_path,
        attempt_id=ATTEMPT_ID,
        nonce="tamper",
        authority=_authority(authority_repo),
        durability_capability=capability,
        artifacts=_artifacts(),
    )
    (committed.final_path / "extra.json").write_bytes(b"{}")
    with pytest.raises(
        DellReportR14ContractError, match="R14_transaction_extra_or_missing_sidecar"
    ):
        read_committed_attempt_r14(
            attempt_root=tmp_path, attempt_id=ATTEMPT_ID
        )

    (committed.final_path / "extra.json").unlink()
    (committed.final_path / "private" / "result.json").write_bytes(b"tampered")
    with pytest.raises(
        DellReportR14ContractError, match="R14_transaction_artifact_reopen_mismatch"
    ):
        read_committed_attempt_r14(
            attempt_root=tmp_path, attempt_id=ATTEMPT_ID
        )


def test_r14_transaction_reader_rejects_actual_descendant_junction(
    tmp_path: Path, authority_repo
) -> None:
    capability = probe_transaction_durability_r14(attempt_root=tmp_path)
    committed = publish_atomic_attempt_r14(
        attempt_root=tmp_path,
        attempt_id=ATTEMPT_ID,
        nonce="junction",
        authority=_authority(authority_repo),
        durability_capability=capability,
        artifacts=_artifacts(),
    )
    external = tmp_path / "external-junction-target"
    external.mkdir()
    junction = committed.final_path / "private" / "forged-junction"
    created = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(external)],
        check=False,
        capture_output=True,
        text=False,
    )
    assert created.returncode == 0
    try:
        with pytest.raises(
            DellReportR14ContractError,
            match="R14_transaction_reader_descendant_reparse_point",
        ):
            read_committed_attempt_r14(
                attempt_root=tmp_path, attempt_id=ATTEMPT_ID
            )
    finally:
        os.rmdir(junction)

def test_r14_transaction_fails_disk_gate_before_attempt_consumption(
    tmp_path: Path, monkeypatch, authority_repo
) -> None:
    monkeypatch.setattr(
        "retrieval.dell_report_transaction_r14.shutil.disk_usage",
        lambda _: SimpleNamespace(total=1024**3, used=1024**3, free=0),
    )
    capability = probe_transaction_durability_r14(attempt_root=tmp_path)
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_transaction_disk_gate_failed_before_reservation",
    ):
        publish_atomic_attempt_r14(
            attempt_root=tmp_path,
            attempt_id=ATTEMPT_ID,
            nonce="disk",
            authority=_authority(authority_repo),
            durability_capability=capability,
            artifacts=_artifacts(),
        )

    assert not (
        tmp_path / "attempt_reservations" / f"{ATTEMPT_ID}.json"
    ).exists()
    assert not (tmp_path / ATTEMPT_ID).exists()


_HARD_CRASH_BOUNDARIES = (
    "before_reservation",
    "after_reservation_write_before_flush",
    "after_reservation_flush_before_close",
    "after_reservation_flush",
    "after_staging_create",
    "after_artifact_0_write_before_flush",
    "after_artifact_0_flush_before_close",
    "after_artifact_flush:0",
    "after_artifact_rename:0",
    "after_artifact_1_write_before_flush",
    "after_artifact_1_flush_before_close",
    "after_artifact_flush:1",
    "after_artifact_rename:1",
    "after_manifest_write_before_flush",
    "after_manifest_flush_before_close",
    "after_manifest_flush",
    "after_manifest_rename",
    "after_marker_write_before_flush",
    "after_marker_flush_before_close",
    "after_marker_flush",
    "after_marker_rename",
    "before_publish_rename",
    "after_publish_rename",
)


@pytest.mark.parametrize("boundary", _HARD_CRASH_BOUNDARIES)
def test_r14_transaction_subprocess_hard_exit_never_exposes_partial_final(
    tmp_path: Path, boundary: str, authority_repo
) -> None:
    driver = r'''
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0, sys.argv[4])
import retrieval.dell_report_transaction_r14 as tx
from retrieval.dell_report_transaction_r14 import TransactionArtifactR14, mint_formal_transaction_authority_r14, probe_transaction_durability_r14, publish_atomic_attempt_r14

attempt_root = Path(sys.argv[1])
selected = sys.argv[2]
attempt_id = sys.argv[3]
evidence = json.loads(sys.argv[5])
evidence["repository_root"] = Path(evidence["repository_root"])
tx.R14_GOVERNANCE_COMMIT = evidence["governance_commit"]
tx.R14_IMPLEMENTATION_EXACT_PATHS = ("implementation.txt",)
tx.R14_BUNDLE_EXACT_PATHS = (evidence["commitment_path"],)
tx._validate_r14_governance_from_implementation = lambda **_: None
authority = mint_formal_transaction_authority_r14(**evidence)
capability = probe_transaction_durability_r14(attempt_root=attempt_root)
tx.shutil.disk_usage = lambda _: SimpleNamespace(total=4 * 1024**3, used=1024**3, free=3 * 1024**3)
artifact_payloads = json.loads(sys.argv[6])
artifacts = {
    path: TransactionArtifactR14(
        bytes.fromhex(row["payload_hex"]), row["semantic_root"]
    )
    for path, row in artifact_payloads.items()
}
def crash(name, _paths):
    if name == selected:
        os._exit(97)
publish_atomic_attempt_r14(
    attempt_root=attempt_root,
    attempt_id=attempt_id,
    nonce="hard-crash",
    authority=authority,
    durability_capability=capability,
    artifacts=artifacts,
    boundary_hook=crash,
)
'''
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(root / "src")
    serialized_evidence = json.dumps(
        {key: str(value) for key, value in authority_repo.items()}
    )
    serialized_artifacts = json.dumps(
        {
            path: {
                "payload_hex": artifact.payload.hex(),
                "semantic_root": artifact.semantic_root,
            }
            for path, artifact in _artifacts().items()
        }
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            driver,
            str(tmp_path),
            boundary,
            ATTEMPT_ID,
            str(root / "src"),
            serialized_evidence,
            serialized_artifacts,
        ],
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert completed.returncode == 97, (completed.stdout, completed.stderr)
    final_path = tmp_path / ATTEMPT_ID
    if boundary == "after_publish_rename":
        assert read_committed_attempt_r14(
            attempt_root=tmp_path, attempt_id=ATTEMPT_ID
        ).final_path == final_path
    else:
        assert not final_path.exists()
