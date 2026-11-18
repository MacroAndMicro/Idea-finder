-- IF-45 pipeline funnel fixture, on top of opportunity_cards_test_data.sql (signals 1-4).
-- Embedded: signals 1, 2, 3 (4 has none). Extractions: 1 = B2B pain point, 2 = consumer pain point,
-- 3 = failed (is_pain_point null), 4 = not a pain point.
-- Expected: embedded 3, extracted 4, pain_points 2, b2b_pain_points 1, failed_extractions 1.
update if_test.raw_signals set embedding = array_fill(0.01::real, array[1536])::vector, embedding_model = 'm'
where id in (1, 2, 3);
insert into if_test.signal_extractions (signal_id, is_pain_point, is_b2b, problem_summary, llm_model) values
  (1, true,  true,  'B2B pain', 'm'),
  (2, true,  false, 'Consumer pain', 'm'),
  (3, null,  null,  null, 'm'),
  (4, false, null,  null, 'm');
