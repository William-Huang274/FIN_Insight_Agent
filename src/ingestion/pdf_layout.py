from __future__ import annotations

from collections import Counter
import hashlib
from pathlib import Path
import re
import statistics
from typing import Any, Callable, Iterable, Mapping, Sequence
import unicodedata

from pypdf import PdfReader


PARSED_PDF_LAYOUT_SCHEMA_VERSION = "fin_ia_parsed_pdf_layout_document_v2_0"
PDF_LAYOUT_QUALITY_SCHEMA_VERSION = "fin_ia_pdf_layout_quality_receipt_v1_0"

_NUMERIC_TOKEN = re.compile(
    r"^(?:[€$£¥]|(?:\(?[-+]?\d[\d,.]*\)?)(?:%|x)?|[-–—])$",
    re.IGNORECASE,
)
_REVISION_TERMS = (
    "adjusted accordingly",
    "comparative figures",
    "reclassified",
    "restated",
    "transferred to",
    "change in segment structure",
)


class PdfLayoutParseError(ValueError):
    """A PDF layout could not be recovered without weakening source lineage."""


def parse_captured_pdf_layout(
    capture: Mapping[str, Any],
    *,
    repository_root: str | Path,
    selected_page_numbers: Sequence[int],
    force_ocr_page_numbers: Iterable[int] = (),
    ocr_engine_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Parse selected pages while auditing the complete captured PDF.

    The function deliberately stops at candidate parsing.  It never grants
    Evidence or NumericFact authority.  Native PDF words and OCR observations
    share one normalized page/word/table contract, so downstream consumers do
    not need provider-specific branches.
    """

    root = Path(repository_root).resolve()
    raw_ref = str(
        capture.get("document_path") or capture.get("raw_object_ref") or ""
    ).strip()
    raw_path = _safe_repo_path(root, raw_ref)
    if not raw_path.is_file():
        raise PdfLayoutParseError("pdf_layout_raw_capture_missing")
    body = raw_path.read_bytes()
    raw_sha256 = hashlib.sha256(body).hexdigest()
    expected_sha256 = str(
        capture.get("sha256") or capture.get("raw_object_sha256") or ""
    ).strip()
    expected_bytes = int(
        capture.get("byte_count") or capture.get("raw_object_bytes") or 0
    )
    if (
        not body
        or raw_sha256 != expected_sha256
        or len(body) != expected_bytes
    ):
        raise PdfLayoutParseError("pdf_layout_raw_capture_digest_mismatch")

    selected = tuple(sorted({int(value) for value in selected_page_numbers}))
    forced_ocr = frozenset(int(value) for value in force_ocr_page_numbers)
    if not selected or min(selected) < 1 or not forced_ocr.issubset(selected):
        raise PdfLayoutParseError("pdf_layout_page_selection_invalid")

    reader = PdfReader(raw_path)
    encryption_state = "not_encrypted"
    if reader.is_encrypted:
        try:
            password_type = reader.decrypt("")
        except Exception as exc:  # pragma: no cover - backend exception varies
            raise PdfLayoutParseError("pdf_layout_pdf_encrypted_unreadable") from exc
        if not password_type:
            raise PdfLayoutParseError("pdf_layout_pdf_encrypted_unreadable")
        encryption_state = "encrypted_empty_user_password_readable"
    page_count = len(reader.pages)
    expected_page_count = int(capture.get("pdf_page_count") or page_count)
    if page_count != expected_page_count or max(selected) > page_count:
        raise PdfLayoutParseError("pdf_layout_page_count_mismatch")

    page_inventory: list[dict[str, Any]] = []
    native_page_text: dict[int, str] = {}
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = _normalize_text(page.extract_text() or "")
        except Exception as exc:  # pragma: no cover - backend exception varies
            raise PdfLayoutParseError(
                f"pdf_layout_inventory_extract_failed:{page_number}"
            ) from exc
        page_inventory.append(
            {
                "page_number": page_number,
                "native_text_characters": len(text),
                "native_text_sha256": hashlib.sha256(
                    text.encode("utf-8")
                ).hexdigest(),
                "native_text_present": bool(text),
            }
        )
        if page_number in selected:
            native_page_text[page_number] = text

    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - dependency gate
        raise PdfLayoutParseError("pdf_layout_pdfplumber_unavailable") from exc

    pages: list[dict[str, Any]] = []
    with pdfplumber.open(raw_path) as pdf:
        for page_number in selected:
            page = pdf.pages[page_number - 1]
            native_words = _native_words(page)
            native_sufficient = (
                len(native_words) >= 20
                and len(native_page_text.get(page_number, "")) >= 80
            )
            use_ocr = page_number in forced_ocr or not native_sufficient
            if use_ocr:
                words, ocr_receipt = _ocr_words(
                    raw_path,
                    page_number=page_number,
                    page_width=float(page.width),
                    page_height=float(page.height),
                    ocr_engine_factory=ocr_engine_factory,
                )
                extraction_mode = (
                    "ocr_forced_evaluation_mutation"
                    if page_number in forced_ocr
                    else "ocr_fallback_low_native_text"
                )
            else:
                words = native_words
                ocr_receipt = {
                    "attempted": False,
                    "engine": None,
                    "recognized_line_count": 0,
                    "mean_confidence": None,
                }
                extraction_mode = "native_pdf_layout"

            lines = _cluster_words_into_lines(words)
            tables = _detect_table_regions(
                page=page,
                words=words,
                lines=lines,
                extraction_mode=extraction_mode,
            )
            footnotes = _detect_footnotes(
                lines,
                page_height=float(page.height),
                table_regions=tables,
            )
            text_blocks = _compile_text_blocks(
                lines,
                page_width=float(page.width),
                table_regions=tables,
                footnotes=footnotes,
            )
            material_words = [
                word for word in words if _is_material_token(str(word["text"]))
            ]
            low_confidence_material = [
                word
                for word in material_words
                if float(word.get("confidence") or 0.0) < 0.90
            ]
            page_text = "\n".join(str(row["text"]) for row in lines).strip()
            page_status = (
                "usable_native_layout_candidate"
                if extraction_mode == "native_pdf_layout"
                else (
                    "ocr_candidate_needs_review"
                    if words and not low_confidence_material
                    else "ocr_low_confidence_abstain"
                )
            )
            pages.append(
                {
                    "page_number": page_number,
                    "page_width": round(float(page.width), 6),
                    "page_height": round(float(page.height), 6),
                    "extraction_mode": extraction_mode,
                    "page_status": page_status,
                    "native_text_characters": len(
                        native_page_text.get(page_number, "")
                    ),
                    "native_word_count": len(native_words),
                    "word_count": len(words),
                    "line_count": len(lines),
                    "table_region_count": len(tables),
                    "footnote_count": len(footnotes),
                    "material_token_count": len(material_words),
                    "low_confidence_material_token_count": len(
                        low_confidence_material
                    ),
                    "text": page_text,
                    "text_sha256": hashlib.sha256(
                        page_text.encode("utf-8")
                    ).hexdigest(),
                    "words": words,
                    "lines": lines,
                    "table_regions": tables,
                    "footnotes": footnotes,
                    "text_blocks": text_blocks,
                    "ocr_receipt": ocr_receipt,
                    "candidate_is_not_evidence": True,
                    "material_numbers_may_enter_s2": False,
                }
            )

    quality = _quality_receipt(
        page_count=page_count,
        selected_pages=pages,
        forced_ocr=forced_ocr,
    )
    text_identity = "\n".join(
        f"PAGE:{page['page_number']}:{page['text_sha256']}"
        for page in pages
    )
    return {
        "schema_version": PARSED_PDF_LAYOUT_SCHEMA_VERSION,
        "parser_adapter": "pdfplumber_layout_plus_rapidocr_v2",
        "capture_schema_version": str(capture.get("schema_version") or ""),
        "capture_id": str(
            capture.get("task_id")
            or capture.get("attempt_id")
            or capture.get("plan_id")
            or ""
        ),
        "route_id": str(capture.get("plan_id") or capture.get("route_id") or ""),
        "source_owner_ticker": str(
            capture.get("ticker") or capture.get("case_key") or ""
        ).strip().upper(),
        "issuer_name": str(
            capture.get("company_name") or capture.get("issuer_name") or ""
        ).strip(),
        "document_type": str(
            capture.get("report_type") or capture.get("document_type") or ""
        ).strip().upper(),
        "title": str(
            (
                (capture.get("selected_candidate") or {}).get("display_name")
                if isinstance(capture.get("selected_candidate"), Mapping)
                else capture.get("title")
            )
            or ""
        ).strip(),
        "publication_date": _publication_date(capture),
        "reporting_period_end": str(capture.get("period_end") or "").strip()
        or None,
        "fiscal_year": int(capture.get("fiscal_year") or 0) or None,
        "source_url": str(capture.get("source_url") or "").strip(),
        "raw_object_ref": raw_ref.replace("\\", "/"),
        "raw_object_sha256": raw_sha256,
        "raw_object_bytes": len(body),
        "page_count": page_count,
        "encryption_state": encryption_state,
        "selected_page_numbers": list(selected),
        "page_inventory": page_inventory,
        "pages": pages,
        "source_text_digest": hashlib.sha256(
            text_identity.encode("utf-8")
        ).hexdigest(),
        "quality_receipt": quality,
        "capture_before_parse": True,
        "parsed_document_is_evidence": False,
        "promotion_status": "parsed_layout_candidates_only_not_evidence",
    }


def public_pdf_layout_projection(parsed: Mapping[str, Any]) -> dict[str, Any]:
    quality = dict(parsed.get("quality_receipt") or {})
    return {
        "schema_version": parsed.get("schema_version"),
        "parser_adapter": parsed.get("parser_adapter"),
        "capture_id": parsed.get("capture_id"),
        "route_id": parsed.get("route_id"),
        "source_owner_ticker": parsed.get("source_owner_ticker"),
        "issuer_name": parsed.get("issuer_name"),
        "document_type": parsed.get("document_type"),
        "title": parsed.get("title"),
        "publication_date": parsed.get("publication_date"),
        "source_url": parsed.get("source_url"),
        "raw_object_sha256": parsed.get("raw_object_sha256"),
        "raw_object_bytes": parsed.get("raw_object_bytes"),
        "page_count": parsed.get("page_count"),
        "selected_page_numbers": parsed.get("selected_page_numbers"),
        "source_text_digest": parsed.get("source_text_digest"),
        "quality_receipt": quality,
        "promotion_status": parsed.get("promotion_status"),
    }


def _safe_repo_path(root: Path, value: str) -> Path:
    if not value or Path(value).is_absolute():
        raise PdfLayoutParseError("pdf_layout_raw_ref_invalid")
    resolved = (root / value).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PdfLayoutParseError("pdf_layout_raw_ref_invalid") from exc
    return resolved


def _publication_date(capture: Mapping[str, Any]) -> str:
    value = str(capture.get("publication_date") or "").strip()
    if value:
        return value
    selected = capture.get("selected_candidate")
    if isinstance(selected, Mapping):
        raw = str(selected.get("released_date") or "").strip()
        if raw:
            from datetime import datetime

            for pattern in ("%b %d, %Y", "%B %d, %Y"):
                try:
                    return datetime.strptime(raw, pattern).date().isoformat()
                except ValueError:
                    pass
    raise PdfLayoutParseError("pdf_layout_publication_date_missing")


def _normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).replace("\x00", "")
    return "\n".join(
        " ".join(line.split()) for line in value.splitlines() if line.strip()
    ).strip()


def _native_words(page: Any) -> list[dict[str, Any]]:
    raw = page.extract_words(
        use_text_flow=False,
        keep_blank_chars=False,
        extra_attrs=["size"],
    )
    width = float(page.width)
    height = float(page.height)
    words: list[dict[str, Any]] = []
    for row in raw:
        text = _normalize_text(str(row.get("text") or ""))
        if not text:
            continue
        bbox = (
            float(row["x0"]),
            float(row["top"]),
            float(row["x1"]),
            float(row["bottom"]),
        )
        words.append(
            {
                "text": text,
                "bbox": _round_bbox(bbox),
                "bbox_normalized": _normalized_bbox(bbox, width, height),
                "confidence": 1.0,
                "font_size": round(float(row.get("size") or 0.0), 4),
                "observation_source": "native_pdf_word",
            }
        )
    return words


def _ocr_words(
    raw_path: Path,
    *,
    page_number: int,
    page_width: float,
    page_height: float,
    ocr_engine_factory: Callable[[], Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        import pypdfium2 as pdfium
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:  # pragma: no cover - dependency gate
        raise PdfLayoutParseError("pdf_layout_ocr_dependency_unavailable") from exc

    document = pdfium.PdfDocument(raw_path)
    try:
        page = document[page_number - 1]
        image = page.render(scale=2.0).to_pil()
    finally:
        document.close()
    factory = ocr_engine_factory or RapidOCR
    engine = factory()
    raw_result, _elapsed = engine(image)
    rows = raw_result or []
    image_width, image_height = image.size
    words: list[dict[str, Any]] = []
    confidences: list[float] = []
    for raw in rows:
        if not isinstance(raw, (list, tuple)) or len(raw) < 3:
            continue
        polygon, raw_text, raw_confidence = raw[:3]
        text = _normalize_text(str(raw_text or ""))
        if not text or not isinstance(polygon, (list, tuple)):
            continue
        xs = [float(point[0]) for point in polygon]
        ys = [float(point[1]) for point in polygon]
        bbox = (
            min(xs) / image_width * page_width,
            min(ys) / image_height * page_height,
            max(xs) / image_width * page_width,
            max(ys) / image_height * page_height,
        )
        confidence = float(raw_confidence)
        confidences.append(confidence)
        words.append(
            {
                "text": text,
                "bbox": _round_bbox(bbox),
                "bbox_normalized": _normalized_bbox(
                    bbox, page_width, page_height
                ),
                "confidence": round(confidence, 6),
                "font_size": None,
                "observation_source": "rapidocr_line",
            }
        )
    return words, {
        "attempted": True,
        "engine": "rapidocr_onnxruntime",
        "render_adapter": "pypdfium2",
        "render_scale": 2.0,
        "recognized_line_count": len(words),
        "mean_confidence": (
            round(statistics.fmean(confidences), 6) if confidences else None
        ),
    }


def _cluster_words_into_lines(
    words: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[list[Mapping[str, Any]]] = []
    for word in sorted(
        words,
        key=lambda item: (
            float(item["bbox"][1]),
            float(item["bbox"][0]),
        ),
    ):
        top = float(word["bbox"][1])
        height = max(1.0, float(word["bbox"][3]) - top)
        match: list[Mapping[str, Any]] | None = None
        for row in reversed(rows[-4:]):
            row_top = statistics.fmean(float(item["bbox"][1]) for item in row)
            row_height = statistics.fmean(
                max(1.0, float(item["bbox"][3]) - float(item["bbox"][1]))
                for item in row
            )
            if abs(top - row_top) <= max(2.2, min(height, row_height) * 0.45):
                match = row
                break
        if match is None:
            rows.append([word])
        else:
            match.append(word)

    segmented_rows: list[list[Mapping[str, Any]]] = []
    for row in rows:
        ordered = sorted(row, key=lambda item: float(item["bbox"][0]))
        if ordered and all(
            item.get("observation_source") == "native_pdf_word"
            for item in ordered
        ):
            current: list[Mapping[str, Any]] = []
            for item in ordered:
                if (
                    current
                    and float(item["bbox"][0]) - float(current[-1]["bbox"][2]) > 20.0
                ):
                    segmented_rows.append(current)
                    current = []
                current.append(item)
            if current:
                segmented_rows.append(current)
        else:
            segmented_rows.append(ordered)

    output: list[dict[str, Any]] = []
    for index, ordered in enumerate(segmented_rows, start=1):
        text = " ".join(str(item["text"]) for item in ordered).strip()
        bbox = (
            min(float(item["bbox"][0]) for item in ordered),
            min(float(item["bbox"][1]) for item in ordered),
            max(float(item["bbox"][2]) for item in ordered),
            max(float(item["bbox"][3]) for item in ordered),
        )
        output.append(
            {
                "line_index": index,
                "text": text,
                "bbox": _round_bbox(bbox),
                "mean_confidence": round(
                    statistics.fmean(
                        float(item.get("confidence") or 0.0) for item in ordered
                    ),
                    6,
                ),
                "word_count": len(ordered),
                "word_indices": [words.index(item) for item in ordered],
            }
        )
    return output


def _detect_table_regions(
    *,
    page: Any,
    words: Sequence[Mapping[str, Any]],
    lines: Sequence[Mapping[str, Any]],
    extraction_mode: str,
) -> list[dict[str, Any]]:
    if extraction_mode == "native_pdf_layout":
        return _vector_rule_tables(page, words)
    return _numeric_line_tables(lines, page_width=float(page.width))


def _vector_rule_tables(
    page: Any,
    words: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    width = float(page.width)
    height = float(page.height)
    segments: list[tuple[float, float, float]] = []
    for line in page.lines:
        x0 = float(line.get("x0") or 0.0)
        x1 = float(line.get("x1") or 0.0)
        y0 = float(line.get("y0") or 0.0)
        y1 = float(line.get("y1") or 0.0)
        if abs(y1 - y0) <= 0.8 and abs(x1 - x0) >= 30.0:
            segments.append((x0, height - y0, x1))
    by_y: list[tuple[float, list[tuple[float, float]]]] = []
    for x0, top, x1 in sorted(segments, key=lambda row: (row[1], row[0])):
        group = next(
            (row for row in reversed(by_y[-3:]) if abs(row[0] - top) <= 0.9),
            None,
        )
        if group is None:
            by_y.append((top, [(x0, x1)]))
        else:
            group[1].append((x0, x1))
    separators = [
        (top, spans)
        for top, spans in by_y
        if len(spans) >= 2 or sum(x1 - x0 for x0, x1 in spans) >= width * 0.34
    ]
    groups: list[list[tuple[float, list[tuple[float, float]]]]] = []
    for separator in separators:
        if not groups or separator[0] - groups[-1][-1][0] > 25.0:
            groups.append([separator])
        else:
            groups[-1].append(separator)

    regions: list[dict[str, Any]] = []
    for group in groups:
        if len(group) < 3:
            continue
        all_spans = [span for _, spans in group for span in spans]
        for x0, x1 in _horizontal_components(all_spans):
            component_rows = [
                (
                    top,
                    [span for span in spans if span[0] >= x0 - 1 and span[1] <= x1 + 1],
                )
                for top, spans in group
            ]
            component_rows = [row for row in component_rows if row[1]]
            if len(component_rows) < 3:
                continue
            y_values = [row[0] for row in component_rows]
            component_spans = [
                span for _, row_spans in component_rows for span in row_spans
            ]
            spans = _stable_cell_spans(component_spans)
            rows: list[dict[str, Any]] = []
            for row_index, (top, bottom) in enumerate(
                zip(y_values[:-1], y_values[1:]), start=1
            ):
                row_words = [
                    word
                    for word in words
                    if top - 0.8
                    <= (float(word["bbox"][1]) + float(word["bbox"][3])) / 2
                    <= bottom + 0.8
                    and x0 - 1
                    <= (float(word["bbox"][0]) + float(word["bbox"][2])) / 2
                    <= x1 + 1
                ]
                cells = _words_to_cells(row_words, spans)
                text = " | ".join(cell["text"] for cell in cells if cell["text"])
                if not text:
                    continue
                numeric_tokens = [
                    token
                    for cell in cells
                    for token in cell["text"].split()
                    if _is_material_token(token)
                ]
                rows.append(
                    {
                        "row_index": row_index,
                        "bbox": _round_bbox((x0, top, x1, bottom)),
                        "cells": cells,
                        "text": text,
                        "numeric_tokens": numeric_tokens,
                        "row_binding_status": (
                            "candidate_row_with_label_and_values"
                            if cells and cells[0]["text"] and numeric_tokens
                            else "structural_row_needs_review"
                        ),
                    }
                )
            if not rows:
                continue
            regions.append(
                {
                    "table_index": len(regions) + 1,
                    "detection_method": "vector_horizontal_rule_grid",
                    "bbox": _round_bbox((x0, y_values[0], x1, y_values[-1])),
                    "cell_spans": [_round_pair(span) for span in spans],
                    "rows": rows,
                    "table_binding_status": "candidate_structure_needs_header_review",
                    "candidate_is_not_evidence": True,
                    "numeric_fact_authority": False,
                }
            )
    return regions


def _horizontal_components(
    spans: Sequence[tuple[float, float]],
) -> list[tuple[float, float]]:
    components: list[list[float]] = []
    for x0, x1 in sorted(spans):
        if not components or x0 - components[-1][1] > 8.0:
            components.append([x0, x1])
        else:
            components[-1][1] = max(components[-1][1], x1)
    return [(row[0], row[1]) for row in components]


def _numeric_line_tables(
    lines: Sequence[Mapping[str, Any]], *, page_width: float
) -> list[dict[str, Any]]:
    numeric_rows: list[Mapping[str, Any]] = []
    for line in lines:
        tokens = str(line.get("text") or "").split()
        numeric = [token for token in tokens if _is_material_token(token)]
        bbox = line.get("bbox") or (0, 0, 0, 0)
        if len(numeric) >= 2 and float(bbox[2]) - float(bbox[0]) >= page_width * 0.2:
            numeric_rows.append(line)
    groups: list[list[Mapping[str, Any]]] = []
    for row in numeric_rows:
        top = float(row["bbox"][1])
        if not groups or top - float(groups[-1][-1]["bbox"][3]) > 26.0:
            groups.append([row])
        else:
            groups[-1].append(row)
    output: list[dict[str, Any]] = []
    for index, group in enumerate(groups, start=1):
        if len(group) < 2:
            continue
        bbox = (
            min(float(row["bbox"][0]) for row in group),
            min(float(row["bbox"][1]) for row in group),
            max(float(row["bbox"][2]) for row in group),
            max(float(row["bbox"][3]) for row in group),
        )
        output.append(
            {
                "table_index": index,
                "detection_method": "ocr_numeric_line_cluster",
                "bbox": _round_bbox(bbox),
                "cell_spans": [],
                "rows": [
                    {
                        "row_index": row_index,
                        "bbox": row["bbox"],
                        "cells": [{"column_index": 1, "text": row["text"], "bbox": row["bbox"]}],
                        "text": row["text"],
                        "numeric_tokens": [
                            token
                            for token in str(row["text"]).split()
                            if _is_material_token(token)
                        ],
                        "row_binding_status": "ocr_structural_row_needs_review",
                    }
                    for row_index, row in enumerate(group, start=1)
                ],
                "table_binding_status": "ocr_candidate_needs_review",
                "candidate_is_not_evidence": True,
                "numeric_fact_authority": False,
            }
        )
    return output


def _stable_cell_spans(
    spans: Sequence[tuple[float, float]],
) -> list[tuple[float, float]]:
    counts = Counter((round(x0, 1), round(x1, 1)) for x0, x1 in spans)
    candidates = [
        (x0, x1, count) for (x0, x1), count in counts.items() if count >= 2
    ]
    if not candidates:
        candidates = [(x0, x1, count) for (x0, x1), count in counts.items()]
    output: list[tuple[float, float]] = []
    for x0, x1, count in sorted(candidates, key=lambda row: (row[0], row[1])):
        contains_narrower = sum(
            1
            for other0, other1, other_count in candidates
            if other_count >= count
            and x0 <= other0
            and other1 <= x1
            and (other0, other1) != (x0, x1)
        )
        if contains_narrower >= 2:
            continue
        output.append((x0, x1))
    return output


def _words_to_cells(
    words: Sequence[Mapping[str, Any]], spans: Sequence[tuple[float, float]]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for column_index, (x0, x1) in enumerate(spans, start=1):
        selected = sorted(
            (
                word
                for word in words
                if x0 - 1
                <= (float(word["bbox"][0]) + float(word["bbox"][2])) / 2
                <= x1 + 1
            ),
            key=lambda item: (float(item["bbox"][1]), float(item["bbox"][0])),
        )
        text = " ".join(str(word["text"]) for word in selected).strip()
        output.append(
            {
                "column_index": column_index,
                "text": text,
                "bbox": _round_bbox(
                    (
                        x0,
                        min((float(word["bbox"][1]) for word in selected), default=0.0),
                        x1,
                        max((float(word["bbox"][3]) for word in selected), default=0.0),
                    )
                ),
            }
        )
    return output


def _detect_footnotes(
    lines: Sequence[Mapping[str, Any]],
    *,
    page_height: float,
    table_regions: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for line in lines:
        text = str(line.get("text") or "").strip()
        bbox = line.get("bbox") or (0, 0, 0, 0)
        top = float(bbox[1])
        if top >= page_height * 0.955:
            continue
        first = text.split(maxsplit=1)[0] if text else ""
        below_table = any(top >= float(table["bbox"][3]) - 2 for table in table_regions)
        if (
            re.fullmatch(r"\d{1,2}", first)
            and len(text) >= 35
            and (below_table or top >= page_height * 0.68)
        ):
            output.append(
                {
                    "footnote_index": len(output) + 1,
                    "marker": first,
                    "text": text,
                    "bbox": list(bbox),
                    "binding_status": "footnote_candidate_needs_table_link_review",
                }
            )
    return output


def _compile_text_blocks(
    lines: Sequence[Mapping[str, Any]],
    *,
    page_width: float,
    table_regions: Sequence[Mapping[str, Any]],
    footnotes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    excluded_line_indices = {
        int(line["line_index"])
        for line in lines
        if any(_bbox_intersects(line["bbox"], table["bbox"]) for table in table_regions)
        or any(_bbox_intersects(line["bbox"], note["bbox"]) for note in footnotes)
    }
    candidates = [
        line
        for line in lines
        if int(line["line_index"]) not in excluded_line_indices
        and float(line["bbox"][1]) < 555
        and len(str(line.get("text") or "")) >= 2
    ]
    columns: dict[str, list[Mapping[str, Any]]] = {"left": [], "right": []}
    for line in candidates:
        start = float(line["bbox"][0])
        columns["left" if start < page_width * 0.48 else "right"].append(line)
    blocks: list[dict[str, Any]] = []
    for column, column_lines in columns.items():
        current: list[Mapping[str, Any]] = []
        for line in sorted(column_lines, key=lambda row: float(row["bbox"][1])):
            line_text = str(line.get("text") or "").strip()
            heading_boundary = (
                len(line_text) <= 88
                and len(line_text.split()) <= 10
                and not line_text.endswith((".", ",", ";", ":"))
                and (
                    line_text.casefold().startswith("change in ")
                    or sum(word[:1].isupper() for word in line_text.split())
                    >= max(2, len(line_text.split()) - 1)
                )
            )
            if current and (
                float(line["bbox"][1]) - float(current[-1]["bbox"][3]) > 17.0
                or heading_boundary
            ):
                blocks.append(_text_block(current, column, len(blocks) + 1))
                current = []
            current.append(line)
        if current:
            blocks.append(_text_block(current, column, len(blocks) + 1))
    return sorted(blocks, key=lambda row: (row["bbox"][1], row["bbox"][0]))


def _text_block(
    lines: Sequence[Mapping[str, Any]], column: str, index: int
) -> dict[str, Any]:
    text = " ".join(str(line["text"]) for line in lines).strip()
    lowered = text.casefold()
    bbox = (
        min(float(line["bbox"][0]) for line in lines),
        min(float(line["bbox"][1]) for line in lines),
        max(float(line["bbox"][2]) for line in lines),
        max(float(line["bbox"][3]) for line in lines),
    )
    return {
        "block_index": index,
        "column": column,
        "text": text,
        "bbox": _round_bbox(bbox),
        "block_role": (
            "revision_or_restatement_context"
            if any(term in lowered for term in _REVISION_TERMS)
            else "page_context"
        ),
    }


def _quality_receipt(
    *,
    page_count: int,
    selected_pages: Sequence[Mapping[str, Any]],
    forced_ocr: frozenset[int],
) -> dict[str, Any]:
    modes = Counter(str(page["extraction_mode"]) for page in selected_pages)
    statuses = Counter(str(page["page_status"]) for page in selected_pages)
    receipt = {
        "schema_version": PDF_LAYOUT_QUALITY_SCHEMA_VERSION,
        "status": (
            "selected_pages_parsed_with_typed_abstention"
            if any("abstain" in key for key in statuses)
            else "selected_pages_parsed_candidate_quality_ready"
        ),
        "complete_document_page_count_verified": True,
        "complete_document_page_count": page_count,
        "selected_page_count": len(selected_pages),
        "extraction_modes": dict(sorted(modes.items())),
        "page_statuses": dict(sorted(statuses.items())),
        "table_region_count": sum(
            int(page["table_region_count"]) for page in selected_pages
        ),
        "footnote_count": sum(int(page["footnote_count"]) for page in selected_pages),
        "low_confidence_material_token_count": sum(
            int(page["low_confidence_material_token_count"])
            for page in selected_pages
        ),
        "forced_ocr_pages": sorted(forced_ocr),
        "accepted_evidence_authority_granted": False,
        "numeric_fact_authority_granted": False,
        "known_boundary": (
            "Parser quality is a candidate-stage receipt. Native or OCR text, table "
            "rows and footnotes require object binding and Evidence review; material "
            "numbers require an independent S2 sibling adjudication."
        ),
    }
    return {**receipt, "quality_digest": _digest(receipt)}


def _is_material_token(value: str) -> bool:
    token = value.strip().rstrip(".,;:")
    return bool(_NUMERIC_TOKEN.fullmatch(token))


def _bbox_intersects(left: Sequence[float], right: Sequence[float]) -> bool:
    return not (
        float(left[2]) < float(right[0])
        or float(right[2]) < float(left[0])
        or float(left[3]) < float(right[1])
        or float(right[3]) < float(left[1])
    )


def _round_bbox(value: Sequence[float]) -> list[float]:
    return [round(float(item), 4) for item in value]


def _round_pair(value: Sequence[float]) -> list[float]:
    return [round(float(item), 4) for item in value]


def _normalized_bbox(
    bbox: Sequence[float], width: float, height: float
) -> list[float]:
    return [
        round(float(bbox[0]) / width, 8),
        round(float(bbox[1]) / height, 8),
        round(float(bbox[2]) / width, 8),
        round(float(bbox[3]) / height, 8),
    ]


def _digest(value: Any) -> str:
    import json

    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "PARSED_PDF_LAYOUT_SCHEMA_VERSION",
    "PDF_LAYOUT_QUALITY_SCHEMA_VERSION",
    "PdfLayoutParseError",
    "parse_captured_pdf_layout",
    "public_pdf_layout_projection",
]
