---
name: technical-design
description: Design architecture, interfaces and implementation impact after requirements
  specification when development-workflow selects technical design.
---

# Technical Design

Run as the first required support under the active specify primary. Consume proposal, delta specs, repository constraints and current implementation. Produce the surrounding `design.md`; preserve an existing `## Frontend design` section byte-for-byte.

1. Inspect concrete entry points, symbols, callers/callees, dependencies, affected tests and migration paths. Use current CodeGraph for the correct repository when available; record exact unavailable/stale/wrong-repository conditions plus targeted fallback evidence otherwise.
2. Write non-empty `## Structural analysis`: evidence, affected boundaries, expected direct/transitive impact and unaffected boundaries. Explain why greenfield or non-code scope is not applicable when appropriate.
3. Compare credible alternatives and record the selected architecture, interfaces, data flow, failure behavior, compatibility, migration and remaining risks.
4. Select Python, Rust and/or HarmonyOS profiles from actual affected files. Record project-defined tests, static/build commands and SDK/version evidence. Profiles constrain the design; they are not new workflows.
5. Record frontend applicability. Leave visible layout and interaction decisions to the controller's conditional frontend-design substep after this support returns.

Return design paths and residual risks with finish-handoff. Do not approve your own design on behalf of the user, decompose tasks or implement code. Test design follows the completed technical and applicable frontend design before task planning.
