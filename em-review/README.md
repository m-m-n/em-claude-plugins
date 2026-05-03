# em-review

Parallel multi-perspective code review for the current `git diff` (or whole codebase when no git is present).

All slash commands live under the `em-review:` namespace.

## What it does

Runs up to **9 reviewers in parallel** against the current diff (or whole codebase when not in a git repo):

| Domain | Claude | GPT (Codex) |
|--------|--------|-------------|
| 🛡️ Security | ✅ | ✅ (Critical/High) |
| ⚡ Performance | ✅ | ✅ (Critical/High) |
| 🏛️ Architecture | ✅ | ✅ (Critical/High) |
| 📐 Spec | ✅ | ✅ (Critical/High) |
| 🌐 Comprehensive | ✅ (correctness + cross-cutting) | — |

The orchestrator (`/em-review:multi-review`):

1. Collects `git diff`, falls back to whole-codebase mode in non-git directories, and locates `SPEC.md`.
2. Launches all reviewers in a single turn (parallel).
3. Aggregates, deduplicates, and scores by Claude-vs-GPT agreement.
4. Runs an auto-fix loop (max 5 iterations) with regression detection.
5. Produces a final Japanese report.

When no `SPEC.md` is found, the two spec reviewers are skipped and the orchestrator runs **7 reviewers** instead of 9.

## Slash commands

### Orchestrator (the main entry point)

| Command | Behavior |
|---------|----------|
| `/em-review:multi-review` | Runs all 9 (or 7) reviewers in parallel, aggregates, fixes, reports. Inherits the main session context. |

### Individual reviewers (standalone)

Each reviewer is also runnable on its own. They run in a forked context, so invoking them does not pollute the main session. They output JSON findings.

| Command | Reviewer |
|---------|----------|
| `/em-review:security` | Claude · security |
| `/em-review:performance` | Claude · performance |
| `/em-review:architecture` | Claude · architecture |
| `/em-review:spec` | Claude · spec compliance (skips cleanly when no `SPEC.md`) |
| `/em-review:comprehensive` | Claude · correctness + cross-cutting |
| `/em-review:gpt.security` | GPT/Codex · security |
| `/em-review:gpt.performance` | GPT/Codex · performance |
| `/em-review:gpt.architecture` | GPT/Codex · architecture |
| `/em-review:gpt.spec` | GPT/Codex · spec compliance |

GPT reviewers skip cleanly when the codex CLI wrapper (`~/.claude/skills/codex-cli/scripts/run_codex_exec.sh`) is not available.

## Investigation budget

Every reviewer follows the same budget:

- The `git diff` is the authoritative source (or the full codebase in whole-codebase mode).
- At most **3 file reads** beyond the diff to resolve unclear symbols.
- Most reviews need 0 file reads.
- Only `medium` severity and above is reported. Style / naming / "nice to have" cleanup is filtered out by design.

## Output format

Each reviewer emits JSON matching `references/review-output-schema.json`. The orchestrator merges the per-reviewer JSON into a final Japanese report with:

- 概要（観点・ループ回数・スキップ状況）
- 検出結果サマリー（重要度 × 検出元 × 修正状態）
- 観点別 Claude vs GPT 対比表
- 信頼度スコア付き統合結果
- 修正ループ履歴
- 良かった点 / 推奨事項

## Confidence scoring

| Situation | Score |
|-----------|-------|
| Claude + GPT agree (same perspective, same file ±5 lines) | 95 |
| Claude only (security / performance / architecture) | 60 |
| GPT only (security / performance / architecture) | 50 |
| Spec — Claude only (GPT-spec skipped because codex unavailable) | 70 |
| Spec — Claude + GPT agree | 95 |
| Comprehensive (Claude only by design) | 65 |
| Multi-perspective bonus (≥2 Claude perspectives flag the same file ±5 lines) | +15, cap 100 |

## Architecture

```
/em-review:multi-review (skill, allowed-tools: Task, ...)
   │
   ▼
agents/multi-review-orchestrator.md (read inline by main session)
   │
   ├─ Task → multi-review-security             (Claude)
   ├─ Task → multi-review-performance          (Claude)
   ├─ Task → multi-review-architecture         (Claude)
   ├─ Task → multi-review-spec                 (Claude, when SPEC.md exists)
   ├─ Task → multi-review-comprehensive        (Claude)
   ├─ Task → multi-review-gpt-security         (Codex)
   ├─ Task → multi-review-gpt-performance      (Codex)
   ├─ Task → multi-review-gpt-architecture     (Codex)
   └─ Task → multi-review-gpt-spec             (Codex, when SPEC.md exists)
```

Each `<perspective>` skill is a thin wrapper:

```yaml
context: fork
agent: multi-review-<perspective>
```

Standalone use therefore goes through the same agent that the orchestrator invokes — no logic duplication.

## Files

```
em-review/
├── .claude-plugin/plugin.json
├── README.md                          (this file)
├── references/
│   ├── review-protocol.md             (shared protocol, single source of truth)
│   └── review-output-schema.json      (JSON Schema for findings)
├── skills/
│   ├── multi-review/SKILL.md          (orchestrator entry → /em-review:multi-review)
│   ├── security/SKILL.md              (→ /em-review:security)
│   ├── performance/SKILL.md
│   ├── architecture/SKILL.md
│   ├── spec/SKILL.md
│   ├── comprehensive/SKILL.md
│   ├── gpt.security/SKILL.md          (→ /em-review:gpt.security)
│   ├── gpt.performance/SKILL.md
│   ├── gpt.architecture/SKILL.md
│   └── gpt.spec/SKILL.md
└── agents/
    ├── multi-review-orchestrator.md
    ├── multi-review-security.md
    ├── multi-review-performance.md
    ├── multi-review-architecture.md
    ├── multi-review-spec.md
    ├── multi-review-comprehensive.md
    ├── multi-review-gpt-security.md
    ├── multi-review-gpt-performance.md
    ├── multi-review-gpt-architecture.md
    └── multi-review-gpt-spec.md
```
