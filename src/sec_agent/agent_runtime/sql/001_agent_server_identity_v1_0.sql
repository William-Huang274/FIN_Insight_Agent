-- FIN-owned durable identity mappings for the Dell Agent Server vertical.
-- This schema is independent from Agent Server implementation tables.
-- Transaction control is intentionally owned by the installer.

SET LOCAL ROLE fin_runtime_migrator;

CREATE SCHEMA IF NOT EXISTS fin_runtime AUTHORIZATION fin_runtime_migrator;
REVOKE ALL ON SCHEMA fin_runtime FROM PUBLIC;

CREATE TABLE IF NOT EXISTS fin_runtime.research_sessions (
    agent_session_id text PRIMARY KEY,
    fin_thread_id text NOT NULL UNIQUE,
    server_thread_id uuid NOT NULL UNIQUE,
    assistant_id text NOT NULL,
    session_identity_digest text NOT NULL,
    bound_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT research_sessions_agent_session_id_valid CHECK (
        agent_session_id = btrim(agent_session_id)
        AND char_length(agent_session_id) BETWEEN 1 AND 180
    ),
    CONSTRAINT research_sessions_fin_thread_id_valid CHECK (
        fin_thread_id = btrim(fin_thread_id)
        AND char_length(fin_thread_id) BETWEEN 1 AND 180
    ),
    CONSTRAINT research_sessions_assistant_id_valid CHECK (
        assistant_id = 'dell_reference_vertical'
    ),
    CONSTRAINT research_sessions_identity_digest_valid CHECK (
        session_identity_digest ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT research_sessions_session_thread_pair_unique
        UNIQUE (agent_session_id, server_thread_id)
);

CREATE TABLE IF NOT EXISTS fin_runtime.research_runs (
    research_run_id text PRIMARY KEY,
    agent_session_id text NOT NULL,
    parent_research_run_id text,
    run_identity_digest text NOT NULL,
    first_bound_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT research_runs_research_run_id_valid CHECK (
        research_run_id = btrim(research_run_id)
        AND char_length(research_run_id) BETWEEN 1 AND 180
    ),
    CONSTRAINT research_runs_identity_digest_valid CHECK (
        run_identity_digest ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT research_runs_run_session_pair_unique
        UNIQUE (research_run_id, agent_session_id),
    CONSTRAINT research_runs_session_fk
        FOREIGN KEY (agent_session_id)
        REFERENCES fin_runtime.research_sessions (agent_session_id),
    CONSTRAINT research_runs_parent_same_session_fk
        FOREIGN KEY (parent_research_run_id, agent_session_id)
        REFERENCES fin_runtime.research_runs (research_run_id, agent_session_id)
);

CREATE TABLE IF NOT EXISTS fin_runtime.research_run_invocations (
    run_invocation_id text PRIMARY KEY,
    research_run_id text NOT NULL,
    agent_session_id text NOT NULL,
    invocation_ordinal integer NOT NULL,
    canonical_invocation_kind text NOT NULL,
    server_invocation_kind text NOT NULL,
    server_thread_id uuid NOT NULL,
    server_run_id uuid NOT NULL UNIQUE,
    assistant_id text NOT NULL,
    invocation_identity_digest text NOT NULL,
    first_server_status text NOT NULL,
    bound_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT research_run_invocations_id_valid CHECK (
        run_invocation_id = btrim(run_invocation_id)
        AND char_length(run_invocation_id) BETWEEN 1 AND 180
    ),
    CONSTRAINT research_run_invocations_ordinal_valid CHECK (
        invocation_ordinal >= 1
    ),
    CONSTRAINT research_run_invocations_kind_valid CHECK (
        (
            invocation_ordinal = 1
            AND canonical_invocation_kind = 'START'
            AND server_invocation_kind = 'start'
        )
        OR (
            invocation_ordinal > 1
            AND canonical_invocation_kind IN ('RESUME', 'RECOVERY')
            AND server_invocation_kind = 'resume'
        )
    ),
    CONSTRAINT research_run_invocations_assistant_id_valid CHECK (
        assistant_id = 'dell_reference_vertical'
    ),
    CONSTRAINT research_run_invocations_identity_digest_valid CHECK (
        invocation_identity_digest ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT research_run_invocations_status_valid CHECK (
        first_server_status = btrim(first_server_status)
        AND char_length(first_server_status) BETWEEN 1 AND 80
    ),
    CONSTRAINT research_run_invocations_run_ordinal_unique
        UNIQUE (research_run_id, invocation_ordinal),
    CONSTRAINT research_run_invocations_run_session_fk
        FOREIGN KEY (research_run_id, agent_session_id)
        REFERENCES fin_runtime.research_runs (research_run_id, agent_session_id),
    CONSTRAINT research_run_invocations_session_thread_fk
        FOREIGN KEY (agent_session_id, server_thread_id)
        REFERENCES fin_runtime.research_sessions (agent_session_id, server_thread_id)
);

CREATE OR REPLACE FUNCTION fin_runtime.reject_durable_identity_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    RAISE EXCEPTION 'fin_runtime_durable_identity_is_append_only'
        USING ERRCODE = '55000';
END;
$function$;

DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_trigger
        WHERE tgname = 'research_sessions_reject_mutation'
          AND tgrelid = 'fin_runtime.research_sessions'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER research_sessions_reject_mutation
        BEFORE UPDATE OR DELETE ON fin_runtime.research_sessions
        FOR EACH ROW EXECUTE FUNCTION fin_runtime.reject_durable_identity_mutation();
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_trigger
        WHERE tgname = 'research_sessions_reject_truncate'
          AND tgrelid = 'fin_runtime.research_sessions'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER research_sessions_reject_truncate
        BEFORE TRUNCATE ON fin_runtime.research_sessions
        FOR EACH STATEMENT EXECUTE FUNCTION fin_runtime.reject_durable_identity_mutation();
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_trigger
        WHERE tgname = 'research_runs_reject_mutation'
          AND tgrelid = 'fin_runtime.research_runs'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER research_runs_reject_mutation
        BEFORE UPDATE OR DELETE ON fin_runtime.research_runs
        FOR EACH ROW EXECUTE FUNCTION fin_runtime.reject_durable_identity_mutation();
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_trigger
        WHERE tgname = 'research_runs_reject_truncate'
          AND tgrelid = 'fin_runtime.research_runs'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER research_runs_reject_truncate
        BEFORE TRUNCATE ON fin_runtime.research_runs
        FOR EACH STATEMENT EXECUTE FUNCTION fin_runtime.reject_durable_identity_mutation();
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_trigger
        WHERE tgname = 'research_run_invocations_reject_mutation'
          AND tgrelid = 'fin_runtime.research_run_invocations'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER research_run_invocations_reject_mutation
        BEFORE UPDATE OR DELETE ON fin_runtime.research_run_invocations
        FOR EACH ROW EXECUTE FUNCTION fin_runtime.reject_durable_identity_mutation();
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_trigger
        WHERE tgname = 'research_run_invocations_reject_truncate'
          AND tgrelid = 'fin_runtime.research_run_invocations'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER research_run_invocations_reject_truncate
        BEFORE TRUNCATE ON fin_runtime.research_run_invocations
        FOR EACH STATEMENT EXECUTE FUNCTION fin_runtime.reject_durable_identity_mutation();
    END IF;
END;
$migration$;

REVOKE ALL ON ALL TABLES IN SCHEMA fin_runtime FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA fin_runtime FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA fin_runtime FROM PUBLIC;
GRANT USAGE ON SCHEMA fin_runtime TO fin_runtime_app;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA fin_runtime TO fin_runtime_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA fin_runtime TO fin_runtime_app;
ALTER DEFAULT PRIVILEGES FOR ROLE fin_runtime_migrator IN SCHEMA fin_runtime
    GRANT SELECT, INSERT ON TABLES TO fin_runtime_app;
ALTER DEFAULT PRIVILEGES FOR ROLE fin_runtime_migrator IN SCHEMA fin_runtime
    GRANT USAGE, SELECT ON SEQUENCES TO fin_runtime_app;
REVOKE UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA fin_runtime
    FROM fin_runtime_app;

COMMENT ON SCHEMA fin_runtime IS
    'FIN-owned identity mappings; independent of Agent Server internal tables; schema_version=1.0';
COMMENT ON TABLE fin_runtime.research_sessions IS
    'AgentSession to server thread: one-to-one';
COMMENT ON TABLE fin_runtime.research_runs IS
    'ResearchRun identity aggregated over one or more immutable invocations';
COMMENT ON TABLE fin_runtime.research_run_invocations IS
    'RunInvocation to server run: one-to-one';
