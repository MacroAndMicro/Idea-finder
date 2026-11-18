-- Agents push-notify the founder whenever a run leaves something waiting on them.
update public.system_prompts set content = replace(content,
  $s$Insert one `agent_run_reports` row, then print a short summary.$s$,
  $s$Insert one `agent_run_reports` row, then print a short summary. If anything from this run now waits on the founder (an MR to review and merge, an inbox question, a blocker, a rollback), also send ONE push notification (PushNotification tool) that says what is needed and includes the MR or ticket link. No notification when nothing needs the founder.$s$)
where key = 'agent_operating_manual';
