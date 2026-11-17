-- 6 cards covering every filter dimension. created_at is fixed so ordering is deterministic.
insert into if_test.opportunity_cards
  (id, title, source_platform, source_url, raw_content_snippet, problem_statement, trigger_context,
   market_size, duct_tape_solutions, economic_intent, mvp_wedge, confidence_score, embedding_model, created_at, updated_at)
values
  (1, 'CI flaky test triage', 'github', 'https://github.com/o/r/issues/1', 'snippet 1', 'P1', 'T1', 'M1', 'D1', 'High',   'W1', 90, 'm', '2026-11-10T00:00:00Z', '2026-11-10T00:00:00Z'),
  (2, 'Stack Exchange quota',  'stackexchange', 'https://stackoverflow.com/q/2', 'snippet 2', 'P2', 'T2', 'M2', 'D2', 'Medium', 'W2', 70, 'm', '2026-11-11T00:00:00Z', '2026-11-11T00:00:00Z'),
  (3, 'Ask HN invoicing',      'hackernews', 'https://news.ycombinator.com/item?id=3', 'snippet 3', 'P3', 'T3', 'M3', 'D3', 'High', 'W3', 55, 'm', '2026-11-12T00:00:00Z', '2026-11-12T00:00:00Z'),
  (4, 'GitHub webhook retries','github', 'https://github.com/o/r/issues/4', 'snippet 4', 'P4', 'T4', 'M4', 'D4', 'Low',    'W4', 30, 'm', '2026-11-13T00:00:00Z', '2026-11-13T00:00:00Z'),
  (5, 'Unscored card',         'reddit', 'https://reddit.com/r/x/5', 'snippet 5', 'P5', 'T5', null, null, null,  null, null, null, '2026-11-14T00:00:00Z', '2026-11-14T00:00:00Z'),
  (6, 'Other unspecified',     'other', null, null, 'P6', 'T6', 'M6', 'D6', 'Unspecified', 'W6', 70, 'm', '2026-11-09T00:00:00Z', '2026-11-09T00:00:00Z');
