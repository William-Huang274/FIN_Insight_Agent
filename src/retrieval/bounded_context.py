from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

from .query_plan import canonical_digest


BOUNDED_CONTEXT_EXPANSION_SCHEMA_VERSION = (
    "fin_ia_bounded_candidate_context_expansion_v1_0"
)

_RELATION_PRIORITY = {
    "selected_parent_table": 0,
    "selected_table_footnote": 1,
    "selected_cross_page_continuation": 2,
    "document_revision_or_restatement": 3,
    "selected_parent_page": 4,
}


class BoundedContextError(ValueError):
    """Raised when parent/context expansion loses an explicit object edge."""


def expand_bounded_candidate_context(
    *,
    selected_object_ids: Sequence[str],
    objects_by_id: Mapping[str, Mapping[str, Any]],
    include_document_revision_context: bool,
    maximum_context_per_candidate: int = 6,
) -> dict[str, Any]:
    """Attach explicit structural context after candidate selection.

    Context objects stay candidate-only. A selected table row can carry its
    table, footnote, cross-page continuation and bounded restatement context
    without forcing support objects to compete with evidence in semantic top-k.
    """

    selected = tuple(str(value) for value in selected_object_ids)
    if (
        not selected
        or len(selected) != len(set(selected))
        or not isinstance(maximum_context_per_candidate, int)
        or maximum_context_per_candidate < 1
    ):
        raise BoundedContextError("bounded_context_selection_invalid")
    missing = [value for value in selected if value not in objects_by_id]
    if missing:
        raise BoundedContextError(f"bounded_context_object_missing:{missing[0]}")

    footnotes_by_table: dict[str, list[str]] = defaultdict(list)
    cross_page_by_endpoint: dict[str, list[str]] = defaultdict(list)
    revisions_by_document: dict[str, list[str]] = defaultdict(list)
    for object_id, row in objects_by_id.items():
        links = row.get("context_links") or {}
        if not isinstance(links, Mapping):
            raise BoundedContextError(
                f"bounded_context_links_invalid:{object_id}"
            )
        for table_id in links.get("linked_table_object_ids") or ():
            footnotes_by_table[str(table_id)].append(str(object_id))
        for endpoint in (links.get("left_object_id"), links.get("right_object_id")):
            if endpoint:
                cross_page_by_endpoint[str(endpoint)].append(str(object_id))
        if (
            str(row.get("source_evidence_type") or "")
            == "revision_or_restatement_context"
        ):
            parent = str(links.get("parent_document_id") or "")
            if parent:
                revisions_by_document[parent].append(str(object_id))

    expansions: list[dict[str, Any]] = []
    for selected_id in selected:
        row = objects_by_id[selected_id]
        links = row.get("context_links") or {}
        related: list[tuple[str, str]] = []
        parent_table = str(links.get("parent_table_object_id") or "")
        parent_page = str(links.get("parent_page_object_id") or "")
        parent_document = str(links.get("parent_document_id") or "")
        if parent_table in objects_by_id:
            related.append(("selected_parent_table", parent_table))
        related.extend(
            ("selected_table_footnote", value)
            for value in footnotes_by_table.get(parent_table, ())
            if value in objects_by_id
        )
        related.extend(
            ("selected_cross_page_continuation", value)
            for value in cross_page_by_endpoint.get(selected_id, ())
            if value in objects_by_id
        )
        if include_document_revision_context:
            related.extend(
                ("document_revision_or_restatement", value)
                for value in revisions_by_document.get(parent_document, ())
                if value in objects_by_id
            )
        if parent_page in objects_by_id:
            related.append(("selected_parent_page", parent_page))

        deduplicated: list[tuple[str, str]] = []
        seen: set[str] = set()
        for relation, context_id in sorted(
            related,
            key=lambda value: (_RELATION_PRIORITY[value[0]], value[1]),
        ):
            if context_id == selected_id or context_id in seen:
                continue
            seen.add(context_id)
            deduplicated.append((relation, context_id))
        for relation, context_id in deduplicated[:maximum_context_per_candidate]:
            context = objects_by_id[context_id]
            expansions.append(
                {
                    "selected_compiled_object_id": selected_id,
                    "context_compiled_object_id": context_id,
                    "relation_type": relation,
                    "context_object_kind": context.get("object_kind"),
                    "source_evidence_type": context.get("source_evidence_type"),
                    "candidate_not_evidence": True,
                    "numeric_authority": False,
                    "evidence_promotion_authorized": False,
                }
            )

    body = {
        "schema_version": BOUNDED_CONTEXT_EXPANSION_SCHEMA_VERSION,
        "status": "bounded_structural_context_compiled",
        "selected_object_ids": list(selected),
        "expansions": expansions,
        "expanded_context_object_ids": list(
            dict.fromkeys(row["context_compiled_object_id"] for row in expansions)
        ),
        "authority": {
            "selection_precedes_context_expansion": True,
            "explicit_object_edges_only": True,
            "context_is_not_independent_evidence": True,
            "numeric_authority": False,
            "runtime_evidence_promotion_authorized": False,
        },
    }
    return {**body, "expansion_digest": canonical_digest(body)}


__all__ = [
    "BOUNDED_CONTEXT_EXPANSION_SCHEMA_VERSION",
    "BoundedContextError",
    "expand_bounded_candidate_context",
]
