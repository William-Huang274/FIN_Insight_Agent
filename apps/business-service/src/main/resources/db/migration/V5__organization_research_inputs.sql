CREATE TABLE organization_research_draft (
 id uuid PRIMARY KEY, project_id uuid NOT NULL, organization_id uuid NOT NULL,
 created_by varchar(240) NOT NULL, request_digest varchar(64) NOT NULL,
 title varchar(120) NOT NULL, question varchar(16000) NOT NULL, research_as_of date NOT NULL,
 manifest_text text NOT NULL, manifest_digest varchar(64) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(project_id,organization_id) REFERENCES organization_project(id,organization_id)
);
CREATE INDEX organization_research_draft_catalog ON organization_research_draft(project_id,created_at DESC,id);
CREATE TABLE organization_research_input (
 draft_id uuid NOT NULL REFERENCES organization_research_draft(id),
 resource_id uuid NOT NULL, space_id uuid NOT NULL,
 resource_revision integer NOT NULL, binding jsonb NOT NULL,
 PRIMARY KEY(draft_id,resource_id),
 FOREIGN KEY(resource_id,space_id) REFERENCES space_resource(id,space_id)
);
