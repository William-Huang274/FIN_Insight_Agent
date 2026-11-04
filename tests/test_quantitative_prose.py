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
