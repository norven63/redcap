# 子 Agent 强制约束（所有角色通用）

> 本文件由项目级 CLAUDE.md / GEMINI.md 通过 `@` 导入。
> 修改本文件即全局生效，无需同步各工具配置文件。

---

## 1. 安全铁律（违反即终止）

- 🔒 严禁硬编码密钥、Token、连接字符串等敏感信息，一律通过环境变量访问
- 🔒 禁止参考含硬编码密钥的示例代码（包括 demo 文件夹内内容）
- 🔒 涉及敏感配置的项目须提供 `.env.example`（仅含变量名 + 尖括号占位符）
- 🔒 `.gitignore` 必须排除 `.env`、`*.key`、`secrets/` 等敏感文件

> 完整安全规范见 `references/security-rules.md`。

## 2. 文件操作约束

- **所有文件写入使用内建 Write/Edit 工具**，严禁 Shell 重定向（`>`、`>>`）
- 只在 Dispatcher 指定的**工作目录和交付目录**下写文件
- 不修改 `.workflow/` 下的框架状态文件（`state.yaml` 等由 Dispatcher 管理）
- 文件路径使用从**项目根目录起算的相对路径**

## 3. 通信协议

- 回复末尾**必须**输出 `__redcap_status` JSON 块（格式见 `references/communication-protocol.md`）
- `status` 字段只能取值：`completed`、`failed`、`blocked`、`need_user`、`need_revision`
- `deliverables` 字段列出本次产生/修改的所有文件路径

## 4. 防退化检查点（长任务必读）

当任务涉及**多文件修改或超过 20 轮工具调用**时，执行以下检查：

- **每完成一个逻辑子任务后**：回顾本文件第 1-3 节约束，确认未违反
- **即将输出最终回复前**：确认 `__redcap_status` JSON 块格式完整、`deliverables` 无遗漏
- **涉及敏感配置时**：重读 `references/security-rules.md` 确认合规

> 本检查点机制是 L-9（长任务上下文压缩导致规则退化）的子 Agent 级对策。
> Dispatcher 级防退化见 SKILL.md §5.12。
