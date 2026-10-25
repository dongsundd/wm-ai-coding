---
name: test-design
description: Design traceable tests, data and environments before implementation when
  development-workflow selects test design after technical and applicable frontend
  design.
---

# Test Design

Run as the final required specify support under the active primary. technical-design must already have returned; for frontend changes frontend-design must also have returned. This is distinct from TDD and actual test execution.

Consumes proposal, delta requirements/scenarios and complete technical/frontend design. Produces `sdd/changes/<change>/test-design.md`, bound into the planning fingerprint and design approval.

For each requirement and scenario record:

| Field | Required information |
|---|---|
| Reference | Stable requirement/scenario identifier |
| Cases | Normal, boundary and failure behavior, with explicit expected results |
| Level | Unit, integration, end-to-end, static/build or manual with rationale |
| Setup | Environment, permissions, data, fixtures and external dependencies |
| Execution | Existing exact command when available; otherwise the test to implement and planned check ID |
| Coverage | What is covered, residual gaps and justified non-applicability |

Prioritize observable behavior, regression risks and contract boundaries. Avoid tests that merely copy implementation or match prose. Separate deterministic automated checks from human/agent semantic review; do not claim planned tests have run.

For visible browser changes, design the user journey, target/environment and necessary evidence artifacts. Backend-only work records browser acceptance as not applicable. Distinguish fact-gathering research from testing expected outcomes.

Return the matrix, feasibility, missing infrastructure and risks. development-planning subsequently assigns runnable checks to independent tasks in the existing verification-plan.json contract; tasks.md remains the sole implementation plan. Do not edit product code or run acceptance on nonexistent behavior.
