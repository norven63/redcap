# 2026-04-22 首读链 / 书记官 / 生命周期 / Hook 硬化

## 0.1 当前已完成

- 已把 `current-status`、`tracking-health`、`docs-catalog`、`acceptance-index`、`token-risk-audit`、`prism-runs-lifecycle` 的关键控制面从 shell heredoc/临时文件迁移到独立 Python 载体，收口到更稳定的只读首读链。
- 已新增 `commit-msg` 机器门禁，强制校验中文主语、简短 why 正文与 `作者:redcap` 尾标；`redcap-on-qa-pass.sh` 也已同步生成合规 commit body。
- 已清掉 `explore-notes` 的历史假阳性活跃条目，并把书记官健康升级为 stale fail-loud；当前 `explore_notes=active:0 archived:9`。
- 已把 installer 实际接入 `redcap-layerB-session-start.sh`，让有 SessionStart Hook 的宿主在启动时真实运行安装/复活入口。
- 已为 `prism/runs` 增加 `inventory / prune-local` 生命周期能力，并实际清理 16 个超过保留阈值的本地命名证据残留；当前仅保留 `.locks`、1 个 formal run、1 个 active named-local-evidence。
- 已同步 README、`CONTRIBUTING.core`、`long-task-context-defense`、`host-reliability`、`prism/protocol`、`execution-guarantees` 与治理债务口径，使实现与说明重新一致。

## 0.2 上一步完成的是

- 上一轮已完成 identity/soul 分层、安装即复活入口、追踪健康显性化与长任务上下文对抗知识沉淀，并将这些入口接到宿主文档、diagnose、acceptance 与 docs catalog。

## 0.3 下一步计划做的是

- 当前无本轮任务级 blocker。若继续推进，只剩 `GD-008` 这类宿主 reply-path 边界问题需要在 host-limited 前提下继续治理，不能伪装成 repo 内可彻底闭环。

## 0.4 整体计划脉络图与当前位置

- 路线：安装即复活 → 追踪健康显性化 → 长任务对抗沉淀 → 首读链 read-only-safe 化 → 书记官 stale gate → Prism 运行残留生命周期 → commit 机器门禁 → Hook 入口接线与文档收口。
- 当前位置：本轮治理 tranche 已收口，repo-owned todo 已清到只剩宿主边界债务。

## 1. 本轮目标

这轮的目标不是再发明一套新机制，而是把前几轮已经识别出来却还停留在“口头约束 / 债务登记 / 假设可行”的事项，真正落到脚本、状态面和生命周期控制里：

- `GD-009`：首读/诊断链不再依赖临时可写目录才能运行
- 书记官：旧条目归档口径统一，活跃条目不能长期假阳性
- `prism/runs`：命名本地证据不再无限堆积
- commit 规范：从文档规则升级成机器门禁
- SessionStart：installer 不再只是文档入口，而是真进入 Hook 启动链

## 2. 关键改动

### 2.1 首读链 read-only-safe 化

- 新增 Python 入口：
  - `compass/tools/redcap-current-status.py`
  - `compass/tools/redcap-docs-catalog.py`
  - `compass/tools/redcap-tracking-health.py`
  - `compass/tools/redcap-acceptance-index.py`
  - `compass/tools/redcap-token-risk-audit.py`
  - `prism/tools/prism-runs-lifecycle.py`
- 对应 shell wrapper 现在只负责参数解析与宿主适配，不再内嵌大段 Python heredoc 或依赖 `mktemp` 生成中间文件。
- `current-status` 额外增加了对 `prism/runs` 本地保留阈值的摘要输出。

### 2.2 书记官 stale gate 与旧账清理

- `compass/knowledge/explore-notes.md` 的旧条目统一补成 `[ARCHIVED]` 口径。
- `redcap-tracking-health.py` 现在会把超过阈值的活跃 explore-notes 条目标成 stale，并返回非零退出码。
- `redcap-explore-notes-check.sh` 的归档识别从精确匹配 `[ARCHIVED]` 改成兼容 `[ARCHIVED ...]` 变体，避免继续出现“正文已归档但检查仍算活跃”的假阳性。

### 2.3 `prism/runs` 生命周期与物理清理

- `prism-runs-lifecycle` 现在支持：
  - `summary`
  - `inventory`
  - `prune-acceptance`
  - `prune-local`
- 新规则把 `named-local-evidence` 从“默认永久保留”改成“超过保留期后进入审查清理候选”。
- 本轮实际执行：
  - `prism/tools/prism-runs-lifecycle.sh prune-local --apply`
  - 清理 16 个超期本地命名证据目录

### 2.4 commit 规范机器门禁

- 新增：
  - `.githooks/commit-msg`
  - `compass/tools/redcap-commit-message-check.py`
- `redcap-ensure-git-hooks.sh` 现在要求 `pre-commit + commit-msg` 同时存在。
- `references/commit-standards.md` 也同步收紧为：
  - 正文必填
  - 必须说明 why
  - 必须以 `作者:redcap` 收尾

### 2.5 SessionStart 真接 installer

- `redcap-layerB-session-start.sh` 新增 `run_install_revival_entry()`。
- 对支持 SessionStart 的宿主，installer 会在启动链中真实执行，并把概要写入 runtime state。
- 安装失败时会记录 degraded mode，而不是静默跳过。

## 3. 验证

本轮已实际验证：

- `bash compass/tools/redcap-tracking-health.sh .dev-task.md`
- `bash compass/tools/redcap-acceptance-index.sh check`
- `bash compass/tools/redcap-token-risk-audit.sh`
- `bash prism/tools/prism-runs-lifecycle.sh summary`
- `bash prism/tools/prism-runs-lifecycle.sh inventory`
- `bash prism/tools/prism-runs-lifecycle.sh prune-local`
- `bash compass/tools/redcap-current-status.sh .dev-task.md`
- `bash compass/tools/redcap-docs-catalog.sh summary`
- `bash compass/tools/redcap-execution-guarantee-check.sh`
- `bash compass/tools/redcap-revival-check.sh "$PWD"`
- `bash compass/tools/redcap-ensure-git-hooks.sh "$PWD"`

## 4. 剩余边界

- `GD-008` 仍在：主 Agent 的 reply-time veto / pre-send guard 依旧取决于宿主是否暴露控制点，repo 内无法诚实宣称 100% 物理拦截。
- 本轮没有把 `main agent 行为边界` 伪装成已自动化；做的只是把它继续保持为 host-limited，并把 repo-owned 首读链尽量做实。

## 5. 收口结论

这轮不是单点修 bug，而是把几条反复被提到的治理短板真正落地：

- 首读链更轻、更稳、更不依赖临时目录
- 书记官不再被历史假阳性污染
- `prism/runs` 不再默认无限堆积
- commit 规则终于有了真门禁
- installer 真进入了宿主启动链

到这一版为止，本轮能在 RedCap repo 内真正补平的 todo 已收口完成；剩下的是宿主边界，而不是仓库内继续打补丁就能假装解决的事。
