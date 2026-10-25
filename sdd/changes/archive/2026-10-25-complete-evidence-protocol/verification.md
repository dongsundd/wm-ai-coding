# Final verification and TODO audit

Ready for archive. Blocking findings: zero.

Full suite: 80 tests passed. Final checks: 18 passed. Bundle version: 0.8.0.

## Item-by-item verification

| Task | Outcome | Acceptance run | Final run | Result |
|---|---|---|---|---|
| task-1 | Task 1: Route stage, support and profile skills through parent handoffs | f1c090b7e47e4e80b2ae681249b52c80 | 3c3c1faf50a54fbe8902fd92323edb5a | PASS |
| task-2 | Task 2: Require executable task acceptance before advancement | 847db815e79f4a1f8561a39f220103d0 | 821be6f827b44d0e8f63602c118d5f2d | PASS |
| task-3 | Task 3: Report archive integrity and failing CLI exit codes | 373bb21a94144218a15a1e72359a2b66 | 9e47fa3d2e1246f3a762fdc094286a08 | PASS |
| task-4 | Task 4: Bind evidence to release and declared environment identity | a63dae270a7b41c0aed425d0b9a4eee2 | b2cfb5f30a6d436085f08391fb3c31b3 | PASS |
| task-5 | Task 5: Guard host tool calls through capability-aware adapters | 8d589edd29964e5d81aeb0c505867e3a | 8e2c3b7e612d45cbba2dafb46b6b44de | PASS |
| task-6 | Task 6: Validate specification transforms and preserve portable evidence | 27bc788878fc4136a090088c77fe5c21 | 45724f1bae0a4cde942c488a8e264460 | PASS |
| task-7 | Task 7: Require structured review and conditional browser results | ac3ccedb8bc243ce95d9145b8ab8c3d5 | 7762ca0a98014a9aa0ce25418028270f | PASS |
| task-8 | Task 8: Exercise lifecycle and host adapters with behavior evaluations | 6b209b44abb844c2a539a1fc96491805 | 72232bb1450743fcb7921a9084a74c63 | PASS |
| task-9 | Task 9: Provide bounded briefs diagnostics and correlated traces | 92ea2b5351e849308408263da5335725 | 7babce2a943445e89408a13a770ed05d | PASS |
| task-10 | Task 10: Run independent checks in isolated workspaces before serial integration | d82001a5dd69471ca467540e42a49294 | 7dac582ac8d44f75a7a942d5b26ecf71 | PASS |

## Requirement and scenario coverage

- runtime::R1: 3c3c1faf50a54fbe8902fd92323edb5a
- runtime::R10: 7dac582ac8d44f75a7a942d5b26ecf71
- runtime::R10::contract-10: 7dac582ac8d44f75a7a942d5b26ecf71
- runtime::R1::contract-1: 3c3c1faf50a54fbe8902fd92323edb5a
- runtime::R2: 821be6f827b44d0e8f63602c118d5f2d
- runtime::R2::contract-2: 821be6f827b44d0e8f63602c118d5f2d
- runtime::R3: 9e47fa3d2e1246f3a762fdc094286a08
- runtime::R3::contract-3: 9e47fa3d2e1246f3a762fdc094286a08
- runtime::R4: b2cfb5f30a6d436085f08391fb3c31b3
- runtime::R4::contract-4: b2cfb5f30a6d436085f08391fb3c31b3
- runtime::R5: 8e2c3b7e612d45cbba2dafb46b6b44de
- runtime::R5::contract-5: 8e2c3b7e612d45cbba2dafb46b6b44de
- runtime::R6: 45724f1bae0a4cde942c488a8e264460
- runtime::R6::contract-6: 45724f1bae0a4cde942c488a8e264460
- runtime::R7: 7762ca0a98014a9aa0ce25418028270f
- runtime::R7::contract-7: 7762ca0a98014a9aa0ce25418028270f
- runtime::R8: 72232bb1450743fcb7921a9084a74c63
- runtime::R8::contract-8: 72232bb1450743fcb7921a9084a74c63
- runtime::R9: 7babce2a943445e89408a13a770ed05d
- runtime::R9::contract-9: 7babce2a943445e89408a13a770ed05d

## Review and residual scope

Self review was performed; no independent reviewer execution is claimed. Two extra regressions (archived migration history and explicit frontend applicability) were reproduced, corrected and included in the final suite.

The legacy harden-harness-runtime archive is absent. Its integrity finding is preserved; no replacement history was created. This does not change the selected change's acceptance.

Host hook activation/trust and live model routing measurements are outside this source verification. DSH exposes the normalized bridge, without automatic Cordis installation. Batch executes declared checks in disjoint workspaces; the host owns agents and serial integration.

CodeGraph before/after status was current with zero pending changes; runtime/CLI callers and both original suites were included in regression coverage. Browser UI acceptance is not applicable because this change affects CLI/plugin behavior. MCP initialization and tools/list succeeded for CodeGraph (8 tools) and Playwright (25 tools).

Portable evidence preserves acceptance/final runs, log hashes, task receipts, structured review, coverage and this report. Native Claude manifest strict validation passed; Codex portable structure was checked against official documented paths and local protocol checks (installed Codex exposes no native plugin validate command). No host installation, merge, push or publication is implied.
