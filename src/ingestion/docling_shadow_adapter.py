"""Fail-closed, non-authoritative projection of Docling JSON.

This qualification-only adapter preserves text, geometry, and lineage while
quarantining structural counterexamples. It never repairs financial data,
infers facts, grants Evidence authority, or calls Docling.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence


DOCLING_SHADOW_SCHEMA_VERSION = "fin_ia_docling_candidate_shadow_v1_0"
_HEX = re.compile(r"^[0-9a-fA-F]{64}$")
_DASH_PERCENT = re.compile(r"^[\-−–—]\s*%$")
_FOOTNOTE = re.compile(r"\(([a-z])\)", re.IGNORECASE)
_SOURCE_KEYS = {"expected_page_count", "source_filename", "source_pdf_bytes", "source_pdf_sha256"}
_PARSER_KEYS = {
    "docling_document_version", "docling_version", "model_package_digest",
    "qualification_attempt_id", "qualification_receipt_sha256", "runtime_manifest_digest",
}


class DoclingShadowAdapterError(ValueError):
    """The source cannot be projected without weakening lineage."""


def _fail(code: str) -> None:
    raise DoclingShadowAdapterError(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        _fail(code)


def _string(value: Any, code: str, *, nonempty: bool = False) -> str:
    _require(isinstance(value, str) and (not nonempty or bool(value.strip())), code)
    return value


def _integer(value: Any, code: str, *, minimum: int = 0) -> int:
    _require(not isinstance(value, bool) and isinstance(value, int) and value >= minimum, code)
    return value


def _number(value: Any, code: str) -> float | int:
    _require(not isinstance(value, bool) and isinstance(value, (int, float)), code)
    _require(not isinstance(value, float) or math.isfinite(value), code)
    return value


def _sha(value: Any, code: str) -> str:
    _require(isinstance(value, str) and bool(_HEX.fullmatch(value)), code)
    return value.lower()


def _strict_json(payload: bytes) -> Any:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DoclingShadowAdapterError("docling_document_utf8_invalid") from exc

    def constant(value: str) -> None:
        _fail(f"docling_document_json_nonfinite_number:{value}")

    def pairs(items: Sequence[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                _fail(f"docling_document_duplicate_key:{key}")
            result[key] = value
        return result

    try:
        value = json.loads(text, parse_constant=constant, object_pairs_hook=pairs)
    except DoclingShadowAdapterError:
        raise
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise DoclingShadowAdapterError("docling_document_json_invalid") from exc

    def finite(item: Any) -> None:
        if isinstance(item, float) and not math.isfinite(item):
            _fail("docling_document_nonfinite_number")
        children = item.values() if isinstance(item, dict) else item if isinstance(item, list) else ()
        for child in children:
            finite(child)

    finite(value)
    return value


def _copy(value: Mapping[str, Any], code: str) -> dict[str, Any]:
    _require(isinstance(value, Mapping), code)
    try:
        copied = json.loads(json.dumps(
            dict(value), ensure_ascii=False, allow_nan=False,
            separators=(",", ":"), sort_keys=True,
        ))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DoclingShadowAdapterError(code) from exc
    _require(isinstance(copied, dict), code)
    return copied


def _bindings(source: Mapping[str, Any], parser: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    source = _copy(source, "source_binding_invalid")
    parser = _copy(parser, "parser_binding_invalid")
    _require(set(source) == _SOURCE_KEYS, "source_binding_keys_invalid")
    _sha(source["source_pdf_sha256"], "source_binding_pdf_sha256_invalid")
    _integer(source["source_pdf_bytes"], "source_binding_pdf_bytes_invalid", minimum=1)
    _integer(source["expected_page_count"], "source_binding_page_count_invalid", minimum=1)
    _string(source["source_filename"], "source_binding_filename_invalid", nonempty=True)
    _require(set(parser) == _PARSER_KEYS, "parser_binding_keys_invalid")
    errors = {
        "docling_version": "parser_binding_docling_version_invalid",
        "docling_document_version": "parser_binding_document_version_invalid",
        "qualification_attempt_id": "parser_binding_attempt_id_invalid",
    }
    for key, code in errors.items():
        _string(parser[key], code, nonempty=True)
    for key in ("qualification_receipt_sha256", "runtime_manifest_digest", "model_package_digest"):
        _sha(parser[key], f"parser_binding_{key}_invalid")
    return source, parser


def _pages(document: Mapping[str, Any], source: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    raw = document.get("pages")
    _require(isinstance(raw, dict) and bool(raw), "docling_pages_invalid")
    pages: dict[int, dict[str, Any]] = {}
    for key, page in raw.items():
        _require(isinstance(key, str) and key.isdigit() and isinstance(page, dict), "docling_page_record_invalid")
        number = _integer(page.get("page_no"), "docling_page_number_invalid", minimum=1)
        _require(str(number) == key and number not in pages, "docling_page_number_mismatch")
        size = page.get("size")
        _require(isinstance(size, dict), "docling_page_size_invalid")
        width, height = (_number(size.get(axis), "docling_page_size_invalid") for axis in ("width", "height"))
        _require(width > 0 and height > 0, "docling_page_size_invalid")
        pages[number] = page
    expected = source["expected_page_count"]
    _require(len(pages) == expected and set(pages) == set(range(1, expected + 1)), "docling_page_inventory_mismatch")
    return pages


def _index(document: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    refs: dict[str, dict[str, Any]] = {}
    kinds: dict[str, str] = {}
    for kind in ("texts", "tables", "pictures", "groups"):
        items = document.get(kind)
        _require(isinstance(items, list), f"docling_collection_invalid:{kind}")
        for index, item in enumerate(items):
            _require(isinstance(item, dict), f"docling_collection_item_invalid:{kind}:{index}")
            ref = f"#/{kind}/{index}"
            _require(item.get("self_ref") == ref and ref not in refs, f"docling_self_ref_invalid:{ref}")
            refs[ref], kinds[ref] = item, kind
    for kind in ("form_items", "key_value_items"):
        items = document.get(kind)
        _require(isinstance(items, list), f"docling_collection_invalid:{kind}")
        _require(not items, f"docling_collection_not_supported:{kind}")
    return refs, kinds


def _ref(value: Any, code: str) -> str:
    _require(isinstance(value, dict) and set(value) == {"$ref"}, code)
    return _string(value["$ref"], code, nonempty=True)


def _root(value: Any, expected: str) -> dict[str, Any]:
    _require(isinstance(value, dict) and value.get("self_ref") == expected, f"docling_root_invalid:{expected}")
    _require(isinstance(value.get("children"), list), f"docling_root_children_invalid:{expected}")
    return value


def _leaf_order(document: Mapping[str, Any], refs: Mapping[str, Mapping[str, Any]]) -> list[str]:
    body = _root(document.get("body"), "#/body")
    furniture = _root(document.get("furniture"), "#/furniture")
    _require(not furniture["children"], "docling_furniture_content_not_supported")
    order: list[str] = []
    visited: set[str] = set()
    active: set[str] = set()

    def walk(children: Sequence[Any], parent: str) -> None:
        for child in children:
            child_ref = _ref(child, "docling_child_ref_invalid")
            _require(child_ref in refs, f"docling_child_ref_unknown:{child_ref}")
            actual_parent = _ref(refs[child_ref].get("parent"), "docling_parent_ref_invalid")
            _require(actual_parent == parent, "docling_parent_ref_mismatch")
            if child_ref.startswith("#/groups/"):
                _require(child_ref not in active, "docling_group_cycle")
                _require(child_ref not in visited, "docling_group_duplicate")
                children = refs[child_ref].get("children")
                _require(isinstance(children, list), "docling_group_children_invalid")
                visited.add(child_ref)
                active.add(child_ref)
                walk(children, child_ref)
                active.remove(child_ref)
            else:
                _require(child_ref not in order, "docling_leaf_ref_duplicate")
                order.append(child_ref)

    walk(body["children"], "#/body")
    groups = {ref for ref in refs if ref.startswith("#/groups/")}
    _require(visited == groups, "docling_group_inventory_mismatch")
    _require(set(order) == set(refs) - groups, "docling_leaf_inventory_mismatch")
    return order


def _bbox(value: Any, code: str, size: Mapping[str, Any] | None) -> dict[str, Any]:
    _require(isinstance(value, dict), code)
    box = {key: _number(value.get(key), code) for key in ("l", "t", "r", "b")}
    box["coord_origin"] = _string(value.get("coord_origin"), code, nonempty=True)
    _require(box["coord_origin"] in {"TOPLEFT", "BOTTOMLEFT"} and box["r"] >= box["l"], code)
    vertical = box["b"] >= box["t"] if box["coord_origin"] == "TOPLEFT" else box["t"] >= box["b"]
    _require(vertical, code)
    if size is not None:
        width, height = (_number(size.get(axis), code) for axis in ("width", "height"))
        tolerance = 1e-6
        _require(
            box["l"] >= -tolerance and box["r"] <= width + tolerance
            and all(-tolerance <= box[key] <= height + tolerance for key in ("t", "b")), code,
        )
    return box


def _provenance(value: Any, self_ref: str, pages: Mapping[int, Mapping[str, Any]], text: str | None) -> list[dict[str, Any]]:
    _require(isinstance(value, list) and bool(value), f"docling_provenance_missing:{self_ref}")
    result: list[dict[str, Any]] = []
    previous_start = previous_end = -1
    for index, entry in enumerate(value):
        _require(isinstance(entry, dict), f"docling_provenance_invalid:{self_ref}:{index}")
        page = _integer(entry.get("page_no"), f"docling_provenance_page_invalid:{self_ref}:{index}", minimum=1)
        _require(page in pages, f"docling_provenance_page_unknown:{self_ref}:{index}")
        code = f"docling_provenance_charspan_invalid:{self_ref}:{index}"
        span = entry.get("charspan")
        _require(isinstance(span, list) and len(span) == 2, code)
        start, end = (_integer(part, code) for part in span)
        _require(end >= start, code)
        if text is not None:
            _require(end <= len(text), f"docling_provenance_charspan_out_of_range:{self_ref}:{index}")
            _require(start >= previous_start and start >= previous_end, f"docling_provenance_charspan_overlap:{self_ref}:{index}")
            previous_start, previous_end = start, end
        result.append({
            "page_no": page,
            "bbox": _bbox(entry.get("bbox"), f"docling_provenance_bbox_invalid:{self_ref}:{index}", pages[page]["size"]),
            "charspan": [start, end],
        })
    if text is not None:
        end = 0
        for entry in result:
            start, next_end = entry["charspan"]
            _require(not text[end:start].strip(), f"docling_provenance_charspan_nonwhitespace_gap:{self_ref}")
            end = next_end
        _require(not text[end:].strip(), f"docling_provenance_charspan_nonwhitespace_gap:{self_ref}")
    return result


def _stable(*parts: str) -> str:
    return "sha256:" + hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def _cell_ref(table_ref: str, index: int) -> str:
    return f"{table_ref}/data/table_cells/{index}"


def _finding(code: str, self_ref: str, digest: str, location: Mapping[str, Any], observed: str | None = None) -> dict[str, Any]:
    location = _copy(location, "finding_location_invalid")
    identity = json.dumps(location, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)
    result = {
        "finding_id": _stable("finding", digest, self_ref, code, identity),
        "code": code, "severity": "blocker", "upstream_self_ref": self_ref,
        "location": location, "disposition": "quarantine_without_repair",
    }
    if observed is not None:
        result["observed_text"] = observed
    return result


def _text(item: Mapping[str, Any], digest: str, prov: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    ref, text = str(item["self_ref"]), str(item["text"])
    candidates = []
    for index, entry in enumerate(prov):
        start, end = entry["charspan"]
        candidates.append({
            "element_id": _stable("text_fragment", digest, ref, str(index)),
            "kind": "text_fragment", "upstream_self_ref": ref, "provenance_index": index,
            "page_no": entry["page_no"], "bbox": entry["bbox"], "charspan": [start, end],
            "text": text[start:end],
            "source_payload": {"text": text, "orig": item.get("orig"), "label": item.get("label")},
        })
    page_numbers = sorted({entry["page_no"] for entry in prov})
    if len(page_numbers) <= 1:
        return candidates, [], [], []
    code = "cross_page_text_semantics_unresolved"
    quarantined = [{
        "element_id": _stable("text_source", digest, ref), "kind": "cross_page_text_source",
        "upstream_self_ref": ref, "page_numbers": page_numbers, "blocker_codes": [code],
        "source_payload": item,
    }]
    findings = [_finding(code, ref, digest, {"page_numbers": page_numbers}, text)]
    unresolved = [{
        "relationship_id": _stable("relationship", digest, ref, code),
        "type": "cross_page_text_fragmentation", "status": "unresolved", "source_ref": ref,
        "page_numbers": page_numbers,
        "fragment_element_ids": [_stable("text_fragment", digest, ref, str(i)) for i in range(len(prov))],
        "automatic_link_created": False,
    }]
    return candidates, quarantined, findings, unresolved


def _cell(value: Any, table_ref: str, index: int, rows: int, cols: int, size: Mapping[str, Any] | None) -> dict[str, Any]:
    code = f"docling_table_cell_invalid:{table_ref}:{index}"
    _require(isinstance(value, dict), code)
    sr = _integer(value.get("start_row_offset_idx"), code)
    er = _integer(value.get("end_row_offset_idx"), code, minimum=1)
    sc = _integer(value.get("start_col_offset_idx"), code)
    ec = _integer(value.get("end_col_offset_idx"), code, minimum=1)
    row_span = _integer(value.get("row_span"), code, minimum=1)
    col_span = _integer(value.get("col_span"), code, minimum=1)
    _require(er > sr and ec > sc and er <= rows and ec <= cols and row_span == er - sr and col_span == ec - sc, code)
    header = value.get("column_header")
    _require(isinstance(header, bool), code)
    return {
        "cell_ref": _cell_ref(table_ref, index), "start_row": sr, "end_row": er,
        "start_col": sc, "end_col": ec, "text": _string(value.get("text"), code),
        "column_header": header, "bbox": _bbox(value.get("bbox"), code, size),
    }


def _table(item: Mapping[str, Any], digest: str, prov: Sequence[Mapping[str, Any]], pages: Mapping[int, Mapping[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    ref, data = str(item["self_ref"]), item.get("data")
    _require(isinstance(data, dict), f"docling_table_data_invalid:{ref}")
    rows = _integer(data.get("num_rows"), f"docling_table_rows_invalid:{ref}", minimum=1)
    cols = _integer(data.get("num_cols"), f"docling_table_cols_invalid:{ref}", minimum=1)
    raw_cells = data.get("table_cells")
    _require(isinstance(raw_cells, list), f"docling_table_cells_invalid:{ref}")
    page_numbers = sorted({entry["page_no"] for entry in prov})
    size = pages[page_numbers[0]]["size"] if len(page_numbers) == 1 else None
    cells, lineage, occupied = [], [], {}
    seen: set[tuple[int, int, int, int]] = set()
    for index, raw in enumerate(raw_cells):
        cell = _cell(raw, ref, index, rows, cols, size)
        bounds = cell["start_row"], cell["end_row"], cell["start_col"], cell["end_col"]
        _require(bounds not in seen, f"docling_table_cell_duplicate:{ref}:{index}")
        seen.add(bounds)
        for row in range(cell["start_row"], cell["end_row"]):
            for col in range(cell["start_col"], cell["end_col"]):
                coordinate = row, col
                if coordinate in occupied:
                    _fail(f"docling_table_cell_overlap:{ref}:{occupied[coordinate]}:{index}")
                occupied[coordinate] = index
        cells.append(cell)
        lineage.append({
            "cell_id": _stable("table_cell", digest, ref, str(index), str(cell["start_row"]), str(cell["start_col"])),
            "cell_ref": cell["cell_ref"], "source_cell_index": index,
            "start_row_offset_idx": cell["start_row"], "end_row_offset_idx": cell["end_row"],
            "start_col_offset_idx": cell["start_col"], "end_col_offset_idx": cell["end_col"],
            "text": cell["text"], "bbox": cell["bbox"],
        })
    findings, unresolved = [], []
    if len(page_numbers) > 1:
        findings.append(_finding("cross_page_table_provenance_unresolved", ref, digest, {"page_numbers": page_numbers}))
    for row in range(rows):
        row_cells = [cell for cell in cells if cell["start_row"] <= row < cell["end_row"]]
        nonempty = [cell for cell in row_cells if cell["text"].strip()]
        if any(cell["column_header"] for cell in nonempty):
            continue
        label = any(cell["text"].strip() for cell in row_cells if cell["start_col"] <= 0 < cell["end_col"])
        numeric = [cell for cell in nonempty if cell["start_col"] > 0 and any(ch.isdigit() for ch in cell["text"])]
        if not label and numeric:
            findings.append(_finding("unlabeled_numeric_row", ref, digest, {
                "row_index": row, "cell_refs": [cell["cell_ref"] for cell in numeric],
            }, " | ".join(cell["text"] for cell in numeric)))
    relations = {}
    for name in ("footnotes", "references", "captions"):
        value = item.get(name)
        _require(isinstance(value, list), f"docling_table_{name}_invalid:{ref}")
        relations[name] = value
    if any(relations.values()):
        findings.append(_finding("upstream_relation_projection_not_supported", ref, digest, {
            "caption_count": len(relations["captions"]), "footnote_count": len(relations["footnotes"]),
            "reference_count": len(relations["references"]),
        }))
    for cell in cells:
        text = cell["text"]
        location = {"row_index": cell["start_row"], "column_index": cell["start_col"], "cell_ref": cell["cell_ref"]}
        if cell["start_col"] > 0 and not cell["column_header"] and sum(text.count(mark) for mark in "$€£¥") > 1:
            findings.append(_finding("repeated_currency_marker", ref, digest, location, text))
        if not cell["column_header"] and _DASH_PERCENT.fullmatch(text.strip()):
            findings.append(_finding("ambiguous_dash_percent", ref, digest, location, text))
        if not relations["footnotes"] and not relations["references"]:
            for match in _FOOTNOTE.finditer(text):
                marker = match.group(0)
                findings.append(_finding("footnote_relation_unresolved", ref, digest, {**location, "marker": marker}, text))
                unresolved.append({
                    "relationship_id": _stable("relationship", digest, ref, cell["cell_ref"], marker.lower()),
                    "type": "footnote_relation", "status": "unresolved", "source_ref": ref,
                    "source_cell_ref": cell["cell_ref"], "marker": marker,
                    "candidate_target_refs": [], "automatic_link_created": False,
                })
    element = {
        "element_id": _stable("table", digest, ref), "kind": "table", "upstream_self_ref": ref,
        "page_numbers": page_numbers, "blocker_codes": sorted({row["code"] for row in findings}),
        "linked_footnotes": [], "cell_lineage": lineage, "source_payload": item,
    }
    return element, findings, unresolved


def _picture(item: Mapping[str, Any], digest: str, prov: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    ref = str(item["self_ref"])
    pages = sorted({entry["page_no"] for entry in prov})
    if len(pages) == 1:
        return [{
            "element_id": _stable("picture", digest, ref), "kind": "picture_locator",
            "upstream_self_ref": ref, "page_no": pages[0], "provenance": list(prov),
            "source_payload": item,
        }], [], []
    code = "cross_page_picture_provenance_unresolved"
    return [], [{
        "element_id": _stable("picture", digest, ref), "kind": "picture",
        "upstream_self_ref": ref, "page_numbers": pages, "blocker_codes": [code],
        "source_payload": item,
    }], [_finding(code, ref, digest, {"page_numbers": pages})]


def _adjacency(order: Sequence[str], provenance: Mapping[str, Sequence[Mapping[str, Any]]], kinds: Mapping[str, str], digest: str) -> list[dict[str, Any]]:
    result = []
    for left, right in zip(order, order[1:]):
        left_pages = sorted({entry["page_no"] for entry in provenance[left]})
        right_pages = sorted({entry["page_no"] for entry in provenance[right]})
        if left_pages[-1] == right_pages[0]:
            continue
        result.append({
            "relationship_id": _stable("adjacency", digest, left, right),
            "type": "cross_page_adjacency", "status": "unresolved",
            "left_ref": left, "left_kind": kinds[left], "left_page_numbers": left_pages,
            "right_ref": right, "right_kind": kinds[right], "right_page_numbers": right_pages,
            "automatic_link_created": False,
        })
    return result


def _digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def compile_docling_shadow(
    document_json: bytes, *, expected_document_sha256: str,
    source_binding: Mapping[str, Any], parser_binding: Mapping[str, Any],
) -> dict[str, Any]:
    """Project exact Docling bytes into deterministic candidates/quarantine."""
    _require(isinstance(document_json, bytes) and bool(document_json), "docling_document_bytes_invalid")
    expected = _sha(expected_document_sha256, "docling_expected_document_sha256_invalid")
    document_digest = hashlib.sha256(document_json).hexdigest()
    _require(document_digest == expected, "docling_document_sha256_mismatch")
    document = _strict_json(document_json)
    _require(isinstance(document, dict), "docling_document_root_invalid")
    source, parser = _bindings(source_binding, parser_binding)
    _require(document.get("schema_name") == "DoclingDocument", "docling_document_schema_unsupported")
    _require(document.get("version") == "1.10.0", "docling_document_version_unsupported")
    _require(parser["docling_document_version"] == document["version"], "parser_binding_document_version_mismatch")
    _string(document.get("name"), "docling_document_name_invalid", nonempty=True)
    origin = document.get("origin")
    _require(isinstance(origin, dict), "docling_document_origin_invalid")
    filename = _string(origin.get("filename"), "docling_document_origin_invalid", nonempty=True)
    _require(filename == source["source_filename"], "docling_document_origin_filename_mismatch")
    _require(origin.get("mimetype") == "application/pdf", "docling_document_origin_mimetype_invalid")
    pages = _pages(document, source)
    refs, kinds = _index(document)
    order = _leaf_order(document, refs)
    provenance = {
        ref: _provenance(item.get("prov"), ref, pages, _string(item.get("text"), "docling_text_value_invalid") if kinds[ref] == "texts" else None)
        for ref, item in refs.items() if kinds[ref] != "groups"
    }
    candidates: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    table_count = candidate_tables = quarantined_tables = 0
    for ref in order:
        kind, item, prov = kinds[ref], refs[ref], provenance[ref]
        if kind == "texts":
            added = _text(item, document_digest, prov)
            candidates.extend(added[0]); quarantined.extend(added[1])
            findings.extend(added[2]); unresolved.extend(added[3])
        elif kind == "tables":
            table_count += 1
            element, table_findings, table_unresolved = _table(item, document_digest, prov, pages)
            findings.extend(table_findings); unresolved.extend(table_unresolved)
            if element["blocker_codes"]:
                quarantined.append(element); quarantined_tables += 1
            else:
                candidates.append(element); candidate_tables += 1
        elif kind == "pictures":
            added = _picture(item, document_digest, prov)
            candidates.extend(added[0]); quarantined.extend(added[1]); findings.extend(added[2])
        else:
            _fail("docling_leaf_collection_invalid")
    unresolved.extend(_adjacency(order, provenance, kinds, document_digest))
    candidate_ids = [row["element_id"] for row in candidates]
    quarantine_ids = [row["element_id"] for row in quarantined]
    _require(len(set(candidate_ids)) == len(candidate_ids) and len(set(quarantine_ids)) == len(quarantine_ids), "docling_shadow_element_id_duplicate")
    _require(not set(candidate_ids) & set(quarantine_ids), "docling_shadow_candidate_quarantine_overlap")
    _require(not any(row.get("kind") == "table" and row.get("blocker_codes") for row in candidates), "docling_shadow_blocked_table_candidate")
    _require(all(row.get("status") == "unresolved" for row in unresolved), "docling_shadow_relationship_authority_invalid")
    candidate_counts = Counter(str(row["kind"]) for row in candidates)
    quarantine_counts = Counter(str(row["kind"]) for row in quarantined)
    output: dict[str, Any] = {
        "schema_version": DOCLING_SHADOW_SCHEMA_VERSION,
        "status": "shadow_blocked_findings_present" if findings or quarantined else "shadow_candidates_ready",
        "source_binding": source, "parser_binding": parser,
        "source_document": {
            "document_json_sha256": document_digest, "schema_name": document["schema_name"],
            "docling_document_version": document["version"], "name": document["name"],
            "origin": document["origin"], "page_count": len(pages),
        },
        "authority": {
            "raw_direct_consumption_allowed": False,
            "financial_semantic_association_proven": False,
            "candidate_is_evidence": False, "numeric_fact_authority": False,
            "evidence_authority": False, "automatic_relationships_allowed": False,
            "repair_performed": False, "adoption_allowed": False,
        },
        "candidate_elements": candidates, "quarantined_elements": quarantined,
        "unresolved_relationships": unresolved, "findings": findings,
        "summary": {
            "source_leaf_count": len(order), "candidate_element_count": len(candidates),
            "quarantined_element_count": len(quarantined), "finding_count": len(findings),
            "unresolved_relationship_count": len(unresolved),
            "candidate_kind_counts": dict(sorted(candidate_counts.items())),
            "quarantine_kind_counts": dict(sorted(quarantine_counts.items())),
            "table_count": table_count, "candidate_table_count": candidate_tables,
            "quarantined_table_count": quarantined_tables,
        },
    }
    output["result_digest"] = _digest(output)
    return output


__all__ = ["DOCLING_SHADOW_SCHEMA_VERSION", "DoclingShadowAdapterError", "compile_docling_shadow"]
