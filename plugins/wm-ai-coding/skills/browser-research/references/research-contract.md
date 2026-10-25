# Playwright research contract

## Design section

```markdown
## Playwright research

### Scope and environment
- Target:
- Purpose:
- Browser/device:
- Authentication mode:
- Allowed mutations:

### Observed user journey
| Step | Action | Observed result | Evidence |
|---|---|---|---|

### States and transitions
| Initial state | Action | Resulting state | Constraint |
|---|---|---|---|

### Errors and edge cases
| Scenario | Observed | Desired |
|---|---|---|

### Accessibility observations
| Flow/element | Observation | Design implication |
|---|---|---|

### Requirement implications
- Observed:
- Inferred:
- Required:
- Non-goals:
- Unverified assumptions:
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
