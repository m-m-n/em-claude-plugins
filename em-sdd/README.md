# em-sdd

Spec-Driven Development (SDD) workflow orchestrator for Claude Code.

Walks a feature through `create-spec → create-plan → verify-plan → implement → check → verify`, tracking progress in `doc/tasks/{feature}/sdd.yaml`. Each step is also usable standalone via `/em-sdd:sdd.<step>`.

## Commands

| Command | Purpose |
|---------|---------|
| `/em-sdd:sdd` | Run the full workflow (resumes from `sdd.yaml` progress) |
| `/em-sdd:sdd status` | Show current workflow state |
| `/em-sdd:sdd update-spec` | Update SPEC.md and cascade to downstream artifacts |
| `/em-sdd:sdd.1-create-spec` | Step 1: requirements + SPEC.md (interactive) |
| `/em-sdd:sdd.2-create-plan` | Step 2: IMPLEMENTATION.md + VERIFICATION.md |
| `/em-sdd:sdd.3-verify-plan` | Step 3: consistency / design review |
| `/em-sdd:sdd.4-implement` | Step 4: TDD implementation |
| `/em-sdd:sdd.5-check` | Step 5: build / test / format / static analysis |
| `/em-sdd:sdd.6-verify` | Step 6: SPEC compliance / E2E / file structure |

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
└── skills/
    ├── sdd/                             # main orchestrator
    ├── sdd.1-create-spec/ … sdd.6-verify/
    ├── sdd.status/ sdd.update-spec/
    ├── sdd-templates/                   # 4 document templates
    └── implementation-plan-writing/     # planning rules (preloaded by planner)
```
