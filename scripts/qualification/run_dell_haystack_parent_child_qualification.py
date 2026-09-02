from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable, Sequence

from haystack import Document
from haystack.components.preprocessors import HierarchicalDocumentSplitter
from haystack.components.retrievers import AutoMergingRetriever
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack.document_stores.types import DuplicatePolicy
from rank_bm25 import BM25Okapi


MANIFEST_SCHEMA = "fin_ia_dell_haystack_parent_child_qualification_manifest_v1_1"
RESULT_SCHEMA = "fin_ia_dell_haystack_parent_child_qualification_result_v1_1"
QUERY_RESULT_SCHEMA = "fin_ia_dell_haystack_parent_child_query_result_v1_1"
DELIVERY_CAP_CHARACTERS = 1_200
LEGACY_TOKEN_PATTERN = r"[a-z0-9][a-z0-9&'/-]*"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
BRANCH_PATTERN = re.compile(r"^[A-Z0-9_]+$")


class QualificationError(ValueError):
    """Raised when frozen inputs or qualification invariants drift."""


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _write_bytes_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _write_json_exclusive(path: Path, value: Any) -> None:
    _write_bytes_exclusive(path, _pretty_json_bytes(value))


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QualificationError(f"json_unreadable:{path}") from exc
    if not isinstance(value, dict):
        raise QualificationError(f"json_root_not_object:{path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for ordinal, line in enumerate(stream, start=1):
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise QualificationError(
                        f"jsonl_row_invalid:{path}:{ordinal}"
                    ) from exc
                if not isinstance(value, dict):
                    raise QualificationError(
                        f"jsonl_row_not_object:{path}:{ordinal}"
                    )
                rows.append(value)
    except (OSError, UnicodeError) as exc:
        raise QualificationError(f"jsonl_unreadable:{path}") from exc
    if not rows:
        raise QualificationError(f"jsonl_empty:{path}")
    return rows


def _resolve_file(path_value: str | Path, *, label: str) -> Path:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise QualificationError(f"{label}_not_file:{path}")
    return path


def _resolve_directory(path_value: str | Path, *, label: str) -> Path:
    path = Path(path_value).expanduser().resolve()
    if not path.is_dir():
        raise QualificationError(f"{label}_not_directory:{path}")
    return path


def _require_within(path: Path, root: Path, *, label: str) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise QualificationError(f"{label}_outside_attempt_root:{path}") from exc


def _require_sha256(value: Any, *, label: str) -> str:
    normalized = str(value or "").strip().lower()
    if not SHA256_PATTERN.fullmatch(normalized):
        raise QualificationError(f"{label}_not_sha256")
    return normalized


def _require_string(value: Any, *, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise QualificationError(f"{label}_empty")
    return normalized


def _normalize_branches(value: Any, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise QualificationError(f"{label}_not_list")
    branches = tuple(str(item).strip() for item in value)
    if (
        not branches
        or any(not BRANCH_PATTERN.fullmatch(item) for item in branches)
        or len(set(branches)) != len(branches)
    ):
        raise QualificationError(f"{label}_invalid")
    return branches


def _tokenize(text: str) -> list[str]:
    return re.findall(LEGACY_TOKEN_PATTERN, text.lower())


def _percentile(values: Sequence[float | int], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _summary(values: Sequence[float | int]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "min": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0, "mean": 0.0}
    return {
        "count": len(values),
        "min": min(values),
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "max": max(values),
        "mean": mean(values),
    }


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _rss_bytes() -> int | None:
    if os.name != "nt":
        try:
            import resource

            value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            return value if sys.platform == "darwin" else value * 1024
        except (ImportError, OSError, ValueError):
            return None
    try:
        counters = _ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        process = kernel32.GetCurrentProcess()
        success = psapi.GetProcessMemoryInfo(
            process,
            ctypes.byref(counters),
            counters.cb,
        )
        return int(counters.WorkingSetSize) if success else None
    except (AttributeError, OSError, ValueError):
        return None


def _git_metadata(repo_root: Path) -> dict[str, Any]:
    def run(*arguments: str) -> str:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=repo_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        return completed.stdout.strip()

    try:
        status_lines = [line for line in run("status", "--short").splitlines() if line]
        return {
            "branch": run("branch", "--show-current"),
            "head": run("rev-parse", "HEAD"),
            "dirty": bool(status_lines),
            "status_lines": status_lines,
        }
    except (OSError, subprocess.CalledProcessError):
        return {"branch": None, "head": None, "dirty": None, "status_lines": []}


def _validate_artifact_reference(
    *,
    artifact: dict[str, Any],
    attempt_root: Path,
    label: str,
) -> dict[str, Any]:
    path = _resolve_file(_require_string(artifact.get("path"), label=f"{label}_path"), label=label)
    _require_within(path, attempt_root, label=label)
    expected = _require_sha256(artifact.get("sha256"), label=f"{label}_expected_digest")
    observed = _sha256_file(path)
    if observed != expected:
        raise QualificationError(f"{label}_digest_drift:{path}")
    return {"path": path.as_posix(), "sha256": observed, "bytes": path.stat().st_size}


def _validate_attempt(attempt_root_value: str | Path) -> dict[str, Any]:
    attempt_root = _resolve_directory(attempt_root_value, label="knowledge_attempt_root")
    manifest_path = _resolve_file(attempt_root / "manifest.json", label="knowledge_manifest")
    manifest = _load_json(manifest_path)
    attempt_id = _require_string(manifest.get("attempt_id"), label="attempt_id")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise QualificationError(f"manifest_artifacts_invalid:{attempt_id}")
    validated_artifacts: dict[str, Any] = {}
    for artifact_name in ("capture_result", "chunks", "input_config"):
        artifact = artifacts.get(artifact_name)
        if not isinstance(artifact, dict):
            raise QualificationError(f"manifest_artifact_missing:{attempt_id}:{artifact_name}")
        validated_artifacts[artifact_name] = _validate_artifact_reference(
            artifact=artifact,
            attempt_root=attempt_root,
            label=f"{attempt_id}_{artifact_name}",
        )

    chunks_path = Path(validated_artifacts["chunks"]["path"])
    if chunks_path != (attempt_root / "chunks.jsonl").resolve():
        raise QualificationError(f"chunks_path_not_attempt_local:{attempt_id}")
    chunks = _load_jsonl(chunks_path)

    source_rows = manifest.get("sources")
    if not isinstance(source_rows, list):
        raise QualificationError(f"manifest_sources_invalid:{attempt_id}")
    parsed_sources: dict[str, dict[str, Any]] = {}
    raw_body_digests: set[str] = set()
    for source_ordinal, source in enumerate(source_rows, start=1):
        if not isinstance(source, dict):
            raise QualificationError(f"manifest_source_not_object:{attempt_id}:{source_ordinal}")
        if source.get("status") != "parsed":
            continue
        route_id = _require_string(source.get("route_id"), label="source_route_id")
        if route_id in parsed_sources:
            raise QualificationError(f"duplicate_parsed_route:{route_id}")
        parsed_path = _resolve_file(
            _require_string(source.get("parsed_path"), label=f"{route_id}_parsed_path"),
            label=f"{route_id}_parsed",
        )
        raw_body_path = _resolve_file(
            _require_string(source.get("raw_body_path"), label=f"{route_id}_raw_body_path"),
            label=f"{route_id}_raw_body",
        )
        _require_within(parsed_path, attempt_root, label=f"{route_id}_parsed")
        _require_within(raw_body_path, attempt_root, label=f"{route_id}_raw_body")
        parsed_digest = _require_sha256(
            source.get("parsed_text_sha256"), label=f"{route_id}_parsed_digest"
        )
        raw_digest = _require_sha256(
            source.get("raw_body_sha256"), label=f"{route_id}_raw_digest"
        )
        if _sha256_file(raw_body_path) != raw_digest:
            raise QualificationError(f"raw_body_digest_drift:{route_id}")
        parsed_text = parsed_path.read_text(encoding="utf-8")
        if not parsed_text.strip():
            raise QualificationError(f"parsed_text_empty:{route_id}")
        # The producer records the digest of the normalized text value.  On
        # Windows, Path.write_text can materialize that value with CRLF bytes,
        # so the on-disk byte digest is not the semantic parsed-text digest.
        if _sha256_bytes(parsed_text.encode("utf-8")) != parsed_digest:
            raise QualificationError(f"parsed_text_digest_drift:{route_id}")
        expected_parsed_chars = int(source.get("parsed_text_chars") or -1)
        observed_contract_chars = len(parsed_text) - 1 if parsed_text.endswith("\n") else len(parsed_text)
        if observed_contract_chars != expected_parsed_chars:
            raise QualificationError(f"parsed_text_character_count_drift:{route_id}")
        branches = _normalize_branches(source.get("branches"), label=f"{route_id}_branches")
        parsed_sources[route_id] = {
            "attempt_id": attempt_id,
            "attempt_root": attempt_root.as_posix(),
            "route_id": route_id,
            "title": _require_string(source.get("title"), label=f"{route_id}_title"),
            "source_url": _require_string(source.get("stable_url"), label=f"{route_id}_stable_url"),
            "source_role": _require_string(source.get("source_role"), label=f"{route_id}_source_role"),
            "publication_date": _require_string(
                source.get("publication_date"), label=f"{route_id}_publication_date"
            ),
            "branches": branches,
            "raw_body_path": raw_body_path.as_posix(),
            "raw_body_sha256": raw_digest,
            "raw_body_bytes": raw_body_path.stat().st_size,
            "parsed_path": parsed_path.as_posix(),
            "parsed_text": parsed_text,
            "parsed_text_sha256": parsed_digest,
            "parsed_text_chars": len(parsed_text),
            "expected_chunk_count": int(source.get("chunk_count") or 0),
        }
        raw_body_digests.add(raw_digest)

    chunk_counts: Counter[str] = Counter()
    chunk_indexes: defaultdict[str, list[int]] = defaultdict(list)
    seen_chunk_ids: set[str] = set()
    for chunk_ordinal, chunk in enumerate(chunks, start=1):
        route_id = _require_string(chunk.get("route_id"), label=f"chunk_route:{chunk_ordinal}")
        source = parsed_sources.get(route_id)
        if source is None:
            raise QualificationError(f"chunk_route_not_parsed:{attempt_id}:{route_id}")
        chunk_id = _require_string(chunk.get("chunk_id"), label=f"chunk_id:{chunk_ordinal}")
        if chunk_id in seen_chunk_ids:
            raise QualificationError(f"duplicate_chunk_id:{chunk_id}")
        seen_chunk_ids.add(chunk_id)
        text = _require_string(chunk.get("text"), label=f"chunk_text:{chunk_id}")
        text_digest = _require_sha256(chunk.get("text_sha256"), label=f"chunk_text_digest:{chunk_id}")
        if _sha256_bytes(text.encode("utf-8")) != text_digest:
            raise QualificationError(f"chunk_text_digest_drift:{chunk_id}")
        raw_digest = _require_sha256(chunk.get("raw_body_sha256"), label=f"chunk_raw_digest:{chunk_id}")
        if raw_digest != source["raw_body_sha256"]:
            raise QualificationError(f"chunk_raw_digest_mismatch:{chunk_id}")
        branches = _normalize_branches(chunk.get("branches"), label=f"chunk_branches:{chunk_id}")
        if branches != source["branches"]:
            raise QualificationError(f"chunk_branch_drift:{chunk_id}")
        if _require_string(chunk.get("stable_url"), label=f"chunk_url:{chunk_id}") != source["source_url"]:
            raise QualificationError(f"chunk_source_url_drift:{chunk_id}")
        chunk_index = chunk.get("chunk_index")
        if not isinstance(chunk_index, int) or isinstance(chunk_index, bool) or chunk_index < 0:
            raise QualificationError(f"chunk_index_invalid:{chunk_id}")
        chunk_counts[route_id] += 1
        chunk_indexes[route_id].append(chunk_index)

    for route_id, source in parsed_sources.items():
        observed_count = chunk_counts[route_id]
        if observed_count != source["expected_chunk_count"]:
            raise QualificationError(f"route_chunk_count_drift:{route_id}")
        if sorted(chunk_indexes[route_id]) != list(range(observed_count)):
            raise QualificationError(f"route_chunk_index_not_contiguous:{route_id}")
    manifest_chunk_count = int(manifest.get("chunk_count") or -1)
    if len(chunks) != manifest_chunk_count:
        raise QualificationError(f"manifest_chunk_count_drift:{attempt_id}")

    return {
        "attempt_root": attempt_root,
        "attempt_id": attempt_id,
        "manifest_path": manifest_path,
        "manifest_sha256": _sha256_file(manifest_path),
        "manifest": manifest,
        "validated_artifacts": validated_artifacts,
        "sources": parsed_sources,
        "chunks": chunks,
        "raw_body_digest_count": len(raw_body_digests),
    }


def _merge_validated_attempts(
    attempts: Sequence[dict[str, Any]],
    *,
    expected_flat_records: int,
    expected_parsed_routes: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    sources: dict[str, dict[str, Any]] = {}
    chunks: list[dict[str, Any]] = []
    chunk_ids: set[str] = set()
    for attempt in attempts:
        for route_id, source in attempt["sources"].items():
            if route_id in sources:
                raise QualificationError(f"cross_attempt_duplicate_route:{route_id}")
            sources[route_id] = source
        for chunk in attempt["chunks"]:
            chunk_id = str(chunk["chunk_id"])
            if chunk_id in chunk_ids:
                raise QualificationError(f"cross_attempt_duplicate_chunk:{chunk_id}")
            chunk_ids.add(chunk_id)
            chunks.append(chunk)
    if len(chunks) != expected_flat_records:
        raise QualificationError(
            f"flat_record_count_drift:expected={expected_flat_records}:observed={len(chunks)}"
        )
    if len(sources) != expected_parsed_routes:
        raise QualificationError(
            f"parsed_route_count_drift:expected={expected_parsed_routes}:observed={len(sources)}"
        )
    return sources, chunks


def _extract_queries(
    planner_outcome_path: Path,
    *,
    expected_queries: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    outcome = _load_json(planner_outcome_path)
    raw_response = outcome.get("raw_response")
    if not isinstance(raw_response, dict):
        raise QualificationError("planner_raw_response_missing")
    tool_calls = raw_response.get("tool_calls")
    if not isinstance(tool_calls, list):
        raise QualificationError("planner_tool_calls_missing")
    tasks: list[Any] | None = None
    for tool_call in tool_calls:
        if not isinstance(tool_call, dict) or tool_call.get("name") != "PlannerSemanticPayload":
            continue
        arguments = tool_call.get("args")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as exc:
                raise QualificationError("planner_tool_args_invalid_json") from exc
        if isinstance(arguments, dict) and isinstance(arguments.get("tasks"), list):
            tasks = arguments["tasks"]
            break
    if tasks is None:
        raise QualificationError("planner_tasks_not_found")

    queries: list[dict[str, Any]] = []
    for task_ordinal, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            raise QualificationError(f"planner_task_invalid:{task_ordinal}")
        branch_id = _require_string(task.get("branch_id"), label="planner_branch_id")
        if not BRANCH_PATTERN.fullmatch(branch_id):
            raise QualificationError(f"planner_branch_invalid:{branch_id}")
        evidence_requests = task.get("evidence_requests")
        if not isinstance(evidence_requests, list):
            raise QualificationError(f"planner_evidence_requests_invalid:{branch_id}")
        for request_ordinal, request in enumerate(evidence_requests, start=1):
            if not isinstance(request, dict):
                raise QualificationError(
                    f"planner_evidence_request_invalid:{branch_id}:{request_ordinal}"
                )
            query = _require_string(request.get("query"), label="planner_query")
            source_route = _require_string(
                request.get("source_route"), label="planner_source_route"
            )
            if source_route not in {"reviewed_first", "external_required"}:
                raise QualificationError(f"planner_source_route_unknown:{source_route}")
            limit = request.get("limit")
            if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 12:
                raise QualificationError(f"planner_limit_invalid:{branch_id}:{request_ordinal}")
            queries.append(
                {
                    "query_index": len(queries) + 1,
                    "branch_id": branch_id,
                    "source_route": source_route,
                    "external_required": source_route == "external_required",
                    "query": query,
                    "purpose": str(request.get("purpose") or "").strip(),
                    "limit": limit,
                    "capture_limit": request.get("capture_limit"),
                }
            )
    if len(queries) != expected_queries:
        raise QualificationError(
            f"planner_query_count_drift:expected={expected_queries}:observed={len(queries)}"
        )
    return queries, outcome


def _branch_filter_key(branch_id: str) -> str:
    if not BRANCH_PATTERN.fullmatch(branch_id):
        raise QualificationError(f"branch_filter_key_invalid:{branch_id}")
    return f"branch__{branch_id}"


def _root_document_id(route_id: str, parsed_text_sha256: str) -> str:
    payload = f"haystack-parent-child-v1|{route_id}|{parsed_text_sha256}".encode("utf-8")
    return "ROOT::" + hashlib.sha256(payload).hexdigest().upper()


def _build_hierarchy(
    sources: dict[str, dict[str, Any]],
    *,
    parent_block_words: int,
    leaf_block_words: int,
    overlap_words: int,
) -> tuple[list[Document], list[Document], list[Document], dict[str, Document]]:
    splitter = HierarchicalDocumentSplitter(
        block_sizes={parent_block_words, leaf_block_words},
        split_overlap=overlap_words,
        split_by="word",
    )
    all_documents: list[Document] = []
    for route_id in sorted(sources):
        source = sources[route_id]
        root_id = _root_document_id(route_id, source["parsed_text_sha256"])
        meta: dict[str, Any] = {
            "route_id": route_id,
            "root_document_id": root_id,
            "title": source["title"],
            "source_url": source["source_url"],
            "source_role": source["source_role"],
            "publication_date": source["publication_date"],
            "raw_body_sha256": source["raw_body_sha256"],
            "parsed_text_sha256": source["parsed_text_sha256"],
            "branches": list(source["branches"]),
            "authority_state": "retrieval_candidate",
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
            "content_contract": "title_then_two_newlines_then_exact_parsed_text_v1",
        }
        for branch_id in source["branches"]:
            meta[_branch_filter_key(branch_id)] = True
        document = Document(
            id=root_id,
            content=f"{source['title']}\n\n{source['parsed_text']}",
            meta=meta,
        )
        route_documents = splitter.run(documents=[document])["documents"]
        if not route_documents:
            raise QualificationError(f"hierarchy_empty:{route_id}")
        all_documents.extend(route_documents)

    documents_by_id = {document.id: document for document in all_documents}
    if len(documents_by_id) != len(all_documents):
        raise QualificationError("hierarchy_document_id_collision")
    parent_documents = [
        document for document in all_documents if document.meta.get("__children_ids")
    ]
    leaf_documents = [
        document for document in all_documents if not document.meta.get("__children_ids")
    ]
    return all_documents, parent_documents, leaf_documents, documents_by_id


def _validate_hierarchy(
    *,
    all_documents: Sequence[Document],
    parent_documents: Sequence[Document],
    leaf_documents: Sequence[Document],
    documents_by_id: dict[str, Document],
    expected_routes: set[str],
) -> dict[str, Any]:
    errors: list[str] = []
    root_ids: set[str] = set()
    for document in all_documents:
        parent_id = document.meta.get("__parent_id")
        children_ids = document.meta.get("__children_ids")
        level = document.meta.get("__level")
        if not isinstance(children_ids, list) or not isinstance(level, int):
            errors.append(f"hierarchy_meta_invalid:{document.id}")
            continue
        if parent_id is None:
            root_ids.add(document.id)
            if level != 0:
                errors.append(f"root_level_invalid:{document.id}")
        else:
            parent = documents_by_id.get(str(parent_id))
            if parent is None:
                errors.append(f"parent_missing:{document.id}:{parent_id}")
            elif document.id not in parent.meta.get("__children_ids", []):
                errors.append(f"parent_backlink_missing:{document.id}:{parent_id}")
        for child_id in children_ids:
            child = documents_by_id.get(str(child_id))
            if child is None:
                errors.append(f"child_missing:{document.id}:{child_id}")
            elif child.meta.get("__parent_id") != document.id:
                errors.append(f"child_backlink_mismatch:{document.id}:{child_id}")
    route_ids = {str(document.meta.get("route_id") or "") for document in all_documents}
    leaf_route_ids = {str(document.meta.get("route_id") or "") for document in leaf_documents}
    if route_ids != expected_routes:
        errors.append("hierarchy_route_coverage_drift")
    if leaf_route_ids != expected_routes:
        errors.append("leaf_route_coverage_drift")
    if errors:
        raise QualificationError("lineage_not_closed:" + errors[0])
    return {
        "closed": True,
        "error_count": 0,
        "root_count": len(root_ids),
        "parent_count": len(parent_documents),
        "leaf_count": len(leaf_documents),
        "all_document_count": len(all_documents),
        "route_count": len(route_ids),
        "leaf_route_count": len(leaf_route_ids),
        "unsplit_root_leaf_count": sum(
            1
            for document in leaf_documents
            if document.meta.get("__parent_id") is None
        ),
        "levels": dict(
            sorted(Counter(int(document.meta["__level"]) for document in all_documents).items())
        ),
    }


def _descendant_leaf_ids(
    document_id: str,
    *,
    documents_by_id: dict[str, Document],
    memo: dict[str, frozenset[str]],
) -> frozenset[str]:
    cached = memo.get(document_id)
    if cached is not None:
        return cached
    document = documents_by_id[document_id]
    child_ids = [str(value) for value in document.meta.get("__children_ids", [])]
    if not child_ids:
        result = frozenset({document_id})
    else:
        result = frozenset(
            leaf_id
            for child_id in child_ids
            for leaf_id in _descendant_leaf_ids(
                child_id,
                documents_by_id=documents_by_id,
                memo=memo,
            )
        )
    memo[document_id] = result
    return result


def _serialize_document_candidate(
    document: Document,
    *,
    rank: int,
    score: float | None,
    matched_leaf_count: int,
) -> dict[str, Any]:
    content = document.content or ""
    branches = [str(value) for value in document.meta.get("branches", [])]
    return {
        "rank": rank,
        "document_id": document.id,
        "route_id": str(document.meta.get("route_id") or ""),
        "title": str(document.meta.get("title") or ""),
        "source_url": str(document.meta.get("source_url") or ""),
        "raw_body_sha256": str(document.meta.get("raw_body_sha256") or ""),
        "branches": branches,
        "hierarchy_level": document.meta.get("__level"),
        "block_size": document.meta.get("__block_size"),
        "parent_id": document.meta.get("__parent_id"),
        "children_count": len(document.meta.get("__children_ids", [])),
        "matched_leaf_count": matched_leaf_count,
        "score": score,
        "content_chars": len(content),
        "content_sha256": _sha256_bytes(content.encode("utf-8")),
        "excerpt": re.sub(r"\s+", " ", content).strip()[:500],
        "candidate_is_not_evidence": True,
    }


def _serialize_flat_candidate(row: dict[str, Any], *, rank: int, score: float) -> dict[str, Any]:
    text = str(row["text"])
    return {
        "rank": rank,
        "document_id": str(row["chunk_id"]),
        "route_id": str(row["route_id"]),
        "title": str(row.get("title") or ""),
        "source_url": str(row.get("stable_url") or ""),
        "raw_body_sha256": str(row.get("raw_body_sha256") or ""),
        "branches": list(row.get("branches") or []),
        "chunk_index": row.get("chunk_index"),
        "page": row.get("page"),
        "score": float(score),
        "content_chars": len(text),
        "content_sha256": _sha256_bytes(text.encode("utf-8")),
        "excerpt": re.sub(r"\s+", " ", text).strip()[:500],
        "candidate_is_not_evidence": True,
    }


def _candidate_metrics(candidates: Sequence[dict[str, Any]], *, branch_id: str) -> dict[str, Any]:
    route_counts = Counter(str(candidate["route_id"]) for candidate in candidates)
    source_counts = Counter(str(candidate["source_url"]) for candidate in candidates)
    count = len(candidates)
    violations = [
        str(candidate["document_id"])
        for candidate in candidates
        if branch_id not in set(candidate.get("branches") or [])
    ]
    return {
        "returned_count": count,
        "unique_routes": len(route_counts),
        "unique_sources": len(source_counts),
        "top_route_share": (max(route_counts.values()) / count) if count else 0.0,
        "top_source_share": (max(source_counts.values()) / count) if count else 0.0,
        "context_chars": sum(int(candidate.get("content_chars") or 0) for candidate in candidates),
        "delivery_cap_normalized_context_chars": sum(
            min(int(candidate.get("content_chars") or 0), DELIVERY_CAP_CHARACTERS)
            for candidate in candidates
        ),
        "branch_violation_count": len(violations),
        "branch_violation_document_ids": violations,
        "route_counts": dict(sorted(route_counts.items())),
    }


class _FlatBM25Baseline:
    def __init__(self, rows: Sequence[dict[str, Any]]) -> None:
        self.rows = tuple(rows)
        corpus = [
            _tokenize(f"{str(row.get('title') or '')}\n{str(row.get('text') or '')}")
            for row in self.rows
        ]
        if any(not tokens for tokens in corpus):
            raise QualificationError("flat_baseline_empty_token_document")
        self.index = BM25Okapi(corpus)

    def search(self, *, query: str, branch_id: str, limit: int) -> dict[str, Any]:
        started = time.perf_counter()
        tokens = _tokenize(query)
        if not tokens:
            raise QualificationError("flat_baseline_query_tokens_empty")
        scores = self.index.get_scores(tokens)
        ranked = sorted(
            enumerate(scores),
            key=lambda item: (-float(item[1]), str(self.rows[item[0]]["chunk_id"])),
        )
        positive = [(index, float(score)) for index, score in ranked if float(score) > 0]
        pre_filter = positive[:limit]
        post_filter = [
            (index, score)
            for index, score in positive
            if branch_id in set(self.rows[index].get("branches") or [])
        ][:limit]
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return {
            "latency_ms": elapsed_ms,
            "pre_filter_candidates": [
                _serialize_flat_candidate(self.rows[index], rank=rank, score=score)
                for rank, (index, score) in enumerate(pre_filter, start=1)
            ],
            "post_filter_candidates": [
                _serialize_flat_candidate(self.rows[index], rank=rank, score=score)
                for rank, (index, score) in enumerate(post_filter, start=1)
            ],
        }


def _haystack_search(
    *,
    query: str,
    branch_id: str,
    limit: int,
    bm25_retriever: InMemoryBM25Retriever,
    auto_merging_retriever: AutoMergingRetriever,
    documents_by_id: dict[str, Document],
    descendant_memo: dict[str, frozenset[str]],
) -> dict[str, Any]:
    started = time.perf_counter()
    filters = {
        "field": f"meta.{_branch_filter_key(branch_id)}",
        "operator": "==",
        "value": True,
    }
    leaf_hits = bm25_retriever.run(
        query=query,
        filters=filters,
        top_k=limit,
    )["documents"]
    parented_hits = [document for document in leaf_hits if document.meta.get("__parent_id")]
    parentless_hits = [document for document in leaf_hits if not document.meta.get("__parent_id")]
    merged = (
        auto_merging_retriever.run(documents=parented_hits)["documents"]
        if parented_hits
        else []
    )
    returned_documents = [*merged, *parentless_hits]

    leaf_rank = {document.id: rank for rank, document in enumerate(leaf_hits, start=1)}
    leaf_score = {document.id: float(document.score or 0.0) for document in leaf_hits}
    matched_leaf_ids = set(leaf_rank)
    ordered: list[tuple[int, float, Document, frozenset[str]]] = []
    for document in returned_documents:
        descendants = _descendant_leaf_ids(
            document.id,
            documents_by_id=documents_by_id,
            memo=descendant_memo,
        )
        matched = frozenset(descendants.intersection(matched_leaf_ids))
        if not matched:
            raise QualificationError(f"auto_merge_return_without_matched_leaf:{document.id}")
        first_rank = min(leaf_rank[leaf_id] for leaf_id in matched)
        score = max(leaf_score[leaf_id] for leaf_id in matched)
        ordered.append((first_rank, -score, document, matched))
    ordered.sort(key=lambda value: (value[0], value[1], value[2].id))
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    leaf_candidates = [
        _serialize_document_candidate(
            document,
            rank=rank,
            score=float(document.score or 0.0),
            matched_leaf_count=1,
        )
        for rank, document in enumerate(leaf_hits, start=1)
    ]
    merged_candidates = [
        _serialize_document_candidate(
            document,
            rank=rank,
            score=-negative_score,
            matched_leaf_count=len(matched),
        )
        for rank, (_, negative_score, document, matched) in enumerate(ordered, start=1)
    ]
    return {
        "latency_ms": elapsed_ms,
        "metadata_filter": filters,
        "leaf_candidates": leaf_candidates,
        "merged_candidates": merged_candidates,
        "leaf_hit_count": len(leaf_hits),
        "merged_return_count": len(merged_candidates),
        "parent_context_return_count": sum(
            1 for candidate in merged_candidates if candidate["children_count"] > 0
        ),
    }


def _query_evaluation_scope(
    *,
    external_required: bool,
    candidates: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    if external_required:
        return {
            "evaluation_scope": "bounded_miss_and_wrong_local_substitution_risk_only",
            "local_source_recall": None,
            "local_source_recall_exclusion_reason": "planner_route_external_required",
            "bounded_local_miss": not candidates,
            "local_substitution_risk_candidate_count": len(candidates),
            "local_substitution_risk_routes": sorted(
                {str(candidate["route_id"]) for candidate in candidates}
            ),
            "human_relevance_judgment_performed": False,
        }
    return {
        "evaluation_scope": "reviewed_first_local_candidate_diagnostics",
        "local_source_recall": None,
        "local_source_recall_exclusion_reason": "no_frozen_source_level_qrels",
        "bounded_local_miss": not candidates,
        "local_substitution_risk_candidate_count": None,
        "local_substitution_risk_routes": [],
        "human_relevance_judgment_performed": False,
    }


def _retrieval_metric_aggregate(
    query_results: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    systems = {
        "flat_bm25_pre_filter": ("baseline", "pre_filter_metrics"),
        "flat_bm25_post_filter": ("baseline", "post_filter_metrics"),
        "haystack_leaf": ("haystack", "leaf_metrics"),
        "haystack_parent_child": ("haystack", "merged_metrics"),
    }
    aggregate: dict[str, Any] = {}
    for system_name, (outer_key, metric_key) in systems.items():
        metrics = [row[outer_key][metric_key] for row in query_results]
        aggregate[system_name] = {
            "branch_violation_count": sum(
                int(metric["branch_violation_count"]) for metric in metrics
            ),
            "unique_routes_per_query": _summary(
                [int(metric["unique_routes"]) for metric in metrics]
            ),
            "unique_sources_per_query": _summary(
                [int(metric["unique_sources"]) for metric in metrics]
            ),
            "top_route_share": _summary(
                [float(metric["top_route_share"]) for metric in metrics]
            ),
            "context_chars": _summary(
                [int(metric["context_chars"]) for metric in metrics]
            ),
            "delivery_cap_normalized_context_chars": _summary(
                [
                    int(metric["delivery_cap_normalized_context_chars"])
                    for metric in metrics
                ]
            ),
            "all_query_result_routes": sorted(
                {
                    route_id
                    for metric in metrics
                    for route_id in metric["route_counts"]
                }
            ),
        }
    aggregate["flat_bm25_latency_ms"] = _summary(
        [float(row["baseline"]["latency_ms"]) for row in query_results]
    )
    aggregate["haystack_parent_child_latency_ms"] = _summary(
        [float(row["haystack"]["latency_ms"]) for row in query_results]
    )
    aggregate["query_count"] = len(query_results)
    return aggregate


def _aggregate_query_results(query_results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    reviewed_first = [row for row in query_results if not row["external_required"]]
    external_required = [row for row in query_results if row["external_required"]]
    if not reviewed_first or not external_required:
        raise QualificationError("query_evaluation_scope_empty")
    return {
        "reviewed_first": {
            **_retrieval_metric_aggregate(reviewed_first),
            "quality_metrics_included": True,
            "scope": "local_candidate_retrieval_diagnostics",
        },
        "external_required": {
            "query_count": len(external_required),
            "quality_metrics_included": False,
            "scope": "wrong_local_substitution_risk_only",
            "flat_queries_with_local_substitution_risk": sum(
                1
                for row in external_required
                if row["baseline"]["evaluation"][
                    "local_substitution_risk_candidate_count"
                ]
            ),
            "haystack_queries_with_local_substitution_risk": sum(
                1
                for row in external_required
                if row["haystack"]["evaluation"][
                    "local_substitution_risk_candidate_count"
                ]
            ),
            "recall_included": False,
        },
        "all_queries_diagnostic": {
            **_retrieval_metric_aggregate(query_results),
            "quality_metrics_included": False,
            "scope": "transport_branch_and_resource_diagnostic_only",
        },
    }


def _serialized_document_bytes(documents: Iterable[Document]) -> int:
    return sum(len(_canonical_json_bytes(document.to_dict())) for document in documents)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a bounded, zero-model Haystack 3.1.0 parent-child qualification "
            "against two frozen Dell knowledge attempts and the A01 planner queries."
        )
    )
    parser.add_argument(
        "--knowledge-attempt-root",
        action="append",
        required=True,
        help="Frozen knowledge attempt root. Supply exactly twice.",
    )
    parser.add_argument("--planner-outcome", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--parent-block-words", type=int, default=900)
    parser.add_argument("--leaf-block-words", type=int, default=240)
    parser.add_argument("--overlap-words", type=int, default=30)
    parser.add_argument("--auto-merge-threshold", type=float, default=0.5)
    parser.add_argument("--expected-flat-records", type=int, default=597)
    parser.add_argument("--expected-parsed-routes", type=int, default=18)
    parser.add_argument("--expected-queries", type=int, default=19)
    args = parser.parse_args(argv)
    if len(args.knowledge_attempt_root) != 2:
        parser.error("--knowledge-attempt-root must be supplied exactly twice")
    if not 1 <= args.leaf_block_words < args.parent_block_words:
        parser.error("word block sizes must satisfy 1 <= leaf < parent")
    if not 0 <= args.overlap_words < args.leaf_block_words:
        parser.error("overlap must satisfy 0 <= overlap < leaf block size")
    if not 0.0 < args.auto_merge_threshold < 1.0:
        parser.error("auto-merge threshold must be between 0 and 1")
    if min(
        args.expected_flat_records,
        args.expected_parsed_routes,
        args.expected_queries,
    ) <= 0:
        parser.error("expected counts must be positive")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    repo_root = Path(__file__).resolve().parents[2]
    output_dir = Path(args.output_dir).expanduser().resolve()
    if output_dir.exists():
        raise QualificationError(f"output_dir_already_exists:{output_dir}")

    rss_observations: list[int] = []
    initial_rss = _rss_bytes()
    if initial_rss is not None:
        rss_observations.append(initial_rss)

    attempts = [_validate_attempt(value) for value in args.knowledge_attempt_root]
    sources, flat_rows = _merge_validated_attempts(
        attempts,
        expected_flat_records=args.expected_flat_records,
        expected_parsed_routes=args.expected_parsed_routes,
    )
    planner_outcome_path = _resolve_file(args.planner_outcome, label="planner_outcome")
    queries, planner_outcome = _extract_queries(
        planner_outcome_path,
        expected_queries=args.expected_queries,
    )
    known_branches = {
        branch_id
        for source in sources.values()
        for branch_id in source["branches"]
    }
    unknown_query_branches = sorted(
        {query["branch_id"] for query in queries}.difference(known_branches)
    )
    if unknown_query_branches:
        raise QualificationError(
            "planner_branches_not_in_frozen_sources:" + ",".join(unknown_query_branches)
        )

    all_documents, parent_documents, leaf_documents, documents_by_id = _build_hierarchy(
        sources,
        parent_block_words=args.parent_block_words,
        leaf_block_words=args.leaf_block_words,
        overlap_words=args.overlap_words,
    )
    lineage = _validate_hierarchy(
        all_documents=all_documents,
        parent_documents=parent_documents,
        leaf_documents=leaf_documents,
        documents_by_id=documents_by_id,
        expected_routes=set(sources),
    )

    leaf_store = InMemoryDocumentStore(
        bm25_tokenization_regex=LEGACY_TOKEN_PATTERN,
        bm25_algorithm="BM25Okapi",
        shared=False,
    )
    parent_store = InMemoryDocumentStore(
        bm25_tokenization_regex=LEGACY_TOKEN_PATTERN,
        bm25_algorithm="BM25Okapi",
        shared=False,
    )
    leaf_written = leaf_store.write_documents(
        list(leaf_documents), policy=DuplicatePolicy.FAIL
    )
    parent_written = parent_store.write_documents(
        list(parent_documents), policy=DuplicatePolicy.FAIL
    )
    stored_leaf_ids = {document.id for document in leaf_store.filter_documents()}
    stored_parent_ids = {document.id for document in parent_store.filter_documents()}
    expected_leaf_ids = {document.id for document in leaf_documents}
    expected_parent_ids = {document.id for document in parent_documents}
    if stored_leaf_ids != expected_leaf_ids or leaf_written != len(expected_leaf_ids):
        raise QualificationError("leaf_store_coverage_failure")
    if stored_parent_ids != expected_parent_ids or parent_written != len(expected_parent_ids):
        raise QualificationError("parent_store_coverage_failure")

    branch_filter_leaf_ids: set[str] = set()
    for branch_id in sorted(known_branches):
        filtered = leaf_store.filter_documents(
            {
                "field": f"meta.{_branch_filter_key(branch_id)}",
                "operator": "==",
                "value": True,
            }
        )
        if any(branch_id not in set(document.meta.get("branches", [])) for document in filtered):
            raise QualificationError(f"leaf_store_branch_filter_violation:{branch_id}")
        branch_filter_leaf_ids.update(document.id for document in filtered)
    if branch_filter_leaf_ids != expected_leaf_ids:
        raise QualificationError("leaf_store_branch_filter_coverage_failure")

    after_build_rss = _rss_bytes()
    if after_build_rss is not None:
        rss_observations.append(after_build_rss)

    flat_baseline = _FlatBM25Baseline(flat_rows)
    bm25_retriever = InMemoryBM25Retriever(
        document_store=leaf_store,
        top_k=max(query["limit"] for query in queries),
        scale_score=False,
    )
    auto_merging_retriever = AutoMergingRetriever(
        document_store=parent_store,
        threshold=args.auto_merge_threshold,
    )
    descendant_memo: dict[str, frozenset[str]] = {}
    query_results: list[dict[str, Any]] = []
    for query in queries:
        baseline = flat_baseline.search(
            query=query["query"],
            branch_id=query["branch_id"],
            limit=query["limit"],
        )
        haystack_result = _haystack_search(
            query=query["query"],
            branch_id=query["branch_id"],
            limit=query["limit"],
            bm25_retriever=bm25_retriever,
            auto_merging_retriever=auto_merging_retriever,
            documents_by_id=documents_by_id,
            descendant_memo=descendant_memo,
        )
        baseline_pre_metrics = _candidate_metrics(
            baseline["pre_filter_candidates"], branch_id=query["branch_id"]
        )
        baseline_post_metrics = _candidate_metrics(
            baseline["post_filter_candidates"], branch_id=query["branch_id"]
        )
        haystack_leaf_metrics = _candidate_metrics(
            haystack_result["leaf_candidates"], branch_id=query["branch_id"]
        )
        haystack_merged_metrics = _candidate_metrics(
            haystack_result["merged_candidates"], branch_id=query["branch_id"]
        )
        if haystack_leaf_metrics["branch_violation_count"]:
            raise QualificationError(
                f"haystack_leaf_branch_violation:query={query['query_index']}"
            )
        if haystack_merged_metrics["branch_violation_count"]:
            raise QualificationError(
                f"haystack_merged_branch_violation:query={query['query_index']}"
            )
        query_results.append(
            {
                "schema_version": QUERY_RESULT_SCHEMA,
                **query,
                "baseline": {
                    **baseline,
                    "pre_filter_metrics": baseline_pre_metrics,
                    "post_filter_metrics": baseline_post_metrics,
                    "evaluation": _query_evaluation_scope(
                        external_required=query["external_required"],
                        candidates=baseline["post_filter_candidates"],
                    ),
                },
                "haystack": {
                    **haystack_result,
                    "leaf_metrics": haystack_leaf_metrics,
                    "merged_metrics": haystack_merged_metrics,
                    "evaluation": _query_evaluation_scope(
                        external_required=query["external_required"],
                        candidates=haystack_result["merged_candidates"],
                    ),
                },
            }
        )
        observed_rss = _rss_bytes()
        if observed_rss is not None:
            rss_observations.append(observed_rss)

    aggregate = _aggregate_query_results(query_results)
    diagnostic = aggregate["all_queries_diagnostic"]
    if diagnostic["haystack_leaf"]["branch_violation_count"] != 0:
        raise QualificationError("haystack_leaf_branch_violation_aggregate")
    if diagnostic["haystack_parent_child"]["branch_violation_count"] != 0:
        raise QualificationError("haystack_parent_child_branch_violation_aggregate")

    document_disk_estimate = {
        "leaf_store_canonical_document_json_bytes": _serialized_document_bytes(leaf_documents),
        "parent_store_canonical_document_json_bytes": _serialized_document_bytes(parent_documents),
    }
    document_disk_estimate["combined_canonical_document_json_bytes"] = sum(
        document_disk_estimate.values()
    )
    ended_at = datetime.now(timezone.utc)
    runtime_versions = {
        "python": platform.python_version(),
        "python_executable": str(Path(sys.executable).resolve()),
        "haystack_ai": importlib.metadata.version("haystack-ai"),
        "rank_bm25": importlib.metadata.version("rank-bm25"),
    }
    input_receipts = [
        {
            "attempt_id": attempt["attempt_id"],
            "attempt_root": attempt["attempt_root"].as_posix(),
            "manifest_path": attempt["manifest_path"].as_posix(),
            "manifest_sha256": attempt["manifest_sha256"],
            "validated_artifacts": attempt["validated_artifacts"],
            "parsed_route_count": len(attempt["sources"]),
            "flat_chunk_count": len(attempt["chunks"]),
            "raw_body_digest_count": attempt["raw_body_digest_count"],
        }
        for attempt in attempts
    ]
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "status": "frozen_inputs_validated_and_execution_complete",
        "attempt_id": output_dir.name,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "elapsed_seconds": time.perf_counter() - started_clock,
        "command": [str(Path(sys.executable).resolve()), str(Path(__file__).resolve()), *sys.argv[1:]],
        "script_path": Path(__file__).resolve().as_posix(),
        "script_sha256": _sha256_file(Path(__file__).resolve()),
        "runtime_versions": runtime_versions,
        "git": _git_metadata(repo_root),
        "model_calls": 0,
        "network_calls": 0,
        "input_receipts": input_receipts,
        "planner_outcome": {
            "path": planner_outcome_path.as_posix(),
            "sha256": _sha256_file(planner_outcome_path),
            "call_id": planner_outcome.get("call_id"),
            "status": planner_outcome.get("status"),
            "query_count": len(queries),
        },
        "configuration": {
            "splitter": "Haystack HierarchicalDocumentSplitter",
            "split_by": "word",
            "parent_block_words": args.parent_block_words,
            "leaf_block_words": args.leaf_block_words,
            "overlap_words": args.overlap_words,
            "retriever": "Haystack InMemoryBM25Retriever",
            "bm25_algorithm": "BM25Okapi",
            "bm25_tokenization_regex": LEGACY_TOKEN_PATTERN,
            "auto_merging_retriever": "Haystack AutoMergingRetriever",
            "auto_merge_threshold": args.auto_merge_threshold,
            "leaf_only_retrieval_store": True,
            "parents_only_parent_store": True,
            "query_top_k_source": "A01 evidence_request.limit",
            "branch_filter": "Haystack metadata boolean equality derived from row branches",
            "content_contract": "title_then_two_newlines_then_exact_parsed_text_v1",
            "delivery_cap_normalization_characters": DELIVERY_CAP_CHARACTERS,
        },
        "authority_boundary": {
            "qualification_input_not_evidence": True,
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
            "evidence_admission_performed": False,
        },
    }
    result = {
        "schema_version": RESULT_SCHEMA,
        "status": "COMPONENT_EXECUTION_PASS_BOUNDED_ZERO_MODEL",
        "adoption_decision": "HOLD_HUMAN_RELEVANCE_REVIEW",
        "attempt_id": output_dir.name,
        "input_validation": {
            "knowledge_attempt_count": len(attempts),
            "flat_record_count": len(flat_rows),
            "parsed_route_count": len(sources),
            "unique_raw_body_digest_count": len(
                {source["raw_body_sha256"] for source in sources.values()}
            ),
            "planner_query_count": len(queries),
            "reviewed_first_query_count": sum(
                1 for query in queries if not query["external_required"]
            ),
            "external_required_query_count": sum(
                1 for query in queries if query["external_required"]
            ),
            "chunks_and_raw_body_digests_verified": True,
        },
        "source_coverage": {
            "input_routes": sorted(sources),
            "hierarchy_route_count": lineage["route_count"],
            "leaf_route_count": lineage["leaf_route_count"],
            "all_input_routes_have_leaf": lineage["leaf_route_count"] == len(sources),
        },
        "hierarchy": lineage,
        "stores": {
            "leaf_written": leaf_written,
            "parent_written": parent_written,
            "all_leaf_retrievable": stored_leaf_ids == expected_leaf_ids,
            "all_parent_retrievable": stored_parent_ids == expected_parent_ids,
            "all_leaf_reachable_through_at_least_one_branch_filter": (
                branch_filter_leaf_ids == expected_leaf_ids
            ),
        },
        "query_aggregate": aggregate,
        "resource_observations": {
            "rss_start_bytes": initial_rss,
            "rss_after_build_bytes": after_build_rss,
            "rss_peak_observed_bytes": max(rss_observations) if rss_observations else None,
            "document_store_disk_estimate": document_disk_estimate,
        },
        "quality_scope": {
            "source_level_qrels_available": False,
            "recall_mrr_ndcg_computed": False,
            "external_required_local_recall_computed": False,
            "external_required_policy": (
                "Only bounded local miss and wrong-local-substitution risk candidates are recorded."
            ),
            "human_relevance_review_required": True,
            "no_keyword_tuning": True,
            "no_network": True,
            "no_model": True,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=False)
    query_results_jsonl = b"".join(_canonical_json_bytes(row) for row in query_results)
    _write_bytes_exclusive(output_dir / "query_results.jsonl", query_results_jsonl)
    _write_json_exclusive(output_dir / "query_results.json", query_results)
    _write_json_exclusive(output_dir / "manifest.json", manifest)
    result["output_artifacts"] = {
        "query_results_jsonl": {
            "path": (output_dir / "query_results.jsonl").as_posix(),
            "sha256": _sha256_file(output_dir / "query_results.jsonl"),
            "bytes": (output_dir / "query_results.jsonl").stat().st_size,
        },
        "query_results_json": {
            "path": (output_dir / "query_results.json").as_posix(),
            "sha256": _sha256_file(output_dir / "query_results.json"),
            "bytes": (output_dir / "query_results.json").stat().st_size,
        },
        "manifest": {
            "path": (output_dir / "manifest.json").as_posix(),
            "sha256": _sha256_file(output_dir / "manifest.json"),
            "bytes": (output_dir / "manifest.json").stat().st_size,
        },
    }
    _write_json_exclusive(output_dir / "result.json", result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except QualificationError as exc:
        print(f"qualification_error:{exc}", file=sys.stderr)
        raise SystemExit(2) from exc
