"""Build and verify the VT4 P07.2 structural-only SaaS and Banks regressions.

This is a local stdlib-only sidecar.  It consumes the frozen candidate profile
and proves only that two non-P36 rows retain their required structural roles
and typed gaps.  It never executes the product runtime or makes a sector
research, release, provider, or network claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SCRIPT_SCHEMA = "fin_ia_0_1_vt4_structural_regressions_v1_0"
PROFILE_SCHEMA = "fin_ia_0_1_vt4_p36_candidate_profile_v1_0"
PROFILE_STATUS = "candidate_profile_fixture_shadow_internal_only"
STRUCTURAL_STATUS = "structural_only_not_sector_research_validity"
RESULT_STATUS = "fixture_shadow_internal_structural_regression_pass"
EXPECTED_CASE_KEYS = ("saas", "us_banks")
ZERO_BOUNDARY_KEYS = (
    "business_writes",
    "live_execution",
    "model_calls",
    "network_calls",
    "provider_calls",
    "release_admission",
    "tool_invocations",
)
REQUIRED_AUTHORITY = {
    "development_mode": "fixture_shadow_internal_only",
    "runtime_admission": "not_granted",
    "production_readiness": "not_admitted",
    "legacy_global_authority": "retained",
}
ROW_KEYS = frozenset(
    {
        "artifact_scope",
        "case_key",
        "required_observations",
        "required_structural_roles",
        "sector_research_validity",
        "status",
        "typed_gaps",
    }
)
DEFAULT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = (
    DEFAULT_ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_vt4_p36_candidate_profile_v1_0.json"
)


class StructuralRegressionError(ValueError):
    """Raised when a structural-only regression is not demonstrably closed."""


def canonical_json_bytes(value: Any) -> bytes:
    """Use one stable encoding for the result and every SHA-256 binding."""
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise StructuralRegressionError(f"mapping_required:{label}")
    return value


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise StructuralRegressionError(f"string_list_required:{label}")
    if len(value) != len(set(value)):
        raise StructuralRegressionError(f"duplicate_string:{label}")
    return list(value)


def _read_json(path: Path, label: str) -> Mapping[str, Any]:
    try:
        return _mapping(json.loads(path.read_text(encoding="utf-8")), label)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StructuralRegressionError(f"json_read_failed:{label}:{path}") from exc


def _validate_authority(profile: Mapping[str, Any]) -> dict[str, str]:
    authority = _mapping(profile.get("authority"), "authority")
    if dict(authority) != REQUIRED_AUTHORITY:
        raise StructuralRegressionError("authority_boundary_opened")
    return dict(authority)


def _role_index(profile: Mapping[str, Any]) -> dict[str, list[str]]:
    planning = _mapping(profile.get("planning_profile"), "planning_profile")
    cells = planning.get("cells")
    if not isinstance(cells, list) or not cells:
        raise StructuralRegressionError("planning_cells_missing")

    roles_by_family: dict[str, list[str]] = {}
    for index, raw_cell in enumerate(cells):
        cell = _mapping(raw_cell, f"planning_profile.cells[{index}]")
        role = cell.get("active_role")
        if not isinstance(role, str) or not role:
            raise StructuralRegressionError(f"active_role_missing:{index}")
        families = _string_list(
            cell.get("feature_scope_families"),
            f"planning_profile.cells[{index}].feature_scope_families",
        )
        for family in families:
            roles_by_family.setdefault(family, []).append(role)
    return {family: sorted(set(roles)) for family, roles in roles_by_family.items()}


def _validate_cases(
    profile: Mapping[str, Any],
    roles_by_family: Mapping[str, list[str]],
) -> list[dict[str, Any]]:
    regressions = _mapping(profile.get("structural_regressions"), "structural_regressions")
    if regressions.get("status") != STRUCTURAL_STATUS:
        raise StructuralRegressionError("structural_regression_status_invalid")
    raw_cases = regressions.get("cases")
    if not isinstance(raw_cases, list):
        raise StructuralRegressionError("structural_regression_cases_missing")

    case_keys = tuple(
        case.get("case_key") if isinstance(case, Mapping) else None for case in raw_cases
    )
    if case_keys != EXPECTED_CASE_KEYS:
        raise StructuralRegressionError("unexpected_structural_regression_cases")

    cases: list[dict[str, Any]] = []
    for raw_case in raw_cases:
        case = _mapping(raw_case, "structural_regression_case")
        if case.get("status") != STRUCTURAL_STATUS:
            raise StructuralRegressionError(f"case_status_invalid:{case.get('case_key')}")
        families = _string_list(
            case.get("expected_cell_families"),
            f"expected_cell_families:{case.get('case_key')}",
        )
        missing = [family for family in families if family not in roles_by_family]
        if missing:
            raise StructuralRegressionError(
                f"required_structural_roles_missing:{case.get('case_key')}:{','.join(missing)}"
            )
        observations = _string_list(
            case.get("required_observations"),
            f"required_observations:{case.get('case_key')}",
        )
        if observations != ["typed_gaps_required", "no_stale_P36_facts"]:
            raise StructuralRegressionError(f"required_observations_invalid:{case.get('case_key')}")
        for forbidden_key in (
            "forbidden_inherited_facts",
            "forbidden_inherited_numbers",
            "forbidden_inherited_rankings",
            "forbidden_inherited_source_refs",
        ):
            if not _string_list(case.get(forbidden_key), f"{forbidden_key}:{case.get('case_key')}"):
                raise StructuralRegressionError(
                    f"forbidden_carryover_contract_missing:{case.get('case_key')}:{forbidden_key}"
                )
        roles = sorted(
            {
                role
                for family in families
                for role in roles_by_family[family]
            }
        )
        if not roles:
            raise StructuralRegressionError(f"required_structural_roles_empty:{case.get('case_key')}")
        cases.append(
            {
                "case_key": case["case_key"],
                "expected_cell_families": families,
                "required_observations": observations,
                "required_structural_roles": roles,
            }
        )
    return cases


def load_profile(profile_path: Path) -> tuple[Mapping[str, Any], list[dict[str, Any]]]:
    """Load and fail closed on the bounded profile contract used by P07.2."""
    profile = _read_json(profile_path, "candidate_profile")
    if profile.get("schema_version") != PROFILE_SCHEMA:
        raise StructuralRegressionError("candidate_profile_schema_invalid")
    if profile.get("status") != PROFILE_STATUS:
        raise StructuralRegressionError("candidate_profile_status_invalid")
    if profile.get("release_id") != "REL-PROD-001":
        raise StructuralRegressionError("release_id_invalid")
    _validate_authority(profile)
    return profile, _validate_cases(profile, _role_index(profile))


def default_sector_rows(cases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Create content-free rows.  They contain structural roles and typed gaps only."""
    return [
        {
            "case_key": case["case_key"],
            "status": STRUCTURAL_STATUS,
            "artifact_scope": "fixture_shadow_internal_only",
            "sector_research_validity": "not_claimed",
            "required_structural_roles": list(case["required_structural_roles"]),
            "required_observations": list(case["required_observations"]),
            "typed_gaps": [
                "typed_gap:no_sector_evidence_or_claims_present",
                "typed_gap:structural_roles_only",
            ],
        }
        for case in cases
    ]


def _forbidden_row_key(key: str) -> bool:
    return any(
        token in key.lower()
        for token in (
            "fact",
            "number",
            "numeric",
            "percent",
            "rank",
            "source",
            "document",
            "content",
            "ticker",
            "issuer",
            "provider",
            "model",
            "tool",
            "network",
            "live",
            "business_write",
            "release_admission",
        )
    )


def _ensure_content_free(value: Any, label: str, *, allow_p36_marker: bool = False) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise StructuralRegressionError(f"non_string_sector_row_key:{label}")
            if _forbidden_row_key(key):
                raise StructuralRegressionError(f"forbidden_sector_row_field:{label}.{key}")
            _ensure_content_free(nested, f"{label}.{key}")
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _ensure_content_free(nested, f"{label}[{index}]", allow_p36_marker=allow_p36_marker)
        return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        raise StructuralRegressionError(f"numeric_sector_content_forbidden:{label}")
    if not isinstance(value, str):
        raise StructuralRegressionError(f"invalid_sector_row_value:{label}")
    lowered = value.lower()
    if "p36" in lowered and not (allow_p36_marker and value == "no_stale_P36_facts"):
        raise StructuralRegressionError(f"p36_carryover_forbidden:{label}")
    if any(token in lowered for token in ("source", "document", "content", "ticker", "issuer")):
        raise StructuralRegressionError(f"reference_or_claim_forbidden:{label}")
    is_allowed_negative_marker = allow_p36_marker and value == "no_stale_P36_facts"
    if (
        not is_allowed_negative_marker
        and (any(character.isdigit() for character in value) or "%" in value or "rank" in lowered)
    ):
        raise StructuralRegressionError(f"numeric_or_ranking_content_forbidden:{label}")


def validate_sector_rows(
    rows: Sequence[Mapping[str, Any]], cases: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Validate the exact two content-free rows emitted for the configured cases."""
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise StructuralRegressionError("sector_rows_list_required")
    expected = {str(case["case_key"]): case for case in cases}
    row_keys = tuple(row.get("case_key") if isinstance(row, Mapping) else None for row in rows)
    if row_keys != EXPECTED_CASE_KEYS:
        raise StructuralRegressionError("sector_rows_do_not_match_configured_cases")

    normalized: list[dict[str, Any]] = []
    for raw_row in rows:
        row = _mapping(raw_row, "sector_row")
        unexpected = set(row) - ROW_KEYS
        forbidden = sorted(key for key in unexpected if isinstance(key, str) and _forbidden_row_key(key))
        if forbidden:
            raise StructuralRegressionError(f"forbidden_sector_row_field:{forbidden[0]}")
        if set(row) != ROW_KEYS:
            raise StructuralRegressionError("sector_row_shape_invalid")
        case_key = row["case_key"]
        if not isinstance(case_key, str) or case_key not in expected:
            raise StructuralRegressionError("sector_row_case_invalid")
        case = expected[case_key]

        _ensure_content_free(row["case_key"], f"{case_key}.case_key")
        _ensure_content_free(row["status"], f"{case_key}.status")
        _ensure_content_free(row["artifact_scope"], f"{case_key}.artifact_scope")
        _ensure_content_free(row["sector_research_validity"], f"{case_key}.sector_research_validity")
        _ensure_content_free(row["required_structural_roles"], f"{case_key}.roles")
        _ensure_content_free(
            row["required_observations"],
            f"{case_key}.observations",
            allow_p36_marker=True,
        )
        _ensure_content_free(row["typed_gaps"], f"{case_key}.typed_gaps")
        if row["status"] != STRUCTURAL_STATUS:
            raise StructuralRegressionError(f"sector_row_status_invalid:{case_key}")
        if row["artifact_scope"] != "fixture_shadow_internal_only":
            raise StructuralRegressionError(f"sector_row_scope_invalid:{case_key}")
        if row["sector_research_validity"] != "not_claimed":
            raise StructuralRegressionError(f"sector_research_validity_claimed:{case_key}")
        if row["required_structural_roles"] != case["required_structural_roles"]:
            raise StructuralRegressionError(f"required_structural_roles_invalid:{case_key}")
        if row["required_observations"] != case["required_observations"]:
            raise StructuralRegressionError(f"required_observations_invalid:{case_key}")
        if row["typed_gaps"] != [
            "typed_gap:no_sector_evidence_or_claims_present",
            "typed_gap:structural_roles_only",
        ]:
            raise StructuralRegressionError(f"typed_gaps_invalid:{case_key}")

        normalized.append(dict(row))
    return normalized


def _zero_boundary_counts() -> dict[str, int]:
    return {key: 0 for key in ZERO_BOUNDARY_KEYS}


def build_result(
    *, profile_path: Path, sector_rows: Sequence[Mapping[str, Any]] | None = None
) -> dict[str, Any]:
    """Build one deterministic P07.2 result without executing research or runtime."""
    profile_path = profile_path.resolve()
    profile, cases = load_profile(profile_path)
    rows = validate_sector_rows(
        default_sector_rows(cases) if sector_rows is None else sector_rows,
        cases,
    )
    payload = {
        "schema_version": SCRIPT_SCHEMA,
        "result_id": "REL-PROD-001:VT4:P07.2:saas-us-banks-structural-regression",
        "status": RESULT_STATUS,
        "release_id": "REL-PROD-001",
        "tranche_id": "VT4_P07_2_STRUCTURAL_ONLY_REGRESSION",
        "profile": {
            "schema_version": profile["schema_version"],
            "status": profile["status"],
            "file_sha256": sha256_bytes(profile_path.read_bytes()),
            "canonical_json_sha256": canonical_sha256(profile),
        },
        "authority": _validate_authority(profile),
        "structural_regression_status": STRUCTURAL_STATUS,
        "sector_research_validity": "not_claimed",
        "sector_rows": rows,
        "boundary_counts": _zero_boundary_counts(),
        "operational_execution": "not_run",
        "rg1_vertical_path": "not_run_separate_authority_required",
        "release_admission": "not_granted",
    }
    return {**payload, "result_sha256": canonical_sha256(payload)}


def write_result(path: Path, result: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(dict(result)) + b"\n")


def verify_result(*, profile_path: Path, result_path: Path) -> dict[str, str]:
    """Fail closed when result bytes, profile bytes, or the canonical digest drift."""
    try:
        raw = result_path.read_bytes()
        result = _mapping(json.loads(raw.decode("utf-8")), "structural_regression_result")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StructuralRegressionError(f"result_read_failed:{result_path}") from exc
    if raw != canonical_json_bytes(result) + b"\n":
        raise StructuralRegressionError("result_not_canonical_json")
    if result.get("result_sha256") != canonical_sha256(
        {key: value for key, value in result.items() if key != "result_sha256"}
    ):
        raise StructuralRegressionError("result_digest_invalid")
    expected = build_result(profile_path=profile_path)
    if dict(result) != expected:
        raise StructuralRegressionError("result_or_profile_drift")
    return {"status": "pass", "result_sha256": str(result["result_sha256"])}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    for mode in ("run", "verify"):
        command = commands.add_parser(mode)
        command.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
        command.add_argument(
            "--output" if mode == "run" else "--result",
            dest="result_path",
            type=Path,
            required=True,
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.mode == "run":
            result = build_result(profile_path=args.profile)
            write_result(args.result_path, result)
            response: Mapping[str, Any] = {
                "status": "pass",
                "result_path": str(args.result_path),
                "result_sha256": result["result_sha256"],
            }
        else:
            response = verify_result(profile_path=args.profile, result_path=args.result_path)
    except StructuralRegressionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(canonical_json_bytes(dict(response)).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
