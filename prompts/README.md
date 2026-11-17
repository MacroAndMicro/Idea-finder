# Agent prompts

**The master copy of every prompt is the Supabase `system_prompts` table.** These files are a snapshot for review in git; edit the database, not these files.

Each agent loads, in order: `master_agent_prompt`, `agent_operating_manual`, then its own prompt.

| Key | Agent |
|---|---|
| `master_agent_prompt` | Product spec (shared) |
| `agent_operating_manual` | Shared rules: names, tables, statuses, inbox, MRs, secrets (shared) |
| `pm_agent_prompt` | PM Agent |
| `data_llm_engineer_agent_prompt` | Data Engineer |
| `senior_backend_engineer_agent_prompt` | Senior SWE |
| `dev_intern_agent_prompt` | Dev Intern |
| `qa_agent_prompt` | QA Agent |
| `senior_ui_ux_designer_agent_prompt` | Senior Designer |
| `user_simulator_agent_prompt` | User Simulator |

Every content change is archived automatically to `system_prompts_history` and bumps `version`.
