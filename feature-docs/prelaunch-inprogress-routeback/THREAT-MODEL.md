# Threat Model: prelaunch-inprogress-routeback

## Verdict
no-applicable-threat

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md (FR1–FR6, NFR1–NFR4), tier `full`,
task domains `concurrency` (task0001, task0002) and `data-persistence`
(task0001). The feature edits the protocol text of Step I.2.a in
`em-workflow/references/implement-phase.md` and adds document-contract tests
that read that file.

One trust boundary is touched: the orchestrator reads `journal.jsonl`, written
by other processes (the launch-guard hook, `merge-task.sh` run by implementers,
the failure-net hooks), to choose the launch-state write set (FR2, FR4). No
STRIDE category realistically applies to what this feature changes there. The
journal's last event is already the authoritative source the protocol reads in
I.2.a selection, the I.2.b reconcile and the I.2.c gate. The feature adds one
more read of the same events under the same interpretation. It adds no new
input, writer, command or privilege, and the `project_commands` approval gate
still precedes every launch (FR1).

Domain re-check: task0001 declares `data-persistence` because it changes when
task state is persisted to workflow.yaml and committed. Its files are the
protocol document and a test module that reads it. Neither is a boundary file:
that persisted write is the orchestrator's own commit inside the integration
worktree, and the journal boundary above is pre-existing and handled as
before.
