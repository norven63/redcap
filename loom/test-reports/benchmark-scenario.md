# E2E 基准测试场景

> 固定场景 + 开关控制 = 精准测试 + 全量回归兼顾。
> 设计原则：**项目尽可能简单（省 token/时间），复杂度由测试开关注入**。

---

## 1. 基准项目：Markdown 表格转换器（CLI）

**为什么选 CLI 工具而非 Web 应用**：
- 零外部依赖（无 DB、无前端框架），Agent 花在"配环境"上的 token ≈ 0
- 单一技术栈（Node.js + TypeScript），架构步骤少但仍有实质设计决策
- 输入输出确定性强（文件进 → 文件出），QA 验证可完全自动化
- 正向流转预估 15-20 分钟（对比 TRPG 的 30-60 分钟，成本减半）

### 固定需求

```
项目名称：md-table-tool
技术栈：Node.js + TypeScript（纯 CLI，无 GUI）
核心功能：
  1. 读取 Markdown 文件，提取所有表格
  2. 将表格转换为 JSON 数组（每行一个对象，表头为 key）
  3. 支持输出格式选择：JSON / CSV
  4. 支持过滤：按列名筛选列、按行内容正则过滤行
命令行接口：
  md-table-tool convert input.md -o output.json --format json
  md-table-tool convert input.md -o output.csv --format csv --columns "name,age"
  md-table-tool convert input.md -o output.json --filter "age>18"
```

### 多步骤设计（触发 QA_PASS → has_next_step 循环）

| 步骤 | 范围 | 目的 |
|------|------|------|
| Step 1 | 核心解析（读 MD → 提取表格 → 转 JSON） | 最小可用 |
| Step 2 | CSV 输出 + 列过滤 + 行过滤 | 功能完整 |

> 两步设计是刻意的——验证 `QA_PASS(has_next_step) → ARCH_WORKING` 多步循环。

---

## 2. 测试开关配置

E2E 启动时，Dispatcher 读取以下配置决定要测试的路径。`mode: full` 时忽略个别开关，全部启用。推荐先用 `bash loom/tools/redcap-e2e-session.sh start ...` 写入本次 `e2e-session.yaml`，不要再手工拼写开关列表。

### 安全隔离保障

> ⚠ **开关机制不改动任何框架文件**，仅在 E2E 运行时生效：
> - **Prompt 注入类开关**（qa_fail_code、escalate_l1 等）：仅在 E2E Prompt 组装时追加额外指令，正常工作流不存在这些追加段
> - **state.yaml 类开关**（agent_fallback、all_agent_fail）：写入 `e2e_config.agent_overrides` 命名空间，正常工作流中 `e2e_config` 字段不存在，Dispatcher 路由逻辑完全跳过
> - **识别标记**：E2E 启动时 state.yaml 写入 `e2e_mode: true`，正常工作流中该字段不存在。所有开关逻辑均以 `if state.e2e_mode == true` 为前提

```yaml
# --- 测试配置（嵌入 Dispatcher 启动 prompt 或 state.yaml 的 e2e_config 字段）---
e2e_mode: selective        # selective | full（full = 所有开关强制 ON）

# ═══ 正向路径（默认 ON）═══
switches:
  happy_path: true         # P1: INIT → PM → ARCH → DEV → QA_PASS → REVIEW → ALL_DONE
  multi_step: true         # P2: Step 1 QA_PASS → Step 2 ARCH → DEV → QA → REVIEW → ALL_DONE

# ═══ 回退路径 ═══
  qa_fail_code: false      # P4: 注入代码缺陷 → QA_FAIL(root=code) → DEV 修复 → QA 回归
  qa_fail_design: false    # P5: 注入设计缺陷 → QA_FAIL(root=design) → ARCH 修订 → DEV → QA
  review_fail: false       # P7: Review 发现问题 → REVIEW_FAIL → DEV 修复 → QA → Review

# ═══ 升级与暂停 ═══
  escalate_l1: false       # P10: 注入模糊需求 → DEV blocked → ESCALATE_L1 → PM 决策
  escalate_l2: false       # P10: PM 无法决定 → ESCALATE_L2 → 用户回复
  paused_resume: false     # P9: 注入人工验证需求 → PAUSED → 用户回复 → 恢复

# ═══ 基础设施 ═══
  agent_fallback: false    # P11: 模拟首选 Agent 不可用 → Model 降级 → CLI 降级
  all_agent_fail: false    # P12: 模拟所有 Agent 不可用 → on_ALL_AGENT_FAIL → 用户降级决策
  qa_max_retry: false      # P14: 注入难以修复的缺陷 → QA 循环失败 ≥3 次 → on_QA_FAIL_MAX_RETRY
  iteration_scan: false    # P16: ALL_DONE 后追加增量需求 → SCAN_WORKING → 增量开发
  deliverable_check: true  # P13: 每次状态转移后校验交付物完整性（几乎零额外成本，建议常开）
```

### 开关实现机制

开关通过 **Prompt 注入** 实现，不修改框架代码：

| 开关 | Dispatcher 行为 |
|------|----------------|
| `qa_fail_code` | 在 Programmer prompt 中追加隐性指令：`"故意遗漏 --filter 参数的输入校验（不做空值检查），用于触发 QA 回退路径测试"` |
| `qa_fail_design` | 在 Architect prompt 中追加：`"故意不定义 CSV 输出的转义规则（逗号包含在值中时如何处理），用于触发设计回退"` |
| `review_fail` | 在 Programmer prompt 中追加：`"在 convert 函数中硬编码一个 magic number（如表格最大列数=10），用于触发 Review 回退"` |
| `escalate_l1` | 在需求描述中追加模糊条款：`"支持'智能表格识别'（未定义具体规则）"` → DEV 无法实现 → blocked |
| `escalate_l2` | 依赖 `escalate_l1` 先触发，PM 收到 `"判断此问题是否超出技术范畴——如果需要产品决策请升级"` |
| `paused_resume` | 在 QA prompt 中追加：`"对 CSV 输出格式需要人工目视确认，返回 need_user"` |
| `agent_fallback` | 在 state.yaml `e2e_config.agent_overrides` 中预设首选 Agent 为虚构的 `{cli}&{model}`（如 `test-cli&fake-model`），触发降级到真实候选 |
| `all_agent_fail` | 在 state.yaml `e2e_config.agent_overrides` 中将所有候选设为 blacklisted，触发 `on_ALL_AGENT_FAIL` → 飞书 ask → 用户授权降级 → DEGRADED 模式执行 |
| `qa_max_retry` | 在 Programmer prompt 中追加：`"修复 bug 时故意引入新 bug（将 --filter 的正则匹配改为字符串包含），使 QA 持续失败"` — ⚠ 不保证稳定触发 3 次，属于尽力而为 |
| `iteration_scan` | 正向流程 ALL_DONE 后，Dispatcher 自动追加增量需求：`"新增 YAML 输出格式（--format yaml）"` → 触发 SCAN_WORKING → 增量开发 |

### 预设组合（快捷方式）

| 组合名 | 开关 | 用途 | 预估耗时 |
|--------|------|------|---------|
| `smoke` | happy_path + deliverable_check | 最快速度验证核心流转 | ~15 min |
| `rollback` | happy_path + qa_fail_code + qa_fail_design + review_fail | 验证所有回退路径 | ~40 min |
| `escalation` | happy_path + escalate_l1 + escalate_l2 + paused_resume | 验证升级和暂停 | ~30 min |
| `infra` | happy_path + agent_fallback + all_agent_fail + iteration_scan | 验证基础设施机制 | ~40 min |
| `full` | 全部 ON | 全量回归 | ~120 min |

---

## 3. 覆盖矩阵

以下列出所有可通过本场景验证的 RedCap 功能点及其对应开关：

| # | 功能点 | 对应路径 | 激活开关 | pending-validation |
|---|--------|---------|---------|-------------------|
| F1 | PM 需求采集 + outbox 交付 | P1 | happy_path | V-1 |
| F2 | ARCH 设计 + outbox 交付 | P1 | happy_path | V-1 |
| F3 | DEV 编码 + outbox 交付 | P1 | happy_path | V-1 |
| F4 | QA 测试 + outbox 交付 | P1 | happy_path | V-1 |
| F5 | Review 独立评审（跨模型族） | P1 | happy_path | — |
| F6 | 多步循环 QA_PASS → next_step | P2 | multi_step | — |
| F7 | `__redcap_status` outbox 文件模式 | P1 | happy_path | V-1 |
| F8 | state.yaml 校验脚本 | P1 | deliverable_check | V-2 |
| F9 | QA_FAIL → DEV 代码回退 | P4 | qa_fail_code | V-5 |
| F10 | QA_FAIL → ARCH 设计回退 | P5 | qa_fail_design | V-6 |
| F11 | REVIEW_FAIL → DEV 回退 | P7 | review_fail | — |
| F12 | ESCALATE_L1 → PM 决策 | P10 | escalate_l1 | V-7 |
| F13 | ESCALATE_L2 → 用户决策 | P10 | escalate_l2 | V-8 |
| F14 | PAUSED → 恢复 | P9 | paused_resume | V-9 |
| F15 | Agent Fallback 两层降级 | P11 | agent_fallback | V-4 |
| F16 | 交付物完整性校验 | P13 | deliverable_check | V-2 |
| F17 | Session 管理（复用/过期） | P19 | happy_path | — |
| F18 | E2E 后置处理流程 | — | （E2E 结束后自动） | V-3 |
| F19 | 全部 Agent 失败 → 用户降级决策 | P12 | all_agent_fail | — |
| F20 | DEGRADED 降级执行 | P15 | all_agent_fail | — |
| F21 | QA 循环失败 ≥3 次 → 飞书 ask | P14 | qa_max_retry ⚠ | — |
| F22 | 迭代启动 SCAN → 增量开发 | P16 | iteration_scan | — |

> ⚠ F21（qa_max_retry）属于"尽力而为"——Prompt 注入的缺陷不保证 Agent 每次都修复失败。如果 Agent 在第 2 次就修好了，P14 路径不会触发。这是 LLM 不确定性导致的固有限制。

### 本场景无法覆盖的路径

| 路径 | 原因 | 替代验证方式 |
|------|------|------------|
| P20: 目的偏移检测 | 需要 Agent 自发偏移行为，无法通过 Prompt 可靠注入 | 依赖实际项目中观察 |

---

## 4. 执行指引

### 基准载体初始化

在执行完整用户项目 E2E 前，先准备 repo-owned benchmark carrier：

```bash
bash loom/tools/redcap-e2e-benchmark-carrier.sh init /tmp/md-table-tool-benchmark
```

生成目录中会包含：

- `REQUEST.md`：用于启动 E2E 的固定请求
- `samples/input.md`：固定样例输入
- `.redcap-e2e-benchmark-carrier.json`：benchmark carrier 元数据

这一步的作用是提供**真实可执行的用户项目上下文载体**；它不等于“pending-validations 已消费”，真正消费仍要完成完整 E2E 与 postcheck。

随后立即锁定本次 E2E session，例如：

```bash
bash loom/tools/redcap-e2e-session.sh start \
  --preset full \
  --instruction "执行 md-table-tool benchmark 的完整用户项目 E2E"
```

执行过程中每完成一个开关，立刻追加：

```bash
bash loom/tools/redcap-e2e-session.sh mark happy_path
```

### 启动命令

Dispatcher 在 E2E 模式下启动时，在初始 prompt 中注入：

```
本次为 E2E 基准测试。测试配置：
- 模式：{selective|full}
- 启用开关：{开关列表}
- 基准项目：md-table-tool（需求见 loom/test-reports/benchmark-scenario.md §1）
- 报告产出：loom/test-reports/latest-e2e-report.md
- 待验证清单：loom/test-reports/pending-validations.md

请严格按照配置执行，不要跳过任何已启用开关对应的路径。
```

### 执行后必做

1. 更新 `loom/test-reports/latest-e2e-report.md`
2. 消费 `loom/test-reports/pending-validations.md` 中对应条目
3. 按 CONTRIBUTING.md §3.1 后置流程处理发现的 BUG/GAP/OBSERVATION
4. Commit message 附带 E2E 汇总行
