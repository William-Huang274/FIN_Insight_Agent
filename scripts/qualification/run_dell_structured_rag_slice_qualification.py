from __future__ import annotations

import argparse
import gc
import hashlib
import importlib
import importlib.util
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


POLICY_SCHEMA = "fin_ia_dell_structured_rag_qualification_policy_v1_0"
QRELS_SCHEMA = "fin_ia_dell_structured_rag_qrels_v1_2"
SUPPORTED_QRELS_SCHEMAS = {
    "fin_ia_dell_structured_rag_qrels_v1_1",
    QRELS_SCHEMA,
}
NODE_SCHEMA = "fin_ia_dell_structured_rag_node_v1_0"
ROUTE_RESULT_SCHEMA = "fin_ia_dell_structured_rag_route_result_v1_0"
RESULT_SCHEMA = "fin_ia_dell_structured_rag_qualification_result_v1_0"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TOKEN_RE = re.compile(
    r"[a-z0-9]+(?:[.&/+_-][a-z0-9]+)*|[\u3400-\u4dbf\u4e00-\u9fff]",
    re.IGNORECASE,
)
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


class QualificationError(ValueError):
    """Raised when a frozen input or bounded qualification invariant fails."""


def canonical_json_bytes(value: Any) -> bytes:
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


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
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
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise QualificationError(
                        f"jsonl_row_invalid:{path}:{ordinal}"
                    ) from exc
                if not isinstance(row, dict):
                    raise QualificationError(
                        f"jsonl_row_not_object:{path}:{ordinal}"
                    )
                rows.append(row)
    except (OSError, UnicodeError) as exc:
        raise QualificationError(f"jsonl_unreadable:{path}") from exc
    if not rows:
        raise QualificationError(f"jsonl_empty:{path}")
    return rows


def _write_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _write_json_exclusive(path: Path, value: Any) -> None:
    _write_exclusive(
        path,
        (
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            + "\n"
        ).encode("utf-8"),
    )


def _write_jsonl_exclusive(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    payload = b"".join(canonical_json_bytes(dict(row)) for row in rows)
    _write_exclusive(path, payload)


def _require_string(value: Any, *, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise QualificationError(f"{label}_empty")
    return normalized


def _require_sha(value: Any, *, label: str) -> str:
    normalized = str(value or "").strip().lower()
    if not SHA256_RE.fullmatch(normalized):
        raise QualificationError(f"{label}_not_sha256")
    return normalized


def _validated_text_sha(value: Any, expected: Any, *, label: str) -> str:
    digest = _require_sha(expected, label=label)
    observed = hashlib.sha256(str(value).encode("utf-8")).hexdigest()
    if observed != digest:
        raise QualificationError(f"{label}_content_digest_drift")
    return digest


def _visible_text(value: Any) -> str:
    text = IMAGE_RE.sub(" ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_RE.findall(text)]


def _section_label(section_path: Any) -> str:
    if not isinstance(section_path, list):
        return ""
    return " > ".join(str(value).strip() for value in section_path if str(value).strip())


def _model_text(metadata: Mapping[str, Any], content: str) -> str:
    fields = [
        f"Issuer: {metadata.get('issuer_id') or metadata.get('company') or 'UNKNOWN'}",
        f"Period: {metadata.get('fiscal_period') or 'UNKNOWN'}; period end: {metadata.get('period_end') or 'UNKNOWN'}",
        f"Source: {metadata.get('title') or metadata.get('route_id')}",
        f"Source role: {metadata.get('source_role') or 'UNKNOWN'}",
        f"Section: {_section_label(metadata.get('section_path')) or 'document root'}",
    ]
    page_start = metadata.get("page_start")
    page_end = metadata.get("page_end")
    if page_start is not None:
        fields.append(f"Page: {page_start}" if page_start == page_end else f"Pages: {page_start}-{page_end}")
    return "\n".join(fields) + "\n\n" + content.strip()


def _validate_authority(row: Mapping[str, Any], *, node_id: str) -> None:
    if row.get("candidate_is_not_evidence") is not True:
        raise QualificationError(f"candidate_authority_drift:{node_id}")
    if row.get("numeric_authority") is not False:
        raise QualificationError(f"numeric_authority_drift:{node_id}")
    if row.get("citation_eligible") is not False:
        raise QualificationError(f"citation_authority_drift:{node_id}")


def load_frozen_corpus(policy: Mapping[str, Any]) -> dict[str, Any]:
    corpus = policy.get("corpus")
    if not isinstance(corpus, Mapping):
        raise QualificationError("policy_corpus_missing")
    root = Path(_require_string(corpus.get("attempt_root"), label="attempt_root")).resolve()
    if not root.is_dir():
        raise QualificationError(f"attempt_root_not_directory:{root}")
    expected_artifacts = corpus.get("artifacts")
    if not isinstance(expected_artifacts, Mapping):
        raise QualificationError("policy_corpus_artifacts_missing")
    artifacts: dict[str, dict[str, Any]] = {}
    for name in (
        "documents.jsonl",
        "sections.jsonl",
        "blocks.jsonl",
        "chunks.jsonl",
        "result.json",
    ):
        path = (root / name).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise QualificationError(f"corpus_artifact_outside_root:{path}") from exc
        if not path.is_file():
            raise QualificationError(f"corpus_artifact_missing:{path}")
        expected = _require_sha(expected_artifacts.get(name), label=f"{name}_digest")
        observed = sha256_file(path)
        if observed != expected:
            raise QualificationError(f"corpus_artifact_digest_drift:{name}")
        artifacts[name] = {
            "path": path.as_posix(),
            "sha256": observed,
            "bytes": path.stat().st_size,
        }
    result = _load_json(Path(artifacts["result.json"]["path"]))
    if result.get("status") != "STRUCTURED_CORPUS_MATERIALIZED_REVIEW_REQUIRED":
        raise QualificationError("structured_corpus_status_drift")
    attempt_id = _require_string(corpus.get("attempt_id"), label="attempt_id")
    if str(result.get("attempt_id") or "") != attempt_id:
        raise QualificationError("structured_corpus_attempt_id_drift")
    if result.get("manual_review_complete") is True:
        raise QualificationError("producer_must_not_self_approve_manual_review")
    result_artifacts = result.get("artifacts")
    if not isinstance(result_artifacts, Mapping):
        raise QualificationError("structured_corpus_result_artifacts_missing")
    for filename, result_key in (
        ("documents.jsonl", "documents"),
        ("sections.jsonl", "sections"),
        ("blocks.jsonl", "blocks"),
        ("chunks.jsonl", "chunks"),
    ):
        receipt = result_artifacts.get(result_key)
        if not isinstance(receipt, Mapping) or str(receipt.get("sha256") or "").lower() != artifacts[filename]["sha256"]:
            raise QualificationError(f"structured_corpus_result_digest_drift:{filename}")
    loaded_rows = {
        "documents": _load_jsonl(Path(artifacts["documents.jsonl"]["path"])),
        "sections": _load_jsonl(Path(artifacts["sections.jsonl"]["path"])),
        "blocks": _load_jsonl(Path(artifacts["blocks.jsonl"]["path"])),
        "chunks": _load_jsonl(Path(artifacts["chunks.jsonl"]["path"])),
    }
    for key, rows in loaded_rows.items():
        if int(result_artifacts[key].get("record_count") or -1) != len(rows):
            raise QualificationError(f"structured_corpus_result_count_drift:{key}")
    return {
        "attempt_id": attempt_id,
        "root": root,
        "artifacts": artifacts,
        **loaded_rows,
    }


def build_retrieval_nodes(corpus: Mapping[str, Any]) -> dict[str, Any]:
    documents = list(corpus["documents"])
    sections = list(corpus["sections"])
    blocks = list(corpus["blocks"])
    chunks = list(corpus["chunks"])
    docs_by_id = {str(row["document_id"]): row for row in documents}
    sections_by_id = {str(row["section_id"]): row for row in sections}
    blocks_by_id = {str(row["block_id"]): row for row in blocks}
    if (
        len(docs_by_id) != len(documents)
        or len(sections_by_id) != len(sections)
        or len(blocks_by_id) != len(blocks)
    ):
        raise QualificationError("structured_parent_identifier_duplicate")

    def inherited(row: Mapping[str, Any]) -> dict[str, Any]:
        document_id = _require_string(row.get("parent_document_id"), label="parent_document_id")
        section_id = str(
            row.get("parent_section_id") or row.get("section_id") or ""
        )
        document = docs_by_id.get(document_id)
        section = sections_by_id.get(section_id) if section_id else None
        if document is None or (section_id and section is None):
            raise QualificationError(f"structured_parent_missing:{document_id}:{section_id}")
        metadata = {
            "route_id": document.get("route_id"),
            "parent_document_id": document_id,
            "parent_section_id": section_id or None,
            "company": document.get("company"),
            "issuer_id": document.get("issuer_id"),
            "ticker": document.get("ticker"),
            "fiscal_period": document.get("fiscal_period"),
            "period_end": document.get("period_end"),
            "publication_date": document.get("publication_date"),
            "source_role": document.get("source_role"),
            "stable_url": document.get("stable_url"),
            "title": document.get("title"),
            "document_kind": document.get("document_kind"),
            "raw_body_sha256": document.get("raw_body_sha256"),
            "section_path": section.get("section_path") if section else [],
            "page_start": row.get("page_start") if row.get("page_start") is not None else (section or {}).get("page_start"),
            "page_end": row.get("page_end") if row.get("page_end") is not None else (section or {}).get("page_end"),
        }
        if str(row.get("route_id") or "") != str(document.get("route_id") or ""):
            raise QualificationError(f"route_parent_drift:{document_id}")
        if str(row.get("raw_body_sha256") or "") != str(document.get("raw_body_sha256") or ""):
            raise QualificationError(f"raw_body_parent_drift:{document_id}")
        return metadata

    parents: list[dict[str, Any]] = []
    for section in sections:
        section_id = _require_string(section.get("section_id"), label="section_id")
        _validate_authority(section, node_id=section_id)
        metadata = inherited(section)
        content = _require_string(section.get("content"), label=f"section_content:{section_id}")
        parents.append(
            {
                "schema_version": NODE_SCHEMA,
                "node_id": section_id,
                "lane": "parent",
                "node_kind": "section",
                **metadata,
                "content": content,
                "content_sha256": _validated_text_sha(
                    content,
                    section.get("content_sha256"),
                    label=f"section_sha:{section_id}",
                ),
                "model_text": _model_text(metadata, content),
                "candidate_is_not_evidence": True,
                "numeric_authority": False,
                "citation_eligible": False,
            }
        )

    prose: list[dict[str, Any]] = []
    mixed_by_id: dict[str, dict[str, Any]] = {}
    mixed_prose_raw_run_count = 0
    mixed_prose_raw_character_count = 0
    for chunk in chunks:
        chunk_id = _require_string(chunk.get("chunk_id"), label="chunk_id")
        _validate_authority(chunk, node_id=chunk_id)
        contains_table = chunk.get("contains_table")
        if not isinstance(contains_table, bool):
            raise QualificationError(f"chunk_contains_table_not_boolean:{chunk_id}")
        source_block_ids = [str(value) for value in chunk.get("block_ids") or []]
        if len(source_block_ids) != len(set(source_block_ids)):
            raise QualificationError(f"chunk_block_identifier_duplicate:{chunk_id}")
        missing_block_ids = [value for value in source_block_ids if value not in blocks_by_id]
        if missing_block_ids:
            raise QualificationError(
                f"chunk_block_missing:{chunk_id}:{','.join(missing_block_ids)}"
            )
        for block_id in source_block_ids:
            block = blocks_by_id[block_id]
            _validate_authority(block, node_id=block_id)
            if (
                str(block.get("parent_document_id") or "")
                != str(chunk.get("parent_document_id") or "")
                or str(block.get("parent_section_id") or "")
                != str(chunk.get("parent_section_id") or "")
                or str(block.get("route_id") or "")
                != str(chunk.get("route_id") or "")
                or str(block.get("raw_body_sha256") or "")
                != str(chunk.get("raw_body_sha256") or "")
            ):
                raise QualificationError(
                    f"chunk_block_lineage_drift:{chunk_id}:{block_id}"
                )
            block_content = _require_string(
                block.get("content"), label=f"block_content:{block_id}"
            )
            _validated_text_sha(
                block_content,
                block.get("content_sha256"),
                label=f"block_sha:{block_id}",
            )
        chunk_content = _require_string(
            chunk.get("text"), label=f"chunk_text:{chunk_id}"
        )
        chunk_content_sha256 = _validated_text_sha(
            chunk_content,
            chunk.get("text_sha256"),
            label=f"chunk_sha:{chunk_id}",
        )
        raw_spans = chunk.get("retrieval_spans")
        if not isinstance(raw_spans, list) or not raw_spans:
            raise QualificationError(f"chunk_retrieval_spans_missing:{chunk_id}")
        if int(chunk.get("retrieval_span_count") or -1) != len(raw_spans):
            raise QualificationError(f"chunk_retrieval_span_count_drift:{chunk_id}")
        if canonical_digest(raw_spans) != _require_sha(
            chunk.get("retrieval_spans_sha256"),
            label=f"chunk_retrieval_spans_sha:{chunk_id}",
        ):
            raise QualificationError(f"chunk_retrieval_spans_digest_drift:{chunk_id}")
        spans: list[dict[str, Any]] = []
        normalized_chunk_content = re.sub(r"\s+", " ", chunk_content).strip()
        for span_index, raw_span in enumerate(raw_spans):
            if not isinstance(raw_span, Mapping):
                raise QualificationError(
                    f"chunk_retrieval_span_not_object:{chunk_id}:{span_index}"
                )
            if int(raw_span.get("span_index") or 0) != span_index:
                raise QualificationError(
                    f"chunk_retrieval_span_index_drift:{chunk_id}:{span_index}"
                )
            span_kind = _require_string(
                raw_span.get("span_kind"),
                label=f"chunk_retrieval_span_kind:{chunk_id}:{span_index}",
            ).casefold()
            span_content = _require_string(
                raw_span.get("content"),
                label=f"chunk_retrieval_span_content:{chunk_id}:{span_index}",
            )
            _validated_text_sha(
                span_content,
                raw_span.get("content_sha256"),
                label=f"chunk_retrieval_span_sha:{chunk_id}:{span_index}",
            )
            span_block_ids = [
                str(value) for value in raw_span.get("source_block_ids") or []
            ]
            if (
                not span_block_ids
                or len(span_block_ids) != len(set(span_block_ids))
                or not set(span_block_ids).issubset(set(source_block_ids))
            ):
                raise QualificationError(
                    f"chunk_retrieval_span_block_drift:{chunk_id}:{span_index}"
                )
            block_kinds = {
                str(blocks_by_id[block_id].get("block_kind") or "").casefold()
                for block_id in span_block_ids
            }
            if (
                (span_kind == "table" and "table" not in block_kinds)
                or (span_kind == "image" and "image" not in block_kinds)
                or (
                    span_kind not in {"table", "image"}
                    and not (block_kinds - {"table", "image"})
                )
            ):
                raise QualificationError(
                    f"chunk_retrieval_span_kind_block_drift:{chunk_id}:{span_index}"
                )
            if (
                re.sub(r"\s+", " ", span_content).strip()
                not in normalized_chunk_content
            ):
                raise QualificationError(
                    f"chunk_retrieval_span_expands_chunk:{chunk_id}:{span_index}"
                )
            spans.append(
                {
                    "span_index": span_index,
                    "span_kind": span_kind,
                    "source_block_ids": span_block_ids,
                    "content": span_content,
                }
            )
        if contains_table != any(span["span_kind"] == "table" for span in spans):
            raise QualificationError(f"chunk_contains_table_span_drift:{chunk_id}")
        reconstructed_span_sha = hashlib.sha256(
            "\n".join(span["content"] for span in spans).encode("utf-8")
        ).hexdigest()
        if reconstructed_span_sha != _require_sha(
            chunk.get("retrieval_span_text_sha256"),
            label=f"chunk_retrieval_span_text_sha:{chunk_id}",
        ):
            raise QualificationError(
                f"chunk_retrieval_span_text_digest_drift:{chunk_id}"
            )
        compiled_variants: list[dict[str, Any]] = []
        if contains_table:
            prose_span_runs: list[list[Mapping[str, Any]]] = []
            current_run: list[Mapping[str, Any]] = []
            for span in spans:
                if span["span_kind"] in {"table", "image"} or not _visible_text(
                    span["content"]
                ):
                    if current_run:
                        prose_span_runs.append(current_run)
                        current_run = []
                    continue
                current_run.append(span)
            if current_run:
                prose_span_runs.append(current_run)
            for mixed_span_index, prose_spans in enumerate(prose_span_runs):
                selected_block_ids = list(
                    dict.fromkeys(
                        block_id
                        for span in prose_spans
                        for block_id in span["source_block_ids"]
                    )
                )
                content = "\n\n".join(
                    str(span["content"]).strip() for span in prose_spans
                )
                content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
                node_id = "MIXEDPROSE::" + canonical_digest(
                    {
                        "parent_document_id": chunk.get("parent_document_id"),
                        "parent_section_id": chunk.get("parent_section_id"),
                        "source_block_ids": selected_block_ids,
                        "content_sha256": content_sha256,
                    }
                )[:24].upper()
                compiled_variants.append(
                    {
                        "node_id": node_id,
                        "node_kind": "mixed_prose_span",
                        "mixed_span_index": mixed_span_index,
                        "source_retrieval_span_indices": [
                            int(span["span_index"]) for span in prose_spans
                        ],
                        "source_block_ids": selected_block_ids,
                        "content": content,
                        "content_sha256": content_sha256,
                    }
                )
                mixed_prose_raw_run_count += 1
                mixed_prose_raw_character_count += len(content)
        else:
            if _visible_text(chunk_content):
                compiled_variants.append(
                    {
                        "node_id": chunk_id,
                        "node_kind": "chunk",
                        "mixed_span_index": None,
                        "source_retrieval_span_indices": [
                            int(span["span_index"]) for span in spans
                        ],
                        "source_block_ids": source_block_ids,
                        "content": chunk_content,
                        "content_sha256": chunk_content_sha256,
                    }
                )
        metadata = inherited(chunk)
        for variant in compiled_variants:
            source_span = {
                "source_chunk_id": chunk_id,
                "section_chunk_index": chunk.get("section_chunk_index"),
                "mixed_span_index": variant["mixed_span_index"],
                "retrieval_span_indices": variant[
                    "source_retrieval_span_indices"
                ],
                "source_chunk_text_sha256": chunk.get("text_sha256"),
            }
            node = {
                "schema_version": NODE_SCHEMA,
                "node_id": variant["node_id"],
                "lane": "prose_leaf",
                "node_kind": variant["node_kind"],
                **metadata,
                "section_chunk_index": chunk.get("section_chunk_index"),
                "mixed_span_index": variant["mixed_span_index"],
                "source_chunk_id": chunk_id,
                "source_chunk_ids": [chunk_id],
                "source_spans": [source_span],
                "source_block_ids": variant["source_block_ids"],
                "source_chunk_text_sha256": chunk.get("text_sha256"),
                "content": variant["content"],
                "content_sha256": variant["content_sha256"],
                "model_text": _model_text(metadata, str(variant["content"])),
                "candidate_is_not_evidence": True,
                "numeric_authority": False,
                "citation_eligible": False,
            }
            if variant["node_kind"] == "mixed_prose_span":
                existing = mixed_by_id.get(str(variant["node_id"]))
                if existing is not None:
                    if (
                        existing["content_sha256"] != node["content_sha256"]
                        or existing["source_block_ids"] != node["source_block_ids"]
                        or existing["parent_document_id"]
                        != node["parent_document_id"]
                        or existing["parent_section_id"]
                        != node["parent_section_id"]
                    ):
                        raise QualificationError(
                            f"mixed_prose_identifier_collision:{variant['node_id']}"
                        )
                    existing["source_chunk_ids"].append(chunk_id)
                    existing["source_spans"].append(source_span)
                    continue
                mixed_by_id[str(variant["node_id"])] = node
            prose.append(node)

    tables: list[dict[str, Any]] = []
    images: list[dict[str, Any]] = []
    for block in blocks:
        kind = str(block.get("block_kind") or "")
        if kind not in {"table", "image"}:
            continue
        block_id = _require_string(block.get("block_id"), label="block_id")
        _validate_authority(block, node_id=block_id)
        metadata = inherited(block)
        content = _require_string(block.get("content"), label=f"block_content:{block_id}")
        base = {
            "schema_version": NODE_SCHEMA,
            "node_id": block_id,
            **metadata,
            "content": content,
            "content_sha256": _validated_text_sha(
                content,
                block.get("content_sha256"),
                label=f"block_sha:{block_id}",
            ),
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
            "citation_eligible": False,
        }
        if kind == "table":
            tables.append(
                {
                    **base,
                    "lane": "table_leaf",
                    "node_kind": "table",
                    "table_id": block.get("table_id"),
                    "table_row_count": block.get("table_row_count"),
                    "table_column_count": block.get("table_column_count"),
                    "model_text": _model_text(metadata, content),
                }
            )
        else:
            images.append(
                {
                    **base,
                    "lane": "image_catalog",
                    "node_kind": "image",
                    "retrieval_eligible": False,
                    "exclusion_reason": "research_material_image_asset_not_captured_and_qualified",
                    "image_asset_captured": block.get("image_asset_captured") is True,
                    "image_references": block.get("image_references") or [],
                }
            )

    all_ids = [row["node_id"] for row in [*parents, *prose, *tables, *images]]
    if len(all_ids) != len(set(all_ids)):
        raise QualificationError("retrieval_node_identifier_duplicate")
    if not parents or not prose or not tables:
        raise QualificationError("required_retrieval_lane_empty")
    mixed_prose = [
        row for row in prose if row.get("node_kind") == "mixed_prose_span"
    ]
    mixed_source_chunk_ids = {
        str(chunk_id)
        for row in mixed_prose
        for chunk_id in row.get("source_chunk_ids") or []
    }
    mixed_non_table_block_ids = {
        str(block_id)
        for row in mixed_prose
        for block_id in row.get("source_block_ids") or []
    }
    pure_chunk_non_table_block_ids = {
        str(block_id)
        for chunk in chunks
        if chunk.get("contains_table") is False
        for block_id in chunk.get("block_ids") or []
        if str(block_id) in blocks_by_id
        and str(blocks_by_id[str(block_id)].get("block_kind") or "")
        not in {"table", "image"}
        and _visible_text(blocks_by_id[str(block_id)].get("content"))
    }
    exclusive_mixed_block_ids = (
        mixed_non_table_block_ids - pure_chunk_non_table_block_ids
    )
    table_chunk_count = sum(chunk.get("contains_table") is True for chunk in chunks)
    return {
        "parents": parents,
        "prose": prose,
        "tables": tables,
        "leaves": [*prose, *tables],
        "images": images,
        "coverage": {
            "table_containing_chunk_count": table_chunk_count,
            "mixed_prose_source_chunk_count": len(mixed_source_chunk_ids),
            "mixed_prose_leaf_count": len(mixed_prose),
            "mixed_prose_raw_span_run_count": mixed_prose_raw_run_count,
            "mixed_prose_deduplicated_run_count": mixed_prose_raw_run_count
            - len(mixed_prose),
            "mixed_prose_raw_span_character_count": mixed_prose_raw_character_count,
            "mixed_prose_candidate_character_count": sum(
                len(str(row["content"])) for row in mixed_prose
            ),
            "table_or_image_only_chunk_count": table_chunk_count
            - len(mixed_source_chunk_ids),
            "mixed_non_table_unique_block_count": len(mixed_non_table_block_ids),
            "mixed_non_table_unique_character_count": sum(
                len(str(blocks_by_id[block_id]["content"]))
                for block_id in mixed_non_table_block_ids
            ),
            "mixed_non_table_exclusive_block_count": len(
                exclusive_mixed_block_ids
            ),
            "mixed_non_table_exclusive_character_count": sum(
                len(str(blocks_by_id[block_id]["content"]))
                for block_id in exclusive_mixed_block_ids
            ),
            "mixed_prose_compilation_digest": canonical_digest(
                [
                    {
                        "node_id": row["node_id"],
                        "source_chunk_ids": row["source_chunk_ids"],
                        "source_spans": row["source_spans"],
                        "source_block_ids": row["source_block_ids"],
                        "content_sha256": row["content_sha256"],
                    }
                    for row in mixed_prose
                ]
            ),
        },
    }


def _forbidden_qrel_key_present(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key) in {"answer", "expected_answer", "supporting_span"}
            or _forbidden_qrel_key_present(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_forbidden_qrel_key_present(child) for child in value)
    return False


def _validate_qrel_label_contract(
    *,
    query_id: str,
    raw: Mapping[str, Any],
    target_ids: Sequence[str],
    node_index: Mapping[str, Mapping[str, Any]],
) -> None:
    contract = raw.get("must_match")
    if not isinstance(contract, Mapping):
        raise QualificationError(f"qrel_must_match_contract_missing:{query_id}")
    issuer = str(contract.get("issuer") or "").strip().casefold()
    period = contract.get("period")
    routes = contract.get("routes")
    if routes is None and contract.get("route") is not None:
        routes = [contract.get("route")]
    allowed_routes = {
        str(value).strip() for value in (routes or []) if str(value).strip()
    }
    source_roles = contract.get("source_roles")
    if source_roles is None and contract.get("source_role") is not None:
        source_roles = [contract.get("source_role")]
    allowed_source_roles = {
        str(value).strip() for value in (source_roles or []) if str(value).strip()
    }
    for node_id in target_ids:
        node = node_index[node_id]
        if issuer and str(node.get("issuer_id") or "").strip().casefold() != issuer:
            raise QualificationError(f"qrel_issuer_contract_drift:{query_id}:{node_id}")
        if period is not None and str(node.get("fiscal_period") or "").strip() != str(period).strip():
            raise QualificationError(f"qrel_period_contract_drift:{query_id}:{node_id}")
        if allowed_routes and str(node.get("route_id") or "") not in allowed_routes:
            raise QualificationError(f"qrel_route_contract_drift:{query_id}:{node_id}")
        if allowed_source_roles and str(node.get("source_role") or "") not in allowed_source_roles:
            raise QualificationError(f"qrel_source_role_contract_drift:{query_id}:{node_id}")


def load_qrels(
    path: Path,
    *,
    node_index: Mapping[str, Mapping[str, Any]],
    corpus_artifacts: Mapping[str, Any],
) -> dict[str, Any]:
    qrels = _load_json(path)
    schema_version = str(qrels.get("schema_version") or "")
    if schema_version not in SUPPORTED_QRELS_SCHEMAS:
        raise QualificationError("qrels_schema_mismatch")
    structured_labels = schema_version == QRELS_SCHEMA
    if _forbidden_qrel_key_present(qrels):
        raise QualificationError("qrels_must_not_embed_answer")
    node_ids = set(node_index)
    bound = qrels.get("corpus_artifacts")
    if not isinstance(bound, Mapping):
        raise QualificationError("qrels_corpus_binding_missing")
    for name, artifact in corpus_artifacts.items():
        if name == "result.json":
            continue
        if str(bound.get(name) or "").lower() != artifact["sha256"]:
            raise QualificationError(f"qrels_corpus_binding_drift:{name}")
    raw_queries = qrels.get("queries")
    if not isinstance(raw_queries, list) or not raw_queries:
        raise QualificationError("qrels_queries_missing")
    seen: set[str] = set()
    queries: list[dict[str, Any]] = []
    for ordinal, raw in enumerate(raw_queries, start=1):
        if not isinstance(raw, Mapping):
            raise QualificationError(f"qrel_not_object:{ordinal}")
        query_id = _require_string(raw.get("query_id"), label=f"query_id:{ordinal}")
        if query_id in seen:
            raise QualificationError(f"query_id_duplicate:{query_id}")
        seen.add(query_id)
        expected_route = str(raw.get("expected_route") or "local").strip().lower()
        if expected_route not in {"local", "external"}:
            raise QualificationError(f"expected_route_invalid:{query_id}")
        gold = [str(value) for value in raw.get("gold_node_ids") or []]
        legacy_alternates = [
            str(value) for value in raw.get("acceptable_alternate_node_ids") or []
        ]
        if structured_labels:
            alternates = [
                str(value) for value in raw.get("direct_alternate_node_ids") or []
            ]
            if legacy_alternates != alternates:
                raise QualificationError(
                    f"qrel_legacy_direct_alternate_drift:{query_id}"
                )
            derivable = [str(value) for value in raw.get("derivable_node_ids") or []]
            partial = [str(value) for value in raw.get("partial_node_ids") or []]
        else:
            alternates = legacy_alternates
            derivable = []
            partial = []
        negatives = [str(value) for value in raw.get("hard_negative_node_ids") or []]
        targets = [*gold, *alternates, *derivable, *partial, *negatives]
        if len(targets) != len(set(targets)):
            raise QualificationError(f"qrel_target_overlap_or_duplicate:{query_id}")
        missing = sorted(set(targets) - node_ids)
        if missing:
            raise QualificationError(f"qrel_target_missing:{query_id}:{','.join(missing)}")
        if expected_route == "local" and not gold:
            raise QualificationError(f"local_qrel_gold_missing:{query_id}")
        if expected_route == "external" and (
            gold or alternates or derivable or partial
        ):
            raise QualificationError(f"external_qrel_must_not_fake_local_gold:{query_id}")
        gold_requirement = str(raw.get("gold_requirement") or "any").strip().lower()
        if gold_requirement not in {"any", "all"}:
            raise QualificationError(f"gold_requirement_invalid:{query_id}")
        scope = _normalized_retrieval_scope(
            raw.get("retrieval_scope"),
            query_id=query_id,
            required=structured_labels and expected_route == "local",
        )
        if expected_route == "external" and any(scope.values()):
            raise QualificationError(f"external_qrel_scope_must_be_empty:{query_id}")
        if structured_labels and expected_route == "local":
            if not scope["issuer_ids"] or not scope["source_roles"]:
                raise QualificationError(f"local_qrel_scope_underbounded:{query_id}")
            for node_id in [*gold, *alternates, *derivable, *partial]:
                if not _node_matches_retrieval_scope(node_index[node_id], scope):
                    raise QualificationError(
                        f"qrel_retrieval_scope_target_drift:{query_id}:{node_id}"
                    )
        if expected_route == "local":
            _validate_qrel_label_contract(
                query_id=query_id,
                raw=raw,
                target_ids=gold if structured_labels else [*gold, *alternates],
                node_index=node_index,
            )
        queries.append(
            {
                **dict(raw),
                "query_id": query_id,
                "question_zh": _require_string(raw.get("question_zh"), label=f"question_zh:{query_id}"),
                "retrieval_query_en": _require_string(raw.get("retrieval_query_en"), label=f"retrieval_query_en:{query_id}"),
                "expected_route": expected_route,
                "critical": raw.get("critical") is True,
                "gold_requirement": gold_requirement,
                "gold_node_ids": gold,
                "acceptable_alternate_node_ids": alternates,
                "direct_alternate_node_ids": alternates,
                "derivable_node_ids": derivable,
                "partial_node_ids": partial,
                "hard_negative_node_ids": negatives,
                "retrieval_scope": scope,
            }
        )
    return {**qrels, "queries": queries}


def _rank(scores: Sequence[float], nodes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if len(scores) != len(nodes):
        raise QualificationError("score_count_mismatch")
    ordered = sorted(
        range(len(nodes)),
        key=lambda index: (-float(scores[index]), str(nodes[index]["node_id"])),
    )
    return [
        {
            "rank": rank,
            "node_id": str(nodes[index]["node_id"]),
            "score": float(scores[index]),
        }
        for rank, index in enumerate(ordered, start=1)
    ]


def _normalized_retrieval_scope(
    value: Any,
    *,
    query_id: str,
    required: bool,
) -> dict[str, list[str]]:
    if value is None and not required:
        return {"issuer_ids": [], "fiscal_periods": [], "source_roles": []}
    if not isinstance(value, Mapping):
        raise QualificationError(f"retrieval_scope_missing_or_not_object:{query_id}")
    forbidden = {
        "route",
        "routes",
        "route_id",
        "route_ids",
        "node_id",
        "node_ids",
        "gold_node_ids",
        "direct_alternate_node_ids",
        "acceptable_alternate_node_ids",
        "derivable_node_ids",
        "partial_node_ids",
        "hard_negative_node_ids",
    }
    unexpected = sorted(str(key) for key in value if str(key) not in {
        "issuer_ids",
        "fiscal_periods",
        "source_roles",
    })
    if set(unexpected) & forbidden:
        raise QualificationError(f"retrieval_scope_answer_or_route_key_forbidden:{query_id}")
    if unexpected:
        raise QualificationError(
            f"retrieval_scope_unknown_key:{query_id}:{','.join(unexpected)}"
        )
    normalized: dict[str, list[str]] = {}
    for key in ("issuer_ids", "fiscal_periods", "source_roles"):
        raw_values = value.get(key, [])
        if not isinstance(raw_values, list):
            raise QualificationError(f"retrieval_scope_field_not_list:{query_id}:{key}")
        values = [str(item).strip() for item in raw_values if str(item).strip()]
        if len(values) != len(raw_values) or len(values) != len(set(values)):
            raise QualificationError(f"retrieval_scope_field_invalid:{query_id}:{key}")
        normalized[key] = values
    return normalized


def _node_matches_retrieval_scope(
    node: Mapping[str, Any], scope: Mapping[str, Sequence[str]]
) -> bool:
    issuer_ids = {str(value).casefold() for value in scope.get("issuer_ids") or []}
    fiscal_periods = {str(value) for value in scope.get("fiscal_periods") or []}
    source_roles = {str(value) for value in scope.get("source_roles") or []}
    return (
        (not issuer_ids or str(node.get("issuer_id") or "").casefold() in issuer_ids)
        and (
            not fiscal_periods
            or str(node.get("fiscal_period") or "") in fiscal_periods
        )
        and (
            not source_roles
            or str(node.get("source_role") or "") in source_roles
        )
    )


def _eligible_nodes_for_query(
    rows: Sequence[Mapping[str, Any]], query: Mapping[str, Any]
) -> list[Mapping[str, Any]]:
    if str(query.get("expected_route") or "local") == "external":
        return list(rows)
    scope = query.get("retrieval_scope")
    if not isinstance(scope, Mapping) or not any(scope.values()):
        return list(rows)
    return [row for row in rows if _node_matches_retrieval_scope(row, scope)]


def _scope_receipt(query: Mapping[str, Any]) -> dict[str, Any]:
    scope = query.get("retrieval_scope")
    return {
        "expected_route": str(query.get("expected_route") or "local"),
        "answer_free_retrieval_scope": dict(scope) if isinstance(scope, Mapping) else {},
        "scope_applied": str(query.get("expected_route") or "local") == "local"
        and isinstance(scope, Mapping)
        and any(scope.values()),
    }


def run_bm25(
    *,
    nodes: Mapping[str, list[dict[str, Any]]],
    queries: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    module = importlib.import_module("rank_bm25")
    expected = policy["execution"]["rank_bm25_runtime_overlay"]
    origin = Path(str(getattr(module, "__file__", ""))).resolve()
    if origin.as_posix() != Path(str(expected["path"])).resolve().as_posix():
        raise QualificationError("rank_bm25_import_origin_drift")
    if sha256_file(origin) != str(expected["sha256"]):
        raise QualificationError("rank_bm25_import_digest_drift")
    BM25Okapi = module.BM25Okapi

    lanes = {
        "leaf_all": nodes["leaves"],
        "parent": nodes["parents"],
        "prose": nodes["prose"],
        "table": nodes["tables"],
    }
    runtimes: dict[
        tuple[str, str], tuple[list[Mapping[str, Any]], Any | None]
    ] = {}
    output: dict[str, dict[str, Any]] = {}
    for query in queries:
        query_id = str(query["query_id"])
        tokens = tokenize(str(query["retrieval_query_en"]))
        if not tokens:
            raise QualificationError(f"bm25_query_empty_after_tokenization:{query_id}")
        scope_receipt = _scope_receipt(query)
        scope_digest = canonical_digest(scope_receipt)
        eligible_leaf_parent_ids = {
            str(row.get("parent_section_id") or "")
            for row in _eligible_nodes_for_query(nodes["leaves"], query)
        }
        lane_rankings: dict[str, list[dict[str, Any]]] = {}
        eligible_counts: dict[str, int] = {}
        for lane, lane_rows in lanes.items():
            cache_key = (scope_digest, lane)
            cached = runtimes.get(cache_key)
            if cached is None:
                eligible_rows = _eligible_nodes_for_query(lane_rows, query)
                if lane == "parent":
                    eligible_rows = [
                        row
                        for row in eligible_rows
                        if str(row.get("node_id") or "")
                        in eligible_leaf_parent_ids
                    ]
                runtime = (
                    BM25Okapi(
                        [tokenize(str(row["model_text"])) for row in eligible_rows]
                    )
                    if eligible_rows
                    else None
                )
                cached = (eligible_rows, runtime)
                runtimes[cache_key] = cached
            eligible_rows, runtime = cached
            eligible_counts[lane] = len(eligible_rows)
            lane_rankings[lane] = (
                _rank(runtime.get_scores(tokens).tolist(), eligible_rows)
                if runtime is not None
                else []
            )
        if not lane_rankings["leaf_all"]:
            raise QualificationError(f"bm25_eligible_leaf_set_empty:{query_id}")
        output[query_id] = {
            "schema_version": ROUTE_RESULT_SCHEMA,
            "query_id": query_id,
            "route": "bm25",
            "ranking": lane_rankings.pop("leaf_all"),
            "lane_rankings": lane_rankings,
            "retrieval_scope_receipt": scope_receipt,
            "eligible_candidate_counts": eligible_counts,
        }
    return output


def _release_cuda_runtime() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def _reset_cuda_peak_memory() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
    except ImportError:
        pass


def _cuda_resource_snapshot() -> dict[str, Any]:
    try:
        import torch

        if not torch.cuda.is_available():
            return {"cuda_available": False}
        properties = torch.cuda.get_device_properties(torch.cuda.current_device())
        return {
            "cuda_available": True,
            "device_name": properties.name,
            "device_total_bytes": int(properties.total_memory),
            "allocated_bytes": int(torch.cuda.memory_allocated()),
            "reserved_bytes": int(torch.cuda.memory_reserved()),
            "peak_allocated_bytes": int(torch.cuda.max_memory_allocated()),
            "peak_reserved_bytes": int(torch.cuda.max_memory_reserved()),
        }
    except ImportError:
        return {"cuda_available": None}


def _load_repo_runtime_module(name: str, path: Path) -> Any:
    resolved = path.resolve()
    spec = importlib.util.spec_from_file_location(name, resolved)
    if spec is None or spec.loader is None:
        raise QualificationError(f"runtime_module_spec_invalid:{resolved}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _token_length_stats(lengths: Sequence[int], *, maximum: int) -> dict[str, Any]:
    ordered = sorted(int(value) for value in lengths)
    if not ordered:
        return {
            "count": 0,
            "maximum_allowed": maximum,
            "observed_maximum": 0,
            "observed_p95": 0,
            "truncated_count": 0,
        }
    p95_index = min(len(ordered) - 1, max(0, int(len(ordered) * 0.95) - 1))
    return {
        "count": len(ordered),
        "maximum_allowed": maximum,
        "observed_maximum": ordered[-1],
        "observed_p95": ordered[p95_index],
        "truncated_count": sum(value > maximum for value in ordered),
    }


def run_dense(
    *,
    nodes: Mapping[str, list[dict[str, Any]]],
    queries: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    cache_dir: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    import numpy as np

    embedding_runtime = _load_repo_runtime_module(
        "fin_ia_dell_embedding_runtime",
        SRC_ROOT / "retrieval" / "embedding_runtime.py",
    )
    load_or_build_qwen_embedding_cache = (
        embedding_runtime.load_or_build_qwen_embedding_cache
    )
    local_model_identity = embedding_runtime.local_model_identity

    dense_policy = policy["retrieval"]["dense"]
    model_dir = Path(str(dense_policy["model_dir"])).resolve()
    model_identity = local_model_identity(model_dir, str(dense_policy["model_id"]))
    all_nodes = list(nodes["leaves"])
    objects = [
        {
            "compiled_object_id": row["node_id"],
            "model_text": row["model_text"],
        }
        for row in all_nodes
    ]
    object_digest = canonical_digest(
        [
            {
                "node_id": row["node_id"],
                "model_text_sha256": hashlib.sha256(
                    str(row["model_text"]).encode("utf-8")
                ).hexdigest(),
            }
            for row in all_nodes
        ]
    )
    runtime: Any | None = None
    _reset_cuda_peak_memory()
    try:
        dense, cache_manifest, runtime = load_or_build_qwen_embedding_cache(
            objects=objects,
            object_sha256=object_digest,
            model_dir=model_dir,
            model_identity=model_identity,
            cache_dir=cache_dir,
            maximum_sequence_length=int(dense_policy["maximum_sequence_length"]),
            batch_size=int(dense_policy["batch_size"]),
        )
        if cache_manifest.get("cache_hit") is not False:
            raise QualificationError("embedding_artifact_must_be_fresh")
        instruction = _require_string(dense_policy.get("query_instruction"), label="dense_query_instruction")
        if not instruction.startswith("Instruct: ") or "\nQuery:" not in instruction:
            raise QualificationError("dense_query_instruction_format_invalid")
        query_texts = [str(query["retrieval_query_en"]) for query in queries]
        serialized_query_texts = [instruction + value for value in query_texts]
        tokenizer = runtime.tokenizer
        document_token_ids = tokenizer(
            [str(row["model_text"]) for row in objects],
            padding=False,
            truncation=False,
            return_attention_mask=False,
        )["input_ids"]
        query_token_ids = tokenizer(
            serialized_query_texts,
            padding=False,
            truncation=False,
            return_attention_mask=False,
        )["input_ids"]
        query_vectors = runtime.encode(
            serialized_query_texts,
            batch_size=min(int(dense_policy["batch_size"]), len(query_texts)),
            prompt=None,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype(np.float32)
        dense_values = np.asarray(dense, dtype=np.float32)
        if not np.isfinite(query_vectors).all() or not np.isfinite(dense_values).all():
            raise QualificationError("dense_embedding_non_finite")
        scores = query_vectors @ dense_values.T
        parent_nodes = nodes["parents"]
        leaf_index_by_id = {
            str(row["node_id"]): index for index, row in enumerate(nodes["leaves"])
        }
        prose_ids = {row["node_id"] for row in nodes["prose"]}
        table_ids = {row["node_id"] for row in nodes["tables"]}
        output: dict[str, dict[str, Any]] = {}
        for query_index, query in enumerate(queries):
            query_id = str(query["query_id"])
            eligible_leaves = _eligible_nodes_for_query(nodes["leaves"], query)
            if not eligible_leaves:
                raise QualificationError(f"dense_eligible_leaf_set_empty:{query_id}")
            eligible_leaf_scores = [
                float(scores[query_index, leaf_index_by_id[str(leaf["node_id"])]])
                for leaf in eligible_leaves
            ]
            leaf_ranking = _rank(eligible_leaf_scores, eligible_leaves)
            eligible_parent_ids = {
                str(leaf.get("parent_section_id") or "") for leaf in eligible_leaves
            }
            eligible_parents = [
                row
                for row in parent_nodes
                if str(row["node_id"]) in eligible_parent_ids
            ]
            eligible_parent_index = {
                str(row["node_id"]): index for index, row in enumerate(eligible_parents)
            }
            parent_scores = [-1.0e9] * len(eligible_parents)
            for leaf, score in zip(
                eligible_leaves, eligible_leaf_scores, strict=True
            ):
                parent_id = str(leaf.get("parent_section_id") or "")
                parent_index = eligible_parent_index.get(parent_id)
                if parent_index is not None:
                    parent_scores[parent_index] = max(parent_scores[parent_index], float(score))
            if any(score <= -1.0e8 for score in parent_scores):
                raise QualificationError(f"dense_parent_projection_missing:{query_id}")
            parent_ranking = _rank(parent_scores, eligible_parents)
            output[query_id] = {
                "schema_version": ROUTE_RESULT_SCHEMA,
                "query_id": query_id,
                "route": "dense",
                "ranking": leaf_ranking,
                "lane_rankings": {
                    "parent": parent_ranking,
                    "prose": [row for row in leaf_ranking if row["node_id"] in prose_ids],
                    "table": [row for row in leaf_ranking if row["node_id"] in table_ids],
                },
                "retrieval_scope_receipt": _scope_receipt(query),
                "eligible_candidate_counts": {
                    "leaf_all": len(eligible_leaves),
                    "parent": len(eligible_parents),
                    "prose": sum(
                        str(row["node_id"]) in prose_ids for row in eligible_leaves
                    ),
                    "table": sum(
                        str(row["node_id"]) in table_ids for row in eligible_leaves
                    ),
                },
            }
        runtime_info = {
            "model_identity": model_identity,
            "embedding_artifact_manifest": cache_manifest,
            "query_count": len(query_texts),
            "embedding_dimension": int(query_vectors.shape[1]),
            "embedded_candidate_lane": "leaves_only",
            "embedded_candidate_count": len(all_nodes),
            "parent_ranking_strategy": "maximum_child_cosine_projection",
            "parent_section_count": len(nodes["parents"]),
            "document_serialization_digest": canonical_digest(
                [str(row["model_text"]) for row in objects]
            ),
            "query_serialization_template": instruction + "{query}",
            "query_serialization_digest": canonical_digest(serialized_query_texts),
            "document_token_lengths": _token_length_stats(
                [len(value) for value in document_token_ids],
                maximum=int(dense_policy["maximum_sequence_length"]),
            ),
            "query_token_lengths": _token_length_stats(
                [len(value) for value in query_token_ids],
                maximum=int(dense_policy["maximum_sequence_length"]),
            ),
            "document_forward_batch_count": (
                len(objects) + int(dense_policy["batch_size"]) - 1
            )
            // int(dense_policy["batch_size"]),
            "query_forward_batch_count": (
                len(query_texts)
                + min(int(dense_policy["batch_size"]), len(query_texts))
                - 1
            )
            // min(int(dense_policy["batch_size"]), len(query_texts)),
            "resource_snapshot": _cuda_resource_snapshot(),
        }
        if local_model_identity(model_dir, str(dense_policy["model_id"])) != model_identity:
            raise QualificationError("dense_model_identity_changed_during_inference")
        return output, runtime_info
    finally:
        if runtime is not None:
            del runtime
        _release_cuda_runtime()


def run_hybrid(
    *,
    bm25: Mapping[str, Mapping[str, Any]],
    dense: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    config = policy["retrieval"]["hybrid"]
    constant = int(config["rrf_constant"])
    depth = int(config["source_depth"])
    weights = {"bm25": float(config["bm25_weight"]), "dense": float(config["dense_weight"])}
    output: dict[str, dict[str, Any]] = {}
    if set(bm25) != set(dense):
        raise QualificationError("hybrid_query_set_drift")
    for query_id in bm25:
        bm25_counts = bm25[query_id].get("eligible_candidate_counts") or {}
        dense_counts = dense[query_id].get("eligible_candidate_counts") or {}
        if (
            bm25[query_id].get("retrieval_scope_receipt")
            != dense[query_id].get("retrieval_scope_receipt")
            or any(
                bm25_counts.get(lane) != dense_counts.get(lane)
                for lane in ("leaf_all", "parent", "prose", "table")
            )
        ):
            raise QualificationError(f"hybrid_retrieval_scope_drift:{query_id}")
        scores: dict[str, float] = {}
        source_ranks: dict[str, dict[str, int]] = {}
        for route_name, rows in (("bm25", bm25[query_id]["ranking"]), ("dense", dense[query_id]["ranking"])):
            for row in rows[:depth]:
                node_id = str(row["node_id"])
                rank = int(row["rank"])
                scores[node_id] = scores.get(node_id, 0.0) + weights[route_name] / (constant + rank)
                source_ranks.setdefault(node_id, {})[route_name] = rank
        ordered_ids = sorted(scores, key=lambda node_id: (-scores[node_id], node_id))
        output[query_id] = {
            "schema_version": ROUTE_RESULT_SCHEMA,
            "query_id": query_id,
            "route": "hybrid_rrf",
            "ranking": [
                {
                    "rank": rank,
                    "node_id": node_id,
                    "score": scores[node_id],
                    "source_ranks": source_ranks[node_id],
                }
                for rank, node_id in enumerate(ordered_ids, start=1)
            ],
            "lane_rankings": {},
            "retrieval_scope_receipt": bm25[query_id].get(
                "retrieval_scope_receipt"
            ),
            "eligible_candidate_counts": bm25[query_id].get(
                "eligible_candidate_counts"
            ),
        }
    return output


def run_reranker(
    *,
    hybrid: Mapping[str, Mapping[str, Any]],
    queries: Sequence[Mapping[str, Any]],
    node_index: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    cross_encoder_runtime = _load_repo_runtime_module(
        "fin_ia_dell_cross_encoder_runtime",
        SRC_ROOT / "retrieval" / "cross_encoder.py",
    )
    cross_encoder_model_identity = cross_encoder_runtime.cross_encoder_model_identity
    load_local_qwen3_reranker = cross_encoder_runtime.load_local_qwen3_reranker
    score_qwen3_reranker_pairs = cross_encoder_runtime.score_qwen3_reranker_pairs

    config = policy["retrieval"]["reranker"]
    model_dir = Path(str(config["model_dir"])).resolve()
    depth = int(config["candidate_depth"])
    pairs: list[tuple[str, str]] = []
    slices: dict[str, tuple[int, int, list[Mapping[str, Any]]]] = {}
    for query in queries:
        query_id = str(query["query_id"])
        candidates = list(hybrid[query_id]["ranking"][:depth])
        start = len(pairs)
        pairs.extend(
            (str(query["retrieval_query_en"]), str(node_index[str(row["node_id"])]["model_text"]))
            for row in candidates
        )
        slices[query_id] = (start, len(pairs), candidates)
    runtime: Any | None = None
    _reset_cuda_peak_memory()
    model_identity = cross_encoder_model_identity(
        model_dir, model_id=str(config["model_id"])
    )
    try:
        runtime = load_local_qwen3_reranker(
            model_dir,
            maximum_sequence_length=int(config["maximum_sequence_length"]),
            instruction=str(config["instruction"]),
        )
        if not pairs:
            raise QualificationError("reranker_pairs_empty")
        tokenizer = runtime[0]
        maximum_sequence_length = int(runtime[3])
        runtime_instruction = str(runtime[4])
        prefix_tokens = runtime[7]
        suffix_tokens = runtime[8]
        serialized_pairs = [
            f"<Instruct>: {runtime_instruction}\n<Query>: {query}\n<Document>: {document}"
            for query, document in pairs
        ]
        content_token_ids = tokenizer(
            serialized_pairs,
            padding=False,
            truncation=False,
            return_attention_mask=False,
        )["input_ids"]
        pair_token_lengths = [
            len(prefix_tokens) + len(value) + len(suffix_tokens)
            for value in content_token_ids
        ]
        smoke_scores = score_qwen3_reranker_pairs(runtime, pairs[:1], batch_size=1)
        scores = [
            *smoke_scores,
            *score_qwen3_reranker_pairs(
                runtime, pairs[1:], batch_size=int(config["batch_size"])
            ),
        ]
        if len(scores) != len(pairs) or not all(math.isfinite(float(value)) for value in scores):
            raise QualificationError("reranker_score_contract_invalid")
        output: dict[str, dict[str, Any]] = {}
        for query_id, (start, end, candidates) in slices.items():
            candidate_scores = scores[start:end]
            ordered = sorted(
                range(len(candidates)),
                key=lambda index: (-float(candidate_scores[index]), str(candidates[index]["node_id"])),
            )
            output[query_id] = {
                "schema_version": ROUTE_RESULT_SCHEMA,
                "query_id": query_id,
                "route": "hybrid_qwen_reranker",
                "ranking": [
                    {
                        "rank": rank,
                        "node_id": str(candidates[index]["node_id"]),
                        "score": float(candidate_scores[index]),
                        "hybrid_rank": int(candidates[index]["rank"]),
                    }
                    for rank, index in enumerate(ordered, start=1)
                ],
                "lane_rankings": {},
                "retrieval_scope_receipt": hybrid[query_id].get(
                    "retrieval_scope_receipt"
                ),
                "eligible_candidate_counts": hybrid[query_id].get(
                    "eligible_candidate_counts"
                ),
            }
        runtime_info = {
            "model_identity": model_identity,
            "pair_count": len(pairs),
            "candidate_depth": depth,
            "resource_smoke_pair_count": 1,
            "pair_serialization_digest": canonical_digest(serialized_pairs),
            "pair_token_lengths": _token_length_stats(
                pair_token_lengths,
                maximum=maximum_sequence_length,
            ),
            "forward_batch_count": 1
            + (
                max(0, len(pairs) - 1) + int(config["batch_size"]) - 1
            )
            // int(config["batch_size"]),
            "resource_snapshot": _cuda_resource_snapshot(),
        }
        if cross_encoder_model_identity(
            model_dir, model_id=str(config["model_id"])
        ) != model_identity:
            raise QualificationError("reranker_model_identity_changed_during_inference")
        return output, runtime_info
    finally:
        if runtime is not None:
            del runtime
        _release_cuda_runtime()


def _acceptable_ids(query: Mapping[str, Any]) -> set[str]:
    direct = query.get("direct_alternate_node_ids")
    if direct is None:
        direct = query.get("acceptable_alternate_node_ids") or []
    return set(query["gold_node_ids"]) | set(direct)


def evaluate_route(
    *, route_results: Mapping[str, Mapping[str, Any]], queries: Sequence[Mapping[str, Any]], cutoffs: Sequence[int]
) -> dict[str, Any]:
    local = [query for query in queries if query["expected_route"] == "local"]
    if not local:
        raise QualificationError("local_qrels_empty")
    details: list[dict[str, Any]] = []
    for query in local:
        query_id = str(query["query_id"])
        ranking = route_results[query_id]["ranking"]
        rank_by_id = {str(row["node_id"]): int(row["rank"]) for row in ranking}
        acceptable = _acceptable_ids(query)
        first = min((rank_by_id[node_id] for node_id in acceptable if node_id in rank_by_id), default=None)
        detail: dict[str, Any] = {
            "query_id": query_id,
            "critical": query["critical"],
            "gold_requirement": query["gold_requirement"],
            "first_acceptable_rank": first,
            "gold_ranks": {node_id: rank_by_id.get(node_id) for node_id in query["gold_node_ids"]},
            "direct_alternate_ranks": {
                node_id: rank_by_id.get(node_id)
                for node_id in query.get("direct_alternate_node_ids")
                or query.get("acceptable_alternate_node_ids")
                or []
            },
            "derivable_ranks": {
                node_id: rank_by_id.get(node_id)
                for node_id in query.get("derivable_node_ids") or []
            },
            "partial_ranks": {
                node_id: rank_by_id.get(node_id)
                for node_id in query.get("partial_node_ids") or []
            },
            "hard_negative_ranks": {node_id: rank_by_id.get(node_id) for node_id in query["hard_negative_node_ids"]},
        }
        detail["alternate_ranks"] = detail["direct_alternate_ranks"]
        first_hard_negative = min(
            (
                rank_by_id[node_id]
                for node_id in query["hard_negative_node_ids"]
                if node_id in rank_by_id
            ),
            default=None,
        )
        detail["first_hard_negative_rank"] = first_hard_negative
        detail["acceptable_precedes_first_hard_negative"] = first is not None and (
            first_hard_negative is None or first < first_hard_negative
        )
        delivery_by_rank = {
            int(row["rank"]): [str(value) for value in row.get("expanded_context_node_ids") or []]
            for row in route_results[query_id].get("delivery") or []
        }
        for cutoff in cutoffs:
            anchors = {str(row["node_id"]) for row in ranking[:cutoff]}
            delivered = set(anchors)
            for rank, expanded_ids in delivery_by_rank.items():
                if rank <= cutoff:
                    delivered.update(expanded_ids)
            if query["gold_requirement"] == "all":
                required_ids = set(query["gold_node_ids"])
                anchor_satisfied = required_ids.issubset(anchors)
                delivered_satisfied = required_ids.issubset(delivered)
            else:
                required_ids = acceptable
                anchor_satisfied = bool(required_ids & anchors)
                delivered_satisfied = bool(required_ids & delivered)
            detail[f"anchor_required_facets_satisfied_at_{cutoff}"] = (
                anchor_satisfied
            )
            detail[f"anchor_missing_required_node_ids_at_{cutoff}"] = (
                sorted(required_ids - anchors)
                if query["gold_requirement"] == "all"
                else ([] if anchor_satisfied else sorted(required_ids))
            )
            detail[f"delivered_context_required_facets_satisfied_at_{cutoff}"] = (
                delivered_satisfied
            )
            detail[f"delivered_context_missing_required_node_ids_at_{cutoff}"] = (
                sorted(required_ids - delivered)
                if query["gold_requirement"] == "all"
                else ([] if delivered_satisfied else sorted(required_ids))
            )
            # Compatibility aliases retain the original delivered-context meaning.
            detail[f"required_facets_satisfied_at_{cutoff}"] = delivered_satisfied
            detail[f"missing_required_node_ids_at_{cutoff}"] = detail[
                f"delivered_context_missing_required_node_ids_at_{cutoff}"
            ]
            detail[f"delivered_hard_negative_ids_at_{cutoff}"] = sorted(
                set(query["hard_negative_node_ids"]) & delivered
            )
        details.append(detail)
    metrics: dict[str, Any] = {
        "query_count": len(details),
        "critical_query_count": sum(row["critical"] for row in details),
        "mrr_acceptable": sum(0.0 if row["first_acceptable_rank"] is None else 1.0 / row["first_acceptable_rank"] for row in details) / len(details),
        "hard_negative_rank_1_count": sum(
            row["first_hard_negative_rank"] == 1 for row in details
        ),
        "critical_acceptable_precedence_failure_count": sum(
            row["critical"]
            and not row["acceptable_precedes_first_hard_negative"]
            for row in details
        ),
        "queries": details,
    }
    for cutoff in cutoffs:
        metrics[f"hit_rate_at_{cutoff}"] = sum(
            row["first_acceptable_rank"] is not None and row["first_acceptable_rank"] <= cutoff
            for row in details
        ) / len(details)
        metrics[f"critical_miss_count_at_{cutoff}"] = sum(
            row["critical"] and (row["first_acceptable_rank"] is None or row["first_acceptable_rank"] > cutoff)
            for row in details
        )
        metrics[f"critical_required_facet_miss_count_at_{cutoff}"] = sum(
            row["critical"] and not row[f"required_facets_satisfied_at_{cutoff}"]
            for row in details
        )
        metrics[f"required_facet_satisfaction_rate_at_{cutoff}"] = sum(
            row[f"required_facets_satisfied_at_{cutoff}"] for row in details
        ) / len(details)
        metrics[f"critical_anchor_required_facet_miss_count_at_{cutoff}"] = sum(
            row["critical"]
            and not row[f"anchor_required_facets_satisfied_at_{cutoff}"]
            for row in details
        )
        metrics[f"anchor_required_facet_satisfaction_rate_at_{cutoff}"] = sum(
            row[f"anchor_required_facets_satisfied_at_{cutoff}"]
            for row in details
        ) / len(details)
        metrics[
            f"critical_delivered_context_required_facet_miss_count_at_{cutoff}"
        ] = metrics[f"critical_required_facet_miss_count_at_{cutoff}"]
        metrics[
            f"delivered_context_required_facet_satisfaction_rate_at_{cutoff}"
        ] = metrics[f"required_facet_satisfaction_rate_at_{cutoff}"]
        metrics[f"hard_negative_count_at_{cutoff}"] = sum(
            rank is not None and rank <= cutoff
            for row in details
            for rank in row["hard_negative_ranks"].values()
        )
        metrics[f"delivered_hard_negative_count_at_{cutoff}"] = sum(
            len(row[f"delivered_hard_negative_ids_at_{cutoff}"]) for row in details
        )
        metrics[f"derivable_count_at_{cutoff}"] = sum(
            rank is not None and rank <= cutoff
            for row in details
            for rank in row["derivable_ranks"].values()
        )
        metrics[f"partial_count_at_{cutoff}"] = sum(
            rank is not None and rank <= cutoff
            for row in details
            for rank in row["partial_ranks"].values()
        )
    return metrics


def _expanded_context_ids(
    node: Mapping[str, Any], *, prose_nodes: Sequence[Mapping[str, Any]], radius: int
) -> list[str]:
    route_id = str(node.get("route_id") or "")
    if "transcript" not in route_id or node.get("page_start") is None:
        return [str(node["node_id"])]
    rows = [
        row
        for row in prose_nodes
        if row.get("route_id") == route_id
        and row.get("page_start") is not None
    ]
    rows.sort(
        key=lambda row: (
            int(row.get("page_start") or 0),
            int(row.get("section_chunk_index") or 0),
            str(row["node_id"]),
        )
    )
    anchor_id = str(node["node_id"])
    anchor_index = next(
        (index for index, row in enumerate(rows) if str(row["node_id"]) == anchor_id),
        None,
    )
    if anchor_index is None:
        return [anchor_id]
    start = max(0, anchor_index - radius)
    end = min(len(rows), anchor_index + radius + 1)
    return [str(row["node_id"]) for row in rows[start:end]]


def attach_delivery_context(
    *,
    route_results: Mapping[str, Mapping[str, Any]],
    node_index: Mapping[str, Mapping[str, Any]],
    prose_nodes: Sequence[Mapping[str, Any]],
    top_k: int,
    radius: int,
) -> None:
    for result in route_results.values():
        delivery: list[dict[str, Any]] = []
        for row in result["ranking"][:top_k]:
            node = node_index[str(row["node_id"])]
            delivery.append(
                {
                    "rank": row["rank"],
                    "node_id": row["node_id"],
                    "expanded_context_node_ids": _expanded_context_ids(
                        node, prose_nodes=prose_nodes, radius=radius
                    ),
                    "neighbor_expansion_changes_ranking": False,
                }
            )
        result["delivery"] = delivery


def render_human_review(
    *,
    queries: Sequence[Mapping[str, Any]],
    routes: Mapping[str, Mapping[str, Mapping[str, Any]]],
    node_index: Mapping[str, Mapping[str, Any]],
) -> str:
    lines = [
        "# Dell structured RAG qualification — human review sheet",
        "",
        "This is a candidate-retrieval review surface. Hits are not Evidence and table values are not NumericFacts.",
        "",
    ]
    for query in queries:
        lines.extend(
            [
                f"## {query['query_id']} — {query['question_zh']}",
                "",
                f"- Retrieval query: `{query['retrieval_query_en']}`",
                f"- Expected route: `{query['expected_route']}`; critical: `{str(query['critical']).lower()}`; gold requirement: `{query['gold_requirement']}`",
                f"- Answer-free retrieval scope: `{json.dumps(query.get('retrieval_scope') or {}, ensure_ascii=False, sort_keys=True)}`",
                f"- Labels: gold={len(query['gold_node_ids'])}; direct alternate={len(query.get('direct_alternate_node_ids') or query.get('acceptable_alternate_node_ids') or [])}; derivable={len(query.get('derivable_node_ids') or [])}; partial={len(query.get('partial_node_ids') or [])}; hard negative={len(query['hard_negative_node_ids'])}",
                "",
            ]
        )
        if query["expected_route"] == "external":
            lines.extend(
                [
                    "Local corpus intentionally has no gold node for this query. Results below are local-substitution diagnostics only and must not be treated as an answer.",
                    "",
                ]
            )
        acceptable = _acceptable_ids(query)
        gold = set(query["gold_node_ids"])
        direct = acceptable - gold
        derivable = set(query.get("derivable_node_ids") or [])
        partial = set(query.get("partial_node_ids") or [])
        negatives = set(query["hard_negative_node_ids"])
        for route_name, route_rows in routes.items():
            result = route_rows[str(query["query_id"])]
            lines.extend([f"### {route_name}", ""])
            for row in result["ranking"][:10]:
                node = node_index[str(row["node_id"])]
                mark = (
                    "LOCAL-SUBSTITUTION-DIAGNOSTIC"
                    if query["expected_route"] == "external"
                    else "GOLD"
                    if row["node_id"] in gold
                    else "DIRECT-ALT"
                    if row["node_id"] in direct
                    else "DERIVABLE-NOT-DIRECT"
                    if row["node_id"] in derivable
                    else "PARTIAL-NOT-DIRECT"
                    if row["node_id"] in partial
                    else "HARD-NEG"
                    if row["node_id"] in negatives
                    else "candidate"
                )
                excerpt = _visible_text(node["content"])[:360]
                lines.append(
                    f"- #{row['rank']} `{row['node_id']}` [{mark}; {node['lane']}; {node['route_id']}; {node.get('fiscal_period')}] — {excerpt}"
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _git_metadata() -> dict[str, Any]:
    def run(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        return completed.stdout.strip()

    try:
        status = [line for line in run("status", "--short").splitlines() if line]
        return {
            "branch": run("branch", "--show-current"),
            "head": run("rev-parse", "HEAD"),
            "tree": run("rev-parse", "HEAD^{tree}"),
            "dirty": bool(status),
            "status_lines": status,
        }
    except (OSError, subprocess.CalledProcessError):
        return {
            "branch": None,
            "head": None,
            "tree": None,
            "dirty": None,
            "status_lines": [],
        }


def _distribution_versions(names: Sequence[str]) -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def _module_origins(names: Sequence[str]) -> dict[str, str | None]:
    origins: dict[str, str | None] = {}
    for name in names:
        try:
            module = importlib.import_module(name)
        except ImportError:
            origins[name] = None
        else:
            value = getattr(module, "__file__", None)
            origins[name] = Path(value).resolve().as_posix() if value else None
    return origins


def _implementation_receipts() -> dict[str, dict[str, Any]]:
    paths = {
        "qualification_runner": Path(__file__).resolve(),
        "embedding_runtime": SRC_ROOT / "retrieval" / "embedding_runtime.py",
        "cross_encoder_runtime": SRC_ROOT / "retrieval" / "cross_encoder.py",
    }
    return {
        name: {
            "path": path.resolve().as_posix(),
            "sha256": sha256_file(path.resolve()),
            "bytes": path.stat().st_size,
        }
        for name, path in paths.items()
    }


def _validate_policy_contract(policy: Mapping[str, Any], *, qrels_path: Path) -> None:
    if policy.get("status") != "frozen_bounded_dell_reference_vertical_qualification_input":
        raise QualificationError("policy_status_invalid")
    qrel_contract = policy.get("qrels")
    if not isinstance(qrel_contract, Mapping):
        raise QualificationError("policy_qrels_contract_missing")
    if str(qrel_contract.get("sha256") or "").lower() != sha256_file(qrels_path):
        raise QualificationError("policy_qrels_digest_drift")
    candidate = policy.get("candidate_policy")
    if not isinstance(candidate, Mapping):
        raise QualificationError("candidate_policy_missing")
    for key, expected in (
        ("candidate_is_not_evidence", True),
        ("numeric_authority", False),
        ("citation_eligible", False),
    ):
        if candidate.get(key) is not expected:
            raise QualificationError(f"candidate_policy_authority_drift:{key}")
    authority = policy.get("authority")
    if not isinstance(authority, Mapping) or any(value is not False for value in authority.values()):
        raise QualificationError("policy_authority_must_be_all_false")
    evaluation = policy.get("evaluation")
    if not isinstance(evaluation, Mapping) or evaluation.get("manual_review_required") is not True:
        raise QualificationError("policy_manual_review_required")
    retrieval = policy.get("retrieval")
    if not isinstance(retrieval, Mapping):
        raise QualificationError("policy_retrieval_missing")
    required_budget_fields = {
        "node_purpose",
        "input_scale",
        "required_output",
        "schema_burden",
        "materiality_quality_risk",
        "comparable_run_evidence",
        "reasoning_profile",
        "stop_truncation_behavior",
    }
    for model_node in ("dense", "reranker"):
        node = retrieval.get(model_node)
        budget = node.get("token_budget_basis") if isinstance(node, Mapping) else None
        if not isinstance(budget, Mapping) or required_budget_fields - set(budget):
            raise QualificationError(f"token_budget_basis_incomplete:{model_node}")
    execution = policy.get("execution")
    overlay = execution.get("rank_bm25_runtime_overlay") if isinstance(execution, Mapping) else None
    if not isinstance(overlay, Mapping):
        raise QualificationError("rank_bm25_runtime_overlay_missing")
    overlay_path = Path(_require_string(overlay.get("path"), label="rank_bm25_overlay_path")).resolve()
    if not overlay_path.is_file() or sha256_file(overlay_path) != _require_sha(
        overlay.get("sha256"), label="rank_bm25_overlay_sha"
    ):
        raise QualificationError("rank_bm25_runtime_overlay_drift")


def _paths_overlap(left: Path, right: Path) -> bool:
    left = left.resolve()
    right = right.resolve()
    return left == right or left in right.parents or right in left.parents


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    policy_path = Path(args.policy).resolve()
    qrels_path = Path(args.qrels).resolve()
    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists():
        raise QualificationError(f"output_dir_already_exists:{output_dir}")
    if not policy_path.is_file() or not qrels_path.is_file():
        raise QualificationError("policy_or_qrels_missing")
    git_start = _git_metadata()
    implementation_start = _implementation_receipts()
    source_guard_start = {
        "policy_sha256": sha256_file(policy_path),
        "qrels_sha256": sha256_file(qrels_path),
        "implementation": implementation_start,
    }
    policy = _load_json(policy_path)
    if policy.get("schema_version") != POLICY_SCHEMA:
        raise QualificationError("policy_schema_mismatch")
    _validate_policy_contract(policy, qrels_path=qrels_path)
    corpus = load_frozen_corpus(policy)
    protected_paths = [REPO_ROOT, Path(corpus["root"])]
    for model_node in ("dense", "reranker"):
        protected_paths.append(
            Path(str(policy["retrieval"][model_node]["model_dir"])).resolve()
        )
    if any(_paths_overlap(output_dir, protected) for protected in protected_paths):
        raise QualificationError("output_dir_overlaps_protected_input")
    nodes = build_retrieval_nodes(corpus)
    node_index = {str(row["node_id"]): row for row in [*nodes["parents"], *nodes["leaves"]]}
    qrels = load_qrels(
        qrels_path,
        node_index=node_index,
        corpus_artifacts=corpus["artifacts"],
    )
    all_queries = qrels["queries"]
    local_queries = [query for query in qrels["queries"] if query["expected_route"] == "local"]
    external_queries = [query for query in qrels["queries"] if query["expected_route"] == "external"]
    qrel_contract = policy["qrels"]
    if (
        len(all_queries) != int(qrel_contract["query_count"])
        or len(local_queries) != int(qrel_contract["local_query_count"])
        or len(external_queries) != int(qrel_contract["external_diagnostic_query_count"])
    ):
        raise QualificationError("qrels_query_count_contract_drift")
    routes = [value.strip() for value in str(args.routes).split(",") if value.strip()]
    allowed_routes = {"bm25", "dense", "hybrid", "reranker"}
    if not routes or len(routes) != len(set(routes)) or set(routes) - allowed_routes:
        raise QualificationError("route_selection_invalid")
    if "hybrid" in routes and not {"bm25", "dense"}.issubset(routes):
        raise QualificationError("hybrid_requires_bm25_and_dense")
    if "reranker" in routes and "hybrid" not in routes:
        raise QualificationError("reranker_requires_hybrid")
    full_route_set = [str(value) for value in policy["execution"]["full_route_set"]]
    route_coverage_complete = routes == full_route_set
    formal_eligible = git_start.get("dirty") is False and route_coverage_complete
    attempt_mode = "bounded_qualification" if formal_eligible else "engineering_preview"
    terminal_status = (
        "QUALIFICATION_MEASURED_REVIEW_REQUIRED"
        if formal_eligible
        else "ENGINEERING_PREVIEW_MEASURED_REVIEW_REQUIRED"
    )

    output_dir.mkdir(parents=True, exist_ok=False)
    _write_jsonl_exclusive(output_dir / "retrieval_nodes.jsonl", [*nodes["parents"], *nodes["leaves"]])
    _write_jsonl_exclusive(output_dir / "image_catalog_excluded.jsonl", nodes["images"])

    route_outputs: dict[str, dict[str, dict[str, Any]]] = {}
    runtime_receipts: dict[str, Any] = {}
    if "bm25" in routes:
        route_outputs["bm25"] = run_bm25(
            nodes=nodes,
            queries=all_queries,
            policy=policy,
        )
    if "dense" in routes:
        dense_rows, dense_receipt = run_dense(
            nodes=nodes,
            queries=all_queries,
            policy=policy,
            cache_dir=output_dir / "qwen_embedding_artifact",
        )
        route_outputs["dense"] = dense_rows
        runtime_receipts["dense"] = dense_receipt
    if "hybrid" in routes:
        route_outputs["hybrid_rrf"] = run_hybrid(
            bm25=route_outputs["bm25"], dense=route_outputs["dense"], policy=policy
        )
    if "reranker" in routes:
        reranked, reranker_receipt = run_reranker(
            hybrid=route_outputs["hybrid_rrf"],
            queries=all_queries,
            node_index=node_index,
            policy=policy,
        )
        route_outputs["hybrid_qwen_reranker"] = reranked
        runtime_receipts["reranker"] = reranker_receipt

    delivery = policy["retrieval"]["delivery"]
    for rows in route_outputs.values():
        attach_delivery_context(
            route_results=rows,
            node_index=node_index,
            prose_nodes=nodes["prose"],
            top_k=int(delivery["top_k"]),
            radius=int(
                delivery.get(
                    "transcript_neighbor_chunk_radius",
                    delivery.get("transcript_neighbor_page_radius", 0),
                )
            ),
        )
    cutoffs = [int(value) for value in policy["evaluation"]["cutoffs"]]
    metrics = {
        name: evaluate_route(route_results=rows, queries=local_queries, cutoffs=cutoffs)
        for name, rows in route_outputs.items()
    }
    route_rows = [row for rows in route_outputs.values() for row in rows.values()]
    _write_jsonl_exclusive(output_dir / "route_results.jsonl", route_rows)
    _write_json_exclusive(output_dir / "metrics.json", metrics)
    _write_exclusive(
        output_dir / "human_review.md",
        render_human_review(
            queries=qrels["queries"], routes=route_outputs, node_index=node_index
        ).encode("utf-8"),
    )
    implementation_end = _implementation_receipts()
    git_end = _git_metadata()
    source_guard_end = {
        "policy_sha256": sha256_file(policy_path),
        "qrels_sha256": sha256_file(qrels_path),
        "implementation": implementation_end,
    }
    if source_guard_end != source_guard_start:
        raise QualificationError("source_changed_during_attempt")
    if git_end != git_start:
        raise QualificationError("git_state_changed_during_attempt")
    for artifact in corpus["artifacts"].values():
        if sha256_file(Path(str(artifact["path"]))) != str(artifact["sha256"]):
            raise QualificationError("corpus_changed_during_attempt")
    manifest = {
        "schema_version": "fin_ia_dell_structured_rag_qualification_manifest_v1_0",
        "attempt_id": output_dir.name,
        "status": terminal_status,
        "attempt_mode": attempt_mode,
        "formal_eligible": formal_eligible,
        "inputs": {
            "policy": {"path": policy_path.as_posix(), "sha256": sha256_file(policy_path)},
            "qrels": {"path": qrels_path.as_posix(), "sha256": sha256_file(qrels_path)},
            "corpus_attempt_id": corpus["attempt_id"],
            "corpus_artifacts": corpus["artifacts"],
        },
        "candidate_counts": {
            "parent": len(nodes["parents"]),
            "prose_leaf": len(nodes["prose"]),
            "mixed_prose_leaf": sum(
                row.get("node_kind") == "mixed_prose_span"
                for row in nodes["prose"]
            ),
            "table_leaf": len(nodes["tables"]),
            "image_catalog_excluded": len(nodes["images"]),
        },
        "candidate_coverage_receipt": nodes["coverage"],
        "query_counts": {
            "total": len(qrels["queries"]),
            "local": len(local_queries),
            "external": len(external_queries),
        },
        "routes": list(route_outputs),
        "requested_routes": routes,
        "full_route_set": full_route_set,
        "route_coverage_complete": route_coverage_complete,
        "runtime_receipts": runtime_receipts,
        "implementation": _implementation_receipts(),
        "execution_environment": {
            "python_executable": Path(sys.executable).resolve().as_posix(),
            "python_version": sys.version,
            "sys_path": [Path(value).resolve().as_posix() if value else "" for value in sys.path],
            "module_origins": _module_origins(
                ["rank_bm25", "numpy", "torch", "transformers", "sentence_transformers"]
            ),
            "parser_site_packages_overlay_used": False,
            "single_module_rank_bm25_overlay_allowed": True,
        },
        "packages": _distribution_versions(
            ["rank-bm25", "numpy", "torch", "transformers", "sentence-transformers"]
        ),
        "git": {"start": git_start, "end": git_end},
        "source_guard": {"start": source_guard_start, "end": source_guard_end},
        "authority": {
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
            "generation_model_calls": 0,
            "paid_calls": 0,
            "deepseek_calls": 0,
            "mcp_promotion_authorized": False,
            "retrieval_promotion_authorized": False,
            "manual_review_required": True,
            "qrel_label_contract_used_for_ranking": False,
            "gold_or_judgment_node_ids_used_for_ranking": False,
            "answer_free_retrieval_scope_used_for_ranking": any(
                any(query.get("retrieval_scope", {}).values())
                for query in local_queries
            ),
            "retrieval_scope_fields": [
                "issuer_ids",
                "fiscal_periods",
                "source_roles",
            ],
            "external_queries_ranked_locally_for_substitution_diagnostics": True,
            "external_queries_bypass_local_retrieval_scope": True,
        },
    }
    _write_json_exclusive(output_dir / "manifest.json", manifest)
    artifact_names = [
        "retrieval_nodes.jsonl",
        "image_catalog_excluded.jsonl",
        "route_results.jsonl",
        "metrics.json",
        "human_review.md",
        "manifest.json",
    ]
    for optional in (
        "qwen_embedding_artifact/dense.float16.npy",
        "qwen_embedding_artifact/manifest.json",
    ):
        if (output_dir / optional).is_file():
            artifact_names.append(optional)
    artifacts = {
        name: {
            "path": (output_dir / name).as_posix(),
            "sha256": sha256_file(output_dir / name),
            "bytes": (output_dir / name).stat().st_size,
        }
        for name in artifact_names
    }
    result = {
        "schema_version": RESULT_SCHEMA,
        "attempt_id": output_dir.name,
        "status": terminal_status,
        "attempt_mode": attempt_mode,
        "formal_eligible": formal_eligible,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "metrics": metrics,
        "artifacts": artifacts,
        "manual_review_complete": False,
        "retrieval_promotion_authorized": False,
        "mcp_promotion_authorized": False,
        "generation_model_calls": 0,
        "paid_calls": 0,
        "deepseek_calls": 0,
    }
    _write_json_exclusive(output_dir / "result.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--qrels", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--routes",
        default="bm25",
        help="Comma-separated ordered subset of bm25,dense,hybrid,reranker.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = run(args)
    except Exception as exc:
        output_dir = Path(args.output_dir).resolve()
        if output_dir.is_dir():
            failure_path = output_dir / "failure_receipt.json"
            if not failure_path.exists():
                _write_json_exclusive(
                    failure_path,
                    {
                        "schema_version": "fin_ia_dell_structured_rag_qualification_failure_v1_0",
                        "status": "FAILED_IMMUTABLE_ATTEMPT",
                        "attempt_id": output_dir.name,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "retrieval_promotion_authorized": False,
                        "mcp_promotion_authorized": False,
                    },
                )
        print(json.dumps({"status": "FAILED_IMMUTABLE_ATTEMPT", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(
        json.dumps(
            {
                "status": result["status"],
                "attempt_id": result["attempt_id"],
                "result_path": str((Path(args.output_dir).resolve() / "result.json")),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
