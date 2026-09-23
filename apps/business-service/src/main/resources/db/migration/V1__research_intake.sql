CREATE TABLE research_task (
    id uuid PRIMARY KEY,
    owner_id varchar(160) NOT NULL,
    project_id uuid NOT NULL,
    submission_key uuid NOT NULL,
    fingerprint char(64) NOT NULL,
    title varchar(120) NOT NULL,
    question text NOT NULL,
    binding jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(owner_id, submission_key)
);
CREATE INDEX research_task_project ON research_task(owner_id, project_id, created_at DESC, id);
CREATE TABLE research_command (
    task_id uuid NOT NULL REFERENCES research_task(id),
    phase varchar(10) NOT NULL CHECK (phase IN ('prepare','start')),
    operation_id uuid NOT NULL UNIQUE,
    request_body text NOT NULL,
    status varchar(12) NOT NULL DEFAULT 'ready' CHECK (status IN ('ready','dispatching','received','unknown','rejected')),
    response_body jsonb,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(task_id, phase)
);
COMMENT ON TABLE research_command IS 'Durable submission receipts; not an execution queue. Unknown commands cannot be redispatched.';
