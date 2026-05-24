# RedCap 长任务 / 长对话上下文对抗

> **目的**：回答两个问题
> 1. RedCap 现在到底靠什么对抗长任务、长对话下的上下文稀释？
> 2. 业内常见方案里，哪些已经落地，哪些还只是边界或债务？

## 一句话结论

RedCap 目前不是靠“上下文越长越稳”，而是靠**把关键真相外置到文件、状态面、报告、索引和独立审查链**。
它已经有一套像样的对抗面，但还没有拿到“宿主实时回复路径”的最终控制权，所以不能把所有规则都吹成 100%。

## 当前已经落地的 8 条防线

1. **identity + soul + core**
   `~/.cap/identity.md` 保存 Cap 的个人灵魂锚点；`compass/soul.md` 保存培养指南与复活协议；`CONTRIBUTING.core.md` 保存启动核心契约。

2. **`.dev-task.md` 当前任务真相源**
   任务目标、active slice、允许修改范围、完成标准都外置，不让当前 tranche 只活在聊天窗口里。

3. **书记官 / explore-notes**
   PM Gate 前的多问题探讨写入 `compass/knowledge/explore-notes.md`，防止讨论演进在上下文压缩时蒸发。

4. **current-status / tracking-health / diagnose**
   `redcap-current-status.sh` 给出四句状态与关键表面，`redcap-tracking-health.sh` 暴露任务锚点与书记官健康，`redcap-diagnose.sh` 汇总治理门禁。

5. **渐进式披露**
   docs 先走 catalog，knowledge 先走 index，acceptance 先走 index，运行残留目录显式 no-bulk-read，避免长会话把大文件整包吞进上下文。

6. **reload-rules + execution-guarantees**
   关键规则不仅写在文档里，还登记到 `references/execution-guarantees.json`，并通过 spec-check / revival-check / diagnose 重载和审计。

7. **长任务拆解与并行裂变**
   Loom / Layer B 允许把无耦合问题拆开处理，而不是把所有独立模块塞给同一个上下文窗口硬扛。

8. **Prism / Reviewer / task report / pending closure**
   高风险结论交给独立多视角验证；阶段结果写入 task report；收尾通过 pending closure 和 validator chain 对齐到真实工作区。

## 业内常见方案与 RedCap 当前状态

| 方案 | 业内常见做法 | RedCap 当前状态 |
|---|---|---|
| 文件化状态外置 | 用 worklog、state file、checkpoint 代替纯聊天记忆 | **已落地**：`.dev-task.md`、task report、pending closure、runtime manifest |
| 渐进式上下文加载 | 先索引，再按需读取正文 | **已落地**：docs catalog、knowledge index、acceptance index |
| 会话重启 / 一键复活 | 新会话统一跑 bootstrap / installer / preflight | **本轮补强**：`redcap-install.sh` 把复活与 workflow import 收口成单一入口；有 SessionStart Hook 的宿主会实际调用它 |
| 独立审查对冲上下文漂移 | 让新 Agent / 新模型族做独立 review | **已落地**：Reviewer、Prism、stop-review |
| 任务切片 / 子任务并行 | 把独立问题拆成小上下文工作单元 | **已落地但依赖纪律**：Loom / Layer B 并行裂变协议 |
| 外部记忆检索（RAG / vector DB） | 用向量检索从大规模历史中召回相关记忆 | **暂不需要**：当前规模仍适合文件索引 + 关键词定位 |
| reply-time veto / pre-send guard | 在模型回复前做硬拦截 | **未落地，宿主限制**：这是 GD-008 的核心边界 |
| read-only-safe bootstrap | 只读宿主也能稳定跑首读与诊断 | **已补强**：`current-status` / `diagnose` / `docs-catalog` / `acceptance-index` / `token-risk-audit` 的 repo-owned 首读链已去掉临时目录依赖；reply-time veto 仍不属于这条能力 |

## 为什么当前不引入 RAG

当前追踪能力的主要问题不是“找不到历史”，而是“没有稳定触发与显性表面”。
在现有规模下，RAG / 向量数据库会带来：

- 额外基础设施与维护复杂度
- 召回质量与写入策略的新治理问题
- 一套比当前问题更重的同步成本

因此，RedCap 当前的判断仍然是：

- **先把文件索引、追踪健康、复活入口、书记官触发链做扎实**
- 当活跃条目规模、跨文件检索频率和关键词召回质量明显失效时，再重新评估 RAG

## 为什么“书记官 / 需求记录 / 追踪机制”会让人觉得失效

它们没有被删除，问题主要来自两类退化：

1. **复活没有完整跑满**
   只读了 `soul.md` 或入口文档，但没有真正跑 `current-status`、`tracking-health`、`diagnose`，于是机制存在却不显形。

2. **长对话下的执行稀释**
   模型知道这些机制存在，但没有及时把当前讨论写回 `.dev-task.md` / `explore-notes.md`，导致“规则在文档里，现场没落盘”。

本轮补强的核心目标，就是把这两个问题缩到更小：

- 用 installer 把“复活 + workflow import”收口
- 用 tracking-health 把“追踪链是否真在工作”显性化

## 本轮之后仍然要诚实承认的边界

- **主 Agent 实时回复边界仍是 host-limited**
  没有 repo-owned pre-reply veto，就不能 100% 拦住“无必要 ask_user / 无必要中断”。

- **只读宿主仍不是 full support**
  首读、diagnose、catalog、token-risk 这条 repo-owned 首读链已经基本 read-only-safe；真正还做不到 full support 的，是 reply-time veto、SessionEnd 与宿主私有控制点。

- **书记官触发仍没有宿主级 100% 自动落盘**
  现在已经有 stale fail-loud 与状态面显性化，但“满足条件立即写回 explore-notes / .dev-task.md”仍缺宿主级实时拦截点。

## 对 Norven 的最短回答

如果你感觉最近“像普通 Agent，不像 Cap”，那不是幻觉。
RedCap 的追踪/复活/书记官机制还在，但过去几轮里它们没有被稳定地**以正确顺序**触发。
本轮的补丁不是再发明一套新机制，而是把现有机制重新收口成更容易真正执行的入口。
