# Merge Result Contract (em-workflow merge skill)

This document is the sole owner of the merge skill's structured result: its
key set and key order, the `merge_result` / `route` / `reason` vocabularies,
the reason-code table, the value rules, the confidentiality rule and the
fixed fallback result. `scripts/merge-result.py` renders a result that
conforms to it, and `skills/merge/SKILL.md` makes that rendering the final
message of every run.

## Purpose

The loop-develop dispatcher reads the last assistant message of a
`/em-workflow:merge --batch <feature>` run and nothing else. Every terminal of
the run ends with exactly one result, except the usage display. A terminal
that reaches the end without a result is read by the dispatcher as an
abnormal outcome, so the skill prints the fallback result (see `## Fallback
result`) rather than nothing.

## Result format

The layout, quoting and escaping of the result are those of
`references/batch-terminal-line.md`: see its `## Result format` and
`## Escaping` sections. This document does not restate them. It states only
what differs: the key set and the vocabularies.

The result carries exactly these eight keys, each written once, in this fixed
order:

```yaml
merge_result: "not_merged"
feature: "unattended-merge"
route: "pr"
reason: "ci_failed"
pr_url: "https://github.com/example-org/sample-repo/pull/12"
merge_commit: ""
worktree_removed: "false"
detail: "a pull request check failed"
```

Every value is a double-quoted string. `worktree_removed` is written as the
string `"true"` or `"false"`.

| Key | Meaning |
|---|---|
| `merge_result` | How the run ended; one of `## Result values` |
| `feature` | The feature name the run was asked to merge; empty when no valid feature name was available |
| `route` | The merge route; one of `## Route values` |
| `reason` | Why the feature is not merged; one of `## Reason codes`; empty when merged |
| `pr_url` | The pull request the run created or found; empty when there is none |
| `merge_commit` | The commit that merged the feature into its base branch, when the run knows it; empty otherwise |
| `worktree_removed` | Whether the run removed the feature's integration worktree |
| `detail` | A one-line, human-facing description |

## Result values

| Value | Meaning |
|---|---|
| `merged` | This run merged the feature into its base branch |
| `already_merged` | The feature was already merged into its base branch; this run merged nothing |
| `not_merged` | The feature is not merged; `reason` says why |

## Route values

| Value | Meaning |
|---|---|
| `pr` | The merge goes through a pull request |
| `local` | The merge is made in the main working tree with a local merge |
| `none` | The route was not decided before the run ended |

## Reason codes

The set below is closed: no other code is written. `reason` is empty for
`merged` and `already_merged`, and mandatory for `not_merged`.

| Code | Condition | Emitted by |
|---|---|---|
| `invalid_arguments` | `--batch` is given but the remaining arguments are not exactly one feature name | the skill |
| `invalid_feature_name` | The feature name fails the feature-name pattern | the skill, merge-preflight |
| `integration_branch_missing` | `em-workflow/<feature>/integration` does not exist | merge-preflight |
| `record_unreadable` | workflow.yaml or the latest review round record is missing, unparseable or malformed | merge-preflight |
| `base_branch_invalid` | The base branch is missing, unsafe, or (local route) absent locally | merge-preflight, merge-git route |
| `precondition_unmet` | A step is not completed or skipped, or verify's result is fail | merge-preflight |
| `unresolved_findings` | The latest review round has critical or high findings whose resolution is neither fixed nor declined | merge-preflight |
| `commands_unapproved` | A non-empty verification command is not approved, or approval cannot be confirmed | merge-preflight |
| `remote_unresolved` | No remote can be chosen, the remote name is unsafe, or gh's default repository differs from the chosen remote's | merge-git route, merge-pr repo |
| `remote_not_github` | gh cannot resolve the chosen remote to a GitHub repository | merge-pr repo |
| `pr_closed` | Only closed unmerged pull requests exist, or the pull request is no longer open at the pre-merge check | merge-pr |
| `pr_draft` | The open pull request is a draft | merge-pr |
| `pr_conflicting` | gh reports the pull request as conflicting at the pre-merge check | merge-pr state |
| `pr_create_failed` | Creating the pull request failed | the skill |
| `lock_busy` | Another run holds the merge lock | merge-lock |
| `lock_lost` | This run does not (or no longer) hold the merge lock | merge-lock verify |
| `worktree_not_clean` | The integration worktree is dirty, on another branch, or inconsistently registered | merge-git worktree-state |
| `conflict_unattributable` | A conflict cannot be attributed to a base-side feature with a readable spec | the skill |
| `verification_failed` | A build, test or e2e command failed or timed out | the skill |
| `push_rejected` | The push of the integration branch was rejected | the skill |
| `ci_failed` | A pull request check failed or was cancelled | merge-ci-wait |
| `ci_timeout` | Checks are still pending at the 60-minute deadline | merge-ci-wait |
| `pr_head_moved` | The pull request head differs from the pushed and verified commit | merge-ci-wait, merge-pr state |
| `base_moving` | The base branch moved again after 3 redos | merge-git base-check |
| `main_tree_not_ready` | The main working tree is not on the base branch or is not clean | merge-git main-tree |
| `merge_failed` | The pull request merge or the main-tree merge failed | the skill |
| `git_failed` | An unexpected git failure: fetch, worktree add, a non-conflict merge failure, or merge abort | merge-git, the skill |
| `internal_error` | A script crash, unparseable script output, or rejected renderer input | the skill, merge-result |

## Field values

- `feature` — empty, or matches `^[a-z0-9][a-z0-9-]*$`.
- `merge_commit` — empty, or 40 lowercase hexadecimal characters.
- `pr_url` — empty, or an `https://` URL made only of the characters a URL may
  carry (no space, no control character, no double quote, no backslash).
- `worktree_removed` — `true` or `false`.
- `detail` — a single line, possibly empty. Before escaping, every control
  character that `references/batch-terminal-line.md`'s `## Escaping`
  writes as a `\uXXXX` sequence, every CR, LF and TAB, and every unpaired
  surrogate is replaced with a space, runs of spaces collapse to one, and the
  ends are trimmed. A `detail` of at most 1000 characters (Unicode code points)
  is kept whole; a longer one is cut to its first 997 characters followed by
  `...`. The redaction of `## Confidentiality` is applied first, so the cap
  counts the redacted text.
- `result`, `route` and `reason` — one of the three vocabularies above.

## Confidentiality

The confidentiality constraint of `references/batch-terminal-line.md`'s
`## Responsibility boundary` applies unchanged: the result is relayed outside
em-workflow's own process boundary, so it carries no confidential information.

On top of that, the replacements of `references/doc-redaction.md` are applied
to every value before the value is validated and written:

| Found in a value | Written instead |
|---|---|
| A Notion URL | `<notion-url>` |
| An absolute path under the project root | The path relative to the project root (the root itself is `.`) |
| Any other absolute path under the home directory | The `~/...` form |

A value that is still invalid after the replacement (a `pr_url` naming a Notion
page, for example) is rejected like any other invalid value, without being
echoed. The project root is an input of the renderer used only for this
replacement; it is never written into the result.

## Renderer

`scripts/merge-result.py` takes one argument, the path of a JSON input
document, and prints one result. The skill writes the document with its
file-writing tool and never assembles it through the shell.

The document is one JSON object with the fields `result`, `feature`, `route`,
`reason`, `pr_url`, `merge_commit`, `worktree_removed` (`true` or `false`) and
`detail`, and the optional `project_root`. All eight fields are required. Any
other key is ignored and never written.

The renderer checks every field against `## Result values`, `## Route values`,
`## Reason codes` and `## Field values`, and checks that `reason` is mandatory
for `not_merged` and empty otherwise. When the document is missing, unreadable,
not JSON or not a JSON object, when the argument count is wrong, or when any
check fails, the printed result is `not_merged` with `reason` `internal_error`:

- `detail` is `invalid renderer input: field <name>` for the first failing
  field in key order, or `invalid renderer input: ...` followed by a fixed
  description when the document as a whole is unusable. It never echoes the
  invalid value.
- Each of `feature`, `route`, `pr_url`, `merge_commit` and `worktree_removed`
  keeps its input value when that value is valid on its own, and is otherwise
  empty (`route` is `none`, `worktree_removed` is `false`).

The exit code is 0 whenever a result was printed. It is non-zero only when
nothing could be printed.

## Fallback result

When the renderer cannot run, or exits non-zero, the skill prints this result
verbatim as its whole final message:

```yaml
merge_result: "not_merged"
feature: ""
route: "none"
reason: "internal_error"
pr_url: ""
merge_commit: ""
worktree_removed: "false"
detail: "the merge result renderer could not run"
```
