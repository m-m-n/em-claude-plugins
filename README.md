# em-claude-plugins

Personal marketplace of Claude Code plugins maintained by em.

## Layout

```
em-claude-plugins/
├── .claude-plugin/
│   └── marketplace.json      # marketplace metadata
└── em-review/              # Plugin: parallel multi-perspective code review
    ├── .claude-plugin/
    │   └── plugin.json
    ├── README.md
    ├── skills/                # User-invokable skills (one per slash command)
    ├── agents/                # Subagent definitions used by the orchestrator
    └── references/            # Shared protocol & schema
```

Each plugin lives at the marketplace root as `./<plugin-name>/`. Adding a new plugin (e.g. `foo`) means creating `./foo/.claude-plugin/plugin.json` and registering it in `marketplace.json`.

## Plugins

| Plugin | Description |
|--------|-------------|
| [em-review](./em-review/) | Parallel multi-perspective code review across 9 reviewers (5 Claude + 4 GPT/Codex). Each reviewer is also usable standalone via `/em-review:<perspective>`. |
| [em-sdd](./em-sdd/) | Spec-Driven Development workflow orchestrator. Drives `create-spec → create-plan → verify-plan → implement → check → verify` against `sdd.yaml`. Entry point `/em-sdd:sdd`; each step usable standalone via `/em-sdd:sdd.<step>`. |

## Adding this marketplace

```
/plugin marketplace add m-m-n/em-claude-plugins
```

Then install a specific plugin:

```
/plugin install em-review@em-claude-plugins
/plugin install em-sdd@em-claude-plugins
```

The marketplace is named `em-claude-plugins`; each plugin's name becomes its slash-command namespace (`/em-review:...`, `/em-sdd:...`).
