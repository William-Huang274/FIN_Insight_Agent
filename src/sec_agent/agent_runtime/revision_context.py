"""Locate wording shared by an opinion and a manuscript. Matches are navigation only."""
import re
import json
from math import sqrt
from difflib import SequenceMatcher

from .source_references import REFERENCE_TOKEN


def consultation_revision_context(messages, original, candidate, active_review=None, *, original_title='', candidate_title=''):
    """Actual imported review of a report or hypotheses; never an investigation verdict."""
    recent=messages[active_review.get('message_boundary', 0):] if active_review else messages
    def view(opinion):
        return revision_wording(original, candidate, opinion, original_title, candidate_title)
    for message in reversed(recent):
        if getattr(message, 'name', '') != 'read_research_agent_result' or getattr(message, 'status', '') != 'success':
            continue
        try:
            result = json.loads(message.content)
        except (ValueError, TypeError):
            continue
        if (not isinstance(result, dict) or result.get('status') != 'completed'
                or result.get('purpose') != 'review' or not isinstance(result.get('opinion'), str)):
            continue
        return {'review_receipt': message.tool_call_id, 'reviewed_report_digest': result.get('reviewed_report_digest'),
                'review_scope': 'report_version' if result.get('reviewed_report_digest') else 'delegated_research_question',
                'status': 'navigation_only_not_a_verdict',
                **view(result['opinion']),
                'review_readback': {'tool': 'read_research_agent_result', 'arguments': {'task_id': result['task_id']}},
                'meaning': 'Exact current wording beside the actual review; matches may be unrelated. A review of hypotheses is not review of this manuscript. Author decides whether the reasoning is consistent. Saved is not reviewed.'}
    if active_review:
        return {'reviewed_report_digest':active_review['reviewed_report_digest'],
                'reviewer':active_review['reviewer'],'review_scope':'report_version',
                'status':'navigation_only_not_a_verdict',
                **view(active_review['opinion']),
                'review_readback':{'tool':'read_current_report','arguments':{'field':'review'}},
                'meaning':'Current report wording beside the actual version-bound review. Matches are navigation, not a consistency verdict; saving is not review approval.'}
    return None


def revision_wording(original, candidate, opinion, original_title='', candidate_title=''):
    """Exact changes and possible restatements, not a semantic pass/fail decision."""
    before, after = original.splitlines(keepends=True), candidate.splitlines(keepends=True)
    old_offsets, new_offsets = [0], [0]
    for line in before: old_offsets.append(old_offsets[-1] + len(line))
    for line in after: new_offsets.append(new_offsets[-1] + len(line))
    changes = []
    for tag, a, b, c, d in SequenceMatcher(None, before, after, autojunk=False).get_opcodes():
        if tag == 'equal': continue
        old, new = ''.join(before[a:b]), ''.join(after[c:d])
        changes.append({'kind':tag, 'before_offset':old_offsets[a], 'after_offset':new_offsets[c],
            'before':old[:400], 'after':new[:400], 'before_characters':len(old), 'after_characters':len(new),
            'excerpt_only':len(old)>400 or len(new)>400,
            'readback':{'tool':'read_current_report','arguments':{'offset':new_offsets[c], 'max_characters':3000}}})
    related=related_wording(original,candidate,opinion)
    for row in related:
        terms=_terms(row['opinion_excerpt'])
        row['possible_change_indices']=[i for i,change in enumerate(changes[:8])
            if len(terms & _terms(change['before']+' '+change['after']))>=4]
    result={'related_wording':related,
            'delivery_anchors':delivery_anchors(candidate),
            'changes':changes[:8], 'total_changes':len(changes), 'omitted_changes':max(0,len(changes)-8)}
    if candidate_title:
        result['title']={'before':original_title,'current':candidate_title,'changed':original_title!=candidate_title,
            'readback':{'tool':'read_current_report','arguments':{'field':'title'}}}
    return result


def delivery_anchors(text):
    """Always expose the current structure, even when lexical matching finds nothing."""
    headings=[{'offset':m.start(),'text':m[0][:180]} for m in re.finditer(r'(?m)^#{1,6} .+$',text)]
    paragraphs=[m for m in re.finditer(r'(?m)^[^\r\n]+',text)
                if not m[0].lstrip().startswith('#')]
    edges=[]
    for label,match in ([('opening',paragraphs[0]),('closing',paragraphs[-1])] if paragraphs else []):
        edges.append({'position':label,'offset':match.start(),'text':match[0][:500],
            'readback':{'tool':'read_current_report','arguments':{'offset':match.start(),'max_characters':3000}}})
    return {'headings':headings[:40],'omitted_headings':max(0,len(headings)-40),'opening_and_closing':edges,
        'meaning':'Structural navigation, not semantic matches to the opinion. Offsets refer to the current version.'}


def current_revision_view(state):
    """Reconstruct navigation from canonical save receipts, not another manuscript copy."""
    report=state.get('report') or {}
    review=state.get('active_report_review')
    messages=state.get('messages',[])
    context=consultation_revision_context(messages,report.get('narrative_markdown',''),
        report.get('narrative_markdown',''),review,
        original_title=report.get('title',''),candidate_title=report.get('title',''))
    if not context: return {'found':False,'reason':'no_active_independent_review'}
    batches=[]
    for msg in messages[review.get('message_boundary',0) if review else 0:]:
        if getattr(msg,'name','') not in {'save_research_report','edit_research_report','repair_report_fields'}:
            continue
        if getattr(msg,'status','')!='success': continue
        try: saved=json.loads(msg.content)
        except (ValueError,TypeError): continue
        if not isinstance(saved,dict): continue
        prior=saved.get('revision_context') or {}
        if not saved.get('saved') or prior.get('reviewed_report_digest')!=context.get('reviewed_report_digest'):
            continue
        if prior.get('review_receipt')!=context.get('review_receipt'): continue
        batches.append({'receipt_id':msg.tool_call_id,'report_version':saved.get('report_version'),
            'digest':saved.get('digest'),'changes':prior.get('changes',[]),'title':prior.get('title'),
            'omitted_changes':prior.get('omitted_changes',0)})
    for row in context['related_wording']:
        terms=_terms(row['opinion_excerpt'])
        row['possible_saved_changes']=[{'receipt_id':b['receipt_id'],'report_version':b['report_version'],'change_index':i}
            for b in batches for i,c in enumerate(b['changes'])
            if len(terms & _terms(c.get('before','')+' '+c.get('after','')))>=4]
    return {'found':True, **context, 'report_version':state.get('report_version',0),
        'source_acquisition_readback':{'tool':'browse_context','arguments':{'region':'acquisition'}},
        'saved_batches':batches, 'meaning':'Saved changes are historical batches, not necessarily current wording. Current related excerpts include unchanged headings and conclusions. No semantic acceptance or mandatory rewrite is inferred.'}


def _terms(text):
    words = re.findall(r'[a-z][a-z0-9-]+|[\u3400-\u9fff]+', re.sub(REFERENCE_TOKEN, '', text).lower())
    return {term for word in words for term in
            ([word] if word.isascii() else [word[i:i+2] for i in range(len(word)-1)])}


def related_wording(original, candidate, opinion):
    """Select bounded exact excerpts; keep closing restatements eligible even when untouched."""
    lines = [(s.strip(), _terms(s)) for s in opinion.splitlines()
             if len(s.strip()) >= 16 and not s.lstrip().startswith(('#', 'PASSAGE', '`PASSAGE'))]
    matches = []
    headings = [(m.start(), m[0]) for m in re.finditer(r'(?m)^#{1,6} .+$', candidate)]
    for match in re.finditer(r'[^。！？!?\n]+[。！？!?]?', candidate):
        sentence = match[0].strip()
        if not lines or len(sentence) < (4 if sentence.startswith('#') else 12):
            continue
        terms = _terms(sentence)
        best = max(((len(terms & other) / sqrt(max(1,len(terms)*len(other))), line)
                    for line, other in lines if len(terms & other) >= 4), default=(0, ''))
        if best[0] >= 0.15:
            start = match.start() + match[0].index(sentence)
            matches.append((best[0], {'offset':start, 'excerpt':sentence[:500],
                'section': next((title for offset, title in reversed(headings) if offset <= start), ''),
                'kind':'heading' if sentence.startswith('#') else 'prose',
                'verbatim_in_base':sentence in original, 'opinion_excerpt':best[1][:500],
                'readback':{'tool':'read_current_report','arguments':{'offset':start,'max_characters':1500}}}))
    # Cover distinct argument sections before filling by similarity. Otherwise
    # repeated legal terms can crowd out a later investment restatement.
    ranked = sorted(matches, key=lambda pair:-pair[0])
    sections = {}
    for pair in ranked:
        sections.setdefault(pair[1]['section'], pair)
    # Headings compete poorly with long paragraphs. Reserve navigation slots for
    # actual lexical matches, without calling an unmatched heading contradictory.
    selected = [p for p in ranked if p[1]['kind']=='heading'][:2]
    selected += [p for p in list(sections.values()) if p not in selected][:max(0,9-len(selected))]
    offsets = {p[1]['offset'] for p in selected}
    selected += [p for p in ranked if p[1]['offset'] not in offsets][:max(0, 11-len(selected))]
    selected += matches[-1:]
    if matches:
        last = matches[-1][1]
        offset = last['offset']
        start = max(candidate.rfind('\n', 0, offset) + 1, offset - 450)
        stop = candidate.find('\n', offset)
        last['paragraph_window'] = candidate[start:min(len(candidate) if stop == -1 else stop, offset + 500)]
    return [v for _,v in sorted({row['offset']:row for _,row in selected}.items())]
