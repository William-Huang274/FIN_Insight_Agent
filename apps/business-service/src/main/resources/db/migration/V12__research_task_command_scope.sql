-- Reuse durable commands, keeping report ordering and child scopes independent.
ALTER TABLE organization_report_command
    ADD COLUMN command_kind varchar(24) NOT NULL DEFAULT 'report',
    ADD COLUMN child_thread_id uuid,
    ADD COLUMN task_action varchar(16),
    ADD CONSTRAINT organization_command_scope CHECK (
        (command_kind='report' AND child_thread_id IS NULL AND task_action IS NULL) OR
        (command_kind='research_task' AND child_thread_id IS NOT NULL AND
         task_action IS NOT NULL AND task_action IN ('create','continue','cancel')));
DROP INDEX organization_report_command_checkpoint;
CREATE UNIQUE INDEX organization_report_command_checkpoint
    ON organization_report_command(execution_id,checkpoint_id)
    WHERE command_kind='report' AND status <> 'rejected';
CREATE UNIQUE INDEX organization_child_create
    ON organization_report_command(child_thread_id)
    WHERE command_kind='research_task' AND task_action='create';
CREATE UNIQUE INDEX organization_child_checkpoint
    ON organization_report_command(execution_id,child_thread_id,checkpoint_id,task_action)
    WHERE command_kind='research_task' AND task_action <> 'cancel' AND status <> 'rejected';
CREATE INDEX organization_child_commands
    ON organization_report_command(execution_id,child_thread_id,command_sequence);
