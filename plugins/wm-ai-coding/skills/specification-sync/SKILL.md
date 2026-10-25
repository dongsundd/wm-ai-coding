---
name: specification-sync
description: Use only when `development-workflow` selects specification synchronization for a verified OpenSpec change.
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

## Sync operation

Run only during close after verification. Read each delta and corresponding durable
spec using its full capability path. Apply only named changes; leave unrelated text and
existing titles and Purpose sections unchanged.

- ADDED creates requirements; a missing capability may be created from ADDED content.
- MODIFIED changes existing requirements while preserving unaffected scenarios.
- REMOVED deletes named requirements; do not invent missing prior requirements.
- RENAMED moves a requirement name, preserving its body unless separately modified.

For new specs use `# <capability> Specification`, copy an authored `## Purpose` when
provided, and place `### Requirement:` / `#### Scenario:` blocks under
`## Requirements`. Remove delta operation headings from durable specs. Report ambiguous,
missing or conflicting merge targets as blocked. Delete an empty capability only when
retirement is explicitly authorized. Recompare every delta after writing; do not claim
semantic synchronization based solely on a hash.

After successful comparison call `wm baseline specs --change <change>`. Empty durable
spec trees can be baselined to support explicitly authorized last-capability retirement.
Return evidence to the controller. Do not archive from this skill.

Use `wm sync --change <name>` for the deterministic transform against the captured preimage. `baseline specs` rejects incorrect bodies, missing scenarios and unrelated edits; hashes alone do not establish synchronization.
