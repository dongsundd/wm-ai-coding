# Harness contract

## Canonical artifact root

Use `<repo>/sdd/` as the single root for every specification-driven development artifact:

```text
sdd/
├── config.yaml
├── specs/
│   └── <capability>/
│       └── spec.md
└── changes/
    ├── <change-name>/
    │   ├── .openspec.yaml
    │   ├── proposal.md
    │   ├── design.md
    │   ├── tasks.md
    │   ├── verification.md
    │   └── specs/
    │       └── <capability>/
    │           └── spec.md
    └── archive/
        └── YYYY-MM-DD-<change-name>/
```

This is direct-root mode. Never create `openspec/`, `sdd/openspec/`, `docs/superpowers/`, `sdd/designs/`, or `sdd/plans/`. The official OpenSpec CLI cannot currently address this layout, so perform artifact transitions with repository file operations and apply the official skills as procedural guidance. Run builds, tests, Git, and source-code tools from `<repo>/`.

When Playwright evidence is necessary, store only screenshots, traces, and attachments under `sdd/changes/<change-name>/evidence/playwright/`. Never store browser profiles, cookies, tokens, or reusable authentication state.

## Pipeline and gates

| Stage | Required evidence | Exit gate |
|---|---|---|
| Discover | repository context, constraints, baseline | problem and boundaries understood |
| Research | `design.md#Playwright research` when browser behavior is in scope | observed behavior is separated from inference and requirements |
| Propose | `proposal.md` | why, scope, and impact are explicit |
| Specify | `specs/**/spec.md` | testable requirements and scenarios exist |
| Design | `design.md` | approach, tradeoffs, risks, and migration are covered |
| CodeGraph | `design.md#CodeGraph impact analysis` | entry points, call/dependency paths, blast radius, and related tests are evidenced |
| Technology profiles | `design.md#Technology profiles` | affected stacks, detected tooling, precedence, and verification commands are explicit |
| Plan | `tasks.md` | ordered, verifiable slices map to requirements |
| Implement | code plus tests | each slice passes RED-GREEN-REFACTOR evidence |
| Review | spec review then quality review | blocking findings resolved |
| Verify | fresh test/check/build output | requirements, code, tests, and tasks agree |
| Finish | final diff and risk summary | user-directed integration action |

OpenSpec's standard dependency shape is proposal first, specs and design after proposal, tasks after both, then apply. Follow the repository's selected schema if it differs.

## Canonical stage handoffs

1. `brainstorming` produces an approved design direction; `openspec-explore` may supply repository evidence. When browser behavior is in scope, `research-with-playwright` supplies observed runtime facts.
2. `openspec-propose` or `openspec-new-change` establishes the named OpenSpec change.
3. `openspec-continue-change` creates each ready artifact; `openspec-ff-change` is an explicit accelerated alternative.
4. `using-git-worktrees` establishes isolation and baseline; `writing-plans` turns artifact tasks into executable steps.
5. `openspec-apply-change` owns task progression while `test-driven-development` enforces RED-GREEN-REFACTOR. Use `systematic-debugging` when observed results diverge.
6. `requesting-code-review` checks the implementation; process feedback with `receiving-code-review` and re-verify corrections.
7. `openspec-verify-change` checks completeness against artifacts. `verification-before-completion` requires fresh evidence for the final claim.
8. `openspec-sync-specs` updates durable specs, `openspec-archive-change` closes the change, and `finishing-a-development-branch` presents integration choices.

Do not archive a change merely because implementation tasks are checked. Verification is a separate gate. Do not merge, push, or discard a branch unless authorized.

## Artifact quality

### Proposal

State the problem, goals, non-goals, affected capabilities, compatibility impact, and risks. Avoid implementation detail that belongs in design.

### Delta specs

Use normative language such as MUST or SHALL. Describe added, modified, and removed behavior. Express scenarios in Given/When/Then form where practical. Each requirement needs at least one scenario and a stable identifier usable by tasks and tests.

### Design

Use one `design.md`. Record clarified requirements, constraints, chosen approach, rejected alternatives, component/data/API changes, failure handling, security and performance considerations, rollout or migration, and unresolved questions. Do not generate a separate brainstorming design document.

Before design exits, use CodeGraph to identify the current implementation path and impact scope. Include concrete symbols, callers/callees, module dependencies, direct and transitive blast radius, related tests, graph-opaque risks, and tool evidence under `## CodeGraph impact analysis`. Broad text search cannot satisfy this gate.

Under `## Technology profiles`, select profiles from the affected CodeGraph scope and repository evidence. Use `harmonyos-ai-coding` for affected HarmonyOS/ArkTS surfaces, `python-ai-coding` for affected Python surfaces, and `rust-ai-coding` for affected Rust surfaces. Record detected versions, frameworks, repository commands, and any profile defaults that do not apply. Repository instructions and checked-in configuration outrank profile defaults.

For browser-visible changes, use Playwright MCP before design exits and record `## Playwright research`. Distinguish observed facts, inference, and desired requirements. For non-browser changes, record why Playwright is not applicable.

### Tasks

Use one `tasks.md`. Create small vertical slices containing affected files or components, requirement references, a `Profile:` entry, RED-GREEN-REFACTOR steps, and exact verification. Use `Profile: none` when no technology profile applies. Do not generate a separate Superpowers plan. Checkbox state must match reality.

### Verification

Use one `verification.md`. Map requirements to implementation and tests, then record specification review, code review, focused and broad tests, static checks, build/package results, migration checks, remaining risks, and the delivery decision. Refresh it from current evidence before completion.

Re-run CodeGraph after implementation and compare observed graph changes with the design prediction. Record unexpected dependencies and test gaps before completion.

Run final checks for every activated technology profile and record them under `## Technology profile verification`. Profile checks supplement, not replace, the repository's focused and broad verification.

For browser-visible changes, execute current delta-spec scenarios with Playwright MCP and record `## Playwright end-to-end verification`. Persist only necessary evidence under the current change and never persist authentication state.

## Execution disciplines

- Brainstorm before committing to architecture; compare at least two credible approaches for consequential choices.
- Establish a clean or understood baseline before implementation.
- Use strict TDD for behavior changes. If a test truly cannot be written first, record the reason and use the strongest executable verification available.
- Review in two passes: specification compliance, then maintainability, correctness, security, and performance.
- Debug by reproducing, gathering evidence, locating the root cause, testing the hypothesis, and only then changing code.
- Verify immediately before completion; include command, exit status, and meaningful result.
- During approved continuous execution, Do not pause between tasks. A completed task hands directly to the next ready task after its evidence is recorded; progress narration is not a continuation prompt.

## Lightweight path

Use only for a local, obvious, low-risk change with no contract, architecture, persistence, dependency, security, or migration impact. Inspect context, make the smallest change, add or update a focused test when behavior changes, run focused verification, and inspect the diff. Escalate to the full harness as soon as hidden scope appears.

## Drift handling

When implementation reveals a missing or incorrect requirement, stop that slice. Update proposal/spec/design/tasks as appropriate, regain any required approval, then resume. Never silently make the code the new source of truth.
