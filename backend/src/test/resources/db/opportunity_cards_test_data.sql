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

-- IF-35 provenance: card 1 spans 2 signals on 2 platforms; cards 2 and 4 have a last_seen_at
-- (4 newer than 1, 1 newer than 2); the rest stay null. llm_model/prompt_version must never be exposed.
update if_test.opportunity_cards set signal_count = 2, platform_count = 2,
  first_seen_at = '2026-11-01T00:00:00Z', last_seen_at = '2026-11-05T00:00:00Z',
  llm_model = 'internal-llm-model', prompt_version = 'internal-prompt-v1' where id = 1;
update if_test.opportunity_cards set signal_count = 1, platform_count = 1,
  first_seen_at = '2026-11-02T00:00:00Z', last_seen_at = '2026-11-02T00:00:00Z' where id = 2;
update if_test.opportunity_cards set last_seen_at = '2026-11-07T00:00:00Z' where id = 4;
-- IF-37: cards 3 and 6 did not pass the B2B filter, card 5 is unknown (null); the rest are B2B.
update if_test.opportunity_cards set is_b2b_filtered = false where id in (3, 6);
update if_test.opportunity_cards set is_b2b_filtered = null where id = 5;

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

-- Ingestion runs (IF-23): github ran twice (latest Partial), hackernews once with no finished_at,
-- reddit and stackexchange never ran. error_summary is set so tests can prove it is never exposed.
insert into if_test.ingestion_runs
  (source_platform, started_at, finished_at, status, fetched_count, inserted_count, skipped_count, error_summary)
values
  ('github',     '2026-11-15T00:00:00Z', '2026-11-15T00:05:00Z', 'Success', 10, 10, 0, null),
  ('github',     '2026-11-16T00:00:00Z', '2026-11-16T00:02:00Z', 'Partial',  4,  3, 1, 'secret-ish error detail'),
  ('hackernews', '2026-11-16T06:00:00Z', null,                   'Failed',   0,  0, 0, 'timeout');
