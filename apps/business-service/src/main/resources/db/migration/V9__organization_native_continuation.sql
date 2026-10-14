-- One explicit promotion from preliminary orientation to full research.
-- Further recovery/revision actions require separate contracts.
CREATE TABLE organization_native_continuation (
    execution_id uuid PRIMARY KEY REFERENCES organization_native_start(execution_id),
    operation_id uuid NOT NULL UNIQUE,
    fingerprint varchar(64) NOT NULL,
    request_body text NOT NULL,
    status varchar(16) NOT NULL DEFAULT 'ready' CHECK (status IN ('ready','dispatching','unknown','received','rejected')),
    run_id uuid UNIQUE,
    response jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
