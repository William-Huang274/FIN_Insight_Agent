import httpx
import pytest
from tests.integration.source_intake_registration import register_index


@pytest.mark.parametrize('post',['success','lost_response','server_error','denied'])
@pytest.mark.parametrize('registered',[True,False])
def test_one_submission_and_exact_confirmation(post,registered):
    calls=[];receipts={};expected={'release_id':'fixed'}
    def handler(request):
        calls.append(request.method)
        if request.method=='POST':
            if post=='lost_response':raise httpx.ReadTimeout('lost',request=request)
            return httpx.Response({'success':200,'server_error':503,'denied':403}[post],json=expected)
        return httpx.Response(200,json={'status':'registered' if registered else 'unconfirmed','contract':expected})
    with httpx.Client(base_url='http://test',transport=httpx.MockTransport(handler)) as client:
        if post=='denied':
            with pytest.raises(httpx.HTTPStatusError):register_index(client,'/release',expected=expected,save=receipts.__setitem__)
            assert calls==['POST']
        elif not registered:
            with pytest.raises(RuntimeError,match='do_not_resubmit'):register_index(client,'/release',expected=expected,save=receipts.__setitem__)
            assert calls==['POST','GET']
        else:
            assert register_index(client,'/release',expected=expected,save=receipts.__setitem__)==expected
            assert calls==['POST','GET'] and receipts['index-registration-request']['submissions']==1


def test_wrong_readback_cannot_confirm_publication():
    def handler(request):return httpx.Response(200,json={'id':1} if request.method=='POST' else {'status':'registered','contract':{'id':2}})
    with httpx.Client(base_url='http://test',transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError,match='confirmation_contract'):
            register_index(client,'/release',expected={'id':1},save=lambda *args:None)
