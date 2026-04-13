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

## 3. Lifecycle / Artifact Boundary

- [ ] 明确区分 repo-tracked、session-isolated、local-only、temporary artifacts
- [ ] 本次新增文件已说明该进 git 还是只允许本地存在
- [ ] 若改动会影响 retention / archive / cleanup，已经同步更新相应规则或 debt

## 4. Executable Norms

- [ ] 本次治理规则若可执行，已经有明确的 gate / validator / script 落点
- [ ] 本次治理规则若暂不可执行，已被明确标注为 design/debt，而非 runtime guarantee
- [ ] 若引用了业内标准，已说明“标准要求 → RedCap 映射”的关系

## 5. Review / Audit / Closure

- [ ] 已说明本 tranche 需要哪些 review 轨道（architecture / governance / contracts）
- [ ] task report 中会体现“需你确认 / 人工验证 / 后续动作”
- [ ] 如有遗留治理债务，已补录到 `compass/knowledge/governance-debt-register.md`

## 6. 最终结论

- [ ] 可以诚实宣称“该治理能力已落地”
- [ ] 或者只能宣称“部分落地 / degraded / design-only”，并说明剩余缺口
