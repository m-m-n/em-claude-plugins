# test/README.md テンプレート

このファイルは `requirements-spec-creator` エージェントの Phase 0.5 で使用されるテンプレートです。
ユーザーのテスティングセットアップ回答から `{placeholder}` を埋めてください。

---

```markdown
# Test Instructions for AI Agents

This document provides guidelines for AI agents when writing and executing tests.

## Test Framework

{Framework name and version}

## Test Execution

### Unit Tests
```bash
{Unit test command}
```

### Integration Tests (if applicable)
```bash
{Integration test command}
```

### E2E Tests (if applicable)
```bash
{E2E test command}
```

## Test File Organization

{Description of where test files should be placed}

## Writing Tests

### Test Naming Conventions
{Naming conventions for test functions/files}

### Test Structure
{How tests should be structured - e.g., table-driven tests for Go}

## Adding New Tests

{Instructions for adding new test cases}

## E2E Test Guidelines (if applicable)

{Specific instructions for E2E tests - helper functions, available commands, etc.}

## Common Patterns

{Project-specific testing patterns and helpers}
```
