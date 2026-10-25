---
name: requirements-analysis
description: Clarify goals, scope, constraints and acceptance intent when development-workflow
  selects requirements analysis for a software change.
---

# Requirements Analysis

Run only from the controller's clarify handoff, then return control. Direct development requests enter development-workflow. Use existing conversation and repository evidence before asking for missing information.

Consumes user intent, any research findings and existing specifications. Produces `design.md#Requirements` in the assigned `sdd/changes/<change>/` with goals, users, scenarios, scope, non-goals, constraints, assumptions and unresolved decisions.

- Establish the problem and observable desired outcome. Separate user requirements from suggested implementation details.
- Identify consequential ambiguity, conflicting constraints and success criteria. Ask only questions that change scope or behavior; preserve already accepted decisions.
- When facts are missing, return a bounded research need to the controller. requirements-research owns broad fact collection; browser-research supplies browser observations only.
- Keep technical alternatives and architecture decisions for technical-design. Record implementation constraints already required by the user without deciding the full solution here.
- For small clear requests, use the existing description and record it without manufacturing a questionnaire or another approval ceremony.

Exit when the builder can state what outcome is wanted, why, for whom and within which boundaries, and distinguish remaining unknown facts from decisions. Return clarified requirements, risks and the exact artifact path. Do not write product code or a second task plan.
