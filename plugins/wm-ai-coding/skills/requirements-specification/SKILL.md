---
name: requirements-specification
description: Write a change proposal and observable requirements with scenarios when
  development-workflow selects the specify stage.
license: MIT
metadata:
  author: openspec
  version: '1.0'
---

# Requirements Specification

This is the specify primary. Run only from development-workflow's scoped handoff. Use `sdd/changes/<change>/`, durable `sdd/specs/` and the WM CLI, not the official OpenSpec CLI or another process root.

Consumes clarified goals, constraints and research. Produces `proposal.md`, delta `specs/**/spec.md` and the initial surrounding `design.md` structure. Preserve existing `## Frontend design` byte-for-byte; only frontend-design may replace it.

- Explain why, goals, non-goals, affected capabilities, compatibility and risks in the proposal.
- Use stable `### Requirement: <id or name>` headings and observable `#### Scenario: <name>` cases. Define conditions, expected outcomes and failure behavior without prescribing unnecessary implementation choices.
- Use ADDED/MODIFIED/REMOVED/RENAMED delta semantics consistent with the durable baseline. Identify conflicts and missing preimages rather than silently overwriting.
- Establish traceability from user intent to requirement and scenario. Keep architecture decisions with technical-design, and verification strategy with test-design.

Return the primary to its controller while it remains running for the ordered supports: technical-design, conditional frontend-design, test-design. After they return, reconcile the combined artifacts, preserve existing authorization and obtain any design approval already required by scope. The runtime checks current support evidence before the primary may finish.

Do not create tasks.md or edit product code during specify. Complete with proposal/spec/design/test-design paths, coverage of the clarified intent and unresolved decisions. Then return control so the controller can advance.
