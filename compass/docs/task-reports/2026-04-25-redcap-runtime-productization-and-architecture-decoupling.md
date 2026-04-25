# 任务完成报告：RedCap 产品形态重定位与系统架构解耦

**报告日期**：2026-04-25  
**执行者**：Cap（Codex.app 宿主；Prism 外部 reviewer 不使用 Copilot CLI）  
**报告版本**：v0.1

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：已把本轮任务重锚定到 `.dev-task.md`，确认北极星是：RedCap 不再只叙述为某个宿主 skill，而是向独立 Agent Runtime / CLI / 多层协作系统演进。
- 已新增 `references/redcap-system-layers.md`，把执行层、Prism 层、知识层、Evolution 层、证据层、人类阅读层、人格层、宿主适配层与检索层拆开，形成后续迁移路线。
- 已新增 `references/file-lookup-dictionary.md`，用“总字典 + 文件短反链”的方式解释关键 JSON / registry / scripts，避免把长注释塞进每个文件头造成新的 token 污染。
- 已新增 `references/prism-provider-policy.json` 与 `compass/tools/redcap-provider-policy.sh`，并把 Copilot CLI 冻结窗口接入 health probe、reviewer order、stop-review、baton launcher、agent detect 和 Prism dispatch check。
- 已把 Feishu 完成通知收敛为 closeout runtime 的 `on-complete` 单一人类可见 owner；`session-end` 在 runtime complete 路径下仍做证据核对，但跳过重复成功通知。
- 已补全 skill lifecycle policy 的生命周期状态与必备控制面，澄清上一轮只完成“唯一信源 / 多宿主 link”底座，不等于完整生命周期。
- 已把本轮两条高价值经验沉淀为 `EVO-2026-04-25-003/004` 并晋升到 lessons：provider freeze 必须守启动口；文件解释应走字典优先。

### 0.2 上一步完成的是

- 上一步完成的是：Kimi 棱镜评审指出 provider policy fail-open 与自定义 registry 耦合风险；随后已补齐 `redcap-provider-policy.sh` 的 Copilot 缺失策略 fail-closed、`redcap-agent-health-probe.py` 的 missing-policy 跳过真实 Copilot、`redcap-detect-agents.sh` 的 policy-unavailable 保护、`redcap-on-stop-review.sh` 的 registry 解耦，以及 acceptance fixture 的测试豁免声明。

### 0.3 下一步计划做的是

- 下一步计划做的是：执行 closeout runtime 生成 receipt，并确认 Feishu 只发一条最终收口通知。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：任务重锚定 → 产品形态/目录边界总纲 → 文件查阅字典 → provider freeze 强门 → skill lifecycle 补全 → Feishu 通知 owner 收敛 → Prism 调度/通信协议升级 → 知识检索路线 → lessons/Evolution 沉淀 → Prism + 回归 + closeout。
- 当前所在位置：实现补丁已落地并通过多组 targeted acceptance；Prism 已绑定为 resource-limited-pass（Kimi 有效，其它非 Copilot provider 不可用，Copilot frozen），仍处于 closeout receipt 生成前，不能宣称已正式完成。

---

## 一、需求背景

用户提出两类要求：

- 架构层：把 RedCap 从“宿主 skill 仓库”重新定位为更独立的 Agent Runtime / CLI / 多层系统，并围绕目录边界、知识/经验/报告分层、skill 生命周期、检索路线和自我进化能力形成可持续升级计划。
- 执行层：从 2026-04-25 到 2026-05-01 00:00 +08:00 不再调用 Copilot CLI；同时为关键控制面文件提供人类可读解释入口，但不能重新制造上下文膨胀。

## 二、方案讨论

### 2.1 文件解释采用字典优先

没有把长解释散落到每个 JSON / shell / Python 文件头部。原因是这会增加上下文污染和多源分叉风险。最终采用：

- `references/file-lookup-dictionary.md` 作为解释主入口。
- 文件头只放一句定位和字典反链。
- README 与 `CONTRIBUTING.core.md` 只指向字典，不默认展开大文件。

### 2.2 Copilot 冻结必须是启动口强门

冻结窗口不是排序建议，而是资源保护策略。因此接入点覆盖：

- `redcap-agent-health-probe.py`：冻结或 policy 缺失时不做真实 live probe。
- `redcap-reviewer-order.py` / `redcap-on-stop-review.sh`：排序和执行都跳过 frozen provider。
- `baton-launcher.sh`：任务委派启动前调用 `assert-not-frozen`。
- `redcap-detect-agents.sh`：冻结或 policy 不可用时不执行 `copilot --version`。
- `prism-dispatch-check.sh`：包含 frozen provider 的 roster 直接 fail。

### 2.3 Feishu 完成通知只保留一个人类可见 owner

`closeout-runtime -> on-complete` 负责最终成功通知。`session-end` 仍保留 blocker / alert 通知能力，但在 runtime complete 路径下通过 `REDCAP_SKIP_SESSION_END_SUCCESS_NOTIFY=1` 跳过重复成功通知。

### 2.4 RedCap 产品形态是迁移路线，不是假装已完成

`references/redcap-system-layers.md` 只宣告目标形态和迁移 tranche，不宣称当前仓库已经完成从 skill-root 到独立 runtime / CLI 的物理迁移。

## 三、落地结果

### 3.1 新增

- `references/redcap-system-layers.md`：RedCap 多层系统与迁移路线。
- `references/file-lookup-dictionary.md`：关键文件查阅字典。
- `references/prism-provider-policy.json`：provider 冻结与调度策略。
- `compass/tools/redcap-provider-policy.sh`：冻结策略机器检查入口。

### 3.2 修改

- `README.md` / `compass/CONTRIBUTING.core.md`：把产品定位、文件字典、provider freeze 和章节路由写入轻量入口。
- `compass/evolution/README.md` / `references/evolution-grade-baseline.json`：修正 Evolution 叙事，避免把全局控制面保障误写成只为自升级服务。
- `references/skill-lifecycle-policy.json` / `redcap-skill-lifecycle-check.py`：补齐 skill 生命周期状态和必备控制面。
- `compass/tools/redcap-agent-health-probe.py`、`redcap-reviewer-order.py`、`redcap-on-stop-review.sh`、`baton-launcher.sh`、`redcap-detect-agents.sh`、`prism-dispatch-check.sh`：接入 provider freeze policy。
- `compass/tools/redcap-layerB-session-end.sh` / `redcap-layerb-closeout-runtime.py`：收敛成功通知 owner。
- `compass/tools/redcap-multi-session-acceptance.sh`：新增冻结、policy 缺失、通知去重等回归。
- `compass/evolution/candidates.json` / `compass/knowledge/lessons.md`：沉淀本轮经验。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮落点 |
|---|---|---|
| provider policy | 一张机器可读的“哪些 Agent 在哪些场景不能启动”的规则表，当前用于禁止 Copilot CLI 在冻结窗口内被 RedCap 启动 | `references/prism-provider-policy.json`、`compass/tools/redcap-provider-policy.sh` |
| file lookup dictionary | 给人和 Agent 查文件用途的字典，负责解释关键 JSON / 脚本的定位，避免把长说明塞进每个文件头 | `references/file-lookup-dictionary.md` |
| system layers | RedCap 从 skill-root 走向 runtime / CLI / 多层系统的分层路线图，不代表迁移已经完成 | `references/redcap-system-layers.md` |
| success notification owner | 最终成功飞书通知的唯一负责人；本轮收敛为 closeout runtime 调用的 on-complete | `compass/tools/redcap-layerb-closeout-runtime.py`、`compass/tools/redcap-layerB-session-end.sh` |
| resource-limited Prism | 外部 reviewer 不足时的诚实状态：可以记录资源受限和已跑证据，但不能冒充 formal quorum | `prism/runs/**`、本报告“四、棱镜与外部 reviewer” |

## 四、人工审核要点

### 4.1 已执行

- Kimi CLI：可用，完成一次独立 review，结论 PASS，并指出两条风险：policy 脚本不可用 fail-open、自定义 registry 下 stop-review freeze 失效。
- Gemini CLI：安装可见，但 headless prompt 在 30 秒和 60 秒有界调用中均超时，只输出 YOLO 提示，无模型正文。
- Claude CLI：安装可见，但 `--bare -p` 90 秒无输出超时。
- Codex CLI：安装可见，但缺少 `@openai/codex-darwin-arm64` optional dependency，无法执行。
- Copilot CLI：按用户要求冻结，未调用真实 Copilot CLI。

### 4.2 Kimi 风险处理结果

- `redcap-provider-policy.sh` 对 Copilot 在 policy 缺失/损坏时 fail-closed。
- `redcap-agent-health-probe.py` 在 Copilot live probe + policy 不可用时返回 `policy-unavailable`，不调用 CLI。
- `redcap-detect-agents.sh` 在 policy 不可用或冻结时跳过 `copilot --version`。
- `redcap-on-stop-review.sh` 的 provider policy 不再依赖默认 registry 路径；测试 fixture 需要 fake Copilot 时必须显式 `REDCAP_DISABLE_PROVIDER_POLICY=1`。
- `scope: "all"` 已统一到 health、reviewer-order、stop-review、provider-policy 与 Prism dispatch。
- stop-review 与 Prism dispatch 在 policy 文件物理缺失时，对 Copilot 也 fail-closed。

### 4.3 当前 Prism 状态

- `prism_acceptance_run`: `review-redcap-runtime-productization-20260425-r1`
- 结果：`resource-limited-pass`
- 含义：这不是 formal quorum；它只证明当前可用外部 reviewer Kimi 未发现 blocker，并且 Gemini / Claude / Codex / Copilot 的不可用或冻结证据已落盘。
- 后续：至少一个非 Copilot 的第二 provider 恢复后，应重跑正式双家族 Prism quorum。

## 五、验证结果

### 5.1 已通过

- `bash -n`：`redcap-provider-policy.sh`、`redcap-detect-agents.sh`、`redcap-multi-session-acceptance.sh`、`redcap-on-stop-review.sh`、`baton-launcher.sh`、`prism-dispatch-check.sh`
- `python3 -m py_compile`：`redcap-agent-health-probe.py`、`redcap-reviewer-order.py`、`redcap-skill-lifecycle-check.py`、`redcap-evolution-grade-check.py`、`redcap-layerb-closeout-runtime.py`
- `bash compass/tools/redcap-multi-session-acceptance.sh agent-health-probe`
- `bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-prefers-copilot-premium-model-over-lighter-clis`
- `bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-falls-back-after-timeout`
- `bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-records-unavailable-rate-limit`
- `bash compass/tools/redcap-multi-session-acceptance.sh session-end-success-notify-skip-for-closeout-runtime`
- `bash compass/tools/redcap-multi-session-acceptance.sh layerb-closeout-runtime-complete-writes-receipt`
- `bash prism/tools/prism-dispatch-check.sh --mode test --agents "kimi&kimi-for-coding:reviewer,gemini&gemini-2.5-flash:tester"` PASS
- `bash prism/tools/prism-dispatch-check.sh --mode test --agents "copilot&gpt-5.4:reviewer,kimi&kimi-for-coding:tester"` 按预期 FAIL，原因是 Copilot provider frozen。

### 5.2 待通过

- closeout runtime receipt

### 5.3 closeout runtime / receipt

| 项 | 当前证据 |
|---|---|
| closeout receipt | 无；当前仍处于 closeout 前，不能宣称已正式完成 |
| pending closure | 待最终 closeout runtime 复核 |
| Feishu 最终通知 | 待最终 closeout 成功后由 on-complete 发送 |

### 5.4 完成等级（禁止混报）

| 层级 | 状态 | 说明 |
|---|---|---|
| 已实现 | 是 | 产品形态路线、文件字典、provider freeze、skill lifecycle、Feishu owner、经验沉淀补丁已落地 |
| 已自检 | 是 | targeted acceptance、full regression、spec-check、diagnose、语法检查均已通过 |
| 已独立验收 | 部分 | 已绑定 resource-limited Prism；Kimi reviewer PASS，其它非 Copilot provider 不可用，未形成 formal quorum |
| 已正式完成 | 否 | 已有 resource-limited Prism binding，但还没有 closeout receipt，不能把当前状态混报为完成 |

## 七、经验沉淀

### 7.3 Evolution Factory 候选处理

| 候选 | 状态 | 处理结果 |
|---|---|---|
| `EVO-2026-04-25-003` provider freeze 启动口强门 | promoted | 已晋升到 `compass/knowledge/lessons.md` 的 L-116 |
| `EVO-2026-04-25-004` 文件解释字典优先 | promoted | 已晋升到 `compass/knowledge/lessons.md` 的 L-117 |

本轮没有留下 `candidate` / `reviewing` 状态的 Evolution 候选；后续如果 formal Prism quorum 恢复并发现新风险，应另立候选而不是塞回本报告。

## 八、附录

### 8.1 关键证据路径

| 证据 | 路径 |
|---|---|
| 任务卡 | `.dev-task.md` |
| 本报告 | `compass/docs/task-reports/2026-04-25-redcap-runtime-productization-and-architecture-decoupling.md` |
| provider policy | `references/prism-provider-policy.json` |
| resource-limited Prism run | `prism/runs/review-redcap-runtime-productization-20260425-r1/` |
| 文件查阅字典 | `references/file-lookup-dictionary.md` |
| RedCap 多层路线 | `references/redcap-system-layers.md` |

## 六、遗留问题与下一步

- 当前只治理 RedCap-owned 启动口；用户手动在 shell 里直接执行 `copilot ...` 不属于仓库可物理拦截范围。
- RedCap 仍处于 skill-root 承载形态；独立 runtime / CLI 是迁移路线，不是本轮已经完成的物理产品化。
- Gemini CLI / Claude CLI / Codex CLI 当前本机 headless 不稳定；本轮会使用 Gemini API 补足第二模型族 review，但会如实记录 CLI 不可用事实。
