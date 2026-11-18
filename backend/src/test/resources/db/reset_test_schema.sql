-- IF-40: per-test reset of the if_test schema that MigratedTestSchema built from
-- supabase/migrations (once per JVM). Empties every table and restarts identities;
-- runs inside the test transaction, so it is rolled back with it.
-- Executed as one statement (see @SqlConfig in the tests) because of the DO block.
do $$
declare tables text;
begin
  select string_agg(format('%I.%I', schemaname, tablename), ', ')
    into tables
    from pg_tables where schemaname = 'if_test';
  if tables is not null then
    execute 'truncate ' || tables || ' restart identity cascade';
  end if;
end $$;
