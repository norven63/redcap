# Prism Report: 飞书完成通知单出口收敛

- run_id: `20260508-feishu-closeout-single-node-report`
- mode: `acceptance-review`
- date: 2026-05-08
- agents: Claude Code + Kimi
- verdict: pass

## 结论

Claude Code 与 Kimi 都认可本轮修复：Layer B 正常完成路径由 closeout runtime 在 receipt/summary 写入后统一发送唯一一次 `node-report`，closeout 内部调用 `redcap-on-complete.sh` 时必须设置 `REDCAP_SKIP_FEISHU=1`，避免 on-complete 提前发送第一条完成通知。

## 共识边界

- 正常 closeout 完成路径只保留 closeout runtime 一个最终 node-report 出口。
- standalone `redcap-on-complete.sh` 保留兼容通知能力，不被本轮删除。
- `session-end` 成功通知在 closeout runtime 路径内继续静音，不恢复刷屏。
- 若最终 node-report 发送失败，closeout runtime 必须写 pending-closure 并阻塞完成态，不能伪装完成。
- 本轮不改变飞书账号、通道、消息格式或 manual-intervention 语义。

## 已吸收动作

- `redcap-layerb-closeout-runtime.py` 在内部调用 on-complete 时显式注入 `REDCAP_SKIP_FEISHU=1`。
- closeout runtime 在 receipt/summary 写入后调用 `feishu-notifier.py notify --window-type node-report`。
- acceptance 用 fake notifier 验证 on-complete 被静音、closeout 只发送一次、发送时 receipt/summary 已存在。
- 飞书策略检查要求 closeout runtime 拥有最终 Layer B node-report，同时保留 standalone on-complete 兼容路径。

## 风险说明

- 如果调用者显式设置 `REDCAP_SKIP_FEISHU=1` 或 `REDCAP_SKIP_CLOSEOUT_NODE_REPORT=1`，closeout 最终通知会被跳过；这属于显式静音语义，不是重复通知漏洞。
- 该机制依赖 closeout runtime 继续设置静音环境变量；策略检查已把这些变量作为静态门禁，降低未来重构回归风险。

## 证据

- Raw outputs: `prism/runs/20260508-feishu-closeout-single-node-report/collect/*`
- Parsed verdicts: `prism/runs/20260508-feishu-closeout-single-node-report/collect/*/parsed.json`
- Acceptance binding: `prism/runs/20260508-feishu-closeout-single-node-report/artifacts/acceptance-binding.json`
