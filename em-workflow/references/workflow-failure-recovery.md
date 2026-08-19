When background sub-agents complete with failures (Bash permission denied, external command errors, timeouts, skipped results, etc.), invoke the `workflow-doctor` agent to analyze the JSONL logs and produce a diagnostic report BEFORE presenting the final workflow results to the user.

Trigger conditions:
- Any sub-agent returns with `is_error: true`
- Any sub-agent output contains "Permission to use ... has been denied"
- Any sub-agent output contains "skipped: true" unexpectedly
- Any Codex second-opinion-agent fails to execute the wrapper script

Pass to workflow-doctor:
- `agent_ids`: The IDs of all failed/skipped agents
- `symptom`: Brief description of what failed

The workflow-doctor report is saved to `./tmp/workflow-doctor-recommend-{timestamp}.md`. Include a summary of the findings in the final workflow output presented to the user.
