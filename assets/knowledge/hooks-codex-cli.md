# Codex CLI / Codex.app — 入口导入与宿主边界

> 本文件记录 RedCap 对 Codex CLI / Codex.app 的当前宿主画像、已落地接入点，以及为什么它目前仍被诚实标成“candidate + degraded”，而不是“已具备完整 Hook 宿主能力”。
> **当前状态**：Codex 的 `AGENTS.md` 启动导入已被 RedCap 正式采用；`codex exec` / `resume` / `mcp` 等非交互能力可以被仓库脚本消费；OpenAI 官方已经提供 Codex official lifecycle hooks（feature flag 后），本仓库已接入最小 `.codex/` candidate 配置；但在真实可信 Codex 会话完成 live marker E2E 前，不能宣称 full host parity，也不能宣称拥有完整 reply-time veto。即使 Codex CLI marker 通过，也不能自动宣称 Codex.app interactive surface 已经 ready，除非另有独立物理证据。

---

## 1. 当前可确认的能力面

结合本机 `codex --help` / `codex exec --help` 与当前仓库的实际接入，Codex 这条线已经可以诚实确认这些能力：

| 能力 | 当前状态 | 证据/落点 |
|------|---------|----------|
| `AGENTS.md` 作为宿主入口 | ✅ 已采用 | 仓库根 `AGENTS.md` |
| 非交互执行 `codex exec` | ✅ 可用 | `compass/tools/baton-launcher.sh`、`compass/tools/redcap-on-stop-review.sh` |
| 非交互结果文件化 | ✅ 可用 | `--output-last-message` 已进入 reviewer runner 与 baton |
| `resume` 会话续接入口 | ✅ CLI 可见 | `codex resume`、`codex exec resume` |
| MCP 管理面 | ✅ CLI 可见 | `codex mcp` |
| 项目级 `.codex/config.toml` | ✅ candidate 已接入 | `.codex/config.toml` 启用 `codex_hooks` feature flag |
| 项目级 `.codex/hooks.json` | ✅ candidate 已接入 | `SessionStart`、`PreToolUse`、`Stop` 接到 RedCap wrapper |
| repo-owned Stop Hook | ⚠ candidate / degraded | 需项目 `.codex/` trust + live marker E2E 证明物理触发 |
| Codex CLI live marker E2E | ⚠ 可执行探针 | `redcap-codex-live-marker-e2e.sh --run`；通过后只证明本机 Codex CLI `exec` 触发，不自动证明 Codex.app interactive |
| 回复前 veto / reply-time 拦截 | ❌ 仍未拥有完整能力 | Codex hooks 不等于完整 reply-time veto，见 `host-reliability.md` |

---

## 2. RedCap 已落地的 Codex 接入点

### 2.1 入口层

Codex 这条线当前的正式入口是仓库根 [AGENTS.md](/Users/norven/.claude/skills/redcap/AGENTS.md)。它只承担三件事：

1. 自动导入 `compass/soul.md`
2. 自动导入 `compass/CONTRIBUTING.core.md`
3. 指向 `redcap-current-status.sh` 与按需考古链

这意味着：

- `AGENTS.md` 是 **Codex 的薄入口**；
- 它不是第二份手册；
- 大文件 (`CONTRIBUTING.md` / `lessons.md`) 不会被默认整包注入。

### 2.2 非交互 runner

当前 RedCap 已把 Codex 接到两个 repo-owned runner 上：

| 落点 | 作用 |
|------|------|
| `compass/tools/baton-launcher.sh` | 作为通用外包原语，支持 `codex exec -C ... --sandbox read-only --ephemeral --output-last-message` |
| `compass/tools/redcap-on-stop-review.sh` | 作为独立评审 runner，在 reviewer 顺序命中 `codex` 时以文件化 prompt + `--output-last-message` 拉起 Codex reviewer |

当前 runner 约束已经固定为：

- 长 prompt 从生成开始就保持文件化；
- `stdin` 输入，不把大 prompt 塞进 argv；
- `stdout/stderr` 只当 transport noise；
- 程序化消费优先读取 `--output-last-message` 的结果文件。

---

## 3. `.codex/` 的正确边界

本地 Codex CLI 帮助信息明确会读取 `~/.codex/config.toml`，也允许 CLI 参数覆盖配置；但**这不等于 RedCap 应把 runtime 状态写进 `.codex/`**。

当前 RedCap 的正确边界是：

| 路径 | 用途 |
|------|------|
| `.codex/config.toml` | Codex 宿主配置（若未来需要） |
| `.codex/agents/` | Codex 自定义 agent 声明（若未来需要） |
| `.agents/skills/` | skill 打包/分发面 |
| `.workflow/` / `开发手册/.workflow/` | RedCap runtime state / session / pending closure / continuity |

一句话说：**`.codex/` 只放宿主声明，不放 RedCap 的活 runtime 账本。**

### 3.1 2026-05-09 Codex Hooks candidate

OpenAI 官方 Codex Hooks 文档已经把 `SessionStart`、`UserPromptSubmit`、`PreToolUse`、`PermissionRequest`、`PostToolUse`、`Stop` 列为生命周期事件；启用方式是 `config.toml` 中的 `[features] codex_hooks = true`。RedCap 当前只接入最小且保守的 candidate：

| 事件 | RedCap 接线 | 当前用途 | 边界 |
|------|-------------|----------|------|
| `SessionStart` | `compass/tools/redcap-codex-session-start.sh` | 转入 RedCap 复活、身份、状态恢复链 | 需要项目 `.codex/` 被 trust；失败时降级提醒，不阻断会话启动 |
| `PreToolUse` | `compass/tools/redcap-codex-pre-tool-use.sh` | 阻止明显危险动作，如 `git reset --hard`、证据目录物理删除、`npm publish` | 官方说明其覆盖不完整，只能做 guardrail，不能冒充全路径安全边界 |
| `Stop` | `compass/tools/redcap-codex-stop.sh` | 转入 Layer B 收尾检查；若仍有 pending closeout，则要求继续一轮 | 需要 JSON 输出，并用 `stop_hook_active` 防止循环续写 |

当前必须保留的升级门槛：

1. **feature flag**：必须启用 `codex_hooks`。
2. **project trust**：项目级 `.codex/` 只有被 Codex 信任后才会加载。
3. **live marker E2E**：必须用真实 Codex 会话验证 `SessionStart` / `Stop` 物理触发，再把状态从 candidate 升级为 ready。当前标准入口是 `bash compass/tools/redcap-codex-live-marker-e2e.sh --run`，它只记录清洗后的 marker 证据到 `references/codex-live-marker-e2e.json`。
4. **not full host parity**：即使 hooks 生效，也不能宣称完整 reply-time veto；`PreToolUse` / `PostToolUse` 不是完整沙箱。

### 3.2 live marker E2E 的人话解释

`redcap-codex-live-marker-e2e.sh --run` 做的事情很窄：开一个最小 `codex exec` 会话，让 Codex 宿主自己加载 `.codex/hooks.json`，再让 `SessionStart` 与 `Stop` wrapper 写两个 marker。它不会把 prompt、模型输出、本地绝对路径写进结果文件，也不会跑完整 closeout 副作用。

这条证据回答的是：“本机 Codex CLI 是否真的触发了 RedCap 的 Codex lifecycle hooks？”它不回答：“当前 Codex.app 图形会话是否也触发了？”因此状态面必须拆开表述：Codex CLI marker 可以 partial-ready，Codex.app interactive 仍要保留 degraded / separately unproven。

---

## 4. 为什么当前仍是 host-limited

Codex 这条线的关键边界不在“能不能读 AGENTS”，而在“RedCap 有没有拿到实时控制点”。

当前仓库没有把 Codex 标成完整 Hook 宿主，原因是：

1. **当前只有 Stop candidate，不是已验证 SessionEnd 等价链**
   RedCap 已把 Codex `Stop` candidate 接到 `redcap-layerB-session-end.sh`，但尚未完成真实 trusted session 的 live marker E2E。

2. **当前没有 reply-time veto**
   RedCap 不能在主 Agent 即将发回复前，物理拦截“无必要打断用户”或“无必要把 commit 升级成人工确认”。

3. **因此只能诚实说是 candidate + degraded，而不是完整闭环**
   这条边界已经落在：
   - `references/host-session-capability-matrix.json`
   - `compass/knowledge/host-reliability.md`
   - `references/execution-guarantee-tiers.md`

---

## 5. 当前推荐用法

在 RedCap 里，Codex 当前最适合做这些事：

1. **主宿主会话入口**
   依赖 `AGENTS.md` + `CONTRIBUTING.core.md` + `redcap-current-status.sh` 的轻量首读。

2. **只读 reviewer / explorer**
   用 `codex exec --sandbox read-only --ephemeral` 跑独立审查、证据检查、只读考古。

3. **文件化非交互任务**
   需要 headless 调用时，把 prompt 放文件，用 stdin 输入，用 `--output-last-message` 取最终答案。

目前**不应**对外宣称已经拥有这些能力：

1. Codex.app interactive lifecycle hooks 已完成独立 live marker E2E
2. Codex 已支持 repo-owned reply veto
3. Codex 当前宿主下的主 Agent 行为约束已达到 100% 物理强保障

---

## 6. 结论

Codex 当前在 RedCap 里的正确认知是：

1. **入口能力强**：`AGENTS.md`、`codex exec`、`resume`、MCP 都能被 RedCap 吃到。
2. **非交互能力够用**：适合 reviewer、explorer、只读 runner、文件化 headless 调用。
3. **生命周期控制面出现候选接线**：official lifecycle hooks 让 Codex 不再只是入口导入，但仍要 feature flag、project trust 和 live marker E2E。
4. **实时控制面仍弱**：没有完整 reply veto，就不能冒充完整 Hook 宿主。
5. **因此当前画像应维持为**：`supported + candidate/degraded`，而不是“已经 full host parity”。
