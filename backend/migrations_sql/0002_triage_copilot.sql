-- Migration 0001 -> 0002 (triage copilot) for Supabase. Paste into the SQL Editor and run once.
-- Same as backend/alembic/versions/20260925_0002_triage_copilot.py (the backend also applies it on start).
-- Additive and idempotent (IF NOT EXISTS): safe next to a teammate's columns such as tickets.assignee.
-- Our version is tracked in alembic_version_triage; a teammate's alembic_version is never touched.

CREATE TABLE IF NOT EXISTS alembic_version_triage (version_num VARCHAR(32) NOT NULL PRIMARY KEY);
INSERT INTO alembic_version_triage (version_num) SELECT '0001' WHERE NOT EXISTS (SELECT 1 FROM alembic_version_triage);

BEGIN;

-- Running upgrade 0001 -> 0002

CREATE TABLE IF NOT EXISTS users (
    email VARCHAR(120) NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    role VARCHAR(10) DEFAULT 'analyst' NOT NULL, 
    teams JSONB DEFAULT '[]'::jsonb NOT NULL, 
    capacity INTEGER DEFAULT '8' NOT NULL, 
    PRIMARY KEY (email)
);

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS assignee VARCHAR(120);

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS ai_service VARCHAR(80);

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS ai_team VARCHAR(80);

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS ai_priority VARCHAR(10);

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS priority_score FLOAT;

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS confidence FLOAT;

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS route VARCHAR(10);

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS escalated BOOLEAN DEFAULT false NOT NULL;

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS sla_due_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS ix_tickets_ai_team ON tickets (ai_team);

CREATE INDEX IF NOT EXISTS ix_tickets_assignee ON tickets (assignee);

CREATE INDEX IF NOT EXISTS ix_tickets_priority_score ON tickets (priority_score);

CREATE INDEX IF NOT EXISTS ix_tickets_route ON tickets (route);

ALTER TABLE triage_results ADD COLUMN IF NOT EXISTS facts JSONB;

ALTER TABLE triage_results ADD COLUMN IF NOT EXISTS priority_score FLOAT;

ALTER TABLE triage_results ADD COLUMN IF NOT EXISTS rubric_trace JSONB DEFAULT '[]'::jsonb NOT NULL;

ALTER TABLE triage_results ADD COLUMN IF NOT EXISTS vote_agreement JSONB DEFAULT '{}'::jsonb NOT NULL;

ALTER TABLE triage_results ADD COLUMN IF NOT EXISTS confidence_detail JSONB;

ALTER TABLE triage_results ADD COLUMN IF NOT EXISTS route VARCHAR(10);

ALTER TABLE triage_results ADD COLUMN IF NOT EXISTS escalated BOOLEAN DEFAULT false NOT NULL;

ALTER TABLE triage_results ADD COLUMN IF NOT EXISTS sla_due_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE triage_results ADD COLUMN IF NOT EXISTS assignee_suggestion JSONB;

ALTER TABLE triage_results ADD COLUMN IF NOT EXISTS playbook_ref VARCHAR(120);

UPDATE alembic_version_triage SET version_num='0002' WHERE alembic_version_triage.version_num = '0001';

COMMIT;

