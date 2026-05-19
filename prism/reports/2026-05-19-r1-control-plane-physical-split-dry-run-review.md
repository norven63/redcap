# Prism Review：R1 控制面物理拆分干跑清单

## 结论

本轮 Prism 先做下一切片选择评审。Claude Code 与 Kimi 均认为当前无需暂停找 Norven；分歧在于先推进哪条工程线：

- Claude Code：建议先做 `internal-control-plane`，因为它是最大、最核心的工程 blocker，下一步可以只做 dry-run manifest 与 alias/rollback plan。
- Kimi：建议先做 `prism-layer-and-evidence`，因为规模更小，且证据边界稳定后再拆 control-plane 风险更低。

Cap 裁决：先做 `internal-control-plane` 的 dry-run manifest。原因是本轮不移动文件、不删除证据、不发布、不改变开关，只把未来物理拆分需要的地图和护栏机器化；Kimi 关于 Prism evidence 的风险被写入漂移哨兵。

## 审查边界

- 不执行真实 registry 发布。
- 不打开公开发布开关。
- 不选择 license。
- 不读取 `.env` 或 secret。
- 不移动、删除、复制或重命名 `compass` / `references`。
- 不移动、删除或清理 Prism evidence。
- 不替 Norven 裁决 Layer A 产品范围。

## 评审证据

- Prompt: `prism/runs/20260519-r1-next-engineering-slice-selection/prompt.md`
- Claude raw: `prism/runs/20260519-r1-next-engineering-slice-selection/claude-reviewer.raw.txt`
- Kimi raw: `prism/runs/20260519-r1-next-engineering-slice-selection/kimi-challenger.raw.txt`

## 验收意见

当前没有发现必须人工介入的 blocker。本轮应当保持为 dry-run / planning / checker 级别，不能把完成态冒充为 physical split 或 release blocker resolved。

## 后续正式验收要求

- `redcap-r1-control-plane-contract-split-check.sh` 必须校验 dry-run manifest 覆盖全部实时 control-plane package candidates。
- acceptance 必须包含缺失 dry-run manifest 与 stale coverage 的反例。
- closeout receipt 之前必须通过 Prism acceptance。
