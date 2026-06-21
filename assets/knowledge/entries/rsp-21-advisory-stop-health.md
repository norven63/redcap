# 建议型 Stop 健康状态不得把退化冒充健康

来源任务：RSP-21 advisory-stop degraded 健康状态治理

经验：健康门禁不能把 degraded 当作 healthy 通过；退化状态必须有原因分类、默认非零退出、显式观测开关和阻塞升级规则。

使用规则：任务前检索命中后，必须说明该经验如何影响计划、实现或验收。

## Review

- reviewer: self-purification-run-loop
- reviewed_at: 2026-06-20T17:58:13+00:00
- reason: 自我净化闭环晋升公共经验。
