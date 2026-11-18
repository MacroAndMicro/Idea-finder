-- IF-58: production drifted from the baseline: opportunity_cards.confidence_score is
-- numeric(3,2) there (max 9.99), while the baseline declares plain numeric and the CHECK
-- constraint / product spec require 1–100. Card synthesis writes 1–100, so every card with
-- a score >= 10 failed with 22003 numeric field overflow.
-- Widening to unconstrained numeric (as in the baseline) never loses data; the CHECK
-- (1–100) stays. Idempotent: a no-op where the column is already plain numeric.

do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'opportunity_cards'
      and column_name = 'confidence_score' and numeric_precision is not null
  ) then
    alter table public.opportunity_cards alter column confidence_score type numeric;
  end if;
end $$;
