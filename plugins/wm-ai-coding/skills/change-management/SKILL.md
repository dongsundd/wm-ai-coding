---
name: change-management
description: Use only when `development-workflow` selects revision of existing OpenSpec planning artifacts for a change.
license: MIT
metadata:
  author: openspec
  version: "1.0"
---

## Controller contract

Run only from a `development-workflow` handoff naming the change, stage, task and exact scope.
A direct user request routes through `development-workflow`. Perform only the assigned operation,
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

## Update operation

Read the changed requirement and current proposal/spec/design/tasks. Update only the
assigned scope while preserving stable references and unaffected text. Inspect affected
implementation before revising architecture. Do not edit product code here.

Return changed artifacts, invalidated assumptions, affected tasks and approval needs.
The controller reconciles evidence and resumes from the earliest invalid gate. Never
retain approval for altered planning inputs or silently advance into apply.
