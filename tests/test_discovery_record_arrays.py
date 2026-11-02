from copy import deepcopy
from structured_source_contract import describe


def view(value):return describe(dict(route='structured_json',structured_object=value))


def test_repository_catalog_does_not_claim_readme():
    data=[dict(id=1,full_name='org/repo',owner={'login':'org'},html_url='https://github.com/org/repo',default_branch='main')]
    old=deepcopy(data);r=view(data)
    assert r['kind']=='github_repository_catalog' and r['records'][0]['locator']=='/0'
    assert r['content_scope']=='repository_metadata_not_readme_or_source_code' and data==old


def test_mixed_issue_and_pull_request_keep_identity_and_body_location():
    issue=dict(id=1,number=12,title='Question',body=None,repository_url='https://api.github.com/repos/a/b',state='open',user={})
    pr=dict(issue,id=2,number=13,body='Text',pull_request={'url':'https://api.github.com/repos/a/b/pulls/13'})
    r=view([issue,pr])
    assert r['kind']=='github_issue_pull_request_records'
    assert [x['record_role'] for x in r['records']]==['issue','pull_request']
    assert r['records'][1]['body_locator']=='/1/body'
    assert 'not_complete_discussion' in r['content_scope']


def test_model_catalog_keeps_revision_without_claiming_model_card():
    r=view([dict(id='org/model',modelId='org/model',sha='revision',siblings=[{'rfilename':'README.md'}],tags=[],author='org')])
    assert r['kind']=='huggingface_model_catalog' and r['records'][0]['revision']=='revision'
    assert 'not_model_card_or_weights' in r['content_scope']


def test_every_record_must_match_and_empty_does_not_guess_provider():
    entry=dict(id=1,full_name='a/b',owner={'login':'a'},html_url='u',default_branch='main')
    assert view([entry,{'id':2}])['kind']=='unresolved_record_array'
    assert view([])['kind']=='unresolved_record_array'
    assert view([dict(id='a',modelId='b',sha='x',siblings=[],tags=[],author='a')])['kind']=='unresolved_record_array'
