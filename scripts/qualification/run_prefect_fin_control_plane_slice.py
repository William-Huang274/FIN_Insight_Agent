from __future__ import annotations

import argparse
import json
from pathlib import Path

from prefect import flow, task

from scripts.qualification.fin_control_plane_slice_common import (
    create_run_directory,
    execute_observed_fin_slice,
    inject_one_transient_failure,
    require_environment_variable_unset,
    require_exact_environment_path,
)


@task(retries=1, retry_delay_seconds=0, persist_result=False)
def execute_slice(run_directory: str, mlflow_tracking_uri: str) -> dict[str, object]:
    run_path = Path(run_directory)
    inject_one_transient_failure(run_path / "transient-failure.marker")
    return execute_observed_fin_slice(
        engine="prefect",
        run_directory=run_path,
        mlflow_tracking_uri=mlflow_tracking_uri,
        retry_count=1,
    )


@flow(
    name="fin-control-plane-qualification-prefect",
    log_prints=True,
    persist_result=False,
)
def qualification_flow(run_directory: str, mlflow_tracking_uri: str) -> dict[str, object]:
    return execute_slice(run_directory, mlflow_tracking_uri)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qualification-root", type=Path, required=True)
    parser.add_argument("--mlflow-tracking-uri", required=True)
    args = parser.parse_args()

    prefect_state = args.qualification_root / "state" / "prefect"
    require_exact_environment_path("PREFECT_HOME", prefect_state)
    require_exact_environment_path(
        "PREFECT_SERVER_MEMO_STORE_PATH", prefect_state / "memo_store.toml"
    )
    require_environment_variable_unset("PREFECT_API_URL")
    require_environment_variable_unset("PREFECT_SERVER_DATABASE_CONNECTION_URL")
    prefect_state.mkdir(parents=True, exist_ok=True)
    run_directory = create_run_directory(args.qualification_root, "prefect")
    state = qualification_flow(
        str(run_directory),
        args.mlflow_tracking_uri,
        return_state=True,
    )
    result = state.result()
    payload = {
        "engine": "prefect",
        "flow_run_id": str(state.state_details.flow_run_id),
        "flow_state": state.name,
        "run_directory": str(run_directory),
        "result": result,
    }
    summary_path = run_directory / "prefect-summary.json"
    summary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
