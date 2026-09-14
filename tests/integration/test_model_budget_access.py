"""Native PostgreSQL grants, private cost projection and snapshot restoration.

Only fresh synthetic databases in the isolated fixture; no model requests,
deletion, production migration, or custom backup/retention engine.
"""
from dataclasses import asdict
import hashlib
import os
from pathlib import Path
import secrets
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest

from test_native_server_runtime import native
from sec_agent.adapters.model_dispatch_store import ModelDispatchStore, DispatchBlocked
from sec_agent.agent_runtime.research_budget import budget_from_host
from sec_agent.agent_runtime.model_dispatch_guard import TokenPrices

pytestmark = pytest.mark.skipif(os.getenv('FIN_NATIVE_QUALIFICATION') != '1', reason='isolated Docker opt-in')


@pytest.fixture(scope='module')
def access(native):
    base=dict(host='127.0.0.1',port=18416,user='probe',password=native.env['FIN_E1_POSTGRES_PASSWORD'])
    admin=make_conninfo(**base,dbname='probe')
    with psycopg.connect(admin,autocommit=True) as db:
        db.execute('CREATE DATABASE fin_budget_probe')
        db.execute('CREATE DATABASE fin_budget_restore')
    admin=make_conninfo(**base,dbname='fin_budget_probe')
    owner=ModelDispatchStore(admin)
    owner.install()
    migration=Path('src/sec_agent/agent_runtime/sql/004_model_dispatch_access_v1.sql').read_text(encoding='utf-8')
    with owner.connection() as db:
        db.execute(migration)
    accounts={}
    for login, group in [('budget_worker','fin_model_worker'),('budget_authorizer','fin_model_provisioner'),
                         ('cost_alice','fin_model_cost_reader'),('cost_bob','fin_model_cost_reader'),('no_access',None)]:
        password=secrets.token_hex(24)
        with owner.connection() as db:
            db.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(
                sql.Identifier(login),sql.Literal(password)))
            if group:
                db.execute(sql.SQL('GRANT {} TO {}').format(sql.Identifier(group),sql.Identifier(login)))
        accounts[login]=make_conninfo(host=base['host'],port=base['port'],dbname='fin_budget_probe',user=login,password=password)
    with owner.connection() as db:
        db.execute("INSERT INTO public.fin_model_cost_access VALUES ('cost_alice','alice'),('cost_bob','bob')")
    authorizer=ModelDispatchStore(accounts['budget_authorizer'])
    for user in ('alice','bob'):
        authorizer.create_budget(user,'root','CNY',10000,1000)
    yield dict(native=native,admin=admin,owner=owner,accounts=accounts,authorizer=authorizer)
    # Native fixture stops all new services and retains this volume for evidence.


def denied(dsn, statement):
    with psycopg.connect(dsn) as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute(statement)


def reserve(store, owner, key, budget='root', reserved=600):
    return store.reserve(owner,budget,key,key,reserved,{'fixture':'synthetic_access'},currency='CNY')


def test_restricted_worker_host_binding_and_private_cost_views(access):
    a=access; dsn=a['accounts']['budget_worker']
    prices=TokenPrices('synthetic','deepseek-v4-pro','CNY',1,0,1)
    binding={'owner_id':'alice','budget_id':'root','prices':[asdict(prices)],'roles':{}}
    runtime=budget_from_host({'model_budget_bindings':{'t':binding}},thread_id='t',metadata={'owner_id':'alice'},
                              environment={'FIN_MODEL_BUDGET_POSTGRES_URI':dsn})
    store=runtime.store
    with pytest.raises(DispatchBlocked,match='overprivileged'):
        a['owner'].require_runtime_role()
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        store.create_budget('alice','unauthorized','CNY',10000,0)
    for statement in (
        "UPDATE public.fin_model_budget SET limit_micros=99999",
        "UPDATE public.fin_model_budget SET owner_id=owner_id",  # trigger blocks mutation, not row locking
        "DELETE FROM public.fin_model_dispatch", "TRUNCATE public.fin_model_dispatch",
        "DELETE FROM public.fin_model_budget", "CREATE TABLE public.unauthorized(x int)",
        "INSERT INTO public.fin_model_cost_access VALUES ('budget_worker','bob')",
        "GRANT fin_model_provisioner TO budget_worker",
        "UPDATE public.fin_model_dispatch SET fingerprint='changed'",
    ): denied(dsn,statement)
    for user in ('alice','bob'):
        reserve(store,user,'known')
        store.received(user,'root','known',{'private_text':'synthetic-private-'+user},200)
        reserve(store,user,'unknown'); store.unknown(user,'root','unknown')
    for statement in (
        "UPDATE public.fin_model_dispatch SET actual_micros=0 WHERE status='received'",
        "UPDATE public.fin_model_dispatch SET response='{}' WHERE status='received'",
        "UPDATE public.fin_model_dispatch SET status='dispatched' WHERE status='unknown'",
    ): denied(dsn,statement)
    with store.connection() as db:
        # A temporary relation cannot shadow the trusted public table.
        db.execute('CREATE TEMP TABLE fin_model_budget(owner_id text)')
        assert store._budget(db,'alice','root')['limit_micros']==10000
    for login,user in [('cost_alice','alice'),('cost_bob','bob')]:
        reader=a['accounts'][login]
        for table in ('fin_model_dispatch','fin_model_budget','fin_model_cost_access'):
            denied(reader,'SELECT * FROM public.'+table)
        denied(reader,'SET ROLE budget_worker')
        denied(reader,"SET SESSION AUTHORIZATION budget_worker")
        with psycopg.connect(reader) as db:
            db.execute("SET app.owner_id='forged-other-owner'")
            db.execute('SET ROLE fin_model_cost_reader')
            with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
                rows=cur.execute('SELECT * FROM public.fin_model_cost_summary').fetchall()
                assert len(rows)==1 and rows[0]['owner_id']==user
                assert int(rows[0]['known_micros'])==200 and int(rows[0]['held_micros'])==600
                assert not {'response','basis','fingerprint','call_id'} & rows[0].keys()
    denied(a['accounts']['no_access'],'SELECT * FROM public.fin_model_dispatch')
    denied(a['accounts']['no_access'],'SELECT * FROM public.fin_model_cost_summary')
    denied(a['accounts']['budget_authorizer'],'SELECT * FROM public.fin_model_dispatch')
    a['native'].save('access_roles',{'host_runtime_used_restricted_login':True,'readers':['alice','bob'],
        'raw_tables_denied':True,'forged_guc_and_set_role_cannot_change_reader_owner':True,
        'budget_mint_mutate_delete_and_membership_denied':True,'private_values_not_exported':True,
        'known_response_cost_and_unknown_state_rewrite_denied':True,
        'trusted_worker_can_read_all_configured_owners':True,'model_calls':0})


def test_restricted_worker_transactions_preserve_budget_under_competing_children(access):
    a=access; a['authorizer'].create_budget('alice','race','CNY',1000,200)
    store=ModelDispatchStore(a['accounts']['budget_worker']); barrier=Barrier(2)
    def compete(key):
        barrier.wait()
        try: reserve(store,'alice',key,'race'); return key
        except DispatchBlocked: return None
    with ThreadPoolExecutor(2) as pool:
        winners=[key for key in pool.map(compete,['a','b']) if key]
    assert len(winners)==1
    store.received('alice','race',winners[0],{'private_text':'synthetic-race'},200)
    assert store.snapshot('alice','race')['known']==200
    access['native'].save('restricted_concurrency',{'winning_children':len(winners),'known_micros':200,'model_calls':0})


def test_native_backup_restore_retains_receipts_unknown_holds_and_reader_grants(access):
    a=access; native=a['native']; store=ModelDispatchStore(a['accounts']['budget_worker'])
    a['authorizer'].create_budget('alice','restore','CNY',10000,1000)
    reserve(store,'alice','saved','restore')
    store.received('alice','restore','saved',{'private_text':'synthetic-restorable'},200)
    reserve(store,'alice','unknown','restore'); store.unknown('alice','restore','unknown')
    reserve(store,'alice','missing-usage','restore')
    store.received('alice','restore','missing-usage',{'private_text':'synthetic-no-usage'},None)
    before=store.snapshot('alice','restore')
    # No requests execute during backup/restore. This is a frozen snapshot test,
    # not PITR or proof that a stale backup contains later paid dispatches.
    native.compose('exec','-T','postgres','pg_dump','-U','probe','-d','fin_budget_probe','-Fc','--no-owner','-f','/tmp/fin_budget.dump')
    backup=native.output/'fin_budget.dump'
    native.compose('cp','postgres:/tmp/fin_budget.dump',str(backup))
    native.compose('exec','-T','postgres','pg_restore','-U','probe','-d','fin_budget_restore','--no-owner','--exit-on-error','/tmp/fin_budget.dump')
    restored_dsn=make_conninfo(a['accounts']['budget_worker'],dbname='fin_budget_restore')
    restored=ModelDispatchStore(restored_dsn); restored.require_runtime_role()
    assert restored.snapshot('alice','restore')==before
    for key in ('saved','missing-usage'):
        assert reserve(restored,'alice',key,'restore')['status']=='received'
    assert reserve(restored,'alice','saved','restore')['response']=={'private_text':'synthetic-restorable'}
    with pytest.raises(DispatchBlocked,match='unresolved_no_retry'):
        reserve(restored,'alice','unknown','restore')
    assert restored.snapshot('alice','restore')==before
    reader=make_conninfo(a['accounts']['cost_alice'],dbname='fin_budget_restore')
    denied(reader,'SELECT * FROM public.fin_model_dispatch')
    denied(restored_dsn,'DELETE FROM public.fin_model_dispatch')
    with psycopg.connect(reader) as db:
        assert db.execute("SELECT known_micros,held_micros FROM public.fin_model_cost_summary WHERE budget_id='restore'").fetchone()==(200,1200)
    native.save('backup_restore',{'before':before,'after':restored.snapshot('alice','restore'),
        'dump_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'dump_bytes':backup.stat().st_size,
        'saved_and_missing_usage_replay':True,'unknown_still_blocks':True,'reader_acl_survives_restore':True,
        'snapshot_only_no_post_backup_calls':True,'model_calls':0})
