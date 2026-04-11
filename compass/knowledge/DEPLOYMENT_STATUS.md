# RedCap Hook 部署现状矩阵

> **单一来源**：本文件记录各宿主 Agent 工具对 RedCap 红线 hook 节点的实际部署状态。
> **更新时机**：每次新增或变更 hook 部署后，必须同步更新本文件。
> **数据来源**：Q3 分析结论（2026-04）+ `compass/knowledge/host-reliability.md` + 各 `hooks-*.md` 详情文件。
> **架构里程碑**：2026-05 三体重组 — 脚本迁移到 `loom/tools/`（Layer A）和 `compass/tools/`（Layer B），hook 注册路径同步更新。

---

## Layer A — RedCap 开发用户项目

> 部署位置：**用户级**配置文件（`~/.claude/settings.json`、`~/.kimi/config.toml` 等）

| 红线节点 | 保障机制 | Claude Code | Kimi CLI | Gemini CLI | VS Code Copilot | Copilot CLI |
|----------|----------|------------|---------|-----------|----------------|------------|
| `on_ALL_DONE`（清理 + 飞书通知） | Stop Hook + 四重过滤 | ✅ 已部署 | ✅ 已部署 | ⏳ 未部署 | ⚠️ 无 Hook | ⏳ 待验证 |
| REVIEW_PASS 检查（review 不可跳过） | Stop → `redcap-layerA-review-fallback.sh` | ✅ 已部署 | ⚠️ 未覆盖 | ⏳ 未部署 | ⚠️ 无 Hook | ⏳ 待验证 |
| `on_QA_PASS`（git commit 规范化） | 脚本封装（LLM 主动调用） | ✅ 脚本可用 | ✅ 脚本可用 | ✅ 脚本可用 | ✅ 脚本可用 | ✅ 脚本可用 |
| `pending_actions` 持久化 | state.yaml 原子写入（LLM 主动） | ✅ | ✅ | ✅ | ✅ | ✅ |
| 临时文件清理（/tmp/redcap-*） | SessionEnd Hook | ✅ 已部署 | ✅ 已部署 | ⏳ 未部署 | ⚠️ 无 Hook | ⏳ 待验证 |

### Layer A 部署详情

| 工具 | 部署文件 | 状态 | 备注 |
|------|----------|------|------|
| Claude Code | `~/.claude/settings.json` | ✅ 已部署 | SessionStart + Stop + SessionEnd → `redcap-layerA-*.sh` |
| Kimi CLI | `~/.kimi/config.toml` + Dispatcher | ✅ 已部署 | Stop + SessionEnd 去重机制（⚠️ 双触发 bug 待修复，见 hooks-kimi-cli.md §4.3） |
| Gemini CLI | `~/.gemini/settings.json` | ⏳ 未部署 | 能力已验证（v0.36.0），部署文档见 hooks-gemini-cli.md §3 |
| VS Code Copilot | 无 | ⚠️ 不可用 | 无 onTaskComplete 等价事件，退守 Layer 1-3 |
| Copilot CLI | `.github/hooks/*.json`（目标仓库级） | ⏳ 未部署 | Layer B 已在本仓库部署；Layer A 仍需为目标仓库生成安装模板 |

---

## Layer B — 开发 RedCap 自身

> 部署位置：**项目级**配置文件（RedCap repo 内的 `.claude/settings.json`、`.gemini/settings.json`、`.github/hooks/*.json`）

| 红线节点 | 保障机制 | Claude Code | Gemini CLI | Copilot CLI |
|----------|----------|------------|-----------|-------------|
| 独立架构评审（作者盲点防护） | Claude: Stop → `redcap-on-stop-review.sh`；其他宿主: SessionEnd → 统一收尾链补跑 | ✅ 已部署 | ✅ 已部署 | ✅ 已部署 |
| 飞书通知兜底（commit 后通知） | SessionEnd → `compass/tools/redcap-layerB-session-end.sh` | ✅ 已部署 | ✅ 已部署 | ✅ 已部署 |
| 任务完成报告模板审计 | SessionEnd → `compass/tools/redcap-task-report-check.sh` | ✅ 已部署 | ✅ 已部署 | ✅ 已部署 |
| 会话初始化（HEAD 捕获） | InstructionsLoaded / SessionStart → `compass/tools/redcap-layerB-session-start.sh` | ✅ 已部署 | ✅ 已部署 | ✅ 已部署 |
| 临时文件清理 | SessionEnd Hook | ✅ 已部署 | ✅ 已部署 | ✅ 已部署 |

### Layer B 部署详情

| 工具 | 部署文件 | 状态 | 备注 |
|------|----------|------|------|
| Claude Code | `.claude/settings.json`（项目级） | ✅ 已部署 | InstructionsLoaded → `compass/tools/redcap-claude-hook-init.sh`；Stop → `compass/tools/redcap-on-stop-review.sh`；SessionEnd → `loom/tools/redcap-layerA-session-end.sh claude` |
| Gemini CLI | `.gemini/settings.json`（项目级） | ✅ 已部署 | SessionStart → `compass/tools/redcap-layerB-session-start.sh gemini`；SessionEnd → `loom/tools/redcap-layerA-session-end.sh gemini` |
| Copilot CLI | `.github/hooks/redcap-layerB.json`（项目级） | ✅ 已部署 | `sessionStart` / `sessionEnd` → `.github/hooks/scripts/*` → 通用分发器 |

---

## 覆盖率摘要

| 场景 | 当前覆盖 | 主要缺口 |
|------|----------|---------|
| Layer A 最高优先级节点（on_ALL_DONE + review） | Claude Code ✅, Kimi CLI ✅ | Gemini CLI 未部署，Copilot CLI 需按仓库安装 |
| Layer B 收尾链（评审 + 报告 + 飞书） | Claude Code ✅, Gemini CLI ✅, Copilot CLI ✅ | Kimi CLI 暂未纳入本仓库项目级部署 |

---

## 下一步行动

| 优先级 | 行动 | 负责人 |
|--------|------|--------|
| P1 | 部署 Gemini CLI Layer A 用户级 Hook（`~/.gemini/settings.json`） | Cap + Norven |
| P2 | 为 Copilot CLI Layer A 生成仓库级 `.github/hooks/*.json` 安装模板 | Cap |
| P3 | Kimi CLI Stop/SessionEnd 去重 bug 修复（hooks-kimi-cli.md §4.3） | Cap |
