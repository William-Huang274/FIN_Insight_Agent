CREATE TABLE organization_project (
 id uuid PRIMARY KEY,
 organization_id uuid NOT NULL REFERENCES resource_organization(id),
 name varchar(60) NOT NULL, description varchar(500) NOT NULL DEFAULT '',
 archived boolean NOT NULL DEFAULT false, revision integer NOT NULL DEFAULT 1,
 created_by varchar(240) NOT NULL, creation_digest varchar(64) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(id, organization_id)
);
CREATE INDEX organization_project_catalog ON organization_project(organization_id, created_at DESC, id);
CREATE TABLE organization_project_member (
 project_id uuid NOT NULL, organization_id uuid NOT NULL, subject varchar(240) NOT NULL,
 role varchar(16) NOT NULL CHECK(role IN ('manager','researcher','viewer')),
 PRIMARY KEY(project_id,subject),
 FOREIGN KEY(project_id,organization_id) REFERENCES organization_project(id,organization_id),
 FOREIGN KEY(organization_id,subject) REFERENCES organization_member(organization_id,subject)
);
CREATE TABLE organization_project_audit (
 id bigserial PRIMARY KEY, project_id uuid NOT NULL REFERENCES organization_project(id),
 actor varchar(240) NOT NULL, action varchar(40) NOT NULL, target varchar(240) NOT NULL,
 revision integer NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now()
);
