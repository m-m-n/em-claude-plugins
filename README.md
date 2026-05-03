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

## Adding this marketplace

```
/plugin marketplace add /path/to/em-claude-plugins
```

…or by URL once published:

```
/plugin marketplace add <url-to-marketplace.json-source>
```

Then install a specific plugin:

```
/plugin install em-review@em-claude-plugins
```

The marketplace is named `em-claude-plugins`; the plugin within it is named `em-review` (becomes the slash-command namespace `/em-review:...`).
