# 任务完成报告：P4-2d public package identity/license/surface 准备

**报告日期**：2026-05-05
**执行者**：Cap（Codex.app + Prism: Kimi / Claude Code）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 的未来公共 npm 包身份已准备为 `@norven63/redcap`，但仍保持私有、不可发布、许可证待人工决策的安全姿态。
- 详情：本轮解决的是“包名和包面已经开始公共化，但不能把准备态冒充成发布态”的问题。现在 package metadata、runtime readiness policy、发布前产品审判和机器检查都统一到 `@norven63/redcap`；同时 `private=true`、`publish_allowed=false`、`license=UNLICENSED` 继续锁住真实发布边界。新增的 package surface gate 会检查候选包面、禁入路径和人工 release 边界，防止把私有证据、运行时残留或未授权发布动作混进未来 npm 包。

### 0.2 上一步完成的是

- 上一步完成的是：P4-2c 已补齐 public CLI 的 `doctor`、`debug --json`、`--trace`、help 和结构化错误产品面。
- 详情：P4-2c 让外部用户和 Agent 容器可以排障；P4-2d 则接着处理“这个 CLI 将来以什么 npm 包身份出现、哪些内容可以进入包、哪些发布动作必须继续锁住”。

### 0.3 下一步计划做的是

- 下一步计划做的是：推进 P4-2e public redcap-arsenal 内容策略与 claim 边界，决定公共 arsenal 仍是 template-only 时如何诚实描述，或是否补充实质内容后再宣传。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-2a 产品架构审判 -> P4-2b 边界拆分 -> P4-2c CLI 诊断产品面 -> P4-2d 包身份/许可证/包面准备 -> P4-2e 公共 arsenal 口径 -> P4-2 正式发布任务。
- 当前所在位置：P4-2d 已完成 readiness 准备；P4-2 正式发布仍未完成，也不能声明 public-release-ready。

### 0.5 是否需要 Norven 人工介入

- 人工介入：当前不需要。
- 说明：本轮没有执行 `npm publish`，也没有替 Norven 选择许可证；这些都被保留为未来正式 release task 的人工决策点。Cap 可以继续推进 P4-2e 或其他父任务线，直到真正进入发布授权、许可证选择、registry 凭据操作时才需要 Norven 介入。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，那么请你和棱镜团队继续稳步推进下面的任务，可以吗？还是说，你有更加建议的事情要做？

> 另外，RedCap的“overlay 治理”可以做到干扰宿主skill的权限？控制skill不允许被加载后越权？这个权限有点太大了吧？

### 1.2 触发背景

P4-2a 的发布前产品审判指出：RedCap 还不能被当作成熟 public npm CLI/runtime 发布。P4-2b 和 P4-2c 已分别处理 workspace 边界和 CLI 诊断产品面，本轮自然接到 P4-2d：把包名、包面、许可证姿态和发布边界从“口头解释”推进到机器可审计的准备态。

用户同时追问 overlay 治理是否会控制宿主 skill 权限。这个问题必须在本轮澄清，因为 RedCap 不能把自身控制面夸大成宿主级安全沙箱。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 继续推进 RedCap public CLI/npm release 前主线，并解释 overlay 治理不是宿主级权限夺取。 |
| 已覆盖 | 已完成 `@norven63/redcap` package identity、manual license posture、public package surface gate、pre-release review 更新、Prism 审查、targeted 回归和 closeout 准备。 |
| 未覆盖/延期 | 真实 npm publish、`private=false`、`publish_allowed=true`、最终许可证选择、registry token/npm ownership 操作、P4-2e public arsenal 内容策略。 |
| 用户可见边界 | 可以声明“公共包身份和包面 readiness 已准备”；不能声明“RedCap 已 npm 发布、已选定开源许可证、已 public-release-ready”。 |
| 后续路径 | P4-2e 继续处理 public redcap-arsenal 的内容口径；正式发布必须另开 release task 并由 Norven 确认许可证和发布凭据。 |

---

## 二、方案讨论

### 2.1 问题分析

本轮最容易犯的错，是把“确定未来包名”误当成“可以发布”。npm 包源码对用户可见，所以安全不能依赖混淆或“别人看不到源码”；必须靠明确的包面白名单、禁入路径、安全扫描和人工发布边界。

overlay 治理的边界也必须讲清：RedCap 只能规定 RedCap-native 工作流里的权威顺序。宿主是否加载某个 skill、某个 app 是否有权限、某个 skill 能否被隐藏或禁止，属于宿主能力；RedCap 不能物理干预，也不应该冒充自己有这种权限。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| P4-2d 包身份 | 只记录候选包名，不改 package metadata | 把 `@norven63/redcap` 作为候选字段保存 | 风险最低 | package metadata 继续漂移，未来检查仍看到旧包名 |
| P4-2d 包身份 | 切到 `@norven63/redcap`，但锁住发布 | 同步 package.json 和 readiness policy，保持 `private=true` / `publish_allowed=false` | 身份准备真实推进，同时不越权发布 | 需要新增机器门禁防误报 |
| license | Cap 直接选择 MIT/Apache 等许可证 | 让发布前 blocker 立即减少 | 表面推进快 | 越权替用户做法律/产品决策 |
| license | 保持 `UNLICENSED`，显性记录人工决策边界 | 只完成准备态，不冒充最终许可证 | 诚实、安全 | 正式发布仍需未来人工确认 |
| overlay | 试图控制宿主 skill 加载权限 | 把 RedCap 当宿主权限层 | 看似强控制 | 技术上不成立，也会越权 |
| overlay | 只定义 RedCap 主流程权威边界 | 外部 skill 产物只能作为建议，不得覆盖任务账本/门禁/receipt | 真实可执行，边界清楚 | 在无 hook 宿主里仍是 host-limited |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| 包身份 | 切到 `@norven63/redcap`，但锁住发布 | 用户此前已确认包名；本轮只准备身份和包面，不执行发布动作。 | Norven 已确认包名；Cap + Prism 执行边界 |
| license | 保持 `UNLICENSED` 并显性记录 manual-before-public-publish | 许可证是法律/产品决策，不能由 Cap 默认选择。 | Cap + Prism |
| 包面 | 新增 public package surface gate | 让候选包面、禁入路径、真实检查命令和 release 边界进入机器审计。 | Cap + Prism |
| overlay | advisory-only 权威边界 | RedCap 不能控制宿主 skill 权限；只能规定 RedCap 工作流不被外部 skill 反向接管。 | Cap |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `package.json` | 修改 | 包名准备为 `@norven63/redcap`，继续保持 `private=true` 与 `license=UNLICENSED`。 |
| `references/runtime-package-readiness-policy.json` | 修改 | readiness policy 同步包名、license 状态和 public package surface policy 依赖。 |
| `references/public-package-surface-policy.json` | 新建 | 固化准备态、禁入路径、候选包面上限、真实检查命令和人工 release 边界。 |
| `compass/tools/redcap-public-package-surface.py` / `.sh` | 新建 | 验证 package metadata、readiness policy、npm pack 候选包面和安全边界。 |
| `bin/redcap` / `redcap-cli-product-surface.py` | 修改 | 新增 `redcap package-surface` 入口，方便 CLI 侧调用同一门禁。 |
| `redcap-diagnose.sh` / `redcap-spec-check.sh` / `redcap-multi-session-acceptance.sh` | 修改 | 把 public package surface gate 接入诊断、总门禁和 acceptance。 |
| `references/pre-release-product-architecture-review.json` | 修改 | 将 package identity 从 blocker 改为 pass，同时保留 publish/license/runtime 等剩余 release blocker。 |
| `references/pre-release-structure-refactor-task-tree.json` / `references/redcap-parent-task-ledger.md` | 修改 | 将 P4-2d 从进行中推进为 completed readiness，下一步转向 P4-2e。 |
| `references/execution-guarantees.json` / `references/file-lookup-dictionary.md` | 修改 | 把新门禁纳入执行保障和文件查找字典。 |
| `compass/knowledge/lessons.md` | 修改 | 新增 L-154，沉淀“公共包准备态不能冒充真实发布”。 |

### 3.2 技术实现要点

本轮采用“准备态”和“发布态”分层：包名已经准备，但发布开关继续锁住。这样将来所有工具都能看到真实 public identity，同时机器门禁会阻止任何人把它误读成已经可以公开发布。

public package surface gate 会同时读取 policy、`package.json`、runtime readiness policy 和 `npm pack --dry-run` 结果。它不只看“能不能打包”，还会检查禁入路径、候选文件数量、真实检查命令是否存在，以及 manual release boundary 是否仍包含 `private=false`、`publish_allowed=true`、license、`npm publish` 和 public-release-ready 这些红线。

棱镜给出的两条路线中，本轮选择了更保守的 route B：先准备 identity 和 surface，不替用户选 license。这样 P4-2d 可以完成 readiness 准备，而正式 release task 仍必须由 Norven 决定许可证、registry 凭据和是否真正发布。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| public package identity | `package.json.name` / runtime readiness policy | RedCap 将来作为 npm 包出现时使用的名字，本轮准备为 `@norven63/redcap`。 |
| readiness-only | `references/runtime-package-readiness-policy.json` | 只能证明“发布前准备和检查可跑”，不能代表已经允许发布。 |
| public package surface | `npm pack --dry-run` 候选文件集合 | 将来 npm 包里可能被用户看到的文件清单。源码可见，所以必须检查私密内容和运行时残留。 |
| manual license boundary | `license_status: manual-before-public-publish` | 许可证选择保留给 Norven，不由 Cap 默认决定。 |
| overlay governance | `overlay_skill_policy: advisory_only` | 外部 skill 可以提供建议，但不能覆盖 RedCap 的任务卡、门禁、receipt 和 closeout 结论。 |

### 3.3 关联变更

pre-release product architecture review 现在区分三个事实：包名已经准备；发布仍被 `private=true` / `publish_allowed=false` 锁住；许可证仍是未来 release task 的人工决策。这让 P4-2d 可以关闭“包名漂移”问题，同时不会把剩余 release blocker 抹掉。

任务树和父账本也同步推进：P4-2d 是 completed readiness，不是 public release completed。下一主线建议转到 P4-2e，而正式 P4-2 发布仍保持 blocked。

---

## 四、人工审核要点

当前没有需要 Norven 立即完成的人工动作。

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 未来许可证选择 | 只有正式 release task 才需要选择 MIT / Apache-2.0 / 其他许可证；本轮不需要现在决定。 | P0-before-public-release |
| 2 | 未来 npm publish 授权 | `private=false`、`publish_allowed=true`、registry token 和 `npm publish` 必须留到独立发布任务。 | P0-before-public-release |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 语法检查 | `bash -n compass/tools/redcap-public-package-surface.sh compass/tools/redcap-multi-session-acceptance.sh && python3 -m py_compile compass/tools/redcap-public-package-surface.py` | ✅ |
| public package surface | `bash compass/tools/redcap-public-package-surface.sh` | ✅ |
| acceptance：package surface | `bash compass/tools/redcap-multi-session-acceptance.sh public-package-surface-check` | ✅ |
| acceptance：runtime manifest | `bash compass/tools/redcap-multi-session-acceptance.sh runtime-package-manifest-check` | ✅ |
| acceptance：发布前审判 | `bash compass/tools/redcap-multi-session-acceptance.sh pre-release-product-architecture-check` | ✅ |
| acceptance：spec 传播 | `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures` | ✅ |
| 发布前产品审判 | `bash compass/tools/redcap-pre-release-product-architecture-check.sh` | ✅ |
| 结构任务树 | `bash compass/tools/redcap-pre-release-structure-task-tree-check.sh` | ✅ |
| 执行保障 / 文件字典 | `bash compass/tools/redcap-execution-guarantee-check.sh && bash compass/tools/redcap-file-lookup-dictionary-check.sh` | ✅ |
| Prism 证据 | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | ✅ |
| clean workspace E2E | `bash compass/tools/redcap-clean-workspace-e2e.sh --write-result && --check-result` | 待实现提交后刷新 |
| full acceptance / umbrella spec | `bash compass/tools/redcap-multi-session-acceptance.sh all` / `bash compass/tools/redcap-spec-check.sh "$PWD"` | 待 clean E2E 刷新后执行 |

### 5.2 人工验证项（Cap 无法自动化验证的）

当前没有 P4-2d 必须依赖 Norven 立即手动完成的验证项。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 待 closeout runtime 核对 |
| 棱镜验收 | Kimi + Claude Code 双路通过，binding 已生成 |
| closeout summary | 待 closeout runtime 生成 |
| closeout receipt | 待 closeout runtime 生成 |
| rescue audit（如有） | 当前无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是；Prism acceptance 已通过 |
| 已正式完成 | 否；仍待 clean E2E 刷新、full gate 和 closeout receipt |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 最终 public license | 许可证是法律/产品决策，不能由 Cap 默认选择。 | P0-before-public-release |
| 真实 npm publish | 当前仍是 readiness-only，不执行 registry 状态变更。 | P0-before-public-release |
| P4-2e public arsenal 内容策略 | 属于下一主线，用来解决公共 arsenal 仍 template-only 时的产品口径。 | P1-before-broad-marketing |
| 更薄的 public product package | 当前 215 个候选文件通过安全门，但未来可继续评估更瘦的产品化包面。 | P1-before-broad-marketing |

### 6.2 触发的新问题

本轮发现并修复了一个策略引用漂移：public package surface policy 一度写成不存在的 `redcap-public-package-surface-check.sh`。已把 checker 加固为会验证 `required_runtime_checks` 必须对应真实脚本，acceptance 也加入了坏策略回归。

### 6.3 推荐的下一步行动

1. 刷新 clean workspace E2E durable result，并跑 full acceptance / umbrella spec。
2. 进入 P4-2e：公共 arsenal 内容策略与 claim 边界。
3. 在正式发布任务前，再由 Norven 决定许可证、npm registry 凭据和是否允许真实 publish。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-154 | 公共包准备态不能冒充真实发布 | 包名、包面 readiness 可以机器化推进，但许可证、publish 开关和 registry 状态必须保留为独立 release 决策。 |

### 7.2 流程改进建议

策略文件里列出的检查命令必须被机器验证为真实存在；否则“策略写了要检查”会变成纸面保障。本轮已把这个要求纳入 public package surface checker 和 acceptance。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | 本轮是既有 release blocker remediation | no-promote；经验沉淀到 L-154，不新增 Evolution candidate | `compass/knowledge/lessons.md` |

---

## 八、附录

### 附录 A：Commits

```
待提交
```

### 附录 B：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| Kimi product review | P4-2d 包身份/许可证/包面策略 | conditional-pass；建议保持发布和许可证人工边界 | `prism/runs/20260505-public-package-identity-surface-review/artifacts/kimi-package-strategy-raw.md` |
| Claude Code architecture review | P4-2d 最小安全补丁 | conditional-pass；建议 route B：只准备 identity/surface，不碰 license/publish | `prism/runs/20260505-public-package-identity-surface-review/artifacts/claude-package-architecture-raw.md` |
