from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from sec_agent.hermetic_test_runner import (
    HermeticTestRunnerError,
    _environment_root_fingerprint,
    _load_semantic_parity_contract,
    _python_environment_inventory,
    _semantic_text_projection,
    _typed_environment_root_rows,
)
from sec_agent.test_resource import repository_test_resource


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_REF = (
    "configs/runtime/fin_ia_0_1_3_typed_environment_semantic_parity_v1_0.json"
)
RUNTIME_RESOURCE_BUNDLE_ID = "runtime_resource_registry"


def _manifest(ref: str = CONTRACT_REF) -> dict[str, Any]:
    return {"hermetic_package_policy": {"semantic_parity_contract_ref": ref}}


def _contract() -> dict[str, Any]:
    contract, ref, digest = _load_semantic_parity_contract(ROOT, _manifest())
    assert contract is not None
    assert ref == CONTRACT_REF
    assert digest and len(digest) == 64
    return contract


def _runtime_rows(contract: dict[str, Any], variant: str) -> list[dict[str, Any]]:
    drive = "C" if variant == "a" else "D"
    values: dict[str, str | list[str]] = {
        "disposable_package_root": f"{drive}:\\Proof\\{variant}\\package",
        "disposable_repository_root": f"{drive}:\\Proof\\{variant}\\repository",
        "disposable_temporary_root": f"{drive}:\\Proof\\{variant}",
        "sys_prefix": f"{drive}:\\Python{variant}",
        "sys_base_prefix": f"{drive}:\\PythonBase{variant}",
        "purelib_root": f"{drive}:\\Python{variant}\\Lib\\site-packages",
        "platlib_root": f"{drive}:\\Python{variant}\\Lib\\site-packages",
        "installed_distribution_roots": [
            f"{drive}:\\Python{variant}\\Lib\\site-packages"
        ],
    }
    rows: list[dict[str, Any]] = []
    for contract_row in contract["normalization"]["allowed_roots"]:
        root_id = contract_row["root_id"]
        absolute_path = values[root_id]
        rows.append(
            {
                "root_id": root_id,
                "role": contract_row["role"],
                "absolute_path": absolute_path,
                "projection_token": contract_row["projection_token"],
                "source": contract_row["source"],
                "digest_or_environment_fingerprint": (
                    _environment_root_fingerprint(root_id, absolute_path)
                ),
            }
        )
    return rows


def test_typed_contract_declares_all_eight_roots_and_diagnostic_fields() -> None:
    contract = _contract()
    assert [
        row["root_id"] for row in contract["normalization"]["allowed_roots"]
    ] == [
        "disposable_package_root",
        "disposable_repository_root",
        "disposable_temporary_root",
        "sys_prefix",
        "sys_base_prefix",
        "purelib_root",
        "platlib_root",
        "installed_distribution_roots",
    ]
    assert contract["semantic_projection"]["normalized_content_fields"] == [
        "test.stdout",
        "test.stderr",
        "test.detail",
        "collection_errors",
        "process_stdout",
        "process_stderr",
    ]
    assert contract["semantic_projection"][
        "business_and_contract_fields_are_never_normalized"
    ] is True


def test_equivalent_windows_drive_slash_site_package_and_prefix_paths_converge() -> None:
    contract = _contract()
    rows_a = _runtime_rows(contract, "a")
    rows_b = _runtime_rows(contract, "b")
    raw_a = (
        'File "c:/Proof/a/repository/tests/sample.py", line 9\n'
        "C:\\Pythona\\Lib\\site-packages\\pydantic\\main.py\n"
        "C:\\PythonBasea\\Lib\\traceback.py"
    ).encode("utf-8")
    raw_b = (
        'File "d:\\Proof\\b\\repository\\tests\\sample.py", line 9\n'
        "D:/Pythonb/Lib/site-packages/pydantic/main.py\n"
        "D:/PythonBaseb/Lib/traceback.py"
    ).encode("utf-8")
    assert hashlib.sha256(raw_a).hexdigest() != hashlib.sha256(raw_b).hexdigest()
    projected_a = _semantic_text_projection(
        raw_a,
        roots=rows_a,
        contract=contract,
    )
    projected_b = _semantic_text_projection(
        raw_b,
        roots=rows_b,
        contract=contract,
    )
    assert projected_a["normalization_valid"] is True
    assert projected_b["normalization_valid"] is True
    assert projected_a["semantic_sha256"] == projected_b["semantic_sha256"]


def test_unknown_absolute_path_and_prefix_collision_fail_closed() -> None:
    contract = _contract()
    rows = _runtime_rows(contract, "a")
    for value in (
        b'File "Z:\\Outside\\module.py", line 1',
        b'File "C:\\Proof\\a2\\repository\\module.py", line 1',
    ):
        projected = _semantic_text_projection(
            value,
            roots=rows,
            contract=contract,
        )
        assert projected["normalization_valid"] is False
        assert projected["unknown_absolute_path_count"] == 1


def test_relative_resource_path_and_business_field_are_not_rewritten() -> None:
    contract = _contract()
    rows = _runtime_rows(contract, "a")
    relative = b"configs/runtime/point01_feature_flags_v1_0.json"
    projected = _semantic_text_projection(
        relative,
        roots=rows,
        contract=contract,
    )
    assert projected["normalization_valid"] is True
    assert projected["semantic_sha256"] == hashlib.sha256(relative).hexdigest()

    payload = {
        "business_values": {"segment_label": "C:\\Revenue\\2026"},
        "process_stderr": b'File "C:\\Proof\\a\\repository\\x.py"',
    }
    before = deepcopy(payload["business_values"])
    _semantic_text_projection(
        payload["process_stderr"],
        roots=rows,
        contract=contract,
    )
    assert payload["business_values"] == before


def test_uri_is_classified_before_filesystem_path_detection() -> None:
    contract = _contract()
    rows = _runtime_rows(contract, "a")
    value = b"fixture://case/evidence/quarterly/report.json"
    projected = _semantic_text_projection(
        value,
        roots=rows,
        contract=contract,
    )
    assert projected["normalization_valid"] is True
    assert projected["unknown_absolute_path_count"] == 0
    assert projected["semantic_sha256"] == hashlib.sha256(value).hexdigest()


def test_escaped_windows_repr_normalizes_only_in_semantic_projection() -> None:
    contract = _contract()
    rows_a = _runtime_rows(contract, "a")
    rows_b = _runtime_rows(contract, "b")
    raw_a = b'File "C:\\\\Proof\\\\a\\\\repository\\\\tests\\\\sample.py"'
    raw_b = b'File "D:/Proof/b/repository/tests/sample.py"'
    projected_a = _semantic_text_projection(
        raw_a,
        roots=rows_a,
        contract=contract,
    )
    projected_b = _semantic_text_projection(
        raw_b,
        roots=rows_b,
        contract=contract,
    )
    assert hashlib.sha256(raw_a).hexdigest() != hashlib.sha256(raw_b).hexdigest()
    assert projected_a["normalization_valid"] is True
    assert projected_a["semantic_sha256"] == projected_b["semantic_sha256"]


def test_unknown_escaped_windows_repr_still_fails_closed() -> None:
    projected = _semantic_text_projection(
        b'File "Z:\\\\Outside\\\\module.py"',
        roots=_runtime_rows(_contract(), "a"),
        contract=_contract(),
    )
    assert projected["normalization_valid"] is False
    assert projected["unknown_absolute_path_count"] == 1


@pytest.mark.parametrize(
    "mutation",
    ["missing", "duplicate", "fingerprint", "role"],
)
def test_typed_runtime_root_mutations_fail_closed(mutation: str) -> None:
    contract = _contract()
    rows = _runtime_rows(contract, "a")
    if mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows.append(deepcopy(rows[0]))
    elif mutation == "fingerprint":
        rows[0]["digest_or_environment_fingerprint"] = "0" * 64
    else:
        rows[0]["role"] = "untyped_root"
    with pytest.raises(HermeticTestRunnerError):
        _semantic_text_projection(b"diagnostic", roots=rows, contract=contract)


def test_host_environment_is_frozen_into_complete_typed_rows() -> None:
    environment = _python_environment_inventory()
    rows = _typed_environment_root_rows(
        package_root=ROOT / "package",
        runtime_root=ROOT / "runtime",
        disposable_parent=ROOT / "temporary",
        python_environment=environment,
    )
    assert len(rows) == 8
    assert {row["root_id"] for row in rows} == {
        "disposable_package_root",
        "disposable_repository_root",
        "disposable_temporary_root",
        "sys_prefix",
        "sys_base_prefix",
        "purelib_root",
        "platlib_root",
        "installed_distribution_roots",
    }
    assert all(len(row["digest_or_environment_fingerprint"]) == 64 for row in rows)


def test_contract_root_or_field_mutation_is_rejected(tmp_path: Path) -> None:
    contract = json.loads(
        repository_test_resource(
            ROOT,
            RUNTIME_RESOURCE_BUNDLE_ID,
            CONTRACT_REF,
        ).read_text(encoding="utf-8")
    )
    contract["normalization"]["allowed_roots"].pop()
    target = tmp_path / "typed.json"
    target.write_text(json.dumps(contract), encoding="utf-8")
    with pytest.raises(HermeticTestRunnerError) as failure:
        _load_semantic_parity_contract(tmp_path, _manifest("typed.json"))
    assert failure.value.code == "semantic_parity_typed_roots_invalid"
