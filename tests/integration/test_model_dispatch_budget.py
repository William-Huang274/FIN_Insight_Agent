"""Real PostgreSQL transactions and native middleware replay, zero provider I/O."""
import json
import os
import pytest

from test_native_server_runtime import native

pytestmark = pytest.mark.skipif(os.getenv('FIN_NATIVE_QUALIFICATION') != '1', reason='isolated Docker opt-in')


def db_code(native, body):
    prelude = "import os,json\nfrom sec_agent.adapters.model_dispatch_store import ModelDispatchStore,DispatchBlocked\ns=ModelDispatchStore(os.environ['POSTGRES_URI'])\ns.install()\n"
    return native.compose('exec', '-T', 'api', 'python', '-c', prelude + body)


def test_postgres_competing_children_settlement_and_delivery_floor(native):
    output = db_code(native, '''
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
s.create_budget('alice','root-concurrent','CNY',1000,200)
barrier=Barrier(2)
def reserve(key):
    barrier.wait()
    try:
        s.reserve('alice','root-concurrent',key,key,600,{'test':'concurrent-child'},currency='CNY')
        return key
    except DispatchBlocked: return None
with ThreadPoolExecutor(2) as pool: rows=list(pool.map(reserve,['child-a','child-b']))
winners=[r for r in rows if r]
assert len(winners)==1, rows
first=s.snapshot('alice','root-concurrent')
assert (first['known'],first['held'])==(0,600)
s.received('alice','root-concurrent',winners[0],{'messages':[]},200)
s.reserve('alice','root-concurrent','child-next','next',600,{'test':'next-child'},currency='CNY')
s.unknown('alice','root-concurrent','child-next')
try: s.reserve('alice','root-concurrent','explore','explore',1,{'test':'explore'},currency='CNY')
except DispatchBlocked: pass
else: raise AssertionError('exploration spent delivery floor')
s.reserve('alice','root-concurrent','delivery','delivery',200,{'test':'delivery'},currency='CNY',delivery=True)
last=s.snapshot('alice','root-concurrent')
assert (last['known'],last['held'],last['available_micros'])==(200,800,0)
print(json.dumps({'winner':winners,'first':first,'last':last}))
''')
    native.save('budget_competing_children', json.loads(output))


def test_postgres_unknown_currency_owner_replay_and_actual_overspend(native):
    output = db_code(native, '''
s.create_budget('alice','root-boundary','CNY',1000,0)
def blocked(**updates):
    args=dict(owner='alice',budget='root-boundary',key='call',fingerprint='fixed',reserved=600,basis={'test':'boundary'},currency='CNY')
    args.update(updates)
    try: s.reserve(**args)
    except DispatchBlocked: return
    raise AssertionError('expected closed boundary')
blocked(owner='bob')
blocked(currency='USD')
s.reserve('alice','root-boundary','call','fixed',600,{'test':'boundary'},currency='CNY')
s.unknown('alice','root-boundary','call')
blocked()
blocked(fingerprint='changed')
assert s.snapshot('alice','root-boundary')['held']==600
s.create_budget('alice','root-actual','CNY',1000,0)
s.reserve('alice','root-actual','known','fixed',600,{'test':'overspend'},currency='CNY')
s.received('alice','root-actual','known',{'messages':[]},1200)
replay=s.reserve('alice','root-actual','known','fixed',600,{'test':'overspend'},currency='CNY')
assert replay['status']=='received'
actual=s.snapshot('alice','root-actual')
assert actual['known']==1200 and actual['available_micros']==-200
blocked(budget='root-actual',key='another')
s.create_budget('alice','root-usage','CNY',1000,0)
s.reserve('alice','root-usage','known','fixed',600,{'test':'usage-missing'},currency='CNY')
s.received('alice','root-usage','known',{'messages':[]},None)
assert s.snapshot('alice','root-usage')['held']==600
assert s.reserve('alice','root-usage','known','fixed',600,{'test':'usage-missing'},currency='CNY')['status']=='received'
print(json.dumps({'unknown':s.snapshot('alice','root-boundary'),'actual':actual,'missing_usage':s.snapshot('alice','root-usage')}))
''')
    native.save('budget_boundary', json.loads(output))


def start_guarded(native, label, mode):
    db_code(native, f"s.create_budget('alice','{label}','CNY',1000,200)")
    thread = native.request('POST', '/threads', json={})['thread_id']
    run = native.request('POST', f'/threads/{thread}/runs', json={'assistant_id':'runtime_probe', 'input':{
        'label':label, 'guard_budget':label, 'guard_owner':'alice', 'guard_mode':mode, 'delay_seconds':12}})
    return thread, run['run_id']


def test_native_unknown_dispatch_blocks_restarted_model_node(native):
    pair = start_guarded(native, 'guard-unknown', 'unknown')
    native.wait(lambda: native.events('guard-unknown','provider_effect'))
    native.compose('stop','-t','8','api')
    native.compose('start','api')
    native.healthy()
    native.terminal(pair, 'error')
    assert len(native.events('guard-unknown','provider_effect'))==1
    assert len(native.events('guard-unknown','work_started'))==2
    snapshot=json.loads(db_code(native,"print(json.dumps(s.snapshot('alice','guard-unknown')))"))
    assert snapshot['held']==600 and snapshot['known']==0
    native.save('guard_unknown',{'run':pair,'snapshot':snapshot,'state':native.state(pair)})


def test_native_saved_model_response_replays_before_node_checkpoint(native):
    pair = start_guarded(native, 'guard-saved', 'saved')
    native.wait(lambda: native.events('guard-saved','guard_returned'))
    native.compose('stop','-t','8','api')
    native.compose('start','api')
    native.healthy()
    native.terminal(pair)
    assert len(native.events('guard-saved','provider_effect'))==1
    assert len(native.events('guard-saved','saved_response_replayed'))==1
    snapshot=json.loads(db_code(native,"print(json.dumps(s.snapshot('alice','guard-saved')))"))
    assert snapshot['held']==0 and snapshot['known']==200
    native.save('guard_saved',{'run':pair,'snapshot':snapshot,'state':native.state(pair)})
