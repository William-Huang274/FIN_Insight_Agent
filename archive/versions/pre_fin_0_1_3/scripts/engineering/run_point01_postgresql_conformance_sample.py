from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m1_postgresql_conformance_sample_result_v1_0.json"

SQL = """
create table research_cases (
  tenant_id text not null,
  project_id text not null,
  case_id text not null,
  primary key (tenant_id, project_id, case_id)
);
create table actor_snapshots (
  tenant_id text not null,
  project_id text not null,
  actor_snapshot_id text not null,
  primary key (tenant_id, project_id, actor_snapshot_id),
  unique (actor_snapshot_id)
);
create table work_units (
  tenant_id text not null,
  project_id text not null,
  case_id text not null,
  work_unit_id text not null,
  work_unit_version integer not null check (work_unit_version >= 1),
  state_version integer not null check (state_version >= 0),
  input_head_digest text not null,
  primary key (tenant_id, project_id, case_id, work_unit_id, work_unit_version, state_version),
  foreign key (tenant_id, project_id, case_id) references research_cases
);
create table attempts (
  tenant_id text not null,
  project_id text not null,
  case_id text not null,
  attempt_id text not null,
  work_unit_id text not null,
  work_unit_version integer not null,
  work_unit_state_version integer not null,
  input_head_digest text not null,
  primary key (tenant_id, project_id, case_id, attempt_id),
  foreign key (tenant_id, project_id, case_id, work_unit_id, work_unit_version, work_unit_state_version)
    references work_units (tenant_id, project_id, case_id, work_unit_id, work_unit_version, state_version)
);
create table artifact_versions (
  tenant_id text not null,
  project_id text not null,
  case_id text not null,
  artifact_version_id text primary key,
  producer_attempt_id text not null,
  input_refs_digest text not null
);
create table events (
  event_id text primary key,
  actor_snapshot_ref text not null,
  work_unit_id text,
  attempt_id text,
  foreign key (actor_snapshot_ref) references actor_snapshots (actor_snapshot_id)
);
create table outbox (
  event_id text primary key references events (event_id),
  delivery_status text not null
);
create table active_legacy_bindings (
  tenant_id text not null,
  project_id text not null,
  normalized_identity_digest text not null,
  binding_id text not null,
  active boolean not null,
  primary key (tenant_id, project_id, binding_id)
);
create unique index active_legacy_identity_once
  on active_legacy_bindings (tenant_id, project_id, normalized_identity_digest)
  where active;

insert into research_cases values ('tenant', 'project', 'case');
insert into actor_snapshots values ('tenant', 'project', 'actor');
insert into work_units values ('tenant', 'project', 'case', 'wu', 1, 0, 'head');
insert into attempts values ('tenant', 'project', 'case', 'attempt', 'wu', 1, 0, 'head');
insert into artifact_versions values ('tenant', 'project', 'case', 'artifact:v1', 'attempt', 'head');
begin;
insert into events values ('event-1', 'actor', 'wu', 'attempt');
insert into outbox values ('event-1', 'pending');
commit;
insert into active_legacy_bindings values ('tenant', 'project', 'legacy-digest', 'binding-1', true);
do $$ begin
  insert into active_legacy_bindings values ('tenant', 'project', 'legacy-digest', 'binding-2', true);
  raise exception 'active_binding_unique_constraint_not_enforced';
exception when unique_violation then
  null;
end $$;
do $$ begin
  insert into events values ('event-missing-actor', 'actor-missing', null, null);
  raise exception 'event_actor_foreign_key_not_enforced';
exception when foreign_key_violation then
  null;
end $$;
select 'postgres_conformance_pass' as status,
       (select count(*) from events event left join outbox outbox on outbox.event_id = event.event_id where outbox.event_id is null) as missing_outbox_count,
       (select count(*) from artifact_versions artifact join attempts attempt on attempt.attempt_id = artifact.producer_attempt_id where artifact.input_refs_digest = attempt.input_head_digest) as digest_matched_artifact_count;
"""


def _run(arguments: list[str], *, input_text: str | None = None, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *arguments],
        cwd=ROOT,
        text=True,
        input=input_text,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ephemeral Point 01 PostgreSQL conformance sample.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    container = f"point01-pg-{uuid4().hex[:12]}"
    postgres_secret = f"p{uuid4().hex}"
    result: dict[str, object] = {
        "result_version": "finsight_point01_m1_postgresql_conformance_sample_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "container_engine": "docker",
        "image": "postgres:16-alpine",
        "container_persisted": False,
        "status": "fail",
    }
    try:
        started = _run([
            "run", "--rm", "-d", "--name", container,
            "-e", f"POSTGRES_PASSWORD={postgres_secret}", "-e", "POSTGRES_DB=point01",
            "postgres:16-alpine",
        ])
        if started.returncode:
            raise RuntimeError(started.stderr.strip() or started.stdout.strip() or "docker_postgres_start_failed")
        for _ in range(30):
            ready = _run(
                ["exec", container, "psql", "-At", "-U", "postgres", "-d", "point01", "-c", "select 1"],
                timeout=30,
            )
            if ready.returncode == 0 and ready.stdout.strip() == "1":
                break
            time.sleep(1)
        else:
            raise RuntimeError("postgres_readiness_timeout")
        executed = _run(["exec", "-i", container, "psql", "-At", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "point01"], input_text=SQL)
        if executed.returncode:
            raise RuntimeError(executed.stderr.strip() or executed.stdout.strip() or "postgres_conformance_sql_failed")
        output = executed.stdout.strip()
        if "postgres_conformance_pass|0|1" not in output:
            raise RuntimeError(f"postgres_conformance_unexpected_output:{output}")
        result.update({"status": "pass", "sql_output": output[-2000:]})
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        _run(["rm", "-f", container], timeout=30)
    target = args.output if args.output.is_absolute() else ROOT / args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(target)}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
