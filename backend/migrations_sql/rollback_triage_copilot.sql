-- ROLLBACK of the triage-copilot migrations (0002 + 0003_messaging + 0004_work_lifecycle) on the shared Supabase.
-- Removes ONLY what our migrations added. Manan's objects are never touched:
--   * his alembic_version table (stays at his revision),
--   * his ticket columns: service_team, assignee, resolution_status, resolution_date, resolution_comments.
-- After running this, the schema matches supabase_snapshot_before_triage_copilot.sql again.
-- Paste into the Supabase SQL editor. Data in the dropped tables/columns is lost.

BEGIN;

DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS users;

DROP INDEX IF EXISTS ix_tickets_ai_team;
DROP INDEX IF EXISTS ix_tickets_assignee;        -- our index on his column; the column itself stays
DROP INDEX IF EXISTS ix_tickets_priority_score;
DROP INDEX IF EXISTS ix_tickets_route;
DROP INDEX IF EXISTS ix_tickets_work_status;
ALTER TABLE tickets
  DROP COLUMN IF EXISTS work_status,
  DROP COLUMN IF EXISTS resolution,
  DROP COLUMN IF EXISTS resolution_comment,
  DROP COLUMN IF EXISTS resolved_by,
  DROP COLUMN IF EXISTS resolved_at,
  DROP COLUMN IF EXISTS activity,
  DROP COLUMN IF EXISTS ai_service,
  DROP COLUMN IF EXISTS ai_team,
  DROP COLUMN IF EXISTS ai_priority,
  DROP COLUMN IF EXISTS priority_score,
  DROP COLUMN IF EXISTS confidence,
  DROP COLUMN IF EXISTS route,
  DROP COLUMN IF EXISTS escalated,
  DROP COLUMN IF EXISTS sla_due_at;

ALTER TABLE triage_results
  DROP COLUMN IF EXISTS facts,
  DROP COLUMN IF EXISTS priority_score,
  DROP COLUMN IF EXISTS rubric_trace,
  DROP COLUMN IF EXISTS vote_agreement,
  DROP COLUMN IF EXISTS confidence_detail,
  DROP COLUMN IF EXISTS route,
  DROP COLUMN IF EXISTS escalated,
  DROP COLUMN IF EXISTS sla_due_at,
  DROP COLUMN IF EXISTS assignee_suggestion,
  DROP COLUMN IF EXISTS playbook_ref;

DROP TABLE IF EXISTS alembic_version_triage;

COMMIT;
