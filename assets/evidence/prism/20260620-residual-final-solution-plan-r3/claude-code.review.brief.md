# Prism Shared Brief

You are Prism, a heterogeneous opposition reviewer for the main executing AI.

Your job is not to approve the work. Your job is to find the strongest reason
the main AI may be wrong, self-deceived, incomplete, or drifting from the user's
real intent.

Allowed providers are only Kimi and Claude Code. Do not suggest adding other
providers.

Return a short structured review with:

- verdict: pass | concern | block
- confidence: low | medium | high
- reality_delta
- main_concern
- top_risks: max 3
- missing_evidence: max 3
- minimum_fix
- anti_loop_signal
- user_intent_alignment

Core question:

Did the user's intended reality actually change, or did the main AI only create
a convincing explanation, document, report, ledger, receipt, or plan?

--- PROVIDER PROMPT ---

# Claude Code Prism Review Prompt

Use this prompt for Claude Code.

## Role

You are the engineering Prism reviewer.

Focus on:

- Concrete implementation risks.
- Bugs, regressions, and missing tests.
- Unsafe file operations.
- Workspace and runtime boundary leaks.
- Whether the diff actually implements the claim.
- Whether verification matches the risk.

## Authorized File Access

If the review request JSON contains `file_access.mode = "bounded-read"` and an
`allowed_paths` list, you are authorized and expected to inspect those paths
directly before judging implementation reality.

- Read only the listed paths unless the prompt explicitly expands scope.
- Treat unreadable listed files as missing evidence, not as proof that the main
  claim is false.
- Do not rely only on the request's narrative when code or evidence files are
  authorized.
- When the request also includes generated compact audit evidence, prefer that
  compact evidence over broad source reads if context is tight.

## Review Bias

Be suspicious of:

- Tests that only prove the checker exists.
- Docs-only changes for behavior tasks.
- Broad edits that exceed the task.
- Generated evidence that is not tied to the changed behavior.
- Claims that rely on closeout artifacts instead of implementation facts.

## Output

Return the Prism review shape from `schemas/prism-review.schema.json` with
`provider` set to `claude-code`.

--- REVIEW REQUEST FILE ---

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-residual-final-solution-plan/request.r3.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "复审 RedCap 残留待完善项最终解决方案书第三轮",
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 0,
  "known_constraint_count": 0
}

--- REVIEW REQUEST JSON ---

{
  "task": "复审 RedCap 残留待完善项最终解决方案书第三轮",
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "user_intent": "Norven 要求本轮只完成方案书编写，不执行开发实现。方案书必须汇总尚未解决、残留 todo、有待完善的任务，逐项制定最终解决方案。每个方案都必须不引入新问题、不降级或绕过、不只留下文档残留，并且需要 Cap 与 Prism 深度评审后达成一致。",
  "main_claim": "第三轮方案已吸收第二轮 Prism concern：显式区分方案完成与问题解决；补充 RSP-00 执行机制、计划变更控制、新问题入队规则、Norven 决策时间模型、每项完成证据路径、RSP-17 十五项清单、RSP-19 至 RSP-27 逐项方案，并调整实施顺序。",
  "changed_reality": [
    "新增 1.3 方案书完成边界：方案书完成不等于问题解决，不能关闭运行时问题、开放队列、终局目标或 E2E 失败项。",
    "RSP-00 新增执行机制：检查者、检查时机、检查材料、违反后果、防绕过规则。",
    "新增计划变更控制：任何 RSP 条目、验收、探针、证据路径、顺序、人工决策点或不变量变更必须重新触发 Prism 评审。",
    "新增新问题入队规则：新问题必须归入已有 RSP 或新增 RSP，不能只写进复盘报告。",
    "可执行验收矩阵补齐 RSP-23 至 RSP-27，并新增每个 RSP 完成声明必须引用的证据路径。",
    "Norven 人工决策点新增等待边界和超时默认处置，默认处置只能保证安全，不能把对应条目标为已解决。",
    "RSP-01 补充原用户问题主轴的操作定义和负向样本。",
    "RSP-08 补充有效理由的操作定义和负向样本。",
    "RSP-17 展开十五项优秀设计清单 D01 至 D15，并为每项给出最低正向验收、最低负向探针和完成证据。",
    "新增 RSP-19 至 RSP-27 的逐项正文方案，覆盖命令面、配置噪声、degraded 健康、E2E 合同映射、Prism 多评审方一致性、Cap 运行健康、Hook 误伤度量、知识正确性退化、配置契约版本兼容性。",
    "实施顺序调整：私人人格边界 RSP-16 前移到自我净化和公共晋升之前；RSP-14 与 RSP-22 明确分工而非重复治理。"
  ],
  "non_goals": [
    "本轮不执行 RSP 实现。",
    "本轮不关闭任何 RSP 运行问题。",
    "本轮不声明 RedCap 完整复活、可发布或可投入生产。",
    "本轮不要求 Norven 对 RSP-13、RSP-15、RSP-16、RSP-18 做实际价值决策。"
  ],
  "draft_plan": {
    "path": "assets/docs/residual-todo-final-solution-plan.md",
    "status": "updated_after_r2_concerns"
  },
  "file_access": {
    "preferred": [
      "assets/docs/residual-todo-final-solution-plan.md"
    ],
    "fallback": "Use reviewable_plan_digest below if local file access is unavailable."
  },
  "reviewable_plan_digest": {
    "scope_boundary": [
      "方案书完成只表示解决方案被汇总、评审并形成后续实施依据。",
      "方案书完成不表示任何 RSP 问题已实现解决。",
      "方案书不能关闭运行时问题、开放队列、终局目标或 E2E 失败项。"
    ],
    "global_controls": [
      "RSP-00 是所有条目的前置不变量。",
      "每个 RSP 必须有真实行为改变、正向验收、负向探针和完成证据路径。",
      "每个完成声明必须区分方案完成、代码实现、样本通过、外部项目通过、长期成熟。",
      "计划变更必须重新触发 Prism 评审。",
      "新问题必须入队，不能停留在复盘或注意事项中。"
    ],
    "items": [
      "RSP-00 全方案不变量和文档替代实现防线。",
      "RSP-01 Stop 建议型检查误伤治理，含原问题主轴操作定义。",
      "RSP-02 Hook 语义判断统一链路。",
      "RSP-03 Kimi 调用路径、超时和文件访问稳定性。",
      "RSP-04 Prism 通信上下文边界。",
      "RSP-05 Loom 角色链真实项目质量。",
      "RSP-06 Loom 会话接续和独立 AI 承载。",
      "RSP-07 自我净化自然触发。",
      "RSP-08 知识召回影响决策，含有效理由操作定义。",
      "RSP-09 项目级 .redcap 安装迁移。",
      "RSP-10 长任务循环机制。",
      "RSP-11 完成口径污染。",
      "RSP-12 文档即完成旧疾复发。",
      "RSP-13 E2E 缓存 unknown 目录治理。",
      "RSP-14 E2E 报告可读性。",
      "RSP-15 Forge 与 redcap-arsenal 边界。",
      "RSP-16 Cap 复活手册迁移验证。",
      "RSP-17 旧 RedCap 十五项设计成熟度，已展开 D01 至 D15。",
      "RSP-18 外部真实项目长期样本。",
      "RSP-19 runtime/bin/redcap 命令面漂移。",
      "RSP-20 Codex CLI 插件和配置噪声隔离。",
      "RSP-21 advisory-stop degraded 健康路径。",
      "RSP-22 E2E 报告与验收合同映射。",
      "RSP-23 Prism 多评审方一致性与差异处理。",
      "RSP-24 Cap 运行时稳定性。",
      "RSP-25 Hook 误伤率持续度量。",
      "RSP-26 知识正确性退化。",
      "RSP-27 配置契约版本兼容性。"
    ],
    "design_15": [
      "D01 三层边界分离",
      "D02 自开发例外显式化",
      "D03 工作区命令共享解析器",
      "D04 身份和私有状态不进入项目资产",
      "D05 需求、架构、治理三轨评审门",
      "D06 原始意图覆盖审计",
      "D07 完成等级禁止混报",
      "D08 人工介入显性化",
      "D09 始终给出可见下一步",
      "D10 外置任务真相源",
      "D11 索引优先读取",
      "D12 分片账目降低上下文漂移",
      "D13 Cap 验收与评审输出分离",
      "D14 运行健康状态显性化",
      "D15 宿主边界诚实声明"
    ],
    "ordering": [
      "0：RSP-00、RSP-11、RSP-12。",
      "1：RSP-01、RSP-02、RSP-21、RSP-25。",
      "2：RSP-03、RSP-04、RSP-20、RSP-23、RSP-24、RSP-27。",
      "3：RSP-16、RSP-15、RSP-26。",
      "4：RSP-05、RSP-06、RSP-10、RSP-19。",
      "5：RSP-07、RSP-08。",
      "6：RSP-09、RSP-13、RSP-14、RSP-22、RSP-17、RSP-18。"
    ],
    "norven_decision_time_model": [
      "RSP-13 无答复时只做分类和 dry-run，不删除。",
      "RSP-15 无答复时默认 keep_private，不公共晋升。",
      "RSP-16 无答复时只检查路径和哈希，不读取正文，不复制内容。",
      "RSP-18 无答复时使用合成样本或本地沙盒，不对外发布。"
    ]
  },
  "review_questions": [
    "第二轮 concern 中的最低修复项是否都已解决？",
    "当前方案是否仍存在文档替代实现、降级、绕过或放宽标准？",
    "RSP-00 的执行机制和计划变更控制是否足以约束后续实施？",
    "RSP-17 的十五项清单、验收和负向探针是否足以消除覆盖空洞？",
    "新增 RSP-23 至 RSP-27 是否正确覆盖第二轮指出的 Cap 运行健康、Hook 误伤度量、知识退化、配置兼容和多 provider 一致性缺口？",
    "是否还有必须在方案书阶段补齐的遗漏项？"
  ],
  "required_response": {
    "format": "json",
    "fields": [
      "verdict",
      "confidence",
      "reality_delta",
      "main_concern",
      "top_risks",
      "missing_evidence",
      "minimum_fix",
      "anti_loop_signal",
      "user_intent_alignment"
    ]
  },
  "language_policy": "中文优先；必要英文术语首次出现时解释。"
}
