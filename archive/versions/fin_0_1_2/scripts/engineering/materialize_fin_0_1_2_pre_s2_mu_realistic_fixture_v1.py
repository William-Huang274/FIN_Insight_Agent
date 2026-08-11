from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.models import canonical_digest


SOURCE_OBJECT_REF = Path(
    ".codex_runtime/"
    "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/"
    "canonical-runtime/objects/fin01/s4/exact-input-heads/29/0e/"
    "290e82aec53d6d3078eb0c8bac94e022bde7cc17a77b72d2315af118ced4958e.json"
)
SOURCE_OBJECT_SHA256 = (
    "290e82aec53d6d3078eb0c8bac94e022bde7cc17a77b72d2315af118ced4958e"
)
SOURCE_OBJECT_BYTES = 196647
SOURCE_INPUT_DIGEST = (
    "7887b5bb447fc6a844c410751f2038a04a1c0b04dbbe7e5bde41b040135a12e1"
)
OUTPUT_REF = Path(
    "tests/fixtures/fin_0_1_2/mu_realistic_three_cell_exact_input_v1.json"
)
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)authorization\s*[:=]"),
    re.compile(r"(?i)api[_-]?key\s*[:=]"),
    re.compile(r"(?i)cookie\s*[:=]"),
    re.compile(r"(?i)private_reasoning"),
)


class FixtureMaterializationError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise FixtureMaterializationError(f"duplicate_json_key:{key}")
        value[key] = item
    return value


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_fixture_payload(source: dict[str, Any]) -> dict[str, Any]:
    input_pack = source.get("input_pack")
    if not isinstance(input_pack, dict):
        raise FixtureMaterializationError("source_input_pack_missing")
    if source.get("input_digest") != SOURCE_INPUT_DIGEST:
        raise FixtureMaterializationError("source_input_digest_mismatch")
    if input_pack.get("input_digest") != SOURCE_INPUT_DIGEST:
        raise FixtureMaterializationError("input_pack_digest_binding_mismatch")
    case_id = str(source.get("case_id") or "")
    case_version = source.get("case_version")
    if (
        input_pack.get("company") != "MU"
        or input_pack.get("case_id") != case_id
        or input_pack.get("case_version") != case_version
    ):
        raise FixtureMaterializationError("source_case_identity_mismatch")
    serialized_input = json.dumps(
        input_pack,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if any(pattern.search(serialized_input) for pattern in _SECRET_PATTERNS):
        raise FixtureMaterializationError("fixture_secret_or_private_output_pattern")
    return {
        "schema_version": "fin_ia_0_1_2_mu_realistic_three_cell_exact_input_fixture_v1_0",
        "fixture_id": "FIN-0.1.2-PRE-S2-MU-REALISTIC-THREE-CELL-EXACT-INPUT-V1",
        "source_object_sha256": SOURCE_OBJECT_SHA256,
        "source_input_digest": SOURCE_INPUT_DIGEST,
        "source_case_id_and_version": {
            "case_id": case_id,
            "case_version": case_version,
        },
        "input_pack": input_pack,
        "provenance_and_nonpromotion_boundary": {
            "source_ref": SOURCE_OBJECT_REF.as_posix(),
            "source_class": "historical_exact_input_head",
            "materialized_from_ignored_host_state": True,
            "fixture_role": "deterministic_zero_call_input_only",
            "credentials_or_authorization_headers_included": False,
            "provider_output_or_private_reasoning_included": False,
            "mutable_work_unit_attempt_or_run_state_included": False,
            "business_acceptance_or_release_claim_included": False,
            "failed_output_business_promotable": False,
        },
    }


def materialize(*, source_path: Path, output_path: Path) -> str:
    source_bytes = source_path.read_bytes()
    if len(source_bytes) != SOURCE_OBJECT_BYTES:
        raise FixtureMaterializationError("source_object_bytes_mismatch")
    if _sha256(source_bytes) != SOURCE_OBJECT_SHA256:
        raise FixtureMaterializationError("source_object_sha256_mismatch")
    source = json.loads(
        source_bytes.decode("utf-8"),
        object_pairs_hook=_strict_object,
    )
    if not isinstance(source, dict):
        raise FixtureMaterializationError("source_object_root_invalid")
    payload = _canonical_fixture_payload(source)
    fixture = {**payload, "content_digest": canonical_digest(payload)}
    rendered = (
        json.dumps(fixture, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and output_path.read_text(encoding="utf-8") != rendered:
        raise FixtureMaterializationError("fixture_output_exists_with_drift")
    output_path.write_text(rendered, encoding="utf-8", newline="\n")
    return _sha256(rendered.encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / SOURCE_OBJECT_REF)
    parser.add_argument("--output", type=Path, default=ROOT / OUTPUT_REF)
    args = parser.parse_args()
    digest = materialize(
        source_path=args.source.resolve(),
        output_path=args.output.resolve(),
    )
    print(
        json.dumps(
            {
                "status": "pass_fixture_materialized",
                "output_ref": args.output.resolve().relative_to(ROOT).as_posix(),
                "fixture_sha256": digest,
                "source_input_digest": SOURCE_INPUT_DIGEST,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
