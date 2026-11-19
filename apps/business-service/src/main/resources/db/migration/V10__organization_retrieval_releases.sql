CREATE TABLE organization_retrieval_release (
 id uuid PRIMARY KEY,
 project_id uuid NOT NULL,
 organization_id uuid NOT NULL,
 source_draft_id uuid NOT NULL REFERENCES organization_research_draft(id),
 created_by varchar(240) NOT NULL,
 request_digest varchar(64) NOT NULL,
 contract jsonb NOT NULL,
 inputs jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(project_id, organization_id) REFERENCES organization_project(id, organization_id)
);
CREATE INDEX organization_retrieval_release_catalog
 ON organization_retrieval_release(project_id, created_at DESC, id);
