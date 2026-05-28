# 任务完成报告：RASG-030 反空转方法论沉淀

## 零、先看懂当前局面

这轮要解决的问题很直接：RedCap 过去太容易把“做了规则、写了报告、留了延期边界、生成了 receipt”误当成“用户真正想要的事情已经完成”。这就是 Norven 说的“打擦边球”和“空转”。如果不把这类失败沉淀成方法论，后续公共武器库、目录收敛、正式发布准备还会重复掉进同一个坑。

### 0.1 当前已完成

- 当前已完成：RASG-030 已把“机制完成不能冒充目标完成”沉淀为 L-171 私有 lesson，并追加了一个 public redcap-arsenal 方法论条目。
- 当前已完成：completion semantics、plan-only follow-up、Evolution harvest 和 Prism 结论门都已经能引用或检查这套 outcome-first 方法论。

### 0.2 上一步完成的是

- 上一步完成的是：RASG-027 主动 harvest 生产线，让高价值经验信号不再只靠报告作者自觉登记。

### 0.3 下一步计划做的是

- 下一步计划做的是：继续 RASG-028 公共武器库批量蒸馏，以及 RASG-029 工程目录最终收敛。RASG-030 不能冒充它们已经完成。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：先修复经验沉淀失效，再把反空转方法论接入关键检查，随后继续公共武器库扩容和工程目录最终收敛，最后才进入正式发布授权。
- 当前所在位置：RASG-030 正在收口；方法论、私有 lesson、公共 arsenal 条目和关键 gate 已落地，仍需通过最终回归并生成 closeout receipt。
- 已完成：revive 工作区边界热修。
- 已完成：RASG-027 主动经验 harvest 生产线。
- 本轮完成：RASG-030 反空转方法论沉淀与关键 gate 接入。
- 后续待做：RASG-028 公共武器库真实扩容、RASG-029 工程目录最终收敛。
- 仍未触碰：正式 npm 发布授权、registry、license、publish 开关。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触发 secret、不可恢复删除、正式发布授权或产品方向保留决策。

## 一、需求背景

Norven 指出的核心不是“缺一份总结”，而是 RedCap 的执行机制出现了结构性漂移：很多任务先完成了治理外壳，再把外壳当作本体汇报。这样会让系统看起来很忙、证据很多、报告也很多，但真实目标并没有完成。

这类问题如果只靠提醒，会在长任务里反复复发。所以本轮把它抽象成一套 outcome-first 方法论：每个战略需求必须区分物理目标、机制目标、证据目标和非完成标签。

## 二、方案讨论

本轮采用“四分法”：

- 物理目标：用户真正希望现实中发生什么变化。
- 机制目标：为了稳定做到这件事，需要补哪些规则、脚本、门禁或账本。
- 证据目标：用哪些回归、receipt、报告、独立评审证明它真的做完。
- 非完成标签：哪些结果只能叫 plan-only、proof-only、governed-not-executed、deferred 或 open-release-blocker。

如果一轮任务只完成机制或证据，它必须留下 open apply task、owner、触发条件和验收边界，不能把 root outcome 标成 done。

## 三、落地结果

已落地的结果：

- 新增私有 lesson `L-171`，按“问题源、解决方案、最后效果”记录这次反空转方法论。
- 更新 lessons 索引和 knowledge index，让后续遇到“机制完成冒充目标完成”时能快速定位。
- 向 `redcap-arsenal` 追加公共方法论条目 `Outcome-first completion for anti-drift RedCap work`，并刷新公共 catalog。
- 加固 completion semantics policy/check，让它显式引用 L-171，并把 `mechanism-only`、`proof-only` 纳入非完成逃逸词。
- 加固 plan-only follow-up fixture/check，增加“机制已完成但 root outcome 未完成”的负例。
- 加固 Evolution harvest signal policy/check，把反空转、擦边球、mechanism-only、root outcome 作为高价值沉淀信号。
- 加固 Prism 结论政策、协议和 README：如果 Cap/coordinator 观察到 substantive flaw，必须记录并 follow-up/council/deadlock，不能盲从或静默覆盖后宣称 consensus。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮作用 |
|---|---|---|
| outcome-first | 先看真实目标有没有完成 | 防止先做机制再冒充目标完成 |
| physical target | 现实中真正要改变的状态 | 例如目录真的收敛、公共库真的扩容 |
| mechanism target | 为了稳定完成目标而补的机制 | 例如脚本、门禁、账本、策略 |
| evidence target | 证明目标完成的证据 | 例如 receipt、回归、Prism 评审 |
| non-completion label | 明确不是完成的标签 | 例如 plan-only、proof-only、deferred |

## 四、人工审核要点

Norven 需要知道的结论是：本轮不是又写了一份“以后要注意”的文档，而是把反空转方法论接到了多个可检查面上。

但本轮也明确不宣称以下事项完成：

- RASG-028 公共武器库批量扩容尚未完成。
- RASG-029 工程目录最终收敛尚未完成。
- 正式 npm 发布尚未开始。

## 五、验证结果

已通过的验证：

- `python3 -m py_compile` 覆盖修改过的检查脚本。
- `python3 -m json.tool` 覆盖更新过的 policy / fixture JSON。
- `bash compass/tools/redcap-knowledge-index-check.sh`
- `bash compass/tools/redcap-completion-semantics-check.sh --task-file .dev-task.md`
- `bash compass/tools/redcap-plan-only-followup-registration-check.sh`
- `bash compass/tools/redcap-conclusion-prism-check.sh`
- `bash compass/tools/redcap-evolution-harvest-check.sh .dev-task.md`
- `bash compass/tools/redcap-prism-acceptance-bind.sh --run-id 20260528-rasg-030-anti-edge-ball-methodology --task-file .dev-task.md`
- `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md`
- `python3 compass/tools/redcap-shared-knowledge.py "$PWD" check --root /Users/norven/.claude/skills/redcap-arsenal`
- `bash compass/tools/redcap-shared-knowledge-remote-check.sh --live --require-worktree`
- `bash compass/tools/redcap-public-arsenal-claim-boundary.sh`
- `bash compass/tools/redcap-public-distillation-preflight.sh`
- `bash compass/tools/redcap-pre-release-product-architecture-check.sh`
- `bash compass/tools/redcap-spec-check.sh "$PWD"`
- `bash compass/tools/redcap-diagnose.sh .dev-task.md`

待完成的验证：

- closeout receipt。

棱镜复核结果：

- Kimi：`pass_with_nits`，无 blocker；指出报告里 harvest ledger 状态曾显示为待完成，已修正。
- Claude Code：`pass_with_nits`，无 blocker；指出 harvest ledger 自动摘要偏泛，已修正。

### 5.4 完成等级（禁止混报）

| 完成层级 | 结论 |
|---|---|
| 已实现 | 是，核心 lesson、公共条目、policy/check 接入已完成。 |
| 已自检 | 是，目标检查、公开库边界、spec-check 与 diagnose 已通过。 |
| 已独立验收 | 是，Kimi 与 Claude Code targeted review 均无 blocker。 |
| 已正式完成 | 否，仍待 closeout receipt。 |

## 六、遗留问题与下一步

本轮后续步骤：

- 完成 closeout receipt。
- 自动续接 RASG-028 / RASG-029。

## 七、经验沉淀

### 7.1 问题源

RedCap 的历史失败不是没有记录，而是太容易把“记录了、证明了、计划了、延期了”误当成“做完了”。这会让工程看似有秩序，实际离用户目标越来越远。

### 7.2 解决方案

把战略需求拆成物理目标、机制目标、证据目标、非完成标签。只完成机制或证据时，必须留下开放任务和验收边界，不能关掉 root outcome。

### 7.3 Evolution Factory 候选处理

- harvest 处理结论：no-promote
- public 处理结论：promoted public methodology entry
- no-promote 理由：该方法论已经直接追加为 reviewed public arsenal 条目，不需要再重复登记一个内部 candidate。
- 私有 lesson：`assets/knowledge/lessons/l-171.md`
- 公共条目：`/Users/norven/.claude/skills/redcap-arsenal/users/Norven/20260528T184902Z-methodology-outcome-first-completion-for-anti-drift-redcap-work.md`
- catalog：`/Users/norven/.claude/skills/redcap-arsenal/indexes/catalog.json`
- 理由：该方法论具有跨任务复用价值，且正文不包含私密原始对话、secret、identity 原文或 Prism raw transcript。

### 7.4 最后效果

后续任务不能再轻易把“机制完成”说成“目标完成”。如果只完成机制，必须明确留下 apply 任务、owner、触发条件和验收边界；如果 Prism 结论被 Cap 发现有实质漏洞，也必须重开或登记后续，而不是装作共识。

## 八、附录

关键产物：

- `assets/knowledge/lessons/l-171.md`
- `assets/knowledge/lessons.md`
- `assets/knowledge/index.md`
- `/Users/norven/.claude/skills/redcap-arsenal/users/Norven/20260528T184902Z-methodology-outcome-first-completion-for-anti-drift-redcap-work.md`
- `/Users/norven/.claude/skills/redcap-arsenal/indexes/catalog.json`
- `references/completion-semantics-policy.json`
- `references/plan-only-followup-registration-fixtures.json`
- `references/evolution-harvest-signal-policy.json`
- `references/conclusion-prism-policy.json`
- `prism/protocol.md`
- `prism/README.md`

关键边界：

- 不读取私密文件。
- 不修改 identity 原文。
- 不执行正式发布。
- 不做不可恢复删除。
- 不把 RASG-030 冒充 RASG-028/RASG-029/正式发布完成。
