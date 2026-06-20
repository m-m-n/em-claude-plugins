---
name: sdd.remove-feature
description: Removes a feature and cascades the deletion across SPEC.md, IMPLEMENTATION.md, VERIFICATION.md, README/docs, sdd.yaml, tasks.yaml, and code residue (dead code / unused imports / orphan tests)
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
---

## SDD Workflow Guard

Before executing this skill:

1. Determine the feature directory:
   - If `$ARGUMENTS` contains a path, use it
   - Otherwise, search `doc/tasks/*/sdd.yaml` with Glob
   - If multiple found, ask user to select
   - If none found: Report "SDD ワークフローが見つかりません。`/em-sdd:sdd.1-create-spec` で開始してください。" and exit

2. **Validate the resolved feature path** per the checklist's "Git safety & path validation"
   rules (`${CLAUDE_PLUGIN_ROOT}/references/feature-removal-checklist.md` is the SSOT for
   path safety — do NOT restate a weaker subset here). It scopes every subsequent
   read / edit / delete, so apply the FULL rejection set the agent also enforces:
   - Canonicalize it and require it to resolve under the repository's `doc/tasks/` root
     (reject `..`, absolute paths, and symlinks escaping that root)
   - Reject names starting with `-`, or containing whitespace / newline / CR / NUL / shell
     metacharacters (`;`, `&&`, `||`, `|`, backticks, `$(`, redirects)
   - Require an `sdd.yaml` to exist inside it
   - If validation fails: report the offending path and exit

3. Read `doc/tasks/{feature}/sdd.yaml`
   - If YAML parse error: Report error, offer `git restore` or regeneration, and exit

4. Verify `create-spec` status is "completed"
   - If not: Report "仕様書がまだ作成されていません。削除対象がありません。" and exit

## Main Execution

**Agent**: Read `${CLAUDE_PLUGIN_ROOT}/agents/feature-remover.md` and follow its instructions.

**Pass the validated feature directory path to the agent explicitly.** The agent MUST use
this resolved path and MUST NOT re-glob to pick a different feature (avoids the skill and
agent resolving different features in a multi-feature repo).

The agent preloads `${CLAUDE_PLUGIN_ROOT}/references/feature-removal-checklist.md` (the
removal knowledge SSOT) and `${CLAUDE_PLUGIN_ROOT}/references/command-execution-protocol.md`
(approval gate for the build/test sanity check).

### Workflow

1. Use the validated feature directory and run git safety on the target artifacts
2. Receive the feature/requirement to remove from the user (FR/NFR ID or description)
3. Impact analysis (using sdd.yaml requirements mapping):
   - Identify target FR/NFR IDs
   - List affected tasks (`requirements.{ID}.tasks`) and tests (`requirements.{ID}.tests`)
   - Reverse-dependency check across other requirements / tasks / docs
   - Warn if any completed task in tasks.yaml is affected
4. Present the deletion scope and get explicit approval (destructive operation)
5. Document cascade — delete feature traces from SPEC.md, IMPLEMENTATION.md,
   VERIFICATION.md, README/docs; remove `requirements.{ID}` from sdd.yaml and obsolete
   tasks from tasks.yaml; sweep for orphaned references; run the post-cascade referential
   integrity check (FR/NFR numbering preserved — gaps left, no renumbering)
6. Code residue verification — scoped + bounded detection, then (with per-item confirmation)
   remove dead code, unused imports, orphan tests, leftover config/flags, and build wiring;
   optionally run the build/test command through the approval gate
7. Output the deletion summary

## SDD Workflow Completion

This skill does NOT advance workflow steps. It removes a feature and the artifacts that
described it. Because a removal has **nothing to regenerate**, it does NOT cascade
`needs_update` to `implement`. It marks **only** the `verify` step as `needs_update` — so
the orchestrator re-runs verification to confirm the codebase still builds and tests pass
with the feature gone. If no `verify` step exists, nothing is marked.

Display:
```
機能を削除しました。

削除した機能: {FR/NFR ID and title}

再実行が必要なステップ:
  verify <- needs_update (削除後のビルド/テスト健全性を確認)   # verify step が存在する場合のみ
```

$ARGUMENTS
