-- Migration 0003_messaging -> 0004_work_lifecycle (work status, specialist resolution, roles) for Supabase. Run after 0003.
-- Same as backend/alembic/versions/20260925_0004_work_lifecycle.py. Additive and idempotent; never clears tickets.assignee (shared with Manan's branch); renames roles lead->analyst, analyst->specialist once.

BEGIN;

-- Running upgrade 0003_messaging -> 0004_work_lifecycle

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS work_status VARCHAR(20) DEFAULT 'open' NOT NULL;

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolution VARCHAR(30);

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolution_comment TEXT;

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolved_by VARCHAR(120);

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS activity JSONB DEFAULT '[]'::jsonb NOT NULL;

CREATE INDEX IF NOT EXISTS ix_tickets_work_status ON tickets (work_status);

UPDATE tickets SET work_status = CASE
            WHEN status = 'done' THEN 'done'
            WHEN assignee IS NOT NULL AND triage_state IN ('approved', 'edited') THEN 'assigned'
            ELSE 'open' END
        WHERE work_status = 'open';

ALTER TABLE users ALTER COLUMN role SET DEFAULT 'specialist';

UPDATE users SET role = CASE role WHEN 'lead' THEN 'analyst' WHEN 'analyst' THEN 'specialist' ELSE role END
        WHERE role IN ('lead', 'analyst') AND NOT EXISTS (SELECT 1 FROM users WHERE role = 'specialist');

UPDATE alembic_version_triage SET version_num='0004_work_lifecycle' WHERE alembic_version_triage.version_num = '0003_messaging';

COMMIT;

