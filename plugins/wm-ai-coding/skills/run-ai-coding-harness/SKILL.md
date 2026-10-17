---
name: run-ai-coding-harness
description: Orchestrate end-to-end AI-assisted software delivery with OpenSpec artifacts and Superpowers engineering disciplines. Use when Codex is asked to build a feature, fix a non-trivial bug, refactor a system, continue an OpenSpec change, execute a specification or plan, run a coding harness, or verify that implementation is ready to ship.
---

# Run AI Coding Harness

Drive work from intent to verified delivery. Treat OpenSpec artifacts as the source of truth and use Superpowers-style practices as execution gates.

Use the bundled upstream skills directly. Read each selected skill's `SKILL.md` completely before following it; this harness defines their order and handoff contract, not a replacement for their instructions.

## Start

1. Run the plugin dependency preflight with `python <plugin-root>/scripts/dependency_preflight.py --project <repo> --json`. It checks that the global `codegraph.cmd` and `playwright-mcp.cmd` commands both exist and can start, and that the current repository has a healthy `.codegraph/` index. If both commands are usable, use them without installation. If either command is missing or broken, run the preflight again with `--install` to install only the affected global npm package. If only the project index is missing, run it with `--project <repo> --init-project` to execute `codegraph init` once, then verify status. Stop when the base Node/npm runtime is missing, installation fails, or indexing fails. CodeGraph's MCP entry point is `codegraph.cmd serve --mcp` on Windows; the plugin owns this MCP registration, so do not run `codegraph install` to create a duplicate Codex registration.
2. Inspect repository instructions, status, tests, and existing `sdd/` state.
3. Perform Technology profile selection from repository evidence and the CodeGraph impact scope. Activate `harmonyos-ai-coding` for affected HarmonyOS/ArkTS surfaces, `python-ai-coding` for affected Python surfaces, and `rust-ai-coding` for affected Rust surfaces. A polyglot change may activate more than one profile; repository presence alone does not activate a profile when the change cannot affect it.
4. Read [references/workflow.md](references/workflow.md) completely.
5. Classify the request:
   - Tiny, low-risk edit: use the lightweight path defined in the reference.
   - Feature, behavior change, refactor, or material bug: use the full harness.
   - Existing OpenSpec change: resume from its earliest incomplete gate; never recreate approved artifacts.
6. Treat `<repo>/sdd/` as the only process-artifact root. Use `sdd/config.yaml`, `sdd/specs/`, and `sdd/changes/` directly. Do not create `openspec/`, `sdd/openspec/`, `docs/superpowers/`, `sdd/designs/`, or `sdd/plans/` trees.
7. Use harness-native file operations for SDD artifacts. Do not run OpenSpec CLI commands that create, update, sync, archive, or validate artifacts because the official CLI requires an `openspec/` directory. Apply the official skills' workflow semantics to the direct `sdd/` paths instead.
8. Validate the artifact contract with repository inspection, requirement mapping, tests, and `scripts/harness_state.py`; clearly report that official CLI validation is intentionally unavailable in direct-root mode.
9. Use `scripts/harness_state.py status <repo> [change-name]` to inspect objective gate evidence. The script reports evidence; it does not replace judgment.

## Route official skills

Invoke the following bundled skills at their stages:

| Harness stage | Required official skill | Purpose |
|---|---|---|
| Clarify | `brainstorming`, optionally `openspec-explore` | Refine intent and compare approaches |
| Product research | `research-with-playwright` when browser behavior is in scope | Observe current/reference user journeys and runtime behavior |
| Code impact | `analyze-codegraph-impact` | Use the semantic code graph to identify implementation paths, blast radius, dependencies, and related tests |
| Technology profiles | `harmonyos-ai-coding`, `python-ai-coding`, and/or `rust-ai-coding` when affected | Add repository-specific stack constraints without creating a separate workflow |
| Propose | `openspec-propose` or `openspec-new-change` then `openspec-continue-change` | Create the change and proposal |
| Specify/design/tasks | `openspec-continue-change`; use `openspec-ff-change` only for explicit fast-forward requests | Build OpenSpec artifacts in dependency order |
| Isolate | `using-git-worktrees` | Prepare an isolated, verified baseline when appropriate |
| Plan | `writing-plans` | Convert approved artifacts into executable slices |
| Implement | `openspec-apply-change` with `test-driven-development`; use `systematic-debugging` for failures | Implement tasks with RED-GREEN-REFACTOR evidence |
| Review | `requesting-code-review`, then `receiving-code-review` | Check spec compliance before code quality and resolve findings |
| Verify | `openspec-verify-change`, then `verification-before-completion` | Prove artifact, implementation, and test consistency |
| Deliver | `openspec-sync-specs`, `openspec-archive-change`, then `finishing-a-development-branch` as applicable | Sync durable specs, archive the change, and offer integration choices |

Use `executing-plans` for inline/batched execution. Use `subagent-driven-development` or `dispatching-parallel-agents` only when subagents are permitted and tasks are independent. Never make subagent use a prerequisite for completing the workflow.

## Full harness

### 1. Discover and clarify

- Understand the current system before proposing a solution.
- Resolve ambiguity through focused questions or safe repository evidence.
- Explore alternatives and record consequential tradeoffs.
- Do not write production code yet.
- Complete `brainstorming` before creating a consequential proposal. Use `openspec-explore` when the problem or repository needs investigation without changing code.
- When browser-visible behavior or external product research is in scope, run `research-with-playwright` before finalizing requirements. Record observed facts separately from inference and desired behavior.

### 2. Establish the OpenSpec contract

- Create or select one change under `sdd/changes/<change-name>/`.
- Write brainstorming and technical design into that change's single `design.md`.
- Write the detailed Superpowers execution plan and progress into that change's single `tasks.md`.
- Write review, test, build, coverage, and delivery evidence into that change's single `verification.md`.
- Store necessary Playwright screenshots, traces, and attachments only under the current change's `evidence/playwright/`; never store browser authentication state.
- Before finalizing design, run `analyze-codegraph-impact`. Require a complete `## CodeGraph impact analysis` section in `design.md`; do not substitute broad grep or speculative file browsing.
- Record activated profiles and detected repository tooling under `## Technology profiles` in `design.md`. Apply repository instructions and checked-in configuration before profile defaults.
- Produce `proposal.md`, delta specs, `design.md`, and `tasks.md` in dependency order.
- Write observable requirements and scenarios. Give every task a requirement or scenario reference.
- Give every implementation task a `Profile:` entry naming the applicable technology profiles or `none`, plus profile-specific verification commands.
- Get user approval when the workflow or request requires a design decision; do not infer approval.
- Prefer `openspec-propose` when the user supplied enough context to create proposal, specs, design, and tasks together. Otherwise use `openspec-new-change` and advance with `openspec-continue-change`.

### 3. Prepare execution

- Prefer an isolated branch or worktree for material work when authorized and practical.
- Verify the baseline before changes. Distinguish pre-existing failures from regressions.
- Turn `tasks.md` into small, ordered units with exact verification steps.
- Keep one active task at a time unless independent work is explicitly parallelized.
- Run `writing-plans` after OpenSpec artifacts are ready. The implementation plan must reference, not contradict, `tasks.md`.
- Derive task file paths, dependency ordering, and test targets from the CodeGraph impact evidence. Any task outside the predicted scope must update the design first.
- Before each task, load every profile named by that task and reconcile it with current repository configuration. Profile selection is preparation, not a user approval point.

### 4. Implement with evidence

- For each behavior, follow RED → GREEN → REFACTOR: add a failing test, observe the expected failure, write the minimum implementation, observe success, then improve structure.
- Debug root causes systematically; do not stack speculative fixes.
- Mark an OpenSpec task complete only after its verification passes.
- Preserve user changes and repository conventions. Avoid unrelated cleanup.
- Review each coherent slice for specification compliance first, then code quality.
- Keep `openspec-apply-change` responsible for OpenSpec task state and `test-driven-development` responsible for implementation discipline.
- Run profile-specific focused checks before marking a task complete.

### Continuous execution contract

- After the user approves the design and implementation plan and execution begins, complete all ready tasks in order without asking whether to continue.
- Do not pause between tasks. After recording one task's evidence and checkbox, immediately load the next task's profiles and start its RED step.
- Progress updates are informational and never requests for permission to continue.
- Pause only for an irreversible or destructive operation, a security-sensitive action, an external side effect that requires authorization, an unresolved scope or observable-behavior change, or a plan defect for which every reasonable path is guesswork.
- Ordinary test failures, compiler errors, lint findings, and implementation defects are debugging work, not pause conditions.

### 5. Close the loop

- Run focused tests, the relevant broader suite, static checks, and build/package checks.
- Map every changed requirement and scenario to implementation and test evidence.
- Validate the direct-root SDD structure and requirement coverage without invoking the OpenSpec CLI.
- Re-run CodeGraph impact analysis against the implemented change and record predicted-versus-observed scope in `verification.md`.
- For browser-visible changes, run Playwright acceptance scenarios from the delta specs and record them under `## Playwright end-to-end verification` in `verification.md`.
- Run every activated profile's final review and repository-defined verification commands. Record results under `## Technology profile verification` in `verification.md`.
- Inspect the final diff for scope drift, secrets, generated debris, and incomplete tasks.
- Never claim completion from intuition or stale output. Cite the fresh commands and results.
- Present remaining risks and let the user choose merge, pull request, keep, or discard actions when those actions were not already authorized.
- Apply the `openspec-verify-change` review semantics before archival, then run `verification-before-completion` immediately before any completion claim. Record the evidence in `verification.md`. Sync and archive only after verification and when the user requested or authorized closure.

## Invariants

- Specifications describe externally observable behavior; designs describe implementation.
- Code, specs, tasks, and tests must agree before completion.
- A checked task is a claim backed by current evidence.
- No destructive Git operations, merges, pushes, or external publication without authorization.
- Do not require subagents or worktrees when the environment or user constraints prohibit them; preserve the gates inline.
- When scope changes, update OpenSpec artifacts before implementing the new scope.

## Handoff

Report: change name, completed artifacts, implemented tasks, verification evidence, requirement-to-test coverage, and residual risks. Keep the summary concise and link to local artifacts.
