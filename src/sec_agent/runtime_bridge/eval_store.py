from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


EVAL_STORE_SCHEMA_VERSION = "finsight_eval_store_v0_2"
EVAL_TABLES = (
    "eval_case_registry",
    "eval_dataset_version",
    "eval_case_membership",
    "eval_run",
    "eval_case_result",
    "eval_node_result",
    "eval_metric_result",
    "eval_failure_event",
    "eval_annotation",
    "eval_gold_promotion",
    "eval_judge_run",
    "eval_dashboard_snapshot",
)


def migrate_eval_store(db_path: str | Path) -> dict[str, Any]:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        _create_schema(conn)
        _set_metadata(conn, "schema_version", EVAL_STORE_SCHEMA_VERSION)
        _set_metadata(conn, "schema_migration_id", "eval_store_v0_2")
    return {
        "schema_version": EVAL_STORE_SCHEMA_VERSION,
        "db_path": str(path.resolve()),
        "schema_objects": list(EVAL_TABLES),
        "storage_policy": "sql_backed_eval_source_jsonl_import_export_only_v0_1",
    }


def record_eval_case_result(db_path: str | Path, result: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(db_path)
    migrate_eval_store(path)
    run_id = _text(result.get("run_id"), "unknown_run")
    case_id = _text(result.get("case_id"), "unknown_case")
    eval_id = _text(result.get("eval_id"), "runtime_bridge_eval")
    now = _now()
    with _connect(path) as conn:
        conn.execute(
            """
            insert or replace into eval_run (
                eval_id, run_id, case_family, status, score, code_commit,
                data_snapshot_id, model_profile, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                eval_id,
                run_id,
                _text(result.get("case_family"), ""),
                _text(result.get("status"), "unknown"),
                float(result.get("score") or 0.0),
                _text(result.get("code_commit"), ""),
                _text(result.get("data_snapshot_id"), ""),
                _text(result.get("model_profile"), ""),
                _json(result),
                now,
            ),
        )
        conn.execute(
            """
            insert or replace into eval_case_result (
                eval_id, case_id, run_id, status, score, data_snapshot_id,
                criteria_version, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                eval_id,
                case_id,
                run_id,
                _text(result.get("status"), "unknown"),
                float(result.get("score") or 0.0),
                _text(result.get("data_snapshot_id"), ""),
                _text(result.get("criteria_version"), ""),
                _json(result),
                now,
            ),
        )
        for node in result.get("node_results") or []:
            if isinstance(node, Mapping):
                conn.execute(
                    """
                    insert into eval_node_result (
                        eval_id, case_id, run_id, node, status, metric_count, payload_json, created_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        eval_id,
                        case_id,
                        run_id,
                        _text(node.get("node"), ""),
                        _text(node.get("status"), "unknown"),
                        int(node.get("metric_count") or len(node.get("metrics") or [])),
                        _json(node),
                        now,
                    ),
                )
                for metric in node.get("metrics") or []:
                    if isinstance(metric, Mapping):
                        conn.execute(
                            """
                            insert into eval_metric_result (
                                eval_id, case_id, run_id, metric_name, metric_value,
                                status, payload_json, created_at
                            ) values (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                eval_id,
                                case_id,
                                run_id,
                                _text(metric.get("name") or metric.get("metric_name"), "unnamed_metric"),
                                float(metric.get("value") or metric.get("metric_value") or 0.0),
                                _text(metric.get("status"), ""),
                                _json(metric),
                                now,
                            ),
                        )
        for failure in result.get("failure_events") or []:
            if isinstance(failure, Mapping):
                conn.execute(
                    """
                    insert into eval_failure_event (
                        eval_id, case_id, run_id, failure_type, node, expected, actual,
                        artifact_refs_json, status, payload_json, created_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        eval_id,
                        case_id,
                        run_id,
                        _text(failure.get("failure_type"), "unknown_failure"),
                        _text(failure.get("node"), ""),
                        _text(failure.get("expected"), ""),
                        _text(failure.get("actual"), ""),
                        _json(failure.get("artifact_refs") or []),
                        _text(failure.get("status"), "observed"),
                        _json(failure),
                        now,
                    ),
                )
        for annotation in result.get("annotations") or []:
            if isinstance(annotation, Mapping):
                conn.execute(
                    """
                    insert into eval_annotation (
                        eval_id, case_id, run_id, annotator, label, note,
                        payload_json, created_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        eval_id,
                        case_id,
                        run_id,
                        _text(annotation.get("annotator"), "system"),
                        _text(annotation.get("label"), ""),
                        _text(annotation.get("note"), ""),
                        _json(annotation),
                        now,
                    ),
                )
        for judge in result.get("judge_runs") or []:
            if isinstance(judge, Mapping):
                conn.execute(
                    """
                    insert into eval_judge_run (
                        eval_id, case_id, run_id, judge_model, rubric_version,
                        prompt_digest, score, explanation, latency_ms, token_count,
                        payload_json, created_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        eval_id,
                        case_id,
                        run_id,
                        _text(judge.get("judge_model"), ""),
                        _text(judge.get("rubric_version"), ""),
                        _text(judge.get("prompt_digest"), ""),
                        float(judge.get("score") or 0.0),
                        _text(judge.get("explanation"), ""),
                        int(judge.get("latency_ms") or 0),
                        int(judge.get("token_count") or judge.get("total_tokens") or 0),
                        _json(judge),
                        now,
                    ),
                )
        _upsert_dashboard_snapshot(conn, eval_id=eval_id, run_id=run_id, created_at=now)
    return {"status": "pass", "db_path": str(path.resolve()), "counts": read_eval_counts(path)}


def register_eval_case(db_path: str | Path, case: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(db_path)
    migrate_eval_store(path)
    eval_id = _text(case.get("eval_id"), "default_eval")
    case_id = _text(case.get("case_id"), "unknown_case")
    dataset_id = _text(case.get("dataset_id"), eval_id)
    now = _now()
    with _connect(path) as conn:
        conn.execute(
            """
            insert or replace into eval_case_registry (
                eval_id, case_id, case_family, status, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?)
            """,
            (
                eval_id,
                case_id,
                _text(case.get("case_family"), ""),
                _text(case.get("status"), "current"),
                _json(case),
                now,
            ),
        )
        conn.execute(
            """
            insert or replace into eval_case_membership (
                dataset_id, eval_id, case_id, status, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?)
            """,
            (
                dataset_id,
                eval_id,
                case_id,
                _text(case.get("membership_status"), "active"),
                _json(case.get("membership") or {}),
                now,
            ),
        )
    return {"status": "pass", "db_path": str(path.resolve()), "counts": read_eval_counts(path)}


def record_eval_gold_promotion(db_path: str | Path, promotion: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(db_path)
    migrate_eval_store(path)
    now = _now()
    with _connect(path) as conn:
        conn.execute(
            """
            insert into eval_gold_promotion (
                eval_id, case_id, state, criteria_version, review_method, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _text(promotion.get("eval_id"), "default_eval"),
                _text(promotion.get("case_id"), "unknown_case"),
                _text(promotion.get("state"), "candidate"),
                _text(promotion.get("criteria_version"), ""),
                _text(promotion.get("review_method"), ""),
                _json(promotion),
                now,
            ),
        )
    return {"status": "pass", "db_path": str(path.resolve()), "counts": read_eval_counts(path)}


def read_eval_counts(db_path: str | Path) -> dict[str, int]:
    with _connect(Path(db_path)) as conn:
        return {table: int(conn.execute(f"select count(*) from {table}").fetchone()[0]) for table in EVAL_TABLES}


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists eval_store_metadata (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists eval_case_registry (
            eval_id text not null,
            case_id text not null,
            case_family text not null default '',
            status text not null default 'current',
            payload_json text not null default '{}',
            created_at text not null,
            primary key (eval_id, case_id)
        );
        create table if not exists eval_dataset_version (
            dataset_id text primary key,
            version text not null,
            data_snapshot_id text not null default '',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists eval_case_membership (
            dataset_id text not null,
            eval_id text not null,
            case_id text not null,
            status text not null default 'active',
            payload_json text not null default '{}',
            created_at text not null,
            primary key (dataset_id, eval_id, case_id)
        );
        create table if not exists eval_run (
            eval_id text not null,
            run_id text not null,
            case_family text not null default '',
            status text not null,
            score real not null default 0,
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            model_profile text not null default '',
            payload_json text not null,
            created_at text not null,
            primary key (eval_id, run_id)
        );
        create table if not exists eval_case_result (
            eval_id text not null,
            case_id text not null,
            run_id text not null,
            status text not null,
            score real not null default 0,
            data_snapshot_id text not null default '',
            criteria_version text not null default '',
            payload_json text not null,
            created_at text not null,
            primary key (eval_id, case_id, run_id)
        );
        create table if not exists eval_node_result (
            id integer primary key autoincrement,
            eval_id text not null,
            case_id text not null,
            run_id text not null,
            node text not null,
            status text not null,
            metric_count integer not null default 0,
            payload_json text not null,
            created_at text not null
        );
        create table if not exists eval_metric_result (
            id integer primary key autoincrement,
            eval_id text not null,
            case_id text not null,
            run_id text not null,
            metric_name text not null,
            metric_value real not null default 0,
            status text not null default '',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists eval_failure_event (
            id integer primary key autoincrement,
            eval_id text not null,
            case_id text not null,
            run_id text not null,
            failure_type text not null,
            node text not null default '',
            expected text not null default '',
            actual text not null default '',
            artifact_refs_json text not null default '[]',
            status text not null default 'observed',
            payload_json text not null,
            created_at text not null
        );
        create table if not exists eval_annotation (
            id integer primary key autoincrement,
            eval_id text not null,
            case_id text not null,
            run_id text not null,
            annotator text not null default 'system',
            label text not null default '',
            note text not null default '',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists eval_gold_promotion (
            id integer primary key autoincrement,
            eval_id text not null,
            case_id text not null,
            state text not null,
            criteria_version text not null default '',
            review_method text not null default '',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists eval_judge_run (
            id integer primary key autoincrement,
            eval_id text not null,
            case_id text not null,
            run_id text not null,
            judge_model text not null default '',
            rubric_version text not null default '',
            prompt_digest text not null default '',
            score real not null default 0,
            explanation text not null default '',
            latency_ms integer not null default 0,
            token_count integer not null default 0,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists eval_dashboard_snapshot (
            eval_id text not null,
            run_id text not null,
            pass_count integer not null default 0,
            fail_count integer not null default 0,
            failure_count integer not null default 0,
            gold_candidate_count integer not null default 0,
            payload_json text not null default '{}',
            created_at text not null,
            primary key (eval_id, run_id)
        );
        create index if not exists idx_eval_run_status on eval_run(eval_id, status);
        create index if not exists idx_eval_failure_type on eval_failure_event(failure_type, node);
        create index if not exists idx_eval_node_run on eval_node_result(run_id, node);
        create index if not exists idx_eval_metric_run on eval_metric_result(run_id, metric_name);
        create index if not exists idx_eval_annotation_label on eval_annotation(eval_id, label);
        """
    )


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma journal_mode=WAL")
    conn.execute("pragma busy_timeout=30000")
    return conn


def _set_metadata(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        """
        insert into eval_store_metadata(key, value_json, updated_at)
        values (?, ?, ?)
        on conflict(key) do update set value_json = excluded.value_json, updated_at = excluded.updated_at
        """,
        (key, _json(value), _now()),
    )


def _upsert_dashboard_snapshot(conn: sqlite3.Connection, *, eval_id: str, run_id: str, created_at: str) -> None:
    status_rows = conn.execute(
        "select status, count(*) from eval_case_result where eval_id = ? and run_id = ? group by status",
        (eval_id, run_id),
    ).fetchall()
    statuses = {str(row[0]): int(row[1]) for row in status_rows}
    failure_count = int(
        conn.execute(
            "select count(*) from eval_failure_event where eval_id = ? and run_id = ?",
            (eval_id, run_id),
        ).fetchone()[0]
    )
    gold_candidate_count = int(
        conn.execute(
            "select count(*) from eval_gold_promotion where eval_id = ? and state in ('candidate','reviewed','active_regression','gold')",
            (eval_id,),
        ).fetchone()[0]
    )
    payload = {
        "eval_id": eval_id,
        "run_id": run_id,
        "status_counts": statuses,
        "failure_count": failure_count,
        "gold_candidate_count": gold_candidate_count,
    }
    conn.execute(
        """
        insert or replace into eval_dashboard_snapshot (
            eval_id, run_id, pass_count, fail_count, failure_count,
            gold_candidate_count, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            eval_id,
            run_id,
            int(statuses.get("pass", 0)),
            int(statuses.get("fail", 0)),
            failure_count,
            gold_candidate_count,
            _json(payload),
            created_at,
        ),
    )


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _text(value: Any, default: str = "") -> str:
    text = "" if value is None else str(value)
    return text if text else default


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
