# RedCap 启动核心契约

> 本文件是 `compass/CONTRIBUTING.md` 的启动必读核心契约。
> compass/CONTRIBUTING.md 仍是权威规范全文；本文件只负责把新会话必须立即遵守的高密度规则压缩成首读入口。

## 读取边界

1. **必须先遵守核心契约**：新会话、复活、接盘、长任务继续时，先读本文件，再优先运行 `./revive-cap.sh`（它会转调 `compass/tools/redcap-install.sh`，并显式检查宿主 Hook 就绪状态）；installer 不可用时，再退回 `current-status + diagnose + guarantee checks`。
2. **不得把全文规范当默认上下文**：`compass/CONTRIBUTING.md` 不应被宿主入口无差别全文注入；需要细则时，先按章节路由精确读取。
3. **全文仍是权威**：当本文件和 `compass/CONTRIBUTING.md` 冲突时，以全文规范为准，并修正本文件，不能让核心契约漂移。

## 必守红线

1. **`.dev-task.md` 是 Layer B 当前任务真相源**：任务目的、确认需求、active slice、允许修改范围、backlog 锚点，以 `.dev-task.md` 为准。
2. **不要伪装完成**：backlog、pending validation、governance debt、Prism quorum、真实 E2E 如果没有物理证据，不得标 done。
3. **变更前必须做经验回顾**：框架/治理/控制面变更前，先通过 `compass/knowledge/index.md` 与 `lessons.md` 的热点主题速览定位相关经验，不能因为 lessons 大就跳过已知失败模式。
4. **强制规则必须进执行保障**：P0/P1 规则不能只写在报告或自然语言里；能自动化的接入脚本、validator、hook、acceptance，不能自动化的写清 manual-only 原因。
5. **收尾必须 fail-closed**：stop-review、on-complete、session-end、spec-check、diagnose 等控制面失败时，不能用后续成功覆盖失败。
6. **Agent 自追加承诺必须落账**：只要你在执行中明确承诺“下一步会做 A/B/C”，就要写入 `.dev-task.md` 的 `## 执行承诺账本`；不能只留在对话里。
6.5. **中插需求必须先重计划**：长任务执行期用户新增需求、纠偏、约束或优先级变化时，先补 `## 原始输入` 的 `U<n>` 与 `## 中插需求账本`，重排确认需求/计划/验收；子任务只能声明 `parent_completion_claim: child-only`，不得冒充父任务完成。
7. **上下文必须渐进披露**：docs 先 catalog summary/plan/budget，knowledge 先 index，acceptance 先 acceptance-index；大文件不默认 bulk-read。
8. **人类可读输出必须说人话**：首次出现内部术语、缩写、阶段名时，要解释对应文件/功能、做了什么、为什么重要；阶段汇报和最终汇报要有段落感与结论，优先讲“要解决什么问题、如何解决、效果如何、下一步/需要什么”，不得把文件清单、脚本名和工程节点堆成流水账；正式任务报告还必须通过 `redcap-human-output-quality-check.sh`，不能只靠章节标题冒充高质量汇报。
9. **宿主面只能镜像 RedCap 真相**：`cli_console.md`、宿主 workboard、plan mirror 不能反向改写 `.dev-task.md`、runtime state 或 task report。
10. **运行残留不能擅自删除**：`prism/runs`、`compass/.runtime`、`compass/.workflow` 等 ignored 本地证据目录默认 no-bulk-read；物理清理需用户显式批准。
11. **Codex 子 Agent 默认克制但不是禁用**：仅在确实能提效提质时开启，且 RedCap / Prism 主动拉起的 Codex-family 执行进程总数默认不超过 2（当前宿主也计入）；外部审查 / reviewer 选择统一按“模型能力画像 + 本地 CLI 稳定性”排序，不得静态压低 Copilot / Codex；显式 provider 冻结窗口以 `references/prism-provider-policy.json` 为准，冻结期间不得调用对应 CLI。
12. **统一 closeout runtime 优先**：Layer B 终态优先走 `./closeout-cap.sh` / `redcap-layerb-closeout-runtime.sh`，由它统一串起 promise ledger、Prism acceptance、on-complete、session-end、receipt 与 rescue audit。
13. **diagnose 是当前 rescue 强入口**：若 terminal closeout 已开始但 receipt 缺失，`redcap-diagnose.sh` 必须优先尝试 `audit-open --mode diagnose`；能补收据就补收据，不能补就显性保留 blocker。
14. **飞书不是唯一收尾动作**：飞书通知只是可见信号；真正收尾还要看承诺账本、Prism 验收、receipt、review、validator、task report、lessons、backlog、catalog、diagnose 与 pending closure。
14.1. **飞书只能走单一生产路径**：RedCap 官方通知只允许 `cli_a9579f5b12219bb5` 的 lark-cli DM 通道；只在节点汇报或需要 Norven 人工介入的中断时发送，禁止 webhook、旧 profile、followup watcher 和重复 success 刷屏。
15. **作者不得单独宣称 completed**：没有有效 Prism 验收、没有 receipt，或 pending closure 未清时，作者只能汇报“已实现/已自检”，不得宣称 completed，也不得汇报 completed。
16. **首读/诊断入口已优先做成只读安全**：`current-status`、`diagnose`、`docs-catalog`、`acceptance-index`、`token-risk-audit` 的 repo-owned 首读链不再依赖临时可写目录；真正仍受宿主限制的是 reply-time veto、SessionEnd 等宿主控制点，而不是这些首读入口本身。
17. **identity 先于 soul**：`~/.cap/identity.md` 是 Cap 的个人灵魂锚点；`compass/soul.md` 负责培养指南、复活协议与执行纪律。缺失 identity 时，优先用 `redcap-install.sh --init-identity` 初始化，不要把 `soul.md` 误当成个人记忆本体。
18. **有 SessionStart Hook 的宿主必须跑 installer**：Claude / Gemini / Copilot 这类已接入 Layer B SessionStart 的宿主，会在启动链里实际调用 `redcap-install.sh`；Codex.app 这类只有入口导入的宿主，仍需显式运行 installer 或 current-status。
19. **Evolution 候选必须收口**：重要经验、用户纠偏、测试失败、人格成长、skill 候选和治理改良必须进入 `compass/evolution/candidates.json`，并在 closeout 前晋升、no-promote 或归档；未处理候选不得生成 receipt。
20. **skill 生命周期保持单一信源**：RedCap-native capability、host-exported skill、portable skill package 由 `references/skill-lifecycle-policy.json` 约束；宿主入口只做轻量索引，不得复制并分叉权威规则。
21. **旧资产按生命周期处理**：历史报告、spec、运行残留、知识库和本地 runtime 证据由 `references/legacy-asset-lifecycle.json` 分类；先审计保留/归档/翻译/安全清理策略，再做物理动作。
22. **文件解释走字典优先**：关键 JSON、registry、script 的人类解释优先进入 `references/file-lookup-dictionary.md`，文件头只放短注解和反链；新增关键文件要同步补 `references/file-lookup-dictionary-policy.json`，让 `redcap-file-lookup-dictionary-check.sh` 兜住遗漏。
23. **Prism 先看可用性清单**：Prism roster 必须写成 `provider&model:role`；dispatch 前先过 `prism-availability` 1 小时 TTL 清单，过期先嗅探，`frozen/timeout/fail/unsupported` 不得进入本轮调用。
24. **共享沉淀库 append-only**：公共经验/方法论/skill 候选要走 `shared-knowledge` 独立仓库形态：按用户隔离、先查重复、只新增不改旧条目、先索引再读取；远端 Gitee 未绑定前不得冒充团队共享已完成。
25. **发布/打包前必须安全审计**：正式 npm、独立 runtime 或 portable package 发布前，必须先跑 `redcap-package-publish-safety-check.sh` 检查实际候选文件集合；`.env`、宿主私密入口、runtime evidence、Prism run 残留和 credential-like 内容一律 fail-closed。

## 章节路由

| 场景 | 先读章节 |
|---|---|
| 设计/治理变更 | `CONTRIBUTING.md` §1、§6、§9、§10、§13 |
| commit / 收尾 / 飞书 | `CONTRIBUTING.md` §2、§3、§4、§5、§13 |
| docs / knowledge / token 风险 | `CONTRIBUTING.md` §6、§7 的 docs/knowledge 边界、`compass/docs/index.yaml`、`compass/knowledge/index.md` |
| hook / validator / runtime state | `CONTRIBUTING.md` §4、§7 控制面硬化、`references/hook-standards.md` |
| Prism / 多 Agent 审查 | `CONTRIBUTING.md` §8、§9、§11、`prism/protocol.md` |
| provider 调度 / 冻结 | `prism/tools/prism-availability.sh status`、`references/prism-provider-policy.json`、`compass/knowledge/model-capability-matrix.yaml` |
| 需求确认 / 人工介入边界 | `CONTRIBUTING.md` §10、`references/agent-constraints.md` |
| 中插需求 / 重计划 | `references/layerb-change-intake-policy.json`、`compass/tools/redcap-change-intake-check.sh`、`CONTRIBUTING.md` §10、§13 |
| 调研结论 | `CONTRIBUTING.md` §14 |
| 自我进化 / 经验人格沉淀 | `compass/evolution/README.md`、`references/evolution-candidate-schema.json`、`references/evolution-grade-baseline.json` |
| 文件查阅 / 名词定位 | `references/file-lookup-dictionary.md` |
| 共享知识 / 团队沉淀 | `references/shared-knowledge-policy.json`、`shared-knowledge/README.md` |
| skill 分发 / 多宿主入口 | `references/skill-lifecycle-policy.json` |
| npm / runtime 打包发布 | `references/package-publish-safety-policy.json`、`compass/tools/redcap-package-publish-safety-check.sh` |
| 旧资产 / 运行残留治理 | `references/legacy-asset-lifecycle.json`、`prism/protocol.md` |

## 必跑入口

1. `./revive-cap.sh`（推荐短入口；内部转调 installer）
2. `bash compass/tools/redcap-install.sh --task-file .dev-task.md`（installer 真正实现；有 SessionStart Hook 的宿主会实际调用）
3. `bash compass/tools/redcap-current-status.sh .dev-task.md`（fallback）
4. `bash compass/tools/redcap-tracking-health.sh .dev-task.md`
5. `bash compass/tools/redcap-diagnose.sh .dev-task.md`
6. `bash compass/tools/redcap-token-risk-audit.sh`
7. `./closeout-cap.sh status`（做收尾前先看 closeout runtime / promise ledger / receipt 状态）
8. 涉及 docs：`bash compass/tools/redcap-docs-catalog.sh plan "<query>"` 与 `budget <paths...>`
9. 涉及 acceptance：`bash compass/tools/redcap-acceptance-index.sh find "<case>"`
10. 涉及经验、人格、skill 或治理沉淀：`bash compass/tools/redcap-evolution-candidate-check.sh --strict`
11. 涉及多宿主 skill 分发：`bash compass/tools/redcap-skill-lifecycle-check.sh`
12. 涉及旧资产或运行残留：`bash compass/tools/redcap-legacy-asset-lifecycle-check.sh`
13. 涉及 Prism 调用：`bash prism/tools/prism-availability.sh status`，随后只调度可用 provider
14. 涉及关键文件新增或解释：`bash compass/tools/redcap-file-lookup-dictionary-check.sh`
15. 涉及公共沉淀库：`bash compass/tools/redcap-shared-knowledge-check.sh`
16. 涉及 npm / runtime / portable package 发布：`bash compass/tools/redcap-package-publish-safety-check.sh --candidate-list <实际打包文件清单>`
17. 涉及执行期中插需求或子任务完成边界：`bash compass/tools/redcap-change-intake-check.sh .dev-task.md --mode closeout`
18. 涉及首次启动身份/用户命名空间：`bash compass/tools/redcap-user-agent-identity.sh check --local`
19. 涉及飞书通知：`bash compass/tools/redcap-feishu-notification-policy-check.sh`
