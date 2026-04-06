# Copilot CLI — Hooks 与指令注入详情

> 本文件从 [host-reliability.md](host-reliability.md) 拆分而来，记录 Copilot CLI 的 Hook 能力、技术规格及 RedCap 部署方案。
> **状态**：技术规格基于 Copilot CLI 自身实测（v1.0.18+, 2025-07），Cap 待独立验证（遵循 L-8）。

---

## 1. Hooks 能力

Copilot CLI 支持仓库级 Hook 配置（`.github/hooks/`），无需全局 Dispatcher 路由（与 Kimi CLI 的全局配置不同）。

### 1.1 支持的事件（8 种）

| 事件 | 触发时机 | 说明 |
|------|----------|------|
| `copilot-setup-steps` | Agent 启动时 | 环境准备（安装依赖等），支持 Dockerfile |
| `pre-tool-consent` | 工具调用前（需授权时） | 可拦截/审批工具调用 |
| `post-tool-call` | 工具调用后 | 可审计工具结果 |
| `session-start` | 会话开始 | Session ID 捕获点 |
| `session-end` | 会话结束 | 收尾/清理 |
| `model-request` | 模型请求前 | 可修改/审计请求 |
| `model-response` | 模型响应后 | 可审计/过滤响应 |
| `context-assembly` | 上下文组装时 | 可注入额外上下文 |

### 1.2 配置位置

```
项目根目录/
└── .github/
    └── hooks/
        ├── session-start.sh        # Session 开始
        ├── session-end.sh          # Session 结束
        ├── post-tool-call.sh       # 工具调用后
        ├── pre-tool-consent.sh     # 工具调用前审批
        └── context-assembly.sh     # 上下文注入
```

**工程级配置**：每个仓库独立管理自己的 hooks，不存在 Kimi CLI 的全局冲突问题。
**无需 Dispatcher 路由**：天然按仓库隔离，是最干净的 Hook 架构。

### 1.3 通信协议

- **输入**：stdin 接收 JSON 上下文（包含 session_id、事件相关字段）
- **输出**：stdout 返回 JSON 响应
- **拦截**：`{"permissionDecision": "deny"}` 阻止操作（与 Claude Code 的 exit code 2 不同）
- **允许**：`{"permissionDecision": "allow"}` 或 exit 0

### 1.4 与其他 CLI 的 Hook 对比

| 维度 | Copilot CLI | Claude Code | Kimi CLI |
|------|-------------|-------------|----------|
| 事件数量 | 8 种 | 4 种 | 13 种 |
| 配置范围 | 仓库级（`.github/hooks/`） | 全局（`~/.claude/hooks/`） | 全局（`~/.kimi/config.toml`） |
| 跨项目隔离 | ✅ 天然隔离 | ❌ 需手动 cwd 判断 | ❌ 需 Dispatcher 路由 |
| 拦截方式 | stdout JSON `deny` | exit code 2 | exit code 2 |
| 环境准备 | ✅ `copilot-setup-steps`（Dockerfile） | ❌ | ❌ |
| 上下文注入 | ✅ `context-assembly` | ❌ | ❌ |

---

## 2. 实测验证

> ⚠️ 以下数据来源于 Copilot CLI Agent 的自身实测报告（session `2a25efa6`，2025-07）。
> Cap 尚未独立验证（L-8 原则），标记为"待验证"。部署前需执行 §2.2 验证流程。

### 2.1 Copilot CLI 自报的验证结果

| 事件 | 触发 | stdin JSON 关键字段 | 自报结果 |
|------|------|---------------------|----------|
| `session-start` | 会话创建后 | `session_id` | ✅ 可用 |
| `post-tool-call` | 工具调用后 | `tool_name`, `tool_input` | ✅ 可用 |
| `session-end` | 会话关闭 | `session_id` | ✅ 可用 |
| `pre-tool-consent` | 工具审批前 | `tool_name` | ✅ 可用 |

### 2.2 独立验证流程（部署前必做）

```bash
# 1. 创建 hook 测试脚本
mkdir -p .github/hooks
cat > .github/hooks/session-start.sh << 'EOF'
#!/bin/bash
JSON=$(cat)
echo "$JSON" > /tmp/copilot-hook-session-start.json
touch /tmp/hook-fired-session-start
EOF
chmod +x .github/hooks/session-start.sh

# 2. 执行 Copilot CLI
copilot -p "echo hello" --allow-all --autopilot

# 3. 验证
[[ -f /tmp/hook-fired-session-start ]] && echo "✅ session-start hook fired" || echo "❌ NOT fired"
cat /tmp/copilot-hook-session-start.json | python3 -m json.tool

# 4. 清理
rm -f /tmp/hook-fired-session-start /tmp/copilot-hook-session-start.json
rm -f .github/hooks/session-start.sh
```

对每个需要使用的事件重复以上步骤。

---

## 3. RedCap 部署方案

### 3.1 需要的 Hook 脚本

| 脚本 | 事件 | 功能 |
|------|------|------|
| `session-start.sh` | session-start | 捕获 session ID → `.workflow/.copilot-session-id`；记录 git HEAD |
| `session-end.sh` | session-end | 检测新 commit → 飞书通知 → 清理临时文件 |
| `post-tool-call.sh` | post-tool-call | 可选：审计文件写入操作 |

### 3.2 session-start.sh 伪代码

```bash
#!/bin/bash
# .github/hooks/session-start.sh — Copilot CLI Session 开始
JSON=$(cat)

# 捕获 session ID
SESSION_ID=$(echo "$JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id','unknown'))")
echo "$SESSION_ID" > .workflow/.copilot-session-id

# 记录初始 HEAD（用于 session-end 对比）
git rev-parse HEAD > /tmp/redcap-copilot-initial-head 2>/dev/null

exit 0
```

### 3.3 session-end.sh 伪代码

```bash
#!/bin/bash
# .github/hooks/session-end.sh — Copilot CLI Session 结束
JSON=$(cat)

INITIAL_HEAD=$(cat /tmp/redcap-copilot-initial-head 2>/dev/null)
CURRENT_HEAD=$(git rev-parse HEAD 2>/dev/null)

if [[ -n "$INITIAL_HEAD" && "$INITIAL_HEAD" != "$CURRENT_HEAD" ]]; then
    # 有新 commit，触发飞书通知
    # tools/feishu-notify.sh ...
    echo "New commits detected, notifying..."
fi

# 清理
rm -f /tmp/redcap-copilot-initial-head
rm -f .workflow/.copilot-session-id

exit 0
```

> ⚠️ 以上均为伪代码，需通过 §2.2 验证流程确认 stdin JSON 字段名后才能实装（L-16 部署链验证）。

### 3.4 部署步骤

```
Phase 2 部署清单（待 E2E 验证后执行）：
1. 执行 §2.2 独立验证 → 确认 session-start/session-end 可用
2. 确认 stdin JSON 字段名（session_id 路径可能与文档不同）
3. 将伪代码转为实装脚本
4. 集成飞书通知（复用 tools/feishu-notify.sh）
5. E2E 测试：copilot -p "创建测试文件并 commit" → 验证飞书收到通知
6. 更新本文档 §2.1 标记为 ✅ 独立验证通过
```

---

## 4. 可靠性评估

**Layer 0** — 确定性执行（Hook 机制内建于 Copilot CLI）：
- `session-start` + `session-end` = 会话级 100% 覆盖
- 仓库级配置天然隔离，无需 Dispatcher 路由（优于 Kimi CLI）
- 8 种事件覆盖面适中，`context-assembly` 提供独特的上下文注入能力

**风险**：
- Copilot CLI 仍在快速迭代（v1.0.x），Hook API 可能变更
- 未经 Cap 独立验证，实际 stdin JSON 字段名可能与文档有出入
- `--allow-all` 模式下 `pre-tool-consent` 是否仍触发待验证
