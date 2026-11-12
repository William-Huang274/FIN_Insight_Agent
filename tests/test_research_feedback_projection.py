from copy import deepcopy
import json

from langchain_core.messages import ToolMessage
from sec_agent.agent_runtime.harness_business_tools import model_receipt
from sec_agent.agent_runtime.research_disposition_binding import disposition_scope, scope_unchanged


def test_feedback_preserves_every_finding_with_exact_canonical_pointer():
    check = {'coverage': {'changed_sentences': 2}, 'findings': [
        {'kind': 'mismatch', 'sentence': 'Claim A', 'action': 'Check numerator',
         'basis': {'original': 'long original ' * 3000}},
        {'kind': 'scope', 'sentence': 'Claim B', 'expected': 'USD', 'actual': '%'}],
        'linked_ratio_bases': [{'original': 'x' * 20000}], 'cited_claim_context': []}
    body = {'saved': True, 'quantitative_change_check': check}
    msg = ToolMessage(content=json.dumps(body), tool_call_id='note-receipt', name='WriteWorkingNote')
    before = deepcopy(msg)
    view = model_receipt(msg)
    feedback = view['result']['quantitative_change_check']
    assert msg == before
    assert len(feedback['findings']) == 2
    assert feedback['findings'][0]['sentence'] == 'Claim A'
    assert feedback['findings'][0]['details_readback']['arguments'] == {
        'tool_call_id': 'note-receipt', 'json_pointer': '/quantitative_change_check/findings/0'}
    assert feedback['context_counts']['linked_ratio_bases'] == 1
    assert len(json.dumps(view)) < len(msg.content) / 10
    assert view['original_readback']['arguments']['tool_call_id'] == 'note-receipt'


def test_disposition_survives_unrelated_section_but_not_bound_changes():
    report = {'title': 'Position', 'narrative_markdown':
        'Introduction\n# Summary\nSummary remains.\n# A\nBound relation [REF-test].\n'
        '# B\nOther topic.\n# Conclusion\nConditional conclusion.', 'citations': {}, 'charts': []}
    response = {'current_quote': 'Bound relation',
                'disposition_scope': disposition_scope(report, 'Bound relation')}
    changed = deepcopy(report)
    changed['narrative_markdown'] = changed['narrative_markdown'].replace('Other topic.', 'Other topic expanded.')
    assert scope_unchanged(changed, response)
    for field, old, new in [('title', 'Position', 'Stronger position'),
                          ('narrative_markdown', 'Summary remains.', 'New summary.'),
                          ('narrative_markdown', 'Conditional conclusion.', 'Unconditional conclusion.'),
                          ('narrative_markdown', 'Bound relation', 'Different relation')]:
        changed = deepcopy(report)
        changed[field] = changed[field].replace(old, new)
        assert not scope_unchanged(changed, response)
    changed = deepcopy(report)
    changed['charts'] = [{'interpretation': 'New claim'}]
    assert not scope_unchanged(changed, response)
    assert not scope_unchanged(report, {'current_quote': 'Bound relation'})


def test_ambiguous_quote_binds_all_occurrences_and_adjacent_claims():
    report = {'narrative_markdown': '# Intro\nIntro\n# A\nSame claim.\n# B\nSame claim.\n# End\nEnd'}
    response = {'current_quote': 'Same claim.', 'disposition_scope': disposition_scope(report, 'Same claim.')}
    changed = {**report, 'narrative_markdown': report['narrative_markdown'].replace('# B\nSame claim.', '# B\nSame claim. Yet its premise changes.')}
    assert not scope_unchanged(changed, response)
