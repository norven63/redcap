# 任务完成报告：Codex lifecycle hooks candidate 接线

**报告日期**：2026-05-09
**执行者**：Cap（Codex.app）
**报告版本**：v1.1
**归档状态**：2026-05-11 从活跃 task-reports inbox 迁入私有知识归档，保留考古价值但不再占用默认 docs 活跃窗口。

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已把 Codex 官方 lifecycle hooks 纳入宿主能力画像，完成最小项目级候选接线，并补做本机 Codex CLI live marker E2E。
- 详情：Codex 现在不再被简单写成“只有 AGENTS 入口”；状态升级为“本机 Codex CLI marker 已通过，但 Codex.app interactive 仍未单独证明”。

### 0.2 上一步完成的是

- 上一步完成的是：P2-15 已把 `prism/runs` 过期证据清理从“按年龄删除”修正为“先看证据链引用”，防止误删历史评审证据。

### 0.3 下一步计划做的是

- 下一步计划做的是：完成 closeout receipt 后回到 RedCap 父任务线继续推进非发布类治理缺口；若要把 Codex.app interactive 升级为 hook-ready，需要另做 Codex.app 交互面的物理 marker E2E。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：父任务线治理 → Codex 新 Hook 能力评估 → candidate 接线 → hook 唯一信源加固 → Codex CLI live marker E2E → 回归/棱镜复核 → closeout → 回到父任务线。
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
| 延期 | 不宣称 Codex.app interactive 已 hook-ready；完整 reply-veto 后续仍是 host-limited。 |
| 用户可见边界 | 本轮让 RedCap 具备“知道、配置、检查、候选接线，并验证本机 Codex CLI 物理触发”的能力，不把 CLI marker 冒充为 Codex.app 或完整宿主强保障。 |

---

## 二、方案讨论

### 2.1 问题分析

这次新能力很有价值，因为它正好补 RedCap 在 Codex 上最薄弱的两条生命线：启动复活和回合收尾。但它仍不是魔法补丁：项目 `.codex/` 可能未被 trust，工具前后置 hook 不覆盖全部路径，Stop 也不是完整 SessionEnd，更不是主 Agent 最终回复前的全局 veto。

### 2.2 决策结果

| 问题 | 决策 | 理由 |
|---|---|---|
| 是否立刻升级 Codex 为 ready | 只升级本机 Codex CLI marker 状态，不升级 Codex.app interactive / full parity | CLI marker 只证明 `codex exec` 触发，不证明 Codex.app 交互会话或 reply-veto。 |
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
- 新增 `redcap-codex-live-marker-e2e.sh`：用安全探针让本机 `codex exec` 触发 SessionStart/Stop，并把清洗证据写入 `references/codex-live-marker-e2e.json`。
- 将“宿主 Hook 配置只做适配，RedCap-native 脚本是唯一信源”写入 `hook-standards` 与 `execution-guarantees`，防止各宿主分叉实现业务逻辑。
- 新增 `redcap-codex-hooks-check.sh`，并接入 spec-check、diagnose 与 multi-session acceptance。
- 更新 Codex 宿主画像、host reliability、host readiness、current-status、父任务账本和文件查阅字典。

### 3.2 人话解释

以前 Codex 对 RedCap 来说像“打开工作区时能读到说明书，但不一定会自动执行复活和收尾”。现在我们给它接上了三根候选线：开局自动复活、做危险动作前先踩刹车、准备停下时先检查是否还有尾巴没收。本轮进一步做了本机 Codex CLI 实测：`codex exec` 确实会触发 SessionStart 和 Stop 两个 hook。但这个结论只能覆盖本机 CLI，不代表 Codex.app 交互会话已经完整通电，也不代表 RedCap 拿到了最终回复前的全局拦截权。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| lifecycle hooks | `.codex/hooks.json` | Codex 在会话启动、工具调用前、回合停止等固定时刻自动运行脚本的能力。 |
| candidate/degraded | `redcap-host-hook-readiness.sh` | 仓库已经有配置和检查，但还没有用真实 Codex 会话证明它一定会触发。 |
| live marker E2E | `redcap-codex-live-marker-e2e.sh` + `references/codex-live-marker-e2e.json` | 开一个最小 Codex CLI 会话，让 hook 写出标记文件，以证明不是“配置看起来对”，而是“物理上真的跑了”。 |
| reply-veto | 宿主最终回复控制点 | 在 Agent 最终回复发出去前拦截和改写的能力；本轮 Codex Hooks 仍不能让 RedCap 宣称完整拥有它。 |

---

## 四、人工审核要点

- 当前不需要 Norven 人工介入。
- 后续如果要把 Codex.app interactive 从未验证升级为 ready，需要你允许一次 Codex.app 交互面 marker E2E；本轮不需要人工介入。
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
| Codex CLI live marker E2E | 通过，证据见 `references/codex-live-marker-e2e.json` |
| hook single-source contract | 通过 |
| full spec-check | 通过，`bash compass/tools/redcap-spec-check.sh "$PWD"` |
| full multi-session acceptance | 通过，`bash compass/tools/redcap-multi-session-acceptance.sh all` |

### 5.2 当前边界

| 边界 | 状态 |
|---|---|
| 本机 Codex CLI project trust / feature flag | 已通过 marker E2E 间接验证 |
| Codex.app interactive SessionStart/Stop marker E2E | 未在本轮验证 |
| 完整 reply-veto | 不支持宣称 |
| 完整工具安全沙箱 | 不支持宣称 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|---|---|
| 已实现 | 是，candidate 阶段已实现 |
| 已自检 | 是 |
| 已独立验收 | 是，Claude Code + Kimi 均 pass |
| 已正式完成 | 待 closeout receipt |

### 5.5 棱镜验收结论

| 评审方 | 结论 | 重点意见 |
|---|---|---|
| Claude Code | pass | candidate/degraded 口径正确；本机 CLI marker 通过后仍要避免把 package surface 膨胀或宿主配置分叉误当 ready。 |
| Kimi | pass | 当前接线可收口；生产 hook 不得注入 E2E probe env，Stop 循环保护要单独有 acceptance。 |

共识：本轮可以作为候选接线完成，并且本机 Codex CLI marker 可升级为 partial-ready；但不能升级 Codex.app interactive 为 ready，不能宣称 full host parity，也不能宣称完整安全沙箱。

后续处理：评审提醒已转为机器检查。`redcap-codex-hooks-check.sh` 会拒绝生产 `.codex/hooks.json` 携带 `REDCAP_CODEX_HOOK_E2E_PROBE`，`codex-hooks-candidate-check` 会单独验证 `stop_hook_active=true` 时不会造成 Stop 递归阻塞。

最新绑定：由于 live marker 与 follow-up 机器检查改变了当前 diff，已新建 `20260509-codex-live-marker-e2e-hardening` 作为当前 closeout 使用的 Prism acceptance run；旧 `20260509-codex-lifecycle-hooks-candidate` 只作为 candidate 初始接线审查记录保留。

---

## 六、遗留问题与下一步

| 问题 | 当前边界 | 下一步 |
|---|---|---|
| Codex CLI hook 物理触发 | 已通过本机 marker E2E | 继续保留清洗证据和回归 |
| Codex.app interactive hook 物理触发 | 未验证 | 另做 Codex.app 交互面 marker E2E 后再升级 ready |
| PermissionRequest / PostToolUse / UserPromptSubmit | 本轮未接 | 等 candidate 稳定后另做策略设计 |
| reply-time veto | Codex Hooks 仍不足以完整覆盖 | 继续登记为 host-limited，不冒充 100% |
| public release | 不在本轮范围 | 继续按 P4-2 release task 处理 |

---

## 七、经验沉淀

| 维度 | 内容 |
|---|---|
| 问题源 | Codex 官方新增生命周期 Hooks 后，RedCap 旧画像仍停留在“AGENTS only”；仅写 `.codex/hooks.json` 又容易把“配置存在”误说成“物理触发”。 |
| 解决方案 | 用分层口径接入：先铺 `.codex/` 配置和 wrapper，再用安全 live marker E2E 验证本机 Codex CLI 触发，同时把 Codex.app interactive 和 reply-veto 留在未验证边界。 |
| 最后效果 | RedCap 能利用 Codex 新 Hook 能力做复活、收尾和危险动作护栏；本机 CLI 触发已有证据，但不会把这个证据外推成 100% 宿主保障。 |

### 7.3 Evolution Factory 候选处理

- 处理：无新增候选 / no-promote。
- 理由：本轮形成了可复用经验，但它不是新的独立知识资产链，而是对既有 hook 唯一信源、执行保障和 Codex 宿主画像的直接加固。经验已写入本报告、`lessons.md` 的 L-155、`hook-standards`、`execution-guarantees` 与 Codex 宿主知识画像。

## 八、附录

### 8.1 关键证据

- 官方事实核准：OpenAI Codex Hooks / config reference。
- 机器回归：`redcap-codex-hooks-check.sh`、`codex-hooks-candidate-check`、`spec-check`、`diagnose`。
- live marker 证据：`references/codex-live-marker-e2e.json`。
- 独立验收：`prism/reports/2026-05-09-codex-lifecycle-hooks-candidate.md`、`prism/reports/2026-05-09-codex-live-marker-e2e-hardening.md`。
- 验收绑定：`prism/runs/20260509-codex-live-marker-e2e-hardening/artifacts/acceptance-binding.json`。

### 8.2 未升级声明

- Codex CLI marker 已通过；Codex.app interactive 仍未验证，Codex 整体不能说成 full host parity。
- 真实 Codex.app interactive live marker E2E 尚未执行。
- `PreToolUse` 只作为危险动作护栏，不是完整沙箱。
