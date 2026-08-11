from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE_RUNNER_PATH = ROOT / (
    "scripts/releases/"
    "run_fin_ia_0_1_s4_t06_entry_single_node_strict_schema_canary.py"
)
EXPECTED_BASE_RUNNER_SHA256 = (
    "18cb228c7002538acfd2f6708e42271eaa3448fb5e9ba02facf4e97774e47844"
)
AUTHORITY_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_openai_credential_requalified_"
    "fresh_strict_schema_canary_authority_decision_v1_0.json"
)
EXPECTED_AUTHORITY_SHA256 = (
    "bb9df485efda0ffacd6ed2a6b496470bca0ed6cb7e56356e7184a9615a1ef27d"
)
METADATA_RESULT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_openai_credential_requalification_"
    "exact_once_metadata_probe_result_v1_0.json"
)
EXPECTED_METADATA_RESULT_SHA256 = (
    "ba1368b9ab3cba319f89e6de96f2d3949a5a59b86b87c6471b013dc2d874766c"
)
OLD_RESULT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_"
    "single_node_strict_schema_canary_exact_once_execution_result_v1_0.json"
)
EXPECTED_OLD_RESULT_SHA256 = (
    "96a5ee24b824bbdd392c735827d2103bb2de118b7535a63009bb9e5d28ae0a0e"
)
RESULT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_openai_credential_requalified_"
    "fresh_strict_schema_canary_exact_once_execution_result_v1_0.json"
)
CANARY_ID = (
    "fin01-s4-t06-entry-openai-strict-schema-dell-demand-"
    "credential-requalified-r1"
)
WORK_ITEM_ID = (
    "S4-T06-ENTRY-OPENAI-CREDENTIAL-REQUALIFIED-FRESH-"
    "STRICT-SCHEMA-CANARY-EXACT-ONCE-EXECUTION"
)
RESULT_SCHEMA_VERSION = (
    "fin_ia_0_1_s4_t06_entry_openai_credential_requalified_"
    "fresh_strict_schema_canary_exact_once_execution_result_v1_0"
)
SUCCESS_NEXT_ACTION = (
    "S4-T06-ENTRY-OPENAI-CREDENTIAL-REQUALIFIED-STRICT-SCHEMA-"
    "CANARY-POST-RESULT-DISPOSITION-DECISION"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_bound_runner():
    expected = {
        BASE_RUNNER_PATH: EXPECTED_BASE_RUNNER_SHA256,
        AUTHORITY_PATH: EXPECTED_AUTHORITY_SHA256,
        METADATA_RESULT_PATH: EXPECTED_METADATA_RESULT_SHA256,
        OLD_RESULT_PATH: EXPECTED_OLD_RESULT_SHA256,
    }
    for path, digest in expected.items():
        if not path.is_file() or _sha256(path) != digest:
            raise RuntimeError(f"fresh_canary_binding_mismatch:{path.name}")
    spec = importlib.util.spec_from_file_location(
        "fin01_s4_t06_bound_strict_schema_canary_base",
        BASE_RUNNER_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("fresh_canary_base_runner_load_failed")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner.AUTHORITY_PATH = AUTHORITY_PATH
    runner.RESULT_PATH = RESULT_PATH
    runner.EXPECTED_AUTHORITY_SHA256 = EXPECTED_AUTHORITY_SHA256
    runner.CANARY_ID = CANARY_ID
    runner.RESULT_SCHEMA_VERSION = RESULT_SCHEMA_VERSION
    runner.WORK_ITEM_ID = WORK_ITEM_ID
    runner.EXPECTED_NEXT_ACTION = WORK_ITEM_ID
    runner.SUCCESS_NEXT_ACTION = SUCCESS_NEXT_ACTION
    return runner


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Consume the fresh exact-once canary identity.",
    )
    args = parser.parse_args()
    runner = _load_bound_runner()
    if args.execute:
        result = runner.execute(result_path=RESULT_PATH)
    else:
        result = runner.preflight(result_path=RESULT_PATH)
        result.pop("template", None)
        result.pop("policy", None)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if str(result["status"]).startswith("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
