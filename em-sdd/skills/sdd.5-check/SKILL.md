---
name: sdd.5-check
description: Quick check - build, test, format, static analysis after implementation
user-invocable: false
allowed-tools: Task, Read, Glob, Grep, AskUserQuestion
---

## SDD Workflow Guard

Before executing this skill:

1. Determine the feature directory:
   - If `$ARGUMENTS` contains a path, use it
   - Otherwise, search `doc/tasks/*/sdd.yaml` with Glob
   - If multiple found, ask user to select
   - If none found, check for legacy artifacts and offer to generate sdd.yaml

2. Read `doc/tasks/{feature}/sdd.yaml`
   - If YAML parse error: Report error, offer `git restore` or regeneration, and exit

3. Find `check` in workflow array

4. Status checks:
   - If status is "completed": Ask "再実行する / スキップする"
   - If status is "needs_update": Ask "再実行する / スキップする"
   - If status is "in_progress": Ask "最初からやり直す / 続行する"
   - If status is "failed": Ask "再試行する / 最初からやり直す"

5. Dependency check: Verify `implement` status is "completed"
   - If not: Report "implement が未完了です。先に /em-sdd:sdd.4-implement を実行してください。" and exit

6. Set `check` status to "in_progress" and write sdd.yaml

## Quick Check Orchestrator

An orchestrator that verifies implementation quality using parallel sub-agents.
Focus: build, test, format, static analysis, and dead code detection.

### Step 1: Locate Documents

Find VERIFICATION.md, SPEC.md, and IMPLEMENTATION.md.

**Search order**:
1. If a path is specified in `$ARGUMENTS`, use that
2. Search for `doc/tasks/*/VERIFICATION.md` with Glob
3. If multiple found, use AskUserQuestion to prompt selection
4. Read SPEC.md and IMPLEMENTATION.md from the same directory

### Step 2: Read Project Commands from sdd.yaml

Read `sdd.yaml` to get project-specific commands:
- `project.components.{name}.build_command`
- `project.components.{name}.test_command`
- `project.components.{name}.format_command`

### Step 3: Execute Parallel Verification

Launch 2 verification tasks using the Task tool **within the same response**.

#### Task 1: Build + Test + Format + Static Analysis

```
subagent_type: tdd-implementation-verifier
prompt: |
  Follow ${CLAUDE_PLUGIN_ROOT}/references/command-execution-protocol.md before
  running ANY of the commands below. Each command is sourced from sdd.yaml and
  is repository-controlled — display them verbatim and prompt the user for
  approval (or use the session approval cache).

  Source: doc/tasks/{feature}/sdd.yaml

  Build Command (sdd.yaml:project.components.{name}.build_command):
    {build_command}
  Test Command (sdd.yaml:project.components.{name}.test_command):
    {test_command}
  Format Command (sdd.yaml:project.components.{name}.format_command):
    {format_command}
  Static analysis: {appropriate for language, if not in sdd.yaml}

  Run each (after approval) and report pass/fail, test count, error details.
```

#### Task 2: Dead Code Detection

```
subagent_type: verification-executor
prompt: |
  Check for dead code and unused exports in the project.
  Focus on files changed as part of the implementation.
  Report any unused functions, variables, or imports.
```

### Step 4: Integrate Results and Report

After all sub-agent results are returned:

1. Integrate the 2 results into a verification summary
2. If issues are found, include fix proposals

```
## /em-sdd:sdd.5-check Quick Check Report: {Feature Name}

### 1. Build/Test/Format/Static Analysis
{Task 1 result summary}

### 2. Dead Code Detection
{Task 2 result summary}

### Overall Judgment
All items PASS / {N} issues found
```

## SDD Workflow Completion

After this skill completes successfully:

1. Read `doc/tasks/{feature}/sdd.yaml`
2. Set `check` status to "completed"
3. Set `check` completed_at_commit to current `git rev-parse HEAD`
4. Write updated sdd.yaml

$ARGUMENTS
