from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import trafilatura
from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from ingestion.official_source_capture import (
    OfficialSourceCaptureError,
    TransportFetcher,
    capture_plan,
    materialize_response_body_capture,
    validate_capture_plan,
)
from sec_agent.research_foundation import load_dell_reference_vertical_foundation


PLAN_SCHEMA = "fin_ia_dell_reference_knowledge_package_plan_v1_0"
MANIFEST_SCHEMA = "fin_ia_dell_reference_knowledge_package_manifest_v1_0"
CHUNK_SCHEMA = "fin_ia_dell_reference_knowledge_chunk_v1_0"
KNOWN_BRANCHES = {
    "Q1_ISSUER_TRUTH", "Q2_DEMAND_QUALITY", "Q3_UNITS_ASP_PVM",
    "Q4_ARCHITECTURE_RAMP", "Q5_SUPPLY_AND_PRICE",
    "Q6_MODEL_COMPUTE_DEMAND", "Q7_EXPORT_CONTROL_CHINA",
    "Q8_COMPETITION_VALUE_POOL", "Q9_COUNTEREVIDENCE_WWC",
}
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_foundation_lifecycle_gate(
    *, plan: Mapping[str, Any], sources: list[dict[str, Any]],
) -> None:
    """Bind event-scoped knowledge inputs to the current foundation lifecycle.

    The old implementation rejected every FY2027 Q2 source by matching words in
    route IDs and titles.  That was only valid before the earnings event.  An
    event-scoped source now carries an explicit ``event_id`` and can enter a
    qualification package only when the answer-free foundation contract is
    hash-bound and declares an allowed lifecycle state for that same event.
    """

    event_ids = {
        str(source.get("event_id") or "").strip()
        for source in sources
        if str(source.get("event_id") or "").strip()
    }
    gate = plan.get("foundation_lifecycle_gate")
    if not event_ids:
        if gate is not None:
            raise ValueError("knowledge_lifecycle_gate_without_event_source")
        return
    if not isinstance(gate, Mapping):
        raise ValueError("knowledge_event_lifecycle_gate_missing")

    contract_ref = str(gate.get("foundation_contract_path") or "").strip()
    expected_sha256 = str(gate.get("expected_foundation_sha256") or "").lower()
    special_event = str(gate.get("special_event") or "").strip()
    allowed_states = gate.get("allowed_snapshot_states")
    if not (
        contract_ref
        and len(expected_sha256) == 64
        and all(character in "0123456789abcdef" for character in expected_sha256)
        and special_event
        and isinstance(allowed_states, list)
        and allowed_states
        and all(isinstance(state, str) and state.strip() for state in allowed_states)
        and event_ids == {special_event}
    ):
        raise ValueError("knowledge_event_lifecycle_gate_invalid")

    foundation_path = Path(contract_ref)
    if not foundation_path.is_absolute():
        foundation_path = REPOSITORY_ROOT / foundation_path
    foundation_path = foundation_path.resolve()
    if not foundation_path.is_file():
        raise ValueError("knowledge_foundation_contract_unavailable")
    foundation_bytes = foundation_path.read_bytes()
    if _sha(foundation_bytes) != expected_sha256:
        raise ValueError("knowledge_foundation_contract_sha256_drift")

    foundation = load_dell_reference_vertical_foundation(foundation_path)
    if foundation.case_identity.case_id != str(plan.get("case_id") or ""):
        raise ValueError("knowledge_foundation_case_mismatch")
    if foundation.freshness_contract.special_event != special_event:
        raise ValueError("knowledge_foundation_event_mismatch")
    if foundation.case_identity.current_snapshot_state not in set(allowed_states):
        raise ValueError("knowledge_event_lifecycle_state_invalid")


def load_plan(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != PLAN_SCHEMA:
        raise ValueError("knowledge_plan_schema_invalid")
    if value.get("status") != "qualification_input_not_evidence":
        raise ValueError("knowledge_plan_status_invalid")
    limits = value.get("limits") or {}
    policy = value.get("processing_policy") or {}
    capture = validate_capture_plan(value.get("capture_plan") or {})
    sources = capture["sources"]
    as_of = datetime.fromisoformat(str(value["as_of"]))
    if not 0 < len(sources) <= int(limits.get("max_sources") or 0) <= 20:
        raise ValueError("knowledge_plan_source_limit_invalid")
    if sum(int(s["byte_ceiling"]) for s in sources) > int(
        limits.get("max_total_declared_bytes") or 0
    ):
        raise ValueError("knowledge_plan_byte_limit_invalid")
    if not (
        policy.get("numeric_authority") is False
        and policy.get("search_snippets_admitted") is False
        and policy.get("model_calls") == 0
        and int(limits.get("min_document_chars") or 0) >= 1
        and 0 <= int(limits.get("chunk_overlap_chars") or -1)
        < int(limits.get("chunk_size_chars") or 0)
    ):
        raise ValueError("knowledge_plan_policy_invalid")
    for source in sources:
        required = {
            "title", "publisher", "publication_date", "source_role",
            "document_kind", "branches", "stable_url", "numeric_authority",
        }
        if not required.issubset(source):
            raise ValueError("knowledge_source_metadata_missing")
        branches = source["branches"]
        if not (
            source["stable_url"] == source["url"]
            and source["numeric_authority"] is False
            and source["document_kind"] in {"html", "pdf"}
            and isinstance(branches, list) and branches
            and set(branches) <= KNOWN_BRANCHES
            and datetime.fromisoformat(source["publication_date"]).date()
            <= as_of.date()
        ):
            raise ValueError("knowledge_source_contract_invalid")
    _validate_foundation_lifecycle_gate(
        plan=value, sources=sources,
    )
    value["capture_plan"] = capture
    return value


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _parse(body: bytes, kind: str) -> list[tuple[int | None, str]]:
    if kind == "html":
        text = trafilatura.extract(
            body, include_comments=False, include_tables=True,
            output_format="txt", favor_precision=True,
        )
        normalized = _normalize(text or "")
        if not normalized:
            # Generic mature-parser fallback for table-heavy or SGML-wrapped
            # official HTML (for example, an EDGAR EX-99 document).  This is
            # deliberately not a site- or issuer-specific selector.
            soup = BeautifulSoup(body, "lxml")
            for tag in soup(("script", "style", "noscript", "svg")):
                tag.decompose()
            normalized = _normalize(soup.get_text(separator="\n"))
        return [(None, normalized)]
    reader = PdfReader(io.BytesIO(body), strict=False)
    return [
        (number, _normalize(page.extract_text(extraction_mode="layout") or ""))
        for number, page in enumerate(reader.pages, start=1)
        if _normalize(page.extract_text(extraction_mode="layout") or "")
    ]


def _split(text: str, size: int, overlap: int) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        length_function=len,
        is_separator_regex=False,
    )
    return [chunk.strip() for chunk in splitter.split_text(text) if chunk.strip()]


def _read_response_capture(row: Mapping[str, Any]) -> dict[str, Any]:
    ref = Path(str((row.get("response_capture") or {})["object_ref"]))
    return json.loads(ref.read_text(encoding="utf-8"))


def build_package(
    plan_path: Path, output_root: Path, attempt_id: str, *,
    transport_fetchers: Mapping[str, TransportFetcher] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    plan = load_plan(plan_path)
    capture_result = capture_plan(
        plan["capture_plan"], output_root=output_root,
        attempt_id=attempt_id, transport_fetchers=transport_fetchers,
    )
    root = output_root.resolve() / attempt_id
    config_bytes = _canonical_bytes(plan)
    (root / "input_config.json").write_bytes(config_bytes)
    metadata = {s["route_id"]: s for s in plan["capture_plan"]["sources"]}
    limits = plan["limits"]
    source_rows: list[dict[str, Any]] = []
    chunk_rows: list[dict[str, Any]] = []
    parsed_dir = root / "parsed"
    parsed_dir.mkdir(parents=True, exist_ok=True)
    for captured in capture_result["sources"]:
        route_id = captured["route_id"]
        source = metadata[route_id]
        row = {
            "route_id": route_id, "title": source["title"],
            "publication_date": source["publication_date"],
            "source_role": source["source_role"], "branches": source["branches"],
            "stable_url": source["stable_url"], "numeric_authority": False,
            "capture_status": captured["status"], "status": "typed_failure",
            "failure_code": captured.get("failure_code"),
            "raw_body_bytes": int(captured.get("body_bytes") or 0),
            "raw_body_sha256": captured.get("body_sha256"), "chunk_count": 0,
        }
        if captured["status"] != "captured":
            row["failure_code"] = row["failure_code"] or "source_capture_failed"
            source_rows.append(row)
            continue
        try:
            response = _read_response_capture(captured)
            materialized = materialize_response_body_capture(
                response, output_root=root / "raw_bodies",
            )
            body = Path(materialized["body_path"]).read_bytes()
            units = _parse(body, source["document_kind"])
            total_text = "\n\n".join(text for _, text in units).strip()
            if len(total_text) < int(limits["min_document_chars"]):
                raise ValueError("parsed_body_below_minimum_chars")
            parsed_path = parsed_dir / f"{route_id}.txt"
            parsed_path.write_text(total_text + "\n", encoding="utf-8")
            for page, unit in units:
                for text in _split(
                    unit, int(limits["chunk_size_chars"]),
                    int(limits["chunk_overlap_chars"]),
                ):
                    index = len([c for c in chunk_rows if c["route_id"] == route_id])
                    text_sha = _sha(text.encode("utf-8"))
                    chunk_rows.append({
                        "schema_version": CHUNK_SCHEMA,
                        "chunk_id": _sha(f"{route_id}:{page}:{index}:{text_sha}".encode()),
                        "route_id": route_id, "chunk_index": index, "page": page,
                        "title": source["title"], "publisher": source["publisher"],
                        "publication_date": source["publication_date"],
                        "source_role": source["source_role"], "branches": source["branches"],
                        "stable_url": source["stable_url"], "as_of": plan["as_of"],
                        "numeric_authority": False,
                        "parser": plan["processing_policy"][f"{source['document_kind']}_parser"],
                        "splitter": plan["processing_policy"]["splitter"],
                        "raw_body_sha256": captured["body_sha256"],
                        "text_sha256": text_sha, "text": text,
                    })
            row.update({
                "status": "parsed", "failure_code": None,
                "parsed_text_chars": len(total_text),
                "parsed_text_sha256": _sha((total_text + "\n").encode("utf-8")),
                "parsed_path": parsed_path.as_posix(),
                "raw_body_path": materialized["body_path"],
                "chunk_count": sum(c["route_id"] == route_id for c in chunk_rows),
            })
        except Exception as exc:  # parser boundary: preserve typed failure, do not crawl
            code = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
            row["failure_code"] = f"body_parse_failure:{code}"
        source_rows.append(row)
    chunks_path = root / "chunks.jsonl"
    chunks_data = b"".join(_canonical_bytes(row) for row in chunk_rows)
    chunks_path.write_bytes(chunks_data)
    capture_path = root / "result.json"
    success = sum(row["status"] == "parsed" for row in source_rows)
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "status": "complete" if success == len(source_rows) else "partial" if success else "failed",
        "attempt_id": attempt_id, "case_id": plan["case_id"], "as_of": plan["as_of"],
        "qualification_input_not_evidence": True, "numeric_authority": False,
        "model_calls": 0, "source_count": len(source_rows),
        "parsed_source_count": success, "failed_source_count": len(source_rows) - success,
        "chunk_count": len(chunk_rows),
        "raw_body_bytes": sum(row["raw_body_bytes"] for row in source_rows),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "artifacts": {
            "input_config": {"path": (root / "input_config.json").as_posix(), "sha256": _sha(config_bytes)},
            "capture_result": {"path": capture_path.as_posix(), "sha256": _sha(capture_path.read_bytes())},
            "chunks": {"path": chunks_path.as_posix(), "sha256": _sha(chunks_data), "bytes": len(chunks_data)},
        },
        "sources": source_rows,
    }
    manifest["manifest_payload_sha256"] = _sha(_canonical_bytes(manifest))
    manifest_path = root / "manifest.json"
    manifest_path.write_bytes(_canonical_bytes(manifest))
    manifest["manifest_file_sha256"] = _sha(manifest_path.read_bytes())
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--attempt-id", required=True)
    args = parser.parse_args()
    result = build_package(args.config, args.output_root, args.attempt_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
