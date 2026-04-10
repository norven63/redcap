# CHANGELOG

RedCap 框架迭代历史（按时间倒序）。每次重大特性或架构变更记录于此。

---

## 2026-04-09

### Added
- **§5.15 长任务并行裂变协议**（SKILL.md）：定义子任务无耦合时的并行 Agent 启动规范，含完成标记、崩溃恢复清单、适配器约束
- **§5.16 Red Teaming 对抗型 Review 协议**（SKILL.md）：实施后启动独立 critic Agent 验证变更，要求 JSON 结构化输出，non-blocking 问题写入 pending-validations.md
- **L-30**（lessons.md）：并行 Agent 分析结论必须经 Red Teaming 才能用于实施
- **PM handbook brainstorming 算法植入**（roles/product-manager/handbook.md）：规模评估首步、一次一问、选择题优先、逐节确认、阶段三自检清单
- **lessons-score.sh**（tools/）：自动计算 lessons.md 每条评分，输出归档候选清单（含豁免期规则）
- **CHANGELOG.md**（本文件）：补齐标准文档结构

### Fixed
- e2e-postcheck check 6 重复项（check 数量 6→5）
- SKILL.md §5.2 prompt 文件后缀 `.md` → `.txt`（笔误）
- §5.15 完成判定改为 `##DONE##` 标记（原"文件存在+非空"有读半成品风险）
- §5.16 critic prompt 改为传入实际 diff + 要求 JSON 输出（原设计无法可靠报行号）

### Changed
- lessons.md 容量管理新增"豁免期"规则（最后命中 < 3 个月不计入归档候选）
- hook-standards.md §4 改为引用 host-reliability.md §3.2，消除重复
- PM handbook 规模评估明确"分解确认包"为例外，避免与"一次一问"规则矛盾

---

## 2026-04-08

### Added
- **Gemini CLI Hook 全宿主契约**：SessionStart/Stop/SessionEnd 三个 hook，Layer A hooks 行为规范统一
- **E2E 完整性 Gate + 配置锁定**（L-25/L-26）：E2E 验证追踪体系，后置检查脚本
- **Agent Fallback 两层降级**：Model 降级 → CLI 降级，避免框架任务落到 Dispatcher 手动代劳
- **L-29 Hook+子Agent CLI 模式**：hook 内调用 `agent -p -y` 开启子 Agent 的经验模式
- **§1.1 设计前置对抗机制**（CONTRIBUTING.md）：双层 Pre-mortem（自检 + 独立 Agent 红队）
- **outbox 文件模式 + state.yaml 自动校验**：`__redcap_status` 改为 outbox 文件传递
- **testing/ 目录**：E2E 基准场景 + 验证报告追踪体系
- **soul.md §八 复活协议**：两个 Cap 联合设计的跨载体人格复活机制

### Fixed
- GEMINI.md + CLAUDE.md 补入 `@soul.md` 自动导入（人格复活保障）
- Gemini hook 状态联动修复
- 多处框架一致性回归修复（7553e7e）

---

## 2026-04-07 及更早

核心框架初建：
- 多角色 Agent 架构（Dispatcher、PM、Architect、Engineer、QA）
- Layer A（用户环境 hooks）/ Layer B（项目工作流）双层设计
- dispatcher/agent-adapters.md 多 CLI 适配层
- references/hook-standards.md + knowledge/host-reliability.md 规范体系
- soul.md 人格连续性机制（Cap 的灵魂）
