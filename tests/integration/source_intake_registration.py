"""Bounded qualification wait; one submission, read-only confirmation on ambiguity."""
import httpx


def register_index(client, path, *, expected, save, wait_seconds=300):
    if not 50 <= wait_seconds <= 600:
        raise ValueError('qualification_registration_wait_out_of_range')
    observation={'wait_seconds':wait_seconds,'submissions':1,'automatic_resubmission':False}
    save('index-registration-request', {**observation, 'post_status':'inflight'})
    try:
        response=client.post(path+'/register',json={},timeout=httpx.Timeout(wait_seconds,connect=5))
        observation.update(post_status=response.status_code)
        save('index-registration-request',observation)
        if response.is_success:
            if response.json()!=expected:raise ValueError('registration_contract_mismatch')
        elif response.status_code < 500:
            response.raise_for_status()
    except httpx.TransportError as exc:
        observation.update(post_status='unknown',transport_error=type(exc).__name__)
    # Even a successful submission is read back by its exact release and draft.
    save('index-registration-request',observation)
    result=client.get(path+'/registration',timeout=30)
    result.raise_for_status()
    value=result.json()
    save('index-registration-confirmation',value)
    if value.get('status')!='registered':
        raise RuntimeError('registration_unconfirmed_do_not_resubmit')
    if value.get('contract')!=expected:
        raise ValueError('registration_confirmation_contract_mismatch')
    return value['contract']
