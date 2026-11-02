"""Reconcile source availability without equating URL similarity with version identity.

Read-only input stores; explicit roots; no network or product database writes.
The exception checklist is a filtered view of the same full-library ledger.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter, defaultdict
import gzip
import hashlib
import html
import json
from pathlib import Path
import re
import sqlite3
import subprocess
from urllib.parse import urlsplit, unquote, urldefrag
import zlib


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_bytes())


def read_lines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from objects(child)


def raw_hints(metadata, nodes):
    keys = ("raw_body_sha256", "original_pdf_sha256", "raw_sha256", "original_sha256",
            "response_sha256", "download_sha256")
    result = {metadata[k] for k in keys if isinstance(metadata.get(k), str)}
    result.update(n.get("raw_body_sha256", "") for n in nodes)
    acquisition = metadata.get("acquisition_manifest", {})
    if isinstance(acquisition, dict):
        result.add(acquisition.get("sha256", ""))
    visual = metadata.get("visual_verification", {})
    if isinstance(visual, dict):
        result.add(visual.get("original_pdf_sha256", ""))
    return sorted(v.lower() for v in result if re.fullmatch(r"[0-9a-fA-F]{64}", v))


def candidate_relation(metadata, source_url, candidate_url):
    """Reject conflicting regulatory identities, even on a related official domain."""
    expected = metadata.get("document_number")
    numbers = re.findall(r"/(\d{4}-\d{4,6})(?:/|\.|$)", candidate_url)
    if expected and numbers and expected not in numbers:
        return "rejected_document_number_mismatch"
    if source_url == candidate_url:
        return "same_url_version_unverified"
    if expected and expected in numbers:
        return "same_document_alternate_representation"
    source_accession = re.findall(r"/edgar/data/\d+/(\d{18})/", source_url)
    target_accession = re.findall(r"/edgar/data/\d+/(\d{18})/", candidate_url)
    if source_accession and target_accession:
        if source_accession != target_accession:
            return "rejected_accession_mismatch"
        if candidate_url.endswith("/index.json"):
            return "filing_directory_not_document"
    return "unproven_relation"


def select_status(candidates, derivative):
    candidates = [c for c in candidates if not c.get("content_check", {}).get("rejected")]
    exact = [c for c in candidates if c.get("identity") == "exact_raw_digest"]
    if exact:
        return ("derivative_parent_recovered" if derivative else "historical_original_recovered", exact)
    decoded = [c for c in candidates if c.get("identity") == "decoded_readme_digest"]
    if decoded:
        return "readme_api_content_recovered", decoded
    archive = [c for c in candidates if c.get("identity") == "recorded_archive_path"]
    if archive:
        return "recorded_archive_version_unverified", archive
    plausible = [c for c in candidates if c.get("identity") in
                 {"same_url_version_unverified", "explicit_alias_version_unverified", "filename_only"}]
    if plausible:
        return "candidate_version_unverified", plausible
    return "derivative_preserved_original_unlocated", []


def inspect_payload(raw):
    """Content identity signals, never a claim that the whole document is correct."""
    if raw.startswith(b"%PDF"):
        return {"kind": "pdf", "rejected": False}
    text = raw.decode("utf-8", errors="replace")
    titles = re.findall(r"<title\b[^>]*>(.*?)</title>", text, re.I | re.S)
    title = html.unescape(re.sub(r"<[^>]+>", " ", titles[0])).strip() if titles else None
    rejected = bool(title and re.search(r"request access|access denied|just a moment|robot check|403 forbidden|404 not found", title, re.I))
    numbers = sorted(set(re.findall(r"\[FR Doc No:\s*(\d{4}-\d{4,6})\]", text)))
    return {"kind": "text_or_html", "title": title, "rejected": rejected,
            "reason": "access_or_error_page" if rejected else None, "fr_document_numbers": numbers}


def decoded_readme_matches(raw, row):
    try:
        value = json.loads(raw)
        decoded = base64.b64decode(value["content"], validate=False)
        return value.get("html_url") == row["url"] and digest(decoded) == row["source_digest"]
    except (ValueError, KeyError, TypeError):
        return False


def metadata_file_urls(item, field, value, matched_urls):
    """A filing primary and its exhibit are distinct documents in one manifest."""
    paired = "exhibit_url" if field == "local_exhibit_path" else "filing_url" if field == "local_primary_path" else None
    if paired and item.get(paired):
        return {item[paired]} & matched_urls
    if item.get("exhibit_url") and item.get("filing_url"):
        # Historical local_html_path points to the exhibit in this manifest shape.
        # Require the filename pairing instead of applying all URLs to all files.
        name = Path(value).name
        return {u for u in matched_urls if unquote(urlsplit(u).path).split("/")[-1] == name}
    return matched_urls


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=2)


def run(args):
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    manifest = read_json(args.manifest)
    sources = {s["document_id"]: s for s in manifest["sources"]}
    old = {r["document_id"]: r for r in read_json(args.resolution)["rows"]}
    derived = {r["document_id"]: r for r in read_lines(args.derived)}
    bindings = {r["document_id"]: r for r in read_json(args.context)["bindings"]}
    prior = {r["document_id"]: r for r in read_lines(args.bindings)}
    selection = {r["original_id"]: r for r in read_lines(args.selection)}
    related = {r["document_id"]: r for r in read_json(args.related)}
    expected = {k for k, s in sources.items() if s["original_resolution"] != "unique_archived_capture"}
    assert expected == set(old) == set(derived)
    assert set(sources) == set(prior) and set(sources) <= set(bindings)

    rows, findings = {}, []
    with readonly(args.snapshots) as db:
        for key in sorted(expected):
            b, s = bindings[key], sources[key]
            record = db.execute("SELECT snapshot FROM attachment_captures WHERE object_id=?", (b["capture_object_id"],)).fetchone()
            assert record and digest(record[0].encode()) == b["capture_sha256"], key
            bundle = json.loads(record[0])["bundle"]
            src = bundle["source"]
            assert src["id"] == b["source_id"] and src["digest"] == s["source_digest"], key
            meta = src.get("metadata", {})
            if isinstance(meta, str):
                meta = json.loads(meta)
            hints = raw_hints(meta, (bundle.get("node_recovery") or {}).get("nodes", []))
            derivative = bool(meta.get("derivative_source") or meta.get("parent_source_id"))
            payload = None
            text = bundle.get("text", "")
            if digest(text.encode()) == s["source_digest"]:
                try:
                    value = json.loads(text)
                    if isinstance(value, (dict, list)):
                        payload = dict(sha256=s["source_digest"], kind=type(value).__name__,
                            note="persisted structured source payload; not byte-identical HTTP wire response")
                except ValueError:
                    pass
            artifact = Path(args.derived).parent / derived[key]["artifact"]
            assert artifact.is_file(), artifact
            artifact_bytes = artifact.read_bytes()
            parsed = json.loads(gzip.decompress(artifact_bytes))
            # Prior derived artifacts vary in envelope; source identity remains anchored by snapshot.
            assert isinstance(parsed, dict)
            rows[key] = dict(document_id=key, title=s["title"], url=s["url"],
                source_id=b["source_id"], source_digest=s["source_digest"], publisher=urlsplit(s["url"]).netloc,
                subject=meta.get("entity_id") or meta.get("company_id") or meta.get("company"),
                category=meta.get("category") or s.get("category") or s["provisional_family"],
                family=s["provisional_family"], metadata=meta, raw_digest_hints=hints,
                is_derivative=derivative, candidates=[], related_review=[],
                structured_payload=payload,
                captured_at=meta.get("captured_at"), published_at=src.get("published_at"), vintage=src.get("vintage"),
                snapshot=dict(object_id=b["capture_object_id"], sha256=b["capture_sha256"], verified=True),
                current_representation=dict(route=derived[key]["route"], path=str(artifact),
                    sha256=digest(artifact_bytes), source_structure_verified=False),
                prior_availability=s["original_resolution"], quality_pass=False, published=False)
    print(f"Verified {len(rows)} snapshots and derived artifacts", flush=True)

    files, inventory_errors = [], []
    for root in args.search_root:
        result = subprocess.run(["rg", "--files", "-uuu", root], capture_output=True, text=True, encoding="utf-8")
        if result.returncode not in (0, 1) or result.stderr.strip():
            inventory_errors.append(dict(root=root, returncode=result.returncode, stderr=result.stderr[:2000]))
        files.extend(Path(p) for p in result.stdout.splitlines())
    files = sorted(set(files))
    by_name = defaultdict(list)
    for path in files:
        by_name[path.name.lower()].append(path)
    urls = defaultdict(set)
    hints_map = defaultdict(set)
    for key, row in rows.items():
        urls[row["url"]].add(key)
        parsed_url = urlsplit(row["url"])
        if parsed_url.netloc == "github.com" and row["category"] == "repository_readme":
            segments = parsed_url.path.strip("/").split("/")
            if len(segments) >= 4 and segments[2] == "blob":
                urls["https://api.github.com/repos/" + "/".join(segments[:2]) + "/readme"].add(key)
        for field in ("original_download_url", "original_filing_url", "original_url", "origin_url"):
            value = row["metadata"].get(field)
            if isinstance(value, str) and value.startswith("http"):
                urls[value].add(key)
        for hint in row["raw_digest_hints"]:
            hints_map[hint].add(key)
    hashed = {}

    def add_file(key, path, evidence, identity):
        path = Path(path)
        if not path.is_file():
            return
        name = str(path.resolve())
        if name not in hashed:
            data = path.read_bytes()
            hashed[name] = (digest(data), inspect_payload(data))
        sha, check = hashed[name]
        row = rows[key]
        item = dict(path=name, sha256=sha, evidence=evidence, content_check=check,
                    identity="exact_raw_digest" if sha in row["raw_digest_hints"] else identity)
        if item not in row["candidates"]:
            row["candidates"].append(item)

    for key, row in rows.items():
        m = row["metadata"]
        archive = m.get("archive")
        if isinstance(archive, str):
            row["recorded_archive_exists"] = Path(archive).is_file()
            add_file(key, archive, "source.metadata.archive", "recorded_archive_path")
        for c in old[key]["local_candidates"]:
            add_file(key, c["path"], c.get("metadata", "prior URL metadata"), "same_url_version_unverified")
        acquisition = m.get("acquisition_manifest", {})
        raw_file = acquisition.get("raw_file") if isinstance(acquisition, dict) else None
        names = [m.get("download_filename"), raw_file, archive]
        url_name = unquote(urlsplit(row["url"]).path).split("/")[-1]
        if "." in url_name and url_name not in ("index.html", "index.json", "README.md"):
            names.append(url_name)
        for value in names:
            if not isinstance(value, str):
                continue
            for path in by_name.get(Path(value).name.lower(), []):
                add_file(key, path, "matching recorded filename; identity requires digest", "filename_only")

    # Follow persisted URL -> local raw paths. Never infer raw identity from a cleaned-text digest.
    metadata_count, metadata_errors = 0, []
    for path in files:
        if path.suffix != ".json" or not any(t in path.name.lower() for t in ("manifest", "metadata")):
            continue
        if path.stat().st_size > 20_000_000:
            continue
        try:
            data = read_json(path)
        except (ValueError, OSError) as exc:
            metadata_errors.append(dict(path=str(path), error=str(exc)[:200]))
            continue
        metadata_count += 1
        for item in objects(data):
            matched_urls = set(v for k, v in item.items() if isinstance(v, str) and v in urls and
                               k in ("url", "source_url", "filing_url", "exhibit_url", "original_url"))
            if not matched_urls:
                continue
            for field in ("raw_file", "raw_path", "local_path", "local_html_path", "local_primary_path",
                          "local_exhibit_path", "html_path", "pdf_path", "file_path"):
                value = item.get(field)
                if not isinstance(value, str):
                    continue
                # Paired primary/exhibit URLs must not cross-bind.
                selected_urls = metadata_file_urls(item,field,value,matched_urls)
                for url in selected_urls:
                    candidates = [Path(value)] if Path(value).is_absolute() else [path.parent / value, path.parent.parent / value]
                    for key in urls[url]:
                        identity = "same_url_version_unverified" if url == rows[key]["url"] else "explicit_alias_version_unverified"
                        for candidate in candidates:
                            add_file(key, candidate, str(path) + "#" + field, identity)
    print(f"Inventoried {len(files)} paths; read {metadata_count} acquisition metadata files; hashed {len(hashed)} candidates", flush=True)

    db_errors, db_count, capture_matches = [], 0, 0
    payload_checks, github_checks = {}, {}
    db_paths = {Path(manifest["database"])} | {p for p in files if p.suffix.lower() in (".sqlite", ".db", ".sqlite3")}
    for path in sorted(db_paths):
        try:
            with readonly(path) as db:
                columns = {r[1] for r in db.execute("PRAGMA table_info(raw_captures)")}
                if not {"url", "digest", "body_zlib", "status"} <= columns:
                    continue
                db_count += 1
                for url, sha in db.execute("SELECT url,digest FROM raw_captures WHERE status=200"):
                    keys = urls.get(url, set()) | hints_map.get(sha, set())
                    if not keys:
                        continue
                    raw = db.execute("SELECT body_zlib FROM raw_captures WHERE url=? AND digest=?", (url, sha)).fetchone()[0]
                    body = zlib.decompress(raw)
                    if digest(body) != sha:
                        findings.append(dict(kind="raw_capture_digest_mismatch", database=str(path), url=url))
                        continue
                    capture_matches += 1
                    if sha not in payload_checks:
                        payload_checks[sha] = inspect_payload(body)
                    for key in keys:
                        identity = "exact_raw_digest" if sha in rows[key]["raw_digest_hints"] else (
                            "same_url_version_unverified" if url == rows[key]["url"] else "explicit_alias_version_unverified")
                        if url.startswith("https://api.github.com/repos/"):
                            check_key = (key, sha)
                            if check_key not in github_checks:
                                github_checks[check_key] = decoded_readme_matches(body, rows[key])
                            if github_checks[check_key]:
                                identity = "decoded_readme_digest"
                        check = dict(payload_checks[sha])
                        expected_number = rows[key]["metadata"].get("document_number")
                        if expected_number and check.get("fr_document_numbers") and expected_number not in check["fr_document_numbers"]:
                            check.update(rejected=True, reason="body_document_number_mismatch")
                        rows[key]["candidates"].append(dict(database=str(path), url=url, sha256=sha, identity=identity, content_check=check,
                            evidence="verified raw_captures body_zlib"))
        except (sqlite3.Error, OSError, zlib.error) as exc:
            db_errors.append(dict(path=str(path), error=str(exc)[:250]))

    for key, row in rows.items():
        for candidate in related.get(key, {}).get("related_original", []):
            row["related_review"].append(dict(**candidate, verdict=candidate_relation(row["metadata"], row["url"], candidate["url"]),
                content_check=payload_checks.get(candidate["digest"], {"kind":"not_reread"})))
        # Repeated copies across historical databases are one candidate with many locators.
        grouped = {}
        for c in row["candidates"]:
            ck = (c["sha256"], c["identity"], c.get("url"), c.get("path"))
            if ck not in grouped:
                grouped[ck] = dict(c, replica_databases=[])
            if c.get("database"):
                grouped[ck]["replica_databases"].append(c["database"])
        row["candidates"] = list(grouped.values())
        row["availability"], selected = select_status(row["candidates"], row["is_derivative"])
        if row["structured_payload"] and row["availability"] in ("candidate_version_unverified", "derivative_preserved_original_unlocated"):
            row["availability"] = "structured_payload_preserved"
        row["selected_originals"] = selected
        row["original_id"] = selected[0]["sha256"] if row["availability"] == "historical_original_recovered" and len({c["sha256"] for c in selected}) == 1 else None
        row["responsible_stage"] = "source_acquisition_and_lineage"
        row["next_action"] = {
            "historical_original_recovered": "送入同一解析队列，保留原件摘要；本次找回不等于解析质量通过",
            "readme_api_content_recovered": "API封装内README解码后与历史源摘要一致；按Markdown路线处理并保留Git对象身份",
            "structured_payload_preserved": "已有完整序列化结构化载荷；沿JSON/SQL路径检查主体、期间、单位和修订，不再当作缺网页正文",
            "derivative_parent_recovered": "登记衍生资料到原件关系，核对摘录范围；不得将父原件当成衍生资料自身版本",
            "recorded_archive_version_unverified": "已有采集记录直指文件；缺少历史原件摘要，补采集记录或内容版本核验",
            "candidate_version_unverified": "核对候选文件与历史文本、采集时间和版本；不能仅按同URL或同名自动替换",
            "derivative_preserved_original_unlocated": "保留现有文本/节点及来源身份；按采集任务查档，必要时另建新版本获取原件",
        }[row["availability"]]
        row["subject_status"] = "recorded" if row["subject"] else "source_identified_subject_not_recorded"
        row["source_relationships"] = []
        base_url, fragment = urldefrag(row["url"])
        if fragment:
            matches = [s["document_id"] for s in sources.values() if s["url"] == base_url]
            row["source_relationships"].append(dict(kind="fragment_points_to_parent_source", url=base_url, fragment=fragment,
                library_document_ids=matches, historical_version_proven=row["availability"] == "derivative_parent_recovered"))
        if row["availability"] == "derivative_preserved_original_unlocated":
            if row["is_derivative"] or fragment or "page" in str(row["metadata"].get("capture_scope", "")).lower():
                row["gap_class"] = "scoped_transcription_requires_parent_identity"
            elif row["current_representation"]["route"] == "existing_recovered_nodes_only":
                row["gap_class"] = "legacy_nodes_without_raw_capture_receipt"
            else:
                row["gap_class"] = "persisted_text_without_located_raw_capture"
        else:
            row["gap_class"] = row["availability"]
        row["review_scope"] = "snapshot/digest/path/acquisition/related-identity audit; not manual full-document quality approval"

    all_rows = []
    for key, source in sources.items():
        if key in rows:
            row = rows[key]
        else:
            p = prior[key]
            sel = selection[p["original_id"]]
            row = dict(document_id=key, title=source["title"], url=source["url"], source_id=bindings[key]["source_id"],
                source_digest=source["source_digest"], publisher=urlsplit(source["url"]).netloc,
                availability="archived_original_existing", original_id=p["original_id"],
                current_representation=sel, responsible_stage="document_structure_quality",
                next_action="沿全库解析质量清单继续审核", quality_pass=False, published=False)
        row["schema_version"] = "library-binding-lineage.v1"
        row["audit_cohort"] = "former_409" if key in rows else "existing_1333"
        all_rows.append(row)
    assert len(all_rows) == manifest["source_bindings"] == len({r["document_id"] for r in all_rows})
    assert all(r["source_id"] and r["url"] and r["responsible_stage"] and r["next_action"] for r in all_rows)
    summary = dict(total_bindings=len(all_rows), reviewed_cohort=len(rows), unchanged_existing_bindings=len(all_rows)-len(rows),
        availability=dict(Counter(r["availability"] for r in rows.values())),
        related_verdicts=dict(Counter(c["verdict"] for r in rows.values() for c in r["related_review"])),
        gap_classes=dict(Counter(r["gap_class"] for r in rows.values())),
        rejected_candidate_bindings=sum(any(c.get("content_check",{}).get("rejected") for c in r["candidates"]) for r in rows.values()),
        snapshot_verified=len(rows), derivative_artifacts_verified=len(rows),
        inventory_paths=len(files), metadata_files=metadata_count, hashed_candidate_files=len(hashed),
        capture_databases=db_count, capture_matches=capture_matches, inventory_errors=inventory_errors,
        metadata_errors=metadata_errors, database_errors=db_errors, findings=findings,
        quality_pass=False, published=False, model_calls=0, downloads=0,
        scope="Explicit local roots and recorded aliases; unlocated does not prove absence on the whole machine",
        inputs={name:dict(path=str(getattr(args,name)),sha256=digest(Path(getattr(args,name)).read_bytes()))
                for name in ("manifest","resolution","derived","context","bindings","selection","related")},
        search_roots=args.search_root)
    summary["implementation_sha256"] = digest(Path(__file__).read_bytes())
    for name, data in (("library-bindings.jsonl", all_rows), ("audit-409.jsonl", list(rows.values()))):
        (out/name).write_text("".join(json.dumps(r, ensure_ascii=False)+"\n" for r in data), encoding="utf-8")
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    write_html(out, list(rows.values()), summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ("inputs","metadata_errors","database_errors")},ensure_ascii=False), flush=True)


def write_html(out, rows, summary):
    labels = {"historical_original_recovered":"历史原件摘要匹配", "derivative_parent_recovered":"找到衍生资料父原件",
        "readme_api_content_recovered":"README原始内容已找回", "structured_payload_preserved":"结构化载荷完整保存",
        "recorded_archive_version_unverified":"采集路径文件存在，版本待核", "candidate_version_unverified":"找到候选，版本待核",
        "derivative_preserved_original_unlocated":"现有内容已归档，历史原件待定位"}
    parts = []
    esc = lambda value: html.escape(str(value or "未记录"))
    for i, r in enumerate(rows, 1):
        candidates = "<br>".join(esc(c.get("path") or c.get("database"))+" · "+esc(c["identity"])+" · "+esc(c["sha256"])+(" · 已拒绝："+esc(c["content_check"].get("reason")) if c.get("content_check",{}).get("rejected") else "") for c in r["candidates"])
        related = "<br>".join(esc(c["verdict"])+" · "+esc(c["url"]) for c in r["related_review"])
        detail = json.dumps({k:r[k] for k in ("metadata","snapshot","current_representation","raw_digest_hints",
            "source_relationships","processing","recovered_content","git_blob_identity") if k in r}, ensure_ascii=False, indent=2)
        parts.append(f'<tr><td>{i}</td><td><b>{esc(r["title"])}</b><p>{esc(r["document_id"])}</p><a href="{html.escape(r["url"],quote=True)}">原始来源链接</a><p>{esc(r["source_id"])}</p></td><td>{esc(r["publisher"])}<p>{esc(r["subject"])}</p>{esc(r["category"])}</td><td>{esc(labels[r["availability"]])}<p>{esc(r.get("audit_reason", "见版本与采集证据"))}</p><p>{esc(r["next_action"])}</p></td><td>{candidates or "未找到可核验原件候选"}<p>{related}</p><details><summary>版本、内容位置及采集证据</summary><pre>{esc(detail)}</pre></details></td></tr>')
    page = '<!doctype html><meta charset="utf-8"><title>409条来源审核清单</title><style>body{font:14px system-ui;margin:28px;color:#263247}table{border-collapse:collapse;width:100%;table-layout:fixed}td,th{border:1px solid #dbe1e8;padding:10px;vertical-align:top;overflow-wrap:anywhere}th{background:#edf2f8;position:sticky;top:0}td:first-child{width:3%}pre{white-space:pre-wrap}input{padding:12px;width:65%}p{margin:7px 0;color:#526174}</style>'
    page += '<h1>409条来源审核清单 · 全库1742条的筛选视图</h1><p>本页与 library-bindings.jsonl 来自同一次生成。来源归属、原件可得性、解析质量分别记录。没有把候选或今天的新版本冒充历史原件；本轮没有下载、调用模型或发布产品。</p>'
    page += '<pre>'+html.escape(json.dumps({labels[k]:v for k,v in summary["availability"].items()},ensure_ascii=False,indent=2))+'</pre><input id="q" placeholder="搜索标题、公司、状态、ID、证据路径"><span id="count"></span><table><thead><tr><th style="width:3%">序号</th><th style="width:23%">资料与稳定身份</th><th style="width:13%">来源与主体</th><th style="width:20%">状态及处置</th><th>候选与审核证据</th></tr></thead><tbody>'+''.join(parts)+'</tbody></table><script>q.oninput=()=>{let n=0;document.querySelectorAll("tbody tr").forEach(r=>{r.hidden=!r.textContent.toLowerCase().includes(q.value.toLowerCase());if(!r.hidden)n++});count.textContent=" 显示 "+n+" / 409"};q.oninput();</script>'
    (out/"audit-409.html").write_text(page,encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest","resolution","derived","context","snapshots","bindings","selection","related","output"):
        parser.add_argument("--"+name,required=True)
    parser.add_argument("--search-root",action="append",required=True)
    run(parser.parse_args())
