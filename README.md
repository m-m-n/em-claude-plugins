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
| [em-review](./em-review/) | Standalone version of the em-workflow review phase. `/em-review:review` runs dynamically selected, skill-injected parallel reviewers (Claude + optional GPT/Codex cross-validation) with bounded auto-fix. Never commits. |

## Adding this marketplace

```
/plugin marketplace add m-m-n/em-claude-plugins
```

Then install a specific plugin:

```
/plugin install em-workflow@em-claude-plugins
/plugin install em-review@em-claude-plugins
```

The marketplace is named `em-claude-plugins`; each plugin's name becomes its slash-command namespace (`/em-workflow:...`, `/em-review:...`).
