---
name: openspec-propose
description: Use only when `using-wm` selects generation of approved OpenSpec planning artifacts for a change.
license: MIT
metadata:
  author: openspec
  version: "1.0"
---

## Controller contract

Run only from a `using-wm` handoff naming the change, stage, task and exact scope.
A direct user request routes through `using-wm`. Perform only the assigned operation,
then return its result to the controller; never invoke another stage skill.

Use `<repo>/sdd/config.yaml`, `<repo>/sdd/specs/` and
`<repo>/sdd/changes/<change>/` directly. Use filesystem operations and the `wm` CLI.
Do not run the official OpenSpec CLI or create an `openspec/` directory.
`tasks.md` is the sole implementation plan. Preserve existing authorization: do not
invent approval or demand a new request when execution is already authorized.
Host permissions and sandbox policy remain authoritative.

Before work read `wm --repo <repo> recovery --change <change>`. The controller records
`wm handoff --scope <repo-relative-paths>`; return with `wm finish-handoff <id>` and
`--result completed --output <existing-paths>`, or a failed/blocked/scope_changed result
with `--reason`. Output paths are repository-relative. The controller owns advancement. A matching completed stage/task handoff is required.
Support/profile calls use `wm handoff --skill <name> --parent <running-id>` and return to that parent; they never advance the stage.

When editing `design.md`, preserve an existing `## Frontend design` section
byte-for-byte. Only `frontend-design` writes that section.

## Specify operation

Create only `proposal.md`, delta `specs/**/spec.md` and the surrounding `design.md`.
Do not create tasks or edit implementation code during specify.

1. Read repository instructions, `sdd/config.yaml`, durable specs and the handoff.
2. Describe why, goals, non-goals, affected capabilities, compatibility and risks.
3. Give requirements stable authored headings (`### Requirement: <id or name>`),
   observable `#### Scenario: <name>` cases and explicit expected outcomes.
4. Inspect implementation structure using current CodeGraph when available; record
   symbols, callers, dependencies, impact and tests under `## Structural analysis`.
   If unavailable or stale, record the exact condition and targeted fallback evidence.
5. Record decisions, alternatives, interfaces, failures, migration and profile commands.
6. Return planning paths, risks and design readiness to the controller. It selects the
   conditional frontend substep, obtains any required design approval, and later routes
   task decomposition. Existing execution authorization remains valid.
