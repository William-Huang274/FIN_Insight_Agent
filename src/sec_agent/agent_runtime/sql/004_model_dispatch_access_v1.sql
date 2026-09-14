-- Explicit one-time bootstrap in a DEDICATED model-budget database.
-- Run 003 first as the migration owner. Never run as an application worker.
-- Roles are cluster objects: on another database provision/reuse reviewed groups
-- separately; this bootstrap deliberately fails on a colliding role name.
CREATE ROLE fin_model_worker NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE fin_model_provisioner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE fin_model_cost_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON public.fin_model_budget, public.fin_model_dispatch FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO fin_model_worker, fin_model_provisioner, fin_model_cost_reader;

-- SELECT FOR UPDATE needs a column UPDATE privilege. The trigger permits the
-- lock but rejects every actual mutation of an already authorized budget.
CREATE FUNCTION public.fin_model_budget_immutable() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    RAISE EXCEPTION 'budget_redefinition_forbidden' USING ERRCODE = '42501';
END
$$;
REVOKE ALL ON FUNCTION public.fin_model_budget_immutable() FROM PUBLIC;
CREATE TRIGGER fin_model_budget_immutable BEFORE UPDATE ON public.fin_model_budget
FOR EACH ROW EXECUTE FUNCTION public.fin_model_budget_immutable();

GRANT SELECT, UPDATE (owner_id) ON public.fin_model_budget TO fin_model_worker, fin_model_provisioner;
GRANT INSERT ON public.fin_model_budget TO fin_model_provisioner;
GRANT SELECT ON public.fin_model_dispatch TO fin_model_worker;
GRANT INSERT (owner_id,budget_id,call_key,call_id,fingerprint,reserved_micros,status,basis)
    ON public.fin_model_dispatch TO fin_model_worker;
GRANT UPDATE (status,response,actual_micros,received_at) ON public.fin_model_dispatch TO fin_model_worker;

-- A worker may finish an in-flight dispatch, not rewrite a known or unknown
-- receipt to reduce its cost, replace its response or enable another attempt.
CREATE FUNCTION public.fin_model_dispatch_final() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF OLD.status <> 'dispatched' OR NEW.status NOT IN ('received','unknown') THEN
        RAISE EXCEPTION 'dispatch_receipt_immutable' USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END
$$;
REVOKE ALL ON FUNCTION public.fin_model_dispatch_final() FROM PUBLIC;
CREATE TRIGGER fin_model_dispatch_final BEFORE UPDATE ON public.fin_model_dispatch
FOR EACH ROW EXECUTE FUNCTION public.fin_model_dispatch_final();

-- Binding is managed only by the database owner, never by a reader or worker.
-- The login identity is authoritative; SET ROLE and arbitrary application GUCs
-- cannot change session_user. Shared reader logins are not tenant isolation.
CREATE TABLE public.fin_model_cost_access (
    login_role name NOT NULL,
    owner_id text NOT NULL,
    PRIMARY KEY (login_role, owner_id)
);
REVOKE ALL ON public.fin_model_cost_access FROM PUBLIC;
CREATE VIEW public.fin_model_cost_summary WITH (security_barrier=true) AS
SELECT b.owner_id, b.budget_id, b.currency, b.limit_micros, b.delivery_floor_micros,
    COALESCE(SUM(d.actual_micros),0) AS known_micros,
    COALESCE(SUM(d.reserved_micros) FILTER (WHERE d.actual_micros IS NULL AND d.call_key IS NOT NULL),0) AS held_micros,
    COUNT(d.call_key) FILTER (WHERE d.actual_micros IS NULL) AS unsettled
FROM public.fin_model_budget b
LEFT JOIN public.fin_model_dispatch d USING (owner_id,budget_id)
WHERE EXISTS (SELECT 1 FROM public.fin_model_cost_access a
              WHERE a.login_role = session_user AND a.owner_id = b.owner_id)
GROUP BY b.owner_id,b.budget_id,b.currency,b.limit_micros,b.delivery_floor_micros;
REVOKE ALL ON public.fin_model_cost_summary FROM PUBLIC;
GRANT SELECT ON public.fin_model_cost_summary TO fin_model_cost_reader;

-- No role receives DELETE, TRUNCATE, ownership, response export or retention
-- automation. Retain raw response + identity + known/unknown spend together.
