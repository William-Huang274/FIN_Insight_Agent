"""Geometry-grounded PDF candidates, without financial or heading authority.

pdfplumber owns edge joining and cell reconstruction. FIN retains its raw
observations and separates a repeated cell grid from an ambiguous layout box.
Neither classification grants authority to suppress source text or write SQL.
"""
from __future__ import annotations

from typing import Any


def ruled_structure_candidates(page: Any) -> dict[str, Any]:
    observations = []
    settings = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}
    for index, table in enumerate(page.find_tables(settings), start=1):
        values = table.extract()
        rows = []
        for row_index, row in enumerate(table.rows):
            cells = []
            for column_index, box in enumerate(row.cells):
                cells.append({
                    "column_index": column_index + 1,
                    "bbox": list(box) if box is not None else None,
                    # None is an absent cell (including a merged-cell slot),
                    # not an empty value and never a value to forward-fill.
                    "text": values[row_index][column_index],
                })
            rows.append({"row_index": row_index + 1, "cells": cells})
        populated = [sum(bool(c["text"] and c["text"].strip()) for c in r["cells"])
                     for r in rows]
        repeated_cells = sum(count >= 2 for count in populated) >= 2
        observations.append({
            "candidate_index": index,
            "bbox": list(table.bbox),
            "rows": rows,
            "geometry_role": "multirow_multicol_grid_candidate" if repeated_cells
                             else "layout_or_sparse_grid_unresolved",
            "role_evidence": {"populated_cells_per_row": populated,
                              "at_least_two_populated_cells_in_two_rows": repeated_cells},
            "semantic_role": "unknown",
            "may_suppress_source_text": False,
            "numeric_fact_authority": False,
        })
    return {
        "schema_version": "fin_pdf_ruled_structure_candidates_v1",
        "adapter": "pdfplumber_find_tables_default_lines",
        "settings": settings,
        "edge_inventory": {"lines": len(page.lines), "rect_edges": len(page.rect_edges),
                           "curve_edges": len(page.curve_edges)},
        "candidates": observations,
        "coverage": "ruled_geometry_only_not_borderless_or_semantic_tables",
    }
