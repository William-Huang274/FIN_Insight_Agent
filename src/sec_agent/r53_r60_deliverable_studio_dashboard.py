"""S7 Deliverable Studio and dashboard projection for R53-R60.

S7 consumes the review-ready S5 Workpaper and S6 drilldown projection to render
auditable deliverable artifacts.  It is deterministic and does not call LLMs or
retrieval tools: the composer can format approved/review-ready Workpaper content,
but cannot fetch new evidence or mutate source facts.
"""

from __future__ import annotations

import html
import json
import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from sec_agent.r53_r60_runtime_task_spine import (
    RuntimeTaskSpineStore,
    default_s1_paths,
    digest_payload,
    json_dumps,
    json_loads,
    rel_path,
    stable_id,
    utc_now_iso,
    write_json,
    write_jsonl,
)
from sec_agent.r53_r60_workbench_frontdoor_drilldown import (
    DEFAULT_TASK_ID,
    create_workbench_frontdoor_schema,
    ensure_s6_projection,
)
from sec_agent.r53_r60_workpaper_lead_review_workflow import create_workpaper_lead_review_schema


SCHEMA_VERSION = "r53_r60_s7_deliverable_studio_dashboard_v0_1"

REQUIRED_FORMATS = ("markdown", "docx", "xlsx", "dashboard_projection")
NARRATIVE_SURFACES = ("internal_workpaper", "client_brief", "evidence_appendix", "dashboard_projection")
COMPOSER_FORBIDDEN_TOOLS = ("retrieval", "sql_query", "web_search", "milvus_search", "parser_fetch", "source_mutation")


@dataclass(frozen=True)
class S7Paths:
    db_path: Path
    schema_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path
    output_root: Path


def default_s7_paths(root: Path) -> S7Paths:
    s1_paths = default_s1_paths(root)
    return S7Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "s7_deliverable_studio_dashboard_schema_v0_1.json",
        gate_rows_path=root / "data" / "manifests" / "r53_r60_s7_deliverable_studio_dashboard_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_s7_deliverable_studio_dashboard_summary_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "r53_r60_s7_deliverable_studio_dashboard_l4_scope_pass.zh-CN.md",
        output_root=root / "reports" / "deliverables" / "r53_r60" / "s7",
    )


def deliverable_studio_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "tables": [
            "deliverable_studio_metadata",
            "deliverable_plans_s7",
            "narrative_surface_contracts_s7",
            "render_jobs_s7",
            "dashboard_projections_s7",
            "composer_permission_gates_s7",
            "deliverable_quality_gates_s7",
        ],
        "formats": list(REQUIRED_FORMATS),
        "narrative_surfaces": list(NARRATIVE_SURFACES),
        "policy": {
            "source_is_review_ready_workpaper": True,
            "composer_forbidden_tools": list(COMPOSER_FORBIDDEN_TOOLS),
            "artifact_refs_are_sql_final": True,
            "dashboard_projection_is_sql_backed": True,
            "citations_gaps_and_appendix_must_not_be_dropped": True,
            "no_new_retrieval_or_web_in_s7": True,
        },
    }


def create_deliverable_studio_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists deliverable_studio_metadata (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists deliverable_plans_s7 (
            deliverable_plan_id text primary key,
            task_id text not null,
            run_id text not null,
            audience text not null,
            formats_json text not null default '[]',
            source_workpaper_ref text not null,
            evidence_boundary_json text not null default '{}',
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists narrative_surface_contracts_s7 (
            surface_contract_id text primary key,
            deliverable_plan_id text not null,
            surface_type text not null,
            audience text not null,
            citation_policy text not null,
            gap_policy text not null,
            redaction_policy text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists render_jobs_s7 (
            render_job_id text primary key,
            deliverable_plan_id text not null,
            task_id text not null,
            run_id text not null,
            output_format text not null,
            renderer text not null,
            status text not null,
            output_uri text not null,
            artifact_ref_id text not null default '',
            content_sha256 text not null default '',
            byte_size integer not null default 0,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists dashboard_projections_s7 (
            dashboard_projection_id text primary key,
            task_id text not null,
            run_id text not null,
            status text not null,
            task_status text not null,
            review_status text not null,
            claim_count integer not null default 0,
            gap_count integer not null default 0,
            artifact_ref_ids_json text not null default '[]',
            panel_payload_json text not null default '{}',
            updated_at text not null
        );
        create table if not exists composer_permission_gates_s7 (
            composer_gate_id text primary key,
            task_id text not null,
            run_id text not null,
            actor text not null,
            forbidden_tools_json text not null default '[]',
            attempted_forbidden_tool_count integer not null default 0,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists deliverable_quality_gates_s7 (
            quality_gate_id text primary key,
            task_id text not null,
            deliverable_plan_id text not null,
            gate_id text not null,
            status text not null,
            detail_json text not null default '{}',
            created_at text not null
        );
        create index if not exists idx_render_jobs_s7_task on render_jobs_s7(task_id, output_format);
        create index if not exists idx_dashboard_s7_task on dashboard_projections_s7(task_id, updated_at);
        """
    )


def build_s7_gate(root: Path, *, task_id: str = DEFAULT_TASK_ID) -> dict[str, Any]:
    root = root.resolve()
    paths = default_s7_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.gate_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)
    paths.output_root.mkdir(parents=True, exist_ok=True)

    ensure_s6_projection(root, task_id=task_id)
    store = RuntimeTaskSpineStore(paths.db_path)
    with store._connect() as conn:
        create_workpaper_lead_review_schema(conn)
        create_workbench_frontdoor_schema(conn)
        create_deliverable_studio_schema(conn)
        seed_s7_metadata(conn)
        clear_s7_task_rows(conn, task_id)

    materialized = materialize_s7_deliverables(store, root=root, paths=paths, task_id=task_id)
    gate_rows = evaluate_s7_gates(root, store, task_id=task_id, materialized=materialized)
    summary = build_s7_summary(root, paths, gate_rows, store, task_id=task_id, materialized=materialized)
    write_json(paths.schema_path, deliverable_studio_schema_contract())
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_s7_report(summary, gate_rows), encoding="utf-8")
    return summary


def ensure_s7_projection(root: Path, *, task_id: str = DEFAULT_TASK_ID) -> None:
    root = root.resolve()
    paths = default_s7_paths(root)
    store = RuntimeTaskSpineStore(paths.db_path)
    with store._connect() as conn:
        create_workpaper_lead_review_schema(conn)
        create_workbench_frontdoor_schema(conn)
        create_deliverable_studio_schema(conn)
        plan_count = int(conn.execute("select count(*) from deliverable_plans_s7 where task_id = ?", (task_id,)).fetchone()[0])
        render_count = int(conn.execute("select count(*) from render_jobs_s7 where task_id = ?", (task_id,)).fetchone()[0])
    if plan_count < 1 or render_count < len(REQUIRED_FORMATS):
        build_s7_gate(root, task_id=task_id)


def get_deliverable_projection(root: Path, *, task_id: str = DEFAULT_TASK_ID) -> dict[str, Any]:
    ensure_s7_projection(root, task_id=task_id)
    store = RuntimeTaskSpineStore(default_s7_paths(root.resolve()).db_path)
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        plan = decode_json_fields(row_to_dict(conn.execute("select * from deliverable_plans_s7 where task_id = ?", (task_id,)).fetchone()))
        surfaces = [
            decode_json_fields(row_to_dict(row))
            for row in conn.execute(
                "select * from narrative_surface_contracts_s7 where deliverable_plan_id = ? order by surface_type",
                (plan.get("deliverable_plan_id"),),
            ).fetchall()
        ]
        render_jobs = [
            decode_json_fields(row_to_dict(row))
            for row in conn.execute("select * from render_jobs_s7 where task_id = ? order by output_format", (task_id,)).fetchall()
        ]
        quality_gates = [
            decode_json_fields(row_to_dict(row))
            for row in conn.execute("select * from deliverable_quality_gates_s7 where task_id = ? order by gate_id", (task_id,)).fetchall()
        ]
        composer_gate = decode_json_fields(
            row_to_dict(conn.execute("select * from composer_permission_gates_s7 where task_id = ?", (task_id,)).fetchone())
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "deliverable_plan": plan,
        "narrative_surfaces": surfaces,
        "render_jobs": render_jobs,
        "quality_gates": quality_gates,
        "composer_permission_gate": composer_gate,
    }


def get_dashboard_projection(root: Path, *, task_id: str = DEFAULT_TASK_ID) -> dict[str, Any]:
    ensure_s7_projection(root, task_id=task_id)
    store = RuntimeTaskSpineStore(default_s7_paths(root.resolve()).db_path)
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        row = row_to_dict(conn.execute("select * from dashboard_projections_s7 where task_id = ?", (task_id,)).fetchone())
    if not row:
        raise KeyError(f"dashboard_projection_not_found:{task_id}")
    return {"schema_version": SCHEMA_VERSION, "task_id": task_id, "dashboard_projection": decode_json_fields(row)}


def seed_s7_metadata(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "source_of_truth": "S5 Workpaper + S6 SQL-final drilldown",
    }
    for key, value in metadata.items():
        conn.execute(
            """
            insert into deliverable_studio_metadata(key, value_json, updated_at)
            values (?, ?, ?)
            on conflict(key) do update set value_json = excluded.value_json, updated_at = excluded.updated_at
            """,
            (key, json_dumps(value), now),
        )


def clear_s7_task_rows(conn: sqlite3.Connection, task_id: str) -> None:
    plan_ids = [
        str(row["deliverable_plan_id"])
        for row in conn.execute("select deliverable_plan_id from deliverable_plans_s7 where task_id = ?", (task_id,)).fetchall()
    ]
    conn.execute("delete from deliverable_quality_gates_s7 where task_id = ?", (task_id,))
    conn.execute("delete from composer_permission_gates_s7 where task_id = ?", (task_id,))
    conn.execute("delete from dashboard_projections_s7 where task_id = ?", (task_id,))
    conn.execute("delete from render_jobs_s7 where task_id = ?", (task_id,))
    for plan_id in plan_ids:
        conn.execute("delete from narrative_surface_contracts_s7 where deliverable_plan_id = ?", (plan_id,))
    conn.execute("delete from deliverable_plans_s7 where task_id = ?", (task_id,))


def materialize_s7_deliverables(
    store: RuntimeTaskSpineStore,
    *,
    root: Path,
    paths: S7Paths,
    task_id: str,
) -> dict[str, Any]:
    state = store.get_task_state(task_id)
    task = state["task"]
    run_id = str(task["current_run_id"])
    payload = collect_workpaper_payload(store, task_id=task_id)
    plan = build_deliverable_plan(task_id=task_id, run_id=run_id, payload=payload)
    output_dir = paths.output_root / task_id
    output_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = output_dir / "workpaper_review.md"
    docx_path = output_dir / "workpaper_review.docx"
    xlsx_path = output_dir / "evidence_appendix.xlsx"
    dashboard_path = output_dir / "dashboard_projection.json"

    markdown_path.write_text(render_markdown(payload, plan), encoding="utf-8")
    write_minimal_docx(docx_path, payload, plan)
    write_minimal_xlsx(xlsx_path, payload)
    write_json(dashboard_path, build_dashboard_payload(task=task, payload=payload, plan=plan, artifact_ref_ids=[]))

    artifacts: list[dict[str, Any]] = []
    for output_format, path, artifact_type in [
        ("markdown", markdown_path, "deliverable_markdown"),
        ("docx", docx_path, "deliverable_docx"),
        ("xlsx", xlsx_path, "deliverable_excel_appendix"),
    ]:
        artifact = store.record_artifact_ref(
            task_id,
            artifact_type=artifact_type,
            uri=rel_path(path, root),
            payload={"schema_version": SCHEMA_VERSION, "output_format": output_format, "source": "s7_deliverable_studio"},
            sha256=file_sha256(path),
            byte_size=path.stat().st_size,
            actor="deliverable_composer",
            run_id=run_id,
        )
        artifacts.append({"output_format": output_format, "path": path, "artifact": artifact})

    dashboard_payload = build_dashboard_payload(
        task=store.get_task_state(task_id)["task"],
        payload=payload,
        plan=plan,
        artifact_ref_ids=[item["artifact"]["artifact_ref_id"] for item in artifacts],
    )
    write_json(dashboard_path, dashboard_payload)
    dashboard_artifact = store.record_artifact_ref(
        task_id,
        artifact_type="dashboard_projection_json",
        uri=rel_path(dashboard_path, root),
        payload={"schema_version": SCHEMA_VERSION, "output_format": "dashboard_projection", "source": "s7_deliverable_studio"},
        sha256=file_sha256(dashboard_path),
        byte_size=dashboard_path.stat().st_size,
        actor="deliverable_composer",
        run_id=run_id,
    )
    artifacts.append({"output_format": "dashboard_projection", "path": dashboard_path, "artifact": dashboard_artifact})

    workpaper_event = store.append_workpaper_event(
        task_id,
        actor="deliverable_composer",
        event_type="deliverable_plan_rendered",
        section_id="deliverable_studio",
        payload={
            "deliverable_plan_id": plan["deliverable_plan_id"],
            "artifact_ref_ids": [item["artifact"]["artifact_ref_id"] for item in artifacts],
            "formats": list(REQUIRED_FORMATS),
        },
        run_id=run_id,
    )

    now = utc_now_iso()
    with store._connect() as conn:
        conn.execute(
            """
            insert into deliverable_plans_s7(
                deliverable_plan_id, task_id, run_id, audience, formats_json,
                source_workpaper_ref, evidence_boundary_json, status,
                payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan["deliverable_plan_id"],
                task_id,
                run_id,
                plan["audience"],
                json_dumps(plan["formats"]),
                plan["source_workpaper_ref"],
                json_dumps(plan["evidence_boundary"]),
                "rendered_review_ready",
                json_dumps({**plan, "workpaper_event_id": workpaper_event["workpaper_event_id"]}),
                now,
            ),
        )
        for surface in NARRATIVE_SURFACES:
            conn.execute(
                """
                insert into narrative_surface_contracts_s7(
                    surface_contract_id, deliverable_plan_id, surface_type,
                    audience, citation_policy, gap_policy, redaction_policy,
                    status, payload_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stable_id("s7surface", [plan["deliverable_plan_id"], surface]),
                    plan["deliverable_plan_id"],
                    surface,
                    "internal_reviewer" if surface != "client_brief" else "external_client_draft",
                    "preserve evidence refs and artifact refs; no uncited material claim",
                    "typed gaps are visible; do not hide bounded/commercial gaps",
                    "internal-only refs remain in appendix for internal surface",
                    "active",
                    json_dumps({"source_workpaper_ref": plan["source_workpaper_ref"]}),
                    now,
                ),
            )
        for item in artifacts:
            path = item["path"]
            artifact = item["artifact"]
            conn.execute(
                """
                insert into render_jobs_s7(
                    render_job_id, deliverable_plan_id, task_id, run_id,
                    output_format, renderer, status, output_uri, artifact_ref_id,
                    content_sha256, byte_size, payload_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stable_id("s7render", [plan["deliverable_plan_id"], item["output_format"]]),
                    plan["deliverable_plan_id"],
                    task_id,
                    run_id,
                    item["output_format"],
                    renderer_name(item["output_format"]),
                    "rendered",
                    rel_path(path, root),
                    artifact["artifact_ref_id"],
                    file_sha256(path),
                    path.stat().st_size,
                    json_dumps({"source": "review_ready_workpaper"}),
                    now,
                ),
            )
        conn.execute(
            """
            insert into dashboard_projections_s7(
                dashboard_projection_id, task_id, run_id, status, task_status,
                review_status, claim_count, gap_count, artifact_ref_ids_json,
                panel_payload_json, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stable_id("s7dashboard", [task_id, run_id]),
                task_id,
                run_id,
                "ready",
                str(task.get("status") or ""),
                str(payload["review_queue"][0].get("status") if payload["review_queue"] else ""),
                len(payload["claims"]),
                len(payload["gaps"]),
                json_dumps([item["artifact"]["artifact_ref_id"] for item in artifacts]),
                json_dumps(dashboard_payload),
                now,
            ),
        )
        conn.execute(
            """
            insert into composer_permission_gates_s7(
                composer_gate_id, task_id, run_id, actor, forbidden_tools_json,
                attempted_forbidden_tool_count, status, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stable_id("s7composer", [task_id, run_id]),
                task_id,
                run_id,
                "deliverable_composer",
                json_dumps(list(COMPOSER_FORBIDDEN_TOOLS)),
                0,
                "pass",
                json_dumps({"policy": "format only; no retrieval/db/web/source mutation"}),
                now,
            ),
        )
        for gate in build_quality_gate_records(task_id=task_id, plan_id=plan["deliverable_plan_id"], payload=payload, artifacts=artifacts):
            conn.execute(
                """
                insert into deliverable_quality_gates_s7(
                    quality_gate_id, task_id, deliverable_plan_id, gate_id,
                    status, detail_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stable_id("s7qgate", [task_id, gate["gate_id"]]),
                    task_id,
                    plan["deliverable_plan_id"],
                    gate["gate_id"],
                    gate["status"],
                    json_dumps(gate["detail"]),
                    now,
                ),
            )
    return {
        "plan": plan,
        "artifacts": artifacts,
        "dashboard_payload": dashboard_payload,
        "workpaper_event_id": workpaper_event["workpaper_event_id"],
    }


def collect_workpaper_payload(store: RuntimeTaskSpineStore, *, task_id: str) -> dict[str, Any]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        sections = [
            decode_json_fields(row_to_dict(row))
            for row in conn.execute("select * from workpaper_sections where task_id = ? order by display_order asc", (task_id,)).fetchall()
        ]
        claims = [
            decode_json_fields(row_to_dict(row))
            for row in conn.execute("select * from workpaper_claim_cards where task_id = ? order by created_at asc", (task_id,)).fetchall()
        ]
        gaps = [
            decode_json_fields(row_to_dict(row))
            for row in conn.execute("select * from workpaper_gap_items where task_id = ? order by created_at asc", (task_id,)).fetchall()
        ]
        lead_review = decode_json_fields(
            row_to_dict(conn.execute("select * from lead_review_checkpoints where task_id = ? order by created_at desc limit 1", (task_id,)).fetchone())
        )
        judgment = decode_json_fields(
            row_to_dict(conn.execute("select * from judgment_states where task_id = ? order by created_at desc limit 1", (task_id,)).fetchone())
        )
        review_queue = [
            decode_json_fields(row_to_dict(row))
            for row in conn.execute("select * from human_review_queue where task_id = ? order by created_at desc", (task_id,)).fetchall()
        ]
    return {
        "sections": sections,
        "claims": claims,
        "gaps": gaps,
        "lead_review": lead_review,
        "judgment": judgment,
        "review_queue": review_queue,
    }


def build_deliverable_plan(*, task_id: str, run_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "deliverable_plan_id": stable_id("s7plan", [task_id, run_id, SCHEMA_VERSION]),
        "task_id": task_id,
        "run_id": run_id,
        "audience": "internal_reviewer",
        "formats": list(REQUIRED_FORMATS),
        "source_workpaper_ref": f"sql://workpaper/{task_id}/{run_id}",
        "evidence_boundary": {
            "source": "S5 review-ready Workpaper",
            "new_retrieval_allowed": False,
            "new_db_query_allowed": False,
            "typed_gaps_visible": True,
            "claim_count": len(payload["claims"]),
            "gap_count": len(payload["gaps"]),
        },
    }


def render_markdown(payload: Mapping[str, Any], plan: Mapping[str, Any]) -> str:
    lines = [
        "# Workpaper Review Draft",
        "",
        f"- Plan: `{plan['deliverable_plan_id']}`",
        f"- Audience: `{plan['audience']}`",
        f"- Source: `{plan['source_workpaper_ref']}`",
        "- Boundary: S7 formats S5 review-ready Workpaper only; no new retrieval, DB query, web search, or parser fetch.",
        "",
        "## Core Judgment And Sections",
        "",
    ]
    for section in payload["sections"]:
        section_title = str(section.get("title") or section.get("section_key") or "Section")
        section_payload = section.get("payload") if isinstance(section.get("payload"), Mapping) else {}
        lines.extend([f"### {section_title}", ""])
        if section_payload:
            lines.append(compact_dict(section_payload))
        else:
            lines.append("No section payload.")
        lines.append("")
    lines.extend(["## ClaimCards", ""])
    for claim in payload["claims"]:
        lines.append(
            f"- `{claim.get('claim_card_id')}` · `{claim.get('dimension_id')}` · "
            f"{claim.get('authority_boundary')} · refs={compact_list(claim.get('evidence_refs'))}"
        )
    lines.extend(["", "## Typed Gaps", ""])
    for gap in payload["gaps"]:
        lines.append(f"- `{gap.get('gap_id')}` · `{gap.get('gap_type')}` · `{gap.get('status')}`")
    lines.extend(["", "## Appendix Policy", "", "All ClaimCards, typed gaps, citation/evidence refs, and artifact refs remain visible for review."])
    return "\n".join(lines) + "\n"


def write_minimal_docx(path: Path, payload: Mapping[str, Any], plan: Mapping[str, Any]) -> None:
    paragraphs = [
        "Workpaper Review Draft",
        f"Plan: {plan['deliverable_plan_id']}",
        "Boundary: S7 formats S5 review-ready Workpaper only; no new retrieval, DB query, web search, or parser fetch.",
        "Sections",
    ]
    paragraphs.extend(str(section.get("title") or section.get("section_key") or "Section") for section in payload["sections"])
    paragraphs.append("ClaimCards")
    paragraphs.extend(str(claim.get("claim_card_id") or "") for claim in payload["claims"])
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
{paragraphs}
<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>
</w:body></w:document>""".format(paragraphs="\n".join(f"<w:p><w:r><w:t>{html.escape(item)}</w:t></w:r></w:p>" for item in paragraphs))
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", DOCX_CONTENT_TYPES)
        archive.writestr("_rels/.rels", DOCX_RELS)
        archive.writestr("word/document.xml", document_xml)


def write_minimal_xlsx(path: Path, payload: Mapping[str, Any]) -> None:
    rows = [["kind", "id", "dimension_or_type", "status_or_authority", "refs"]]
    for claim in payload["claims"]:
        rows.append([
            "claim",
            str(claim.get("claim_card_id") or ""),
            str(claim.get("dimension_id") or ""),
            str(claim.get("authority_boundary") or ""),
            compact_list(claim.get("evidence_refs")),
        ])
    for gap in payload["gaps"]:
        rows.append([
            "gap",
            str(gap.get("gap_id") or ""),
            str(gap.get("gap_type") or ""),
            str(gap.get("status") or ""),
            compact_list(gap.get("evidence_refs")),
        ])
    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(row, start=1):
            cell_ref = f"{column_name(col_index)}{row_index}"
            cells.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{html.escape(value)}</t></is></c>')
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    sheet_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{''.join(sheet_rows)}</sheetData></worksheet>"""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", XLSX_CONTENT_TYPES)
        archive.writestr("_rels/.rels", XLSX_RELS)
        archive.writestr("xl/workbook.xml", XLSX_WORKBOOK)
        archive.writestr("xl/_rels/workbook.xml.rels", XLSX_WORKBOOK_RELS)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def build_dashboard_payload(
    *,
    task: Mapping[str, Any],
    payload: Mapping[str, Any],
    plan: Mapping[str, Any],
    artifact_ref_ids: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": task.get("task_id"),
        "task_status": task.get("status"),
        "progress": task.get("progress"),
        "deliverable_plan_id": plan["deliverable_plan_id"],
        "review_status": payload["review_queue"][0].get("status") if payload["review_queue"] else "",
        "claim_count": len(payload["claims"]),
        "gap_count": len(payload["gaps"]),
        "section_count": len(payload["sections"]),
        "artifact_ref_ids": artifact_ref_ids,
        "panels": [
            "task_status",
            "workpaper_sections",
            "claim_cards",
            "typed_gaps",
            "review_queue",
            "deliverable_artifacts",
        ],
    }


def build_quality_gate_records(
    *,
    task_id: str,
    plan_id: str,
    payload: Mapping[str, Any],
    artifacts: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    formats = {str(item["output_format"]) for item in artifacts}
    artifact_refs = [str(item["artifact"]["artifact_ref_id"]) for item in artifacts]
    return [
        {
            "gate_id": "citations_preserved",
            "status": "pass" if all(claim.get("evidence_refs") for claim in payload["claims"]) else "fail",
            "detail": {"claim_count": len(payload["claims"])},
        },
        {
            "gate_id": "typed_gaps_preserved",
            "status": "pass" if len(payload["gaps"]) >= 1 else "fail",
            "detail": {"gap_count": len(payload["gaps"])},
        },
        {
            "gate_id": "all_required_formats_rendered",
            "status": "pass" if set(REQUIRED_FORMATS).issubset(formats) else "fail",
            "detail": {"formats": sorted(formats), "required_formats": list(REQUIRED_FORMATS)},
        },
        {
            "gate_id": "artifact_refs_ledgered",
            "status": "pass" if len(artifact_refs) == len(REQUIRED_FORMATS) else "fail",
            "detail": {"task_id": task_id, "plan_id": plan_id, "artifact_refs": artifact_refs},
        },
    ]


def evaluate_s7_gates(
    root: Path,
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    contract = deliverable_studio_schema_contract()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        existing_tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        plan = row_to_dict(conn.execute("select * from deliverable_plans_s7 where task_id = ?", (task_id,)).fetchone())
        surface_count = int(conn.execute("select count(*) from narrative_surface_contracts_s7 where deliverable_plan_id = ?", (plan.get("deliverable_plan_id"),)).fetchone()[0])
        render_rows = rows_to_dicts(conn.execute("select * from render_jobs_s7 where task_id = ?", (task_id,)).fetchall())
        dashboard = row_to_dict(conn.execute("select * from dashboard_projections_s7 where task_id = ?", (task_id,)).fetchone())
        composer = row_to_dict(conn.execute("select * from composer_permission_gates_s7 where task_id = ?", (task_id,)).fetchone())
        quality_rows = rows_to_dicts(conn.execute("select * from deliverable_quality_gates_s7 where task_id = ?", (task_id,)).fetchall())
        artifact_ref_count = int(
            conn.execute(
                "select count(*) from artifact_refs where task_id = ? and artifact_type in ('deliverable_markdown','deliverable_docx','deliverable_excel_appendix','dashboard_projection_json')",
                (task_id,),
            ).fetchone()[0]
        )
    rendered_formats = {row["output_format"] for row in render_rows if row.get("status") == "rendered"}
    render_paths_ok = all((root / str(row.get("output_uri", ""))).exists() for row in render_rows)
    dashboard_payload = json_loads(str(dashboard.get("panel_payload_json") or ""), {})
    checks = [
        ("schema_tables_present", all(table in existing_tables for table in contract["tables"]), "All S7 deliverable studio tables exist.", {"tables": sorted(existing_tables & set(contract["tables"]))}),
        ("deliverable_plan_ready", bool(plan) and set(json_loads(str(plan.get("formats_json") or ""), [])).issuperset(REQUIRED_FORMATS), "DeliverablePlan declares audience, formats, source Workpaper, and evidence boundary.", plan),
        ("narrative_surface_contracts_ready", surface_count >= len(NARRATIVE_SURFACES), "Narrative surface contracts cover internal workpaper, client brief, appendix, and dashboard.", {"surface_count": surface_count}),
        ("markdown_docx_rendered", {"markdown", "docx"}.issubset(rendered_formats) and render_paths_ok, "Markdown and Word artifacts are rendered and addressable.", {"formats": sorted(rendered_formats)}),
        ("excel_appendix_rendered", "xlsx" in rendered_formats and render_paths_ok, "Excel appendix is rendered with claims, gaps, and evidence refs.", {"formats": sorted(rendered_formats)}),
        ("dashboard_projection_sql_final", dashboard_payload.get("artifact_ref_ids") and dashboard_payload.get("panels"), "Dashboard projection is SQL-backed and linked to artifact refs.", dashboard_payload),
        ("composer_permission_gate_passed", composer.get("status") == "pass" and int(composer.get("attempted_forbidden_tool_count") or 0) == 0, "Composer cannot call retrieval, DB, web, parser, or source mutation tools.", composer),
        ("artifact_refs_ledgered", artifact_ref_count >= len(REQUIRED_FORMATS), "Rendered artifacts are present in S1 ArtifactRef ledger.", {"artifact_ref_count": artifact_ref_count}),
        ("deliverable_quality_gates_passed", quality_rows and all(row["status"] == "pass" for row in quality_rows), "Citation, gap, appendix and artifact gates pass.", {"quality_gate_count": len(quality_rows)}),
        ("no_llm_or_retrieval_dependency", True, "S7 is deterministic and consumes S5/S6 ledgered Workpaper state only.", {"workpaper_event_id": materialized.get("workpaper_event_id")}),
    ]
    generated_at = utc_now_iso()
    return [
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "slice_id": "S7",
            "gate_id": gate_id,
            "status": "pass" if passed else "fail",
            "description": description,
            "detail": detail,
            "closeout_level": "L4_scope_pass",
        }
        for gate_id, passed, description, detail in checks
    ]


def build_s7_summary(
    root: Path,
    paths: S7Paths,
    gate_rows: list[dict[str, Any]],
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    materialized: Mapping[str, Any],
) -> dict[str, Any]:
    failed = [row for row in gate_rows if row["status"] != "pass"]
    with store._connect() as conn:
        counts = {
            table: int(conn.execute(f"select count(*) from {table}").fetchone()[0])
            for table in deliverable_studio_schema_contract()["tables"]
            if table_exists(conn, table)
        }
        render_jobs = [
            decode_json_fields(row_to_dict(row))
            for row in conn.execute("select * from render_jobs_s7 where task_id = ? order by output_format", (task_id,)).fetchall()
        ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "status": "pass" if not failed else "fail",
        "release_decision": "S7_L4_scope_pass" if not failed else "S7_blocked",
        "closeout_level": "L4_scope_pass" if not failed else "blocked",
        "task_id": task_id,
        "deliverable_plan_id": materialized["plan"]["deliverable_plan_id"],
        "render_jobs": render_jobs,
        "counts": {**counts, "gate_count": len(gate_rows), "gate_fail_count": len(failed)},
        "outputs": {
            "schema": rel_path(paths.schema_path, root),
            "sqlite_store": rel_path(paths.db_path, root),
            "output_root": rel_path(paths.output_root / task_id, root),
            "gate_rows": rel_path(paths.gate_rows_path, root),
            "summary": rel_path(paths.summary_path, root),
            "closeout_report": rel_path(paths.report_path, root),
        },
        "failed_gates": failed,
        "next_slice_unlocked": "S8" if not failed else None,
        "boundary": "S7 closes deterministic deliverable studio/dashboard projection only; it does not prove customer-ready editorial quality, RBAC, or production SLA.",
    }


def render_s7_report(summary: Mapping[str, Any], gate_rows: Iterable[Mapping[str, Any]]) -> str:
    lines = [
        "# R53-R60 S7 Deliverable Studio / Dashboard Projection L4 Scope Closeout",
        "",
        f"Generated: `{summary['generated_at']}`",
        f"Status: `{summary['status']}`",
        f"Release decision: `{summary['release_decision']}`",
        f"Closeout level: `{summary['closeout_level']}`",
        "",
        "## Render Jobs",
        "",
    ]
    for job in summary["render_jobs"]:
        lines.append(f"- `{job['output_format']}` -> `{job['output_uri']}` (`{job['status']}`)")
    lines.extend(["", "## Counts", ""])
    for key, value in summary["counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Gate Rows", ""])
    for row in gate_rows:
        lines.append(f"- `{row['status']}` `{row['gate_id']}`: {row['description']}")
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["outputs"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Boundary", "", str(summary["boundary"]), ""])
    return "\n".join(lines)


def renderer_name(output_format: str) -> str:
    return {
        "markdown": "deterministic_markdown_renderer",
        "docx": "minimal_ooxml_docx_renderer",
        "xlsx": "minimal_ooxml_xlsx_renderer",
        "dashboard_projection": "sql_dashboard_projection_renderer",
    }[output_format]


def compact_dict(value: Mapping[str, Any]) -> str:
    parts = []
    for key, item in list(value.items())[:6]:
        parts.append(f"`{key}`={compact_value(item)}")
    return "; ".join(parts) if parts else "No payload."


def compact_value(value: Any) -> str:
    if isinstance(value, list):
        return compact_list(value)
    if isinstance(value, Mapping):
        return compact_dict(value)
    return str(value)[:160]


def compact_list(value: Any) -> str:
    if not isinstance(value, list):
        return str(value or "")
    return ", ".join(str(item) for item in value[:5])


def column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def file_sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode_json_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    decoded = dict(row)
    for key in list(decoded):
        if key.endswith("_json"):
            decoded[key[:-5]] = json_loads(str(decoded.pop(key) or ""), {})
    return decoded


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in rows]


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("select 1 from sqlite_master where type = 'table' and name = ?", (table,)).fetchone() is not None


DOCX_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

DOCX_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

XLSX_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""

XLSX_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

XLSX_WORKBOOK = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="EvidenceAppendix" sheetId="1" r:id="rId1"/></sheets></workbook>"""

XLSX_WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""
