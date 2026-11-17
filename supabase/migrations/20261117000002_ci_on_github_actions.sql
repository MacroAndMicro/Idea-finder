-- CI moved from GitLab CI to GitHub Actions on the mirror (reports status back to GitLab).
update public.system_prompts set content = replace(content,
  $s$a GitLab CI pipeline must run on the MR and pass, and the MR must not touch `.gitlab-ci.yml`, secrets, or auth/billing code unless the ticket says so.$s$,
  $s$the MR's CI must run and pass. CI runs as GitHub Actions on the GitHub mirror and reports back to GitLab as the external pipeline / commit status `github-actions` (allow a few minutes after pushing for the mirror to sync and CI to finish). The MR must not touch `.github/workflows/`, secrets, or auth/billing code unless the ticket says so.$s$)
where key = 'agent_operating_manual';
