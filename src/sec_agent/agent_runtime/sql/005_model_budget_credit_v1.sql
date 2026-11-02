-- Explicit migration after 003. Existing envelopes and dispatch history remain immutable.
CREATE TABLE IF NOT EXISTS public.fin_model_budget_credit (
    owner_id text NOT NULL,
    budget_id text NOT NULL,
    authorization_id text NOT NULL CHECK (length(trim(authorization_id)) > 0),
    amount_micros bigint NOT NULL CHECK (amount_micros > 0),
    authorization_ref text NOT NULL CHECK (length(trim(authorization_ref)) > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, authorization_id),
    FOREIGN KEY (owner_id, budget_id) REFERENCES public.fin_model_budget
);
CREATE INDEX IF NOT EXISTS fin_model_budget_credit_envelope
    ON public.fin_model_budget_credit (owner_id,budget_id);
REVOKE ALL ON public.fin_model_budget_credit FROM PUBLIC;
CREATE OR REPLACE FUNCTION public.fin_model_credit_immutable() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    RAISE EXCEPTION 'budget_credit_immutable' USING ERRCODE = '42501';
END
$$;
REVOKE ALL ON FUNCTION public.fin_model_credit_immutable() FROM PUBLIC;
DROP TRIGGER IF EXISTS fin_model_credit_immutable ON public.fin_model_budget_credit;
CREATE TRIGGER fin_model_credit_immutable BEFORE UPDATE OR DELETE ON public.fin_model_budget_credit
    FOR EACH ROW EXECUTE FUNCTION public.fin_model_credit_immutable();
DO $$ BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname='fin_model_worker') THEN
        GRANT SELECT ON public.fin_model_budget_credit TO fin_model_worker;
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname='fin_model_provisioner') THEN
        GRANT SELECT, INSERT ON public.fin_model_budget_credit TO fin_model_provisioner;
    END IF;
END $$;
-- Keep the existing tenant-filtered cost view consistent on upgraded databases.
DO $$ BEGIN
    IF to_regclass('public.fin_model_cost_summary') IS NOT NULL THEN
        EXECUTE $view$
        CREATE OR REPLACE VIEW public.fin_model_cost_summary WITH (security_barrier=true) AS
        SELECT b.owner_id, b.budget_id, b.currency, b.limit_micros, b.delivery_floor_micros,
            COALESCE(SUM(d.actual_micros),0) AS known_micros,
            COALESCE(SUM(d.reserved_micros) FILTER (WHERE d.actual_micros IS NULL AND d.call_key IS NOT NULL),0) AS held_micros,
            COUNT(d.call_key) FILTER (WHERE d.actual_micros IS NULL) AS unsettled,
            (SELECT COALESCE(SUM(c.amount_micros),0) FROM public.fin_model_budget_credit c
                WHERE c.owner_id=b.owner_id AND c.budget_id=b.budget_id) AS credited_micros,
            b.limit_micros + (SELECT COALESCE(SUM(c.amount_micros),0) FROM public.fin_model_budget_credit c
                WHERE c.owner_id=b.owner_id AND c.budget_id=b.budget_id) AS authorized_micros
        FROM public.fin_model_budget b LEFT JOIN public.fin_model_dispatch d USING (owner_id,budget_id)
        WHERE EXISTS (SELECT 1 FROM public.fin_model_cost_access a
                      WHERE a.login_role=session_user AND a.owner_id=b.owner_id)
        GROUP BY b.owner_id,b.budget_id,b.currency,b.limit_micros,b.delivery_floor_micros
        $view$;
    END IF;
END $$;
