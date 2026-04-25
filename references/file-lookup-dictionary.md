# RedCap File Lookup Dictionary

> 目的：给人类和 Agent 一个“先看这里”的文件地图。具体文件只保留短注解和反链，长解释集中在本字典，避免每个脚本头部都膨胀成 token 污染源。

## How To Read

- 先按“你想理解的对象”找到条目，再跳到对应文件。
- 机器可读文件优先看 `meaning` / `owner` / `check` 三列，不要默认打开全文历史报告。
- 文件头里的 `Dictionary:` 注解只负责反链，不复制本字典的大段解释。

## Control Plane Assurance

| 文件 | 定位 | 含义 | owner | check |
|---|---|---|---|---|
| [`references/evolution-grade-baseline.json`](../references/evolution-grade-baseline.json) | control-plane assurance registry 兼容路径 | 用统一维度审计 RedCap 各保障节点是否达到、降级或受宿主限制；文件名保留 `evolution-grade` 是兼容历史，语义上不是只服务自升级 | Compass governance | `bash compass/tools/redcap-evolution-grade-check.sh` |
| [`compass/tools/redcap-evolution-grade-check.sh`](../compass/tools/redcap-evolution-grade-check.sh) | assurance registry shell entry | 轻量入口；默认校验上面的 registry | Compass validator | `bash compass/tools/redcap-evolution-grade-check.sh` |
| [`compass/tools/redcap-evolution-grade-check.py`](../compass/tools/redcap-evolution-grade-check.py) | assurance registry validator | 校验节点、路径、降级理由、remediation 是否完整 | Compass validator | 由 `.sh` 包装调用 |

## Runtime And Closeout

| 文件 | 定位 | 含义 | owner | check |
|---|---|---|---|---|
| [`closeout-cap.sh`](../closeout-cap.sh) | root closeout facade | 人类/Agent 记一个短入口；内部转调 Layer B closeout runtime | Layer B runtime | `./closeout-cap.sh status` |
| [`compass/tools/redcap-layerb-closeout-runtime.py`](../compass/tools/redcap-layerb-closeout-runtime.py) | unified closeout runtime | 串起承诺账本、Prism acceptance、on-complete、session-end、receipt 和 rescue audit | Layer B runtime | `bash compass/tools/redcap-layerb-closeout-runtime-check.sh` |
| [`compass/tools/redcap-intent-coverage-check.sh`](../compass/tools/redcap-intent-coverage-check.sh) | original intent coverage gate | PM Gate 的原始意图覆盖审计，防止把用户战略目标降级成只完成路线图的小账本 | Layer B PM Gate | `bash compass/tools/redcap-intent-coverage-check.sh .dev-task.md` |
| [`compass/tools/redcap-on-complete.sh`](../compass/tools/redcap-on-complete.sh) | on-complete gate | closeout 前置校验、摘要和主成功通知 owner；被 closeout runtime 编排 | Layer B runtime | acceptance cases with `on-complete-*` |
| [`compass/tools/redcap-layerB-session-end.sh`](../compass/tools/redcap-layerB-session-end.sh) | session-end reconcile gate | 会话结束兜底审计、pending closure 清账、blocker 告警；在 closeout runtime 中不再重复发送成功通知 | Layer B runtime | acceptance cases with `session-end-*` |

## Prism And Providers

| 文件 | 定位 | 含义 | owner | check |
|---|---|---|---|---|
| [`references/prism-provider-policy.json`](../references/prism-provider-policy.json) | provider policy | 记录 provider 选择、冻结窗口和 evidence 口径；当前包含 Copilot CLI 临时冻结 | Prism governance | `bash compass/tools/redcap-agent-health-probe.sh --stdout --live ...` |
| [`compass/tools/redcap-provider-policy.sh`](../compass/tools/redcap-provider-policy.sh) | provider freeze gate | RedCap-owned CLI launcher 的冻结期硬门，调用前判断 provider 是否可启动 | Prism governance | `bash compass/tools/redcap-provider-policy.sh assert-not-frozen <agent> <scope>` |
| [`compass/tools/redcap-agent-health-probe.py`](../compass/tools/redcap-agent-health-probe.py) | live health probe | 区分“已安装”与“真实 headless 可用”；遇到冻结 provider 时返回 `frozen` 且不执行 CLI | Prism governance | `bash compass/tools/redcap-agent-health-probe.sh --stdout` |
| [`compass/tools/redcap-detect-agents.sh`](../compass/tools/redcap-detect-agents.sh) | registry refresh | 轻量刷新本地 CLI 可见性；冻结 provider 只记录 frozen，不调用其 version/probe | Prism governance | `bash compass/tools/redcap-detect-agents.sh /tmp/registry.yaml --agent <agent>` |
| [`compass/tools/baton-launcher.sh`](../compass/tools/baton-launcher.sh) | direct CLI launcher | Loom / baton 的通用 Agent 启动器；启动前必须通过 provider freeze gate | Loom + Prism governance | baton acceptance / provider policy check |
| [`compass/tools/redcap-reviewer-order.py`](../compass/tools/redcap-reviewer-order.py) | reviewer router | 按模型能力画像、本地稳定性、冻结策略生成 stop-review fallback 顺序 | Prism governance | stop-review acceptance |
| [`prism/protocol.md`](../prism/protocol.md) | Prism protocol | 定义独立取样、council、evidence、provider 选择与 `prism/runs` 生命周期 | Prism | `bash prism/tools/prism-evidence-check.sh` |

## Skill And Host Distribution

| 文件 | 定位 | 含义 | owner | check |
|---|---|---|---|---|
| [`references/skill-lifecycle-policy.json`](../references/skill-lifecycle-policy.json) | skill lifecycle source | 定义 RedCap-native capability、host-exported skill、portable package 的状态、门禁、回滚和弃用规则 | Host adapters | `bash compass/tools/redcap-skill-lifecycle-check.sh` |
| [`compass/tools/redcap-skill-lifecycle-check.py`](../compass/tools/redcap-skill-lifecycle-check.py) | skill lifecycle validator | 防止宿主入口复制分叉规则，并校验 lifecycle fields | Host adapters | 由 `.sh` 包装调用 |
| [`AGENTS.md`](../AGENTS.md) / [`CLAUDE.md`](../CLAUDE.md) / [`GEMINI.md`](../GEMINI.md) / [`.github/copilot-instructions.md`](../.github/copilot-instructions.md) | host thin entries | 宿主入口只做轻量索引和复活，不承载权威规则正文 | Host adapters | revival / skill lifecycle checks |

## Product Shape And Retrieval

| 文件 | 定位 | 含义 | owner | check |
|---|---|---|---|---|
| [`references/redcap-system-layers.md`](../references/redcap-system-layers.md) | productization roadmap | 把 RedCap 从 skill repo 演进为 Agent Runtime / CLI / 多层系统的边界和迁移路线讲清楚；不是已完成迁移声明 | Architecture | task report + Prism review |
| [`README.md`](../README.md) | public landing page | 面向人类的一眼看懂入口，只讲核心优势和导航，不承载细则 | Product narrative | human-output review |
| [`compass/docs/catalog.json`](../compass/docs/catalog.json) | docs catalog | docs 首读索引，防止任务一开始 bulk-read 历史报告 | Docs governance | `bash compass/tools/redcap-docs-catalog.sh summary` |
| [`compass/knowledge/index.md`](../compass/knowledge/index.md) | knowledge index | lessons/knowledge 首读索引，防止默认打开知识库全文 | Knowledge governance | `bash compass/tools/redcap-knowledge-index-check.sh` |
