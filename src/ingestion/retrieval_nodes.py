"""Source-bound retrieval node projection used by the maintained public library builder.

FIN 0.1.3 projection extracted unchanged; evaluation, qrels and provider probes
remain in the historical archive. No source content gains evidence authority.
"""
from __future__ import annotations
import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence
NODE_SCHEMA = "fin_ia_dell_structured_rag_node_v1_0"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
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


def build_retrieval_nodes(corpus: Mapping[str, Any], *, require_tables: bool = True) -> dict[str, Any]:
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
    if not parents or not prose or (require_tables and not tables):
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
