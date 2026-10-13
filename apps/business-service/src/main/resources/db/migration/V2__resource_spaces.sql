CREATE TABLE resource_organization (
 id uuid PRIMARY KEY, name varchar(120) NOT NULL, created_by varchar(240) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE organization_member (
 organization_id uuid NOT NULL REFERENCES resource_organization(id), subject varchar(240) NOT NULL,
 display_name varchar(80) NOT NULL, role varchar(16) NOT NULL CHECK(role IN ('admin','member')),
 active boolean NOT NULL DEFAULT true, PRIMARY KEY(organization_id,subject)
);
CREATE TABLE resource_space (
 id uuid PRIMARY KEY, organization_id uuid NOT NULL REFERENCES resource_organization(id), name varchar(120) NOT NULL,
 kind varchar(16) NOT NULL CHECK(kind IN ('personal','team')), principal varchar(240),
 CHECK((kind='personal')=(principal IS NOT NULL)), UNIQUE(organization_id,principal)
);
CREATE TABLE space_member (
 space_id uuid NOT NULL REFERENCES resource_space(id), subject varchar(240) NOT NULL,
 role varchar(16) NOT NULL CHECK(role IN ('manager','reader')), PRIMARY KEY(space_id,subject)
);
CREATE TABLE organization_invite (
 token_hash varchar(64) PRIMARY KEY, organization_id uuid NOT NULL REFERENCES resource_organization(id),
 expires_at timestamptz NOT NULL DEFAULT now()+interval '7 days', used_by varchar(240)
);
CREATE TABLE space_resource (
 id uuid PRIMARY KEY, space_id uuid NOT NULL REFERENCES resource_space(id), created_by varchar(240) NOT NULL,
 title varchar(180) NOT NULL, resource_type varchar(16) NOT NULL CHECK(resource_type IN ('files','knowledge','database')),
 binding jsonb NOT NULL, active boolean NOT NULL DEFAULT true, revision integer NOT NULL DEFAULT 1,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX space_resource_catalog ON space_resource(space_id,created_at DESC,id);
CREATE TABLE resource_space_audit (
 id bigserial PRIMARY KEY, organization_id uuid NOT NULL REFERENCES resource_organization(id),
 actor varchar(240) NOT NULL, action varchar(40) NOT NULL, target varchar(240) NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT now()
);
