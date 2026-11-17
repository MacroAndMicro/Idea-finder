-- IF-24 fixture vectors (needs pgvector, as in CI). e1/e2 are the first two unit axes of 1536 dims.
-- Relative to card 1 (e1): card 2 ~0.995, card 3 ~0.7071, card 4 0 (orthogonal), card 5 opposite,
-- card 6 has no embedding.
update if_test.opportunity_cards c
set embedding = v.vec::vector
from (
  select id, (
    select array_agg(case when i = 1 then x when i = 2 then y else 0 end::float4 order by i)
    from generate_series(1, 1536) i
  ) as vec
  from (values (1, 1.0, 0.0), (2, 1.0, 0.1), (3, 1.0, 1.0), (4, 0.0, 1.0), (5, -1.0, 0.0)) as p(id, x, y)
) v
where c.id = v.id;
