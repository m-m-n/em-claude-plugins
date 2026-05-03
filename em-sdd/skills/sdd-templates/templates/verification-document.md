# VERIFICATION.md テンプレート

このファイルは `implementation-executor` エージェントの Phase 4 で使用されるテンプレートです。
Phase 3 の実行結果から `{placeholder}` を埋めてください。

---

```markdown
# {Feature Name} Implementation Verification

**Date:** {YYYY-MM-DD}
**Status:** ✅ Implementation Complete
**All Tests:** ✅ PASS

## Implementation Summary

{Brief overview of what was implemented}

### Phase Summary ✅
- [x] Phase 1: {Phase Name}
- [x] Phase 2: {Phase Name}
...

## Code Quality Verification

### Build Status
```bash
$ {build command}
✅ Build successful
```

### Test Results
```bash
$ {test command}
✅ All tests PASS
```

### Code Formatting
```bash
$ {format command}
✅ All code formatted
```

### File Size Check

**CRITICAL: Verify file sizes before completing implementation.**

Run this check on modified files:
```bash
wc -l path/to/modified/files/*.go | sort -rn
```

| Threshold | Status | Action |
|-----------|--------|--------|
| ≤500 lines | ✅ OK | No action needed |
| 501-1000 lines | ⚠️ Warning | Consider splitting in future changes |
| >1000 lines | 🚨 **BLOCKER** | Must split before proceeding |

**If any file exceeds 1000 lines:**
1. **Stop the current implementation**
2. Analyze the file structure for logical split points
3. Split by responsibility or feature:
   - `model.go` → `model.go` + `model_handlers.go` + `model_navigation.go`
   - `pane.go` → `pane.go` + `pane_sort.go` + `pane_filter.go`
4. Move related code to new files
5. Update imports and run tests
6. Resume implementation

**Rationale:**
- Files >1000 lines exceed AI context windows
- Large files cause incomplete reads and missed context
- Smaller files improve maintainability and code review

## Feature Implementation Checklist

{For each requirement from SPEC.md}
- [x] Requirement description (SPEC §section)

**Implementation:**
- `path/to/file.go:line` - Description

## Test Coverage

### Unit Tests
- `path/to/test.go` - Test description

### E2E Tests
{Project-specific E2E framework, if any. Otherwise omit this subsection.}
- Run: `{e2e_test_command from sdd.yaml}`
- Test scenario description

## E2E Testing

{Describe the project's E2E framework here, if any (Docker, Playwright, Cypress, tauri-driver, etc.). em-sdd does not prescribe one.}

### Existing E2E Regression
- Result: {Phase 3.8 result: PASS / FAIL / SKIPPED}
- Command: {executed command}

### New E2E Test Scenarios
- [ ] {Scenario 1}
- [ ] {Scenario 2}

## Manual Testing (E2E Not Possible)

### Items Requiring Human Judgment
- [ ] {Manual-only scenario}

## Known Limitations

1. {Limitation description}

## Compliance with SPEC.md

### Success Criteria
- [x] Criterion 1 ✅
- [x] Criterion 2 ✅
...

## Conclusion

✅ **All implementation phases complete**
✅ **All tests pass**
✅ **Build succeeds**
✅ **SPEC.md success criteria met**

**Next Steps:**
1. Run Docker E2E tests (see E2E Testing section above)
2. Perform manual testing for E2E-not-possible items
3. Gather feedback
4. Address any issues
```
