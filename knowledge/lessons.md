# RedCap 框架级经验库（Framework Lessons Learned）

> 本文件记录跨项目可复用的经验教训。由 Dispatcher 在识别到高价值经验时手动归档。
> 项目级经验存放在各项目的 `开发手册/shared/lessons-learned.md`。

---

### L-1: Agent 文件路径必须使用绝对路径或明确基准
- **场景**：QA Agent 将 `last-result.json` 写到项目根目录而非 `开发手册/.workflow/` 下
- **根因**：Agent 对"当前工作目录"的理解与 Dispatcher 预期不一致，相对路径基准不同
- **经验规则**：Prompt 中涉及文件读写路径时，一律使用从项目根目录起算的完整相对路径，不依赖 Agent 自行推断基准目录
- **来源**：AI-Coding-Museum 冒烟测试, QA Agent, 2025-07

### L-2: Prompt 中必须包含交付物文件清单
- **场景**：Agent 完成工作但遗漏部分交付文件，Dispatcher 无法可靠验证
- **根因**：Prompt 仅描述任务目标，未明确列出 Agent 必须写入的文件列表
- **经验规则**：每个 Agent 的 Prompt 末尾必须附带 `## 必须写入的文件` 清单，Dispatcher 据此做交付物完整性校验（§5.7）
- **来源**：AI-Coding-Museum 冒烟测试, 多角色, 2025-07
