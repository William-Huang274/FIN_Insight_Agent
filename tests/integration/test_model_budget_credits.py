"""Real SQL/roles/concurrency. Explicit fresh test database; no model calls.

FIN_BUDGET_CREDIT_TEST_DSN must name a disposable fin_budget_credit_test_* DB.
Its migration owner must provision the existing 003/004/005 contract first.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
from psycopg.conninfo import conninfo_to_dict
import pytest

from sec_agent.adapters.model_dispatch_store import ModelDispatchStore, DispatchBlocked

DSN = os.getenv('FIN_BUDGET_CREDIT_TEST_DSN')
pytestmark = pytest.mark.skipif(not DSN, reason='explicit isolated credit database required')


@pytest.fixture
def store():
    assert conninfo_to_dict(DSN)['dbname'].startswith('fin_budget_credit_test_')
    return ModelDispatchStore(DSN)


def test_credit_replay_currency_envelope_and_unknown_cost(store):
    owner = str(uuid4())
    store.create_budget(owner, 'a', 'USD', 500000, 0)
    store.create_budget(owner, 'b', 'USD', 500000, 0)
    store.reserve(owner, 'a', 'spent', 'x', 400000, {'purpose': 'fixture'}, currency='USD')
    store.received(owner, 'a', 'spent', {'saved': True}, 103279)
    with pytest.raises(DispatchBlocked):
        store.reserve(owner, 'a', 'next', 'x', 400000, {'purpose': 'fixture'}, currency='USD')
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda _: store.add_credit(owner, 'a', 'approval', 'USD', 500000, 'user:fixture'), range(4)))
    row = store.snapshot(owner, 'a')
    assert (row['limit_micros'], row['credited_micros'], row['available_micros']) == (500000,500000,896721)
    for budget, currency, amount, ref in [('b','USD',500000,'user:fixture'), ('a','EUR',500000,'user:fixture'),
                                         ('a','USD',1,'user:fixture'), ('a','USD',500000,'changed')]:
        with pytest.raises(DispatchBlocked):
            store.add_credit(owner, budget, 'approval', currency, amount, ref)
    store.reserve(owner, 'a', 'next', 'x', 400000, {'purpose':'fixture'}, currency='USD')
    store.unknown(owner, 'a', 'next')
    store.add_credit(owner, 'a', 'second', 'USD', 100000, 'user:next')
    assert store.snapshot(owner, 'a')['held'] == 400000
    with pytest.raises(DispatchBlocked, match='prior_dispatch_unresolved'):
        store.reserve(owner, 'a', 'next', 'x', 400000, {'purpose':'fixture'}, currency='USD')
    assert store.lookup(owner, 'a', 'spent')['actual_micros'] == 103279
    assert store.snapshot(owner, 'b')['credited_micros'] == 0


def test_credit_cannot_mutate_history_or_be_minted_by_worker(store):
    owner = str(uuid4())
    store.create_budget(owner, 'a', 'USD', 500000, 0)
    store.add_credit(owner, 'a', 'approval', 'USD', 500000, 'user:fixture')
    for statement in ["UPDATE fin_model_budget SET limit_micros=900000 WHERE owner_id=%s",
                      "UPDATE fin_model_budget_credit SET amount_micros=900000 WHERE owner_id=%s",
                      "DELETE FROM fin_model_budget_credit WHERE owner_id=%s"]:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with store.connection() as db:
                db.execute(statement, (owner,))
    for role in ['fin_model_worker', 'fin_model_cost_reader']:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with store.connection() as db:
                db.execute('SET LOCAL ROLE '+role)
                db.execute("INSERT INTO fin_model_budget_credit(owner_id,budget_id,authorization_id,amount_micros,authorization_ref) VALUES (%s,'a','forged',1,'model')",(owner,))
    with store.connection() as db:
        db.execute('SET LOCAL ROLE fin_model_provisioner')
        db.execute("INSERT INTO fin_model_budget_credit(owner_id,budget_id,authorization_id,amount_micros,authorization_ref) VALUES (%s,'a','approved',1,'user:second')",(owner,))
    assert store.snapshot(owner, 'a')['authorized_micros'] == 1000001


def test_credited_budget_still_serializes_competing_reservations(store):
    owner = str(uuid4())
    store.create_budget(owner, 'a', 'USD', 500000, 100000)
    store.add_credit(owner, 'a', 'approval', 'USD', 500000, 'user:fixture')
    def reserve(key):
        try:
            store.reserve(owner,'a',key,key,600000,{'purpose':'fixture'},currency='USD')
            return True
        except DispatchBlocked:
            return False
    with ThreadPoolExecutor(2) as pool:
        assert sum(pool.map(reserve,['a','b'])) == 1
    assert store.snapshot(owner, 'a')['held'] == 600000


def test_migration_replay_and_scoped_cost_view(store):
    owner, other = str(uuid4()), str(uuid4())
    store.create_budget(owner, 'a', 'USD', 500000, 0)
    store.create_budget(other, 'a', 'USD', 500000, 0)
    store.add_credit(owner, 'a', 'approval', 'USD', 500000, 'user:fixture')
    store.install()  # Existing budget/access triggers and added credits survive migration replay.
    with store.connection() as db:
        db.execute("INSERT INTO fin_model_cost_access VALUES ('fin_model_cost_reader',%s)",(owner,))
    with store.connection() as db:
        db.execute('SET SESSION AUTHORIZATION fin_model_cost_reader')
        rows=db.execute('SELECT * FROM fin_model_cost_summary WHERE owner_id IN (%s,%s)',(owner,other)).fetchall()
        assert len(rows)==1 and rows[0]['owner_id']==owner
        assert rows[0]['limit_micros']==500000 and rows[0]['authorized_micros']==1000000
