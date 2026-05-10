# Governance Review Checklist

> **定位**：适用于 `governance_tranche: true` 的 Layer B 任务。
> 目标不是做“文档 review”，而是确保治理类改动真的落到了 RedCap 的可执行保障链里。

## 1. Hook / Gate / Validator / Closure

- [ ] 本次新增或修改的 hook / gate / validator / closure 机制，都列出了物理落点（脚本、入口、调用链）
- [ ] 新规则不是只写在 spec / 文档里，而是已经明确落到脚本、校验器或 runtime state
- [ ] 若当前只能做到 degraded / unsupported，文档与收尾消息中有诚实标记，没有假装“已完全支持”

## 2. Authority / Truth Boundary

- [ ] 明确说明了 canonical truth 是谁，mirror surface 是谁
- [ ] 没有把宿主 workboard / session mirror / cli_console / spec 文档误当成 runtime authority
- [ ] 如果新增了 state / manifest / ledger，说明了它与 `.dev-task.md`、runtime state、task report 的关系
- [ ] 若当前任务绑定长期路线 backlog，已说明机器权威、`.dev-task.md` 与人类说明文档各自负责什么，且没有互相越权

## 3. Lifecycle / Artifact Boundary

- [ ] 明确区分 repo-tracked、session-isolated、local-only、temporary artifacts
- [ ] 本次新增文件已说明该进 git 还是只允许本地存在
- [ ] 若改动会影响 retention / archive / cleanup，已经同步更新相应规则或 debt
- [ ] 若新增了入口层 / 索引层 / core 层文件，已说明它与现有文件的 authority、生命周期和默认读取职责为何不同，而不是单纯把原内容切碎

## 4. Executable Norms

- [ ] 本次治理规则若可执行，已经有明确的 gate / validator / script 落点
- [ ] 本次治理规则若暂不可执行，已被明确标注为 design/debt，而非 runtime guarantee
- [ ] 新增能力已先做“固化保障优先级”评估：能否进入脚本 / validator / hook / acceptance / receipt / diagnose / spec-check；若没有进入，已写明 non-automation reason
- [ ] 本次新增或改写的保障规则，已明确自己属于哪一档：物理强保障 / 宿主耦合保障 / 人工-宿主边界保障，而不是把所有规则混叫成“已保障”
- [ ] 若引用了业内标准，已说明“标准要求 → RedCap 映射”的关系
- [ ] 面向人阅读的 repo-tracked 资产（如 backlog 说明、task report）已提供人话摘要 / 术语对照，并已接入对应检查
- [ ] 新增或修改的 spec 已遵守 `references/spec-contribution-standard.md`，其文件名 / role / status / summary 满足生命周期准入规则
- [ ] 若 spec 被标成 `superseded`，它已经迁入 `compass/docs/archive/specs/`，并在 registry 中声明 `replaced_by`
- [ ] 若新增宿主入口 shim、`CONTRIBUTING.core.md`、catalog/index 一类首读压缩层，已证明它们减少默认读取成本且没有制造第二权威或考古断层

## 5. Review / Audit / Closure

- [ ] 已说明本 tranche 需要哪些 review 轨道（architecture / governance / contracts）
- [ ] 三轨评审以 `references/review-tracks.json` 为机器权威；stop-review prompt 已消费该 registry，而不是只靠本 checklist 的自然语言提示
- [ ] 若输出会形成 RedCap 官方结论，已按 `references/conclusion-prism-policy.json` 进入 Prism-backed conclusion gate；未进入时明确标为建议稿 / 初判
- [ ] task report 中会体现“当前已完成 / 上一步完成的是 / 下一步计划做的是 / 整体计划脉络图与当前位置”
- [ ] 如有遗留治理债务，已补录到 `compass/knowledge/governance-debt-register.md`

## 6. 最终结论

- [ ] 可以诚实宣称“该治理能力已落地”
- [ ] 或者只能宣称“部分落地 / degraded / design-only”，并说明剩余缺口
