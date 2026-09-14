-- Opt-in FIN research budget; PostgreSQL owns locks/transactions, not a new queue.
CREATE TABLE IF NOT EXISTS public.fin_model_budget (
    owner_id text NOT NULL,
    budget_id text NOT NULL,
    currency text NOT NULL,
    limit_micros bigint NOT NULL CHECK (limit_micros > 0),
    delivery_floor_micros bigint NOT NULL CHECK (delivery_floor_micros >= 0),
    PRIMARY KEY (owner_id, budget_id),
    CHECK (delivery_floor_micros <= limit_micros)
);
CREATE TABLE IF NOT EXISTS public.fin_model_dispatch (
    owner_id text NOT NULL,
    budget_id text NOT NULL,
    call_key text NOT NULL,
    call_id uuid NOT NULL,
    fingerprint text NOT NULL,
    reserved_micros bigint NOT NULL CHECK (reserved_micros > 0),
    actual_micros bigint CHECK (actual_micros >= 0),
    status text NOT NULL CHECK (status IN ('dispatched', 'unknown', 'received')),
    basis jsonb NOT NULL,
    response jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    received_at timestamptz,
    PRIMARY KEY (owner_id, budget_id, call_key),
    FOREIGN KEY (owner_id, budget_id) REFERENCES public.fin_model_budget,
    CHECK ((status = 'received') = (response IS NOT NULL)),
    CHECK (actual_micros IS NULL OR status = 'received')
);
