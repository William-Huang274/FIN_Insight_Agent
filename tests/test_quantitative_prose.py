from sec_agent.agent_runtime.quantitative_prose import audit_changes


def ratio(benefit, denominator, label):
    return dict(calculation_id='CALC::'+label, result_state='non_authoritative_metric', arithmetic_verified=True,
                result_unit='ratio', value_decimal=str(benefit/denominator), expression='benefit / change',
                rationale=label, operands={'benefit':{'quote':f'benefit of $ {benefit} million','literal':str(benefit)},
                                           'change':{'literal':str(denominator)}})


def test_changed_arithmetic_scope_and_counterfactual():
    sources={'CALC::revenue':ratio(6,50,'revenue'),'CALC::earnings':ratio(4,25,'earnings')}
    old='历史：保持既有范围。'
    scope='XYZ 分部单独分配未知。'
    shared='6 million 占收入变化的12%、净利润变化的16%。'
    adjust='XYZ利润率（剔除6 million）。'
    report=audit_changes(old,scope+shared+adjust,sources)
    assert [f['kind'] for f in report['findings']]==['different_numerators','allocation_basis_needed']
    assert len(report['linked_ratio_bases'])==2
    assert {float(r['result_percent']) for r in report['linked_ratio_bases']} == {12,16}
    from sec_agent.agent_runtime.quantitative_prose import amounts
    assert amounts('3.2bn约为') == amounts('32 亿美元')
    correct=scope+'6 million 占收入变化的12%，4 million 占净利润变化的16%。假设全部分配给XYZ，剔除6 million测算利润率。'
    assert not audit_changes(old,correct,sources)['findings']
    assert not audit_changes(shared,shared,sources)['findings']
    assert not audit_changes(old,shared,{},context=scope)['findings']


def test_adjustment_compares_only_explicit_periods_and_respects_scenario():
    source = ratio(6,50,'FY2022 consolidated benefit')
    sources = {'CALC::period':source}
    result = audit_changes('', '2024年剔除6 million 后的收入。', sources)
    assert [f['kind'] for f in result['findings']] == ['check_period_of_adjustment']
    assert not audit_changes('', '如果2024年仍有同额收益，则剔除6 million。', sources)['findings']

def test_changed_qualitative_claim_gets_actual_evidence_and_old_limit():
    from sec_agent.agent_runtime.source_references import reference_handle

    key = 'PASSAGE::approved'
    ref = reference_handle(key)
    before = f'过去未提供分项。[{ref}]'
    after = f'附注明确给出分项，故可确认归属。[{ref}]'
    source = {key:dict(result_state='source_bound_passage', writer_citable=True, passage='Allocation to unit X: 18.')}
    result = audit_changes(before, after, source)
    row, = result['cited_claim_context']
    assert row['evidence'][0]['excerpt'] == 'Allocation to unit X: 18.'
    assert len(row['earlier_statements']) == 1
    assert not result['findings']
    assert not audit_changes(after, after, source)['cited_claim_context']
    assert not audit_changes(before, after, {})['cited_claim_context']


def test_ratio_feedback_uses_only_the_cited_verified_denominator():
    from sec_agent.agent_runtime.source_references import reference_handle

    key = 'CALC::verified'
    ref = reference_handle(key)
    for offset in (47, 70):
        calc = ratio(offset, 100, 'offset divided by combined increases')
        row, = audit_changes('', f'抵消了其中一部分。[{ref}]', {key:calc})['cited_claim_context']
        evidence, = row['evidence']
        assert float(evidence['percent_of_specified_denominator']) == offset
        assert evidence['expression'] == calc['expression']
        assert evidence['readback']['arguments']['source_id'] == key

def test_only_accepted_current_note_versions_supply_prior_wording():
    import json
    from langchain_core.messages import AIMessage, ToolMessage
    from sec_agent.agent_runtime.quantitative_prose import saved_note_wording

    def pair(version, mode, text, saved):
        key = 'note-call-' + text
        return [
            AIMessage(content='', tool_calls=[dict(name='WriteWorkingNote', args=dict(
                mode=mode, title='x', body=text), id=key, type='tool_call')]),
            ToolMessage(name='WriteWorkingNote', tool_call_id=key, content=json.dumps(
                dict(saved=saved, note_id='one', version=version)))]

    rows = pair(1,'replace','first',True) + pair(2,'append','conditional',True)
    assert saved_note_wording(rows) == 'first\nconditional'
    rows += pair(3,'replace','rejected',False)
    assert saved_note_wording(rows) == 'first\nconditional'
    rows += pair(3,'replace','new evidence',True)
    assert saved_note_wording(rows) == 'new evidence'

def test_legacy_source_id_and_handle_share_one_evidence_entry_in_change_view():
    from sec_agent.agent_runtime.source_references import reference_handle

    key = 'PASSAGE::abc123'
    ref = reference_handle(key)
    source = {key:dict(result_state='source_bound_passage', writer_citable=True, passage='current record')}
    new = f'归属已明确。[{ref}]\n因此可以确认具体分项。[{ref}]'
    rows = audit_changes('', new, source, earlier_notes=f'该项曾待核对。[{key}]')['cited_claim_context']
    assert len(rows) == 2
    assert rows[0]['evidence'][0]['excerpt'] == 'current record'
    assert rows[1]['evidence'] == [{'receipt':ref}]
    assert rows[1]['earlier_statements'] and len(rows[1]['earlier_statements']) == 1
def test_growth_spread_definition_without_any_numeric_literal():
    from sec_agent.agent_runtime.quantitative_prose import audit_changes
    text = '跟踪单位收入增速减去单位成本增速（RASM − CASM-ex）。'
    finding, = audit_changes('', text, {})['findings']
    assert finding['operands'] == ['RASM', 'CASM-ex']
    assert not audit_changes(text, text, {})['findings']
    for valid in ('单位收入减单位成本（RASM − CASM）。',
                  '销售增长率减成本增长率（SalesYoY − CostsYoY）。',
                  '单位收入增速减去单位成本增速（同比(RASM) − 同比(CASM-ex)）。'):
        assert not audit_changes('', valid, {})['findings']


def test_metric_name_requires_a_bound_matching_amount():
    from sec_agent.agent_runtime.quantitative_prose import bound_claim_checks
    handle = 'REF-' + 'a'*16
    def checks(label, unit='cents per unit', value='8.36'):
        line = label + '[' + handle + ']'
        return bound_claim_checks(line, {line}, {handle:{'arithmetic_verified':True,
            'expression':'r-c','result_unit':unit,'value_decimal':value}})
    assert checks('利润率为8.36美分/件')[0]['kind'] == 'verify_metric_name'
    assert not checks('单位差额为8.36美分/件')
    assert not checks('差额为8.36美分/件，利润率承压')
    assert not checks('利润率为37.2%，分母为单位收入', 'percent','37.2')
    assert not checks('利润率为8.36美分/件',value='9.00')


def test_group_comparison_returns_disclosures_without_inventing_a_verdict():
    from sec_agent.agent_runtime.quantitative_prose import bound_claim_checks
    handles = ['REF-' + ch*16 for ch in 'abc']
    summary = '三家方向一致。'
    for homogeneous in (False, True):
        sources, lines = {}, []
        for i,key in enumerate(handles):
            comparable = homogeneous or i < 2
            src = {'entity':str(i),'writer_citable':True,'passage':'original',
                   'metric':'营业利润' if comparable else '单位收入',
                   'disclosure_type':'实绩' if comparable else '指引',
                   'publication_date':'2026-07-15'}
            if comparable:
                src['period'] = 'Q2'
            sources[key] = src
            lines.append(str(i)+src['metric']+'增长['+key+']。')
        group, = bound_claim_checks('\n'.join([*lines,summary]), {summary}, sources)
        entries = group['cited_observations']
        assert [r['receipt'] for r in entries] == handles
        assert entries[-1]['metric'] == sources[handles[-1]]['metric']
        assert entries[-1].get('period') == ('Q2' if homogeneous else None)
        assert {r['disclosure_type'] for r in entries} == ({'实绩'} if homogeneous else {'实绩','指引'})
        assert 'verdict' not in group
