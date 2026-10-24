# Doc Redaction

What the workflow commits must not carry identifiers of the user's machine or
of external task trackers. This document is the SSOT for that rule; other
documents cite it.

## Scope

Everything the workflow writes to be committed:

- files under `feature-docs/` and `test-docs/`
- commit messages
- worker and reviewer output that the orchestrator persists into those files
  (findings, reports, packets)

## Forbidden content and replacements

| Forbidden | Write instead |
| --- | --- |
| A Notion URL (host `notion.so`, `notion.site`, `notion.com`, or a subdomain of them) | `<notion-url>`, or drop it |
| An absolute path under the user's home directory (e.g. `/home/<user>/...`) | A path relative to the repository root; outside the repository, `~/...` |

- Paths inside the repository are written relative to the repository root,
  even when the prompt handed over an absolute path.
- A worktree path is written relative to the repository root
  (`.claude/worktrees/...`).
- An example path in a test case or a SPEC uses a placeholder home such as
  `/home/user`, never the real one.

## Persisting worker output

The orchestrator applies the replacements above to worker and reviewer
output before writing it into a committed file.

## Enforcement

`hooks/doc-redaction-guard.py` denies a Write / Edit / MultiEdit into
`feature-docs/` or `test-docs/` whose new content contains forbidden content.
On denial, apply the replacements and write again.
