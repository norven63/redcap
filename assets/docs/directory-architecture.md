# RedCap Directory Architecture

This workspace is organized into two top-level units, not by old RedCap
history.

| Directory | Unit | Role |
| --- | --- | --- |
| `runtime/` | Running unit | Executable and operational RedCap capability |
| `assets/` | Asset unit | Persistent non-executable contracts, docs, knowledge, and archaeology |

Root keeps only discovery and host-entry files. The closed root set is
`README.md`, `AGENTS.md`, `.codex/`, `runtime/`, and `assets/`.
`runtime/bin/redcap layout-check` rejects any other root entry unless the
machine policy is deliberately updated.

## Runtime Unit

| Directory | Role |
| --- | --- |
| `runtime/bin/` | Short commands such as `runtime/bin/redcap` |
| `runtime/prism/` | Prism protocol, rules, provider briefs, review schemas, gate evaluator |
| `runtime/core/` | RedCap runtime kernels such as FSM, knowledge gateway, session ownership, layout guard |
| `runtime/bootstrap/` | First-start, revive, intake, and health entrypoints |
| `runtime/host-adapters/` | Thin host shims and live-marker probes |

## Functional Directories

| Function | Directory |
| --- | --- |
| Source execution logic | `runtime/bin/`, `runtime/core/`, `runtime/host-adapters/`, `runtime/prism/bin/`, `runtime/prism/lib/` |
| Runtime assets | `runtime/prism/prompts/`, `runtime/prism/rules/`, `runtime/prism/schemas/`, `runtime/prism/examples/`, `runtime/prism/docs/` |
| Archaeology archive assets | `assets/archaeology/` |

## Host Entry Unit

| Directory | Role |
| --- | --- |
| `.codex/` | Codex project-local hook deployment config. This is a host entry at root, not an asset dumping ground. |

## Asset Unit

| Directory | Role |
| --- | --- |
| `assets/contracts/` | Schemas, protocols, and machine-readable cross-layer policies |
| `assets/docs/` | Doctrine, revival map, architecture explanations |
| `assets/knowledge/` | Reviewed reusable knowledge and private wiki entries |
| `assets/evidence/` | Evidence boundary notice and ignore policy; live runtime evidence belongs in project `.redcap/evidence/` |
| `assets/fixtures/` | Portable deterministic fixtures for contract checks and installed-package self-checks; not live runtime evidence |
| `assets/archaeology/` | Source maps and exact-path extraction from old RedCap |

## Placement Rules

- Put anything executable or operational in `runtime/`.
- Keep Prism cohesive under `runtime/prism/`; do not split its prompts, rules,
  schemas, and helper command across units.
- Keep source execution logic only in the source execution directories above.
- Keep runtime-consumed prompts, rules, schemas, examples, and Prism protocol
  docs only in the runtime asset directories above.
- Put durable non-executable material in `assets/`.
- Put shared schemas and machine contracts in `assets/contracts/`.
- Put RedCap runtime kernels in `runtime/core/`.
- Put host-specific wiring in `runtime/host-adapters/`; keep RedCap rules
  elsewhere.
- Keep Codex host deployment config in `.codex/`; keep adapter implementation in
  `runtime/host-adapters/`.
- Put reusable knowledge in `assets/knowledge/`; keep raw old material in
  `assets/archaeology/` by exact reference only.
- Put live runtime proof in the active project `.redcap/evidence/` or a temporary external run directory; do not use source-tree evidence as task state.
- Put portable deterministic check fixtures in `assets/fixtures/`; do not place
  mutable task evidence there.
- Put first-read explanation in `assets/docs/`; do not let docs become
  authority over executable contracts.
- Do not put executable or source-like implementation files under `assets/`;
  assets are durable material, not running code.

## Executable Guard

The canonical policy is
`assets/contracts/directory-structure.json`. The guard is
`runtime/core/layout_guard.py` and is invoked by
`runtime/bin/redcap layout-check` and `runtime/bin/redcap check`.

It currently enforces:

- closed root entries;
- closed direct children for `.codex/`, `runtime/`, and `assets/`;
- required path presence;
- common sprawl name rejection such as `scratch/`, `tmp/`, `reports/`,
  `node_modules/`, and build output names;
- no executable bits or source-like executable extensions under `assets/`;
- path-specific file placement rules, so prompts, schemas, contracts, source
  files, evidence, docs, and archaeology extracts cannot drift into directories
  with a different function merely because the parent directory is allowed;
- cross-validation that every functional directory has a same-role placement
  rule, and that placement rules cannot claim a functional role outside the
  functional map;
- a hash lock for `assets/contracts/directory-structure.json`, so policy
  erosion cannot be hidden by editing the allowlist alone;
- negative self-check fixtures for root sprawl, runtime sprawl, host-entry
  sprawl, asset executables, missing required paths, forbidden-name casing,
  source/runtime-asset drift, contract/doc drift, archaeology/source drift,
  Prism-root file drift, placement-rule executable bits, functional-directory
  coverage, reverse functional-role coverage, duplicate placement paths, and
  policy erosion.

Legitimate policy expansion is intentionally a two-unit change:

1. Edit `assets/contracts/directory-structure.json`.
2. Compute the new hash with
   `shasum -a 256 assets/contracts/directory-structure.json`.
3. Update `EXPECTED_POLICY_SHA256` in `runtime/core/layout_guard.py`.
4. Run `runtime/bin/redcap layout-check self-check`.
5. Run `runtime/bin/redcap check`.

If only the policy file changes, `layout-check` must fail with a policy hash
mismatch. That failure is the guard doing its job, not a signal to weaken the
policy.

## First Work Sequence

1. `runtime/bin/redcap gate --task "<task>"`.
2. Follow the gate decision.
3. Place files according to this directory architecture.
4. Run `runtime/bin/redcap layout-check`.
5. Run `runtime/bin/redcap check`.

## Non-Goals

- No old RedCap directory mirroring.
- No raw task-report import by default.
- No root-level dumping ground.
- No public release authorization claim yet. The source layout supports a
  controlled 1.0 project-use baseline, while public release remains
  human-gated.
