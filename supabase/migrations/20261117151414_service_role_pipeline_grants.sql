-- IF-25: the scrapers pipeline writes through PostgREST with the service-role key,
-- but this project does not auto-grant table privileges to service_role: it only
-- holds TRIGGER/REFERENCES/TRUNCATE, so every read/insert returns 42501
-- "permission denied for table raw_signals" (HTTP 403).
-- Grant DML on the pipeline tables to service_role only. anon/authenticated get
-- nothing; RLS stays enabled with no public policies (service_role bypasses RLS).
-- Additive only.

grant select, insert, update on table public.raw_signals        to service_role;
grant select, insert, update on table public.signal_extractions to service_role;
grant select, insert         on table public.ingestion_runs     to service_role;
grant select, insert, update on table public.opportunity_cards  to service_role;
grant select, insert, delete on table public.card_signals       to service_role;

-- Identity columns: PostgREST inserts need the sequences.
grant usage, select on all sequences in schema public to service_role;
