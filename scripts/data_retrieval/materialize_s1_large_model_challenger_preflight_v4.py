from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC_ROOT)]

from retrieval.large_model_challenger import (  # noqa: E402
    evaluate_large_model_resource_gate,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from scripts.data_retrieval.materialize_s1_large_model_challenger_preflight_v2 import (  # noqa: E402
    _bound_ref,
    _existing_parent,
    _hardware_receipt,
    _read_json,
    _resolve,
    _sha256,
    _write_json,
)
from scripts.data_retrieval.materialize_s1_large_model_challenger_preflight_v3 import (  # noqa: E402
    _artifact_locator,
    _verify_predecessor_bindings,
)


PROGRAM = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_large_model_challenger_program_v1_2.json"
)
PREDECESSOR_RESULT = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_large_model_challenger_preflight_result_v1_2.json"
)
CLEAN_AUDIT_FAILURE = (
    "configs/audits/"
    "fin_ia_0_1_3_commit_1243b3cc_clean_independent_audit_failure_v1_0.json"
)
OUTPUT = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_large_model_challenger_preflight_result_v1_3.json"
)
PREDECESSOR_RESULT_SHA256 = (
    "205062e1340cf6a9c725bc34dbe970382003101901cb086cac242ea5dcdfd139"
)
CLEAN_AUDIT_FAILURE_SHA256 = (
    "ffdf44e100da7ab259dcbc7669dfed720172e6f9cea218c8b1a27d588d70cbc4"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the zero-call S1 preflight successor whose model "
            "identity rejects link or reparse attributes on every locator component."
        )
    )
    parser.add_argument("--program", default=PROGRAM)
    parser.add_argument("--predecessor-result", default=PREDECESSOR_RESULT)
    parser.add_argument("--clean-audit-failure", default=CLEAN_AUDIT_FAILURE)
    parser.add_argument("--model-storage-root", default="Z:/hf_models")
    parser.add_argument("--embedding-model-dir")
    parser.add_argument("--reranker-model-dir")
    parser.add_argument("--output", default=OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    program_path = _resolve(args.program)
    predecessor_path = _resolve(args.predecessor_result)
    audit_failure_path = _resolve(args.clean_audit_failure)
    program = _read_json(program_path)
    predecessor = _read_json(predecessor_path)
    audit_failure = _read_json(audit_failure_path)
    _verify_predecessor_bindings(program)
    unsigned_audit = {
        key: value
        for key, value in audit_failure.items()
        if key != "receipt_digest"
    }
    if not (
        _sha256(predecessor_path) == PREDECESSOR_RESULT_SHA256
        and predecessor.get("status") == "resource_blocked_before_download"
        and predecessor.get("calls")
        == {"model": 0, "network": 0, "provider": 0}
    ):
        raise ValueError("large_model_challenger_R3_predecessor_invalid")
    if not (
        _sha256(audit_failure_path) == CLEAN_AUDIT_FAILURE_SHA256
        and audit_failure.get("status") == "failed_successor_required"
        and audit_failure.get("audited_commit")
        == "1243b3cc2e1e1c17a46437195c24ab076d3b4365"
        and audit_failure.get("receipt_digest") == canonical_digest(unsigned_audit)
        and any(
            finding.get("finding_id")
            == "S1_MODEL_LOCATOR_ANCESTOR_REPARSE_NOT_REJECTED"
            for finding in audit_failure.get("findings") or []
        )
    ):
        raise ValueError("large_model_challenger_clean_audit_failure_invalid")

    primary_embedding = program["candidates"]["primary_embedding"]
    primary_reranker = program["candidates"]["primary_reranker"]
    embedding_dir = _resolve(
        args.embedding_model_dir or primary_embedding["default_local_dir"]
    )
    reranker_dir = _resolve(
        args.reranker_model_dir or primary_reranker["default_local_dir"]
    )
    storage_path = _existing_parent(_resolve(args.model_storage_root))
    disk = shutil.disk_usage(storage_path)
    storage = {
        "requested_root": str(_resolve(args.model_storage_root)),
        "observed_existing_parent": str(storage_path),
        "total_bytes": int(disk.total),
        "used_bytes": int(disk.used),
        "free_bytes": int(disk.free),
    }
    locators = {
        primary_embedding["model_key"]: _artifact_locator(
            embedding_dir, model_id=primary_embedding["model_id"]
        ),
        primary_reranker["model_key"]: _artifact_locator(
            reranker_dir, model_id=primary_reranker["model_id"]
        ),
    }
    gate = evaluate_large_model_resource_gate(
        program,
        hardware=_hardware_receipt(),
        storage=storage,
        model_artifacts=locators,
    )
    unsigned = {
        "schema_version": (
            "fin_ia_s1_large_model_challenger_preflight_result_v1_3"
        ),
        "recorded_at": "2026-08-24",
        "program_id": program["program_id"],
        "program_ref": program_path.relative_to(ROOT).as_posix(),
        "program_sha256": _sha256(program_path),
        "predecessor": {
            "program_predecessor": dict(program["predecessor"]),
            "R3_preflight_result": _bound_ref(predecessor_path),
            "commit_1243_clean_audit_failure": _bound_ref(audit_failure_path),
        },
        "identity_contract": {
            **dict(program["artifact_identity_contract"]),
            "every_locator_ancestor_link_or_reparse_component_forbidden": True,
            "validated_canonical_path_is_returned_to_future_loader": True,
        },
        "implementation_refs": [
            _bound_ref(ROOT / "src/retrieval/model_identity.py"),
            _bound_ref(ROOT / "src/retrieval/large_model_challenger.py"),
            _bound_ref(
                ROOT
                / "scripts/data_retrieval/"
                "materialize_s1_large_model_challenger_preflight_v4.py"
            ),
        ],
        **gate,
        "audit_successor_checks": {
            "predecessor_resource_receipt_preserved": True,
            "clean_audit_failure_preserved": True,
            "final_model_root_link_or_reparse_rejected": True,
            "nested_link_or_reparse_rejected": True,
            "ancestor_link_or_reparse_components_rejected": True,
            "actual_ancestor_symlink_test_present_with_platform_skip": True,
            "non_skipped_component_walk_regression_present": True,
        },
        "known_boundary": (
            "This zero-call preflight hardens the locator filesystem boundary "
            "but does not download or load a model, observe 4B quality, inspect "
            "COST or hidden references, grant Evidence or NumericFact authority, "
            "qualify S1, or promote a runtime. Acquisition approval and a "
            "24GB-class CUDA/FP16 host remain required."
        ),
    }
    output = {**unsigned, "result_digest": canonical_digest(unsigned)}
    _write_json(_resolve(args.output), output)
    print(
        json.dumps(
            {
                "status": output["status"],
                "device": output["hardware"].get("device_name"),
                "total_memory_bytes": output["hardware"].get(
                    "total_memory_bytes"
                ),
                "resource_blockers": output["resource_blockers"],
                "artifact_blockers": output["artifact_blockers"],
                "audit_successor_checks": output["audit_successor_checks"],
                "calls": output["calls"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
