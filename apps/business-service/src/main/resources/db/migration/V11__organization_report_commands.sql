-- Multiple explicit report questions/revisions. Existing command rows stay intact.
CREATE TABLE organization_report_command (
    id uuid PRIMARY KEY,
    execution_id uuid NOT NULL REFERENCES organization_execution_binding(id),
    command_sequence bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    operation_id uuid NOT NULL UNIQUE,
    principal varchar(160) NOT NULL,
    fingerprint varchar(64) NOT NULL,
    checkpoint_id uuid NOT NULL,
    request_body text NOT NULL,
    status varchar(16) NOT NULL DEFAULT 'ready'
        CHECK (status IN ('ready','dispatching','unknown','received','rejected')),
    run_id uuid UNIQUE,
    response jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX organization_report_command_execution
    ON organization_report_command(execution_id,command_sequence DESC);
-- A concurrent second request cannot spend against the same report checkpoint.
-- Definite pre-dispatch rejection releases it; an unknown result never does.
-- This is a native checkpoint, NOT a report version: a completed question
-- creates another checkpoint even when the report text/version stays unchanged.
CREATE UNIQUE INDEX organization_report_command_checkpoint
    ON organization_report_command(execution_id,checkpoint_id) WHERE status <> 'rejected';
