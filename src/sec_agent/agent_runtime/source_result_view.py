"""Model-facing source cards; full parser/transport records stay in observations.

Normalize only structured source results. Never parse prose, truncate evidence,
limit candidates, or infer that two different periods/revisions are equivalent.
"""
import json
from collections.abc import Mapping


_SOURCE_STATES = {"retrieval_candidate", "source_bound_passage"}
_TRANSPORT_KEYS = {"mcp_receipt_chain", "mcp_receipt", "cell_binding_used", "source_tool_lane_receipt_id"}
# Implementation names are not source coverage. Keep revision explanations,
# acquisition URLs, parsing limitations, dates, hashes and unknown metadata.
_PARSER_IMPLEMENTATION_KEYS = {"parser", "material_card_version"}


def _company_source_menu(row):
    """A known company sources section is a file menu, not a company profile.

    Keep all records and financial/source identity. Detailed profile remains
    available through company navigation, documents through outline/read.
    """
    if row.get('company_section') != 'sources' or not isinstance(row.get('sources'), list):
        return row
    menu = {k: v for k, v in row.items() if k not in {
        'card', 'profile', 'listing', 'data_counts', 'positions_count',
        'financial_groups', 'data_channels', 'relationship_processing', 'section_navigation'}}
    sources = []
    for original in row['sources']:
        if not isinstance(original, dict) or not original.get('id'):
            sources.append(original)
            continue
        item = {k: v for k, v in original.items() if k not in {
            'captured_at', 'material_group_label', 'display_title', 'url',
            'link_role', 'material_group', 'categories', 'publisher_names'}}
        if original.get('publisher_names'):
            item['publisher_names'] = original['publisher_names']
        if original.get('display_title') not in (None, original.get('title')):
            item['display_title'] = original['display_title']
        meta = _metadata(item.get('metadata', {}))
        if isinstance(meta, dict):
            meta = {k: v for k, v in meta.items() if k not in {
                'captured_at', 'data_tables', 'runtime_compatibility_parse', 'window',
                'entity_id', 'research_dimension'} and not
                (k in item and item[k] == v) and not
                (k == 'origin_url' and v == original.get('url')) and not
                (k == 'publication_date' and v == item.get('published_at'))}
        if meta:
            item['metadata'] = meta
        else:
            item.pop('metadata', None)
        item['document_id'] = original['id']
        item['readback'] = {'source_space': 'library', 'operation': 'outline', 'document_id': original['id']}
        sources.append(item)
    # One identical coverage description for this menu, not 20 repeated copies.
    coverage = [s.get('metadata', {}).get('document_coverage') for s in sources
        if isinstance(s, dict) and isinstance(s.get('metadata', {}), dict)]
    if len(coverage) == len(sources) and len(sources) > 1 and coverage[0] and all(c == coverage[0] for c in coverage):
        menu['shared_document_coverage'] = coverage[0]
        for source in sources:
            source['metadata'].pop('document_coverage')
            if not source['metadata']:
                source.pop('metadata')
    menu['sources'] = sources
    menu['menu_notice'] = 'File navigation, not evidence. Shared document coverage applies to all rows when present. URLs, profile and processing details remain in original records; use document_id with outline/search/read. Counts and all returned files are preserved.'
    if row.get('entity_id'):
        menu['company_readback'] = {'operation': 'company', 'source_space': 'library', 'entity_id': row['entity_id']}
    return menu


def _metadata(value):
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            return value
        if not isinstance(decoded, dict):
            return value
        value = decoded
    if not isinstance(value, Mapping):
        return value
    row = {k: v for k, v in value.items() if k not in _PARSER_IMPLEMENTATION_KEYS | _TRANSPORT_KEYS}
    if "routing_metadata_v1" in row:
        routing = _metadata(row["routing_metadata_v1"])
        if isinstance(routing, dict):
            # Only exact copies disappear. Conflicts remain visible at their
            # original path; do not silently choose one period/identity.
            routing = {k: v for k, v in routing.items() if k not in row or row[k] != v}
        if routing != {}:
            row["routing_metadata_v1"] = routing
        else:
            row.pop("routing_metadata_v1")
    return row


def source_result_view(value):
    """Idempotent request-only projection shared by fresh and restored reads."""
    if isinstance(value, Mapping):
        row = {k: source_result_view(v) for k, v in value.items() if k not in _TRANSPORT_KEYS}
        if row.get("result_state") in _SOURCE_STATES and "metadata" in row:
            metadata = _metadata(row["metadata"])
            if isinstance(metadata, dict):
                # The public card already carries these values. URL/date
                # aliases are removed only when their values also match.
                aliases = {"origin_url": "url", "publication_date": "published_at"}
                metadata = {k: v for k, v in metadata.items()
                            if k not in row or row[k] != v}
                metadata = {k: v for k, v in metadata.items()
                            if aliases.get(k) not in row or row[aliases[k]] != v}
            if metadata != {}:
                row["metadata"] = metadata
            else:
                row.pop("metadata")
        if row.get('result_state') == 'retrieval_candidate':
            row = _company_source_menu(row)
        return row
    if isinstance(value, (list, tuple)):
        return [source_result_view(v) for v in value]
    return value


def source_message_views(messages):
    """Reproject legacy saved messages as well as freshly assembled results."""
    from langchain_core.messages import HumanMessage, ToolMessage
    result = []
    changed = False
    for message in messages:
        view = message
        if isinstance(message, (HumanMessage, ToolMessage)) and isinstance(message.content, str):
            try:
                body = json.loads(message.content)
            except (ValueError, TypeError):
                body = None
            # User prose and unknown JSON contracts are not a tool result.
            if isinstance(body, dict) and ("progress" in body or (isinstance(message, ToolMessage) and "result" in body)):
                projected = source_result_view(body)
                if projected != body:
                    view = message.model_copy(update={"content": json.dumps(projected, ensure_ascii=False, separators=(",", ":"))})
                    changed = True
        result.append(view)
    return result if changed else messages
