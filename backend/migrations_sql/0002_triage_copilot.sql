-- Migration 0001 -> 0002 (triage copilot) for Supabase: paste into the SQL Editor and run once.
-- Equivalent to the Alembic migration backend/alembic/versions/20260925_0002_triage_copilot.py
-- (the backend also applies it automatically on start). Purely additive: a new users table and
-- nullable/defaulted columns, so teammates on older code keep working.

BEGIN;

-- Running upgrade 0001 -> 0002

CREATE TABLE users (
    email VARCHAR(120) NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    role VARCHAR(10) DEFAULT 'analyst' NOT NULL, 
    teams JSONB DEFAULT '[]'::jsonb NOT NULL, 
    capacity INTEGER DEFAULT '8' NOT NULL, 
    PRIMARY KEY (email)
);

ALTER TABLE tickets ADD COLUMN assignee VARCHAR(120);

ALTER TABLE tickets ADD COLUMN ai_service VARCHAR(80);

ALTER TABLE tickets ADD COLUMN ai_team VARCHAR(80);

ALTER TABLE tickets ADD COLUMN ai_priority VARCHAR(10);

ALTER TABLE tickets ADD COLUMN priority_score FLOAT;

ALTER TABLE tickets ADD COLUMN confidence FLOAT;

ALTER TABLE tickets ADD COLUMN route VARCHAR(10);

ALTER TABLE tickets ADD COLUMN escalated BOOLEAN DEFAULT false NOT NULL;

ALTER TABLE tickets ADD COLUMN sla_due_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX ix_tickets_ai_team ON tickets (ai_team);

CREATE INDEX ix_tickets_assignee ON tickets (assignee);

CREATE INDEX ix_tickets_priority_score ON tickets (priority_score);

CREATE INDEX ix_tickets_route ON tickets (route);

ALTER TABLE triage_results ADD COLUMN facts JSONB;

ALTER TABLE triage_results ADD COLUMN priority_score FLOAT;

ALTER TABLE triage_results ADD COLUMN rubric_trace JSONB DEFAULT '[]'::jsonb NOT NULL;

ALTER TABLE triage_results ADD COLUMN vote_agreement JSONB DEFAULT '{}'::jsonb NOT NULL;

ALTER TABLE triage_results ADD COLUMN confidence_detail JSONB;

ALTER TABLE triage_results ADD COLUMN route VARCHAR(10);

ALTER TABLE triage_results ADD COLUMN escalated BOOLEAN DEFAULT false NOT NULL;

ALTER TABLE triage_results ADD COLUMN sla_due_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE triage_results ADD COLUMN assignee_suggestion JSONB;

ALTER TABLE triage_results ADD COLUMN playbook_ref VARCHAR(120);

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';

COMMIT;

