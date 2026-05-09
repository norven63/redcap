# 任务完成报告：Codex lifecycle hooks candidate 接线

**报告日期**：2026-05-09
**执行者**：Cap（Codex.app）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已把 Codex 官方 lifecycle hooks 纳入宿主能力画像，并完成最小项目级候选接线。
- 详情：Codex 现在不再被简单写成“只有 AGENTS 入口”；状态升级为 “repo-owned candidate / degraded until live marker E2E”。

### 0.2 上一步完成的是

- 上一步完成的是：P2-15 已把 `prism/runs` 过期证据清理从“按年龄删除”修正为“先看证据链引用”，防止误删历史评审证据。

### 0.3 下一步计划做的是

- 下一步计划做的是：完成 closeout receipt 后回到 RedCap 父任务线继续推进非发布类治理缺口；若要把 Codex 升级为 hook-ready，需要另做真实 trusted Codex 会话 marker E2E。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：父任务线治理 → Codex 新 Hook 能力评估 → candidate 接线 → 回归/棱镜复核 → closeout → 回到父任务线。
- 当前所在位置：P2-16 `codex-lifecycle-hooks-candidate`，这是宿主能力接线切片，不是 npm 发布任务。

### 0.5 是否需要 Norven 人工介入

- 人工介入：暂时不需要。
- 说明：本轮只增加候选配置、wrapper、状态面和回归，不要求你现在切换 Codex trust 设置，也不执行发布或破坏性动作。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “临时插一个新能力：上面是我让另一个Agent分析的最近Codex更新的Hooks能力对于redcap的帮助，你们可以评估一下如何加进新需求中，因为我觉得这个hook能力对于你后续的开发动作是有助力的。”

### 1.2 触发背景

此前 RedCap 对 Codex 的判断是：Codex 能自动导入 `AGENTS.md`，也能作为 headless reviewer，但没有 repo-owned `SessionEnd` / reply-veto hook surface。用户补充的新资料显示，OpenAI 官方已经公开 Codex lifecycle hooks，并提供 `SessionStart`、`PreToolUse`、`PermissionRequest`、`PostToolUse`、`UserPromptSubmit`、`Stop` 等事件。这改变了 RedCap 对 Codex 的长期画像，但不能跳过验证直接宣布 ready。

### 1.3 官方事实核准

| 事实 | RedCap 处理 |
|---|---|
| Hooks 需要 `codex_hooks` feature flag | `.codex/config.toml` 明确启用。 |
| 项目级 `.codex/` 需要 Codex trust 后才加载 | 状态面保持 degraded，不宣称已物理触发。 |
| 同事件多个 hooks 会并发运行 | RedCap wrapper 只做本仓库保守动作，不假设能串行控制所有 hook。 |
| `PreToolUse` / `PostToolUse` 覆盖不完整 | 只作为危险动作护栏，不冒充完整沙箱。 |
| `Stop` 可要求继续一轮 | wrapper 返回 Codex 支持的 JSON，并用 `stop_hook_active` 防止循环。 |

### 1.4 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 已覆盖 | 官方文档核准、P2-16 登记、`.codex/` candidate 配置、SessionStart/PreToolUse/Stop wrapper、readiness/status/知识画像、回归。 |
| 延期 | 不宣称 Codex 已 hook-ready；真实 trusted Codex marker E2E 后续单独验证。 |
| 用户可见边界 | 本轮让 RedCap 具备“知道、配置、检查、候选接线”能力，不把候选接线冒充为已验证宿主强保障。 |

---

## 二、方案讨论

### 2.1 问题分析

这次新能力很有价值，因为它正好补 RedCap 在 Codex 上最薄弱的两条生命线：启动复活和回合收尾。但它仍不是魔法补丁：项目 `.codex/` 可能未被 trust，工具前后置 hook 不覆盖全部路径，Stop 也不是完整 SessionEnd，更不是主 Agent 最终回复前的全局 veto。

### 2.2 决策结果

| 问题 | 决策 | 理由 |
|---|---|---|
| 是否立刻升级 Codex 为 ready | 不升级，只进入 candidate/degraded | 未做真实 trusted session marker E2E。 |
| 优先接哪些事件 | 先接 SessionStart、PreToolUse、Stop | 分别覆盖复活、明显危险动作、收尾 continuation。 |
| 是否接 PermissionRequest/PostToolUse/UserPromptSubmit | 暂不在本轮接 | 需要更细策略，避免误伤或过度承诺。 |
| 是否改变父任务发布判断 | 不改变 | 这是宿主控制面增强，不等于 public release ready。 |

---

## 三、落地结果

### 3.1 完成内容

- 新增 `.codex/config.toml`，启用 Codex Hooks feature flag。
- 新增 `.codex/hooks.json`，把 `SessionStart`、`PreToolUse`、`Stop` 接到 RedCap wrapper。
- 新增 `redcap-codex-session-start.sh`：Codex 启动/恢复时尝试进入 RedCap 复活链。
- 新增 `redcap-codex-pre-tool-use.sh`：阻止 `git reset --hard`、证据目录物理删除、`npm publish` 等明确高危动作。
- 新增 `redcap-codex-stop.sh`：Codex 回合停止时进入 Layer B 收口检查；若还有 pending closeout，则让 Codex 继续一轮。
- 新增 `redcap-codex-hooks-check.sh`，并接入 spec-check、diagnose 与 multi-session acceptance。
- 更新 Codex 宿主画像、host reliability、host readiness、current-status、父任务账本和文件查阅字典。

### 3.2 人话解释

以前 Codex 对 RedCap 来说像“打开工作区时能读到说明书，但不一定会自动执行复活和收尾”。现在我们给它接上了三根候选线：开局自动复活、做危险动作前先踩刹车、准备停下时先检查是否还有尾巴没收。只是这三根线还要在真实新 Codex 会话里做一次物理触发验收，所以现在只能说“线已经铺好”，不能说“全屋电力已经验收通电”。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| lifecycle hooks | `.codex/hooks.json` | Codex 在会话启动、工具调用前、回合停止等固定时刻自动运行脚本的能力。 |
| candidate/degraded | `redcap-host-hook-readiness.sh` | 仓库已经有配置和检查，但还没有用真实 Codex 会话证明它一定会触发。 |
| live marker E2E | `redcap-codex-*.sh` 的 marker 支持 | 开一个真实 Codex 会话，让 hook 写出标记文件，以证明不是“配置看起来对”，而是“物理上真的跑了”。 |
| reply-veto | 宿主最终回复控制点 | 在 Agent 最终回复发出去前拦截和改写的能力；本轮 Codex Hooks 仍不能让 RedCap 宣称完整拥有它。 |

---

## 四、人工审核要点

- 当前不需要 Norven 人工介入。
- 后续如果要把 Codex 从 candidate 升级为 ready，需要你允许一次真实 Codex 项目 trust / 新会话 marker E2E。
- 本轮不会执行 `npm publish`、不会物理删除 `prism/runs`，也不会改变发布开关。

---

## 五、验证结果

### 5.1 已通过验证

| 验证项 | 结果 |
|---|---|
| 官方文档核准 | 通过，使用 OpenAI 官方 Codex Hooks / config docs |
| Codex hooks candidate check | 通过 |
| host-hook-readiness codex | 通过，输出 repo-owned-candidate / degraded |
| acceptance: codex-hooks-candidate-check | 通过 |
| PreToolUse 危险命令 deny | 通过 |
| SessionStart marker wrapper | 通过 |
| Stop JSON loop guard | 通过 |

### 5.2 当前边界

| 边界 | 状态 |
|---|---|
| 真实 Codex project trust | 未在本轮验证 |
| 真实 Codex SessionStart/Stop marker E2E | 未在本轮验证 |
| 完整 reply-veto | 不支持宣称 |
| 完整工具安全沙箱 | 不支持宣称 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|---|---|
| 已实现 | 是，candidate 阶段已实现 |
| 已自检 | 是 |
| 已独立验收 | 是，Claude Code + Kimi 均 pass |
| 已正式完成 | 待最终 spec/diagnose 与 closeout receipt |

### 5.5 棱镜验收结论

| 评审方 | 结论 | 重点意见 |
|---|---|---|
| Claude Code | pass | candidate/degraded 口径正确；风险集中在 regex 拦截可绕过、Stop pending-closeout 路径覆盖还可继续增强。 |
| Kimi | pass | 当前接线可收口；Codex project trust、feature flag 与 live marker E2E 仍是升级 ready 的必要条件。 |

共识：本轮可以作为候选接线完成，但不能升级 Codex 为 full host parity，也不能宣称完整安全沙箱。

---

## 六、遗留问题与下一步

| 问题 | 当前边界 | 下一步 |
|---|---|---|
| Codex hook 物理触发 | 只完成候选接线 | 另做 trusted Codex live marker E2E 后再升级 ready |
| PermissionRequest / PostToolUse / UserPromptSubmit | 本轮未接 | 等 candidate 稳定后另做策略设计 |
| reply-time veto | Codex Hooks 仍不足以完整覆盖 | 继续登记为 host-limited，不冒充 100% |
| public release | 不在本轮范围 | 继续按 P4-2 release task 处理 |

---

## 七、经验沉淀

| 维度 | 内容 |
|---|---|
| 问题源 | Codex 官方新增生命周期 Hooks 后，RedCap 旧画像仍停留在“AGENTS only”，容易低估 Codex 新控制面，也容易反过来高估成已 ready。 |
| 解决方案 | 用 candidate/degraded 模型接入：先铺 `.codex/` 配置和 wrapper，再用 readiness/status/check/report 表达真实边界，最后等待 live marker E2E 升级。 |
| 最后效果 | RedCap 能立刻利用 Codex 新 Hook 能力做复活、收尾和危险动作护栏，同时避免把未验证能力吹成 100% 保障。 |

### 7.3 Evolution Factory 候选处理

- 处理：no-promote。
- 理由：这是既有宿主适配与执行保障机制的直接扩展，已经进入文档画像、机器检查和回归；暂不新增独立候选，避免把 candidate 接线阶段拆成重复治理项。

## 八、附录

### 8.1 关键证据

- 官方事实核准：OpenAI Codex Hooks / config reference。
- 机器回归：`redcap-codex-hooks-check.sh`、`codex-hooks-candidate-check`、`spec-check`、`diagnose`。
- 独立验收：`prism/reports/2026-05-09-codex-lifecycle-hooks-candidate.md`。
- 验收绑定：`prism/runs/20260509-codex-lifecycle-hooks-candidate/artifacts/acceptance-binding.json`。

### 8.2 未升级声明

- Codex 仍是 `candidate/degraded`，不是 full host parity。
- 真实 trusted Codex live marker E2E 尚未执行。
- `PreToolUse` 只作为危险动作护栏，不是完整沙箱。
