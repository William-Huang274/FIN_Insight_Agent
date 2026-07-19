from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = (
    REPO_ROOT / "scripts" / "releases" / "run_fin_ia_0_1_vt4_structural_regressions.py"
)
PROFILE_PATH = (
    REPO_ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_vt4_p36_candidate_profile_v1_0.json"
)


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("vt4_structural_regressions", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REGRESSIONS = _module()


def _profile() -> dict[str, object]:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.write_bytes(REGRESSIONS.canonical_json_bytes(value) + b"\n")


def _profile_copy(tmp_path: Path) -> Path:
    path = tmp_path / "profile.json"
    _write_json(path, _profile())
    return path


def test_run_emits_both_content_free_structural_cases_and_zero_boundaries(tmp_path: Path) -> None:
    profile_path = _profile_copy(tmp_path)
    result_path = tmp_path / "result.json"

    completed = subprocess.run(
        [
            "python",
            str(SCRIPT_PATH),
            "run",
            "--profile",
            str(profile_path),
            "--output",
            str(result_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["status"] == REGRESSIONS.RESULT_STATUS
    assert [row["case_key"] for row in result["sector_rows"]] == ["saas", "us_banks"]
    assert all(row["sector_research_validity"] == "not_claimed" for row in result["sector_rows"])
    assert all(row["typed_gaps"] for row in result["sector_rows"])
    assert all(row["required_structural_roles"] for row in result["sector_rows"])
    assert result["boundary_counts"] == {
        key: 0 for key in REGRESSIONS.ZERO_BOUNDARY_KEYS
    }
    assert result["operational_execution"] == "not_run"
    assert result["rg1_vertical_path"] == "not_run_separate_authority_required"
    assert result["release_admission"] == "not_granted"


def test_result_is_deterministic_and_verifyable(tmp_path: Path) -> None:
    profile_path = _profile_copy(tmp_path)
    first = REGRESSIONS.build_result(profile_path=profile_path)
    second = REGRESSIONS.build_result(profile_path=profile_path)
    result_path = tmp_path / "result.json"
    REGRESSIONS.write_result(result_path, first)

    assert first == second
    assert REGRESSIONS.verify_result(profile_path=profile_path, result_path=result_path) == {
        "status": "pass",
        "result_sha256": first["result_sha256"],
    }


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("p36_fact", "P36 fixture conclusion", "forbidden_sector_row_field:p36_fact"),
        ("numeric_value", 42, "forbidden_sector_row_field:numeric_value"),
        ("company_ranking", "first", "forbidden_sector_row_field:company_ranking"),
        ("source_ref", "issuer filing", "forbidden_sector_row_field:source_ref"),
        ("document_ref", "report", "forbidden_sector_row_field:document_ref"),
        ("ticker_claim", "NVDA", "forbidden_sector_row_field:ticker_claim"),
    ],
)
def test_forbidden_p36_numeric_ranking_and_reference_carryover_fails_closed(
    tmp_path: Path, field: str, value: object, error: str
) -> None:
    profile_path = _profile_copy(tmp_path)
    _, cases = REGRESSIONS.load_profile(profile_path)
    rows = REGRESSIONS.default_sector_rows(cases)
    rows[0][field] = value

    with pytest.raises(REGRESSIONS.StructuralRegressionError, match=error):
        REGRESSIONS.validate_sector_rows(rows, cases)


def test_p36_text_carryover_inside_a_permitted_field_fails_closed(tmp_path: Path) -> None:
    profile_path = _profile_copy(tmp_path)
    _, cases = REGRESSIONS.load_profile(profile_path)
    rows = REGRESSIONS.default_sector_rows(cases)
    rows[0]["typed_gaps"] = [
        "typed_gap:P36 fixture conclusion carried over",
        "typed_gap:structural_roles_only",
    ]

    with pytest.raises(REGRESSIONS.StructuralRegressionError, match="p36_carryover_forbidden:saas.typed_gaps"):
        REGRESSIONS.validate_sector_rows(rows, cases)


def test_verify_detects_result_tampering_and_profile_drift(tmp_path: Path) -> None:
    profile_path = _profile_copy(tmp_path)
    result_path = tmp_path / "result.json"
    result = REGRESSIONS.build_result(profile_path=profile_path)
    REGRESSIONS.write_result(result_path, result)

    tampered = copy.deepcopy(result)
    tampered["boundary_counts"]["network_calls"] = 1
    _write_json(result_path, tampered)
    with pytest.raises(REGRESSIONS.StructuralRegressionError, match="result_digest_invalid"):
        REGRESSIONS.verify_result(profile_path=profile_path, result_path=result_path)

    REGRESSIONS.write_result(result_path, result)
    profile = _profile()
    profile["tranche_id"] = "VT4_PROFILE_DRIFT"
    _write_json(profile_path, profile)
    with pytest.raises(REGRESSIONS.StructuralRegressionError, match="result_or_profile_drift"):
        REGRESSIONS.verify_result(profile_path=profile_path, result_path=result_path)
