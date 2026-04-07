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

E2E 启动时，Dispatcher 读取以下配置决定要测试的路径。`mode: full` 时忽略个别开关，全部启用。

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
| `agent_fallback` | 在 state.yaml 中预设首选 Agent 为一个已知不可用的 `{cli}&{model}` |

### 预设组合（快捷方式）

| 组合名 | 开关 | 用途 | 预估耗时 |
|--------|------|------|---------|
| `smoke` | happy_path + deliverable_check | 最快速度验证核心流转 | ~15 min |
| `rollback` | happy_path + qa_fail_code + qa_fail_design + review_fail | 验证所有回退路径 | ~40 min |
| `escalation` | happy_path + escalate_l1 + escalate_l2 + paused_resume | 验证升级和暂停 | ~30 min |
| `full` | 全部 ON | 全量回归 | ~90 min |

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

### 本场景无法覆盖的路径

以下路径需要特殊环境条件，不适合在固定场景中测试：

| 路径 | 原因 | 替代验证方式 |
|------|------|------------|
| P12: 全部 Agent 失败 | 需要所有 CLI 同时不可用 | 手动断网测试 |
| P14: QA 循环失败 ≥3 次 | 需要 QA 连续产出不合格报告 | 极端条件，可在实际项目中观察 |
| P15: DEGRADED 降级执行 | 依赖 P12 先触发 | 同上 |
| P16: 迭代启动 SCAN | 需要已有项目做增量开发 | 首次 E2E 全量完成后，用同项目追加需求验证 |
| P20: 目的偏移检测 | 需要 Agent 产出偏离目的 | 难以可靠注入，依赖实际观察 |

---

## 4. 执行指引

### 启动命令

Dispatcher 在 E2E 模式下启动时，在初始 prompt 中注入：

```
本次为 E2E 基准测试。测试配置：
- 模式：{selective|full}
- 启用开关：{开关列表}
- 基准项目：md-table-tool（需求见 testing/benchmark-scenario.md §1）
- 报告产出：testing/latest-e2e-report.md
- 待验证清单：testing/pending-validations.md

请严格按照配置执行，不要跳过任何已启用开关对应的路径。
```

### 执行后必做

1. 更新 `testing/latest-e2e-report.md`
2. 消费 `testing/pending-validations.md` 中对应条目
3. 按 CONTRIBUTING.md §3.1 后置流程处理发现的 BUG/GAP/OBSERVATION
4. Commit message 附带 E2E 汇总行
