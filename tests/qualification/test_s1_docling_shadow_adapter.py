from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

import pytest

from ingestion.docling_shadow_adapter import (
    DoclingShadowAdapterError,
    compile_docling_shadow,
)


SOURCE_BINDING = {
    "expected_page_count": 2,
    "source_filename": "dell_fy26_results.pdf",
    "source_pdf_bytes": 683251,
    "source_pdf_sha256": "a" * 64,
}
PARSER_BINDING = {
    "docling_document_version": "1.10.0",
    "docling_version": "2.124.0",
    "model_package_digest": "b" * 64,
    "qualification_attempt_id": "20260901T050341Z-run2-strict",
    "qualification_receipt_sha256": "c" * 64,
    "runtime_manifest_digest": "d" * 64,
}


def _bbox(origin: str = "BOTTOMLEFT") -> dict[str, Any]:
    return {
        "b": 20.0 if origin == "TOPLEFT" else 10.0,
        "coord_origin": origin,
        "l": 10.0,
        "r": 100.0,
        "t": 10.0 if origin == "TOPLEFT" else 20.0,
    }


def _prov(
    page: int = 1,
    span: tuple[int, int] = (0, 0),
    origin: str = "BOTTOMLEFT",
) -> dict[str, Any]:
    return {"bbox": _bbox(origin), "charspan": list(span), "page_no": page}


def _text(
    value: str = "Dell result",
    prov: list[dict[str, Any]] | None = None,
    *,
    orig: str | None = None,
    self_ref: str = "#/texts/0",
    parent: str = "#/body",
    children: list[dict[str, str]] | None = None,
    content_layer: str = "body",
    label: str = "text",
) -> dict[str, Any]:
    raw = value if orig is None else orig
    return {
        "children": children or [],
        "content_layer": content_layer,
        "label": label,
        "orig": raw,
        "parent": {"$ref": parent},
        "prov": prov or [_prov(span=(0, len(raw)))],
        "self_ref": self_ref,
        "text": value,
    }


def _cell(
    row: int,
    col: int,
    value: str,
    *,
    header: bool = False,
    end_row: int | None = None,
    end_col: int | None = None,
) -> dict[str, Any]:
    end_row = row + 1 if end_row is None else end_row
    end_col = col + 1 if end_col is None else end_col
    return {
        "bbox": _bbox("TOPLEFT"),
        "col_span": end_col - col,
        "column_header": header,
        "end_col_offset_idx": end_col,
        "end_row_offset_idx": end_row,
        "row_span": end_row - row,
        "start_col_offset_idx": col,
        "start_row_offset_idx": row,
        "text": value,
    }


def _table(
    rows: list[list[str]],
    *,
    prov: list[dict[str, Any]] | None = None,
    header_rows: set[int] | None = None,
    self_ref: str = "#/tables/0",
    parent: str = "#/body",
    children: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    headers = header_rows or set()
    cells = [
        _cell(row, col, value, header=row in headers)
        for row, values in enumerate(rows)
        for col, value in enumerate(values)
    ]
    return {
        "captions": [],
        "children": children or [],
        "content_layer": "body",
        "data": {
            "grid": [],
            "num_cols": max(map(len, rows)),
            "num_rows": len(rows),
            "orientation": "horizontal",
            "table_cells": cells,
        },
        "footnotes": [],
        "label": "table",
        "parent": {"$ref": parent},
        "prov": prov or [_prov()],
        "references": [],
        "self_ref": self_ref,
    }


def _picture(
    index: int,
    *,
    parent: str = "#/body",
    children: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "annotations": [],
        "captions": [],
        "children": children or [],
        "content_layer": "body",
        "footnotes": [],
        "label": "picture",
        "parent": {"$ref": parent},
        "prov": [_prov()],
        "references": [],
        "self_ref": f"#/pictures/{index}",
    }


def _group(
    index: int,
    *,
    parent: str = "#/body",
    children: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "children": children or [],
        "content_layer": "body",
        "label": "group",
        "name": "group",
        "parent": {"$ref": parent},
        "self_ref": f"#/groups/{index}",
    }


def _document(
    *,
    text: dict[str, Any] | None = None,
    table: dict[str, Any] | None = None,
    texts: list[dict[str, Any]] | None = None,
    tables: list[dict[str, Any]] | None = None,
    pictures: list[dict[str, Any]] | None = None,
    groups: list[dict[str, Any]] | None = None,
    body_children: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    text_items = list(texts) if texts is not None else [text or _text()]
    table_items = list(tables) if tables is not None else ([] if table is None else [table])
    picture_items = list(pictures or [])
    group_items = list(groups or [])
    items = [*text_items, *table_items, *picture_items, *group_items]
    children = body_children if body_children is not None else [
        {"$ref": item["self_ref"]}
        for item in items
        if item.get("parent") == {"$ref": "#/body"}
    ]
    return {
        "body": {
            "children": children,
            "label": "unspecified",
            "parent": None,
            "self_ref": "#/body",
        },
        "form_items": [],
        "furniture": {
            "children": [],
            "label": "unspecified",
            "parent": None,
            "self_ref": "#/furniture",
        },
        "groups": group_items,
        "key_value_items": [],
        "name": "dell_fy26_results",
        "origin": {
            "binary_hash": 7421240698696950521,
            "filename": "dell_fy26_results.pdf",
            "mimetype": "application/pdf",
        },
        "pages": {
            str(page): {
                "page_no": page,
                "size": {"height": 792.0, "width": 612.0},
            }
            for page in (1, 2)
        },
        "pictures": picture_items,
        "schema_name": "DoclingDocument",
        "tables": table_items,
        "texts": text_items,
        "version": "1.10.0",
    }


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _call(
    payload: bytes,
    *,
    expected: str | None = None,
    source: dict[str, Any] | None = None,
    parser: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return compile_docling_shadow(
        payload,
        expected_document_sha256=expected or hashlib.sha256(payload).hexdigest(),
        source_binding=source or dict(SOURCE_BINDING),
        parser_binding=parser or dict(PARSER_BINDING),
    )


def _compile(document: dict[str, Any]) -> dict[str, Any]:
    return _call(_canonical(document))


def _codes(result: dict[str, Any]) -> set[str]:
    return {item["code"] for item in result["findings"]}


def _table_element(result: dict[str, Any], collection: str) -> dict[str, Any]:
    return next(
        item
        for item in result[collection]
        if item["upstream_self_ref"] == "#/tables/0"
    )


def _has_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_has_key(item, key) for item in value.values())
    return isinstance(value, list) and any(_has_key(item, key) for item in value)


def test_safe_projection_is_deterministic_and_authority_is_fail_closed() -> None:
    document = _document()
    first, second = _compile(document), _compile(deepcopy(document))
    candidate = first["candidate_elements"][0]

    assert first == second
    assert first["schema_version"] == "fin_ia_docling_candidate_shadow_v1_1"
    assert len(first["result_digest"]) == 64
    assert first["status"] != "ADOPTED"
    assert (candidate["kind"], candidate["upstream_self_ref"], candidate["text"]) == (
        "text_fragment", "#/texts/0", "Dell result"
    )
    assert first["quarantined_elements"] == []
    assert first["unresolved_relationships"] == []
    assert set(first["authority"]) == {
        "adoption_allowed", "automatic_relationships_allowed",
        "candidate_is_evidence", "evidence_authority",
        "financial_semantic_association_proven", "numeric_fact_authority",
        "raw_direct_consumption_allowed", "repair_performed",
    }
    assert not any(first["authority"].values())
    assert not _has_key(first, "numeric_value")
    assert candidate["upstream_parent_ref"] == "#/body"
    assert candidate["content_layer"] == "body"
    assert candidate["charspan_basis"] == "orig"
    assert candidate["normalized_text"] == "Dell result"


def test_text_provenance_slices_orig_and_preserves_normalized_list_text() -> None:
    raw = "- Revenue increased by 16%."
    normalized = "Revenue increased by 16%."
    result = _compile(_document(text=_text(normalized, orig=raw, label="list_item")))
    candidate = result["candidate_elements"][0]

    assert candidate["text"] == raw
    assert candidate["normalized_text"] == normalized
    assert candidate["charspan"] == [0, len(raw)]
    assert candidate["charspan_basis"] == "orig"
    assert candidate["source_payload"] == {
        "label": "list_item",
        "orig": raw,
        "text": normalized,
    }


def test_quoted_nan_text_is_preserved_but_never_gains_authority() -> None:
    result = _compile(_document(text=_text("NaN")))
    assert result["candidate_elements"][0]["text"] == "NaN"
    assert not any(result["authority"].values())


@pytest.mark.parametrize(
    ("header", "row", "code", "raw"),
    [
        (["Metric", "FY26", "FY25"], ["", "723", "785"],
         "unlabeled_numeric_row", "723"),
        (["Metric", "FY26"], ["Operating income", "$ 3,092 $"],
         "repeated_currency_marker", "$ 3,092 $"),
        (["Metric", "FY26"], ["Corporate and other (a)", "77"],
         "footnote_relation_unresolved", "Corporate and other (a)"),
        (["Metric", "Change"], ["Margin", "-%"],
         "ambiguous_dash_percent", "-%"),
    ],
)
def test_financial_counterexample_quarantines_without_repair(
    header: list[str], row: list[str], code: str, raw: str
) -> None:
    result = _compile(_document(table=_table([header, row], header_rows={0})))
    blocked = _table_element(result, "quarantined_elements")

    assert code in _codes(result) and code in blocked["blocker_codes"]
    cells = blocked["source_payload"]["data"]["table_cells"]
    assert any(cell["text"] == raw for cell in cells)
    assert not any(e["upstream_self_ref"] == "#/tables/0" for e in result["candidate_elements"])
    assert not result["authority"]["repair_performed"]
    assert not result["authority"]["automatic_relationships_allowed"]
    assert not _has_key(blocked, "numeric_value")
    assert blocked["linked_footnotes"] == []
    if code == "footnote_relation_unresolved":
        relation = next(
            item
            for item in result["unresolved_relationships"]
            if item["type"] == "footnote_relation"
        )
        assert relation["status"] == "unresolved"
        assert relation["candidate_target_refs"] == []


def test_duplicate_finding_ids_fail_closed_without_redefining_footnotes() -> None:
    table = _table(
        [["Role", "Count"], ["Director(s) or employee(s)", "3"]],
        header_rows={0},
    )

    with pytest.raises(DoclingShadowAdapterError, match="finding_id_duplicate"):
        _compile(_document(table=table))


def test_header_blank_first_cell_is_not_unlabeled_numeric_row() -> None:
    rows = [["", "January 30, 2026", "January 31, 2025"], ["Revenue", "12", "11"]]
    result = _compile(_document(table=_table(rows, header_rows={0})))
    assert "unlabeled_numeric_row" not in _codes(result)
    assert _table_element(result, "candidate_elements")


def test_group_children_are_traversed_but_group_is_not_projected() -> None:
    text = _text(parent="#/groups/0")
    group = _group(0, children=[{"$ref": "#/texts/0"}])
    result = _compile(_document(texts=[text], groups=[group]))

    assert [item["kind"] for item in result["candidate_elements"]] == ["text_fragment"]
    assert result["candidate_elements"][0]["upstream_parent_ref"] == "#/groups/0"
    assert not any(
        item["upstream_self_ref"].startswith("#/groups/")
        for item in [*result["candidate_elements"], *result["quarantined_elements"]]
    )


def test_picture_child_is_preordered_without_caption_or_ocr_inference() -> None:
    child = _text("Chart label", parent="#/pictures/0")
    picture = _picture(0, children=[{"$ref": "#/texts/0"}])
    result = _compile(_document(texts=[child], pictures=[picture]))

    assert [item["kind"] for item in result["candidate_elements"]] == [
        "picture_locator", "text_fragment",
    ]
    text_candidate = result["candidate_elements"][1]
    assert text_candidate["upstream_parent_ref"] == "#/pictures/0"
    assert text_candidate["text"] == "Chart label"
    assert result["unresolved_relationships"] == []
    assert not _has_key(result, "ocr_text")
    assert not result["authority"]["automatic_relationships_allowed"]


def test_table_caption_child_is_preordered_but_relation_stays_blocked() -> None:
    caption = _text(
        "Revenue by segment",
        parent="#/tables/0",
        label="caption",
    )
    table = _table(
        [["Metric", "FY26"], ["Revenue", "12"]],
        header_rows={0},
        children=[{"$ref": "#/texts/0"}],
    )
    table["captions"] = [{"$ref": "#/texts/0"}]
    result = _compile(_document(texts=[caption], tables=[table]))
    blocked = _table_element(result, "quarantined_elements")

    assert "upstream_relation_projection_not_supported" in blocked["blocker_codes"]
    assert result["candidate_elements"][0]["upstream_self_ref"] == "#/texts/0"
    assert result["candidate_elements"][0]["upstream_parent_ref"] == "#/tables/0"
    assert blocked["linked_footnotes"] == []
    assert not result["authority"]["automatic_relationships_allowed"]


def test_nested_non_group_children_keep_complete_preorder() -> None:
    text = _text("Nested label", parent="#/pictures/1")
    inner = _picture(
        1,
        parent="#/pictures/0",
        children=[{"$ref": "#/texts/0"}],
    )
    outer = _picture(0, children=[{"$ref": "#/pictures/1"}])
    result = _compile(_document(texts=[text], pictures=[outer, inner]))

    assert [item["upstream_self_ref"] for item in result["candidate_elements"]] == [
        "#/pictures/0", "#/pictures/1", "#/texts/0",
    ]
    assert result["candidate_elements"][-1]["upstream_parent_ref"] == "#/pictures/1"


def test_node_cycle_fails_closed() -> None:
    outer = _picture(0, children=[{"$ref": "#/pictures/1"}])
    inner = _picture(
        1,
        parent="#/pictures/0",
        children=[{"$ref": "#/pictures/0"}],
    )
    with pytest.raises(DoclingShadowAdapterError, match="cycle"):
        _compile(_document(texts=[], pictures=[outer, inner]))


def test_duplicate_node_reference_fails_closed() -> None:
    text = _text()
    duplicate = [{"$ref": "#/texts/0"}, {"$ref": "#/texts/0"}]
    with pytest.raises(DoclingShadowAdapterError, match="duplicate"):
        _compile(_document(texts=[text], body_children=duplicate))


def test_orphan_node_fails_closed_inventory() -> None:
    first = _text("First", self_ref="#/texts/0")
    orphan = _text("Orphan", self_ref="#/texts/1")
    with pytest.raises(DoclingShadowAdapterError, match="inventory"):
        _compile(
            _document(
                texts=[first, orphan],
                body_children=[{"$ref": "#/texts/0"}],
            )
        )


def test_parent_mismatch_fails_closed() -> None:
    text = _text(parent="#/pictures/0")
    picture = _picture(0)
    with pytest.raises(DoclingShadowAdapterError, match="parent_ref_mismatch"):
        _compile(
            _document(
                texts=[text],
                pictures=[picture],
                body_children=[{"$ref": "#/texts/0"}],
            )
        )


def test_unknown_child_reference_fails_closed() -> None:
    with pytest.raises(DoclingShadowAdapterError, match="child_ref_unknown"):
        _compile(
            _document(
                texts=[],
                body_children=[{"$ref": "#/texts/99"}],
            )
        )


@pytest.mark.parametrize(
    ("collection", "match"),
    [
        ("furniture", "furniture_content_not_supported"),
        ("form_items", "collection_not_supported:form_items"),
        ("key_value_items", "collection_not_supported:key_value_items"),
    ],
)
def test_unsupported_node_routes_remain_fail_closed(
    collection: str,
    match: str,
) -> None:
    document = _document()
    if collection == "furniture":
        document[collection]["children"] = [{"$ref": "#/texts/0"}]
    else:
        document[collection] = [{"self_ref": f"#/{collection}/0"}]
    with pytest.raises(DoclingShadowAdapterError, match=match):
        _compile(document)


def test_cross_page_text_is_mechanically_split_not_auto_joined() -> None:
    text = _text("Alpha Beta", [_prov(1, (0, 5)), _prov(2, (6, 10))])
    result = _compile(_document(text=text))
    fragments = result["candidate_elements"]
    source = result["quarantined_elements"][0]
    relation = result["unresolved_relationships"][0]

    assert [item["text"] for item in fragments] == ["Alpha", "Beta"]
    assert [item["page_no"] for item in fragments] == [1, 2]
    assert source["source_payload"]["text"] == "Alpha Beta"
    assert (relation["type"], relation["status"]) == (
        "cross_page_text_fragmentation", "unresolved"
    )
    assert not result["authority"]["automatic_relationships_allowed"]


def test_cross_page_table_is_quarantined_without_cell_loss() -> None:
    table = _table(
        [["Metric", "FY26"], ["Revenue", "12"]],
        prov=[_prov(1), _prov(2)], header_rows={0},
    )
    result = _compile(_document(table=table))
    blocked = _table_element(result, "quarantined_elements")
    code = "cross_page_table_provenance_unresolved"

    assert code in _codes(result) and code in blocked["blocker_codes"]
    cells = blocked["source_payload"]["data"]["table_cells"]
    assert [cell["text"] for cell in cells] == ["Metric", "FY26", "Revenue", "12"]


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda d: d.update(schema_name="OtherDocument"), "schema"),
        (lambda d: d.update(version="9.9.9"), "version"),
        (lambda d: d["texts"][0].update(self_ref="#/texts/7"), "self_ref|ref"),
        (lambda d: d["texts"][0]["prov"][0].update(page_no=3), "page"),
        (lambda d: d["texts"][0]["prov"][0]["bbox"].update(r="bad"), "bbox"),
        (lambda d: d["texts"][0]["prov"][0].update(charspan=[0, 99]), "charspan"),
    ],
)
def test_schema_lineage_and_geometry_drift_fail_closed(mutation: Any, match: str) -> None:
    document = _document()
    mutation(document)
    with pytest.raises(DoclingShadowAdapterError, match=match):
        _compile(document)


@pytest.mark.parametrize("spans", [[(0, 7), (6, 10)], [(-1, 5), (6, 10)], [(0, 5), (6, 11)]])
def test_invalid_cross_page_charspans_fail_closed(spans: list[tuple[int, int]]) -> None:
    text = _text("Alpha Beta", [_prov(1, spans[0]), _prov(2, spans[1])])
    with pytest.raises(DoclingShadowAdapterError, match="charspan"):
        _compile(_document(text=text))


@pytest.mark.parametrize(
    ("value", "spans"),
    [
        ("Alpha Beta", [(1, 10)]), ("AlphaXBeta", [(0, 5), (6, 10)]),
        ("Alpha Beta", [(0, 9)]), ("Alpha", [(0, 0)]),
    ],
    ids=["prefix-gap", "middle-gap", "suffix-gap", "zero-span"],
)
def test_charspans_cannot_drop_nonwhitespace(
    value: str, spans: list[tuple[int, int]]
) -> None:
    text = _text(value, [_prov(1, span) for span in spans])
    with pytest.raises(DoclingShadowAdapterError, match="charspan|coverage|gap"):
        _compile(_document(text=text))


def test_charspan_whitespace_gap_is_allowed() -> None:
    text = _text("Alpha Beta", [_prov(1, (0, 5)), _prov(1, (6, 10))])
    result = _compile(_document(text=text))
    assert [item["text"] for item in result["candidate_elements"]] == ["Alpha", "Beta"]


@pytest.mark.parametrize(
    "cells",
    [
        [_cell(0, 0, "A"), _cell(0, 0, "B")],
        [_cell(0, 0, "A", end_row=2), _cell(1, 0, "B")],
        [_cell(0, 0, "A", end_col=2), _cell(0, 1, "B")],
    ],
    ids=["exact", "partial-row", "partial-column"],
)
def test_overlapping_table_cells_quarantine_whole_table(
    cells: list[dict[str, Any]],
) -> None:
    table = _table([["A", "B"], ["C", "D"]])
    table["data"]["table_cells"] = cells
    result = _compile(_document(table=table))
    blocked = _table_element(result, "quarantined_elements")
    finding = next(item for item in result["findings"] if item["code"] == "table_cell_overlap")

    assert "table_cell_overlap" in blocked["blocker_codes"]
    assert finding["severity"] == "blocker"
    assert finding["disposition"] == "quarantine_without_repair"
    assert len(blocked["cell_lineage"]) == len(cells)
    assert blocked["source_payload"]["data"]["table_cells"] == cells
    assert not any(
        item["upstream_self_ref"] == "#/tables/0"
        for item in result["candidate_elements"]
    )
    assert not result["authority"]["repair_performed"]


@pytest.mark.parametrize("field", ["captions", "footnotes", "references"])
def test_upstream_table_relations_are_blocked(field: str) -> None:
    table = _table([["Metric", "FY26"], ["Revenue", "12"]], header_rows={0})
    table[field] = [{"$ref": "#/texts/0"}]
    result = _compile(_document(table=table))
    blocked = _table_element(result, "quarantined_elements")
    code = "upstream_relation_projection_not_supported"

    assert code in _codes(result) and code in blocked["blocker_codes"]
    assert blocked["linked_footnotes"] == []
    assert not any(e["upstream_self_ref"] == "#/tables/0" for e in result["candidate_elements"])
    assert not result["authority"]["automatic_relationships_allowed"]


@pytest.mark.parametrize(
    ("coordinate", "value"),
    [("l", -0.01), ("r", 612.01), ("b", -0.01), ("t", 792.01)],
)
def test_provenance_bbox_must_be_within_page(coordinate: str, value: float) -> None:
    document = _document()
    document["texts"][0]["prov"][0]["bbox"][coordinate] = value
    with pytest.raises(DoclingShadowAdapterError, match="bbox|page"):
        _compile(document)


def test_provenance_bbox_may_touch_page_boundaries() -> None:
    bbox = {"b": 0.0, "coord_origin": "BOTTOMLEFT", "l": 0.0, "r": 612.0, "t": 792.0}
    document = _document()
    document["texts"][0]["prov"][0]["bbox"] = bbox
    assert _compile(document)["candidate_elements"][0]["bbox"] == bbox


@pytest.mark.parametrize("binding", ["source", "parser"])
def test_binding_contract_rejects_extra_keys(binding: str) -> None:
    source, parser = dict(SOURCE_BINDING), dict(PARSER_BINDING)
    (source if binding == "source" else parser)["unexpected_authority"] = True
    with pytest.raises(DoclingShadowAdapterError, match="binding|extra|key|unexpected"):
        _call(_canonical(_document()), source=source, parser=parser)


def test_result_digest_binds_canonical_output_content() -> None:
    result = _compile(_document())
    claimed = result.pop("result_digest")
    assert hashlib.sha256(_canonical(result)).hexdigest() == claimed
    result["candidate_elements"][0]["text"] = "mutated"
    assert hashlib.sha256(_canonical(result)).hexdigest() != claimed


def test_exact_input_hash_is_required() -> None:
    payload = _canonical(_document())
    with pytest.raises(DoclingShadowAdapterError, match="sha256|digest|hash"):
        _call(payload, expected="0" * 64)


@pytest.mark.parametrize(
    "payload",
    [
        b'{"schema_name":"DoclingDocument","value":NaN}',
        b'{"schema_name":"DoclingDocument","value":Infinity}',
        b'{"schema_name":"DoclingDocument","value":-Infinity}',
        b'{"schema_name":"DoclingDocument","schema_name":"duplicate"}',
    ],
)
def test_nonstandard_or_ambiguous_json_is_rejected(payload: bytes) -> None:
    with pytest.raises(DoclingShadowAdapterError, match="JSON|json|duplicate|nonfinite"):
        _call(payload)
