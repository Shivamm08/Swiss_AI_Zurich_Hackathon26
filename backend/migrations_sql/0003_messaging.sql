-- Migration 0002 -> 0003_messaging (team channels + direct messages) for Supabase. Run after 0002.
-- Same as backend/alembic/versions/20260925_0003_messaging.py. Additive and idempotent.

BEGIN;

-- Running upgrade 0002 -> 0003_messaging

CREATE TABLE IF NOT EXISTS messages (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    channel VARCHAR(300) NOT NULL, 
    sender VARCHAR(120) NOT NULL, 
    body TEXT NOT NULL, 
    kind VARCHAR(20) DEFAULT 'message' NOT NULL, 
    ticket_id UUID, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(ticket_id) REFERENCES tickets (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_messages_channel ON messages (channel);

CREATE INDEX IF NOT EXISTS ix_messages_created_at ON messages (created_at);

CREATE INDEX IF NOT EXISTS ix_messages_ticket_id ON messages (ticket_id);

UPDATE alembic_version_triage SET version_num='0003_messaging' WHERE alembic_version_triage.version_num = '0002';

COMMIT;

