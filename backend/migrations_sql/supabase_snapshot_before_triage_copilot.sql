-- SNAPSHOT of the shared Supabase schema BEFORE the triage-copilot migrations (read-only record).
-- Taken 2026-09-25 02:28 UTC from aws-1-eu-west-1.pooler.supabase.com.
-- This is Manan's schema state: alembic_version = the value below, plus his extra ticket columns.
-- It is kept for reference; restoring his build needs nothing, because our migrations do not
-- touch his alembic_version table or his columns (see rollback_triage_copilot.sql).

-- alembic_version: ['0003']

-- table alembic_version
--   version_num            character varying(32)          NOT NULL

-- table kb_documents
--   id                     uuid                           NOT NULL DEFAULT gen_random_uuid()
--   kind                   character varying(30)          NOT NULL
--   ref_id                 character varying(120)         NOT NULL
--   title                  text                           NOT NULL
--   content                text                           NOT NULL
--   meta                   jsonb                          NOT NULL DEFAULT '{}'::jsonb
--   embedding              USER-DEFINED                   NULL
--   updated_at             timestamp with time zone       NOT NULL DEFAULT now()

-- table reviews
--   id                     uuid                           NOT NULL DEFAULT gen_random_uuid()
--   ticket_id              uuid                           NOT NULL
--   triage_result_id       uuid                           NOT NULL
--   action                 character varying(10)          NOT NULL
--   final                  jsonb                          NULL
--   overridden_fields      jsonb                          NOT NULL DEFAULT '[]'::jsonb
--   reviewer               character varying(120)         NOT NULL
--   notes                  text                           NULL
--   review_seconds         double precision               NULL
--   created_at             timestamp with time zone       NOT NULL DEFAULT now()

-- table tickets
--   id                     uuid                           NOT NULL DEFAULT gen_random_uuid()
--   number                 integer                        NOT NULL
--   source                 character varying(20)          NOT NULL
--   work_type              character varying(40)          NULL
--   request_type           character varying(80)          NULL
--   summary                text                           NOT NULL
--   description            text                           NOT NULL DEFAULT ''::text
--   affected_service       character varying(80)          NULL
--   business_entity        character varying(40)          NULL
--   reporter               character varying(120)         NULL
--   urgency                character varying(10)          NULL
--   impact                 character varying(10)          NULL
--   priority               character varying(10)          NULL
--   status                 character varying(20)          NULL
--   linked_issues          jsonb                          NOT NULL DEFAULT '[]'::jsonb
--   comments               jsonb                          NOT NULL DEFAULT '[]'::jsonb
--   raw                    jsonb                          NOT NULL DEFAULT '{}'::jsonb
--   triage_state           character varying(20)          NOT NULL DEFAULT 'new'::character varying
--   source_created_at      timestamp with time zone       NULL
--   created_at             timestamp with time zone       NOT NULL DEFAULT now()
--   updated_at             timestamp with time zone       NOT NULL DEFAULT now()
--   service_team           character varying(80)          NULL
--   assignee               character varying(120)         NULL
--   resolution_status      character varying(30)          NULL
--   resolution_date        timestamp with time zone       NULL
--   resolution_comments    text                           NULL

-- table triage_results
--   id                     uuid                           NOT NULL DEFAULT gen_random_uuid()
--   ticket_id              uuid                           NOT NULL
--   work_type              character varying(40)          NOT NULL
--   service                character varying(80)          NOT NULL
--   team                   character varying(80)          NOT NULL
--   assignee               character varying(120)         NULL
--   urgency                character varying(10)          NOT NULL
--   impact                 character varying(10)          NOT NULL
--   priority               character varying(10)          NOT NULL
--   resolution             character varying(30)          NOT NULL
--   resolution_comment     text                           NOT NULL
--   confidence             double precision               NOT NULL
--   rationale              text                           NOT NULL DEFAULT ''::text
--   evidence               jsonb                          NOT NULL DEFAULT '[]'::jsonb
--   changed_fields         jsonb                          NOT NULL DEFAULT '[]'::jsonb
--   model                  character varying(80)          NOT NULL
--   latency_ms             integer                        NOT NULL
--   created_at             timestamp with time zone       NOT NULL DEFAULT now()

-- indexes (exact definitions)
CREATE UNIQUE INDEX alembic_version_pkc ON public.alembic_version USING btree (version_num);
CREATE INDEX ix_kb_documents_kind ON public.kb_documents USING btree (kind);
CREATE UNIQUE INDEX kb_documents_pkey ON public.kb_documents USING btree (id);
CREATE UNIQUE INDEX kb_documents_ref_id_key ON public.kb_documents USING btree (ref_id);
CREATE INDEX ix_reviews_ticket_id ON public.reviews USING btree (ticket_id);
CREATE UNIQUE INDEX reviews_pkey ON public.reviews USING btree (id);
CREATE INDEX ix_tickets_source ON public.tickets USING btree (source);
CREATE INDEX ix_tickets_triage_state ON public.tickets USING btree (triage_state);
CREATE UNIQUE INDEX tickets_number_key ON public.tickets USING btree (number);
CREATE UNIQUE INDEX tickets_pkey ON public.tickets USING btree (id);
CREATE INDEX ix_triage_results_ticket_id ON public.triage_results USING btree (ticket_id);
CREATE UNIQUE INDEX triage_results_pkey ON public.triage_results USING btree (id);
