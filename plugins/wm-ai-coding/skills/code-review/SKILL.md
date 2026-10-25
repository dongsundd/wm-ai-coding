---
name: code-review
description: Review changed code against requirements, design and current test evidence
  when development-workflow selects review before final change verification.
---

# Code Review

Run only as the required verify support after test-execution has returned. Consume current diff, requirements, design, test design and execution evidence. Review the integrated source, not just individual task receipts.

- Check correctness, interfaces, failures, compatibility, migrations, maintainability and plausible regression risks. Compare predicted dependencies with actual impact using current CodeGraph when available.
- Ground findings in concrete code paths and explain the user-visible consequence. Do not inflate stylistic preferences into blockers.
- Review normal, boundary and failure behavior against authored scenarios. Flag gaps even if tests pass, and distinguish confirmed bugs from uncertain risks.
- Record reviewer identity and honest `self` or host-asserted `independent` mode. Do not automatically spawn reviewers or imply authenticated independence.

Produce review input JSON with reviewer, mode, findings (severity blocking/warning/info, message, resolved boolean), and applicable browser_runs. Call `wm review --file <input> --change <name>` to bind review.json to current planning and source.

Unresolved blocking findings stop final acceptance. Do not mark them resolved without evidence. If fixes change source, return to the primary for current test execution and another review; old results are stale. Finish with review.json and the findings summary, then return control. Do not approve design, advance, commit or publish.
