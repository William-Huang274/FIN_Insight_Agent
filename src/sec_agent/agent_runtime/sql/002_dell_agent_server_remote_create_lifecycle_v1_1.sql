-- FIN-owned remote-create and canonical recovery bridge for the Dell vertical.
-- Extends the immutable v1.0 identity schema without reading or modifying
-- Agent Server implementation tables. Transaction control remains caller-owned.

SET LOCAL ROLE fin_runtime_migrator;

DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_constraint
        WHERE conname = 'research_run_invocations_id_server_run_unique'
          AND conrelid = 'fin_runtime.research_run_invocations'::regclass
    ) THEN
        ALTER TABLE fin_runtime.research_run_invocations
            ADD CONSTRAINT research_run_invocations_id_server_run_unique
            UNIQUE (run_invocation_id, server_run_id);
    END IF;
END;
$migration$;

CREATE OR REPLACE FUNCTION fin_runtime.canonical_timestamptz_or_null(
    value jsonb
)
RETURNS timestamptz
LANGUAGE plpgsql
IMMUTABLE
STRICT
AS $function$
DECLARE
    rendered text;
    parsed timestamptz;
BEGIN
    IF pg_catalog.jsonb_typeof(value) IS DISTINCT FROM 'string' THEN
        RETURN NULL;
    END IF;
    rendered := value #>> '{}';
    IF rendered !~
        '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]{1,6})?(Z|[+-][0-9]{2}:[0-9]{2})$'
    THEN
        RETURN NULL;
    END IF;
    BEGIN
        parsed := rendered::timestamptz;
    EXCEPTION WHEN OTHERS THEN
        RETURN NULL;
    END;
    IF NOT pg_catalog.isfinite(parsed) THEN
        RETURN NULL;
    END IF;
    RETURN parsed;
END;
$function$;

CREATE TABLE IF NOT EXISTS fin_runtime.agent_server_run_create_lifecycle (
    run_invocation_id text NOT NULL,
    lifecycle_ordinal integer NOT NULL,
    lifecycle_state text NOT NULL,
    research_run_id text NOT NULL,
    agent_session_id text NOT NULL,
    invocation_ordinal integer NOT NULL,
    canonical_invocation_kind text NOT NULL,
    server_invocation_kind text NOT NULL,
    server_thread_id uuid NOT NULL,
    assistant_id text NOT NULL,
    server_assistant_id uuid NOT NULL,
    execution_profile text NOT NULL,
    session_identity_digest text NOT NULL,
    research_run_identity_digest text NOT NULL,
    run_invocation_identity_digest text NOT NULL,
    launch_request_digest text NOT NULL,
    server_metadata_digest text NOT NULL,
    bound_run_invocation_id text,
    server_run_id uuid,
    server_run_status text,
    recovery_reason_code text,
    server_observation_digest text,
    final_binding_digest text,
    lifecycle_event_digest text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT agent_server_run_create_lifecycle_pk
        PRIMARY KEY (run_invocation_id, lifecycle_ordinal),
    CONSTRAINT agent_server_run_create_lifecycle_event_unique
        UNIQUE (run_invocation_id, lifecycle_event_digest),
    CONSTRAINT agent_server_run_create_lifecycle_run_ordinal_event_unique
        UNIQUE (research_run_id, invocation_ordinal, lifecycle_event_digest),
    CONSTRAINT agent_server_run_create_lifecycle_ids_valid CHECK (
        run_invocation_id = btrim(run_invocation_id)
        AND char_length(run_invocation_id) BETWEEN 1 AND 180
        AND research_run_id = btrim(research_run_id)
        AND char_length(research_run_id) BETWEEN 1 AND 180
        AND agent_session_id = btrim(agent_session_id)
        AND char_length(agent_session_id) BETWEEN 1 AND 180
        AND invocation_ordinal >= 1
    ),
    CONSTRAINT agent_server_run_create_lifecycle_kind_valid CHECK (
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
    CONSTRAINT agent_server_run_create_lifecycle_authority_valid CHECK (
        assistant_id = 'dell_reference_vertical'
        AND execution_profile IN ('product', 'zero_model_control_plane_v1')
    ),
    CONSTRAINT agent_server_run_create_lifecycle_digests_valid CHECK (
        session_identity_digest ~ '^[0-9a-f]{64}$'
        AND research_run_identity_digest ~ '^[0-9a-f]{64}$'
        AND run_invocation_identity_digest ~ '^[0-9a-f]{64}$'
        AND launch_request_digest ~ '^[0-9a-f]{64}$'
        AND server_metadata_digest ~ '^[0-9a-f]{64}$'
        AND lifecycle_event_digest ~ '^[0-9a-f]{64}$'
        AND (
            server_observation_digest IS NULL
            OR server_observation_digest ~ '^[0-9a-f]{64}$'
        )
        AND (
            final_binding_digest IS NULL
            OR final_binding_digest ~ '^[0-9a-f]{64}$'
        )
    ),
    CONSTRAINT agent_server_run_create_lifecycle_remote_pair_valid CHECK (
        (server_run_status IS NULL OR server_run_id IS NOT NULL)
        AND (
            server_run_status IS NULL
            OR server_run_status IN (
                'pending', 'running', 'error', 'success', 'timeout',
                'interrupted'
            )
        )
    ),
    CONSTRAINT agent_server_run_create_lifecycle_reason_valid CHECK (
        recovery_reason_code IS NULL
        OR (
            recovery_reason_code = btrim(recovery_reason_code)
            AND char_length(recovery_reason_code) BETWEEN 1 AND 120
        )
    ),
    CONSTRAINT agent_server_run_create_lifecycle_transition_shape CHECK (
        (
            lifecycle_state = 'PENDING'
            AND lifecycle_ordinal = 1
            AND bound_run_invocation_id IS NULL
            AND server_run_id IS NULL
            AND server_run_status IS NULL
            AND recovery_reason_code IS NULL
            AND server_observation_digest IS NULL
            AND final_binding_digest IS NULL
        )
        OR (
            lifecycle_state = 'DISPATCHED'
            AND lifecycle_ordinal = 2
            AND bound_run_invocation_id IS NULL
            AND server_run_id IS NULL
            AND server_run_status IS NULL
            AND recovery_reason_code IS NULL
            AND server_observation_digest IS NULL
            AND final_binding_digest IS NULL
        )
        OR (
            lifecycle_state = 'ORPHAN'
            AND lifecycle_ordinal >= 3
            AND bound_run_invocation_id IS NULL
            AND recovery_reason_code IS NOT NULL
            AND server_observation_digest IS NOT NULL
            AND final_binding_digest IS NULL
        )
        OR (
            lifecycle_state = 'RECONCILED'
            AND lifecycle_ordinal >= 3
            AND bound_run_invocation_id = run_invocation_id
            AND server_run_id IS NOT NULL
            AND server_run_status IS NOT NULL
            AND recovery_reason_code IS NOT NULL
            AND server_observation_digest IS NOT NULL
            AND final_binding_digest IS NOT NULL
        )
    ),
    CONSTRAINT agent_server_run_create_lifecycle_session_thread_fk
        FOREIGN KEY (agent_session_id, server_thread_id)
        REFERENCES fin_runtime.research_sessions (agent_session_id, server_thread_id),
    CONSTRAINT agent_server_run_create_lifecycle_final_binding_fk
        FOREIGN KEY (bound_run_invocation_id, server_run_id)
        REFERENCES fin_runtime.research_run_invocations (
            run_invocation_id,
            server_run_id
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS
    agent_server_run_create_lifecycle_single_pending
    ON fin_runtime.agent_server_run_create_lifecycle (run_invocation_id)
    WHERE lifecycle_state = 'PENDING';
CREATE UNIQUE INDEX IF NOT EXISTS
    agent_server_run_create_lifecycle_run_ordinal_pending_unique
    ON fin_runtime.agent_server_run_create_lifecycle (
        research_run_id,
        invocation_ordinal
    )
    WHERE lifecycle_state = 'PENDING';
CREATE UNIQUE INDEX IF NOT EXISTS
    agent_server_run_create_lifecycle_single_dispatched
    ON fin_runtime.agent_server_run_create_lifecycle (run_invocation_id)
    WHERE lifecycle_state = 'DISPATCHED';
CREATE UNIQUE INDEX IF NOT EXISTS
    agent_server_run_create_lifecycle_single_reconciled
    ON fin_runtime.agent_server_run_create_lifecycle (run_invocation_id)
    WHERE lifecycle_state = 'RECONCILED';
CREATE UNIQUE INDEX IF NOT EXISTS
    agent_server_run_create_lifecycle_observation_unique
    ON fin_runtime.agent_server_run_create_lifecycle (
        run_invocation_id,
        server_observation_digest
    )
    WHERE lifecycle_state = 'ORPHAN';

CREATE TABLE IF NOT EXISTS fin_runtime.agent_server_action_attempt_snapshots (
    run_invocation_id text NOT NULL,
    snapshot_ordinal smallint NOT NULL,
    action_state text NOT NULL,
    action_outcome text,
    action_attempt_id text NOT NULL,
    action_attempt_digest text NOT NULL,
    canonical_action_attempt jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT agent_server_action_attempt_snapshots_pk
        PRIMARY KEY (run_invocation_id, snapshot_ordinal),
    CONSTRAINT agent_server_action_attempt_snapshots_state_unique
        UNIQUE (run_invocation_id, action_state),
    CONSTRAINT agent_server_action_attempt_snapshots_digest_unique
        UNIQUE (run_invocation_id, action_attempt_digest),
    CONSTRAINT agent_server_action_attempt_snapshots_shape CHECK (
        (
            snapshot_ordinal = 1
            AND action_state = 'INTENT_COMMITTED'
            AND action_outcome IS NULL
        )
        OR (
            snapshot_ordinal = 2
            AND action_state = 'DISPATCHED'
            AND action_outcome IS NULL
        )
        OR (
            snapshot_ordinal = 2
            AND action_state = 'TERMINAL'
            AND action_outcome = 'FAILED_BEFORE_DISPATCH'
        )
        OR (
            snapshot_ordinal = 3
            AND action_state = 'TERMINAL'
            AND action_outcome IN ('APPLIED', 'AMBIGUOUS_AFTER_DISPATCH')
        )
    ),
    CONSTRAINT agent_server_action_attempt_snapshots_digest_valid CHECK ((
        action_attempt_digest ~ '^[0-9a-f]{64}$'
        AND jsonb_typeof(canonical_action_attempt) = 'object'
        AND canonical_action_attempt - ARRAY[
            'schema_version', 'action_attempt_id', 'session_id', 'run_id',
            'run_invocation_id', 'actor_id', 'action_kind', 'action_name',
            'request_ref', 'request_digest', 'state', 'outcome',
            'was_dispatched', 'potentially_chargeable', 'receipt_kind',
            'receipt_ref', 'receipt_digest', 'failure_code',
            'parent_action_attempt_id', 'created_at', 'terminal_at',
            'action_attempt_digest'
        ]::text[] = '{}'::jsonb
        AND action_attempt_id =
            'ACTION::AGENT_SERVER_RUN_CREATE::' || run_invocation_id
        AND canonical_action_attempt @> pg_catalog.jsonb_build_object(
            'schema_version', 'fin_ia_action_attempt_v1_2',
            'action_attempt_id', action_attempt_id,
            'run_invocation_id', run_invocation_id,
            'actor_id', 'runtime://fin-agent-server-client',
            'action_kind', 'TOOL',
            'action_name', 'langgraph_agent_server.runs.create',
            'request_ref',
                'fin-runtime://agent-server/run-create/' || run_invocation_id,
            'state', action_state,
            'outcome', action_outcome,
            'action_attempt_digest', action_attempt_digest
        )
        AND jsonb_typeof(canonical_action_attempt -> 'session_id') = 'string'
        AND btrim(canonical_action_attempt ->> 'session_id') <> ''
        AND jsonb_typeof(canonical_action_attempt -> 'run_id') = 'string'
        AND btrim(canonical_action_attempt ->> 'run_id') <> ''
        AND jsonb_typeof(canonical_action_attempt -> 'request_digest') = 'string'
        AND canonical_action_attempt ->> 'request_digest' ~ '^[0-9a-f]{64}$'
        AND jsonb_typeof(canonical_action_attempt -> 'created_at') = 'string'
        AND fin_runtime.canonical_timestamptz_or_null(
            canonical_action_attempt -> 'created_at'
        ) IS NOT NULL
    ) IS TRUE),
    CONSTRAINT agent_server_action_attempt_snapshots_profile_valid CHECK ((
        canonical_action_attempt @> '{"parent_action_attempt_id": null}'::jsonb
        AND (
            (
                action_state = 'INTENT_COMMITTED'
                AND canonical_action_attempt @> '{
                    "was_dispatched": false,
                    "potentially_chargeable": false,
                    "receipt_kind": null,
                    "receipt_ref": null,
                    "receipt_digest": null,
                    "failure_code": null,
                    "terminal_at": null
                }'::jsonb
            )
            OR (
                action_state = 'DISPATCHED'
                AND canonical_action_attempt @> '{
                    "was_dispatched": true,
                    "potentially_chargeable": true,
                    "receipt_kind": null,
                    "receipt_ref": null,
                    "receipt_digest": null,
                    "failure_code": null,
                    "terminal_at": null
                }'::jsonb
            )
            OR (
                action_state = 'TERMINAL'
                AND action_outcome = 'FAILED_BEFORE_DISPATCH'
                AND canonical_action_attempt @> '{
                    "was_dispatched": false,
                    "potentially_chargeable": false,
                    "receipt_kind": null,
                    "receipt_ref": null,
                    "receipt_digest": null,
                    "failure_code": null
                }'::jsonb
                AND jsonb_typeof(
                    canonical_action_attempt -> 'terminal_at'
                ) = 'string'
                AND fin_runtime.canonical_timestamptz_or_null(
                    canonical_action_attempt -> 'terminal_at'
                ) >= fin_runtime.canonical_timestamptz_or_null(
                    canonical_action_attempt -> 'created_at'
                )
            )
            OR (
                action_state = 'TERMINAL'
                AND action_outcome = 'APPLIED'
                AND canonical_action_attempt @> '{
                    "was_dispatched": true,
                    "potentially_chargeable": true,
                    "receipt_kind": "SUCCESS",
                    "failure_code": null
                }'::jsonb
                AND jsonb_typeof(canonical_action_attempt -> 'receipt_ref') =
                    'string'
                AND btrim(canonical_action_attempt ->> 'receipt_ref') <> ''
                AND jsonb_typeof(canonical_action_attempt -> 'receipt_digest') =
                    'string'
                AND canonical_action_attempt ->> 'receipt_digest' ~
                    '^[0-9a-f]{64}$'
                AND jsonb_typeof(
                    canonical_action_attempt -> 'terminal_at'
                ) = 'string'
                AND fin_runtime.canonical_timestamptz_or_null(
                    canonical_action_attempt -> 'terminal_at'
                ) >= fin_runtime.canonical_timestamptz_or_null(
                    canonical_action_attempt -> 'created_at'
                )
            )
            OR (
                action_state = 'TERMINAL'
                AND action_outcome = 'AMBIGUOUS_AFTER_DISPATCH'
                AND canonical_action_attempt @> '{
                    "was_dispatched": true,
                    "potentially_chargeable": true,
                    "receipt_kind": null,
                    "receipt_ref": null,
                    "receipt_digest": null,
                    "failure_code": null
                }'::jsonb
                AND jsonb_typeof(
                    canonical_action_attempt -> 'terminal_at'
                ) = 'string'
                AND fin_runtime.canonical_timestamptz_or_null(
                    canonical_action_attempt -> 'terminal_at'
                ) >= fin_runtime.canonical_timestamptz_or_null(
                    canonical_action_attempt -> 'created_at'
                )
            )
        )
    ) IS TRUE)
);

CREATE TABLE IF NOT EXISTS fin_runtime.agent_server_recovery_cases (
    recovery_case_id text NOT NULL,
    run_invocation_id text NOT NULL UNIQUE,
    research_run_id text NOT NULL,
    agent_session_id text NOT NULL,
    recovery_research_run_digest text NOT NULL,
    source_run_invocation_digest text NOT NULL,
    ambiguous_action_attempt_id text NOT NULL,
    ambiguous_action_attempt_digest text NOT NULL,
    lifecycle_event_digest text NOT NULL,
    recovery_reason_code text NOT NULL,
    server_run_id uuid,
    server_run_status text,
    canonical_recovery_research_run jsonb NOT NULL,
    canonical_source_run_invocation jsonb NOT NULL,
    canonical_ambiguous_action_attempt jsonb NOT NULL,
    opened_at timestamptz NOT NULL,
    recovery_case_digest text NOT NULL UNIQUE,
    CONSTRAINT agent_server_recovery_cases_pk
        PRIMARY KEY (recovery_case_id),
    CONSTRAINT agent_server_recovery_cases_identity_valid CHECK (
        recovery_case_id = btrim(recovery_case_id)
        AND char_length(recovery_case_id) BETWEEN 1 AND 240
        AND pg_catalog.isfinite(opened_at)
    ),
    CONSTRAINT agent_server_recovery_cases_id_pair_unique
        UNIQUE (recovery_case_id, run_invocation_id),
    CONSTRAINT agent_server_recovery_cases_digests_valid CHECK (
        recovery_research_run_digest ~ '^[0-9a-f]{64}$'
        AND source_run_invocation_digest ~ '^[0-9a-f]{64}$'
        AND ambiguous_action_attempt_digest ~ '^[0-9a-f]{64}$'
        AND lifecycle_event_digest ~ '^[0-9a-f]{64}$'
        AND recovery_case_digest ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT agent_server_recovery_cases_remote_pair_valid CHECK (
        (server_run_status IS NULL OR server_run_id IS NOT NULL)
        AND (
            server_run_status IS NULL
            OR server_run_status IN (
                'pending', 'running', 'error', 'success', 'timeout',
                'interrupted'
            )
        )
    ),
    CONSTRAINT agent_server_recovery_cases_payload_valid CHECK ((
        jsonb_typeof(canonical_recovery_research_run) = 'object'
        AND jsonb_typeof(canonical_source_run_invocation) = 'object'
        AND jsonb_typeof(canonical_ambiguous_action_attempt) = 'object'
        AND canonical_recovery_research_run ?& ARRAY[
            'schema_version', 'run_id', 'session_id', 'parent_run_id',
            'origin_kind', 'legacy_paid_full_chain_execution_label',
            'status', 'base_plan_ref', 'base_plan_digest',
            'current_plan_ref', 'current_plan_digest',
            'last_session_sequence', 'created_at', 'terminal_at', 'run_digest'
        ]::text[]
        AND canonical_recovery_research_run - ARRAY[
            'schema_version', 'run_id', 'session_id', 'parent_run_id',
            'origin_kind', 'legacy_paid_full_chain_execution_label',
            'status', 'base_plan_ref', 'base_plan_digest',
            'current_plan_ref', 'current_plan_digest',
            'last_session_sequence', 'created_at', 'terminal_at', 'run_digest'
        ]::text[] = '{}'::jsonb
        AND canonical_source_run_invocation ?& ARRAY[
            'schema_version', 'invocation_id', 'session_id', 'run_id',
            'ordinal', 'invocation_kind', 'status', 'trigger_ref', 'lease_ref',
            'started_at', 'finished_at', 'invocation_digest'
        ]::text[]
        AND canonical_source_run_invocation - ARRAY[
            'schema_version', 'invocation_id', 'session_id', 'run_id',
            'ordinal', 'invocation_kind', 'status', 'trigger_ref', 'lease_ref',
            'started_at', 'finished_at', 'invocation_digest'
        ]::text[] = '{}'::jsonb
        AND canonical_ambiguous_action_attempt ?& ARRAY[
            'schema_version', 'action_attempt_id', 'session_id', 'run_id',
            'run_invocation_id', 'actor_id', 'action_kind', 'action_name',
            'request_ref', 'request_digest', 'state', 'outcome',
            'was_dispatched', 'potentially_chargeable', 'receipt_kind',
            'receipt_ref', 'receipt_digest', 'failure_code',
            'parent_action_attempt_id', 'created_at', 'terminal_at',
            'action_attempt_digest'
        ]::text[]
        AND canonical_ambiguous_action_attempt - ARRAY[
            'schema_version', 'action_attempt_id', 'session_id', 'run_id',
            'run_invocation_id', 'actor_id', 'action_kind', 'action_name',
            'request_ref', 'request_digest', 'state', 'outcome',
            'was_dispatched', 'potentially_chargeable', 'receipt_kind',
            'receipt_ref', 'receipt_digest', 'failure_code',
            'parent_action_attempt_id', 'created_at', 'terminal_at',
            'action_attempt_digest'
        ]::text[] = '{}'::jsonb
        AND canonical_recovery_research_run @> pg_catalog.jsonb_build_object(
            'schema_version', 'fin_ia_research_run_v1_2',
            'run_id', research_run_id,
            'session_id', agent_session_id,
            'status', 'RECOVERY_REQUIRED',
            'run_digest', recovery_research_run_digest,
            'terminal_at', NULL
        )
        AND jsonb_typeof(
            canonical_recovery_research_run -> 'created_at'
        ) = 'string'
        AND fin_runtime.canonical_timestamptz_or_null(
            canonical_recovery_research_run -> 'created_at'
        ) IS NOT NULL
        AND jsonb_typeof(
            canonical_recovery_research_run -> 'origin_kind'
        ) = 'string'
        AND (
            (
                canonical_recovery_research_run ->> 'origin_kind' = 'INITIAL'
                AND canonical_recovery_research_run @>
                    '{"parent_run_id": null}'::jsonb
            )
            OR (
                canonical_recovery_research_run ->> 'origin_kind' = 'FOLLOW_UP'
                AND jsonb_typeof(
                    canonical_recovery_research_run -> 'parent_run_id'
                ) = 'string'
                AND btrim(
                    canonical_recovery_research_run ->> 'parent_run_id'
                ) <> ''
                AND canonical_recovery_research_run ->> 'parent_run_id' <>
                    research_run_id
            )
        )
        AND canonical_recovery_research_run @>
            '{"legacy_paid_full_chain_execution_label": null}'::jsonb
        AND jsonb_typeof(
            canonical_recovery_research_run -> 'base_plan_ref'
        ) = 'string'
        AND btrim(canonical_recovery_research_run ->> 'base_plan_ref') <> ''
        AND jsonb_typeof(
            canonical_recovery_research_run -> 'base_plan_digest'
        ) = 'string'
        AND canonical_recovery_research_run ->> 'base_plan_digest' ~
            '^[0-9a-f]{64}$'
        AND jsonb_typeof(
            canonical_recovery_research_run -> 'current_plan_ref'
        ) = 'string'
        AND btrim(canonical_recovery_research_run ->> 'current_plan_ref') <> ''
        AND jsonb_typeof(
            canonical_recovery_research_run -> 'current_plan_digest'
        ) = 'string'
        AND canonical_recovery_research_run ->> 'current_plan_digest' ~
            '^[0-9a-f]{64}$'
        AND jsonb_typeof(
            canonical_recovery_research_run -> 'last_session_sequence'
        ) = 'number'
        AND canonical_recovery_research_run ->> 'last_session_sequence' ~
            '^(0|[1-9][0-9]*)$'
        AND canonical_source_run_invocation @> pg_catalog.jsonb_build_object(
            'schema_version', 'fin_ia_run_invocation_v1_2',
            'invocation_id', run_invocation_id,
            'run_id', research_run_id,
            'session_id', agent_session_id,
            'status', 'INTERRUPTED',
            'invocation_digest', source_run_invocation_digest
        )
        AND jsonb_typeof(
            canonical_source_run_invocation -> 'ordinal'
        ) = 'number'
        AND canonical_source_run_invocation ->> 'ordinal' ~ '^[1-9][0-9]*$'
        AND jsonb_typeof(
            canonical_source_run_invocation -> 'invocation_kind'
        ) = 'string'
        AND canonical_source_run_invocation ->> 'invocation_kind' IN (
            'START', 'RESUME', 'RECOVERY'
        )
        AND jsonb_typeof(
            canonical_source_run_invocation -> 'started_at'
        ) = 'string'
        AND fin_runtime.canonical_timestamptz_or_null(
            canonical_source_run_invocation -> 'started_at'
        ) IS NOT NULL
        AND jsonb_typeof(
            canonical_source_run_invocation -> 'trigger_ref'
        ) = 'string'
        AND btrim(canonical_source_run_invocation ->> 'trigger_ref') <> ''
        AND (
            canonical_source_run_invocation @> '{"lease_ref": null}'::jsonb
            OR (
                jsonb_typeof(
                    canonical_source_run_invocation -> 'lease_ref'
                ) = 'string'
                AND btrim(
                    canonical_source_run_invocation ->> 'lease_ref'
                ) <> ''
            )
        )
        AND (
            (
                canonical_source_run_invocation ->> 'ordinal' = '1'
                AND canonical_source_run_invocation ->> 'invocation_kind' =
                    'START'
            )
            OR (
                canonical_source_run_invocation ->> 'ordinal' ~
                    '^([2-9]|[1-9][0-9]+)$'
                AND canonical_source_run_invocation ->> 'invocation_kind' IN (
                    'RESUME', 'RECOVERY'
                )
            )
        )
        AND canonical_ambiguous_action_attempt @> pg_catalog.jsonb_build_object(
            'schema_version', 'fin_ia_action_attempt_v1_2',
            'action_attempt_id', ambiguous_action_attempt_id,
            'run_invocation_id', run_invocation_id,
            'run_id', research_run_id,
            'session_id', agent_session_id,
            'state', 'TERMINAL',
            'outcome', 'AMBIGUOUS_AFTER_DISPATCH',
            'action_attempt_digest', ambiguous_action_attempt_digest,
            'was_dispatched', TRUE,
            'potentially_chargeable', TRUE,
            'receipt_kind', NULL,
            'receipt_ref', NULL,
            'receipt_digest', NULL,
            'failure_code', NULL
        )
        AND jsonb_typeof(
            canonical_source_run_invocation -> 'finished_at'
        ) = 'string'
        AND fin_runtime.canonical_timestamptz_or_null(
            canonical_source_run_invocation -> 'finished_at'
        ) >= fin_runtime.canonical_timestamptz_or_null(
            canonical_source_run_invocation -> 'started_at'
        )
        AND jsonb_typeof(
            canonical_ambiguous_action_attempt -> 'terminal_at'
        ) = 'string'
        AND jsonb_typeof(
            canonical_ambiguous_action_attempt -> 'created_at'
        ) = 'string'
        AND fin_runtime.canonical_timestamptz_or_null(
            canonical_ambiguous_action_attempt -> 'terminal_at'
        ) >= fin_runtime.canonical_timestamptz_or_null(
            canonical_ambiguous_action_attempt -> 'created_at'
        )
        AND fin_runtime.canonical_timestamptz_or_null(
            canonical_source_run_invocation -> 'finished_at'
        ) >= fin_runtime.canonical_timestamptz_or_null(
            canonical_ambiguous_action_attempt -> 'terminal_at'
        )
        AND opened_at >= fin_runtime.canonical_timestamptz_or_null(
            canonical_source_run_invocation -> 'finished_at'
        )
    ) IS TRUE),
    CONSTRAINT agent_server_recovery_cases_action_fk
        FOREIGN KEY (run_invocation_id, ambiguous_action_attempt_digest)
        REFERENCES fin_runtime.agent_server_action_attempt_snapshots (
            run_invocation_id,
            action_attempt_digest
        ) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT agent_server_recovery_cases_lifecycle_fk
        FOREIGN KEY (run_invocation_id, lifecycle_event_digest)
        REFERENCES fin_runtime.agent_server_run_create_lifecycle (
            run_invocation_id,
            lifecycle_event_digest
        )
);

CREATE TABLE IF NOT EXISTS fin_runtime.agent_server_recovery_dispositions (
    recovery_disposition_id text NOT NULL,
    recovery_case_id text NOT NULL,
    run_invocation_id text NOT NULL,
    agent_session_id text NOT NULL,
    research_run_id text NOT NULL,
    research_run_digest text NOT NULL,
    ambiguous_action_attempt_id text NOT NULL,
    ambiguous_action_attempt_digest text NOT NULL,
    source_run_invocation_id text NOT NULL,
    source_run_invocation_digest text NOT NULL,
    recovery_decision text NOT NULL,
    decision_authority_ref text NOT NULL,
    recovery_disposition_digest text NOT NULL UNIQUE,
    canonical_recovery_disposition jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT agent_server_recovery_dispositions_pk
        PRIMARY KEY (recovery_disposition_id),
    CONSTRAINT agent_server_recovery_dispositions_identity_valid CHECK (
        recovery_disposition_id = btrim(recovery_disposition_id)
        AND char_length(recovery_disposition_id) BETWEEN 1 AND 240
    ),
    CONSTRAINT agent_server_recovery_dispositions_case_unique
        UNIQUE (recovery_case_id),
    CONSTRAINT agent_server_recovery_dispositions_invocation_unique
        UNIQUE (run_invocation_id),
    CONSTRAINT agent_server_recovery_dispositions_decision_valid CHECK (
        recovery_decision IN (
            'DO_NOT_RETRY',
            'ABANDON_RUN'
        )
    ),
    CONSTRAINT agent_server_recovery_dispositions_payload_valid CHECK ((
        research_run_digest ~ '^[0-9a-f]{64}$'
        AND ambiguous_action_attempt_digest ~ '^[0-9a-f]{64}$'
        AND source_run_invocation_digest ~ '^[0-9a-f]{64}$'
        AND recovery_disposition_digest ~ '^[0-9a-f]{64}$'
        AND jsonb_typeof(canonical_recovery_disposition) = 'object'
        AND canonical_recovery_disposition ?& ARRAY[
            'schema_version', 'recovery_disposition_id', 'session_id',
            'run_id', 'research_run_digest', 'ambiguous_action_attempt_id',
            'ambiguous_action_attempt_digest', 'source_run_invocation_id',
            'source_run_invocation_digest', 'investigation_receipt_refs',
            'potentially_duplicate_cost', 'decision',
            'decision_authority_ref', 'next_run_invocation_id',
            'next_run_invocation_digest', 'replacement_action_attempt_id',
            'replacement_action_attempt_digest', 'created_at',
            'recovery_disposition_digest'
        ]::text[]
        AND canonical_recovery_disposition - ARRAY[
            'schema_version', 'recovery_disposition_id', 'session_id',
            'run_id', 'research_run_digest', 'ambiguous_action_attempt_id',
            'ambiguous_action_attempt_digest', 'source_run_invocation_id',
            'source_run_invocation_digest', 'investigation_receipt_refs',
            'potentially_duplicate_cost', 'decision',
            'decision_authority_ref', 'next_run_invocation_id',
            'next_run_invocation_digest', 'replacement_action_attempt_id',
            'replacement_action_attempt_digest', 'created_at',
            'recovery_disposition_digest'
        ]::text[] = '{}'::jsonb
        AND canonical_recovery_disposition @> pg_catalog.jsonb_build_object(
            'schema_version', 'fin_ia_recovery_disposition_v1_2',
            'recovery_disposition_id', recovery_disposition_id,
            'decision', recovery_decision,
            'session_id', agent_session_id,
            'run_id', research_run_id,
            'research_run_digest', research_run_digest,
            'ambiguous_action_attempt_id', ambiguous_action_attempt_id,
            'ambiguous_action_attempt_digest', ambiguous_action_attempt_digest,
            'source_run_invocation_id', source_run_invocation_id,
            'source_run_invocation_digest', source_run_invocation_digest,
            'decision_authority_ref', decision_authority_ref,
            'recovery_disposition_digest', recovery_disposition_digest,
            'potentially_duplicate_cost', TRUE,
            'next_run_invocation_id', NULL,
            'next_run_invocation_digest', NULL,
            'replacement_action_attempt_id', NULL,
            'replacement_action_attempt_digest', NULL
        )
        AND decision_authority_ref = btrim(decision_authority_ref)
        AND char_length(decision_authority_ref) BETWEEN 1 AND 240
        AND jsonb_typeof(
            canonical_recovery_disposition -> 'investigation_receipt_refs'
        ) = 'array'
        AND jsonb_array_length(
            canonical_recovery_disposition -> 'investigation_receipt_refs'
        ) >= 1
        AND jsonb_typeof(
            canonical_recovery_disposition -> 'potentially_duplicate_cost'
        ) = 'boolean'
        AND jsonb_typeof(
            canonical_recovery_disposition -> 'created_at'
        ) = 'string'
    ) IS TRUE),
    CONSTRAINT agent_server_recovery_dispositions_case_fk
        FOREIGN KEY (recovery_case_id, run_invocation_id)
        REFERENCES fin_runtime.agent_server_recovery_cases (
            recovery_case_id,
            run_invocation_id
        )
);

CREATE OR REPLACE FUNCTION fin_runtime.require_valid_recovery_case()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM fin_runtime.agent_server_run_create_lifecycle AS orphan
        WHERE orphan.run_invocation_id = NEW.run_invocation_id
          AND orphan.lifecycle_state = 'ORPHAN'
          AND orphan.lifecycle_event_digest = NEW.lifecycle_event_digest
          AND orphan.research_run_id = NEW.research_run_id
          AND orphan.agent_session_id = NEW.agent_session_id
          AND orphan.invocation_ordinal::text =
              NEW.canonical_source_run_invocation ->> 'ordinal'
          AND orphan.canonical_invocation_kind =
              NEW.canonical_source_run_invocation ->> 'invocation_kind'
          AND orphan.recovery_reason_code = NEW.recovery_reason_code
          AND orphan.server_run_id IS NOT DISTINCT FROM NEW.server_run_id
          AND orphan.server_run_status IS NOT DISTINCT FROM NEW.server_run_status
          AND orphan.server_observation_digest IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'fin_runtime_recovery_case_orphan_binding_invalid'
            USING ERRCODE = '23514';
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM fin_runtime.agent_server_action_attempt_snapshots AS action
        WHERE action.run_invocation_id = NEW.run_invocation_id
          AND action.action_state = 'TERMINAL'
          AND action.action_outcome = 'AMBIGUOUS_AFTER_DISPATCH'
          AND action.action_attempt_id = NEW.ambiguous_action_attempt_id
          AND action.action_attempt_digest =
              NEW.ambiguous_action_attempt_digest
          AND action.canonical_action_attempt =
              NEW.canonical_ambiguous_action_attempt
    ) THEN
        RAISE EXCEPTION 'fin_runtime_recovery_case_ambiguous_action_invalid'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION fin_runtime.require_valid_recovery_disposition()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    canonical_created_at timestamptz;
BEGIN
    canonical_created_at := fin_runtime.canonical_timestamptz_or_null(
        NEW.canonical_recovery_disposition -> 'created_at'
    );
    IF canonical_created_at IS NULL THEN
        RAISE EXCEPTION 'fin_runtime_recovery_disposition_time_invalid'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.recovery_decision NOT IN ('DO_NOT_RETRY', 'ABANDON_RUN') THEN
        RAISE EXCEPTION 'fin_runtime_recovery_disposition_decision_unsupported'
            USING ERRCODE = '23514';
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM fin_runtime.agent_server_recovery_cases AS recovery
        WHERE recovery.recovery_case_id = NEW.recovery_case_id
          AND recovery.run_invocation_id = NEW.run_invocation_id
          AND recovery.agent_session_id = NEW.agent_session_id
          AND recovery.research_run_id = NEW.research_run_id
          AND recovery.recovery_research_run_digest = NEW.research_run_digest
          AND recovery.ambiguous_action_attempt_id =
              NEW.ambiguous_action_attempt_id
          AND recovery.ambiguous_action_attempt_digest =
              NEW.ambiguous_action_attempt_digest
          AND recovery.run_invocation_id = NEW.source_run_invocation_id
          AND recovery.source_run_invocation_digest =
              NEW.source_run_invocation_digest
          AND recovery.canonical_ambiguous_action_attempt ->
              'potentially_chargeable' =
              NEW.canonical_recovery_disposition ->
              'potentially_duplicate_cost'
    ) THEN
        RAISE EXCEPTION 'fin_runtime_recovery_disposition_case_binding_invalid'
            USING ERRCODE = '23514';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM jsonb_array_elements(
            NEW.canonical_recovery_disposition -> 'investigation_receipt_refs'
        ) AS receipt(value)
        WHERE jsonb_typeof(receipt.value) <> 'string'
           OR btrim(receipt.value #>> '{}') = ''
    ) OR (
        SELECT COUNT(*)
        FROM jsonb_array_elements_text(
            NEW.canonical_recovery_disposition -> 'investigation_receipt_refs'
        )
    ) <> (
        SELECT COUNT(DISTINCT receipt)
        FROM jsonb_array_elements_text(
            NEW.canonical_recovery_disposition -> 'investigation_receipt_refs'
        ) AS receipt
    ) THEN
        RAISE EXCEPTION 'fin_runtime_recovery_disposition_receipts_invalid'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.canonical_recovery_disposition ->> 'next_run_invocation_id'
            IS NOT NULL
       OR NEW.canonical_recovery_disposition ->> 'next_run_invocation_digest'
            IS NOT NULL
       OR NEW.canonical_recovery_disposition ->>
            'replacement_action_attempt_id' IS NOT NULL
       OR NEW.canonical_recovery_disposition ->>
            'replacement_action_attempt_digest' IS NOT NULL THEN
        RAISE EXCEPTION 'fin_runtime_recovery_disposition_continuation_unsupported'
            USING ERRCODE = '23514';
    END IF;
    IF canonical_created_at < (
        SELECT recovery.opened_at
        FROM fin_runtime.agent_server_recovery_cases AS recovery
        WHERE recovery.recovery_case_id = NEW.recovery_case_id
    ) OR canonical_created_at < (
        SELECT (
            recovery.canonical_ambiguous_action_attempt ->> 'terminal_at'
        )::timestamptz
        FROM fin_runtime.agent_server_recovery_cases AS recovery
        WHERE recovery.recovery_case_id = NEW.recovery_case_id
    ) THEN
        RAISE EXCEPTION 'fin_runtime_recovery_disposition_time_invalid'
            USING ERRCODE = '23514';
    END IF;
    IF canonical_created_at > clock_timestamp() + interval '5 minutes' THEN
        RAISE EXCEPTION 'fin_runtime_recovery_disposition_time_invalid'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.recovery_decision = 'DO_NOT_RETRY' AND (
        (
            SELECT COUNT(DISTINCT observed.server_run_id)
            FROM fin_runtime.agent_server_run_create_lifecycle AS observed
            WHERE observed.run_invocation_id = NEW.run_invocation_id
              AND observed.lifecycle_state = 'ORPHAN'
              AND observed.server_run_id IS NOT NULL
              AND observed.server_run_status IS NOT NULL
        ) <> 1
        OR NOT EXISTS (
            SELECT 1
            FROM fin_runtime.agent_server_run_create_lifecycle AS observed
            WHERE observed.run_invocation_id = NEW.run_invocation_id
              AND observed.lifecycle_state = 'ORPHAN'
              AND observed.server_run_id IS NOT NULL
              AND observed.server_run_status IS NOT NULL
              AND observed.recorded_at <= canonical_created_at
        )
    ) THEN
        RAISE EXCEPTION 'fin_runtime_recovery_disposition_exact_observation_required'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION fin_runtime.append_recovery_disposition(
    recovery_case_id text,
    canonical_disposition jsonb
)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, fin_runtime
AS $function$
DECLARE
    inserted_digest text;
BEGIN
    IF session_user <> 'fin_runtime_operator' THEN
        RAISE EXCEPTION 'fin_runtime_recovery_operator_authority_required'
            USING ERRCODE = '42501';
    END IF;
    INSERT INTO fin_runtime.agent_server_recovery_dispositions (
        recovery_disposition_id, recovery_case_id, run_invocation_id,
        agent_session_id, research_run_id, research_run_digest,
        ambiguous_action_attempt_id, ambiguous_action_attempt_digest,
        source_run_invocation_id, source_run_invocation_digest,
        recovery_decision, decision_authority_ref,
        recovery_disposition_digest, canonical_recovery_disposition
    )
    VALUES (
        canonical_disposition ->> 'recovery_disposition_id',
        recovery_case_id,
        canonical_disposition ->> 'source_run_invocation_id',
        canonical_disposition ->> 'session_id',
        canonical_disposition ->> 'run_id',
        canonical_disposition ->> 'research_run_digest',
        canonical_disposition ->> 'ambiguous_action_attempt_id',
        canonical_disposition ->> 'ambiguous_action_attempt_digest',
        canonical_disposition ->> 'source_run_invocation_id',
        canonical_disposition ->> 'source_run_invocation_digest',
        canonical_disposition ->> 'decision',
        canonical_disposition ->> 'decision_authority_ref',
        canonical_disposition ->> 'recovery_disposition_digest',
        canonical_disposition
    )
    RETURNING recovery_disposition_digest INTO inserted_digest;
    RETURN inserted_digest;
END;
$function$;

CREATE OR REPLACE FUNCTION fin_runtime.require_valid_action_attempt_lineage()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    mutable_fields constant text[] := ARRAY[
        'state', 'outcome', 'was_dispatched', 'potentially_chargeable',
        'receipt_kind', 'receipt_ref', 'receipt_digest', 'failure_code',
        'terminal_at', 'action_attempt_digest'
    ];
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM fin_runtime.agent_server_run_create_lifecycle AS pending
        WHERE pending.run_invocation_id = NEW.run_invocation_id
          AND pending.lifecycle_state = 'PENDING'
          AND pending.research_run_id =
              NEW.canonical_action_attempt ->> 'run_id'
          AND pending.agent_session_id =
              NEW.canonical_action_attempt ->> 'session_id'
          AND pending.launch_request_digest =
              NEW.canonical_action_attempt ->> 'request_digest'
    ) THEN
        RAISE EXCEPTION 'fin_runtime_run_create_action_pending_lineage_required'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.action_state = 'INTENT_COMMITTED' THEN
        RETURN NEW;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM fin_runtime.agent_server_action_attempt_snapshots AS intent
        WHERE intent.run_invocation_id = NEW.run_invocation_id
          AND intent.action_state = 'INTENT_COMMITTED'
          AND intent.action_attempt_id = NEW.action_attempt_id
          AND intent.canonical_action_attempt - mutable_fields =
              NEW.canonical_action_attempt - mutable_fields
    ) THEN
        RAISE EXCEPTION 'fin_runtime_run_create_action_intent_lineage_required'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.action_state = 'TERMINAL'
       AND NEW.action_outcome IN ('APPLIED', 'AMBIGUOUS_AFTER_DISPATCH')
       AND NOT EXISTS (
           SELECT 1
           FROM fin_runtime.agent_server_action_attempt_snapshots AS dispatched
           WHERE dispatched.run_invocation_id = NEW.run_invocation_id
             AND dispatched.action_state = 'DISPATCHED'
             AND dispatched.action_attempt_id = NEW.action_attempt_id
             AND dispatched.canonical_action_attempt - mutable_fields =
                 NEW.canonical_action_attempt - mutable_fields
       ) THEN
        RAISE EXCEPTION 'fin_runtime_run_create_action_dispatched_lineage_required'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION
    fin_runtime.require_action_attempt_lifecycle_closure()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    IF NEW.action_state = 'INTENT_COMMITTED' THEN
        RETURN NEW;
    END IF;

    IF NEW.action_state = 'DISPATCHED' AND EXISTS (
        SELECT 1
        FROM fin_runtime.agent_server_run_create_lifecycle AS dispatched
        WHERE dispatched.run_invocation_id = NEW.run_invocation_id
          AND dispatched.lifecycle_state = 'DISPATCHED'
    ) THEN
        RETURN NEW;
    END IF;

    IF NEW.action_state = 'TERMINAL'
       AND NEW.action_outcome = 'FAILED_BEFORE_DISPATCH'
       AND NOT EXISTS (
           SELECT 1
           FROM fin_runtime.agent_server_run_create_lifecycle AS dispatched
           WHERE dispatched.run_invocation_id = NEW.run_invocation_id
             AND dispatched.lifecycle_state = 'DISPATCHED'
       ) THEN
        RETURN NEW;
    END IF;

    IF NEW.action_state = 'TERMINAL'
       AND NEW.action_outcome = 'APPLIED'
       AND EXISTS (
           SELECT 1
           FROM fin_runtime.agent_server_run_create_lifecycle AS reconciled
           WHERE reconciled.run_invocation_id = NEW.run_invocation_id
             AND reconciled.lifecycle_state = 'RECONCILED'
             AND NEW.canonical_action_attempt ->> 'receipt_ref' =
                 'agent-server://runs/' || reconciled.server_run_id::text
             AND NEW.canonical_action_attempt ->> 'receipt_digest' =
                 reconciled.server_observation_digest
       ) THEN
        RETURN NEW;
    END IF;

    IF NEW.action_state = 'TERMINAL'
       AND NEW.action_outcome = 'AMBIGUOUS_AFTER_DISPATCH'
       AND EXISTS (
           SELECT 1
           FROM fin_runtime.agent_server_recovery_cases AS recovery
           WHERE recovery.run_invocation_id = NEW.run_invocation_id
             AND recovery.ambiguous_action_attempt_id = NEW.action_attempt_id
             AND recovery.ambiguous_action_attempt_digest =
                 NEW.action_attempt_digest
             AND recovery.canonical_ambiguous_action_attempt =
                 NEW.canonical_action_attempt
       ) THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'fin_runtime_run_create_action_lifecycle_closure_required'
        USING ERRCODE = '23514';
END;
$function$;

CREATE OR REPLACE FUNCTION fin_runtime.require_valid_run_create_lifecycle_event()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    expected_ordinal integer;
BEGIN
    SELECT COALESCE(MAX(existing.lifecycle_ordinal), 0) + 1
      INTO expected_ordinal
      FROM fin_runtime.agent_server_run_create_lifecycle AS existing
     WHERE existing.run_invocation_id = NEW.run_invocation_id
       AND existing.lifecycle_event_digest <> NEW.lifecycle_event_digest;
    IF NEW.lifecycle_ordinal <> expected_ordinal THEN
        RAISE EXCEPTION 'fin_runtime_run_create_lifecycle_ordinal_invalid'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.lifecycle_state = 'PENDING' AND EXISTS (
        SELECT 1
        FROM fin_runtime.research_run_invocations AS bound
        WHERE bound.run_invocation_id = NEW.run_invocation_id
           OR (
                bound.research_run_id = NEW.research_run_id
                AND bound.invocation_ordinal = NEW.invocation_ordinal
           )
    ) THEN
        RAISE EXCEPTION 'fin_runtime_run_create_final_binding_preexists'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.lifecycle_state = 'PENDING' THEN
        RETURN NEW;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM fin_runtime.agent_server_run_create_lifecycle AS pending
        WHERE pending.run_invocation_id = NEW.run_invocation_id
          AND pending.lifecycle_state = 'PENDING'
          AND pending.lifecycle_ordinal = 1
          AND pending.research_run_id = NEW.research_run_id
          AND pending.agent_session_id = NEW.agent_session_id
          AND pending.invocation_ordinal = NEW.invocation_ordinal
          AND pending.canonical_invocation_kind = NEW.canonical_invocation_kind
          AND pending.server_invocation_kind = NEW.server_invocation_kind
          AND pending.server_thread_id = NEW.server_thread_id
          AND pending.assistant_id = NEW.assistant_id
          AND pending.server_assistant_id = NEW.server_assistant_id
          AND pending.execution_profile = NEW.execution_profile
          AND pending.session_identity_digest = NEW.session_identity_digest
          AND pending.research_run_identity_digest =
              NEW.research_run_identity_digest
          AND pending.run_invocation_identity_digest =
              NEW.run_invocation_identity_digest
          AND pending.launch_request_digest = NEW.launch_request_digest
          AND pending.server_metadata_digest = NEW.server_metadata_digest
    ) THEN
        RAISE EXCEPTION 'fin_runtime_run_create_pending_identity_required'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.lifecycle_state = 'DISPATCHED' THEN
        RETURN NEW;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM fin_runtime.agent_server_run_create_lifecycle AS dispatched
        WHERE dispatched.run_invocation_id = NEW.run_invocation_id
          AND dispatched.lifecycle_state = 'DISPATCHED'
    ) THEN
        RAISE EXCEPTION 'fin_runtime_run_create_dispatched_required'
            USING ERRCODE = '23514';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM fin_runtime.agent_server_run_create_lifecycle AS prior
        WHERE prior.run_invocation_id = NEW.run_invocation_id
          AND prior.lifecycle_state = 'RECONCILED'
    ) THEN
        RAISE EXCEPTION 'fin_runtime_run_create_event_after_reconciled'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.lifecycle_state IN ('ORPHAN', 'RECONCILED')
       AND NEW.server_run_id IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM fin_runtime.agent_server_run_create_lifecycle AS prior
           WHERE prior.run_invocation_id = NEW.run_invocation_id
             AND prior.lifecycle_state = 'ORPHAN'
             AND prior.server_run_id IS NOT NULL
             AND prior.server_run_id <> NEW.server_run_id
       ) THEN
        RAISE EXCEPTION 'fin_runtime_run_create_server_run_identity_drift'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.lifecycle_state IN ('ORPHAN', 'RECONCILED') THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'fin_runtime_run_create_lifecycle_state_invalid'
        USING ERRCODE = '23514';
END;
$function$;

CREATE OR REPLACE FUNCTION fin_runtime.require_reconciled_run_create_lifecycle()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM fin_runtime.agent_server_run_create_lifecycle AS pending
        JOIN fin_runtime.agent_server_run_create_lifecycle AS reconciled
          ON reconciled.run_invocation_id = pending.run_invocation_id
         AND reconciled.lifecycle_state = 'RECONCILED'
        WHERE pending.run_invocation_id = NEW.run_invocation_id
          AND pending.lifecycle_state = 'PENDING'
          AND pending.research_run_id = NEW.research_run_id
          AND pending.agent_session_id = NEW.agent_session_id
          AND pending.invocation_ordinal = NEW.invocation_ordinal
          AND pending.canonical_invocation_kind = NEW.canonical_invocation_kind
          AND pending.server_invocation_kind = NEW.server_invocation_kind
          AND pending.server_thread_id = NEW.server_thread_id
          AND pending.assistant_id = NEW.assistant_id
          AND pending.run_invocation_identity_digest = NEW.invocation_identity_digest
          AND reconciled.bound_run_invocation_id = NEW.run_invocation_id
          AND reconciled.server_run_id = NEW.server_run_id
          AND reconciled.server_run_status = NEW.first_server_status
          AND reconciled.lifecycle_ordinal = (
              SELECT MAX(last_event.lifecycle_ordinal)
              FROM fin_runtime.agent_server_run_create_lifecycle AS last_event
              WHERE last_event.run_invocation_id = NEW.run_invocation_id
          )
    ) THEN
        RAISE EXCEPTION 'fin_runtime_reconciled_run_create_lifecycle_required'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION fin_runtime.require_run_create_action_snapshot()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    IF NEW.lifecycle_state = 'PENDING' AND NOT EXISTS (
        SELECT 1 FROM fin_runtime.agent_server_action_attempt_snapshots AS action
        WHERE action.run_invocation_id = NEW.run_invocation_id
          AND action.action_state = 'INTENT_COMMITTED'
          AND action.canonical_action_attempt ->> 'session_id' =
              NEW.agent_session_id
          AND action.canonical_action_attempt ->> 'run_id' =
              NEW.research_run_id
          AND action.canonical_action_attempt ->> 'request_digest' =
              NEW.launch_request_digest
    ) THEN
        RAISE EXCEPTION 'fin_runtime_run_create_intent_snapshot_required'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.lifecycle_state = 'DISPATCHED' AND NOT EXISTS (
        SELECT 1 FROM fin_runtime.agent_server_action_attempt_snapshots AS action
        WHERE action.run_invocation_id = NEW.run_invocation_id
          AND action.action_state = 'DISPATCHED'
          AND action.canonical_action_attempt ->> 'session_id' =
              NEW.agent_session_id
          AND action.canonical_action_attempt ->> 'run_id' =
              NEW.research_run_id
          AND action.canonical_action_attempt ->> 'request_digest' =
              NEW.launch_request_digest
    ) THEN
        RAISE EXCEPTION 'fin_runtime_run_create_dispatched_snapshot_required'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.lifecycle_state = 'RECONCILED' AND NOT EXISTS (
        SELECT 1 FROM fin_runtime.agent_server_action_attempt_snapshots AS action
        LEFT JOIN fin_runtime.agent_server_recovery_cases AS recovery
          ON recovery.run_invocation_id = action.run_invocation_id
        LEFT JOIN fin_runtime.agent_server_recovery_dispositions AS disposition
          ON disposition.recovery_case_id = recovery.recovery_case_id
        WHERE action.run_invocation_id = NEW.run_invocation_id
          AND action.action_state = 'TERMINAL'
          AND action.canonical_action_attempt ->> 'session_id' =
              NEW.agent_session_id
          AND action.canonical_action_attempt ->> 'run_id' =
              NEW.research_run_id
          AND action.canonical_action_attempt ->> 'request_digest' =
              NEW.launch_request_digest
          AND (
              (
                  action.action_outcome = 'APPLIED'
                  AND action.canonical_action_attempt ->> 'receipt_kind' =
                      'SUCCESS'
                  AND action.canonical_action_attempt ->> 'receipt_ref' =
                      'agent-server://runs/' || NEW.server_run_id::text
                  AND action.canonical_action_attempt ->> 'receipt_digest' =
                      NEW.server_observation_digest
              )
              OR (
                  action.action_outcome = 'AMBIGUOUS_AFTER_DISPATCH'
                  AND disposition.recovery_decision = 'DO_NOT_RETRY'
                  AND EXISTS (
                      SELECT 1
                      FROM fin_runtime.agent_server_run_create_lifecycle AS observed
                      WHERE observed.run_invocation_id = NEW.run_invocation_id
                        AND observed.lifecycle_state = 'ORPHAN'
                        AND observed.server_run_id = NEW.server_run_id
                        AND observed.server_run_status = NEW.server_run_status
                        AND observed.server_observation_digest =
                            NEW.server_observation_digest
                  )
              )
          )
    ) THEN
        RAISE EXCEPTION 'fin_runtime_run_create_terminal_snapshot_required'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$function$;

DO $migration$
DECLARE
    target regclass;
    trigger_name text;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_trigger
        WHERE tgname = 'agent_server_action_attempt_require_valid_lineage'
          AND tgrelid =
              'fin_runtime.agent_server_action_attempt_snapshots'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER agent_server_action_attempt_require_valid_lineage
        AFTER INSERT ON fin_runtime.agent_server_action_attempt_snapshots
        FOR EACH ROW EXECUTE FUNCTION
            fin_runtime.require_valid_action_attempt_lineage();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_trigger
        WHERE tgname = 'agent_server_action_attempt_require_lifecycle_closure'
          AND tgrelid =
              'fin_runtime.agent_server_action_attempt_snapshots'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE CONSTRAINT TRIGGER
            agent_server_action_attempt_require_lifecycle_closure
        AFTER INSERT ON fin_runtime.agent_server_action_attempt_snapshots
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION
            fin_runtime.require_action_attempt_lifecycle_closure();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_trigger
        WHERE tgname = 'agent_server_run_create_lifecycle_require_valid_event'
          AND tgrelid = 'fin_runtime.agent_server_run_create_lifecycle'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER agent_server_run_create_lifecycle_require_valid_event
        AFTER INSERT ON fin_runtime.agent_server_run_create_lifecycle
        FOR EACH ROW EXECUTE FUNCTION
            fin_runtime.require_valid_run_create_lifecycle_event();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_trigger
        WHERE tgname = 'research_run_invocations_require_reconciled_create'
          AND tgrelid = 'fin_runtime.research_run_invocations'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE CONSTRAINT TRIGGER research_run_invocations_require_reconciled_create
        AFTER INSERT ON fin_runtime.research_run_invocations
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION
            fin_runtime.require_reconciled_run_create_lifecycle();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_trigger
        WHERE tgname = 'agent_server_run_create_requires_action_snapshot'
          AND tgrelid = 'fin_runtime.agent_server_run_create_lifecycle'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE CONSTRAINT TRIGGER agent_server_run_create_requires_action_snapshot
        AFTER INSERT ON fin_runtime.agent_server_run_create_lifecycle
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION
            fin_runtime.require_run_create_action_snapshot();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_trigger
        WHERE tgname = 'agent_server_recovery_disposition_require_valid_case'
          AND tgrelid = 'fin_runtime.agent_server_recovery_dispositions'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER agent_server_recovery_disposition_require_valid_case
        AFTER INSERT ON fin_runtime.agent_server_recovery_dispositions
        FOR EACH ROW EXECUTE FUNCTION
            fin_runtime.require_valid_recovery_disposition();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_trigger
        WHERE tgname = 'agent_server_recovery_case_require_valid_sources'
          AND tgrelid = 'fin_runtime.agent_server_recovery_cases'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER agent_server_recovery_case_require_valid_sources
        AFTER INSERT ON fin_runtime.agent_server_recovery_cases
        FOR EACH ROW EXECUTE FUNCTION
            fin_runtime.require_valid_recovery_case();
    END IF;

    FOREACH target IN ARRAY ARRAY[
        'fin_runtime.agent_server_run_create_lifecycle'::regclass,
        'fin_runtime.agent_server_action_attempt_snapshots'::regclass,
        'fin_runtime.agent_server_recovery_cases'::regclass,
        'fin_runtime.agent_server_recovery_dispositions'::regclass
    ] LOOP
        trigger_name := replace(target::text, 'fin_runtime.', '') || '_reject_mutation';
        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_trigger
            WHERE tgname = trigger_name
              AND tgrelid = target
              AND NOT tgisinternal
        ) THEN
            EXECUTE format(
                'CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON %s '
                'FOR EACH ROW EXECUTE FUNCTION fin_runtime.reject_durable_identity_mutation()',
                trigger_name,
                target
            );
        END IF;
        trigger_name := replace(target::text, 'fin_runtime.', '') || '_reject_truncate';
        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_trigger
            WHERE tgname = trigger_name
              AND tgrelid = target
              AND NOT tgisinternal
        ) THEN
            EXECUTE format(
                'CREATE TRIGGER %I BEFORE TRUNCATE ON %s '
                'FOR EACH STATEMENT EXECUTE FUNCTION fin_runtime.reject_durable_identity_mutation()',
                trigger_name,
                target
            );
        END IF;
    END LOOP;
END;
$migration$;

REVOKE ALL ON fin_runtime.agent_server_run_create_lifecycle FROM PUBLIC;
REVOKE ALL ON fin_runtime.agent_server_action_attempt_snapshots FROM PUBLIC;
REVOKE ALL ON fin_runtime.agent_server_recovery_cases FROM PUBLIC;
REVOKE ALL ON fin_runtime.agent_server_recovery_dispositions FROM PUBLIC;

GRANT SELECT, INSERT ON fin_runtime.agent_server_run_create_lifecycle,
    fin_runtime.agent_server_action_attempt_snapshots,
    fin_runtime.agent_server_recovery_cases TO fin_runtime_app;
GRANT SELECT ON fin_runtime.agent_server_recovery_dispositions TO fin_runtime_app;
REVOKE INSERT ON fin_runtime.agent_server_recovery_dispositions
    FROM fin_runtime_app;

GRANT USAGE ON SCHEMA fin_runtime TO fin_runtime_operator;
GRANT SELECT ON fin_runtime.agent_server_run_create_lifecycle,
    fin_runtime.agent_server_action_attempt_snapshots,
    fin_runtime.agent_server_recovery_cases,
    fin_runtime.agent_server_recovery_dispositions TO fin_runtime_operator;
REVOKE INSERT ON fin_runtime.agent_server_recovery_dispositions
    FROM fin_runtime_operator;

REVOKE UPDATE, DELETE, TRUNCATE ON
    fin_runtime.agent_server_run_create_lifecycle,
    fin_runtime.agent_server_action_attempt_snapshots,
    fin_runtime.agent_server_recovery_cases,
    fin_runtime.agent_server_recovery_dispositions
    FROM fin_runtime_app, fin_runtime_operator;

REVOKE ALL ON FUNCTION
    fin_runtime.canonical_timestamptz_or_null(jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
    fin_runtime.canonical_timestamptz_or_null(jsonb) TO fin_runtime_app;
REVOKE ALL ON FUNCTION
    fin_runtime.require_valid_action_attempt_lineage() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
    fin_runtime.require_valid_action_attempt_lineage() TO fin_runtime_app;
REVOKE ALL ON FUNCTION
    fin_runtime.require_action_attempt_lifecycle_closure() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
    fin_runtime.require_action_attempt_lifecycle_closure() TO fin_runtime_app;
REVOKE ALL ON FUNCTION
    fin_runtime.require_reconciled_run_create_lifecycle() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
    fin_runtime.require_reconciled_run_create_lifecycle() TO fin_runtime_app;
REVOKE ALL ON FUNCTION
    fin_runtime.require_valid_run_create_lifecycle_event() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
    fin_runtime.require_valid_run_create_lifecycle_event() TO fin_runtime_app;
REVOKE ALL ON FUNCTION
    fin_runtime.require_run_create_action_snapshot() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
    fin_runtime.require_run_create_action_snapshot() TO fin_runtime_app;
REVOKE ALL ON FUNCTION
    fin_runtime.require_valid_recovery_disposition() FROM PUBLIC;
REVOKE ALL ON FUNCTION
    fin_runtime.require_valid_recovery_case() FROM PUBLIC;
REVOKE ALL ON FUNCTION
    fin_runtime.append_recovery_disposition(text, jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
    fin_runtime.append_recovery_disposition(text, jsonb)
    TO fin_runtime_operator;

COMMENT ON SCHEMA fin_runtime IS
    'FIN-owned Agent Server identity and canonical recovery bridge; schema_version=1.1';
COMMENT ON TABLE fin_runtime.agent_server_run_create_lifecycle IS
    'Append-only PENDING, DISPATCHED, zero-or-more ORPHAN observations, RECONCILED';
COMMENT ON TABLE fin_runtime.agent_server_action_attempt_snapshots IS
    'Canonical v1.2 run-create ActionAttempt snapshots; original terminal ambiguity is immutable';
COMMENT ON TABLE fin_runtime.agent_server_recovery_cases IS
    'Owner-visible open recovery requests with exact canonical source snapshots';
COMMENT ON TABLE fin_runtime.agent_server_recovery_dispositions IS
    'Independent operator-authored canonical v1.2 recovery decisions; runtime app is read-only';
