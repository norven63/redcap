# RedCap Runtime Core

This directory is the minimum physical runtime layout used by RedCap's package-readiness path.

It is intentionally thin:

- Root `bin/redcap`, `revive-cap.sh`, and `closeout-cap.sh` remain compatibility entrypoints.
- Runtime wrappers here delegate back to those root entrypoints.
- `compass/tools` and `prism/tools` are not moved in this tranche.

This proves a package-visible runtime layer exists without pretending the full execution-layer split is complete.

## Contract boundary

- Public runtime commands are the end-user entrypoints: `redcap revive`, `redcap status`, `redcap doctor`, `redcap diagnose`, `redcap debug`, `redcap closeout`, `redcap prism-availability`, `redcap help`, and `redcap version`.
- Maintainer release-readiness commands are packaged only for alpha/readiness support: `redcap package-manifest`, `redcap publish-safety`, `redcap package-surface`, and `redcap pre-release-review`.
- Source-maintainer commands such as `redcap file-dictionary`, `redcap shared-knowledge`, and `redcap change-intake` support RedCap's own governance; they are not normal end-user workflow.

The machine-readable boundary is `references/runtime-public-contract-policy.json`.
