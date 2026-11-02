"""Freeze a usable current corpus, excluding invalid bodies without rewriting history.

Raw-version identity and parser-recipe identity are independent. Uncertain historical
equivalence does not prevent a proven current source from entering a new baseline.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import zlib

from audit_source_binding_lineage import digest, inspect_payload, read_json, read_lines, readonly


def body_check(raw):
    if not raw.strip():
        return dict(rejected=True, reason="empty_body")
    result = inspect_payload(raw)
    if not result["rejected"] and raw.lstrip().startswith(b"{"):
        try:
            value = json.loads(raw)
            if set(value) <= {"message", "documentation_url", "status"} and value.get("message") in (
                "Not Found", "Bad credentials", "Requires authentication", "API rate limit exceeded"):
                return dict(rejected=True,reason="api_error_envelope")
        except (ValueError, TypeError):
            pass
    return result


def preferred(candidates):
    """No filename-only selection, no choosing arbitrarily between conflicting bytes."""
    strength = {"exact_raw_digest":0,"recorded_archive_path":1,"same_url_version_unverified":2,
                "explicit_alias_version_unverified":3}
    eligible = [c for c in candidates if c.get("identity") in strength and not c.get("check",{}).get("rejected")]
    if not eligible:
        return None, "no_verified_current_source"
    best = min(strength[c["identity"]] for c in eligible)
    pool = [c for c in eligible if strength[c["identity"]] == best]
    hashes = {c["current_sha256"] for c in pool}
    if len(hashes) == 1:
        return sorted(pool,key=lambda c:json.dumps(c,sort_keys=True))[0], "unique_current_content"
    # Capture timestamps identify versions; a tie is not permission to pick one.
    dated = [c for c in pool if c.get("captured_at")]
    if len({c["current_sha256"] for c in dated}) == len(hashes):
        newest = max(c["captured_at"] for c in dated)
        last = [c for c in dated if c["captured_at"] == newest]
        if len({c["current_sha256"] for c in last}) == 1:
            return last[0], "latest_recorded_capture_new_baseline"
    return None, "conflicting_current_versions"


def run(args):
    source, output = Path(args.audit), Path(args.output)
    output.mkdir(parents=True,exist_ok=False)
    baseline_id = output.parent.name + "/" + output.name
    rows = read_lines(source/"library-bindings.jsonl")
    manifest = read_json(args.manifest)
    job_by_binding = {bid:j for j in manifest["jobs"] for bid in j["bindings"]}
    metadata_by_binding = {s["document_id"]:s for s in manifest["sources"]}
    snapshots = {b["document_id"]:b for b in read_json(args.context)["bindings"]}
    checked, excluded, unavailable, changes, artifact_changes = {}, {}, [], [], []
    parser_code = {str(p.relative_to(Path(args.repo))):digest(p.read_bytes()) for p in
        (Path(args.repo)/"scripts/engineering").glob("*.py") if any(word in p.name for word in
        ("native_", "source_heading", "source_part", "section_alignment", "source_signature", "source_role", "prechunk"))}

    def inspect(candidate):
        loc = (candidate.get("path"),candidate.get("database"),candidate.get("url"),candidate.get("sha256"))
        if loc in checked:
            return checked[loc]
        result = dict(candidate)
        try:
            if candidate.get("path"):
                raw = Path(candidate["path"]).read_bytes()
            else:
                with readonly(candidate["database"]) as db:
                    value = db.execute("SELECT body_zlib,captured_at,digest FROM raw_captures WHERE url=?",(candidate["url"],)).fetchone()
                if not value:
                    raise ValueError("capture_missing")
                raw = zlib.decompress(value[0])
                result["captured_at"] = value[1]
                result["store_digest"] = value[2]
            sha = digest(raw)
            result.update(current_sha256=sha, bytes=len(raw), check=body_check(raw),
                          changed_since_audit=sha!=candidate["sha256"])
            if result.get("store_digest") and sha != result["store_digest"]:
                raise ValueError("capture_store_integrity_failure")
            if result["changed_since_audit"]:
                changes.append(dict(locator=loc,previous_sha256=candidate["sha256"],current_sha256=sha))
                # Historical raw-digest proof no longer applies to changed content.
                if result.get("identity")=="exact_raw_digest":
                    result["identity"]="same_url_version_unverified" if candidate.get("url") else "recorded_archive_path"
            if result["check"].get("rejected"):
                excluded.setdefault(sha,dict(sha256=sha,reason=result["check"]["reason"],
                    title=result["check"].get("title"),locators=[],bindings=[]))["locators"].append(dict(locator=loc))
            checked[loc] = result
            return result
        except (OSError, ValueError, sqlite3.Error, zlib.error) as exc:
            failure=dict(locator=loc,error=str(exc)[:200])
            unavailable.append(failure)
            result.update(check=dict(rejected=True,reason="unavailable_not_invalid"),failure=failure)
            checked[loc]=result
            return result

    results, plans = [], []
    with readonly(args.snapshots) as snapshot_db:
        for index, old in enumerate(rows,1):
            row = dict(old)
            key = row["document_id"]
            binding = snapshots[key]
            snapshot = snapshot_db.execute("SELECT snapshot FROM attachment_captures WHERE object_id=?",
                                           (binding["capture_object_id"],)).fetchone()
            if not snapshot or digest(snapshot[0].encode()) != binding["capture_sha256"]:
                raise ValueError("Frozen source snapshot changed: " + key)
            bundle = json.loads(snapshot[0])["bundle"]
            # Library text is independently checked: a bad alternative must not delete a good source.
            content = bundle.get("text", "")
            if not content:
                nodes=(bundle.get("node_recovery") or {}).get("nodes",[])
                content="\n".join(str(n.get("text") or n.get("content") or "") for n in nodes)
            text_check = body_check(content.encode()) if content.strip() else {"rejected":False,"reason":"node_representation_requires_review"}
            candidates = []
            if key in job_by_binding:
                job=job_by_binding[key]
                candidates.append(dict(database=manifest["database"],url=job["url"],sha256=job["id"],identity="exact_raw_digest"))
            candidates += row.get("candidates",[])
            # Include rejected related captures in the exclusion ledger, not in selection.
            for c in row.get("related_review",[]):
                check = inspect(dict(database=manifest["database"],url=c["url"],sha256=c["digest"],identity="related_only"))
                if check.get("current_sha256") in excluded:
                    excluded[check["current_sha256"]]["bindings"].append(key)
            verified = []
            for c in candidates:
                check=inspect(c)
                if check.get("current_sha256") in excluded:
                    excluded[check["current_sha256"]]["bindings"].append(key)
                expected_number = row.get("metadata",{}).get("document_number")
                numbers = check["check"].get("fr_document_numbers",[])
                wrong_document = bool(expected_number and numbers and expected_number not in numbers)
                if not check["check"].get("rejected") and not wrong_document:
                    verified.append(check)
            current, reason = preferred(verified)
            artifact = row.get("current_representation",{})
            artifact_path = artifact.get("selected_artifact") or artifact.get("path")
            artifact_expected = artifact.get("selected_sha256") or artifact.get("sha256")
            artifact_intact = bool(artifact_path and Path(artifact_path).is_file() and digest(Path(artifact_path).read_bytes())==artifact_expected)
            if artifact_path and not artifact_intact:
                artifact_changes.append(dict(document_id=key,path=artifact_path,expected_sha256=artifact_expected,
                                             decision="do_not_reuse_changed_or_missing_parser_output"))
            recovered = row.get("recovered_content")
            recovered_intact = bool(recovered and Path(recovered["path"]).is_file() and digest(Path(recovered["path"]).read_bytes())==recovered["sha256"])
            invalid_original = key in job_by_binding and any(c.get("current_sha256") in excluded for c in map(inspect,candidates[:1]))
            row["baseline_id"] = baseline_id
            row["history"] = dict(parent_availability=old["availability"],parent_original_id=old.get("original_id"),
                                   prior_parser_artifact=artifact,source_snapshot_sha256=binding["capture_sha256"])
            row["candidates"] = verified
            row["related_review"] = [c for c in row.get("related_review",[]) if not c.get("content_check",{}).get("rejected")]
            row.pop("selected_originals",None)
            row["source_version_decision"] = reason
            row["current_source"] = current
            row["historical_same_version_proven"] = bool(current and current["identity"]=="exact_raw_digest" and not current["changed_since_audit"])
            row["quality_pass"] = False
            if recovered_intact:
                row["active"] = True
                row["current_source"] = dict(path=recovered["path"],current_sha256=recovered["sha256"],identity="verified_saved_content")
                stage = "native_markdown_parse" if old["availability"]=="readme_api_content_recovered" else "structured_record_validation"
                reuse = False
            elif current and not old.get("is_derivative"):
                row["active"] = True
                reuse = bool(artifact_intact and old.get("original_id")==current["current_sha256"] and key in job_by_binding)
                stage = "continue_structure_quality" if reuse else "parse_current_original"
            elif invalid_original or text_check.get("rejected"):
                row["active"] = False
                stage, reuse = "excluded_invalid_body", False
            else:
                row["active"] = True
                stage, reuse = "derived_content_processing", artifact_intact
                row["source_limit"] = "Only preserved derived content; original completeness/version not established"
                if old.get("is_derivative") and current:
                    row["parent_original"] = current
                    row["current_source"] = None
            row["current_parser_artifact"] = artifact if reuse else None
            # Current queue no longer waits for historical equivalence when current source is proven.
            plan=dict(document_id=key,source_id=row["source_id"],baseline_id=baseline_id,stage=stage,
                current_source=row["current_source"],reuse_validated_adaptation=reuse,
                current_parser_artifact=row["current_parser_artifact"],state="ready" if row["active"] else "removed",
                route=metadata_by_binding[key]["provisional_family"],historical_review_blocks_processing=False)
            row["processing"] = plan
            row["responsible_stage"] = stage
            results.append(row);plans.append(plan)
            if index%100==0:
                print(json.dumps(dict(processed=index,excluded_bindings=sum(not r["active"] for r in results),
                                     unique_invalid_bodies=len(excluded))),flush=True)
    for entry in excluded.values():
        entry["bindings"] = sorted(set(entry["bindings"]))
    assert len(results)==len({r["document_id"] for r in results})==len(rows)
    for r in results:
        assert not r.get("current_source") or not r["current_source"].get("check",{}).get("rejected")
    for filename,values in (("library-bindings.jsonl",results),("active-library.jsonl",[r for r in results if r["active"]]),
        ("parse-plan.jsonl",[p for p in plans if p["state"]=="ready"]),("excluded-bodies.jsonl",list(excluded.values())),
        ("version-changes.jsonl",changes),("unavailable-locators.jsonl",unavailable)):
        (output/filename).write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in values),encoding="utf-8")
    summary=dict(baseline_id=baseline_id,created_at=datetime.now(timezone.utc).isoformat(),total_bindings=len(results),
        active_bindings=sum(r["active"] for r in results),excluded_bindings=sum(not r["active"] for r in results),
        unique_invalid_bodies=len(excluded),invalid_candidate_bindings=len({b for e in excluded.values() for b in e["bindings"]}),
        current_stages=dict(Counter(p["stage"] for p in plans)),actual_raw_byte_changes=len(changes),
        parser_artifact_changes=artifact_changes,
        unavailable_locators=len(unavailable),unmodified_historical_stores=True,quality_pass=False,
        parser_recipe_sha256=parser_code,parent_ledger_sha256=digest((source/"library-bindings.jsonl").read_bytes()),
        implementation_sha256=digest(Path(__file__).read_bytes()),provider_calls=0)
    (output/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k!='parser_recipe_sha256'},ensure_ascii=False),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("audit","manifest","context","snapshots","repo","output"):
        p.add_argument("--"+name,required=True)
    run(p.parse_args())
