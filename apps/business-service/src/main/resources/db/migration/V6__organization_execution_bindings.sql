-- Authorization scope, not a native run or a dispatch receipt.
CREATE TABLE organization_execution_binding (
 id uuid PRIMARY KEY,
 draft_id uuid NOT NULL REFERENCES organization_research_draft(id),
 principal varchar(240) NOT NULL,
 request_digest varchar(64) NOT NULL,
 manifest_digest varchar(64) NOT NULL,
 closed boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now(),
 closed_at timestamptz,
 CHECK (closed = (closed_at IS NOT NULL))
);
CREATE INDEX organization_execution_draft ON organization_execution_binding(draft_id);
