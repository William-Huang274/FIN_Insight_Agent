CREATE TABLE organization_native_preparation (
 execution_id uuid PRIMARY KEY REFERENCES organization_execution_binding(id),
 operation_id uuid NOT NULL UNIQUE,
 fingerprint varchar(64) NOT NULL,
 request_body text NOT NULL,
 status varchar(16) NOT NULL DEFAULT 'ready' CHECK (status IN ('ready','dispatching','unknown','received','rejected')),
 response jsonb,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
