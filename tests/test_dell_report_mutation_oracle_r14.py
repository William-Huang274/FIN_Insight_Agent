from __future__ import annotations

from copy import deepcopy
from dataclasses import fields, is_dataclass, replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

import retrieval.dell_report_mutation_oracle_r14 as mutation_module
from retrieval.dell_report_mutation_oracle_r14 import (
    MUTATION_EXECUTION_PROTOCOL,
    MutationExecutionReportR14,
    TRANSACTION_HARD_EXIT_BOUNDARIES,
    build_critical_mutation_kill_receipt_r14,
    build_default_critical_mutation_manifest_r14,
    execute_critical_mutation_suite_r14,
    validate_critical_mutation_kill_receipt_r14,
    validate_critical_mutation_manifest_r14,
)
from retrieval.dell_report_r14_common import (
    DellReportR14ContractError,
    TARGET_IDS,
    canonical_digest,
    canonical_json_bytes,
    domain_rows_digest,
    sha256_bytes,
    with_result_digest,
)
from retrieval.dell_report_delta_r14 import build_r13_to_r14_delta_receipt_r14
from retrieval.dell_report_population_manifest_r14 import (
    build_input_population_manifest_r14,
    build_population_commitment_r14,
    validate_input_population_manifest_r14,
)
from retrieval.dell_report_property_oracle_r14 import (
    build_author_property_manifest_r14,
    build_author_property_receipt_r14,
)
from retrieval.dell_report_r14_contracts import (
    load_and_validate_r14_contracts,
)
from retrieval.dell_report_reconciliation_r14 import (
    build_planned_program_artifact_contracts_r14,
    build_preformal_decision_commitment_r14,
    project_public_reconciliation_r14,
    validate_public_reconciliation_projection_r14,
)
from retrieval.dell_report_resource_gate_r14 import (
    FROZEN_HARD_LIMIT_MS,
    FROZEN_HARD_MEMORY_LIMIT_BYTES,
    FROZEN_WARNING_LIMIT_MS,
    build_performance_receipt_r14,
    build_resource_gate_receipt_r14,
)
from retrieval.dell_report_runner_r14 import (
    PARSER_VERSION,
    build_full_program_r14,
    build_program_artifact_payloads_r14,
)
from retrieval.dell_report_decision_vector_r14 import build_decision_vector_receipt_r14
from retrieval.dell_report_decision_vector_rebuilder_r14 import rebuild_decision_vector_r14
from retrieval.dell_report_graph_schema_r14 import (
    validate_event_argument_graph_r14,
    validate_price_attachment_graph_r14,
)
from retrieval.dell_report_target_compiler_r14 import (
    build_target_graph_view_r14,
    compile_target_decisions_r14,
)
from retrieval.dell_report_transaction_r14 import (
    mint_formal_transaction_authority_r14,
    probe_transaction_durability_r14,
    publish_atomic_attempt_r14,
    read_committed_attempt_r14,
)


ROOT = Path(__file__).resolve().parents[1]
REQUIREMENT_PATH = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_r14_requirement_manifest_v1_0.json"
)


@pytest.fixture(scope="module")
def requirement() -> dict:
    return json.loads(REQUIREMENT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def mutation_manifest(requirement) -> dict:
    return build_default_critical_mutation_manifest_r14(
        requirement_manifest=requirement,
        author_seed="R14-AUTHOR-SEED-20260829",
        generator_identity="R14-MUTATION-TEST-GENERATOR",
    )


@pytest.fixture(scope="module")
def implementation_source_repo(tmp_path_factory, mutation_manifest):
    repository_root = tmp_path_factory.mktemp("r14_implementation_source_repo")
    subprocess.run(
        ["git", "init", "-q"],
        cwd=repository_root,
        check=True,
    )
    for key, value in (
        ("user.name", "R14 Test Author"),
        ("user.email", "r14-test-author@example.invalid"),
        ("core.autocrlf", "false"),
    ):
        subprocess.run(
            ["git", "config", key, value],
            cwd=repository_root,
            check=True,
        )
    for row in mutation_manifest["handler_source_rows"]:
        source = ROOT / row["path"]
        destination = repository_root / row["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    subprocess.run(
        ["git", "add", "--", "."],
        cwd=repository_root,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "freeze R14 implementation source closure"],
        cwd=repository_root,
        check=True,
    )
    implementation_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    implementation_tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    drift_path = repository_root / mutation_manifest["handler_source_rows"][0]["path"]
    drift_path.write_bytes(drift_path.read_bytes() + b"\nR14-GIT-BLOB-DRIFT\n")
    subprocess.run(
        ["git", "add", "--", str(drift_path.relative_to(repository_root))],
        cwd=repository_root,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "create negative source-drift commit"],
        cwd=repository_root,
        check=True,
    )
    drift_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    drift_tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return SimpleNamespace(
        root=repository_root,
        commit=implementation_commit,
        tree=implementation_tree,
        drift_commit=drift_commit,
        drift_tree=drift_tree,
    )


_SUPPORT_MODULES: dict[str, object] = {}


def _support_module(stem: str):
    cached = _SUPPORT_MODULES.get(stem)
    if cached is not None:
        return cached
    path = ROOT / "tests" / f"test_dell_report_{stem}_r14.py"
    spec = importlib.util.spec_from_file_location(f"_r14_mutation_support_{stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _SUPPORT_MODULES[stem] = module
    return module


def _artifact_payload(value):
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if is_dataclass(value):
        return {
            item.name: _artifact_payload(getattr(value, item.name))
            for item in fields(value)
            if not item.name.startswith("_")
        }
    if isinstance(value, dict):
        return {str(key): _artifact_payload(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [_artifact_payload(child) for child in value]
    return value


def _artifact_digest(value) -> str:
    return canonical_digest(_artifact_payload(value))


def _typed_rejection(callable_) -> str:
    try:
        callable_()
    except (DellReportR14ContractError, TypeError, ValueError) as exc:
        return f"{type(exc).__name__}::{exc}"
    return "none"


def _filesystem_snapshot(root: Path) -> dict:
    rows = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file():
            payload = path.read_bytes()
            rows.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
        elif path.is_dir():
            rows.append({"path": path.relative_to(root).as_posix() + "/", "directory": True})
    return {"root_exists": root.exists(), "rows": rows}


def _transaction_attempt_snapshot(root: Path, attempt_id: str) -> dict:
    snapshot = _filesystem_snapshot(root)
    reservation = f"attempt_reservations/{attempt_id}.json"
    final_prefix = f"{attempt_id}/"
    staging_prefix = f".{attempt_id}.incomplete."
    rows = [
        row
        for row in snapshot["rows"]
        if row["path"] == attempt_id + "/"
        or row["path"].startswith(final_prefix)
        or row["path"] == reservation
        or row["path"].startswith(staging_prefix)
    ]
    return {
        "schema_version": "fin_ia_dell_03B_R14_transaction_attempt_state_v1_0",
        "attempt_id": attempt_id,
        "rows": rows,
    }


def _run_direct_transaction_hard_exit(
    *, attempt_root: Path, boundary: str, evidence: dict, support
) -> dict:
    driver = r'''
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
    source_root = ROOT / "src"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(source_root)
    artifacts = support._artifacts()
    serialized_artifacts = json.dumps(
        {
            path: {
                "payload_hex": artifact.payload.hex(),
                "semantic_root": artifact.semantic_root,
            }
            for path, artifact in artifacts.items()
        }
    )
    before_state = _transaction_attempt_snapshot(attempt_root, support.ATTEMPT_ID)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            driver,
            str(attempt_root),
            boundary,
            support.ATTEMPT_ID,
            str(source_root),
            json.dumps({key: str(value) for key, value in evidence.items()}),
            serialized_artifacts,
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=False,
        timeout=20,
    )
    final_path = attempt_root / support.ATTEMPT_ID
    reservation_path = (
        attempt_root
        / "attempt_reservations"
        / f"{support.ATTEMPT_ID}.json"
    )
    final_visible = final_path.exists()
    final_reopens = False
    read_rejection = "none"
    if final_visible:
        try:
            final_reopens = (
                read_committed_attempt_r14(
                    attempt_root=attempt_root,
                    attempt_id=support.ATTEMPT_ID,
                ).final_path
                == final_path
            )
        except DellReportR14ContractError:
            final_reopens = False
    else:
        read_rejection = _typed_rejection(
            lambda: read_committed_attempt_r14(
                attempt_root=attempt_root,
                attempt_id=support.ATTEMPT_ID,
            )
        )
    after_state = _transaction_attempt_snapshot(attempt_root, support.ATTEMPT_ID)
    staging_prefix = f".{support.ATTEMPT_ID}.incomplete."
    staging_rows = [
        row
        for row in after_state["rows"]
        if row["path"].startswith(staging_prefix)
    ]
    expected_final = boundary == "after_publish_rename"
    expected_reservation = boundary != "before_reservation"
    nonfinal_reader_rejected = read_rejection.endswith(
        "R14_transaction_final_attempt_not_visible"
    )
    empty_attempt_state = {
        "schema_version": "fin_ia_dell_03B_R14_transaction_attempt_state_v1_0",
        "attempt_id": support.ATTEMPT_ID,
        "rows": [],
    }
    before_reservation_state_is_exact = (
        boundary != "before_reservation"
        or (
            before_state == empty_attempt_state
            and after_state == before_state
            and staging_rows == []
        )
    )
    return {
        "boundary_reached": completed.returncode == 97,
        "child_returncode": completed.returncode,
        "final_visible": final_visible,
        "final_reopens": final_reopens,
        "reservation_visible": reservation_path.is_file(),
        "expected_final_visible": expected_final,
        "expected_reservation_visible": expected_reservation,
        "nonfinal_reader_rejected": nonfinal_reader_rejected,
        "before_reservation_state_is_exact": before_reservation_state_is_exact,
        "protected": (
            completed.returncode == 97
            and final_visible == expected_final
            and (not expected_final or final_reopens)
            and (expected_final or nonfinal_reader_rejected)
            and reservation_path.is_file() == expected_reservation
            and before_reservation_state_is_exact
        ),
        "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
    }


def _authority_observation(evidence: dict, support) -> dict:
    repository_root = Path(evidence["repository_root"]).resolve(strict=True)
    commitment_bytes = support._git_blob_bytes(
        repository_root,
        str(evidence["bundle_commit"]),
        str(evidence["commitment_path"]),
    )
    audit_bytes = support._git_blob_bytes(
        repository_root,
        str(evidence["audit_commit"]),
        str(evidence["preformal_audit_path"]),
    )
    policy_bytes = support._git_blob_bytes(
        repository_root,
        str(evidence["policy_commit"]),
        str(evidence["policy_path"]),
    )
    return with_result_digest(
        {
            "schema_version": "fin_ia_dell_03B_R14_mutation_authority_input_v1_0",
            "repository_root": repository_root.as_posix(),
            "commit_chain": {
                key: str(evidence[key])
                for key in (
                    "governance_commit",
                    "implementation_commit",
                    "bundle_commit",
                    "audit_commit",
                    "policy_commit",
                )
            },
            "control_paths": {
                key: str(evidence[key])
                for key in (
                    "commitment_path",
                    "preformal_audit_path",
                    "policy_path",
                )
            },
            "bound_blob_sha256": {
                "commitment": hashlib.sha256(commitment_bytes).hexdigest(),
                "audit": hashlib.sha256(audit_bytes).hexdigest(),
                "policy": hashlib.sha256(policy_bytes).hexdigest(),
            },
        }
    )


def _forge_replaced_bundle_commitment_chain(
    *, evidence: dict, support, destination: Path
) -> tuple[dict, dict, dict]:
    source_repo = Path(evidence["repository_root"]).resolve(strict=True)
    subprocess.run(
        ["git", "clone", "--quiet", str(source_repo), str(destination)],
        check=True,
        capture_output=True,
    )
    support._run_git(destination, "config", "user.email", "r14-mutation@example.invalid")
    support._run_git(destination, "config", "user.name", "R14 Mutation")
    support._run_git(
        destination,
        "checkout",
        "--detach",
        str(evidence["implementation_commit"]),
    )
    commitment = json.loads(
        support._git_blob_bytes(
            source_repo,
            str(evidence["bundle_commit"]),
            str(evidence["commitment_path"]),
        ).decode("utf-8")
    )
    forged_commitment = deepcopy(commitment)
    forged_commitment["canonical_serializer_identity"] = (
        "canonical_json_v1_replaced"
    )
    forged_commitment = with_result_digest(forged_commitment)
    commitment_path = destination / str(evidence["commitment_path"])
    commitment_path.parent.mkdir(parents=True, exist_ok=True)
    commitment_path.write_bytes(canonical_json_bytes(forged_commitment))
    bundle_commit = support._commit(destination, "B-prime exact commitment mutation")

    audit_path = destination / str(evidence["preformal_audit_path"])
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_bytes(
        support._git_blob_bytes(
            source_repo,
            str(evidence["audit_commit"]),
            str(evidence["preformal_audit_path"]),
        )
    )
    audit_commit = support._commit(destination, "A-prime stale audit binding")
    policy_path = destination / str(evidence["policy_path"])
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_bytes(
        support._git_blob_bytes(
            source_repo,
            str(evidence["policy_commit"]),
            str(evidence["policy_path"]),
        )
    )
    policy_commit = support._commit(destination, "P-prime stale policy binding")
    forged_evidence = {
        **evidence,
        "repository_root": destination,
        "bundle_commit": bundle_commit,
        "audit_commit": audit_commit,
        "policy_commit": policy_commit,
    }
    return forged_evidence, commitment, forged_commitment


def _surface_independent_asp_signature(view, decision) -> dict:
    selected_proof_ids = set(decision.proof_ids)
    selected_event_ids = set(decision.event_ids)
    proof_shapes = sorted(
        (
            {
                "proof_family": row.proof_family,
                "rule_id": row.rule_id,
                "state": row.state,
                "node_count": len(row.node_ids),
                "edge_count": len(row.edge_ids),
            }
            for row in view.proofs
            if row.proof_id in selected_proof_ids
        ),
        key=lambda row: (
            row["proof_family"],
            row["rule_id"],
            row["state"],
            row["node_count"],
            row["edge_count"],
        ),
    )
    event_shapes = sorted(
        (
            {
                "event_types": list(row.event_types),
                "target_labels": list(row.target_labels),
                "predicate_operator_ids": list(row.predicate_operator_ids),
                "polarity": row.polarity,
                "modality": row.modality,
                "actuality": row.actuality,
                "lifecycle": row.lifecycle,
                "speech_mode": row.speech_mode,
                "inference_barrier_ids": list(row.inference_barrier_ids),
            }
            for row in view.typed_nodes
            if row.node_id in selected_event_ids
        ),
        key=canonical_json_bytes,
    )
    return {
        "target_id": decision.target_id,
        "outcome": decision.outcome,
        "satisfied_roles": list(decision.satisfied_roles),
        "missing_roles": list(decision.missing_roles),
        "reason_codes": list(decision.reason_codes),
        "selected_proof_shapes": proof_shapes,
        "selected_event_semantics": event_shapes,
    }


def _actual_production_mutation_observation(
    payload: dict,
    *,
    tmp_path: Path,
    tmp_path_factory,
    monkeypatch,
) -> dict:
    family = str(payload["family"])
    operator = str(payload["operator_id"])
    variant = str(payload["operator_variant"])
    target_layer = str(payload["target_layer"])
    production_oracle = ""
    failure_code = ""
    mutation_input_before = None
    mutation_input_after = None
    mutation_target_schema = f"{family}::{operator}"

    if family == "population":
        support = _support_module("population_manifest")
        sources = [support._source("S1", "one"), support._source("S2", "two")]
        objects = [support._object("O1", "S1", "one"), support._object("O2", "S2", "two")]
        before = support._manifest(sources, objects)
        validate_input_population_manifest_r14(before)
        after = deepcopy(before)
        if operator == "delete_cell":
            after["source_canonical_order"].pop()
        elif operator == "duplicate_cell":
            after["object_canonical_order"].append(deepcopy(after["object_canonical_order"][0]))
        elif operator == "move_cell":
            after["source_canonical_order"][0]["manifest_index"] = 1
            after["source_canonical_order"][1]["manifest_index"] = 0
        elif operator == "resign_all_derived_surfaces":
            after["source_canonical_order"][0]["input_digest"] = "f" * 64
            after["source_keyset_digest"] = "e" * 64
            after["manifest_root"] = "d" * 64
        else:
            after["object_canonical_order"][0]["input_digest"] = "c" * 64
        after = with_result_digest(after)
        mutation_input_before = before
        mutation_input_after = after
        mutation_target_schema = "input_population_manifest"
        failure_code = _typed_rejection(lambda: validate_input_population_manifest_r14(after))
        production_oracle = "validate_input_population_manifest_r14"
    elif family == "encoding_error":
        support = _support_module("decision_vector")
        manifest, receipt, details = support._build()
        before = {"receipt": receipt, "details": list(details)}
        if operator in {"bit_flip", "nonzero_padding", "wrong_endian"}:
            mutated = deepcopy(receipt)
            mutated["outcome_bytes_hex"] = {
                "bit_flip": "5b80",
                "nonzero_padding": "1b81",
                "wrong_endian": "801b",
            }[operator]
            mutated = with_result_digest(mutated)
            after = {"receipt": mutated, "details": list(details)}
            failure_code = _typed_rejection(
                lambda: rebuild_decision_vector_r14(
                    manifest=manifest,
                    receipt=mutated,
                    details=details,
                )
            )
            production_oracle = "rebuild_decision_vector_r14"
        elif operator == "C_null_topology":
            reduced = tuple(row for row in details if row["manifest_index"] != 0)
            mutated = deepcopy(receipt)
            mutated["detail_count"] = len(reduced)
            mutated["detail_root"] = domain_rows_digest(
                b"FIN_IA_R14_DECISION_DETAIL_V1\0",
                (canonical_json_bytes(row) for row in reduced),
            )
            mutated = with_result_digest(mutated)
            after = {"receipt": mutated, "details": list(reduced)}
            mutation_input_before = {
                "details_by_manifest_index": {
                    str(row["manifest_index"]): row for row in details
                },
                "receipt_detail_count": receipt["detail_count"],
                "receipt_detail_root": receipt["detail_root"],
                "receipt_result_digest": receipt["result_digest"],
            }
            mutation_input_after = {
                "details_by_manifest_index": {
                    str(row["manifest_index"]): row for row in reduced
                },
                "receipt_detail_count": mutated["detail_count"],
                "receipt_detail_root": mutated["detail_root"],
                "receipt_result_digest": mutated["result_digest"],
            }
            failure_code = _typed_rejection(
                lambda: rebuild_decision_vector_r14(
                    manifest=manifest,
                    receipt=mutated,
                    details=reduced,
                )
            )
            production_oracle = "rebuild_decision_vector_r14"
        else:
            cells = support._cells(manifest)
            before = {"cells": deepcopy(cells)}
            if operator == "orphan_or_N_detail":
                cells[2]["detail"] = {"author_note": "not allowed"}
            else:
                cells[1]["outcome"] = "E"
                cells[1]["detail"] = {
                    "malformed_input_key": "S1",
                    "typed_error_code": "UNREGISTERED_AMBIGUITY",
                }
            after = {"cells": deepcopy(cells)}
            failure_code = _typed_rejection(
                lambda: build_decision_vector_receipt_r14(
                    manifest=manifest,
                    target_id=support.TARGET,
                    lane="source",
                    cells=cells,
                    parser_version="parser",
                    target_topology_digest="1" * 64,
                    price_graph_version="price",
                    pre_registered_malformed_keys=("S3",),
                )
            )
            production_oracle = "build_decision_vector_receipt_r14"
        if mutation_input_before is None:
            mutation_input_before = before
            mutation_input_after = after
        mutation_target_schema = "decision_vector_production_input"
    elif family in {"event", "price", "positive_protection", "transformation"}:
        bundle = load_and_validate_r14_contracts(root=ROOT)
        structural = _support_module("structural_graph")
        target = _support_module("target_compiler")
        transformation = _support_module("transformation")
        if family == "event":
            if operator == "copy_material_role_across_shared_subject":
                graph = structural.build_event_argument_graph_r14(
                    text="Dell offered PowerEdge at $100 and shipped HBM today.",
                    bundle=bundle,
                )
                source_event, destination_event = graph.events
                price_edge = next(row for row in graph.role_edges if row.role == "price")
                copied = replace(
                    price_edge,
                    event_scope_id=destination_event.event_scope_id,
                    event_id=destination_event.event_id,
                )
                mutated = replace(
                    graph,
                    role_edges=tuple(
                        sorted(
                            (*graph.role_edges, copied),
                            key=lambda row: (row.event_id, row.role, row.mention_id, row.edge_digest),
                        )
                    ),
                )
                mutation_input_before = {
                    "copied_role_edge": None,
                }
                mutation_input_after = {
                    "copied_role_edge": copied.as_dict(),
                }
            elif operator == "different_owner_or_period":
                graph = structural.build_event_argument_graph_r14(
                    text="Dell shipped PowerEdge in 2026.", bundle=bundle
                )
                event = graph.events[0]
                mutated_event = replace(event, assertion_owner="micron")
                mutated = replace(graph, events=(mutated_event,))
                mutation_input_before = {
                    "assertion_owner": event.assertion_owner
                }
                mutation_input_after = {
                    "assertion_owner": mutated_event.assertion_owner
                }
            elif operator == "known_to_nonce_predicate":
                before_text = "Micron allocated HBM capacity to Dell in 2026."
                after_text = "Micron glorped HBM capacity to Dell in 2026."
                graph = structural.build_event_argument_graph_r14(
                    text=before_text,
                    bundle=bundle,
                )
                mutated = structural.build_event_argument_graph_r14(
                    text=after_text,
                    bundle=bundle,
                )
                before_event = graph.events[0]
                after_event = next(
                    row for row in mutated.events if "glorp" in row.predicate_normalized
                )
                before_material = bool(before_event.semantic_labels) and (
                    before_event.event_types != ("unknown",)
                )
                after_degraded = (
                    after_event.semantic_labels == ()
                    and after_event.event_types == ("unknown",)
                    and "predicate_semantic_type_unproved"
                    in after_event.limitations
                    and not any(
                        after_event.event_id
                        in {row.source_event_id, row.destination_event_id}
                        and row.proof_state == "PROVED"
                        for row in mutated.target_bridge_edges
                    )
                )
                mutation_input_before = {"raw_text": before_text}
                mutation_input_after = {"raw_text": after_text}
            else:
                graph = structural.build_event_argument_graph_r14(
                    text="Dell shipped PowerEdge and AI server in 2026.",
                    bundle=bundle,
                )
                object_list_proof = next(
                    row
                    for row in graph.proofs
                    if row.rule_id == "G22-OBJECT-LIST" and row.state == "PROVED"
                )
                promoted_mention = next(
                    row
                    for row in graph.mentions
                    if row.mention_id == object_list_proof.premise_node_ids[1]
                )
                source_event = graph.events[0]
                forged_event = replace(
                    source_event,
                    event_scope_id=(
                        f"{source_event.event_scope_id}::FORGED-OBJECT-LIST-EVENT"
                    ),
                    predicate_span=(promoted_mention.start, promoted_mention.end),
                    predicate_surface=graph.raw_text[
                        promoted_mention.start : promoted_mention.end
                    ],
                    predicate_normalized=promoted_mention.normalized_value,
                )
                mutated = replace(
                    graph,
                    events=tuple(
                        sorted(
                            (*graph.events, forged_event),
                            key=lambda row: (
                                row.document_span,
                                row.predicate_span,
                                row.event_scope_id,
                                row.node_digest,
                            ),
                        )
                    ),
                )
                mutation_input_before = {
                    "events": [row.as_dict() for row in graph.events]
                }
                mutation_input_after = {
                    "events": [row.as_dict() for row in mutated.events]
                }
            before = graph
            after = mutated
            if mutation_input_before is None:
                mutation_input_before = graph
                mutation_input_after = mutated
            mutation_target_schema = (
                "structural_raw_text_input"
                if operator == "known_to_nonce_predicate"
                else "event_argument_graph"
            )
            if operator == "known_to_nonce_predicate":
                failure_code = (
                    "GraphOracle::KNOWN_TO_NONCE_PREDICATE_DEGRADED"
                    if before_material and after_degraded
                    else "none"
                )
                production_oracle = "build_event_argument_graph_r14"
            else:
                failure_code = _typed_rejection(
                    lambda: validate_event_argument_graph_r14(mutated)
                )
                production_oracle = "validate_event_argument_graph_r14"
        elif family == "price":
            if operator in {
                "known_to_nonce_higher_head_or_link",
                "direct_product_to_service_contract",
                "multi_head_or_multi_price",
            }:
                baseline_text = (
                    "Dell offered a hardware bundle of PowerEdge R760 and "
                    "PowerEdge XE9680 for a total of $30,000."
                    if operator == "known_to_nonce_higher_head_or_link"
                    else "Dell offered PowerEdge at $100."
                )
                before_graph = structural.build_event_argument_graph_r14(
                    text=baseline_text, bundle=bundle
                )
                before_price = structural.build_price_attachment_graph_r14(
                    graph=before_graph, bundle=bundle
                )
                mutated_text = {
                    "known_to_nonce_higher_head_or_link": (
                        "Dell offered a florple package of PowerEdge R760 and "
                        "PowerEdge XE9680 for a total of $30,000."
                    ),
                    "direct_product_to_service_contract": "Dell offered PowerEdge for $100 under service agreement.",
                    "multi_head_or_multi_price": (
                        "Dell offered PowerEdge at $100, $200."
                    ),
                }[operator]
                after_graph = structural.build_event_argument_graph_r14(
                    text=mutated_text, bundle=bundle
                )
                after_price = structural.build_price_attachment_graph_r14(
                    graph=after_graph, bundle=bundle
                )
                before = {"event": before_graph, "price": before_price}
                after = {"event": after_graph, "price": after_price}
                mutation_input_before = {"raw_text": baseline_text}
                mutation_input_after = {"raw_text": mutated_text}
                before_proved = [
                    row for row in before_price.proofs if row.state == "PROVED"
                ]
                assert len(before_proved) == 1
                degraded = not any(
                    row.state == "PROVED" for row in after_price.proofs
                )
                if operator == "multi_head_or_multi_price":
                    degraded = (
                        degraded
                        and bool(after_price.proofs)
                        and any(
                            row.competing_head_ids
                            or row.competing_price_ids
                            or any(
                                "multiple_price" in limitation
                                or "competing" in limitation
                                for limitation in row.limitations
                            )
                            for row in after_price.proofs
                        )
                    )
                failure_code = (
                    f"PriceOracle::PROVED_TO_UNPROVED::{operator}"
                    if degraded
                    else "none"
                )
                production_oracle = "build_price_attachment_graph_r14"
            else:
                graph = structural.build_event_argument_graph_r14(
                    text="Dell offered PowerEdge at $100.", bundle=bundle
                )
                price = structural.build_price_attachment_graph_r14(
                    graph=graph, bundle=bundle
                )
                proved = next(row for row in price.proofs if row.state == "PROVED")
                rebound = replace(proved, product_mention_ids=("MISSING-PRODUCT",))
                mutated = replace(price, proofs=(rebound,))
                before = price
                after = mutated
                failure_code = _typed_rejection(
                    lambda: validate_price_attachment_graph_r14(mutated, graph=graph)
                )
                production_oracle = "validate_price_attachment_graph_r14"
                mutation_input_before = {
                    "product_mention_ids": list(proved.product_mention_ids)
                }
                mutation_input_after = {
                    "product_mention_ids": list(rebound.product_mention_ids)
                }
            mutation_target_schema = "price_production_input"
        elif family == "transformation":
            source = transformation._view(
                "Dell shipped 20 PowerEdge systems in 2026.", bundle
            )
            baseline = transformation._receipt(source, source)
            if operator == "event_node_role_period_head_or_path_add_delete_rebind":
                quantity = next(
                    row
                    for row in source.typed_edges
                    if row.edge_family == "event_role" and row.edge_type == "quantity"
                )
                period = next(row for row in source.typed_nodes if row.node_type == "period")
                rebound = replace(quantity, destination_node_id=period.node_id)
                compiled = replace(
                    source,
                    typed_edges=tuple(
                        sorted(
                            (rebound if row is quantity else row for row in source.typed_edges),
                            key=lambda row: (row.edge_family, row.edge_type, row.edge_id),
                        )
                    ),
                )
                mutated_receipt = transformation._receipt(source, compiled)
                mutation_input_before = {
                    "quantity_destination_node_id": quantity.destination_node_id,
                }
                mutation_input_after = {
                    "quantity_destination_node_id": rebound.destination_node_id,
                }
            else:
                mutated_receipt = transformation._receipt(
                    source, source, source_passed=False, compiled_passed=False
                )
                mutation_input_before = {
                    "source_graph_valid": True,
                    "compiled_graph_valid": True,
                }
                mutation_input_after = {
                    "source_graph_valid": False,
                    "compiled_graph_valid": False,
                }
            before = baseline
            after = mutated_receipt
            assert baseline["status"] == "PASS_PRESERVATION"
            failure_code = (
                "TransformationOracle::"
                + "+".join(sorted(mutated_receipt["finding_counts"]))
                if mutated_receipt["status"] == "FAIL_TYPED_FINDING"
                else "none"
            )
            production_oracle = "build_graph_transformation_receipt_r14"
            mutation_target_schema = "graph_transformation_input"
        else:
            if operator == "direct_price_structure_damage":
                _, _, view, decisions = target._compile(
                    "Dell offered PowerEdge at $100.", bundle
                )
                before_asp = next(row for row in decisions if row.target_id.endswith("ASP"))
                price_proofs = tuple(
                    row
                    for row in view.proofs
                    if row.proof_family == "price_path"
                    and row.state == "PROVED"
                    and row.event_id in before_asp.event_ids
                )
                assert len(price_proofs) == 1
                price_proof = price_proofs[0]
                mutated_view = replace(
                    view,
                    proofs=tuple(
                        row for row in view.proofs if row.proof_id != price_proof.proof_id
                    ),
                )
                mutated_decisions = compile_target_decisions_r14(
                    view=mutated_view, topology_contract=bundle.topology
                )
                before = {"view": view, "decisions": decisions}
                after = {"view": mutated_view, "decisions": mutated_decisions}
                after_asp = next(row for row in mutated_decisions if row.target_id.endswith("ASP"))
                assert before_asp.outcome == "C"
                failure_code = (
                    "TargetCompiler::ASP_C_TO_P"
                    if after_asp.outcome == "P"
                    else "none"
                )
                production_oracle = "compile_target_decisions_r14"
                mutation_input_before = {
                    "price_path_proof": price_proof.as_dict()
                }
                mutation_input_after = {
                    "price_path_proof": None
                }
                mutation_target_schema = "target_graph_view"
            elif operator == "object_list_structure_damage":
                before_graph = structural.build_event_argument_graph_r14(
                    text="Dell shipped PowerEdge and AI server in 2026.", bundle=bundle
                )
                after_graph = structural.build_event_argument_graph_r14(
                    text="Dell shipped PowerEdge and glorp AI server in 2026.", bundle=bundle
                )
                before = before_graph
                after = after_graph
                assert any(row.rule_id == "G22-OBJECT-LIST" and row.state == "PROVED" for row in before_graph.proofs)
                failure_code = (
                    "GraphOracle::OBJECT_LIST_PROOF_REMOVED"
                    if not any(
                        row.rule_id == "G22-OBJECT-LIST" and row.state == "PROVED"
                        for row in after_graph.proofs
                    )
                    else "none"
                )
                production_oracle = "build_event_argument_graph_r14"
                mutation_input_before = {
                    "raw_text": "Dell shipped PowerEdge and AI server in 2026."
                }
                mutation_input_after = {
                    "raw_text": (
                        "Dell shipped PowerEdge and glorp AI server in 2026."
                    )
                }
                mutation_target_schema = "structural_raw_text_input"
            elif operator == "supplier_family_structure_damage":
                _, _, view, decisions = target._compile(
                    "Micron supplied HBM in 2026 and Dell shipped HBM PowerEdge in 2026.",
                    bundle,
                )
                mutated_view = replace(
                    view,
                    typed_edges=tuple(row for row in view.typed_edges if row.edge_type != "typed_target_bridge"),
                )
                mutated_decisions = compile_target_decisions_r14(
                    view=mutated_view, topology_contract=bundle.topology
                )
                target_id = "DELL-RSQ-03A-TARGET-HBM-SUPPLY"
                before_target = next(row for row in decisions if row.target_id == target_id)
                after_target = next(row for row in mutated_decisions if row.target_id == target_id)
                before = {"view": view, "decisions": decisions}
                after = {"view": mutated_view, "decisions": mutated_decisions}
                assert before_target.outcome == "C"
                failure_code = (
                    "TargetCompiler::HBM_C_TO_P"
                    if after_target.outcome == "P"
                    else "none"
                )
                production_oracle = "compile_target_decisions_r14"
                mutation_input_before = {
                    "typed_target_bridge_edges": [
                        row.as_dict()
                        for row in view.typed_edges
                        if row.edge_type == "typed_target_bridge"
                    ]
                }
                mutation_input_after = {
                    "typed_target_bridge_edges": []
                }
                mutation_target_schema = "target_graph_view"
            else:
                before_text = "Dell offered PowerEdge at $100."
                after_text = "Dell offered PowerEdge at $100!"
                before_event = structural.build_event_argument_graph_r14(
                    text=before_text,
                    bundle=bundle,
                )
                before_price = structural.build_price_attachment_graph_r14(
                    graph=before_event,
                    bundle=bundle,
                )
                before_view = build_target_graph_view_r14(
                    event_graph=before_event,
                    price_graph=before_price,
                )
                before_decisions = compile_target_decisions_r14(
                    view=before_view,
                    topology_contract=bundle.topology,
                )
                after_event = structural.build_event_argument_graph_r14(
                    text=after_text,
                    bundle=bundle,
                )
                after_price = structural.build_price_attachment_graph_r14(
                    graph=after_event,
                    bundle=bundle,
                )
                after_view = build_target_graph_view_r14(
                    event_graph=after_event,
                    price_graph=after_price,
                )
                after_decisions = compile_target_decisions_r14(
                    view=after_view,
                    topology_contract=bundle.topology,
                )
                before = {"view": before_view, "decisions": before_decisions}
                after = {"view": after_view, "decisions": after_decisions}
                mutation_input_before = {"raw_text": before_text}
                mutation_input_after = {"raw_text": after_text}
                before_asp = next(row for row in before_decisions if row.target_id.endswith("ASP"))
                after_asp = next(row for row in after_decisions if row.target_id.endswith("ASP"))
                before_signature = _surface_independent_asp_signature(
                    before_view,
                    before_asp,
                )
                after_signature = _surface_independent_asp_signature(
                    after_view,
                    after_asp,
                )
                assert before_asp.outcome == "C" and after_asp.outcome == "C"
                failure_code = (
                    "TargetCompiler::IRRELEVANT_SURFACE_C_PROTECTED"
                    if before_signature == after_signature
                    and sum(
                        row.proof_family == "price_path"
                        and row.state == "PROVED"
                        and row.proof_id in set(before_asp.proof_ids)
                        for row in before_view.proofs
                    )
                    == 1
                    and sum(
                        row.proof_family == "price_path"
                        and row.state == "PROVED"
                        and row.proof_id in set(after_asp.proof_ids)
                        for row in after_view.proofs
                    )
                    == 1
                    else "none"
                )
                production_oracle = "compile_target_decisions_r14"
                mutation_target_schema = "metamorphic_raw_text_input"
    elif family == "privacy_route":
        support = _support_module("reconciliation")
        _, _, _, _, reconciliation, commitment = support._artifacts()
        if operator == "route_omission_or_rebind":
            before = reconciliation
            after = deepcopy(reconciliation)
            rebound_target = after["target_lane_rows"][0]["target_id"]
            for row in after["target_lane_rows"]:
                if row["target_id"] == rebound_target:
                    row["route_disposition"] = "AUTHOR_REBOUND_ROUTE"
            route_registry = {
                row["target_id"]: row["route_disposition"]
                for row in after["target_lane_rows"]
            }
            after["route_registry_digest"] = canonical_digest(
                dict(sorted(route_registry.items()))
            )
            after["receipt_binding_root"] = domain_rows_digest(
                b"FIN_IA_R14_RECONCILIATION_BINDINGS_V1\0",
                (canonical_json_bytes(row) for row in after["target_lane_rows"]),
            )
            after = with_result_digest(after)
            failure_code = _typed_rejection(
                lambda: project_public_reconciliation_r14(
                    reconciliation=after,
                    commitment=commitment,
                )
            )
            production_oracle = "project_public_reconciliation_r14"
            mutation_input_before = reconciliation
            mutation_input_after = after
            mutation_target_schema = "reconciliation_projection_input"
        else:
            before = project_public_reconciliation_r14(
                reconciliation=reconciliation,
                commitment=commitment,
            )
            after = deepcopy(before)
            after["target_lane_rows"][0]["source_record_id"] = "PRIVATE-SOURCE-ID"
            after["target_lane_rows"][0]["text"] = "private model text"
            after["target_lane_rows"][0]["locator"] = "D:/private/source.json"
            after = with_result_digest(after)
            failure_code = _typed_rejection(
                lambda: validate_public_reconciliation_projection_r14(
                    after,
                    reconciliation=reconciliation,
                    commitment=commitment,
                )
            )
            production_oracle = "validate_public_reconciliation_projection_r14"
            mutation_input_before = before
            mutation_input_after = after
            mutation_target_schema = "public_projection_input"
    elif family == "authority" and operator == "feed_preview_vector_into_formal_compiler":
        support = _support_module("runner")
        bundle = load_and_validate_r14_contracts(root=ROOT)
        sources = [support._source("S-PRICE", "Dell offered PowerEdge at $100.")]
        objects = [support._object("O-PRICE", "S-PRICE", sources[0]["text"])]
        manifest = support._manifest(sources, objects)
        routes = {target_id: "03C_AFTER_R14" for target_id in TARGET_IDS}
        preview = build_full_program_r14(
            manifest=manifest,
            source_rows=sources,
            object_rows=objects,
            bundle=bundle,
            route_registry=routes,
        )
        private_bytes = canonical_json_bytes(manifest)
        population_commitment = build_population_commitment_r14(
            manifest,
            private_sha256=sha256_bytes(private_bytes),
            private_bytes=len(private_bytes),
        )
        commitment = support._synthetic_preformal_commitment(
            preview,
            population_commitment,
        )
        envelope = support.build_formal_compiler_input_envelope_r14(
            manifest=manifest,
            source_rows=sources,
            object_rows=objects,
            bundle=bundle,
            route_registry=routes,
            preformal_commitment=commitment,
            bound_preformal_evidence=support.bind_preformal_evidence_for_formal_r14(
                commitment
            ),
        )
        support.run_formal_recompute_and_compare_r14(input_envelope=envelope)
        before = envelope
        after = dict(envelope)
        after["preview_vector"] = preview.reconciliation["target_lane_rows"]
        failure_code = _typed_rejection(
            lambda: support.run_formal_recompute_and_compare_r14(
                input_envelope=after
            )
        )
        production_oracle = "run_formal_recompute_and_compare_r14"
        mutation_input_before = _artifact_payload(envelope)
        mutation_input_after = _artifact_payload(after)
        mutation_target_schema = "formal_compiler_input_envelope"
    else:
        transaction = _support_module("transaction")
        fixture_factory = getattr(transaction.authority_repo, "__wrapped__")
        generator = fixture_factory(tmp_path_factory)
        evidence = next(generator)
        import retrieval.dell_report_transaction_r14 as transaction_runtime

        monkeypatch.setattr(
            transaction_runtime.shutil,
            "disk_usage",
            lambda _: SimpleNamespace(total=4 * 1024**3, used=1024**3, free=3 * 1024**3),
        )
        try:
            if family == "authority":
                mint_formal_transaction_authority_r14(**evidence)
                before = _authority_observation(evidence, transaction)
                if operator == "replace_B_commitment":
                    forged, original_commitment, forged_commitment = (
                        _forge_replaced_bundle_commitment_chain(
                            evidence=evidence,
                            support=transaction,
                            destination=tmp_path / "authority-B-prime",
                        )
                    )
                    mutation_input_before = original_commitment
                    mutation_input_after = forged_commitment
                else:
                    forged = dict(evidence)
                    forged["preformal_audit_path"] = evidence[
                        "commitment_path"
                    ]
                    mutation_input_before = {
                        "preformal_audit_path": str(
                            evidence["preformal_audit_path"]
                        )
                    }
                    mutation_input_after = {
                        "preformal_audit_path": str(
                            forged["preformal_audit_path"]
                        )
                    }
                after = _authority_observation(forged, transaction)
                failure_code = _typed_rejection(
                    lambda: mint_formal_transaction_authority_r14(**forged)
                )
                production_oracle = "mint_formal_transaction_authority_r14"
                mutation_target_schema = "formal_transaction_authority_input"
            else:
                attempt_root = tmp_path / f"actual-{operator}-{variant.replace(':', '-')}"
                attempt_root.mkdir()
                artifacts = transaction._artifacts()
                authority = mint_formal_transaction_authority_r14(**evidence)
                if operator == "kill_at_each_write_flush_manifest_marker_rename_boundary":
                    before = _transaction_attempt_snapshot(
                        attempt_root, transaction.ATTEMPT_ID
                    )
                    mutation_input_before = {
                        "boundary_hook": "none",
                    }
                    mutation_input_after = {
                        "boundary_hook": variant,
                    }
                    transaction_observation = _run_direct_transaction_hard_exit(
                        attempt_root=attempt_root,
                        boundary=variant,
                        evidence=evidence,
                        support=transaction,
                    )
                    after = _transaction_attempt_snapshot(
                        attempt_root, transaction.ATTEMPT_ID
                    )
                    protected = transaction_observation["protected"]
                elif operator == "collision":
                    capability = probe_transaction_durability_r14(
                        attempt_root=attempt_root
                    )
                    publish_atomic_attempt_r14(
                        attempt_root=attempt_root,
                        attempt_id=transaction.ATTEMPT_ID,
                        nonce="baseline",
                        authority=authority,
                        durability_capability=capability,
                        artifacts=artifacts,
                    )
                    before = _transaction_attempt_snapshot(
                        attempt_root, transaction.ATTEMPT_ID
                    )
                    mutation_input_before = {
                        "publish_ordinal": 1,
                        "attempt_id": transaction.ATTEMPT_ID,
                    }
                    mutation_input_after = {
                        "publish_ordinal": 2,
                        "attempt_id": transaction.ATTEMPT_ID,
                    }
                    collision_boundary_trace: list[str] = []

                    def record_collision_boundary(selected: str, _paths) -> None:
                        collision_boundary_trace.append(selected)

                    collision_rejection = _typed_rejection(
                        lambda: publish_atomic_attempt_r14(
                            attempt_root=attempt_root,
                            attempt_id=transaction.ATTEMPT_ID,
                            nonce="collision",
                            authority=authority,
                            durability_capability=capability,
                            artifacts=artifacts,
                            boundary_hook=record_collision_boundary,
                        )
                    )
                    after = _transaction_attempt_snapshot(
                        attempt_root, transaction.ATTEMPT_ID
                    )
                    reopened = read_committed_attempt_r14(
                        attempt_root=attempt_root,
                        attempt_id=transaction.ATTEMPT_ID,
                    )
                    protected = (
                        collision_rejection.endswith(
                            "R14_transaction_target_already_exists"
                        )
                        and before == after
                        and collision_boundary_trace == []
                        and reopened.final_path
                        == attempt_root / transaction.ATTEMPT_ID
                    )
                else:
                    capability = probe_transaction_durability_r14(
                        attempt_root=attempt_root
                    )
                    before = _transaction_attempt_snapshot(
                        attempt_root, transaction.ATTEMPT_ID
                    )
                    mutation_input_before = {"boundary_hook": "none"}
                    mutation_input_after = {
                        "boundary_hook": "after_staging_create"
                    }
                    boundary_trace: list[str] = []

                    def stop(selected: str, _paths) -> None:
                        boundary_trace.append(selected)
                        if selected == "after_staging_create":
                            raise RuntimeError(f"injected:{selected}")

                    raised = False
                    try:
                        publish_atomic_attempt_r14(
                            attempt_root=attempt_root,
                            attempt_id=transaction.ATTEMPT_ID,
                            nonce="partial-staging",
                            authority=authority,
                            durability_capability=capability,
                            artifacts=artifacts,
                            boundary_hook=stop,
                        )
                    except RuntimeError as exc:
                        raised = str(exc) == "injected:after_staging_create"
                    after = _transaction_attempt_snapshot(
                        attempt_root, transaction.ATTEMPT_ID
                    )
                    final_path = attempt_root / transaction.ATTEMPT_ID
                    staging_paths = list(
                        attempt_root.glob(
                            f".{transaction.ATTEMPT_ID}.incomplete.*"
                        )
                    )
                    read_rejection = _typed_rejection(
                        lambda: read_committed_attempt_r14(
                            attempt_root=attempt_root,
                            attempt_id=transaction.ATTEMPT_ID,
                        )
                    )
                    expected_boundary_trace = [
                        "before_reservation",
                        "after_reservation_write_before_flush",
                        "after_reservation_flush_before_close",
                        "after_reservation_flush",
                        "after_staging_create",
                    ]
                    reservation_relative_path = (
                        "attempt_reservations/"
                        f"{transaction.ATTEMPT_ID}.json"
                    )
                    staging_relative_path = (
                        f".{transaction.ATTEMPT_ID}.incomplete.partial-staging/"
                    )
                    after_rows_by_path = {
                        row["path"]: row for row in after["rows"]
                    }
                    reservation_row = after_rows_by_path.get(
                        reservation_relative_path
                    )
                    staging_row = after_rows_by_path.get(staging_relative_path)
                    exact_partial_inventory = (
                        before
                        == {
                            "schema_version": (
                                "fin_ia_dell_03B_R14_"
                                "transaction_attempt_state_v1_0"
                            ),
                            "attempt_id": transaction.ATTEMPT_ID,
                            "rows": [],
                        }
                        and after.get("schema_version")
                        == (
                            "fin_ia_dell_03B_R14_"
                            "transaction_attempt_state_v1_0"
                        )
                        and after.get("attempt_id") == transaction.ATTEMPT_ID
                        and set(after_rows_by_path)
                        == {reservation_relative_path, staging_relative_path}
                        and isinstance(reservation_row, dict)
                        and set(reservation_row) == {"path", "bytes", "sha256"}
                        and type(reservation_row["bytes"]) is int
                        and reservation_row["bytes"] > 0
                        and len(str(reservation_row["sha256"])) == 64
                        and staging_row
                        == {"path": staging_relative_path, "directory": True}
                    )
                    protected = (
                        raised
                        and boundary_trace == expected_boundary_trace
                        and not final_path.exists()
                        and len(staging_paths) == 1
                        and staging_paths[0].is_dir()
                        and exact_partial_inventory
                        and read_rejection.endswith(
                            "R14_transaction_final_attempt_not_visible"
                        )
                    )
                failure_code = (
                    f"TransactionOracle::{operator}::{variant}"
                    if protected
                    else "none"
                )
                production_oracle = "publish_atomic_attempt_r14"
                mutation_target_schema = "transaction_control_input"
        finally:
            try:
                next(generator)
            except StopIteration:
                pass

    before_digest = _artifact_digest(before)
    after_digest = _artifact_digest(after)
    assert mutation_input_before is not None and mutation_input_after is not None
    mutation_input_before_payload = _artifact_payload(mutation_input_before)
    mutation_input_after_payload = _artifact_payload(mutation_input_after)
    mutation_patch = mutation_module._build_exact_mutation_patch_r14(
        target_schema=mutation_target_schema,
        before_input=mutation_input_before_payload,
        after_input=mutation_input_after_payload,
    )
    assert production_oracle == payload["production_oracle"]
    production_entry_relative_path = str(payload["production_entry_path"])
    production_entry_path = ROOT / production_entry_relative_path
    assert production_entry_path.is_file()
    production_entry_source_sha256 = hashlib.sha256(
        production_entry_path.read_bytes()
    ).hexdigest()
    assert production_entry_source_sha256 == payload[
        "production_entry_source_sha256"
    ]
    killed = failure_code != "none"
    mutation_spec = {
        "case_id": payload["case_id"],
        "family": family,
        "operator_id": operator,
        "operator_variant": variant,
        "production_oracle": production_oracle,
        "production_entry_path": production_entry_relative_path,
        "before_artifact_digest": before_digest,
        "after_artifact_digest": after_digest,
        "handler_dependency_root": payload["handler_dependency_root"],
        "mutation_patch_digest": mutation_patch["result_digest"],
        "mutation_after_input_sha256": mutation_patch[
            "after_input_sha256"
        ],
        "mutation_patch_contract_digest": payload[
            "mutation_patch_contract_digest"
        ],
    }
    body = {
        "protocol": mutation_module.ACTUAL_MUTATION_OBSERVATION_PROTOCOL,
        "case_id": payload["case_id"],
        "family": family,
        "operator_id": operator,
        "operator_variant": variant,
        "payload_digest": payload["payload_digest"],
        "before_artifact_digest": before_digest,
        "after_artifact_digest": after_digest,
        "mutation_input_before": mutation_input_before_payload,
        "mutation_input_after": mutation_input_after_payload,
        "mutation_patch": mutation_patch,
        "mutation_after_input_sha256": mutation_patch[
            "after_input_sha256"
        ],
        "mutation_patch_contract_digest": payload[
            "mutation_patch_contract_digest"
        ],
        "handler_dependency_sources": payload[
            "handler_dependency_sources"
        ],
        "handler_dependency_root": payload["handler_dependency_root"],
        "production_oracle": production_oracle,
        "production_entry_path": production_entry_relative_path,
        "production_entry_source_sha256": production_entry_source_sha256,
        "production_mutation_spec_digest": canonical_digest(mutation_spec),
        "oracle_status": "KILLED" if killed else "SURVIVED",
        "oracle_outcome_type": (
            mutation_module._operator_oracle_kind(family, operator)
            if killed
            else "none"
        ),
        "observation_layer": target_layer if killed else "none",
        "observed_failure_code": failure_code,
    }
    return {**body, "row_digest": canonical_digest(body)}


def test_r14_injected_operator_fixture_is_consumed_by_oracle_process(
    tmp_path,
    tmp_path_factory,
    monkeypatch,
) -> None:
    payload_path = os.environ.get("FIN_IA_R14_MUTATION_PAYLOAD_PATH")
    if not payload_path:
        pytest.skip("worker-only injected mutation oracle")
    payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    payload_body = dict(payload)
    payload_digest = payload_body.pop("payload_digest")
    assert payload_digest == mutation_module.canonical_digest(payload_body)
    assert payload_digest == os.environ["FIN_IA_R14_MUTATION_PAYLOAD_DIGEST"]
    assert payload["case_id"] == os.environ["FIN_IA_R14_MUTATION_CASE_ID"]
    assert payload["operator_id"] == os.environ["FIN_IA_R14_MUTATION_OPERATOR"]
    assert payload["operator_variant"] == os.environ["FIN_IA_R14_MUTATION_VARIANT"]
    assert payload["handler_dependency_sources"] == list(
        mutation_module._handler_dependency_sources(
            root=ROOT,
            production_entry_path=payload["production_entry_path"],
        )
    )
    assert payload["handler_dependency_root"] == mutation_module._handler_dependency_root(
        payload["handler_dependency_sources"]
    )
    observation = _actual_production_mutation_observation(
        payload,
        tmp_path=tmp_path,
        tmp_path_factory=tmp_path_factory,
        monkeypatch=monkeypatch,
    )
    observation_path = Path(os.environ["FIN_IA_R14_MUTATION_OBSERVATION_PATH"])
    observation_path.write_bytes(canonical_json_bytes(observation))


@pytest.fixture(scope="module")
def execution_report(mutation_manifest, requirement):
    return execute_critical_mutation_suite_r14(
        manifest=mutation_manifest,
        requirement_manifest=requirement,
        repository_root=ROOT,
    )


def test_r14_mutation_manifest_freezes_every_operator_and_transaction_boundary(
    requirement, mutation_manifest
) -> None:
    validate_critical_mutation_manifest_r14(
        mutation_manifest, requirement_manifest=requirement
    )
    required_operator_count = sum(
        len(rows) for rows in requirement["critical_operator_families"].values()
    )
    covered = {
        (row["family"], row["operator_id"])
        for row in mutation_manifest["case_rows"]
    }
    transaction_rows = [
        row
        for row in mutation_manifest["case_rows"]
        if row["operator_id"]
        == "kill_at_each_write_flush_manifest_marker_rename_boundary"
    ]

    assert len(covered) == required_operator_count
    assert len(transaction_rows) == len(TRANSACTION_HARD_EXIT_BOUNDARIES)
    assert mutation_manifest["critical_case_count"] == len(
        mutation_manifest["case_rows"]
    )
    assert mutation_manifest["frozen_before_execution"] is True


def test_r14_every_case_is_bound_to_a_production_handler_matrix_row(
    requirement,
    mutation_manifest,
) -> None:
    matrix = mutation_module.build_critical_mutation_handler_matrix_r14(
        manifest=mutation_manifest,
        requirement_manifest=requirement,
    )
    assert len(matrix) == len(mutation_manifest["case_rows"]) == 55
    assert [row["case_id"] for row in matrix] == [
        row["case_id"] for row in mutation_manifest["case_rows"]
    ]
    assert len({row["row_digest"] for row in matrix}) == 55
    for manifest_row, matrix_row in zip(mutation_manifest["case_rows"], matrix):
        payload = mutation_module._bound_case_payload(
            row=manifest_row,
            root=ROOT,
            node_id=mutation_module._INJECTED_FIXTURE_CONSUMER_NODE,
        )
        assert payload["protocol"] == MUTATION_EXECUTION_PROTOCOL
        assert "before_fixture" not in payload and "after_fixture" not in payload
        assert payload["manifest_fixture_digest"] == manifest_row["fixture_digest"]
        assert payload["production_mutation_node_id"] == matrix_row["production_handler_node"]
        assert payload["production_oracle"] == matrix_row["production_oracle"]
        assert payload["production_entry_path"] == matrix_row["production_entry_path"]
        assert matrix_row["oracle_outcome_type"] == manifest_row["oracle_expectation_type"]
        assert matrix_row["observation_layer"] == manifest_row["target_layer"]
        assert matrix_row["expected_failure_code"]


def test_r14_manifest_freezes_full_implementation_source_closure(
    requirement,
    mutation_manifest,
) -> None:
    import retrieval.dell_report_transaction_r14 as transaction_runtime

    bindings = mutation_manifest["handler_source_rows"]
    assert [row["path"] for row in bindings] == list(
        transaction_runtime.R14_IMPLEMENTATION_EXACT_PATHS
    )
    assert all(row["bytes"] >= 0 and len(row["sha256"]) == 64 for row in bindings)
    assert all(
        row["handler_source_root"] == mutation_manifest["handler_source_root"]
        and row["mutation_patch_contract_digest"]
        == row["mutation_patch_contract"]["result_digest"]
        for row in mutation_manifest["case_rows"]
    )

    resigned = deepcopy(mutation_manifest)
    resigned["handler_source_rows"] = resigned["handler_source_rows"][:-1]
    resigned["handler_source_root"] = mutation_module._handler_dependency_root(
        resigned["handler_source_rows"]
    )
    resigned = with_result_digest(resigned)
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_mutation_manifest_handler_source_binding_invalid",
    ):
        validate_critical_mutation_manifest_r14(
            resigned,
            requirement_manifest=requirement,
        )


def test_r14_frozen_source_root_rejects_support_drift(
    tmp_path: Path,
    mutation_manifest,
) -> None:
    for row in mutation_manifest["handler_source_rows"]:
        source = ROOT / row["path"]
        destination = tmp_path / row["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    drifted = tmp_path / "tests/test_dell_report_transaction_r14.py"
    drifted.write_bytes(drifted.read_bytes() + b"\n# drift\n")
    row = next(
        row
        for row in mutation_manifest["case_rows"]
        if row["family"] == "transaction" and row["operator_id"] == "collision"
    )
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_mutation_payload_source_differs_from_frozen_manifest",
    ):
        mutation_module._bound_case_payload(
            row=row,
            root=tmp_path,
            node_id=mutation_module._INJECTED_FIXTURE_CONSUMER_NODE,
        )


def test_r14_git_i_source_binding_rejects_descendant_blob_drift(
    mutation_manifest,
    implementation_source_repo,
) -> None:
    assert mutation_module._validate_manifest_source_bindings_against_git_r14(
        manifest=mutation_manifest,
        repository_root=implementation_source_repo.root,
        implementation_commit=implementation_source_repo.commit,
        implementation_tree=implementation_source_repo.tree,
    ) == mutation_manifest["handler_source_root"]

    with pytest.raises(
        DellReportR14ContractError,
        match="R14_mutation_source_git_blob_binding_mismatch",
    ):
        mutation_module._validate_manifest_source_bindings_against_git_r14(
            manifest=mutation_manifest,
            repository_root=implementation_source_repo.root,
            implementation_commit=implementation_source_repo.drift_commit,
            implementation_tree=implementation_source_repo.drift_tree,
        )


def test_r14_exact_patch_rejects_extra_missing_or_renamed_shape() -> None:
    contract = mutation_module._production_mutation_patch_contract(
        family="price",
        operator="multi_head_or_multi_price",
        variant="default",
    )
    before = {"raw_text": "Dell offered PowerEdge at $100."}
    after = {"raw_text": "Dell offered PowerEdge at $100, $200."}
    patch = mutation_module._build_exact_mutation_patch_r14(
        target_schema="price_production_input",
        before_input=before,
        after_input=after,
    )
    mutation_module._validate_exact_mutation_patch_r14(
        patch,
        before_input=before,
        after_input=after,
        expected_contract=contract,
    )

    renamed = deepcopy(patch)
    renamed["target_schema"] = "decoy_input"
    renamed = with_result_digest(renamed)
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_mutation_patch_actual_diff_or_contract_mismatch",
    ):
        mutation_module._validate_exact_mutation_patch_r14(
            renamed,
            before_input=before,
            after_input=after,
            expected_contract=contract,
        )

    extra = deepcopy(patch)
    extra["changes"].append(
        {
            "operation": "ADD",
            "json_pointer": "/decoy",
            "before_value_digest": "0" * 64,
            "after_value_digest": "1" * 64,
        }
    )
    extra["change_count"] += 1
    extra = with_result_digest(extra)
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_mutation_patch_actual_diff_or_contract_mismatch",
    ):
        mutation_module._validate_exact_mutation_patch_r14(
            extra,
            before_input=before,
            after_input=after,
            expected_contract=contract,
        )

    missing = deepcopy(patch)
    missing["changes"] = []
    missing["change_count"] = 0
    missing = with_result_digest(missing)
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_mutation_patch_actual_diff_or_contract_mismatch",
    ):
        mutation_module._validate_exact_mutation_patch_r14(
            missing,
            before_input=before,
            after_input=after,
            expected_contract=contract,
        )

    with pytest.raises(
        DellReportR14ContractError,
        match="R14_mutation_patch_has_no_control_change",
    ):
        mutation_module._build_exact_mutation_patch_r14(
            target_schema="price_production_input",
            before_input=before,
            after_input=deepcopy(before),
        )


def test_r14_bound_worker_consumes_fixture_and_returns_machine_observation(
    mutation_manifest,
) -> None:
    row = next(
        row
        for row in mutation_manifest["case_rows"]
        if row["family"] == "population" and row["operator_id"] == "delete_cell"
    )
    payload = mutation_module._bound_case_payload(
        row=row,
        root=ROOT,
        node_id=mutation_module._INJECTED_FIXTURE_CONSUMER_NODE,
    )
    receipt = mutation_module._run_bound_case_subprocess(payload=payload, root=ROOT)

    assert receipt["protocol"] == MUTATION_EXECUTION_PROTOCOL
    assert receipt["payload_digest"] == payload["payload_digest"]
    assert receipt["oracle_status"] == "KILLED"
    assert receipt["before_artifact_digest"] != receipt["after_artifact_digest"]
    assert receipt["production_oracle"] == "validate_input_population_manifest_r14"
    assert receipt["production_entry_path"].endswith(
        "dell_report_population_manifest_r14.py"
    )
    assert receipt["production_mutation_spec_digest"]
    assert receipt["oracle_outcome_type"] == "MUTANT_REJECTED"
    assert receipt["observed_failure_code"].startswith(
        "DellReportR14ContractError::R14_"
    )


def _assert_bound_actual_production_observation(
    mutation_manifest,
    *,
    family: str,
    operator: str,
    variant: str,
) -> None:
    row = next(
        row
        for row in mutation_manifest["case_rows"]
        if row["family"] == family
        and row["operator_id"] == operator
        and row["operator_variant"] == variant
    )
    payload = mutation_module._bound_case_payload(
        row=row,
        root=ROOT,
        node_id=mutation_module._INJECTED_FIXTURE_CONSUMER_NODE,
    )
    receipt = mutation_module._run_bound_case_subprocess(payload=payload, root=ROOT)

    assert receipt["oracle_status"] == "KILLED", receipt
    assert receipt["production_oracle"] == payload["production_oracle"]
    assert receipt["production_entry_path"] == payload["production_entry_path"]
    assert receipt["oracle_outcome_type"] == row["oracle_expectation_type"]
    assert receipt["observation_layer"] == row["target_layer"]
    assert receipt["mutation_patch"]["change_count"] > 0
    assert receipt["mutation_after_input_sha256"] == receipt[
        "mutation_patch"
    ]["after_input_sha256"]
    assert receipt["observed_failure_code"].startswith(
        payload["expected_failure_code_prefix"]
    )


def _unique_operator_preflight_cases() -> tuple[object, ...]:
    requirement = json.loads(REQUIREMENT_PATH.read_text(encoding="utf-8"))
    manifest = build_default_critical_mutation_manifest_r14(
        requirement_manifest=requirement,
        author_seed="R14-AUTHOR-SEED-20260829",
        generator_identity="R14-MUTATION-TEST-GENERATOR",
    )
    selected: dict[tuple[str, str], tuple[str, str, str]] = {}
    for row in manifest["case_rows"]:
        family = str(row["family"])
        operator = str(row["operator_id"])
        variant = str(row["operator_variant"])
        key = (family, operator)
        if (
            operator
            == "kill_at_each_write_flush_manifest_marker_rename_boundary"
            and variant != "before_reservation"
        ):
            continue
        selected.setdefault(key, (family, operator, variant))
    assert len(selected) == 33
    return tuple(
        pytest.param(*case, id="::".join(case))
        for _, case in sorted(selected.items())
    )


@pytest.mark.parametrize(
    ("family", "operator", "variant"),
    _unique_operator_preflight_cases(),
)
def test_r14_unique_operator_preflight_uses_actual_production_observation(
    mutation_manifest,
    family,
    operator,
    variant,
) -> None:
    _assert_bound_actual_production_observation(
        mutation_manifest,
        family=family,
        operator=operator,
        variant=variant,
    )


def test_r14_bound_worker_rejects_resigned_handler_source_rebind(
    mutation_manifest,
) -> None:
    row = next(
        row
        for row in mutation_manifest["case_rows"]
        if row["family"] == "population" and row["operator_id"] == "delete_cell"
    )
    payload = mutation_module._bound_case_payload(
        row=row,
        root=ROOT,
        node_id=mutation_module._INJECTED_FIXTURE_CONSUMER_NODE,
    )
    forged = deepcopy(payload)
    forged["production_mutation_source_sha256"] = "f" * 64
    forged_body = dict(forged)
    forged_body.pop("payload_digest")
    forged["payload_digest"] = mutation_module.canonical_digest(forged_body)

    with pytest.raises(
        DellReportR14ContractError,
        match="R14_mutation_worker_production_node_rebind",
    ):
        mutation_module._execute_bound_case_worker(forged, root=ROOT)


def test_r14_mutation_manifest_rejects_posthoc_denominator_drop(
    requirement, mutation_manifest
) -> None:
    mutated = deepcopy(mutation_manifest)
    mutated["case_rows"] = mutated["case_rows"][:-1]
    mutated["case_count"] -= 1
    mutated["critical_case_count"] -= 1
    mutated = with_result_digest(mutated)

    with pytest.raises(
        DellReportR14ContractError, match="R14_mutation_manifest_denominator_invalid"
    ):
        validate_critical_mutation_manifest_r14(
            mutated, requirement_manifest=requirement
        )


def test_r14_execution_report_is_one_bound_observation_per_case(
    mutation_manifest,
    execution_report,
) -> None:
    groups = list(execution_report.execution_group_receipts)
    observations = list(execution_report.observations)
    assert len(groups) == len(observations) == mutation_manifest["critical_case_count"] == 55
    assert len({row["case_id"] for row in groups}) == 55
    assert len({row["worker_observation_row_digest"] for row in groups}) == 55
    assert all(row["mutation_patch"]["change_count"] > 0 for row in groups)
    survivors = [
        (row["case_id"], row["returncode"], row["node_ids"])
        for row in groups
        if row["verdict"] != "KILLED"
    ]
    assert not survivors, f"R14 mutation survivors: {survivors!r}"

    forged = deepcopy(groups)
    forged[0]["mutation_after_input_sha256"] = "0" * 64
    body = dict(forged[0])
    body.pop("row_digest")
    forged[0]["row_digest"] = mutation_module.canonical_digest(body)
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_mutation_execution_patch_binding_invalid",
    ):
        mutation_module._validate_execution_group_receipts_r14(
            forged,
            manifest=mutation_manifest,
        )

    forged = deepcopy(groups)
    forged[0]["production_mutation_spec_digest"] = "f" * 64
    body = dict(forged[0])
    body.pop("row_digest")
    forged[0]["row_digest"] = mutation_module.canonical_digest(body)
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_mutation_execution_production_spec_binding_invalid",
    ):
        mutation_module._validate_execution_group_receipts_r14(
            forged,
            manifest=mutation_manifest,
        )


def test_r14_mutation_kill_receipt_requires_exact_keyset_and_100_percent(
    requirement, mutation_manifest, execution_report, implementation_source_repo
) -> None:
    receipt = build_critical_mutation_kill_receipt_r14(
        manifest=mutation_manifest,
        requirement_manifest=requirement,
        execution_report=execution_report,
        repository_root=implementation_source_repo.root,
        implementation_commit=implementation_source_repo.commit,
        implementation_tree=implementation_source_repo.tree,
        test_identity="R14-T1-DIRECT-MUTATION-SUITE",
    )
    assert receipt["status"] == "PASS_100_PERCENT_KILLED"
    assert receipt["killed"] == receipt["denominator"]
    assert receipt["survived"] == receipt["unexecuted"] == receipt["excluded"] == 0

    with pytest.raises(TypeError, match="minted only"):
        MutationExecutionReportR14()
    with pytest.raises(
        DellReportR14ContractError, match="R14_mutation_execution_report_not_minted"
    ):
        build_critical_mutation_kill_receipt_r14(
            manifest=mutation_manifest,
            requirement_manifest=requirement,
            execution_report=object(),
            repository_root=implementation_source_repo.root,
            implementation_commit=implementation_source_repo.commit,
            implementation_tree=implementation_source_repo.tree,
            test_identity="R14-T1-DIRECT-MUTATION-SUITE",
        )


def test_r14_mutation_survivor_cannot_be_resigned_as_pass(
    requirement, mutation_manifest, execution_report, implementation_source_repo
) -> None:
    receipt = build_critical_mutation_kill_receipt_r14(
        manifest=mutation_manifest,
        requirement_manifest=requirement,
        execution_report=execution_report,
        repository_root=implementation_source_repo.root,
        implementation_commit=implementation_source_repo.commit,
        implementation_tree=implementation_source_repo.tree,
        test_identity="R14-T1-DIRECT-MUTATION-SUITE",
    )
    forged = deepcopy(receipt)
    group = forged["execution_group_receipts"][0]
    group["verdict"] = "SURVIVED"
    group["oracle_status"] = "SURVIVED"
    group["oracle_outcome_type"] = "none"
    group["observation_layer"] = "none"
    group["observed_failure_code"] = "none"
    group_body = dict(group)
    group_body.pop("row_digest")
    group["row_digest"] = canonical_digest(group_body)

    observation = forged["observation_rows"][0]
    observation["execution_group_row_digest"] = group["row_digest"]
    observation["case_execution_root"] = (
        mutation_module._case_execution_root_from_group_r14(
            group=group,
            manifest_row=mutation_manifest["case_rows"][0],
        )
    )
    row_body = dict(observation)
    row_body.pop("row_digest")
    observation["row_digest"] = canonical_digest(row_body)
    execution_observations = [
        {
            key: row[key]
            for key in (
                "case_id",
                "observed_verdict",
                "oracle_outcome_type",
                "observation_layer",
                "observed_failure_code",
                "duration_ms",
                "execution_group",
                "execution_group_row_digest",
                "case_execution_root",
            )
        }
        for row in forged["observation_rows"]
    ]
    forged["execution_root"] = domain_rows_digest(
        b"FIN_IA_R14_CRITICAL_MUTATION_EXECUTION_V1\0",
        (
            canonical_json_bytes(row)
            for row in (
                *forged["execution_group_receipts"],
                *execution_observations,
            )
        ),
    )
    forged["observation_root"] = domain_rows_digest(
        b"FIN_IA_R14_CRITICAL_MUTATION_KILLS_V1\0",
        (canonical_json_bytes(row) for row in forged["observation_rows"]),
    )
    forged = with_result_digest(forged)
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_mutation_observation_group_binding_invalid",
    ):
        validate_critical_mutation_kill_receipt_r14(
            forged, manifest=mutation_manifest
        )


def test_r14_mutation_kill_receipt_rejects_resigned_row_rebind(
    requirement, mutation_manifest, execution_report, implementation_source_repo
) -> None:
    receipt = build_critical_mutation_kill_receipt_r14(
        manifest=mutation_manifest,
        requirement_manifest=requirement,
        execution_report=execution_report,
        repository_root=implementation_source_repo.root,
        implementation_commit=implementation_source_repo.commit,
        implementation_tree=implementation_source_repo.tree,
        test_identity="R14-T1-DIRECT-MUTATION-SUITE",
    )
    forged = deepcopy(receipt)
    forged["observation_rows"][0]["manifest_row_digest"] = "f" * 64
    row_body = dict(forged["observation_rows"][0])
    row_body.pop("row_digest")
    forged["observation_rows"][0]["row_digest"] = with_result_digest(row_body)[
        "result_digest"
    ]
    forged = with_result_digest(forged)

    with pytest.raises(
        DellReportR14ContractError,
        match="R14_mutation_kill_receipt_row_binding_invalid",
    ):
        validate_critical_mutation_kill_receipt_r14(
            forged, manifest=mutation_manifest
        )


def test_r14_preformal_builder_integrates_all_real_gate_receipts(
    tmp_path,
    monkeypatch,
    requirement,
    mutation_manifest,
    execution_report,
    implementation_source_repo,
) -> None:
    # This is a contract-composition test, not authority to consume a real
    # formal attempt.  Keep the production disk gate intact while giving the
    # synthetic fixture a deterministic, ample-volume observation.
    monkeypatch.setattr(
        "retrieval.dell_report_resource_gate_r14.shutil.disk_usage",
        lambda _: SimpleNamespace(
            total=4 * 1024**3,
            used=1024**3,
            free=3 * 1024**3,
        ),
    )
    bundle = load_and_validate_r14_contracts(root=ROOT)
    text = "Dell offered PowerEdge at USD 100."
    source = {
        "evidence_id": "R14-PREFORMAL-SOURCE",
        "text": text,
        "metadata": {"source_page_record_id": "R14-PREFORMAL-FAMILY"},
    }
    compiled_object = {
        "compiled_object_id": "R14-PREFORMAL-OBJECT",
        "model_text": text,
        "object_kind": "claim",
        "lineage_source_record_ids": [source["evidence_id"]],
        "base_object_view": {
            "source_record_id": source["evidence_id"],
            "source_lineage": {
                "source_page_record_id": "R14-PREFORMAL-FAMILY"
            },
            "surface_text": text,
            "focus_binding": {
                "mode": "exact_text",
                "char_start": 0,
                "char_end": len(text),
            },
        },
    }
    manifest = build_input_population_manifest_r14(
        source_rows=[source],
        object_rows=[compiled_object],
        source_ref="private/source.jsonl",
        source_sha256="a" * 64,
        object_ref="private/object.jsonl",
        object_sha256="b" * 64,
        implementation_identity="R14-PREFORMAL-INTEGRATION",
        changed_path_digest="c" * 64,
        recorded_at="2026-08-29T00:00:00+08:00",
    )
    routes = {
        target_id: "03C_EXTERNAL_LADDER_AFTER_R14" for target_id in TARGET_IDS
    }
    program = build_full_program_r14(
        manifest=manifest,
        source_rows=[source],
        object_rows=[compiled_object],
        bundle=bundle,
        route_registry=routes,
    )
    manifest_bytes = canonical_json_bytes(manifest)
    population_commitment = build_population_commitment_r14(
        manifest,
        private_sha256=sha256_bytes(manifest_bytes),
        private_bytes=len(manifest_bytes),
    )
    summary = {
        field: program.program_receipt[field]
        for field in (
            "family_count",
            "candidate_ceiling",
            "rank_summary",
            "route_summary",
        )
    }
    delta = build_r13_to_r14_delta_receipt_r14(
        program_receipt=program.program_receipt,
        r13_result_digest="d" * 64,
        r13_summary=summary,
        explanations={},
    )
    performance = build_performance_receipt_r14(
        source_input_count=1,
        compiled_input_count=1,
        logical_decision_count=12,
        elapsed_ms=1,
        peak_memory_bytes=1,
        warning_limit_ms=FROZEN_WARNING_LIMIT_MS,
        hard_limit_ms=FROZEN_HARD_LIMIT_MS,
        hard_memory_limit_bytes=FROZEN_HARD_MEMORY_LIMIT_BYTES,
    )
    payloads = build_program_artifact_payloads_r14(program)
    planned_rows = build_planned_program_artifact_contracts_r14(
        payloads=payloads,
        program_receipt=program.program_receipt,
        reconciliation=program.reconciliation,
    )
    capability = probe_transaction_durability_r14(attempt_root=tmp_path)
    resource = build_resource_gate_receipt_r14(
        attempt_root=tmp_path,
        planned_artifacts=planned_rows,
        durability_capability=capability,
        implementation_commit=implementation_source_repo.commit,
        implementation_tree=implementation_source_repo.tree,
        population_manifest_result_digest=manifest["result_digest"],
        program_receipt_result_digest=program.program_receipt["result_digest"],
        performance_receipt_result_digest=performance["result_digest"],
        serializer_scratch_bytes=0,
        raw_capture_or_copy_bytes=0,
        replay_temp_bytes=0,
        failure_receipt_bytes=0,
        runtime_drift_bytes=0,
    )
    mutation_receipt = build_critical_mutation_kill_receipt_r14(
        manifest=mutation_manifest,
        requirement_manifest=requirement,
        execution_report=execution_report,
        repository_root=implementation_source_repo.root,
        implementation_commit=implementation_source_repo.commit,
        implementation_tree=implementation_source_repo.tree,
        test_identity="R14-PREFORMAL-INTEGRATION",
    )
    property_manifest = build_author_property_manifest_r14(
        requirement_manifest=requirement,
        author_seed="R14-PREFORMAL-PROPERTY-SEED",
    )
    property_receipt = build_author_property_receipt_r14(
        manifest=property_manifest,
        requirement_manifest=requirement,
        bundle=bundle,
        implementation_commit=implementation_source_repo.commit,
        implementation_tree=implementation_source_repo.tree,
    )
    commitment_inputs = {
        "repository_root": implementation_source_repo.root,
        "implementation_commit": implementation_source_repo.commit,
        "implementation_tree": implementation_source_repo.tree,
        "implementation_parent": "3" * 40,
        "population_commitment": population_commitment,
        "reconciliation": program.reconciliation,
        "program_receipt": program.program_receipt,
        "r13_delta_receipt": delta,
        "performance_receipt": performance,
        "resource_gate_receipt": resource,
        "mutation_manifest": mutation_manifest,
        "mutation_kill_receipt": mutation_receipt,
        "property_manifest": property_manifest,
        "property_receipt": property_receipt,
        "requirement_manifest": requirement,
        "parser_version": PARSER_VERSION,
        "target_topology_digest": bundle.topology["result_digest"],
        "transformation_version": "R14-exact-source-slice-transformation-v1",
        "canonical_serializer_identity": "canonical_json_v1",
        "planned_artifact_payloads": payloads,
    }
    commitment = build_preformal_decision_commitment_r14(**commitment_inputs)

    assert commitment["critical_mutation_status"] == "PASS_100_PERCENT_KILLED"
    assert commitment["property_status"] == "PASS"
    assert commitment["resource_gate_status"] == "PASS"

    forged_mutation_receipt = deepcopy(mutation_receipt)
    forged_mutation_receipt["implementation_commit"] = (
        implementation_source_repo.drift_commit
    )
    forged_mutation_receipt["implementation_tree"] = (
        implementation_source_repo.drift_tree
    )
    for observation in forged_mutation_receipt["observation_rows"]:
        observation["implementation_commit"] = (
            implementation_source_repo.drift_commit
        )
        observation["implementation_tree"] = implementation_source_repo.drift_tree
        observation_body = dict(observation)
        observation_body.pop("row_digest")
        observation["row_digest"] = canonical_digest(observation_body)
    forged_mutation_receipt["observation_root"] = domain_rows_digest(
        b"FIN_IA_R14_CRITICAL_MUTATION_KILLS_V1\0",
        (
            canonical_json_bytes(row)
            for row in forged_mutation_receipt["observation_rows"]
        ),
    )
    forged_mutation_receipt = with_result_digest(forged_mutation_receipt)
    forged_inputs = {
        **commitment_inputs,
        "implementation_commit": implementation_source_repo.drift_commit,
        "implementation_tree": implementation_source_repo.drift_tree,
        "mutation_kill_receipt": forged_mutation_receipt,
    }
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_mutation_source_git_blob_binding_mismatch",
    ):
        build_preformal_decision_commitment_r14(**forged_inputs)
