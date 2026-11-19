-- Root continuations reuse durable command receipts; child commands remain separate.
ALTER TABLE organization_report_command DROP CONSTRAINT organization_command_scope;
ALTER TABLE organization_report_command ADD CONSTRAINT organization_command_scope CHECK (
    (command_kind IN ('report','root_task') AND child_thread_id IS NULL AND task_action IS NULL) OR
    (command_kind='research_task' AND child_thread_id IS NOT NULL AND
     task_action IS NOT NULL AND task_action IN ('create','continue','cancel')));
DROP INDEX organization_report_command_checkpoint;
CREATE UNIQUE INDEX organization_report_command_checkpoint
    ON organization_report_command(execution_id,checkpoint_id)
    WHERE command_kind IN ('report','root_task') AND status <> 'rejected';
