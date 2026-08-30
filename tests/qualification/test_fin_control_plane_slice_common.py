from pathlib import Path

import pytest

from scripts.qualification.fin_control_plane_slice_common import (
    create_run_directory,
    fixture_payload,
    inject_one_transient_failure,
    require_environment_variable_unset,
    require_exact_environment_path,
    sha256_text,
    canonical_json,
)


def test_fixture_digest_is_stable() -> None:
    first = sha256_text(canonical_json(fixture_payload()))
    second = sha256_text(canonical_json(fixture_payload()))
    assert first == second
    assert len(first) == 64


def test_transient_failure_is_injected_exactly_once(tmp_path: Path) -> None:
    marker = tmp_path / "failure.marker"
    try:
        inject_one_transient_failure(marker)
    except RuntimeError as error:
        assert str(error) == "QUALIFICATION_TRANSIENT_FAILURE_INJECTED"
    else:
        raise AssertionError("first attempt did not fail")
    inject_one_transient_failure(marker)


def test_create_run_directory_is_unique(tmp_path: Path) -> None:
    first = create_run_directory(tmp_path, "prefect")
    second = create_run_directory(tmp_path, "prefect")
    assert first != second
    assert first.is_dir()
    assert second.is_dir()


def test_framework_state_path_must_match_qualification_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = tmp_path / "state" / "dagster"
    monkeypatch.delenv("DAGSTER_HOME", raising=False)
    with pytest.raises(RuntimeError, match="must be set"):
        require_exact_environment_path("DAGSTER_HOME", expected)

    monkeypatch.setenv("DAGSTER_HOME", str(tmp_path / "elsewhere"))
    with pytest.raises(RuntimeError, match="must resolve"):
        require_exact_environment_path("DAGSTER_HOME", expected)

    monkeypatch.setenv("DAGSTER_HOME", str(expected))
    assert require_exact_environment_path("DAGSTER_HOME", expected) == expected.resolve()

    prefect_home = tmp_path / "state" / "prefect"
    memo_store = prefect_home / "memo_store.toml"
    monkeypatch.setenv("PREFECT_SERVER_MEMO_STORE_PATH", str(prefect_home))
    with pytest.raises(RuntimeError, match="must resolve"):
        require_exact_environment_path("PREFECT_SERVER_MEMO_STORE_PATH", memo_store)

    monkeypatch.setenv("PREFECT_SERVER_MEMO_STORE_PATH", str(memo_store))
    assert (
        require_exact_environment_path("PREFECT_SERVER_MEMO_STORE_PATH", memo_store)
        == memo_store.resolve()
    )

    monkeypatch.setenv("PREFECT_API_URL", "https://example.invalid")
    with pytest.raises(RuntimeError, match="must be unset"):
        require_environment_variable_unset("PREFECT_API_URL")
    monkeypatch.delenv("PREFECT_API_URL")
    require_environment_variable_unset("PREFECT_API_URL")
