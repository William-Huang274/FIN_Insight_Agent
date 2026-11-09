-- Organizational lineage does not rewrite frozen inputs or native thread IDs.
ALTER TABLE organization_research_draft ADD COLUMN topic_id uuid;
ALTER TABLE organization_research_draft ADD COLUMN parent_draft_id uuid REFERENCES organization_research_draft(id);
ALTER TABLE organization_research_draft ADD COLUMN revision_note text NOT NULL DEFAULT '';
UPDATE organization_research_draft SET topic_id=id;
ALTER TABLE organization_research_draft ALTER COLUMN topic_id SET NOT NULL;
CREATE INDEX organization_research_topic_idx ON organization_research_draft(project_id,topic_id,created_at);
