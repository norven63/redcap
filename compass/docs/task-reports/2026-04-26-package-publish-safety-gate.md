# 任务完成报告：RedCap 发布/打包前安全拦截保障

**报告日期**：2026-04-26  
**执行者**：Cap（Codex.app 主 Agent）  
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已新增发布/打包前安全 gate，并接入 execution guarantees、spec-check、diagnose、acceptance、CLI facade 和 File Lookup Dictionary。
- 详情：未来 npm / 独立 runtime / portable package 发布前，应把实际打包文件清单交给 `redcap-package-publish-safety-check.sh`；它会阻断 `.env`、宿主私密入口、本地 runtime evidence、Prism run 残留和 credential-like 内容。

### 0.2 上一步完成的是

- 上一步完成的是：上一轮 R0-R22 任务已经 closeout，receipt 覆盖提交 `7c57451`；本轮是其后的新增安全需求，不应复用上一轮 receipt 冒充完成。

### 0.3 下一步计划做的是

- 下一步计划做的是：提交本轮安全 gate，并由 closeout runtime 生成新的 receipt。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：新增需求进入 `.dev-task.md` → policy/checker → spec/diagnose/guarantee/acceptance 接线 → 文档与 lesson → 回归 → closeout receipt。
- 当前所在位置：实现与 targeted 回归已完成，处于提交和 closeout 前。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 1. 你当前的运行轨迹是不是超出了LayerB的工作流？或者说，是不是还没进入到LayerB？  
> 2. 为什么会没有完成就中途打断向我汇报？这个是不是又印证了第1点的观点？  
> 3. 追加需求：RedCap 正式 npm/独立 runtime 打包之前的时刻，务必做好安全审核与拦截，保证没有私密数据信息被打包发布、保证没有把本地安全信息泄漏。这条需要加入到100%保障体系。

### 1.2 流程判断

上一轮最终汇报后的追问发生在旧任务 closeout 之后。那一刻如果继续口头解释而不新建任务卡，就确实会游离在 Layer B 主链外。本轮已纠正：把追加需求写入新的 `.dev-task.md`，用承诺账本、执行保障和 closeout runtime 处理。

“中途汇报”的根因不是代码实现完成，而是用户追问上一轮边界时，我给了澄清答复。它本身不是实现收口，也不能算 completed。正确做法是：澄清以后如果出现新增需求，必须立刻重锚任务卡。

---

## 二、方案讨论

本轮有两个方案：一是写发布前人工提醒，二是做 repo-owned fail-closed gate。由于用户明确要求加入 100% 保障体系，采用第二个方案：用 policy 定义发布候选面、禁止路径和密钥模式，再把 checker 接入 spec-check、diagnose、acceptance、execution guarantees 与 CLI。

关键设计取舍是：默认检查“未来发布候选包面”，不是扫整个工作区。这样能避免本地 `.env` 和测试 fixture 让日常回归误炸，同时未来真实 package builder 仍必须把精确 file list 交给本 gate 审计。

## 三、落地结果

| 文件 | 变更摘要 |
|------|---------|
| `references/package-publish-safety-policy.json` | 新增发布安全策略：默认候选包、默认排除项、禁止路径、密钥模式、人工发布边界 |
| `compass/tools/redcap-package-publish-safety-check.py` / `.sh` | 新增 fail-closed checker，支持默认包面、显式路径和候选清单 |
| `references/execution-guarantees.json` / checker | 新增 `package-publish-safety-gate`，纳入 P0 执行保障 |
| `compass/tools/redcap-spec-check.sh` / `redcap-diagnose.sh` | 接入发布安全 gate |
| `compass/tools/redcap-multi-session-acceptance.sh` | 新增 targeted acceptance，覆盖安全通过、`.env` 阻断、密钥内容阻断 |
| `bin/redcap` | 新增 `publish-safety` CLI facade |
| `references/file-lookup-dictionary.md` / policy | 新增发布安全相关文件定位 |
| `README.md` / `CONTRIBUTING.core.md` / `lessons.md` | 补充发布前安全门和经验沉淀 |

### 2.1 设计边界

这不是日常全仓 secret scanner。全仓扫描会被本地 `.env`、测试 fixture 和 ignored runtime 误炸，导致诊断链不可用。正确边界是：**发布前审计实际候选包文件集合**。默认检查先覆盖当前未来包化的合理候选面；真正 npm/runtime builder 出现后，必须传入它生成的精确 file list。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| package publish safety gate | `redcap-package-publish-safety-check.sh` | 发布/打包前的安全闸门，检查“准备被打进包里的文件”是否带了秘密或本地证据 |
| candidate list | `--candidate-list <files>` | 真实构建器输出的打包文件清单；未来正式发布时必须优先检查这份清单 |
| default package surface | `references/package-publish-safety-policy.json` | 还没有正式构建器时，RedCap 先定义的一组合理默认候选包面 |
| denied path | policy 的 `deny_path_globs` | 不允许进入发布包的路径，例如 `.env`、宿主入口、runtime 证据、Prism runs |
| credential-like content | policy 的 `secret_patterns` | 看起来像 API key、token、webhook、private key 的内容；命中就 fail-closed |

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 正式发布目标 | 本轮不执行 npm/pip/brew 发布；真实 registry、包名、凭据和公开 metadata 仍需独立发布决策 | P1 |
| 2 | 真实 package builder | 未来若新增构建器，必须输出精确候选文件清单并调用 `redcap-package-publish-safety-check.sh` | P1 |

## 五、验证结果

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 发布安全默认包面 | `bash compass/tools/redcap-package-publish-safety-check.sh` | 通过 |
| 发布安全 targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh package-publish-safety-check` | 通过 |
| File Lookup Dictionary coverage | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过，required_paths=99 |
| Execution guarantees | `bash compass/tools/redcap-execution-guarantee-check.sh` | 通过 |
| Prism resource-limited review | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | resource-limited-pass |

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 待 closeout runtime 同步 |
| 棱镜验收 | resource-limited-pass；Kimi 单席复审通过，其他 provider 不可用/冻结/unsupported 写入 resource-limited evidence |
| closeout summary | 待提交后生成 |
| closeout receipt | 待提交后生成 |
| rescue audit（如有） | 暂无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，targeted acceptance + Kimi resource-limited Prism review |
| 已正式完成 | 否，待提交后由 closeout runtime 生成 receipt |

---

## 六、遗留问题与下一步

| 问题 | 说明 |
|------|------|
| 正式 npm 发布 | 本轮不执行真实发布；发布动作、包名、registry token 与远端权限仍需独立发布决策 |
| 未来 package builder | 一旦新增真实构建器，它必须输出精确候选文件清单并调用本 gate |

---

## 七、经验沉淀

新增 lesson：L-123《发布安全不能等到 npm publish 那一刻才靠人肉想起》。

### 7.3 Evolution Factory 候选处理

无新增候选：本轮不是把一个待判断的经验留在候选池里，而是把用户明确追加的 P0 安全红线直接落成 execution guarantee，并同步沉淀 L-123。

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 发布/打包前安全拦截 | 用户新增 P0 安全要求 | 直接晋升为 execution guarantee 与 lesson，无未处理 candidate | `references/execution-guarantees.json`、`compass/knowledge/lessons.md` |

---

## 八、附录

### 附录 A：Commits

```text
待提交本轮最终变更
```

### 附录 B：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| resource-limited | 发布安全 gate 是否存在 fail-open blocker | Kimi 先抓到 `spec-check -x` fail-open 风险；修复后复审通过，无 blockers | `prism/runs/20260426-package-publish-safety-resource-limited/` |
