-- Phase 1 sources: add Hacker News and Stack Exchange (Reddit API approval pending).
alter table public.opportunity_cards drop constraint opportunity_cards_source_chk;
alter table public.opportunity_cards add constraint opportunity_cards_source_chk check (source_platform in
  ('reddit','github','hackernews','stackexchange','g2','capterra','other'));

-- Prompt updates (archive trigger keeps the previous versions).
update public.system_prompts set content = replace(replace(replace(content,
  $s$Official Reddit API (OAuth) only.
- **GitHub Issues & Discussions** — workarounds, broken integrations, popular feature requests on open-source tools. Official GitHub API with a token only.
$s$,
  $s$Official Reddit API (OAuth) only; access approval is pending, so build and test against recorded fixtures until keys arrive.
- **GitHub Issues & Discussions** — workarounds, broken integrations, popular feature requests on open-source tools. Official GitHub API with a token only.
- **Hacker News** — "Ask HN" threads and comments: founder and developer pain points. Official HN API and Algolia HN Search API (no key).
- **Stack Exchange** (Stack Overflow, Server Fault, Super User, etc.) — recurring "how do I…" questions about broken tools and workarounds. Official Stack Exchange API with `STACKEXCHANGE_KEY`; respect its quota and backoff.
$s$),
  $s$(`reddit`, `github`, `g2`, `capterra`, `other`)$s$,
  $s$(`reddit`, `github`, `hackernews`, `stackexchange`, `g2`, `capterra`, `other`)$s$),
  $s$- **Free:** Reddit + GitHub;$s$,
  $s$- **Free:** Reddit, GitHub, Hacker News, Stack Exchange;$s$)
where key = 'master_agent_prompt';

update public.system_prompts set content = replace(content,
  $s$`GITHUB_TOKEN`, `TEST_USER_*`$s$,
  $s$`GITHUB_TOKEN`, `STACKEXCHANGE_KEY`, `TEST_USER_*`$s$)
where key = 'agent_operating_manual';

update public.system_prompts set content = replace(content,
  $s$and GitHub Issues/Discussions via the official API (`GITHUB_TOKEN`).$s$,
  $s$GitHub Issues/Discussions via the official API (`GITHUB_TOKEN`), Hacker News via the official HN API and Algolia HN Search API (no key), and Stack Exchange via the official API (`STACKEXCHANGE_KEY`). Reddit API access is pending approval: build the Reddit adapter against recorded fixtures now so it works as soon as keys are added; start live ingestion with GitHub, Hacker News and Stack Exchange.$s$)
where key = 'data_llm_engineer_agent_prompt';

update public.system_prompts set content = replace(content,
  $s$run Reddit/GitHub adapters against fixtures$s$,
  $s$run the Phase 1 adapters (Reddit, GitHub, Hacker News, Stack Exchange) against fixtures$s$)
where key = 'qa_agent_prompt';

update public.system_prompts set content = replace(content,
  $s$(Reddit, GitHub)$s$,
  $s$(Reddit, GitHub, Hacker News, Stack Exchange)$s$)
where key = 'user_simulator_agent_prompt';

update public.system_prompts set content = replace(content,
  $s$Ingestion adapters (Reddit, GitHub)$s$,
  $s$Ingestion adapters (Reddit, GitHub, Hacker News, Stack Exchange)$s$)
where key = 'pm_agent_prompt';
