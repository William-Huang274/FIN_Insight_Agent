from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from financial_facts import (
    CompanyFactMartPolicy,
    CompanyFactObservation,
    FactLookup,
    MetricDefinition,
    execute_fact_lookup,
    write_company_fact_mart,
)


EXPECTED_BEFORE_VALUE = "40000000000"
EXPECTED_AFTER_VALUE = "43842000000"
PRODUCER = "https://github.com/William-Huang274/FIN_Insight_Agent"

# These values mirror the semantics of the existing DELL PIT unit-test fixture.
# They are deterministic qualification data, not a replay of live SEC bytes or
# proof that the placeholder source metadata is authentic.


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_run_directory(root: Path, engine: str) -> Path:
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    run_directory = root / "artifacts" / engine / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    return run_directory


def require_exact_environment_path(variable: str, expected_path: Path) -> Path:
    """Fail closed when a framework state path can escape the qualification root."""

    raw_value = os.environ.get(variable)
    if not raw_value:
        raise RuntimeError(f"{variable} must be set for qualification")
    actual_path = Path(raw_value).expanduser().resolve()
    resolved_expected = expected_path.resolve()
    if actual_path != resolved_expected:
        raise RuntimeError(
            f"{variable} must resolve to {resolved_expected}; got {actual_path}"
        )
    return actual_path


def require_environment_variable_unset(variable: str) -> None:
    """Reject external service/database overrides during an isolated qualification run."""

    if os.environ.get(variable):
        raise RuntimeError(f"{variable} must be unset for isolated qualification")


def inject_one_transient_failure(marker_path: Path) -> None:
    if marker_path.exists():
        return
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text("first-attempt failure injected\n", encoding="utf-8")
    raise RuntimeError("QUALIFICATION_TRANSIENT_FAILURE_INJECTED")


def _metric() -> MetricDefinition:
    return MetricDefinition(
        metric_id="revenue",
        unit_family="currency",
        concepts=(("us-gaap", "revenue"),),
        allowed_units=("USD",),
        formula=None,
    )


def _observation(
    observation_id: str,
    value: str,
    *,
    accepted_at: str,
    accession: str,
) -> CompanyFactObservation:
    return CompanyFactObservation(
        observation_id=observation_id,
        ticker="DELL",
        cik="0001571996",
        legal_name="Dell Technologies Inc.",
        metric_id="revenue",
        unit_family="currency",
        taxonomy="us-gaap",
        concept="revenue",
        concept_priority=0,
        value_decimal=value,
        unit="USD",
        period_start="2026-01-31",
        period_end="2026-05-01",
        duration_days=91,
        period_role="quarter_discrete",
        fiscal_year=2027,
        fiscal_period="Q1",
        reported_fiscal_year=2027,
        reported_fiscal_period="Q1",
        form="10-Q",
        accession_number=accession,
        filed_at=accepted_at[:10],
        accepted_at=accepted_at,
        frame=None,
        primary_document="dell-20260501.htm",
        citation_url="https://www.sec.gov/Archives/example",
        companyfacts_ref="capture/companyfacts.json",
        companyfacts_sha256="a" * 64,
        submissions_ref="capture/submissions.json",
        submissions_sha256="b" * 64,
        captured_at="2026-08-06T03:51:44+00:00",
    )


def _lookup(research_as_of: str) -> FactLookup:
    return FactLookup(
        fact_request_id=f"QUALIFICATION::DELL::revenue::{research_as_of}",
        ticker="DELL",
        metric_id="revenue",
        research_as_of=research_as_of,
        period={
            "start_date": "2026-01-31",
            "end_date": "2026-05-01",
            "fiscal_years": [2027],
        },
        granularity="quarter_discrete",
        requested_unit="reported_source_unit",
    )


def fixture_payload() -> dict[str, Any]:
    return {
        "case": "DELL",
        "metric": "revenue",
        "period_start": "2026-01-31",
        "period_end": "2026-05-01",
        "unit": "USD",
        "observations": [
            {
                "id": "OBS-OLD",
                "value": EXPECTED_BEFORE_VALUE,
                "accepted_at": "2026-05-20T20:00:00+00:00",
                "accession": "0001571996-26-000020",
            },
            {
                "id": "OBS-LATEST",
                "value": EXPECTED_AFTER_VALUE,
                "accepted_at": "2026-06-09T20:11:41+00:00",
                "accession": "0001571996-26-000030",
            },
        ],
    }


def emit_lineage_event(
    client: Any,
    *,
    state: Any,
    lineage_run_id: str,
    engine: str,
    input_digest: str,
    output_digest: str | None,
) -> None:
    from openlineage.client.run import Dataset, Job, Run, RunEvent

    outputs = []
    if output_digest is not None:
        outputs.append(Dataset(namespace="fin-qualification", name=f"result:{output_digest}"))
    client.emit(
        RunEvent(
            eventType=state,
            eventTime=datetime.now(timezone.utc).isoformat(),
            run=Run(runId=lineage_run_id),
            job=Job(namespace="fin-qualification", name=f"{engine}-financial-fact-slice"),
            producer=PRODUCER,
            inputs=[Dataset(namespace="fin-qualification", name=f"fixture:{input_digest}")],
            outputs=outputs,
        )
    )


def execute_observed_fin_slice(
    *,
    engine: str,
    run_directory: Path,
    mlflow_tracking_uri: str,
    retry_count: int,
) -> dict[str, Any]:
    import mlflow
    from mlflow import MlflowClient
    from openlineage.client import OpenLineageClient
    from openlineage.client.run import RunState
    from openlineage.client.transport import FileTransport
    from openlineage.client.transport.file import FileConfig
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    fixture = fixture_payload()
    input_digest = sha256_text(canonical_json(fixture))
    lineage_path = run_directory / "openlineage-events.jsonl"
    lineage_client = OpenLineageClient(
        transport=FileTransport(FileConfig(log_file_path=str(lineage_path), append=True))
    )
    lineage_run_id = str(uuid4())
    emit_lineage_event(
        lineage_client,
        state=RunState.START,
        lineage_run_id=lineage_run_id,
        engine=engine,
        input_digest=input_digest,
        output_digest=None,
    )

    exporter = InMemorySpanExporter()
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": "fin-control-plane-qualification",
                "fin.workflow.engine": engine,
            }
        )
    )
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("fin.qualification.control_plane")

    try:
        with tracer.start_as_current_span("fin.control-plane-slice") as root_span:
            root_span.set_attribute("fin.case", "DELL")
            root_span.set_attribute("fin.input.sha256", input_digest)
            root_span.set_attribute("fin.retry_count", retry_count)

            metric = _metric()
            observations = (
                _observation(
                    "OBS-OLD",
                    EXPECTED_BEFORE_VALUE,
                    accepted_at="2026-05-20T20:00:00+00:00",
                    accession="0001571996-26-000020",
                ),
                _observation(
                    "OBS-LATEST",
                    EXPECTED_AFTER_VALUE,
                    accepted_at="2026-06-09T20:11:41+00:00",
                    accession="0001571996-26-000030",
                ),
            )
            policy = CompanyFactMartPolicy(
                recorded_at="2026-08-13",
                research_as_of="2026-08-06",
                minimum_period_end="2022-01-01",
                allowed_forms=("10-K", "10-Q"),
                sources=(),
                metrics=(metric,),
                acceptance_qrels=(),
                authority={
                    "raw_capture_digest_required": True,
                    "accepted_at_required": True,
                    "preserve_all_vintages": True,
                    "fact_signal_context_mixed_table_forbidden": True,
                    "typed_conflict_fails_closed": True,
                },
            )
            sqlite_path = run_directory / "facts.sqlite"
            with tracer.start_as_current_span("fin.fact-mart.write"):
                write_company_fact_mart(
                    sqlite_path,
                    observations=observations,
                    metrics=(metric,),
                    policy=policy,
                )
            with tracer.start_as_current_span("fin.fact-mart.lookup-before"):
                before = execute_fact_lookup(sqlite_path, _lookup("2026-06-01"))
            with tracer.start_as_current_span("fin.fact-mart.lookup-after"):
                after = execute_fact_lookup(sqlite_path, _lookup("2026-08-06"))

            if before.status != "resolved" or before.facts[0].value_decimal != EXPECTED_BEFORE_VALUE:
                raise AssertionError("PIT lookup before latest vintage changed")
            if after.status != "resolved" or after.facts[0].value_decimal != EXPECTED_AFTER_VALUE:
                raise AssertionError("PIT lookup after latest vintage changed")
            if len(after.facts[0].source_digests) != 2:
                raise AssertionError("vintage source lineage was not preserved")

            business_result = {
                "engine": engine,
                "case": "DELL",
                "metric": "revenue",
                "input_sha256": input_digest,
                "before": asdict(before),
                "after": asdict(after),
                "retry_count": retry_count,
            }
            business_result["result_sha256"] = sha256_text(canonical_json(business_result))

        provider.force_flush()
        spans = exporter.get_finished_spans()
        span_summary = [
            {
                "name": span.name,
                "status": span.status.status_code.name,
                "attributes": dict(span.attributes or {}),
            }
            for span in spans
        ]
        business_result["otel_span_count"] = len(span_summary)
        business_result["otel_span_names"] = sorted(span["name"] for span in span_summary)

        result_path = run_directory / "result.json"
        result_path.write_text(
            json.dumps(business_result, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        span_path = run_directory / "otel-spans.json"
        span_path.write_text(
            json.dumps(span_summary, ensure_ascii=False, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )

        mlflow.set_tracking_uri(mlflow_tracking_uri)
        experiment_name = "fin-control-plane-qualification"
        mlflow.set_experiment(experiment_name)
        with mlflow.start_run(run_name=f"{engine}-{run_directory.name}") as active_run:
            mlflow.log_params(
                {
                    "engine": engine,
                    "case": "DELL",
                    "metric": "revenue",
                    "input_sha256": input_digest,
                }
            )
            mlflow.log_metrics(
                {
                    "retry_count": float(retry_count),
                    "fact_count": float(len(after.facts)),
                    "otel_span_count": float(len(span_summary)),
                }
            )
            mlflow.log_artifact(str(result_path), artifact_path="result")
            mlflow.log_artifact(str(span_path), artifact_path="telemetry")
            mlflow_run_id = active_run.info.run_id

        fetched = MlflowClient(tracking_uri=mlflow_tracking_uri).get_run(mlflow_run_id)
        if fetched.data.params.get("input_sha256") != input_digest:
            raise AssertionError("MLflow readback did not preserve the input digest")
        business_result["mlflow_run_id"] = mlflow_run_id
        business_result["mlflow_readback_status"] = fetched.info.status

        emit_lineage_event(
            lineage_client,
            state=RunState.COMPLETE,
            lineage_run_id=lineage_run_id,
            engine=engine,
            input_digest=input_digest,
            output_digest=business_result["result_sha256"],
        )
        lineage_events = [
            json.loads(line)
            for line in lineage_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if [event["eventType"] for event in lineage_events] != ["START", "COMPLETE"]:
            raise AssertionError("OpenLineage did not persist START/COMPLETE")
        if len({event["run"]["runId"] for event in lineage_events}) != 1:
            raise AssertionError("OpenLineage START/COMPLETE run IDs diverged")
        business_result["openlineage_event_count"] = len(lineage_events)
        business_result["openlineage_run_id"] = lineage_run_id

        final_path = run_directory / "qualification-result.json"
        final_path.write_text(
            json.dumps(business_result, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return business_result
    except Exception:
        emit_lineage_event(
            lineage_client,
            state=RunState.FAIL,
            lineage_run_id=lineage_run_id,
            engine=engine,
            input_digest=input_digest,
            output_digest=None,
        )
        raise
    finally:
        provider.shutdown()
