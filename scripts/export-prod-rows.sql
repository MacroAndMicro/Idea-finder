-- IF-84: read-only export of the prod rows that scripts/local-api-from-prod.sh loads.
--
-- Run each statement with the Supabase connector (execute_sql, project ikmzwnyaijkvpqisgzms).
-- Each returns one row with one column, "rows": a JSON array (or [] when the table is empty).
-- Save that array, unchanged, as .local-data/<table>.json (gitignored). Nothing here writes.
--
-- Large tables: add  where id > <last id>  and  limit 500  inside the subquery and save the
-- chunks as .local-data/<table>.part-001.json, .part-002.json, ... (all are loaded).

-- .local-data/opportunity_cards.json
select coalesce(json_agg(t order by t.id), '[]'::json) as rows
  from (select * from public.opportunity_cards) t;

-- .local-data/raw_signals.json
select coalesce(json_agg(t order by t.id), '[]'::json) as rows
  from (select * from public.raw_signals) t;

-- .local-data/ingestion_runs.json
select coalesce(json_agg(t order by t.id), '[]'::json) as rows
  from (select * from public.ingestion_runs) t;

-- .local-data/signal_extractions.json
select coalesce(json_agg(t order by t.id), '[]'::json) as rows
  from (select * from public.signal_extractions) t;

-- .local-data/card_signals.json
select coalesce(json_agg(t order by t.card_id, t.signal_id), '[]'::json) as rows
  from (select * from public.card_signals) t;
