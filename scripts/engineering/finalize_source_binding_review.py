"""Integrate a verified source audit with the existing full-library issue/parse ledger."""
from __future__ import annotations

import argparse
import base64
from collections import Counter
import json
from pathlib import Path
import zlib

from audit_source_binding_lineage import digest, read_json, read_lines, readonly, write_html


def queue_record(row):
    status = row["availability"]
    route = row.get("family") or row["current_representation"].get("lane")
    if status == "archived_original_existing":
        stage = "structure_quality_review"
    elif status == "historical_original_recovered":
        stage = "parse_recovered_original"
    elif status == "readme_api_content_recovered":
        route, stage = "markdown", "parse_recovered_content"
    elif status == "structured_payload_preserved":
        route, stage = "structured_json", "record_contract_review"
    elif status == "derivative_parent_recovered":
        stage = "parent_excerpt_alignment"
    elif status in ("candidate_version_unverified", "recorded_archive_version_unverified"):
        stage = "historical_version_review"
    else:
        stage = "source_acquisition_recovery"
    return dict(document_id=row["document_id"], source_id=row["source_id"], route=route,
                stage=stage, state="pending", evidence_status=status, action=row["next_action"])


def integrate_issues(issues, reviewed):
    ids = {r["document_id"] for r in reviewed}
    replaced = {r["document_id"] for r in issues if r["kind"] == "missing_verified_original"}
    if replaced != ids:
        raise ValueError("The old missing-original cohort must match the reviewed cohort exactly")
    result = [r for r in issues if r["kind"] != "missing_verified_original"]
    result.extend(dict(kind="source_lineage_review", document_id=r["document_id"],
        availability=r["availability"], gap_class=r["gap_class"], stage=r["processing"]["stage"],
        next_action=r["next_action"], quality_pass=False) for r in reviewed)
    return result


def finalize(args):
    src, out = Path(args.audit), Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    rows = read_lines(src/"library-bindings.jsonl")
    review_ids = {r["document_id"] for r in read_lines(src/"audit-409.jsonl")}
    summary = read_json(src/"summary.json")
    for key, value in summary["inputs"].items():
        if digest(Path(value["path"]).read_bytes()) != value["sha256"]:
            raise ValueError("Input changed after audit: " + key)
    if any(summary[key] for key in ("inventory_errors","metadata_errors","database_errors","findings")):
        raise ValueError("Audit errors must be reviewed before integration")
    materialized = out/"recovered-content"
    materialized.mkdir()
    with readonly(args.snapshots) as snapshots:
        for row in rows:
            if row["document_id"] in review_ids:
                status = row["availability"]
                content = None
                if status == "readme_api_content_recovered":
                    candidate = row["selected_originals"][0]
                    with readonly(candidate["database"]) as db:
                        record = db.execute("SELECT body_zlib FROM raw_captures WHERE url=? AND digest=?",
                                            (candidate["url"],candidate["sha256"])).fetchone()
                    raw = zlib.decompress(record[0])
                    assert digest(raw) == candidate["sha256"]
                    envelope = json.loads(raw)
                    content = base64.b64decode(envelope["content"])
                    assert envelope["html_url"] == row["url"]
                    assert digest(content) == row["source_digest"]
                    row["git_blob_identity"] = envelope.get("sha")
                    row["capture_transport_url"] = candidate["url"]
                    suffix = ".md"
                elif status == "structured_payload_preserved":
                    snap = snapshots.execute("SELECT snapshot FROM attachment_captures WHERE object_id=?",
                                             (row["snapshot"]["object_id"],)).fetchone()[0]
                    assert digest(snap.encode()) == row["snapshot"]["sha256"]
                    content = json.loads(snap)["bundle"]["text"].encode()
                    assert digest(content) == row["source_digest"]
                    assert isinstance(json.loads(content), (dict,list))
                    suffix = ".json"
                if content is not None:
                    file = materialized/(digest(content)+suffix)
                    if file.exists():
                        assert file.read_bytes() == content
                    else:
                        file.write_bytes(content)
                    row["recovered_content"] = dict(path=str(file),sha256=digest(content),bytes=len(content))
                # Cause classification records evidence, not a guess that absent files were deleted.
                row["audit_reason"] = {
                    "historical_original_recovered":"原件在其他采集目录/归档库或下载URL下；原先仅查一个库和同URL漏记，现以原始摘要核实",
                    "readme_api_content_recovered":"保存键为GitHub API，资料键为README网页；已解码API载荷并核对完整源摘要",
                    "structured_payload_preserved":"资料本来是结构化API/记录载荷；完整JSON与源摘要一致，不能以没有网页原件判为丢失",
                    "derivative_parent_recovered":"局部转录是独立资料；父原件摘要匹配，保留父子关系而不冒充整篇原件",
                    "recorded_archive_version_unverified":"采集元数据直指文件且仍存在；历史原件摘要缺失，暂不声称字节级同版本",
                    "candidate_version_unverified":"同URL/显式来源链或文件名找到候选；缺少能证明历史同版本的证据",
                    "derivative_preserved_original_unlocated":"冻结内容存在；已查明示路径、采集清单和21个归档库，仍未定位可核验原件；不推断已删除",
                }[status]
            row["processing"] = queue_record(row)
            row["responsible_stage"] = row["processing"]["stage"]
    reviewed = [r for r in rows if r["document_id"] in review_ids]
    issues = integrate_issues(read_lines(args.issues), reviewed)
    for name, values in (("library-bindings.jsonl",rows),("audit-409.jsonl",reviewed),
                         ("library-work-queue.jsonl",[r["processing"] for r in rows]),("library-issues.jsonl",issues)):
        (out/name).write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in values),encoding="utf-8")
    summary.update(parent_audit=str(src),parent_audit_sha256=digest((src/"library-bindings.jsonl").read_bytes()),
        finalizer_implementation_sha256=digest(Path(__file__).read_bytes()),
        prior_issues_sha256=digest(Path(args.issues).read_bytes()),
        queue_stages=dict(Counter(r["processing"]["stage"] for r in rows)),
        materials=len(list(materialized.iterdir())), former_blanket_missing_records_replaced=len(reviewed),
        supersedes_availability_only=True, unchanged_parser_selection=True,
        execution_note="One offline full-library queue; task records are not completed parser jobs or a deployed product queue")
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    write_html(out,reviewed,summary)
    integrity = dict(total=len(rows),unique_ids=len({r["document_id"] for r in rows}),reviewed=len(reviewed),
        old_generic_missing_remaining=sum(r["kind"]=="missing_verified_original" for r in issues),
        unassigned=sum(not r.get("source_id") or not r.get("url") or not r.get("processing",{}).get("stage") for r in rows),
        files={p.name:digest(p.read_bytes()) for p in out.iterdir() if p.is_file()},quality_pass=False)
    assert integrity["total"] == integrity["unique_ids"] == summary["total_bindings"]
    assert integrity["reviewed"] == summary["reviewed_cohort"] and integrity["unassigned"] == 0
    (out/"integrity-final.json").write_text(json.dumps(integrity,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k in ("availability","queue_stages","materials","total_bindings")},ensure_ascii=False))


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("audit","issues","snapshots","output"):
        p.add_argument("--"+name,required=True)
    finalize(p.parse_args())
