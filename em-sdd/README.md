# em-sdd

Spec-Driven Development (SDD) workflow orchestrator for Claude Code.

Walks a feature through `create-spec → create-plan → verify-plan → implement → check → verify`, tracking progress in `doc/tasks/{feature}/sdd.yaml`. Per-step skills are invoked internally by the orchestrator and are not user-invocable.

## Commands

| Command | Purpose |
|---------|---------|
| `/em-sdd:sdd` | Run the full workflow (resumes from `sdd.yaml` progress) |
| `/em-sdd:sdd status` | Show current workflow state |
| `/em-sdd:sdd update-spec` | Update SPEC.md and cascade to downstream artifacts |

## ⚠️ Trust boundary: sdd.yaml is executed

`sdd.yaml` records project-specific shell commands:

```yaml
project:
  components:
    main:
      build_command: "..."
      test_command: "..."
      format_command: "..."
      e2e_test_command: "..."
```

These are **passed to `Bash` by SDD agents** (`tdd-implementation-verifier`, `verification-executor`, `implementation-executor`) during the workflow.

**Treat `sdd.yaml` like a `Makefile` or `package.json` script section** — only run SDD against repositories whose `sdd.yaml` you trust. A malicious `sdd.yaml` (smuggled in via PR or fetched from an untrusted clone) can execute arbitrary commands when you run `/em-sdd:sdd.4-implement` / `/em-sdd:sdd.5-check` / `/em-sdd:sdd.6-verify`.

The agents present each command for approval the first time they run it in a session, but you should still review `sdd.yaml` before working in an untrusted repo.

## Auto-continuation (Stop hook)

The plugin ships a `Stop` hook (`hooks/sdd-stop-guard.ts`) that prevents the orchestrator from halting mid-workflow. It activates only when an actively-modified `sdd.yaml` exists in `cwd/doc/tasks/*/` and there is a non-completed step that does not require user intervention (`failed` / `needs_update` are excluded).

**Requirement**: `bun` must be on `$PATH`. Install via `curl -fsSL https://bun.sh/install | bash` if missing.

Behavior:

- When triggered, the hook exits with code 2 and feeds Claude an instruction to read `sdd.yaml` and invoke the next sub-skill.
- Per `(session_id, step_id)` retry counter caps consecutive blocks at 3 (escape hatch to avoid infinite loops).
- Outside SDD projects (no `sdd.yaml` in `cwd/doc/tasks/*/`) or when `sdd.yaml` was not touched within the last 10 minutes, the hook is a silent no-op.
- Cold start ≈ 20ms (well under the 10s hook timeout).

Tunables via env vars:

- `EM_SDD_STOP_GUARD_RECENCY` — recency window in seconds (default `600`)
- `EM_SDD_STOP_GUARD_MAX_RETRIES` — max consecutive blocks per step (default `3`)

## Out of scope (intentionally)

- **E2E test framework** — em-sdd reads `e2e_test_command` from `sdd.yaml` if present, but does not bundle a framework. Choose Docker / Playwright / Cypress / tauri-driver as the project requires.
- **Cross-model second opinion on the design** — run `/em-review:multi-review` after the SDD workflow completes if you want independent cross-validation.
- **Language-specific implementer agents** — em-sdd does TDD inline. Load language-specific skills separately if needed.
- **Code review** — pick whatever review tool you prefer once SDD finishes.

## Bundled artifacts

```
em-sdd/
├── agents/                              # 7 agents (all internal, no external deps)
│   ├── requirements-spec-creator.md     # interactive requirement gathering
│   ├── implementation-planner.md        # IMPLEMENTATION.md + VERIFICATION.md
│   ├── plan-consistency-verifier.md     # design review (Claude-only)
│   ├── implementation-executor.md       # TDD execution
│   ├── tdd-implementation-verifier.md   # build/test runner (haiku)
│   ├── verification-executor.md         # SPEC compliance / E2E / etc.
│   └── spec-updater.md                  # spec change cascading
├── skills/
│   ├── sdd/                             # main orchestrator
│   ├── sdd.1-create-spec/ … sdd.6-verify/
│   ├── sdd.status/ sdd.update-spec/
│   ├── sdd-templates/                   # 4 document templates
│   └── implementation-plan-writing/     # planning rules (preloaded by planner)
└── hooks/
    ├── hooks.json                       # Stop hook registration
    └── sdd-stop-guard.ts                # auto-continuation guard (Bun)
```
