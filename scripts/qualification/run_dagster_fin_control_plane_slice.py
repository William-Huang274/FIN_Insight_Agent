from __future__ import annotations

import argparse
import json
from pathlib import Path

from dagster import DagsterInstance, RetryPolicy, job, op

from scripts.qualification.fin_control_plane_slice_common import (
    create_run_directory,
    execute_observed_fin_slice,
    inject_one_transient_failure,
    require_exact_environment_path,
)


@op(
    config_schema={"run_directory": str, "mlflow_tracking_uri": str},
    retry_policy=RetryPolicy(max_retries=1, delay=0),
)
def execute_slice(context) -> dict[str, object]:
    run_directory = Path(context.op_config["run_directory"])
    inject_one_transient_failure(run_directory / "transient-failure.marker")
    return execute_observed_fin_slice(
        engine="dagster",
        run_directory=run_directory,
        mlflow_tracking_uri=context.op_config["mlflow_tracking_uri"],
        retry_count=1,
    )


@job(name="fin_control_plane_qualification_dagster")
def qualification_job() -> None:
    execute_slice()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qualification-root", type=Path, required=True)
    parser.add_argument("--mlflow-tracking-uri", required=True)
    args = parser.parse_args()

    instance_directory = args.qualification_root / "state" / "dagster"
    require_exact_environment_path("DAGSTER_HOME", instance_directory)
    instance_directory.mkdir(parents=True, exist_ok=True)
    run_directory = create_run_directory(args.qualification_root, "dagster")
    with DagsterInstance.get() as instance:
        result = qualification_job.execute_in_process(
            instance=instance,
            run_config={
                "ops": {
                    "execute_slice": {
                        "config": {
                            "run_directory": str(run_directory),
                            "mlflow_tracking_uri": args.mlflow_tracking_uri,
                        }
                    }
                }
            },
        )
        if not result.success:
            raise RuntimeError("Dagster qualification job did not succeed")
        business_result = result.output_for_node("execute_slice")
        dagster_run_id = result.run_id

    payload = {
        "engine": "dagster",
        "dagster_run_id": dagster_run_id,
        "job_success": result.success,
        "run_directory": str(run_directory),
        "result": business_result,
    }
    summary_path = run_directory / "dagster-summary.json"
    summary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
