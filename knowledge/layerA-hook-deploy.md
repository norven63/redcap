# Layer A Hook 部署指南

> 本文件指导如何部署 RedCap Layer A 的用户级 Hook（`on_ALL_DONE` Layer 0 保护）。

---

## 前置条件

- Claude Code CLI 已安装
- RedCap 框架目录：`~/.claude/skills/redcap/`（根据实际路径调整）
- `jq` 非必需（脚本用 grep/sed 解析 JSON，零外部依赖）

## 部署步骤

### 1. 合并 Hook 配置到 `~/.claude/settings.json`

将以下 hooks 配置合并到你的用户级设置文件中（注意：如果已有其他 hooks，需要合并而非覆盖）：

```jsonc
// ~/.claude/settings.json
{
  // ... 其他配置 ...
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "<REDCAP_DIR>/tools/redcap-layerA-session-start.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "<REDCAP_DIR>/tools/redcap-layerA-stop.sh"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "<REDCAP_DIR>/tools/redcap-layerA-session-end.sh"
          }
        ]
      }
    ]
  }
}
```

> ⚠ 将 `<REDCAP_DIR>` 替换为 RedCap 实际安装的绝对路径（如 `/Users/yourname/.claude/skills/redcap`）。

### 2. 验证脚本可执行

```bash
ls -la ~/.claude/skills/redcap/tools/redcap-layerA-*.sh
# 确认 -rwxr-xr-x 权限
# 若权限不足：chmod +x ~/.claude/skills/redcap/tools/redcap-layerA-*.sh
```

### 3. 验证部署

```bash
claude --debug
# 观察 SessionStart 时是否看到 hook 执行日志
```

## 工作原理

```
SessionStart → 捕获 HEAD + 清理僵尸标记
       ↓
  (Agent 工作中...)
       ↓
    Stop（每轮）→ 检测 state.yaml 存在？→ 否：跳过
                                         → 是：ALL_DONE？→ 否：跳过
                                                          → 是：已通知？→ 是：跳过
                                                                         → 否：执行 on-complete.sh → 标记已通知
       ↓
SessionEnd → 清理 session 标记文件
```

## 与 Layer B 的共存

- **Layer B**（开发 RedCap 自身）：项目级 `.claude/settings.json`，检测 RedCap 仓库的新 commit
- **Layer A**（RedCap 开发用户项目）：用户级 `~/.claude/settings.json`，检测用户项目的 ALL_DONE 状态

两者通过不同的 settings.json 层级隔离，互不干扰：
- 在 RedCap repo 中工作时：Layer B hooks 生效（项目级），Layer A hooks 也生效但因无 `开发手册/.workflow/state.yaml` 而跳过
- 在用户项目中工作时：Layer A hooks 生效（用户级），Layer B hooks 不生效（不在 RedCap 项目中）

## 故障排查

| 问题 | 排查 |
|------|------|
| Hook 不触发 | `claude --debug` 检查 hook 日志 |
| 重复通知 | 检查 `/tmp/redcap-layerA-notified-*` 是否存在 |
| 僵尸标记累积 | `find /tmp -name "redcap-layerA-*" -ls`，SessionStart 会自动清理 >24h 的 |
| on-complete.sh 失败 | 检查 `feishu-notifier.py` 和 `feishu-config.json` 配置 |
