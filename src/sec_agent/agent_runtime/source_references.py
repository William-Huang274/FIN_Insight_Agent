"""Short display references derived from exact, already observed source identities.

No counters, model-selected registrations or separate evidence store. Handles
survive restart/fork and are resolved only against the current task's receipts.
"""
from copy import deepcopy
from hashlib import sha256
import re

from .conversation_handoff import observed_sources

HANDLE = re.compile(r"\bREF-[0-9a-f]{16}\b")
REFERENCE_TOKEN = r'(?:REF-[0-9a-f]{16}|(?:PASSAGE|CALC|NUMFACT)::[A-Za-z0-9_:.\-…]+)'


def reference_handle(source_id):
    return 'REF-' + sha256(source_id.encode('utf-8')).hexdigest()[:16]


def reference_sources(state):
    rows = [m.model_dump(mode='json') if hasattr(m, 'model_dump') else m
            for m in state.get('messages', [])]
    sources = observed_sources({'values': {'messages': rows}})
    handles = {}
    for key in sources:
        handle = reference_handle(key)
        if handle in handles and handles[handle] != key:
            raise ValueError('source_reference_collision')
        handles[handle] = key
    return sources, handles


def resolve_reference(value, sources, handles):
    if value in sources:
        return value
    if value in handles:
        return handles[value]
    # Legacy author abbreviations are accepted only when the entire pattern
    # uniquely matches an observed identity, never by title or semantic similarity.
    if value.startswith(('PASSAGE::', 'CALC::', 'NUMFACT::')) and ('…' in value or '...' in value):
        parts = re.split(r'(?:…|\.{3})+', value)
        if sum(len(p) for p in parts[1:]) >= 12:
            pattern = '.*'.join(re.escape(p) for p in parts)
            matches = [key for key in sources if re.fullmatch(pattern, key)]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise ValueError('ambiguous_source_reference:' + value + '; candidates=' + ','.join(matches))
    elif value.startswith(('PASSAGE::', 'CALC::', 'NUMFACT::')) and len(value.split('::', 1)[1]) >= 16:
        matches = [key for key in sources if key.startswith(value)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError('ambiguous_source_reference:' + value + '; candidates=' + ','.join(matches))
    if HANDLE.fullmatch(value):
        raise ValueError('unobserved_source_reference:' + value)
    return value


def expand_references(value, state):
    """Normalize IDs and bracketed citations only, never financial prose."""
    sources, handles = reference_sources(state)
    def visit(obj, key=''):
        if isinstance(obj, dict):
            return {k: visit(v, k) for k, v in obj.items()}
        if isinstance(obj, list):
            return [visit(v, key) for v in obj]
        if not isinstance(obj, str):
            return obj
        if key in {'source_id', 'passage_id', 'calculation_id', 'source_ids', 'citation_ids'}:
            return resolve_reference(obj, sources, handles)
        return re.sub(REFERENCE_TOKEN, lambda m: resolve_reference(m[0], sources, handles), obj)
    return visit(value)


def present_references(value):
    """Add handles only to read evidence/calculations, never retrieval candidates."""
    if isinstance(value, list):
        return [present_references(x) for x in value]
    if not isinstance(value, dict):
        return value
    result = {k: present_references(v) for k, v in value.items()}
    kind = value.get('result_state')
    key = value.get('passage_id') if kind == 'source_bound_passage' and value.get('writer_citable') is True else (
        value.get('calculation_id') if kind == 'non_authoritative_metric' else (
            value.get('numeric_fact_id') if kind == 'numeric_fact' and value.get('numeric_fact_authority') is True else None))
    if key:
        result = {'citation_handle': reference_handle(key), **result}
    return result


def render_answer_references(text, state):
    """Keep the native original; return a reader-facing projection and bindings."""
    sources, handles = reference_sources(state)
    bindings, unresolved = {}, []
    def replace(match):
        key = match[1]
        try:
            source_id = resolve_reference(key, sources, handles)
        except ValueError as exc:
            unresolved.append(str(exc)); return match[0]
        if source_id not in sources:
            unresolved.append(key); return match[0]
        source = sources[source_id]
        handle = reference_handle(source_id)
        bindings[handle] = {'source_id': source_id, 'source': deepcopy(source)}
        url = source.get('source_url')
        if isinstance(url, str) and url.startswith(('https://', 'http://')):
            return '[' + handle + '](' + url.replace(' ', '%20').replace(')', '%29') + ')'
        return '[' + handle + ']'
    rendered = re.sub(r'\[?(' + REFERENCE_TOKEN + r')\]?', replace, text)
    return rendered, bindings, unresolved
