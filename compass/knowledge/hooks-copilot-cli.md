# Copilot CLI — Hooks 与指令注入详情

> 本文件从 [host-reliability.md](host-reliability.md) 拆分而来，记录 Copilot CLI 的 Hook 能力、官方约束与 RedCap 的实际部署。
> **当前状态**：官方文档已确认 Copilot CLI 会从仓库内的 `.github/hooks/*.json` 加载 Hook 配置；本仓库 Layer B 已部署 `redcap-layerB.json`。`sessionStart` / `sessionEnd` 输入**不含 sessionId**，因此 Session 续传能力与 Hook 是两条独立机制。

---

## 1. Hooks 能力

Copilot CLI 支持**仓库级** Hook，配置文件必须放在 `.github/hooks/*.json`。
仅有 `.github/hooks/` 目录或脚本文件本身，**不等于已部署**；必须存在 JSON 配置文件把事件绑定到脚本。

### 1.1 已确认的关键事件

以下事件由 GitHub 官方 Hook 文档明确记录，足以覆盖 RedCap 目前需要的 Layer B 收尾链：

| 事件 | 触发时机 | 关键字段 | 备注 |
|------|----------|----------|------|
| `sessionStart` | 新会话开始 / 恢复时 | `timestamp`, `cwd`, `source`, `initialPrompt` | **无 sessionId**；输出被忽略 |
| `sessionEnd` | 会话完成 / 终止时 | `timestamp`, `cwd`, `reason` | **无 sessionId**；输出被忽略 |
| `userPromptSubmitted` | 用户提交 prompt 后 | `timestamp`, `cwd`, `prompt` | 适合审计，不适合收尾 |
| `preToolUse` | 工具调用前 | `toolName`, `toolArgs` | 可通过 stdout JSON 拒绝执行 |
| `postToolUse` | 工具调用后 | `toolName`, `toolArgs`, `toolResult` | 适合日志与策略审计 |
| `errorOccurred` | Agent 运行出错时 | `error.*` | 输出被忽略 |

### 1.2 配置位置

官方教程明确：Copilot CLI 会自动发现仓库内的 `.github/hooks/*.json`。

当前 RedCap Layer B 的实际结构：

```text
.github/
└── hooks/
    ├── redcap-layerB.json
    └── scripts/
        ├── redcap-layerB-session-start.sh
        └── redcap-layerB-session-end.sh
```

其中：

1. `.github/hooks/redcap-layerB.json` 负责声明事件绑定
2. `scripts/*.sh` 只是轻量包装层
3. 真正的收尾逻辑仍汇聚到 RedCap 通用脚本：
   - `compass/tools/redcap-layerB-session-start.sh`
   - `loom/tools/redcap-layerA-session-end.sh copilot`
   - `compass/tools/redcap-layerB-session-end.sh`

### 1.3 通信协议

| 类型 | 协议 |
|------|------|
| 输入 | stdin JSON |
| 输出（`sessionStart` / `sessionEnd` / `postToolUse` 等） | 被忽略 |
| 输出（`preToolUse`） | stdout JSON，使用 `permissionDecision` / `permissionDecisionReason` |

> 关键差异：Copilot CLI 的拦截结果是**stdout JSON**，不是特殊退出码。

### 1.4 Session 兼容 ≠ Hook

这是 Copilot 线最容易混淆的点：

| 问题 | 正确答案 |
|------|----------|
| Hook 能拿到 `sessionId` 吗？ | **不能**。官方 `sessionStart` / `sessionEnd` 输入都没有 `sessionId`。 |
| `sessionStart` 因此没用吗？ | **不是**。它仍然适合做初始 HEAD 捕获、会话开始审计等无须 `sessionId` 的动作。 |
| Copilot 的会话恢复 / 跟进能力靠什么？ | 靠 `--resume` / `--continue`，或 `--output-format=json` 结果中的 `sessionId`，**不是 Hook**。 |

---

## 2. RedCap 部署现状

### 2.1 Layer B（开发 RedCap 自身）

当前仓库已经落地以下配置：

```json
{
  "version": 1,
  "hooks": {
    "sessionStart": [
      {
        "type": "command",
        "bash": "./scripts/redcap-layerB-session-start.sh",
        "cwd": ".github/hooks"
      }
    ],
    "sessionEnd": [
      {
        "type": "command",
        "bash": "./scripts/redcap-layerB-session-end.sh",
        "cwd": ".github/hooks"
      }
    ]
  }
}
```

### 2.2 当前链路职责

| 文件 | 职责 |
|------|------|
| `.github/hooks/redcap-layerB.json` | Copilot 仓库级 Hook 注册入口 |
| `.github/hooks/scripts/redcap-layerB-session-start.sh` | 包装到统一 SessionStart 脚本 |
| `.github/hooks/scripts/redcap-layerB-session-end.sh` | 包装到统一 SessionEnd 分发器 |
| `compass/tools/redcap-layerB-session-start.sh` | 捕获初始 HEAD |
| `compass/tools/redcap-task-report-check.sh` | 审计最近 commit 区间内是否存在模板完整的任务报告 |
| `compass/tools/redcap-layerB-session-end.sh` | 飞书兜底、任务报告审计、非 Claude 宿主补跑独立评审 |

### 2.3 Layer A 状态

Copilot CLI 的能力已经足够覆盖 Layer A，但**当前框架尚未自动为用户项目生成 `.github/hooks/*.json`**。
因此：

- **Layer B**：已部署
- **Layer A**：能力存在，但仍需按仓库安装

### 2.4 本地独立验证（2026-04-11）

已在本仓库用 `copilot -p ... --no-custom-instructions -s --model gpt-5-mini` 做两轮最小验证：

1. **SessionEnd 触发证明**
   - 预写入 `/tmp/redcap-layerB-copilot-last-notified-head = HEAD~1`
   - 运行后 `/tmp/redcap-layerB-copilot-last-alerted-head = CURRENT_HEAD`
   - 说明 `sessionEnd -> redcap-layerB-session-end.sh` 已真实执行
2. **SessionStart 触发证明（间接）**
   - 清空 `last-notified` / `initial-head` 后运行同样命令
   - 运行结束后 `last-notified` 仍为 `(missing)`
   - 若 `sessionStart` 未触发，`sessionEnd` 会走无基线降级分支并写入 `last-notified`
   - 因此该结果反向证明本次运行中 `sessionStart` 已先写入初始 HEAD，再被 `sessionEnd` 的无差异分支清理

结论：**本仓库 Copilot Layer B 的 `sessionStart` / `sessionEnd` 已通过本地独立验证。**

---

## 3. 可靠性评估

**优势**

1. 仓库级配置天然隔离，不需要像 Kimi / Claude 那样靠 cwd 路由全局 Hook
2. `sessionStart` + `sessionEnd` 足以支撑 Layer B 的确定性收尾链
3. `preToolUse` / `postToolUse` 为未来策略审计留出了扩展面

**边界**

1. `sessionStart` / `sessionEnd` 不提供 `sessionId`
2. Layer A 仍未自动部署，不能把“能力存在”误写成“默认已覆盖”
3. Copilot CLI 仍在快速迭代，Hook API 与字段名需持续跟踪官方文档

---

## 4. 结论

Copilot CLI 这条线当前的正确认知是：

1. **Hook 能力真实存在，且官方支持仓库级 `.github/hooks/*.json`**
2. **Session 兼容能力不靠 Hook，而靠 `--resume` / `--continue` 与 JSONL `sessionId`**
3. **RedCap Layer B 已经实装 Copilot SessionStart / SessionEnd 收尾链**
4. **Layer A 仍需后续补安装模板，不能再把“可做”写成“已部署”**
