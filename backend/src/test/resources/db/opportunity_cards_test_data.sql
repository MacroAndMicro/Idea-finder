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

-- 4 raw signals. Card 1 has two (signal 2 is newer by source_created_at), card 2 has one,
-- card 3 has none, signal 4 is not linked to any card. Hashes are set so tests can prove
-- they are never exposed.
insert into if_test.raw_signals
  (id, source_platform, external_id, url, title, body, author_handle_hash, score, comment_count,
   source_created_at, fetched_at, processed_at, content_hash)
overriding system value
values
  (1, 'github', 'o/r#1', 'https://github.com/o/r/issues/1', 'Flaky CI', repeat('x', 600), 'authhash1', 10, 3,
   '2026-11-01T00:00:00Z', '2026-11-15T00:00:00Z', '2026-11-15T01:00:00Z', 'contenthash1'),
  (2, 'hackernews', '42', 'https://news.ycombinator.com/item?id=42', 'Ask HN: flaky tests', 'short body', 'authhash2', 55, 20,
   '2026-11-05T00:00:00Z', '2026-11-15T00:00:00Z', null, 'contenthash2'),
  (3, 'stackexchange', 'so:7', 'https://stackoverflow.com/q/7', 'Quota exceeded', null, null, null, null,
   null, '2026-11-14T00:00:00Z', '2026-11-14T01:00:00Z', null),
  (4, 'reddit', 't3_abc', 'https://reddit.com/r/x/abc', 'Unlinked', 'b', null, 1, 0,
   '2026-11-16T00:00:00Z', '2026-11-16T12:00:00Z', null, null);
insert into if_test.card_signals (card_id, signal_id) values (1, 1), (1, 2), (2, 3);
