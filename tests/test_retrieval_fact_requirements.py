from copy import deepcopy
from hashlib import sha256
import pytest
from scripts.engineering.retrieval_fact_requirements import review_requirements, score_requirements


def fixture():
    bodies = {'text': 'December 31, 2025 Cash 23.4 million USD.',
              'table': 'December 31, 2025 (Amounts in thousands) Cash | 23,421',
              'coarse': 'December 31, 2025 Cash 23 million USD.'}
    originals = {n: {'source_id': 's', 'source_digest': 'v1', 'body': b} for n,b in bodies.items()}
    context = dict(source_id='s',source_digest='v1',entity='Example',period='2025-12-31',measure='cash')
    def alternative(node, value, scale, resolution, unit):
        return dict(context=context,reviewer='fixture',review='original_scope_units_and_precision_checked',
                    citations=[dict(node_id=node,body_sha256=sha256(bodies[node].encode()).hexdigest(),quote=bodies[node])],
                    quantity=dict(value=value,scale=scale,resolution=resolution,currency='USD',unit_quote=unit))
    contract={'schema':'reviewed-fact-requirements.v1','requirements':[
        dict(id='cash',context=context,quantity=dict(value='23.4',scale='millions',resolution='0.1',currency='USD'),
             alternatives=[alternative('text','23.4','millions','0.1','million USD'),
                           alternative('table','23,421','thousands','1','Amounts in thousands'),
                           alternative('coarse','23','millions','1','million USD')])]}
    return contract, originals


def test_same_version_unit_conversion_and_precision_are_separate():
    contract, originals=fixture()
    validated=review_requirements(contract,originals)
    assert score_requirements(['table'],validated)['all_complete']
    assert score_requirements(['coarse'],validated)['requirements'][0]['status']=='precision_insufficient'
    assert score_requirements([],validated)['requirements'][0]['status']=='missing'


def test_typed_fact_period_requires_own_citation_not_filing_date():
    contract, originals = fixture()
    contract['schema']='reviewed-fact-requirements.v2'
    requirement=contract['requirements'][0]
    requirement['context'].update(disclosure_period='2025-12-31',
        period={'kind':'instant','role':'balance_as_of','value':'2025-12-31'})
    with pytest.raises(ValueError,match='period_original_citations'):review_requirements(contract, originals)
    for a in requirement['alternatives']:
        a['period_citations']=[{'node_id':a['citations'][0]['node_id'],'quote':'December 31, 2025'}]
    assert review_requirements(contract, originals)
    requirement['alternatives'][0]['period_citations'][0]['quote']='September 30, 2025'
    with pytest.raises(ValueError,match='period_quote'):review_requirements(contract, originals)


@pytest.mark.parametrize('period',[
    '2025-12-31', {'kind':'instant','role':'expiration','value':'2025-12-31'},
    {'kind':'instant','role':'balance_as_of','value':'2025-02-30'},
    {'kind':'duration','role':'flow_during_period','start':'2025-12-31','end':'2025-01-01'},
    {'kind':'fiscal_year','role':'flow_during_period','value':'2025-09-26'},
    {'kind':'unknown','role':'unresolved','reason':''}])
def test_typed_fact_period_rejects_ambiguous_or_invalid_forms(period):
    from scripts.engineering.retrieval_fact_requirements import validate_period
    with pytest.raises(ValueError):validate_period(period)


@pytest.mark.parametrize('field,value',[('period','2024-12-31'),('entity','Other'),
    ('source_digest','v2'),('measure','restricted_cash')])
def test_other_period_owner_measure_or_revision_not_equivalent(field,value):
    contract,originals=fixture()
    contract=deepcopy(contract)
    contract['requirements'][0]['alternatives'][1]['context']=dict(contract['requirements'][0]['context'],**{field:value})
    with pytest.raises(ValueError,match='mismatch'):review_requirements(contract,originals)


def test_quotes_currency_and_source_binding_fail_closed():
    for mutate in (lambda a:a['quantity'].update(currency='EUR'),
                   lambda a:a['quantity'].update(value='999'),
                   lambda a:a['quantity'].update(scale='millions'),
                   lambda a:a['quantity'].update(resolution='0.01'),
                   lambda a:a['citations'][0].update(body_sha256='changed'),
                   lambda a:a.update(review='automatically_inferred')):
        contract,originals=fixture();mutate(contract['requirements'][0]['alternatives'][1])
        with pytest.raises(ValueError):review_requirements(contract,originals)


def test_and_across_citations_and_requirements_or_between_alternatives():
    contract,originals=fixture()
    need=deepcopy(contract['requirements'][0]);need.pop('quantity');need['id']='scope'
    need['alternatives']=[deepcopy(need['alternatives'][0])]
    need['alternatives'][0].pop('quantity')
    need['alternatives'][0]['citations'].append(contract['requirements'][0]['alternatives'][1]['citations'][0])
    contract['requirements'].append(need)
    reviewed=review_requirements(contract,originals)
    assert not score_requirements(['text'],reviewed)['all_complete']
    assert score_requirements(['text','table'],reviewed)['all_complete']


def test_wrong_value_cannot_hide_behind_coarse_precision():
    contract,originals=fixture()
    original=originals['coarse'];original['body']=original['body'].replace('23 million','90 million')
    alternative=contract['requirements'][0]['alternatives'][2]
    alternative['quantity']['value']='90'
    alternative['citations'][0].update(quote=original['body'],body_sha256=sha256(original['body'].encode()).hexdigest())
    result=score_requirements(['coarse'],review_requirements(contract,originals))
    assert result['requirements'][0]['status']=='value_mismatch'
