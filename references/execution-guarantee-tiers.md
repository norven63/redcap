# Execution Guarantee Tiers

> **定位**：解释 RedCap 所说的“执行保障”到底分几档、每一档能承诺什么、不能承诺什么。
>
> **关联权威**：`references/execution-guarantees.json` 负责登记具体规则；本文负责解释这些规则的保障强度边界。

## 一句话先看懂

RedCap 不是把所有规则都混叫成“已保障”，而是把它们分成三档：

1. **物理强保障**：规则已经绑到脚本、Hook、validator、CI 或 fail-closed gate 上，命中时能被确定性执行或阻断。
2. **宿主耦合保障**：规则是否成立，取决于当前宿主是否真的提供了对应 Hook、session identity 或 runtime 接入点。
3. **人工/宿主边界保障**：规则已经被文档化、审计化、诊断化，但当前没有 repo-owned veto 点，不能诚实承诺 100% 物理强制。

## 为什么要分层

如果不分层，系统就会犯两种错：

1. 把脚本能 fail-close 的规则，和只能靠主 Agent 自觉遵守的规则混成一种“都已保障”。
2. 把“当前宿主没给控制面”误说成“RedCap 已经物理拦截住了”。

所以，**保障强度不是看规则重不重要，而是看它绑到了哪一层控制点**。

## 三档定义

### G1：物理强保障

满足以下任一特征时，可归到 G1：

- 有 repo-owned shell 脚本或 validator 在关键路径 fail-close
- 有宿主原生 Hook 或 CI / git gate 在触发点直接执行
- 有 runtime state / closure ledger / pending closure 这样的物理账本兜底
- 有 acceptance / replay 能证明该路径真实执行过

典型例子：

- `redcap-spec-check.sh`
- `redcap-validator-chain.sh`
- `redcap-task-report-check.sh`
- `redcap-docs-catalog.sh budget/check`
- `pending closure` / `closure-ledger`

G1 的正确承诺方式是：

- “这条规则已经进入物理控制链”
- “命中失败条件时会阻断或写回 pending”

### G2：宿主耦合保障

当规则是否成立依赖宿主能力时，应归到 G2。它通常有这些特征：

- RedCap 已经准备好了接入脚本
- 但是否真的生效，要看宿主有没有给出 session-start / stop / session-end / binding / hook 能力
- 不同宿主下，保障强度可能是 `supported` / `degraded` / `unsupported`

典型例子：

- 宿主 session-start / session-end 接入
- runtime binding / host session identity
- stop-review 是否能被宿主原生触发

G2 的正确承诺方式是：

- “这条规则在某些宿主下可物理执行，在另一些宿主下只能降级”
- “必须结合 `references/host-session-capability-matrix.json` 才能判断当前宿主的真实保障强度”

### G3：人工/宿主边界保障

当规则已经被 RedCap 明确认定为重要，但当前没有 repo-owned veto 点时，应归到 G3。它通常有这些特征：

- 有明确规则来源
- 有 task report / diagnose / checklist / execution-guarantees 登记
- 可以被事后审计、被错误地发现、被报告成 debt
- 但没有办法在事件发生瞬间物理拦截

典型例子：

- 主 Agent 不应无必要打断用户
- 主 Agent 不应把“只是保守”升级成人工决策门
- 身份内容、lessons 内容质量、外部 CLI 凭证这类不适合被脚本自动改写的事项

G3 的正确承诺方式是：

- “已被登记、可审计、可诊断”
- “当前仍属 host-limited / manual-only，不能冒充 100% 物理保障”

## 关键澄清：保障的是“动作控制点”，不是抽象任务

常见误解是：

> 既然有些规则能做到 100%，那为什么不把所有失败规则都投入同一个 100% 体系？

更准确的答案是：

- **能否做到强保障，不取决于规则愿望，而取决于有没有更强的控制点可以绑定。**
- 如果某条规则的决定瞬间发生在主宿主 Agent 的实时回复回路里，而当前宿主又不给 pre-reply / veto / pre-send Hook，那么 RedCap 就没有办法仅靠仓库内脚本把它升级成 G1。

所以真正正确的治理动作是：

1. 能迁到更强控制点的，必须迁。
2. 暂时迁不上去的，要诚实登记为 G2 或 G3。
3. 不允许把 G2 / G3 伪装成 G1。

## 与 `execution-guarantees.json` 的关系

`references/execution-guarantees.json` 是具体规则清单；本文是解释这些字段应怎样被理解：

- `status=scripted|hooked|validator`：通常偏向 G1，但仍要看是否真的命中物理控制链。
- `status=manual-only`：通常属于 G3。
- `auto_enforceable=false`：不能再对外宣称它已经是物理强保障。
- `host session capability matrix`：决定某些规则在当前宿主上是 G1 还是 G2。

## 当前 RedCap 的诚实口径

截至当前版本，RedCap 可以诚实这样说：

1. **大量 repo-owned gate / validator / closure 规则已经达到 G1。**
2. **宿主 Hook、session identity、runtime attach 这类规则多数属于 G2。**
3. **主 Agent 实时回复行为边界，在 Codex.app 这类未暴露 reply-veto 的宿主上仍属于 G3。**

这不是 RedCap 失败，而是**边界被明确、承诺被校准、治理从“模糊自信”升级成“分层诚实”**。
