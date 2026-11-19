-- A failed nested run can leave the outer checkpoint unchanged. A new explicit
-- recovery is bound to the new terminal predecessor; duplicate dispatch from
-- the same predecessor/checkpoint is still rejected transactionally.
DROP INDEX organization_report_command_checkpoint;
CREATE UNIQUE INDEX organization_report_command_checkpoint
    ON organization_report_command(execution_id,checkpoint_id,
        (COALESCE(request_body::jsonb->>'previous_run_id','')))
    WHERE command_kind IN ('report','root_task') AND status <> 'rejected';
