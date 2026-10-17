# CodeGraph analysis contract

## Required design section

```markdown
## CodeGraph impact analysis

### Index evidence
- Repository:
- Revision/worktree:
- Freshness check:

### Entry points and symbols
| Symbol | Kind | Location | Role | Evidence tool |
|---|---|---|---|---|

### Call and dependency paths
| Source | Relationship | Target | Depth | Design implication |
|---|---|---|---|---|

### Blast radius
| Affected area | Direct/transitive | Risk | Expected change | Evidence tool |
|---|---|---|---|---|

### Related tests and gaps
| Production symbol | Existing tests | Coverage gap | Planned verification |
|---|---|---|---|

### Graph-opaque checks
| Targeted fallback | Why CodeGraph cannot model it | Result |
|---|---|---|

### Scope boundaries
- Expected to change:
- Explicitly unaffected:
- Uncertain:
```

## Evidence rules

- Name concrete symbols and paths; avoid generic architecture summaries.
- Distinguish direct graph edges from inferred risk.
- Record transitive depth when available.
- Treat reflection, dependency injection, runtime registration, configuration, templates, generated code, database migrations, and external services as potentially graph-opaque.
- Do not claim “no impact” from an empty result until index scope and freshness are confirmed.
- Use targeted search only after graph analysis and only for a documented graph-opaque question.

## Design exit gate

Pass only when the graph evidence explains the current implementation path, blast radius, related tests, risk boundaries, and unresolved dynamic edges. Otherwise keep the design stage incomplete.
