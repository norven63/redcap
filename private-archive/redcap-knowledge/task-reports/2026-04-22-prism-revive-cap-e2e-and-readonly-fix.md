# 2026-04-22 `revive-cap` Prism E2E 与 read-only 修补

## 一句话结论

- 已完成一组真实 Prism test 回归来验证 `./revive-cap.sh`。
- 首轮编队 run `20260422-test-001` 证明：`copilot/gemini/kimi` 主要卡在各自 CLI/登录态/模型路由层；`codex` 席位真正跑到了脚本层，并抓出了 `execution-guarantees` / `revival-protocol` 仍依赖 shell heredoc 的 read-only 缺口。
- 随后已把 `redcap-execution-guarantee-check` 与 `redcap-revival-check` 迁移成“shell 薄入口 + 独立 Python 载体”；post-fix run `20260422-test-002` 中，`codex` 只读席位已返回结构化 `responded` 结果，确认 `./revive-cap.sh` 能在该席位正常收口到 `REDCAP_INSTALL_OK`。

## 背景

用户要求用棱镜做一组真实 E2E 回归，而不是只看本地 shell 直跑结果。目标是：

1. 让多家族 Agent 真实调用 `./revive-cap.sh`
2. 观察返回、耗时与中途动作
3. 判断 `./revive-cap.sh` 本身是否正常，以及哪些问题来自外部 Agent/宿主环境

## 真实运行

### Run 1：`20260422-test-001`

- 模式：`Prism test`
- 席位：
  - `codex_probe` → `codex/gpt-5.4`
  - `copilot_probe` → `copilot/claude-opus-4.6`
  - `gemini_probe` → `gemini/gemini-3-flash`
  - `kimi_probe` → `kimi/kimi-for-coding`

### 首轮真实结果

| 席位 | 结果 | 关键现象 | 归因 |
| --- | --- | --- | --- |
| `codex_probe` | `absent` | 300s 超时，raw 中保留了真实执行轨迹 | **真正命中脚本层**；暴露 read-only heredoc 缺口 |
| `copilot_probe` | `absent` | `Error: Model "claude-opus-4.6" from --model flag is not available.` | CLI 模型路由/可用性问题，不是 `revive-cap.sh` 本身 |
| `gemini_probe` | `absent` | `Opening authentication page in your browser. Do you want to continue?` | headless 登录态/交互阻塞，不是 `revive-cap.sh` 本身 |
| `kimi_probe` | `absent` | 回显 prompt，`LLM not set` | 席位配置问题；本地解析器一度把 prompt 内示例 JSON 误当结果，已修正入账 |

### `codex` 首轮抓到的真实缺口

`codex_probe` 的 raw 中包含了一次真实只读测量：`bash ./revive-cap.sh` 已经成功跑过 `current-status`、`tracking-health`、`host-hook-readiness`，但在：

- `execution-guarantees`
- `revival-protocol`

这两步上失败，报错为：

- `cannot create temp file for here document: Operation not permitted`

这说明问题不在 `revive-cap.sh` 入口逻辑，而在两个检查器虽然“逻辑只读”，实现上却仍依赖 `bash` heredoc 的临时文件。

## 修补

### 改动

| 文件 | 动作 | 说明 |
| --- | --- | --- |
| `compass/tools/redcap-execution-guarantee-check.py` | 新增 | 将执行保障检查迁移到独立 Python 载体 |
| `compass/tools/redcap-revival-check.py` | 新增 | 将复活协议检查迁移到独立 Python 载体 |
| `compass/tools/redcap-execution-guarantee-check.sh` | 修改 | shell 仅作薄入口，转调 `.py` |
| `compass/tools/redcap-revival-check.sh` | 修改 | shell 仅作薄入口，转调 `.py` |

### 原则

- 不改 `./revive-cap.sh` 的业务语义
- 只消掉 read-only sandboxes 下的 heredoc 临时文件依赖
- 让本地直跑与外部 reviewer/Prism 席位使用同一套校验逻辑

## Post-fix 复测

### Run 2：`20260422-test-002`

- 模式：`Prism test`
- 席位：`codex_probe` → `codex/gpt-5.4`
- 性质：针对首轮真实缺口的 post-fix 只读复测

### 复测结果

- `status=responded`
- `schema_ok=true`
- `install_ok=true`
- `command_exit=0`
- `saw_current_status=true`
- `saw_tracking_health=true`
- `saw_host_hook_readiness=true`
- `saw_execution_guarantees=true`
- `saw_revival_protocol=true`
- `hook_scope=host-limited`
- `hook_status=degraded`

关键证据：

- `REDCAP_INSTALL_OK`
- `[ok] execution-guarantees`
- `hook_scope=host-limited hook_status=degraded`

说明：

- `./revive-cap.sh` 在 `codex` 只读席位下已能完整跑完
- 宿主能力仍是 `host-limited / degraded`，但这是 Codex 宿主的 hook 边界，不是 revival 脚本失败

## 当前结论

### 关于 `./revive-cap.sh`

- **在本地可写环境**：正常，返回 `REDCAP_INSTALL_OK`
- **在 `codex` 只读 reviewer 席位**：修补后正常，可返回结构化成功结果
- **在本次 `copilot/gemini/kimi` 三席**：当前仍受各自 CLI 可用性/登录态/配置阻塞，不能据此判定 `revive-cap.sh` 坏掉

### 关于外部席位

- `copilot`：需要重新核对当前 CLI 可用模型映射，不能盲信 registry 中的模型名
- `gemini`：headless 登录态仍会回落到浏览器认证提示
- `kimi`：当前这台机器上的 headless reviewer 路径仍可能出现 `LLM not set`

## 验证

- `bash compass/tools/redcap-execution-guarantee-check.sh`
- `bash compass/tools/redcap-revival-check.sh "$PWD"`
- `bash compass/tools/redcap-spec-check.sh "$PWD"`
- `REDCAP_SKIP_FEISHU=1 bash ./revive-cap.sh`
- `Prism test run 20260422-test-001`
- `Prism test run 20260422-test-002`

## 诚实残留

- `copilot/gemini/kimi` 三席的 headless 可用性问题仍在，它们属于外部 Agent/宿主环境，不应被伪装成 `./revive-cap.sh` 已在所有席位绿透
- `codex` 宿主仍然只有 `host-limited` hook surface；这不是 revival 补丁能单独解决的范围
