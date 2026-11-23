# em-claude-plugins

Personal marketplace of Claude Code plugins maintained by em.

## Layout

```
em-claude-plugins/
├── .claude-plugin/
│   └── marketplace.json      # marketplace metadata
└── <plugin-name>/            # each plugin lives at the marketplace root
    ├── .claude-plugin/
    │   └── plugin.json
    ├── README.md
    ├── skills/               # skills (slash commands + injected knowledge)
    ├── agents/               # subagent definitions
    └── references/           # shared protocol & schema (plugin SSOT)
```

Each plugin lives at the marketplace root as `./<plugin-name>/`. Adding a new plugin (e.g. `foo`) means creating `./foo/.claude-plugin/plugin.json` and registering it in `marketplace.json`.

## Plugins

| Plugin | Description |
|--------|-------------|
| [em-workflow](./em-workflow/) | Unified SDD + parallel-implementation + dynamic-review workflow. `/em-workflow:develop` drives spec → plan → wave-based parallel implementation in git worktrees → dynamic review → verify → retrospect. |
| [em-review](./em-review/) | Standalone version of the em-workflow review phase. `/em-review:multi-review` runs dynamically selected, skill-injected parallel reviewers (Claude + optional GPT/Codex cross-validation) with bounded auto-fix. Never commits. |
| [plugin-dev](./plugin-dev/) | Toolbox for developing Claude Code plugins. The `plugin-dev` skill guides creating a new plugin and updating an existing one; plugin versions are bumped by GitHub Actions on merge to main. |

### How the plugins relate

em-workflow is the full development workflow; em-review is its review phase extracted (forked) into a standalone plugin for everyday reviews outside the SDD flow — quick diff reviews and GitHub PR reviews. Feature development driven by `/em-workflow:develop` already includes the same review protocol, so em-review is not needed there. Install either or both; they do not interfere.

## Adding this marketplace

```
/plugin marketplace add m-m-n/em-claude-plugins
```

Then install a specific plugin:

```
/plugin install em-workflow@em-claude-plugins
/plugin install em-review@em-claude-plugins
/plugin install plugin-dev@em-claude-plugins
```

The marketplace is named `em-claude-plugins`; each plugin's name becomes its slash-command namespace (`/em-workflow:...`, `/em-review:...`, `/plugin-dev:...`).

## Maintenance

Plugin versions are bumped by `.github/workflows/plugin-version-bump.yml`. The procedures below are run by hand.

### Recovering a lost version update

When the version-update commit of the Actions workflow is lost from main, run the workflow once with `workflow_dispatch` on `main`, giving the plugin name and a `min_version`. When the plugin's current version is lower than or equal to `min_version` and has the same major and minor, the run writes `min_version` with its patch raised by 1 to the plugin's `plugin.json` and to its entry in `.claude-plugin/marketplace.json`, and a pull request carrying the change is created and merged.

To recover the lost em-workflow update, run it with:

- ref: `main`
- plugin: `em-workflow`
- min_version: `0.5.3` (the version recorded by the lost update commit `f87807a8e`, "chore: bump plugin versions (em-workflow@0.5.3)")

Then confirm:

- The pull request created by the run is merged into main.
- After pulling main, em-workflow's version in `em-workflow/.claude-plugin/plugin.json` and in its entry in `.claude-plugin/marketplace.json` are equal, and greater than `min_version`.

When the current version already exceeds `min_version`, the run changes nothing and succeeds.

### Confirming the installed cache

After the run above, update the marketplace in Claude Code and restart Claude Code. Then confirm in the installed cache:

- `~/.claude/plugins/cache/<marketplace>/em-workflow/` has a directory for em-workflow's version after the run above.
- Files in that directory match main, for example `references/phases/create-plan-phase.md` and `references/contracts/planner-contract.md` under em-workflow.
