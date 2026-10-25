---
name: python-development
description: Use only when `development-workflow` selects the Python profile for an affected OpenSpec stage or task.
---

## Harness entry contract

Execute only from a `development-workflow` handoff whose affected code scope activates Python. A direct user request must enter `development-workflow`. Apply this profile only to the assigned stage or task, then return control to `development-workflow`.

# Python Development

Apply Python constraints as a technology profile inside `development-workflow`. This profile supplements OpenSpec, TDD, review, and delivery, and uses CodeGraph when it is available; it does not create a separate workflow.

## Select the profile

Activate when repository evidence or the affected code scope includes Python source, `pyproject.toml`, `setup.cfg`, `setup.py`, requirements files, or Python lock files. Inspect the repository before choosing rules:

- supported Python versions and package manager;
- application type: library, CLI, service, job, data pipeline, or test tooling;
- formatter, linter, type checker, test runner, framework, ORM, and validation library;
- commands already defined by project scripts, CI, tox, nox, Make, or task runners.

Record the detected choices under `## Technology profiles` in the active `design.md`. Repository configuration and instructions override profile defaults.

## Route references

Read only the references relevant to the detected project:

- repository-compatible Python style: [references/pyguide.md](references/pyguide.md)
- typing and generic patterns: [references/typing-patterns.md](references/typing-patterns.md)
- exception and boundary handling: [references/error-handling-patterns.md](references/error-handling-patterns.md)
- Pydantic patterns, only when the repository uses Pydantic: [references/pydantic-patterns.md](references/pydantic-patterns.md)
- Google-style Pylint defaults, only when compatible with repository linting: [references/pylintrc](references/pylintrc)

Do not introduce Pydantic, Marshmallow, Requests, an ORM, or a particular style tool merely because a reference demonstrates it.

## Design and planning contract

For each Python task in `tasks.md`, include:

- affected package and files;
- requirement or scenario reference;
- public interfaces and compatibility constraints;
- RED test and exact focused test command;
- configured format, lint, type, test, and packaging checks that apply.

When available, use CodeGraph to identify imports, callers, public surfaces, framework registration, and related tests before planning edits.

## Implementation gates

- Load this profile before editing affected Python source or package configuration.
- Use `test-driven-development` for behavior changes.
- Preserve the repository's supported Python floor and dependency strategy.
- Keep public interfaces typed to the level enforced by the existing project; avoid unjustified `Any` at new boundaries.
- Catch exceptions where recovery, translation, cleanup, or context is meaningful; never silently swallow unexpected failures.
- Bound network and subprocess operations with project-appropriate timeouts and propagate actionable failure context.
- Manage sessions, files, locks, tasks, clients, and streams with context managers or explicit cleanup.
- Validate untrusted input at its boundary using the repository's chosen mechanism. Pydantic or Marshmallow is conditional, not universal.
- Keep secrets and environment-specific addresses out of source control.
- Follow the project's formatter, import ordering, docstring language, and architecture instead of imposing a new convention.

Re-fetching after a remote create or update is required only when the API contract says the mutation response is incomplete or eventual consistency makes it necessary.

## Conditional overlays

- **Web/API:** verify request parsing, authentication, authorization, validation, status mapping, and error responses.
- **Database/ORM:** verify transaction boundaries, rollback, session cleanup, migrations, and query behavior.
- **Async:** verify cancellation, timeout, task ownership, resource cleanup, and sync/async boundary behavior.
- **Library:** preserve exported API, supported versions, packaging metadata, and downstream compatibility.
- **CLI/job:** verify exit codes, stdout/stderr contract, signals, retries, idempotency, and partial-failure behavior.

Apply an overlay only when repository evidence confirms it.

## Review and verification

Review changed Python code for type regressions, exception swallowing, unsafe input boundaries, resource leaks, blocking work in async paths, environment coupling, dependency drift, and missing tests.

Run repository-defined commands first. When the repository has no explicit commands, choose the smallest applicable set from its installed tooling: focused tests, full tests, formatting check, lint, type check, and build/package check. Never install a new checker solely to satisfy this profile. Record fresh commands, exit codes, and meaningful output in `verification.md`.

## Continuous execution

Completing a Python task is not a user approval gate. Under continuous execution, write its evidence, select the next task's technology profile, and continue automatically. Pause only for a scope or observable-behavior change, a new dependency or compatibility decision not covered by the approved design, a security-sensitive or destructive action, or an external side effect requiring authorization.
