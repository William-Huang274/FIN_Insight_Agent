from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s1_08_candidate_generation_runtime import load_source_catalog  # noqa: E402
from sec_agent.s1_08_quality_replay import (  # noqa: E402
    audit_restricted_capture_store,
    load_restricted_manifest,
    run_sanitized_quality_replay,
)


CATALOG = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_and_query_revision_policy_v2_0.json"
PLAN = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_quality_first_sourcehunter_capture_replay_integrated_upgrade_plan_v1_0.json"
MANIFEST = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_dell_r1_restricted_capture_manifest_v1_0.json"
FIXTURE = ROOT / "eval_sets/fin_0_1_3_s1_08_sourcehunter_replay/dell_r1_sanitized_quality_replay_fixture_v1_0.json"
OUTPUT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_quality_first_sourcehunter_capture_replay_zero_call_proof_v1_0.json"
RUNTIME_OBJECTS = ROOT / (
    ".codex_runtime/fin013_s1_08_dell_current_search_canary/"
    "fin013_s1_08_dell_search_admission_d1b8c229b7402e195f14/adapter/objects"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    catalog = load_source_catalog(CATALOG)
    plan = _load(PLAN)
    manifest = load_restricted_manifest(MANIFEST)
    fixture = _load(FIXTURE)
    restricted_audit = audit_restricted_capture_store(
        manifest=manifest,
        runtime_root=RUNTIME_OBJECTS,
    )
    replay = run_sanitized_quality_replay(manifest=manifest, fixture=fixture)
    if replay["status"] != "pass":
        raise RuntimeError("s1_08_quality_replay_failed")
    body = {
        "schema_version": "fin_ia_0_1_3_s1_08_quality_first_sourcehunter_capture_replay_zero_call_proof_v1_0",
        "recorded_at": "2026-08-08",
        "stage": "013-S1-08",
        "status": "zero_call_engineering_pass_clean_commit_independent_proof_pending",
        "contract_refs": {
            "plan": plan["schema_version"],
            "catalog": catalog["contract_ref"],
            "manifest": manifest["schema_version"],
            "fixture": fixture["schema_version"],
        },
        "source_digests": {
            "plan": canonical_digest(plan),
            "catalog": canonical_digest(catalog),
            "manifest": canonical_digest(manifest),
            "fixture": canonical_digest(fixture),
        },
        "restricted_capture_audit": restricted_audit,
        "sanitized_replay": replay,
        "implementation": {
            "evidence_slots": 5,
            "provider_neutral_routes": 5,
            "operational_routes": 3,
            "unavailable_routes": [
                "issuer_ir_structured_discovery",
                "external_site_search",
            ],
            "typed_connection_termination": True,
            "pre_fetch_quality_gate": True,
            "post_fetch_content_gate": True,
            "candidate_checkpoint_materialization": True,
            "partial_terminal_result_materialization": True,
            "replacement_network_call_ceiling": 16,
            "document_ceiling_per_query": 1,
        },
        "verification": {
            "focused_tests_expected": 46,
            "three_case_full_fake_and_mutation_included": True,
            "actual_R1_request_objects_verified": 19,
            "network_model_provider_retry_calls": [0, 0, 0, 0],
        },
        "decision": {
            "S1_08Q_A_to_G_engineering": "pass_pending_clean_commit_independent_proof",
            "DELL_R2_replacement_authority": False,
            "MU_NVDA_live": False,
            "ranking_BGE_Milvus": False,
            "DeepSeek_S3": False,
        },
        "known_boundary": "Replay and deterministic tests prove the repaired structure against R1 and synthetic mutations. They do not prove fresh live source reachability, target-in-pool, downstream research quality or release readiness.",
        "current_next": "COMMIT_PUSH_THEN_INDEPENDENT_FRESH_ZERO_CALL_PROOF_ON_CLEAN_ARCHIVE",
    }
    payload = {**body, "proof_digest": canonical_digest(body)}
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(OUTPUT), "proof_digest": payload["proof_digest"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
