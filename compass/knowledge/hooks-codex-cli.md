# Codex CLI / Codex.app — 入口导入与宿主边界

> 本文件记录 RedCap 对 Codex CLI / Codex.app 的当前宿主画像、已落地接入点，以及为什么它目前仍被诚实标成 host-limited 而不是“已具备完整 Hook 宿主能力”。
> **当前状态**：Codex 的 `AGENTS.md` 启动导入已被 RedCap 正式采用；`codex exec` / `resume` / `mcp` 等非交互能力可以被仓库脚本消费；但当前仓库仍未拥有 Codex 的 repo-owned `SessionEnd` / reply-veto 控制点。

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
| 项目级 `.codex/config.toml` | ⚠ 理论存在，但当前仓库未依赖 | 本仓库当前没有 `.codex/` 目录 |
| repo-owned SessionEnd Hook | ❌ 当前未见 | 本仓库未声明 Codex 原生 Hook 配置 |
| 回复前 veto / reply-time 拦截 | ❌ 当前未见 | `host-limited`，见 `host-reliability.md` |

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

---

## 4. 为什么当前仍是 host-limited

Codex 这条线的关键边界不在“能不能读 AGENTS”，而在“RedCap 有没有拿到实时控制点”。

当前仓库没有把 Codex 标成完整 Hook 宿主，原因是：

1. **当前没有 repo-owned 的 Codex SessionEnd 链**
   也就是说，RedCap 还没有像 Claude / Gemini / Copilot 那样，把一个宿主原生结束事件稳定汇聚到 `redcap-layerB-session-end.sh`。

2. **当前没有 reply-time veto**
   RedCap 不能在主 Agent 即将发回复前，物理拦截“无必要打断用户”或“无必要把 commit 升级成人工确认”。

3. **因此只能诚实说是入口导入可用，而不是完整闭环**
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

1. Codex 原生 `SessionEnd` 已接到 RedCap 收尾链
2. Codex 已支持 repo-owned reply veto
3. Codex 当前宿主下的主 Agent 行为约束已达到 100% 物理强保障

---

## 6. 结论

Codex 当前在 RedCap 里的正确认知是：

1. **入口能力强**：`AGENTS.md`、`codex exec`、`resume`、MCP 都能被 RedCap 吃到。
2. **非交互能力够用**：适合 reviewer、explorer、只读 runner、文件化 headless 调用。
3. **实时控制面仍弱**：没有 repo-owned `SessionEnd` / reply veto，就不能冒充完整 Hook 宿主。
4. **因此当前画像应维持为**：`supported + degraded`，而不是“已经 full host parity”。
