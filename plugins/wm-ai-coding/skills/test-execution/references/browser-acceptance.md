# Browser acceptance evidence contract

```markdown
## Playwright end-to-end verification

### Environment
- URL/route:
- Revision:
- Browser/device:
- Authentication mode:

### Scenario results
| Requirement | Scenario | Result | Evidence |
|---|---|---|---|

### Console and network findings
| Type | Finding | Impact |
|---|---|---|

### Accessibility verification
| Check | Result | Remaining issue |
|---|---|---|

### Research-to-implementation comparison
- Preserved behavior:
- Intentional differences:
- Unexpected regressions:
```

## Evidence paths

Use only when necessary:

```text
sdd/changes/<change-name>/evidence/playwright/
├── screenshots/
├── traces/
└── attachments/
```

Never store browser profiles, cookies, local storage, session storage, passwords, tokens, or reusable authentication state in these paths.
