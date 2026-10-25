---
name: frontend-design
description: Use only when `development-workflow` is in the design stage and a requirement or affected code scope changes a visible Web or app page, screen, component, layout, interaction, responsive behavior, accessibility behavior, or design system.
---

# Frontend Design

Turn an accepted product direction into an implementation-ready interface design before task decomposition. Cover Web and native app surfaces without becoming an implementation profile.

## Harness entry contract

Execute only from a `development-workflow` handoff for the active change's `specify` stage when `frontend_surface_changed` is true. A direct user request must enter `development-workflow`. Work only on the frontend design artifact, then return control to `development-workflow`.

Use a support handoff under the active requirements-specification primary, after technical-design returns and before test-design begins. The runtime requires that same parent and the ordered return evidence; this skill never advances a stage.

## Establish current-system evidence

- When available, use CodeGraph to locate routes, screens, shells, components, styling, tokens, state, assets, and related tests.
- For an existing Web surface, use `browser-research` when rendered observation or reference research is necessary. For native apps, use available device, emulator, preview, or supplied visual evidence.
- Treat user direction, supplied references, existing product behavior, and the repository design system as constraints.
- Preserve the established framework, component library, and styling strategy unless the approved architecture explicitly changes them.

## Write the design contract

Act as the only writer for `## Frontend design`. Add or update only that section in `sdd/changes/<change-name>/design.md`; preserve every other section and never replace the whole `design.md` file. Include:

- applicability and affected Web/app surfaces;
- primary user goal, journey, information hierarchy, and first-viewport priority;
- layout, navigation, components, copy, assets, and interaction behavior;
- loading, empty, error, disabled, focus, validation, permission, and reduced-motion states where applicable;
- responsive breakpoints or native device variants;
- typography, color roles, spacing, density, and reusable tokens from the existing system;
- keyboard, screen-reader, contrast, touch-target, and non-color accessibility requirements;
- accepted visual direction, alternatives rejected, unresolved risks, and observable acceptance criteria.

For an established product, extend its visual language. For a greenfield surface, define only the smallest coherent token and component set required by this change.

## Boundary

Do not modify product code, implement components, install dependencies, run implementation builds, or create a second plan. Finish this design before task decomposition. The later `tasks` stage translates the approved design and acceptance criteria into minimum independently acceptable implementation loops; technology profiles govern implementation.

If no visible frontend surface changes, record `Frontend design: not applicable` in `design.md` and return without inventing UI work.

## Return evidence

Return the changed design section, evidence consulted, acceptance criteria, open risks, and whether the design is ready for user approval. Return control to `development-workflow`; do not select or start the next stage.
