# Prism Review：RASG-020 公开 runtime 契约边界

**日期**：2026-05-11  
**模式**：acceptance-review  
**Run ID**：`20260511-rasg020-runtime-contract-surface`  
**结论**：pass-after-fixes

## 结论摘要

Claude Code 和 Kimi 都完成了独立评审。Claude Code 无阻塞通过；Kimi 认可整体方向与发布安全姿态，但指出两个“权威性补强”缺口：公开命令 `prism-availability` 没在 import map 中独立表达，检查器也缺少“所有公开命令都必须进入 import map”的反向完整性校验。

这两个建议已在本轮修复，并通过 `redcap-runtime-contract-surface-check` 复验。因此本轮结论为 `pass-after-fixes`。

## 评审发现

| 来源 | 结论 | 处理 |
|------|------|------|
| Claude Code | `pass`，无阻塞项 | 接受；保留两个正式发布阶段风险提醒 |
| Kimi | `pass-with-fixes`，无阻塞项 | 已补 `prism-availability` import-map 入口，并补公开命令完整性检查 |

## 接受边界

- 可接受：RASG-020 已建立机器可检查的“普通用户 runtime 命令”和“维护者/源码治理命令”边界。
- 可接受：候选包面中的内部脚本仍可作为 alpha readiness 支持工具存在，但不会被声明为稳定公开 API。
- 不可冒充：这不是正式 npm 发布，不选择许可证，不打开 `private=false`，也不完成 RASG-021。

## 证据路径

- `prism/runs/20260511-rasg020-runtime-contract-surface/session-registry.yaml`
- `prism/runs/20260511-rasg020-runtime-contract-surface/collect/reviewer/parsed.json`
- `prism/runs/20260511-rasg020-runtime-contract-surface/collect/challenger/parsed.json`
- `prism/runs/20260511-rasg020-runtime-contract-surface/artifacts/fixes-applied.json`
- `prism/runs/20260511-rasg020-runtime-contract-surface/artifacts/acceptance-binding.json`
