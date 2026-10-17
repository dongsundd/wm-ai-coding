---
name: rust-ai-coding
description: Use when a change touches Rust `.rs` files, Cargo manifests or lockfiles, crates, ownership or lifetime behavior, async Rust, error types, unsafe code, FFI, axum, sqlx, database transactions, testing, linting, or packaging.
---

# Rust AI Coding

Apply Rust constraints as a technology profile inside `run-ai-coding-harness`. This profile adds stack-specific design, implementation, review, and verification gates without replacing the harness workflow.

## Select the profile

Activate when repository evidence or the CodeGraph impact scope includes `.rs`, `Cargo.toml`, `Cargo.lock`, `rust-toolchain*`, or Cargo workspace configuration. Inspect before deciding rules:

- workspace members, crate types, MSRV/toolchain pin, targets, and feature matrix;
- library, binary, service, embedded, WASM, FFI, build-script, or proc-macro context;
- configured formatter, lints, test commands, deny policy, and CI checks;
- actual frameworks and dependencies such as tokio, axum, sqlx, anyhow, or thiserror.

Record the detected choices under `## Technology profiles` in the active `design.md`. Repository configuration, public API compatibility, and accepted architecture take precedence over profile defaults.

## Route references

Read only what the task needs:

- language and ownership background: [references/book.md](references/book.md)
- core language concepts: [references/core.md](references/core.md)
- public API and style guidance: [references/rust-style.md](references/rust-style.md)
- standard-library lookup: [references/std.md](references/std.md)
- Cargo, rustfmt, Clippy, tests, docs, and toolchain commands: [references/tools.md](references/tools.md)
- axum/sqlx and error-handling patterns, only when those crates are present: [references/patterns.md](references/patterns.md)

Do not introduce axum, sqlx, PostgreSQL, anyhow, thiserror, or a layered service architecture merely because a reference demonstrates it.

## Design and planning contract

For each Rust task in `tasks.md`, include:

- affected workspace member, crate, targets, features, and files;
- requirement or scenario reference;
- changed public interfaces, error semantics, ownership boundaries, and compatibility constraints;
- RED test and exact focused command;
- applicable format, lint, test, check, documentation, and target/feature commands.

Use CodeGraph to identify callers, trait implementations, feature-gated paths, module exports, related tests, and downstream API impact before editing.

## Implementation gates

- Load this profile before editing affected Rust source or Cargo configuration.
- Use `test-driven-development` for behavior changes.
- Preserve MSRV, target, feature, workspace, and dependency policies.
- Model recoverable failures with the project's established error types. Add context without erasing typed error semantics.
- Avoid panic paths in production-facing recoverable flows. `unwrap`, `expect`, `panic`, and unreachable assertions require a locally provable invariant or a test-only context.
- Keep unsafe blocks minimal, documented with their safety invariant, and covered by focused tests or analysis appropriate to the risk.
- Preserve ownership, cancellation, Send/Sync, locking, and cleanup behavior across async boundaries.
- Parameterize SQL values and align decoded nullability with the schema when sqlx is present.
- Use explicit transactions only for operations whose atomicity contract spans multiple statements; do not require transactions for every query.
- Follow the repository's module architecture, visibility, documentation language, and derive conventions.

## Conditional overlays

- **Library:** preserve semver-relevant public API, feature behavior, MSRV, docs, and downstream compile compatibility.
- **Async/service:** verify cancellation, timeouts, task ownership, backpressure, locks, shutdown, and error-to-response mapping.
- **Database/sqlx:** verify query binding, nullability, transaction atomicity, migrations, rollback, and compile-time/offline query metadata where configured.
- **Unsafe/FFI:** document invariants, ownership transfer, ABI, nullability, panic boundaries, and platform behavior.
- **CLI/binary:** verify exit codes, signals, stdout/stderr contract, configuration, and graceful shutdown.

Apply an overlay only when repository evidence confirms it.

## Review and verification

Review changed Rust code for API breakage, unjustified panics, lost error context, unsafe invariant gaps, deadlocks, blocking work in async paths, feature/target omissions, resource leaks, SQL/schema mismatch, and missing tests.

Run repository-defined commands first. When no commands are defined, derive the smallest applicable set from the workspace: `cargo fmt --check`, focused tests, relevant feature/target tests, `cargo clippy` using the repository's warning policy, `cargo test`, and `cargo check`. Do not assume `--all-features` or all targets are valid without project evidence. Record fresh commands, exit codes, and meaningful output in `verification.md`.

## Continuous execution

Completing a Rust task is not a user approval gate. Under continuous execution, record its evidence, select the next task's technology profile, and continue automatically. Pause only for a scope or observable-behavior change, a public API/MSRV/dependency decision outside the approved design, a safety-critical or destructive action, or an external side effect requiring authorization.
