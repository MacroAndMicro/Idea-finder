-- IF-62: the deterministic card quality gate records failed clusters in
-- synthesis_rejections with reason 'quality:<rule>[,<rule>...]' (rule names are
-- lowercase snake_case, see scrapers/card_quality.py). Non-destructive: widens the
-- check constraint only; existing rows ('rejected' / 'invalid') stay valid.
alter table public.synthesis_rejections
  drop constraint if exists synthesis_rejections_reason_chk;
alter table public.synthesis_rejections
  add constraint synthesis_rejections_reason_chk
  check (reason in ('rejected', 'invalid') or reason ~ '^quality:[a-z_]+(,[a-z_]+)*$');
