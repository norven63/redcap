# 任务完成报告：Runtime / CLI / Package Readiness

**报告日期**：2026-04-26
**执行者**：Cap（Codex.app 主执行，Codex CLI + Kimi Prism reviewers）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P2-1 已建立 RedCap runtime / CLI / package readiness 层，但没有执行真实公网发布。
- 详情：新增 `package.json`、`.npmignore`、`references/runtime-package-readiness-policy.json` 和 `redcap-runtime-package-manifest`，由机器策略生成精确候选清单，再把候选清单交给 package safety gate 检查。

### 0.2 上一步完成的是

- 上一步完成的是：P2-2 父任务 receipt 聚合 gate 已 closeout，明确父任务不能由子任务 receipt 冒充完成。
- 详情：P2-1 接在该 gate 后推进产品化 readiness，同时继续禁止把父任务整体标记为 complete。

### 0.3 下一步计划做的是

- 下一步计划做的是：P1-3 shared-knowledge 远端绑定仍需外部仓库与权限；P2-3 formal Prism quorum 仍需单独复验 provider 健康；真实 npm/Gitee/GitHub 发布仍需独立 release 任务。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P1 dry-run 边界 → P2-1 package readiness → P2-2 父任务聚合 gate → 外部绑定/发布/Prism quorum 后续收口。
- 当前所在位置：RedCap 有可审计 package readiness，但仍不是已公开发布的 npm package。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 继续

### 1.2 触发背景

父任务账本中 P2-1 仍为 open：RedCap 已有 `bin/redcap` 薄 facade 和发布前安全 gate，但尚未把 package 形态、候选清单生成、真实包面安全检查串成可审计 readiness。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 推进正式 runtime / CLI / package 发布设计与实现。 |
| 已覆盖 | package metadata、package readiness policy、candidate list generator、CLI facade、package safety gate、npm dry-run sanity check、acceptance、spec/diagnose 接线、lesson。 |
| 未覆盖/延期 | 不执行真实公网发布，不绑定 registry token，不抢占包名，不移动全部 runtime 目录。 |
| 用户可见边界 | P2-1 完成只代表“可审计 package readiness”，不代表 `npm publish` 或跨机器分发已完成。 |

---

## 二、方案讨论

### 2.1 决策

| Q | 采纳方案 | 决策理由 |
|---|---|---|
| package 形态 | npm/package-style readiness，`private: true` | npm 是最贴近 CLI 分发的下一步，但 `private: true` 阻止误发。 |
| 候选文件来源 | 机器 policy 生成精确 candidate list | 避免只靠默认 glob 或人工记忆判断包面。 |
| 发布安全 | candidate list 必须进入 package safety gate | 复用既有 P0 安全门，审计真实准备打包的文件集合。 |
| 真实发布 | 延期到单独 release 任务 | 包名、registry、token、公开 metadata 都是外部/人工决策。 |

### 2.2 关键边界

`npm pack --dry-run` 曾显示宽泛 `package.json.files` 会把 `redcap-multi-session-acceptance.sh` 带入真实包面；本轮已用 `!compass/tools/redcap-multi-session-acceptance.sh` 显式排除，并把这个规则写进 manifest checker。最终版本还增加了 `--npm-pack-dry-run`，可把生成的 candidate list 与真实 npm packlist 做差异对账。

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `package.json` | 新建 | npm package metadata，`private: true`，`bin.redcap=bin/redcap`，files whitelist 显式排除 acceptance 巨型套件。 |
| `.npmignore` | 新建 | deny `.env`、宿主私密入口、本地 runtime evidence、Prism runs 和缓存文件。 |
| `references/runtime-package-readiness-policy.json` | 新建 | package readiness 单一机器策略，定义候选 glob、required files、人工发布边界。 |
| `compass/tools/redcap-runtime-package-manifest.py/.sh` | 新建 | 生成候选清单、验证 package metadata、调用 package safety gate。 |
| `bin/redcap` | 修改 | 新增 `package-manifest` CLI 子命令。 |
| `references/package-publish-safety-policy.json` | 修改 | 默认包面加入 package metadata、root runtime facades。 |
| `compass/tools/redcap-spec-check.sh` / `redcap-diagnose.sh` | 修改 | 接入 runtime package manifest gate。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增 `runtime-package-manifest-check` acceptance。 |
| `references/file-lookup-dictionary*` | 修改 | 新增 package readiness 文件索引。 |
| `references/execution-guarantees.json` / checker | 修改 | 新增 `runtime-package-readiness-gate`。 |
| `references/parent-receipt-aggregation-policy.json` / checker | 修改 | 将 P2-1 从 not-complete 边界移动到 completed children，父任务仍因 P1-3/P2-3 不可 complete。 |
| `README.md` / `compass/knowledge/lessons.md` | 修改 | 说明 package readiness 用法并沉淀 L-130。 |

### 3.2 技术实现要点

`redcap-runtime-package-manifest.sh --check` 会执行三步：校验 `publish_allowed=false` 与 `package.json.private=true`，展开 policy 候选文件清单并检查必需文件，再把生成清单交给 `redcap-package-publish-safety-check.sh --candidate-list`。在有 npm 的环境中可加 `--npm-pack-dry-run`，确保候选清单和真实 npm pack 输出一致。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| package readiness | `references/runtime-package-readiness-policy.json` | 已具备可审计打包准备，不等于已经发布。 |
| candidate list | `redcap-runtime-package-manifest.sh --output` | 准备进入包面的精确文件清单。 |
| package safety gate | `redcap-package-publish-safety-check.sh` | 检查候选文件是否含本地秘密、runtime evidence 或禁止路径。 |
| `private: true` | `package.json` | 防止误执行真实 npm publish。 |

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 真实发布决策 | 包名、registry、token、公开 metadata、release notes 仍需另立 release 任务。 | P1 |
| 2 | 跨机器安装验证 | 本轮是 package readiness；真实跨机器安装和宿主 hook 部署仍需后续 E2E。 | P2 |

---

## 五、验证结果

| 验证项 | 命令 | 结果 |
|--------|------|------|
| runtime manifest | `bash compass/tools/redcap-runtime-package-manifest.sh --check` | 通过，candidate_count=150 |
| package safety on candidate list | `bash compass/tools/redcap-package-publish-safety-check.sh --candidate-list /tmp/redcap-runtime-candidates.txt` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh runtime-package-manifest-check` | 通过 |
| package safety acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh package-publish-safety-check` | 通过 |
| dictionary / guarantees | `redcap-file-lookup-dictionary-check.sh`、`redcap-execution-guarantee-check.sh` | 通过 |
| npm dry-run sanity | `npm pack --dry-run --json` 后检查禁止项 | 通过，未包含 acceptance 巨型套件、`.env`、宿主私密入口、`prism/runs` |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过，Codex CLI + Kimi，2 families |
| spec-check / diagnose | 待最终回归 | 待执行 |

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 待 closeout runtime 同步 |
| 棱镜验收 | `20260426-runtime-cli-package-readiness-review` pass（Codex CLI + Kimi，2 families） |
| closeout summary | 待提交后生成 |
| closeout receipt | 待提交后生成 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Codex CLI + Kimi 双 reviewer 通过 |
| 已正式完成 | 否，待提交后 closeout runtime receipt |

---

## 六、遗留问题与下一步

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 真实 public release | 需要人工决定 registry、包名、token、公开 metadata。 | P1 |
| 跨机器安装 E2E | 需要另开 throwaway install / host adapter E2E。 | P2 |
| P1-3 shared-knowledge 远端绑定 | 需要外部仓库与权限。 | P1 |
| P2-3 formal Prism quorum 恢复复验 | availability 层仍需单独复验 provider 稳定性。 | P2 |

---

## 七、经验沉淀

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-130 | package readiness 要核对“声明的候选清单”和“真实打包面” | candidate list、安全 gate 和 `npm pack --dry-run` 的真实包面不能分叉。 |

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | 本轮实现与回归 | no-promote；已沉淀为 L-130，不新增 Evolution candidate | `compass/knowledge/lessons.md` |

---

## 八、附录

### 附录 A：Commits

```text
本报告随 P2-1 实现提交一起进入 git；closeout receipt 将记录最终 HEAD。
```

### 附录 B：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| reviewer / openai | package readiness 是否存在安全/包面 blocker | Codex CLI reviewer pass；建议保留 npm pack dry-run release 检查 | `prism/runs/20260426-runtime-cli-package-readiness-review/collect/reviewer/parsed.json` |
| reviewer / moonshot | package readiness 是否存在安全/包面 blocker | Kimi reviewer pass；确认 publish-disabled、安全 gate、packlist 对账、symlink CLI 均满足 | `prism/runs/20260426-runtime-cli-package-readiness-review/collect/kimi_review/parsed.json` |
