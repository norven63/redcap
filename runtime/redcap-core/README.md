# RedCap Runtime Core

This directory is the minimum physical runtime layout used by RedCap's package-readiness path.

It is intentionally thin:

- Root `bin/redcap`, `revive-cap.sh`, and `closeout-cap.sh` remain compatibility entrypoints.
- Runtime wrappers here delegate back to those root entrypoints.
- `compass/tools` and `prism/tools` are not moved in this tranche.

This proves a package-visible runtime layer exists without pretending the full execution-layer split is complete.
