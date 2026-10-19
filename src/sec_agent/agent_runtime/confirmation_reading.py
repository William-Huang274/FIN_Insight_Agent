"""Version-bound reading coverage for local confirmations, not financial approval."""
import re
import json
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, ToolMessage
from .research_graph_contracts import canonical_sha256
from .review_inspection import read_location, read_structured_location, text_locations


def section_ranges(text, spans):
    """Keep complete Markdown sections (including tables/notes), plus preamble.

    Diff characters locate sections; they are not sufficient reading context.
    Unstructured prose stays one field. The reviewer may read beyond this floor.
    """
    headings = [m.start() for m in re.finditer(r'(?m)^#{1,6} +', text)]
    edges = sorted(set([0, *headings, len(text)]))
    selected = set()
    for span in spans:
        a, b = span['after']
        if not 0 <= a <= b <= len(text):
            raise ValueError('invalid_current_change_span')
        for left, right in zip(edges, edges[1:]):
            if (left < b and right > a) or (a == b and left <= a <= right):
                selected.add((left, right))
    if selected and headings:
        # Document-level period/unit qualifiers commonly precede subsections.
        first_subsection = next((m.start() for m in re.finditer(r'(?m)^#{2,6} +', text)), len(text))
        selected.add((0, first_subsection))
    merged = []
    for a, b in sorted(selected):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(b, merged[-1][1])
        else:
            merged.append([a, b])
    return merged


def reading_targets(artifacts, confirmation, pid):
    paper = artifacts.read_paper(pid)
    digest = canonical_sha256(paper)
    change = confirmation.get('changes', {}).get(pid)
    if not change or change.get('current_digest') != digest:
        return None  # Old handoffs without reliable change records keep full-read protection.
    fields = dict(text_locations(paper))
    targets, objects = {}, {}
    for row in change.get('locations', []):
        path = row['path']
        if path not in fields:
            try:
                grouped = read_structured_location(artifacts, pid, path)
            except ValueError:
                return None
            objects[path] = [[0, grouped['total_characters']]]
            continue
        leaves = [(p, t) for p, t in fields.items() if p == path or p.startswith(path + '/')]
        for p, text in leaves:
            ranges = section_ranges(text, row['spans']) if p == path and row.get('spans') else [[0, len(text)]]
            targets.setdefault(p, []).extend(ranges)
        if not leaves:
            return None  # Removed structured fields require seeing their current surrounding object.
    claims = {c['claim_id']: c for c in paper.get('claims', [])}
    ids = set(change.get('changed_claim_ids', []))
    for finding in confirmation.get('findings_to_confirm', {}).get(pid, []):
        ids.update(finding.get('claim_ids', []))
        quote = finding.get('problematic_quote', '')
        # If the old offending words remain, also read their current context.
        if quote:
            for path, text in fields.items():
                if path.startswith('/claims/'):
                    continue
                matches = list(re.finditer(re.escape(quote), text))
                if matches:
                    targets.setdefault(path, []).extend(section_ranges(text,
                        [{'after': [m.start(), m.end()]} for m in matches]))
    if not ids.issubset(claims) or not (targets or objects or ids):
        return None
    return {'paper_id': pid, 'paper_digest': digest, 'fields': targets, 'objects': objects, 'claim_ids': sorted(ids)}


def missing_reads(artifacts, confirmation, pid, messages):
    target = reading_targets(artifacts, confirmation, pid)
    if target is None:
        return None
    spans, claims = {}, set()
    expected_claims = {c['claim_id']: c for c in artifacts.read_paper(pid, 'claims')}
    for m in messages:
        if not isinstance(m, ToolMessage) or m.status != 'success' or not isinstance(m.artifact, dict):
            continue
        v = m.artifact
        if v.get('paper_id') != pid:
            continue
        if m.name == 'read_review_location' and v.get('paper_digest') == target['paper_digest'] and v.get('text'):
            try:
                reader = read_structured_location if v.get('view') == 'json' else read_location
                exact = reader(artifacts, pid, v['field_path'], v['offset'], len(v['text']))
            except (ValueError, KeyError):
                continue
            if v == exact:
                spans.setdefault((v['field_path'], v.get('view', 'text')), []).append((v['offset'], v['offset'] + len(v['text'])))
        if m.name == 'read_research_artifact' and v.get('section') == 'claims':
            for claim in v.get('content', []):
                cid = claim.get('claim_id')
                if cid in expected_claims and claim == expected_claims[cid]:
                    claims.add(cid)  # Unchanged claim contents remain reusable, even across paper revisions.
    missing = []
    for path, ranges in {**target['fields'], **target['objects']}.items():
        view = 'json' if path in target['objects'] else 'text'
        for a, b in ranges:
            cursor = a
            for left, right in sorted(spans.get((path, view), [])):
                if left <= cursor:
                    cursor = max(cursor, right)
            if cursor < b:
                missing.append({'tool': 'read_review_location', 'arguments': {'paper_id': pid,
                    'field_path': path, 'offset': cursor, 'max_characters': min(6000, b - cursor)},
                    'required_end': b})
                if view == 'json':
                    missing[-1]['arguments']['view'] = 'json'
    ids = sorted(set(target['claim_ids']) - claims)
    if ids:
        missing.append({'tool': 'read_research_artifact', 'arguments': {'paper_id': pid,
            'section': 'claims', 'claim_ids': ids}})
    return missing


def with_reading_targets(artifacts, confirmation, messages=()):
    """Replace legacy full-field guidance in the view; original stored handoff stays intact."""
    from copy import deepcopy
    value = deepcopy(confirmation)
    if value:
        value['current_reading_targets'] = {}
        for pid in value['findings_to_confirm']:
            targets = missing_reads(artifacts, value, pid, messages)
            value['current_reading_targets'][pid] = targets if targets is not None else [
                {'tool': 'read_research_artifact', 'arguments': {'paper_id': pid, 'section': 'workpaper'},
                 'reason': 'Version-bound local change coverage unavailable; read current paper.'}]
        for change in value.get('changes', {}).values():
            change['notice'] = ('Version-bound change locations, not proof of resolution. Read current_reading_targets '
                'and any necessary related explanations or source/calculation context; unchanged research is reusable.')
    return value


def finding_was_read(artifacts, messages, finding):
    """A partial saved finding needs its own current text, not every repair read."""
    pid, quote = finding.paper_id, finding.problematic_quote
    current = {c['claim_id']: c for c in artifacts.read_paper(pid, 'claims')}
    for m in messages:
        if not isinstance(m, ToolMessage) or m.status != 'success' or not isinstance(m.artifact, dict):
            continue
        v = m.artifact
        if v.get('paper_id') != pid:
            continue
        if m.name == 'read_review_location' and v.get('location_id'):
            from .review_inspection import bind_location
            try:
                if quote in bind_location(artifacts, [m], pid, v['location_id']):
                    return True
            except ValueError:
                continue
        if m.name == 'read_research_artifact' and v.get('section') == 'claims':
            for claim in v.get('content', []):
                if claim == current.get(claim.get('claim_id')) and any(quote in text for _, text in text_locations(claim)):
                    return True
    return False


class ReviewReadingContext(AgentMiddleware):
    """Refresh only runtime-owned handoff views; preserve the original journal."""
    def __init__(self, artifacts, confirmation=None):
        self.artifacts, self.confirmation = artifacts, confirmation

    def project(self, request):
        messages = []
        for message in request.messages:
            if isinstance(message, HumanMessage) and isinstance(message.content, str):
                try:
                    value = json.loads(message.content)
                except ValueError:
                    value = None
                if isinstance(value, dict):
                    if value.get('origin') == 'runtime_model_call_allowance':
                        continue
                    if self.confirmation and 'revision_confirmation' in value:
                        value['revision_confirmation'] = with_reading_targets(
                            self.artifacts, self.confirmation, request.state.get('messages', request.messages))
                        message = message.model_copy(update={'content': json.dumps(value, ensure_ascii=False)})
            messages.append(message)
        return request.override(messages=messages)

    def wrap_model_call(self, request, handler):
        return handler(self.project(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self.project(request))
