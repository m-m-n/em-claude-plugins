---
name: sdd-templates
description: SDD workflow document templates (requirements, spec, test readme, verification). Referenced by requirements-spec-creator and implementation-executor agents.
user-invocable: false
---

# SDD Document Templates

Templates for documents generated during the SDD workflow.

## Templates

| Template | Used by | Phase |
|----------|---------|-------|
| [requirements-document.md](templates/requirements-document.md) | requirements-spec-creator | Phase 4 (要件定義書.md) |
| [spec-document.md](templates/spec-document.md) | requirements-spec-creator | Phase 5 (SPEC.md) |
| [test-readme.md](templates/test-readme.md) | requirements-spec-creator | Phase 0.5 (test/README.md) |
| [verification-document.md](templates/verification-document.md) | implementation-executor | Phase 4 (VERIFICATION.md) |

## Usage

Agents read templates with `Read` tool from `${CLAUDE_PLUGIN_ROOT}/skills/sdd-templates/templates/{file}` and fill in `{placeholder}` values from gathered context.
