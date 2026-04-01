# RedCap 自身开发 — Gemini CLI 系统级指令

> 本文件由 Gemini CLI 在每次对话自动加载，不受上下文压缩影响。
> 等价于 `.github/copilot-instructions.md` 的 Gemini CLI 版本。
> 完整规范见 `CONTRIBUTING.md`，本文件仅提取**必须强制执行**的核心规则。

---

## 强制规则（不可跳过）

### R1: 变更前必读经验库

修改 RedCap 框架文件前，**必须先读取 `knowledge/lessons.md`**，检查本次变更是否涉及已知陷阱。

### R2: Commit 格式

```
type(scope): 简要描述
```

type: feat | fix | refactor | docs | chore
scope 见 CONTRIBUTING.md §2

### R3: 变更后经验沉淀检查

每轮变更完成后自检：是否发现新的失败模式/反直觉行为/错误假设？→ 归档到 `knowledge/lessons.md`

### R4: 飞书完成通知（必须，自动执行）

每轮变更全部完成并 git commit 后、**结束任务之前**，必须自动执行：

```bash
python3 tools/feishu-notifier.py notify "RedCap 框架变更完成: <简要描述>\n\nCommits:\n$(git log --oneline <初始commit>..HEAD)" --project "redcap"
```

> ⚠ 这是强制步骤。通知失败时记录警告但不阻塞任务完成。

### R5: 文件变更影响范围

修改以下文件时，必须检查是否需要同步更新关联文件：

| 修改的文件 | 必须检查 |
|-----------|---------|
| SKILL.md §5.2 事件循环 | dispatcher/state-machine.md 伪代码 |
| SKILL.md §5.10 Hooks | dispatcher/state-machine.md 对应触发点 |
| references/communication-protocol.md | roles/ 下各角色手册 |
| dispatcher/agent-adapters.md | SKILL.md §5.5 路由表 |

### R6: 防退化 — 工作流规范重载（仅 RedCap 项目开发时）

当作为 Dispatcher 执行 RedCap 工作流时，**每轮事件循环开始前**必须：

1. 读取 `dispatcher/reload-rules.yaml`
2. 根据当前检查点（角色切换/即将commit/即将结束/PAUSED）重读对应规范段落

> 这是防止长任务上下文压缩导致规则退化的核心机制（L-9）。
