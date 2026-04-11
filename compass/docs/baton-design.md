# 指挥棒设计（Baton Design）

> **本文件属于 Layer B 设计文档**，描述 compass 指挥棒（Layer B 调度能力）与 loom/dispatcher（Layer A 调度能力）的架构关系及共享原语。
> **状态**：设计已定案，脚本层已实现（2026-04-11）。

---

## 一、问题背景

三体重组后（见 commit `refactor(arch): 三体重组`），框架形成三体架构：

```
compass/   ← Layer B（框架自身开发/运营的大脑）
loom/      ← Layer A（用户项目开发的执行引擎）
prism/     ← 公共底层（多视角协同分析）
```

Layer A 有成熟的 `loom/dispatcher/`：状态机驱动、角色序列固定、基于文件系统通信。
Layer B（compass）目前缺乏系统性调度能力——Cap 处理 RedCap 自身任务时，只能靠 inline 决策，无可复用的调度原语。

**核心问题**：当 Cap 需要并行裂变子任务（§8）、棱镜委托（§11）或跨任务编排时，没有标准工具，每次从头造轮子。

---

## 二、OOP 类比（设计心智模型）

```
AbstractDispatcher（共享调度原语）
├── launch_agent(cli, prompt, session_id?) → result
├── collect_result(path, timeout) → content | BLOCKED | TIMEOUT
├── route_by_signal(signal) → next_action
└── broadcast_status(event, details) → 飞书通知（可选）

        ↙                      ↘
loom/dispatcher              compass 指挥棒
（Layer A 子类）              （Layer B 子类）
├── 状态机驱动                ├── 自由编排
├── 固定角色序列               ├── 动态任务图
├── 用户项目任务               ├── 框架自身任务
└── PM→Arch→Code→QA→Rev       └── §8并行 / §11棱镜 / skill外包
```

**关键原则**：
- 两者**共享"调度原语"**，但各自独立实现自己的调度逻辑
- loom/dispatcher 不变（稳定 Layer A 用户体验是优先级）
- compass 指挥棒作为新能力叠加，不替代 loom/dispatcher

---

## 三、共享调度原语（AbstractDispatcher）

以下是两者的公共能力，最终可以提取为共享工具脚本或文档协议：

### 3.1 Agent 启动原语

```bash
# 通用签名（各适配器实现不同）
launch_agent \
  --cli {gemini|claude|copilot|kimi} \
  --prompt "{prompt 内容}" \
  --session-id "{UUID（可选）}" \
  --skill-path "{skill 路径（可选，Skill外包模式）}" \
  --output-file "{结果写入路径}" \
  --timeout {N_seconds}
```

### 3.2 结果收集原语

```bash
baton-collect.sh \
  --output-file "{结果文件路径}" \
  --role "{角色名}" \
  --workflow-dir "{工作流目录}"
# exit 0 = DONE, exit 2 = BLOCKED（自动写 .workflow/blocked-*.md），
# exit 1 = 无信号/解析失败, exit 3 = 参数错误
```

> **注**：超时机制由 `baton-launcher.sh --timeout` 或 `baton-delegate.sh` 的 `timeout` 包装负责，
> `baton-collect.sh` 自身为单次读取，不轮询。

### 3.3 信号路由

| 信号 | loom 处理 | compass 指挥棒处理 |
|------|---------|-----------------|
| `completed` | 推进状态机到下一角色 | 标记子任务完成，继续编排 |
| `blocked` | 升级到上级角色或 Norven | 写 blocked 文件，等待透传 |
| `need_revision` | 回流到 programmer | 记录失败，降级或重试 |
| `timeout` | Fallback Agent | 记录 lessons，手工处理 |

---

## 四、compass 指挥棒特性

在共享原语之上，compass 指挥棒实现以下 Layer B 特有能力：

### 4.1 动态任务图（vs loom 的固定序列）

loom/dispatcher 按 PM→Arch→Code→QA→Rev 顺序执行，适合用户项目开发的线性工作流。
compass 指挥棒支持：
- **并行裂变**（§8）：N 个独立子任务同时启动，等待全部完成后汇总
- **条件分支**：根据 Prism 结论动态决定下一步
- **skill 外包**（§12）：将子任务委托给指定 skill，回收结果

### 4.2 与 loom/dispatcher 的通信

compass 可触发 Layer A 工作流（如启动一次完整的用户项目开发）：

```bash
# compass 触发 loom dispatcher 的入口
cd {user_project_root}
bash {loom_path}/dispatcher/dispatch.sh --task "{任务描述}" --project-dir "."
```

通信信道：文件系统（loom 的 `shared/` 目录），compass 通过读取 `state.yaml` 监控进度。

---

## 五、实现路线图

| 阶段 | 内容 | 状态 |
|------|------|------|
| 设计定案 | 本文件 | ✅ 完成 |
| 共享原语文档化 | `loom/dispatcher/agent-adapters.md §12`（多轮接力协议）| ✅ 已落地 |
| compass §8/§9 协议 | `compass/CONTRIBUTING.md §8/§9` | ✅ 已存在 |
| skill 外包协议 | `prism/protocol.md §六`（Skill-Delegation）| ✅ 已落地 |
| 实现共享工具脚本 | `compass/tools/baton-launcher.sh` | ✅ 已完成（2026-04-11） |
| 实现共享工具脚本 | `compass/tools/baton-collect.sh` | ✅ 已完成（2026-04-11） |
| 实现共享工具脚本 | `compass/tools/baton-delegate.sh` | ✅ 已完成（2026-04-11） |
| compass 指挥棒 CLI | `compass/tools/baton.sh` | 🔲 待实现（未来规划） |

---

## 六、设计决策记录

| 决策 | 选项 A（未采纳） | 选项 B（采纳） | 理由 |
|------|---------------|-------------|------|
| 指挥棒归属 | 挪进 compass，废弃 loom/dispatcher | compass 独立扩展，loom 原地不动 | 不破坏 Layer A 用户体验；两者独立演进 |
| 调度模型 | 实时进程间通信（IPC）| 文件系统接力 | 与棱镜现有通信模型同构；无额外依赖 |
| 共享方式 | 公共库（Python/Shell）| 文档协议（标准化原语描述）| 当前规模下文档协议成本更低；实现时再提取 |
