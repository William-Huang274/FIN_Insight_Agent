"""Thin PostgreSQL transactions for one research budget and its descendants.

No expiry, retries, queue, or automatic reconciliation. Calls with unknown cost
continue occupying their reservation. Install the SQL explicitly before use.
"""
import json
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class DispatchBlocked(RuntimeError):
    pass


def amount(value, *, positive=False):
    if type(value) is not int or not (1 if positive else 0) <= value < 2**63:
        raise ValueError('invalid_integer_money_amount')
    return value


class ModelDispatchStore:
    def __init__(self, dsn):
        self._dsn = dsn

    @contextmanager
    def connection(self):
        # Do not hold a transaction across provider/network execution.
        with psycopg.connect(self._dsn, connect_timeout=5, row_factory=dict_row) as db:
            db.execute('SET LOCAL search_path = pg_catalog, public, pg_temp')
            db.execute("SET LOCAL lock_timeout = '5s'")
            db.execute("SET LOCAL statement_timeout = '10s'")
            yield db

    def require_runtime_role(self):
        """Reject privileged/native-server credentials at the product boundary."""
        with self.connection() as db:
            row = db.execute('''SELECT
                current_user = session_user
                AND NOT (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls)
                AND pg_has_role(current_user,'fin_model_worker','MEMBER')
                AND NOT has_schema_privilege(current_user,'public','CREATE')
                AND NOT has_table_privilege(current_user,'public.fin_model_budget','INSERT,DELETE,TRUNCATE')
                AND NOT has_column_privilege(current_user,'public.fin_model_budget','limit_micros','UPDATE')
                AND NOT has_table_privilege(current_user,'public.fin_model_dispatch','DELETE,TRUNCATE')
                AS allowed FROM pg_roles r WHERE r.rolname=session_user''').fetchone()
            if not row or not row['allowed']:
                raise DispatchBlocked('model_budget_runtime_role_overprivileged')

    def install(self):
        """Explicit isolated setup/migration only; never called during dispatch."""
        sql = Path(__file__).parents[1] / 'agent_runtime/sql/003_model_dispatch_budget_v1.sql'
        with self.connection() as db:
            db.execute(sql.read_text(encoding='utf-8'))

    def create_budget(self, owner, budget, currency, limit, delivery_floor):
        if not all(isinstance(v, str) and v.strip() for v in (owner, budget, currency)):
            raise ValueError('budget_identity_missing')
        amount(limit, positive=True)
        amount(delivery_floor)
        if delivery_floor > limit:
            raise ValueError('delivery_floor_exceeds_budget')
        with self.connection() as db:
            db.execute('INSERT INTO fin_model_budget VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                       (owner, budget, currency, limit, delivery_floor))
            row = self._budget(db, owner, budget)
            if (row['currency'], row['limit_micros'], row['delivery_floor_micros']) != (currency, limit, delivery_floor):
                raise DispatchBlocked('budget_redefinition_forbidden')

    def _budget(self, db, owner, budget):
        row = db.execute('SELECT * FROM fin_model_budget WHERE owner_id=%s AND budget_id=%s FOR UPDATE',
                         (owner, budget)).fetchone()
        if row is None:
            raise DispatchBlocked('budget_not_authorized')
        return row

    def _totals(self, db, owner, budget):
        row = db.execute('''SELECT COALESCE(SUM(actual_micros),0) AS known,
            COALESCE(SUM(reserved_micros) FILTER (WHERE actual_micros IS NULL),0) AS held,
            COUNT(*) FILTER (WHERE actual_micros IS NULL) AS unsettled
            FROM fin_model_dispatch WHERE owner_id=%s AND budget_id=%s''', (owner, budget)).fetchone()
        return {key: int(value) for key, value in row.items()}

    def snapshot(self, owner, budget):
        with self.connection() as db:
            row = self._budget(db, owner, budget)
            totals = self._totals(db, owner, budget)
            return {**row, **totals, 'available_micros': row['limit_micros'] - totals['known'] - totals['held']}

    def reserve(self, owner, budget, key, fingerprint, reserved, basis, *, currency, delivery=False):
        amount(reserved, positive=True)
        if not key or not fingerprint or not isinstance(basis, dict) or not basis:
            raise ValueError('dispatch_binding_missing')
        with self.connection() as db:
            envelope = self._budget(db, owner, budget)
            if currency != envelope['currency']:
                raise DispatchBlocked('budget_currency_mismatch')
            prior = db.execute('SELECT * FROM fin_model_dispatch WHERE owner_id=%s AND budget_id=%s AND call_key=%s',
                               (owner, budget, key)).fetchone()
            if prior:
                if prior['fingerprint'] != fingerprint:
                    raise DispatchBlocked('native_step_payload_changed')
                if prior['status'] != 'received':
                    raise DispatchBlocked('prior_dispatch_unresolved_no_retry')
                return prior
            totals = self._totals(db, owner, budget)
            floor = 0 if delivery else envelope['delivery_floor_micros']
            if totals['known'] + totals['held'] + reserved + floor > envelope['limit_micros']:
                raise DispatchBlocked('research_budget_exhausted_delivery_reserve_preserved')
            call_id = uuid4()
            db.execute('''INSERT INTO fin_model_dispatch
                (owner_id,budget_id,call_key,call_id,fingerprint,reserved_micros,status,basis)
                VALUES (%s,%s,%s,%s,%s,%s,'dispatched',%s)''',
                (owner, budget, key, call_id, fingerprint, reserved, Jsonb(basis)))
            return {'status': 'dispatched', 'call_id': call_id}

    def received(self, owner, budget, key, response, actual):
        if actual is not None:
            amount(actual)
        if not isinstance(response, dict) or len(json.dumps(response).encode()) > 4_000_000:
            raise ValueError('dispatch_response_invalid_or_too_large')
        with self.connection() as db:
            self._budget(db, owner, budget)
            changed = db.execute('''UPDATE fin_model_dispatch SET status='received',response=%s,
                actual_micros=%s,received_at=now()
                WHERE owner_id=%s AND budget_id=%s AND call_key=%s AND status='dispatched' ''',
                (Jsonb(response), actual, owner, budget, key)).rowcount
            if changed != 1:
                raise DispatchBlocked('dispatch_settlement_state_conflict')
            # Actual spend may exceed reservation/limit. Never discard real cost.

    def unknown(self, owner, budget, key):
        with self.connection() as db:
            self._budget(db, owner, budget)
            db.execute("UPDATE fin_model_dispatch SET status='unknown' WHERE owner_id=%s AND budget_id=%s AND call_key=%s AND status='dispatched'",
                       (owner, budget, key))
