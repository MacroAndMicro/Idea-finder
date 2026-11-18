-- Agents wait up to 10 minutes for the github-actions CI result before handing an MR to the founder.
update public.system_prompts set content = replace(content,
  $s$**If no CI pipeline runs on the MR, do not merge** — leave it in `Ready for QA`, set `needs_founder`, and note "no CI gate".$s$,
  $s$**Wait for CI before deciding:** after pushing, poll the MR's `github-actions` status about every 30 seconds for up to 10 minutes (mirror sync plus CI usually takes 2–4 minutes). Merge only when it is `success`; if it fails, read the run log, fix, push and wait again. **If no CI result appears within 10 minutes, do not merge** — leave it in `Ready for QA`, set `needs_founder`, and note "no CI result after 10 min".$s$)
where key = 'agent_operating_manual';
