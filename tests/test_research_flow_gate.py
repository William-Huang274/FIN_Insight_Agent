from scripts.engineering.check_research_flow_gate import assess_gate


def test_missing_research_and_old_open_failure_do_not_pass_on_engineering_success():
    plan={'stages':[{'id':'A','depends_on':[],'cases':['D5'],'required':['engineering','research']},
                    {'id':'B','depends_on':['A'],'cases':['new'],'required':['engineering']}]}
    records={'D5':{'engineering':'accepted','research':'partial','evidence_refs':['real artifact']},
             'new':{'engineering':'accepted','evidence_refs':['fixture']}}
    result=assess_gate(plan,records,'B')
    assert not result['passed'] and result['missing']==[{'stage':'A','case':'D5','axis':'research','state':'partial'}]
    records['D5']['research']='accepted';records['D5']['open_material_errors']=['omitted condition']
    assert not assess_gate(plan,records,'B')['passed']
    records['D5']['open_material_errors']=[]
    assert assess_gate(plan,records,'B')['passed']
