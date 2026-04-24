# RedCap 工作流全景图

> 面向 Norven 的人话版。它解释 RedCap 现在如何把“讨论、立项、计划、执行、评审、收尾、考古”串成一个 Agent 工程框架。

## 1. 先用一句话看懂

RedCap 不是一个“让 Agent 更努力”的提示词集合，而是一套把 Agent 工作外置成账本、状态、验收和收据的工程系统。

## 2. Layer A 和 Layer B 的区别

| 层 | 人话类比 | 适合场景 | 状态机形态 |
|---|---|---|---|
| Layer A | 一次项目流水线 | 构建一个用户项目，从需求到交付 | 单中心 FSM，主要由 `.workflow/state.yaml` 驱动 |
| Layer B | 持续作战指挥室 | RedCap 自身持续治理、修补、重构、考古 | 分布式 FSM，由任务卡、检查器、棱镜、receipt 等共同约束 |

Layer A 更像“做完一个项目”。Layer B 更像“维护一个会持续进化的 Agent 框架”。因此 Layer B 更复杂，也更接近 Norven 和 Cap 日常共事时真正需要的 Agent 工作模式。

## 3. Layer B 的状态主链

```mermaid
flowchart TD
  A["书记官/底稿层<br/>讨论还没锁定"] --> B["PM Gate<br/>把方向锁成正式任务"]
  B --> C["REANCHORED<br/>会话复活并认回任务"]
  C --> D["TASK_LOCKED<br/>任务边界和允许范围已锁定"]
  D --> E["PLANNING<br/>制定方案、切片、承诺和验证路径"]
  E --> F["PLANNING_REVIEW<br/>棱镜审核计划"]
  F --> G["EXECUTING<br/>实现、修改、验证"]
  G --> H["REVIEW_PENDING<br/>棱镜/独立评审验收结果"]
  H --> I["CLOSEOUT_PENDING<br/>承诺、报告、通知、收据收口"]
  I --> J["CLOSED<br/>正式完成"]
  D --> G
  F --> K["BLOCKED<br/>计划或验收失败"]
  G --> K
  H --> K
  I --> K
  K --> C
```

## 4. 书记官和任务账本的关系

| 名称 | 作用 | 是否 FSM 主链 |
|---|---|---|
| 书记官/底稿层 | 记录 PM Gate 前的讨论、分歧、选项和演进 | 不是主链，是上游喂料层 |
| canonical task ledger | 当前正式任务的法定账本，目前主要是 `.dev-task.md` | 是主链的任务真相源 |

书记官解决“讨论不要蒸发”。任务账本解决“正式任务到底是什么”。PM Gate 的作用，就是把底稿里已经对齐的内容翻译成任务账本。

## 5. 为什么要有 PLANNING 和 PLANNING_REVIEW

过去 plan 更像一个工件，容易出现“计划本身错了，但执行阶段才发现”的问题。复杂任务里，计划应当成为独立状态：

- `PLANNING`：Cap 制定方案、拆分切片、列承诺账本、定义验证路径。
- `PLANNING_REVIEW`：棱镜审核计划是否完整、必要、没有遗漏关键 gate。

这让 Norven 只负责战略方向，不再被迫审核每个执行细节。

## 6. 三表对账是什么

三表对账就是让三个视角互相校验：

| 视角 | 命令 | 看什么 |
|---|---|---|
| 收尾总控 | `./closeout-cap.sh status` | closeout runtime 自己认为任务是否完成 |
| 当前状态板 | `redcap-current-status.sh` | Norven 接盘时看到的全局状态 |
| 总体验血单 | `redcap-diagnose.sh` | 各检查器、证据、收尾链是否一致 |

如果三者说法打架，就说明 RedCap 自己内部出现了状态漂移。2026-04-24 抓到的 `sync-promises` 状态回退 bug，就是通过这个办法发现的。

## 7. 常见术语人话词典

| 术语 | 人话解释 |
|---|---|
| lifecycle | 一个任务从开始、计划、执行、评审到收尾的生命周期 |
| closeout | 正式收尾，不是“我说完了”，而是执行收尾程序 |
| receipt | 完工收据，证明任务真的闭环 |
| pending closure | 当前还没清掉的红线或 blocker |
| closure-ledger | 历史收尾日志，记录曾经怎么卡住、怎么清掉 |
| Prism acceptance | 棱镜验收，作者不能自证完成 |
| canonical task ledger | 当前任务的法定账本，主要是 `.dev-task.md` |
| runtime state | 机器运行时写出的状态，不靠聊天记忆保存 |

## 8. 老旧资产治理如何进入工作流

“老旧资产治理”本身会作为新的 Layer B 任务进入 FSM。治理对象包括旧报告、旧镜像、旧模板、旧说明和旧状态面。处理方式分四类：

| 处理方式 | 适用对象 |
|---|---|
| 保留 | 历史证据、receipt、pending closure、closure-ledger、Prism 证据 |
| 翻译 | 入口文档、模板、状态面、`.dev-task.md` 这类仍承担当前工作流角色的资产 |
| 降级/归档 | 只剩历史价值、容易误导成 authority 的旧摘要或镜像 |
| 删除 | 已有新权威面替代且不会破坏考古能力的冗余文件 |

原则是边运行边迁移：先标注权威关系，再迁移高风险资产，最后才考虑删除。

## 9. 这套系统现在仍未解决什么

最大边界仍是 `GD-008`：Codex.app 这类宿主还没有公开的 repo-owned `pre-reply` / `final-reply veto`。RedCap 可以把“完成判定”从口头回复中拿走，但还不能在回复生成前 100% 拦住不该说的话。
