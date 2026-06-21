# Hook 意图矩阵必须保守处理语义失败

来源任务：RSP-02 Hook 语义意图矩阵实现

经验：Hook 意图判断不能只依赖硬规则枚举，也不能把裁决无条件交给 LLM；高风险歧义请求在语义评审失败时必须显式 degraded，并保守转为非变更裁决，防止静默放行。

使用规则：任务前检索命中后，必须说明该经验如何影响计划、实现或验收。

## Review

- reviewer: self-purification-run-loop
- reviewed_at: 2026-06-20T17:45:24+00:00
- reason: 自我净化闭环晋升公共经验。
