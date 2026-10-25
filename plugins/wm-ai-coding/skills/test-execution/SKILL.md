---
name: test-execution
description: Execute task tests and final automated or browser acceptance with current
  evidence when development-workflow selects testing during apply or verify.
---

# Test Execution

Run only as a support under an active apply or verify primary. It is mandatory before code-review in verify. Consume test design, runnable Check definitions, current implementation and an authorized environment. Return control after testing; never advance or archive.

Run the exact check through `wm check <id>` so logs, input/source/environment identity and result are captured. Task acceptance runs must belong to the task's primary handoff: run task checks from that parent before opening this support, or return executable check instructions to the parent. Do not manufacture task receipts from a child run.

- Execute focused regression tests and the relevant full suite, static checks and builds declared by the project. Report each failed, skipped or unavailable check separately; a previous success cannot replace the latest failure.
- Map requirements/scenarios to actual run IDs, distinguishing planned and executed coverage. Source-mutating checks or stale environment/plan/source do not establish current success.
- In verify all declared checks must have successful current output before this support can finish. Write `verification.md#Test execution` with commands, results, environment and remaining gaps.

## Browser acceptance

Read the [browser evidence contract](references/browser-acceptance.md) for the result and evidence shape.

For browser-visible changes, use available Playwright MCP on the authorized local/staging target and reproduce specified scenarios. Declare `kind: browser`, exact target and necessary evidence artifacts in verification-plan.json. Execute the check, record its run ID and feed browser run IDs to the structured review.

Use structured snapshots as the primary observation. Capture resulting state after each interaction, console/network findings, and keyboard/error/loading behavior when relevant. Store necessary screenshots or traces under this change's evidence directory; convert repeatable journeys to repository-owned automation when supported.

Use an isolated session; reuse user authentication only if authorized. Do not publish, purchase, message, delete or change external state without authorization. Do not store credentials. Missing MCP/environment is a blocked browser check, not equivalent evidence from HTTP or an old screenshot. For non-browser work record non-applicability explicitly.

Unexpected behavior returns to the controller for debugging, specification correction or implementation changes. Do not suppress failures to finish the stage. Comprehensive acceptance remains change-verification's responsibility.
