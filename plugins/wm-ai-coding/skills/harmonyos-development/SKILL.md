---
name: harmonyos-development
description: Use only when `development-workflow` selects the HarmonyOS profile for an affected OpenSpec stage or task.
---

## Harness entry contract

Execute only from a `development-workflow` handoff whose affected code scope activates HarmonyOS. A direct user request must enter `development-workflow`. Apply this profile only to the assigned stage or task, then return control to `development-workflow`.

# HarmonyOS Development

Apply HarmonyOS and ArkTS constraints as a technology profile inside `development-workflow`. This is an implementation overlay, not an independent workflow: OpenSpec, TDD, review, and delivery remain owned by the harness, and CodeGraph is used when available.

## Select the profile

Activate only when repository evidence or the affected code scope includes `.ets`, `hvigorfile.ts`, `build-profile.json5`, `oh-package.json5`, or HarmonyOS module configuration. Record the detected SDK/API version, modules, build entry point, and verification commands under `## Technology profiles` in the active `design.md`.

Repository instructions and checked-in configuration take precedence over this profile. Treat reference examples as defaults, never as proof of the installed SDK signature. Before using a platform API, inspect the project's SDK `.d.ts` declaration or the documentation matching its configured API level.

## Route references

Read only what the task needs:

- ArkTS syntax and strict-mode constraints: [references/arkts-basics.md](references/arkts-basics.md)
- ArkUI state and observation: [references/state-management-best-practices.md](references/state-management-best-practices.md)
- Dialog ownership and lifecycle: [references/dialog-patterns.md](references/dialog-patterns.md)
- Platform API patterns: [references/harmonyos-api.md](references/harmonyos-api.md)
- hvigor discovery and build diagnosis: [references/build-guide.md](references/build-guide.md)
- Source provenance and offline documentation: [references/official-docs-submodule.md](references/official-docs-submodule.md)

Do not assume a machine-specific SDK path. Discover it from the repository, environment, DevEco configuration, or executable search path.

## Design and planning contract

For each HarmonyOS task in `tasks.md`, include:

- affected module and `.ets`/configuration files;
- relevant requirement or scenario;
- SDK declarations or existing components that constrain the design;
- a RED test or strongest executable pre-implementation check;
- focused verification and the module/application build command.

When available, use CodeGraph first for project structure and impact scope. Use targeted SDK declaration lookup only for APIs CodeGraph cannot model.

## Implementation gates

- Load this profile before editing an affected `.ets` file.
- Follow the repository's decorator, routing, state-management, logging, localization, and module-boundary conventions.
- Preserve complete decorator chains and valid component lifecycle ownership.
- Update observed state in the form required by the project's state-management generation; do not generalize rules from another API level.
- Handle asynchronous failures visibly and release files, timers, listeners, dialogs, and other resources on every exit path.
- Keep permissions compatible with the declared application type and APL; do not add elevated permissions as a shortcut.
- Verify API names and signatures against the configured SDK before implementation.

Use `test-driven-development` for behavior changes. If the platform surface cannot be unit-tested before implementation, record why and use the strongest executable component, preview, integration, or build check available.

## Review and verification

Review the final HarmonyOS diff for:

- SDK/API-level compatibility;
- decorator and lifecycle correctness;
- state update and list identity behavior;
- routing and entry configuration;
- permission and resource declarations;
- resource cleanup and user-visible error handling;
- new warnings, deprecated APIs, and encoding damage.

Run repository-defined tests and lint first, then a fresh hvigor build for every affected module or application. Record commands, exit codes, and meaningful results in `verification.md`. Browser Playwright evidence does not replace device, emulator, preview, or hvigor evidence.

## Continuous execution

Completing a HarmonyOS task is not a user approval gate. Under continuous execution, update its evidence, select the next task's technology profile, and continue automatically. Pause only for a scope or observable-behavior change, an unresolved SDK incompatibility, a security-sensitive or destructive action, or an external side effect requiring authorization.
