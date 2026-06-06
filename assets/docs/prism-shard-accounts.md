# Prism 分片账目

Prism 分片账目用于把长任务拆成边界清楚、可验收、可合并的小单元，避免一次任务把上下文、旧仓库材料和 provider 输出全部塞进同一个窗口。

运行入口：

```bash
runtime/bin/redcap prism-shard check --account path/to/account.json
runtime/bin/redcap prism-shard merge --account path/to/account.json --out path/to/merge.json
runtime/bin/redcap prism-shard self-check
```

账号规则：

- 每个分片必须写清问题、范围、停止条件、验收标准、provider 集合、provider 会话记录和输出结构。
- `candidate_sources` 只能是精确文件，目录和通配符会被拒绝。
- 账号必须声明 `context_policy`，并固定为索引优先、禁止默认批量加载、禁止默认读取 raw 证据、大材料只能显式引用。
- 账号必须声明 `acceptance_policy`，Cap 验收是最终入口，provider 输出只能作为辅助证据。
- 每个分片必须声明 `context_budget`，限制可读来源数量、provider 最大轮次、默认加载策略和 raw 证据默认读取。
- `verified` 分片必须指向有效的 `prism-shard-output` JSON 文件。
- 分片输出只能声明读取了该分片 `candidate_sources` 中列出的文件。
- `ready_for_merge` 和 `merged` 账号不能包含未终止分片。
- Cap 仲裁必须有最大讨论轮次；达到上限后由 Cap 强制决策，不能无限循环。

这套机制是后续 360 度旧 RedCap 扫描的长任务基础。它不直接替代 provider 调度；provider 调用仍走 `prism-dispatch` 和同一任务的 Prism 会话清单。
