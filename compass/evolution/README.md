# RedCap Evolution Factory / RedCap 进化工厂

RedCap Evolution Factory 是 RedCap 的“进化工厂层”：它把运行痕迹、用户纠偏、失败链路和审查结论加工成可复用资产，同时防止自我修改本身变成新的漂移源。

它不是 RedCap 的全部，也不是本轮所有控制面重构的唯一主语。RedCap 的长期产品形态见 `references/redcap-system-layers.md`；Evolution Factory 只负责其中的经验、人格、skill、规则和 validator 候选沉淀。

## Purpose / 作用

- Collect evolution candidates from task cards, task reports, Prism verdicts, receipts, tests, user corrections, and closeout failures.
- Require every candidate to explain at least: problem source, solution, and final effect.
- Promote reviewed candidates into lessons, identity proposals, skills, rules, validators, backlog items, or explicit no-promote decisions.
- Keep active rules and identity files protected: discovery can be automatic, but promotion must be reviewed and evidence-backed.

## First-Read Rule / 首读规则

Do not bulk-read future candidate pools. Start from:

1. `references/evolution-grade-baseline.json`（历史兼容路径；语义上是 control-plane assurance registry）
2. `references/evolution-candidate-schema.json`
3. `compass/evolution/candidates.json`
4. `compass/tools/redcap-evolution-grade-check.sh`
5. `compass/tools/redcap-evolution-candidate-check.sh --strict`

## Lifecycle

```text
runtime trace
→ evolution candidate
→ schema check
→ Prism / independent review
→ promotion or no-promote-with-reason
→ closeout receipt may proceed only when candidates are handled
```

The first implementation is intentionally sidecar-first. It audits and gates RedCap-owned flows before any broader host-level automation is claimed.

## Closeout Gate

`redcap-layerb-closeout-runtime.sh complete` runs the candidate checker in strict mode before it can write a receipt. Any candidate still in `candidate` or `reviewing` blocks closeout until it is promoted, explicitly marked `no-promote` with a reason, or archived by policy.
