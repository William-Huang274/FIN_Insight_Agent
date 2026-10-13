ALTER TABLE resource_space ADD CONSTRAINT resource_space_org_identity UNIQUE(id,organization_id);
ALTER TABLE space_resource ADD CONSTRAINT space_resource_space_identity UNIQUE(id,space_id);
CREATE TABLE organization_project_resource (
 project_id uuid NOT NULL, organization_id uuid NOT NULL,
 space_id uuid NOT NULL, resource_id uuid NOT NULL,
 linked_by varchar(240) NOT NULL, linked_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(project_id,resource_id),
 FOREIGN KEY(project_id,organization_id) REFERENCES organization_project(id,organization_id),
 FOREIGN KEY(space_id,organization_id) REFERENCES resource_space(id,organization_id),
 FOREIGN KEY(resource_id,space_id) REFERENCES space_resource(id,space_id)
);
CREATE INDEX organization_project_resource_lookup ON organization_project_resource(space_id,project_id,resource_id);
