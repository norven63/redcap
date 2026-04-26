# 任务完成报告：RedCap 执行层重构与公共知识库治理落地

**报告日期**：2026-04-26  
**执行者**：Cap（Codex.app 主 Agent + Kimi resource-limited Prism reviewer）  
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：R0-R22 已完成本地控制面落地：Prism 可用性 TTL 清单、File Lookup Dictionary coverage gate、shared-knowledge append-only 模板、`bin/redcap` 薄 CLI facade、文档表达、targeted/full acceptance 与整体控制面回归。
- 详情：Prism 调度前现在会先检查 1 小时 TTL 可用性清单；字典不再靠人工记忆维护，而是有 policy/check 接入 diagnose/spec-check；公共沉淀库先以本地模板和写入工具落地，远端 Gitee 绑定明确延期。

### 0.2 上一步完成的是

- 上一步完成的是：跑完 full acceptance、`spec-check`、`diagnose`，并修复回归中暴露的 `execution-guarantees.json` 大文件结构治理缺口。

### 0.3 下一步计划做的是

- 下一步计划做的是：无本轮剩余实现任务；提交后由 `./closeout-cap.sh` 生成同一任务 hash 的正式 receipt。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：需求重锚 → Planning/coverage 设计 → Prism/Dictionaries/Shared Knowledge/CLI 实现 → targeted acceptance → 独立审查 → 全量回归 → closeout receipt。
- 当前所在位置：实现、独立审查与回归均已完成，处于 closeout receipt 收口点。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 审核通过。补2个需求：
> 1. “Prism 使用增强”的细节：新增“可用性”嗅探机制，并建立一份清单，标注哪些Agent可用/不可用，清单文件时效1小时，使用时发现如果过期则重新嗅探，每次使用Prism时先检索一遍可用清单，只挑可用的Agent调用，这样可以避免每次任务浪费在大量的调试、等待无效的Agent上。
> 2. RedCap File Lookup Dictionary.md文件细节：当前是最全的索引了吗？感觉还遗漏了很多；另外，这个索引是需要实时更新的，并且这个更新机制要加入100%保障中
>
> 这次是一个非常长、复杂的开发任务，你要想尽办法稳步前进、安全落地，不要因为复杂任务而改出新问题，时刻做好回归验证，注意“不要再像之前那样遗漏需求实现”。期间允许你“因发现不合理的设计而新增需求“，但如果是涉及到”必须要我人工介入“的问题则应当中断与我讨论后再继续。最后，期待你的最终汇报，Cap

### 1.2 触发背景

这轮任务是在用户已经批准 R0-R20 架构升级清单后追加的收口要求：不能再把“路线图、文档建议、半成品脚本”当成完成结果。核心目标是把 RedCap 从 skill-root 大杂烩继续推进到可安装 runtime / CLI / 多层系统，同时把容易吞 token 的知识和报告层改为索引优先、按需披露。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 原始意图 | 完整落地 R0-R22 的本地控制面，避免需求缩水和遗漏，尤其 Prism 可用性、File Lookup Dictionary、执行层/公共知识库分层 |
| 已覆盖 | 本地脚本、policy、checker、CLI facade、shared-knowledge 模板、targeted acceptance、diagnose/spec-check 接线、文档表达 |
| 未覆盖/延期 | 远端 Gitee 仓库创建与绑定、大规模历史资产物理迁移、正式 npm/pip/brew 分发 |
| 用户可见边界 | 本轮不能宣称远端团队共享库已部署，也不能宣称所有旧报告已物理迁移出执行层 |
| 后续路径 | 使用本轮新增工具绑定远端 shared-knowledge；另立迁移任务执行历史资产 dry-run/apply |

---

## 二、方案讨论

### 2.1 问题分析

本轮暴露的是两个同源问题：第一，Prism 的“可见 Agent”与“真可用 Agent”混在一起，导致长任务可能把时间浪费在登录态丢失、冻结或超时的 CLI 上；第二，关键文件地图只是人类文档，没有机器 coverage gate，所以新增文件后容易继续漏索引。

公共知识库和执行层分离则是更上层的产品形态问题：RedCap 不应把所有报告、经验、人格、共享方法论都塞在 skill-root 里。正确方向是执行层保留高频 runtime 和 validator，长期沉淀进入独立、append-only、索引优先的共享库。

### 2.2 方案选项

| 主题 | 选项 | 描述 | 优点 | 缺点 |
|---|---|---|---|---|
| Prism 可用性 | A | 只在文档中提醒先嗅探 | 低成本 | 仍靠人记忆，不能阻断错误 roster |
| Prism 可用性 | B | 新增 TTL cache 并接入 dispatch-check | 调度前可 fail-closed | 首次或过期时会花时间探测 |
| 字典治理 | A | 手工扩写字典 | 快 | 未来仍会漏 |
| 字典治理 | B | policy + checker + diagnose/spec-check | 可持续防漏 | 需要维护 policy |
| 公共知识库 | A | 直接搬迁历史资产 | 立刻干净 | 高风险，可能破坏考古引用 |
| 公共知识库 | B | 先落模板/schema/tool，再另立迁移 | 低风险、可逆 | 物理瘦身不是本轮全部完成 |

### 2.3 决策结果

| 主题 | 采纳方案 | 决策理由 | 决策方 |
|---|---|---|---|
| Prism 可用性 | B | 用户明确要求 1 小时清单和调用前过滤，必须脚本化 | NORVEN_DECIDE + CAP_DECIDE |
| 字典治理 | B | “最全索引”必须能被机器持续校验，而不是一次性补文档 | NORVEN_DECIDE + CAP_DECIDE |
| 公共知识库 | B | 先做可逆控制面，避免边开飞机边大搬家 | CAP_DECIDE |
| CLI 形态 | 薄 facade | 先把入口统一成 `bin/redcap`，底层逻辑不搬迁 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `prism/tools/prism-availability.py` / `.sh` | 新建 | 维护 1 小时 TTL Agent 可用性清单，支持 status / check-roster / filter-roster |
| `prism/tools/prism-dispatch-check.sh` | 修改 | dispatch 前强制检查可用 roster，拒绝不可用或未写 provider 的 Agent |
| `references/file-lookup-dictionary-policy.json` | 新建 | 定义 96 个关键文件 coverage 要求 |
| `compass/tools/redcap-file-lookup-dictionary-check.py` / `.sh` | 新建 | 校验字典覆盖关键文件和本地链接 |
| `references/file-lookup-dictionary.md` | 修改 | 补齐机器覆盖镜像和新机制条目 |
| `shared-knowledge/README.md` / `schemas/entry.schema.json` | 新建 | 公共知识库本地模板和条目 schema |
| `references/shared-knowledge-policy.json` | 新建 | 定义 append-only、用户隔离、索引优先、远端边界 |
| `compass/tools/redcap-shared-knowledge.py` / `.sh` / `-check.sh` | 新建 | 支持 init / append / index / dedupe / check |
| `bin/redcap` | 新建 | 薄 CLI facade，路由 revive/status/diagnose/closeout/prism-availability/file-dictionary/shared-knowledge |
| `compass/tools/redcap-spec-check.sh` / `redcap-diagnose.sh` | 修改 | 接入 Prism availability、字典 coverage、shared-knowledge check |
| `references/execution-guarantees.json` / checker | 修改 | 新增 Prism availability、file dictionary、shared knowledge 三条保障 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增三组 targeted acceptance |
| `README.md` / `ARCHITECTURE.md` / `compass/CONTRIBUTING*.md` / `prism/*.md` / `references/redcap-system-layers.md` | 修改 | 更新执行层、Prism 可用性、shared knowledge、字典保障表达 |

### 3.2 技术实现要点

Prism 可用性清单不是替代模型能力评估，而是解决“本地这个 provider 现在能不能被 headless 调用”。`prism-availability` 只把 `live_status=pass` 视为可用，`frozen/timeout/fail/unsupported` 都不能进入 dispatch roster；`prism-dispatch-check` 还要求 roster 使用 `provider&model:role`，防止模型名和 CLI provider 混淆。

File Lookup Dictionary 现在分成两层：`file-lookup-dictionary.md` 给人读，`file-lookup-dictionary-policy.json` 给机器审计。新增关键文件时，如果没有同步补 policy 和字典，`redcap-file-lookup-dictionary-check.sh` 会在 diagnose/spec-check 中失败。

shared-knowledge 是未来独立仓库的本地模板，不是把新知识库强塞回启动上下文。`redcap-shared-knowledge.sh append` 会按用户 namespace 写入时间戳文件，并先用 normalized fingerprint 做 exact duplicate 拒绝；`index` 输出 metadata，任务确需证据时再读正文。

`bin/redcap` 是薄 facade，不复制业务逻辑。它的价值是让 RedCap 的产品形态开始从“某宿主 skill 文件夹”走向“可安装 runtime / CLI”，同时保持现有 root 脚本和宿主 hook 兼容。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| Prism availability | `prism/tools/prism-availability.sh` | Prism 调用前的 1 小时可用性清单；过期先嗅探，只让真可用 Agent 入队 |
| provider-qualified roster | `provider&model:role` | roster 里必须写清本地调用谁，例如 `kimi&kimi-k2:reviewer` |
| File Lookup Dictionary policy | `references/file-lookup-dictionary-policy.json` | 机器用的“关键文件必须被字典覆盖”清单 |
| shared-knowledge | `shared-knowledge/` + `redcap-shared-knowledge.sh` | 未来独立公共沉淀库的本地模板，按用户隔离、只新增、先索引 |
| thin CLI facade | `bin/redcap` | 统一短入口，只转调现有工具，不搬迁底层逻辑 |
| resource-limited Prism | `prism/runs/20260426-redcap-execution-layer-resource-limited` | formal quorum 不可用时的诚实降级验收：记录不可用 provider，并保留至少一席独立审查 |

### 3.3 关联变更

本轮新增机制都接入了执行保障，而不是只写在报告里：Prism availability、File Lookup Dictionary coverage、shared-knowledge append-only 均已进入 `references/execution-guarantees.json`、`redcap-spec-check.sh`、`redcap-diagnose.sh` 和 acceptance。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 远端 Gitee 绑定 | 需要用户提供 remote 和权限，Cap 不能替用户创建/绑定远端团队仓库 | P1 |
| 2 | 历史资产物理迁移 | 本轮只做控制面和迁移支撑；真正搬迁旧报告/研究材料需要单独 dry-run/apply 任务 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| Prism availability targeted | `bash compass/tools/redcap-multi-session-acceptance.sh prism-availability` | 通过 |
| File Lookup Dictionary targeted | `bash compass/tools/redcap-multi-session-acceptance.sh file-lookup-dictionary-check` | 通过 |
| Shared Knowledge targeted | `bash compass/tools/redcap-multi-session-acceptance.sh shared-knowledge-check` | 通过 |
| Dictionary check | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| Shared knowledge check | `bash compass/tools/redcap-shared-knowledge-check.sh` | 通过 |
| Execution guarantees | `bash compass/tools/redcap-execution-guarantee-check.sh` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | resource-limited-pass |
| Bash syntax | `bash -n prism/tools/prism-availability.sh prism/tools/prism-dispatch-check.sh compass/tools/redcap-file-lookup-dictionary-check.sh compass/tools/redcap-shared-knowledge.sh compass/tools/redcap-shared-knowledge-check.sh bin/redcap compass/tools/redcap-spec-check.sh compass/tools/redcap-diagnose.sh` | 通过 |
| Python compile | `python3 -m py_compile prism/tools/prism-availability.py compass/tools/redcap-file-lookup-dictionary-check.py compass/tools/redcap-shared-knowledge.py compass/tools/redcap-execution-guarantee-check.py` | 通过 |
| Token risk audit | `bash compass/tools/redcap-token-risk-audit.sh` | 通过 |
| Spec check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| Diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |
| Full acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 用户后续提供 Gitee remote 后，执行 shared-knowledge 远端绑定。
- [ ] 若要物理迁移历史长报告，另开 dry-run/apply 迁移任务。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 已清，15/15 |
| 棱镜验收 | resource-limited-pass |
| closeout summary | `compass/.runtime/closeout/summaries/redcap-execution-layer-and-shared-knowledge-governance-144a58c8d0eee218dfbe4349f7bbb750dbeab915e9b0d9d49b821ee3a341ca4d.md` |
| closeout receipt | `compass/.runtime/closeout/receipts/redcap-execution-layer-and-shared-knowledge-governance-144a58c8d0eee218dfbe4349f7bbb750dbeab915e9b0d9d49b821ee3a341ca4d.json` |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，resource-limited Prism |
| 已正式完成 | 是；提交后由 closeout runtime 生成上方 receipt |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 远端 Gitee 仓库绑定 | 需要用户提供仓库和权限 | P1 |
| 历史资产大规模物理迁移 | 风险高，不能和控制面落地混在一批 apply | P1 |
| npm/pip/brew 正式分发 | 已有 `bin/redcap` facade，但正式包化需要独立发行设计 | P2 |

### 6.2 触发的新问题

Prism 可用性 cache 需要同时考虑 TTL 和 probe timeout；本轮已补入 timeout freshness 判定，避免 5 秒快速失败 cache 污染后续 20 秒正式嗅探。

### 6.3 推荐的下一步行动

1. 提供 Gitee remote 后，用 shared-knowledge 工具初始化并绑定独立仓库。
2. 单独立项执行历史人类报告层外移 dry-run，确认引用不破坏后再 apply。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-120 | Prism 可用性 cache 要同时记录时间新鲜度和探测强度 | TTL 只解决时间新鲜度，不解决短 timeout 造成的误判；cache freshness 要比较 probe timeout |
| L-121 | File Lookup Dictionary 必须有 coverage policy | 人类索引文档如果没有 policy/check，会再次退化成一次性维护 |
| L-122 | 公共知识库要先建立写入边界，再谈历史资产搬迁 | append-only、用户隔离、索引优先、去重先成立，再做远端绑定和历史迁移 |

### 7.2 流程改进建议

后续涉及新增关键脚本或 registry 时，开发者必须同步更新 `file-lookup-dictionary-policy.json`，让字典更新成为 spec/diagnose 的一部分，而不是报告里的“记得做”。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| EVO-2026-04-26-003 | 用户要求 Prism 可用性与字典保障 | promoted | `references/execution-guarantees.json` |
| EVO-2026-04-26-004 | 用户要求公共知识库产品化 | promoted | `shared-knowledge/README.md` |

---

## 八、附录

### 附录 A：Commits

```text
待提交本轮最终变更
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| test / resource-limited | R0-R22 覆盖审查 | Kimi reviewer pass，无 blockers；其他 provider 不可用/冻结已记录 | `prism/runs/20260426-redcap-execution-layer-resource-limited/` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 关键架构：`references/redcap-system-layers.md`
- Prism 可用性：`prism/tools/prism-availability.sh`
- 字典保障：`references/file-lookup-dictionary-policy.json`
- 公共知识库：`references/shared-knowledge-policy.json`
