# md-table-tool benchmark carrier

这是 RedCap 的 repo-owned 基准用户项目载体，用来承接 `loom/test-reports/benchmark-scenario.md` 中定义的完整用户项目 E2E。

用途：

1. 让 `pending-validations.md` 里的 V-2 / V-3 / V-4 / V-6 / V-7 / V-8 / V-9 不再依赖“临时找一个真实用户项目”。
2. 保持跨版本可重放的固定需求、样例输入和启动提示。
3. 作为完整用户项目 E2E tranche 的起点，而不是直接冒领“已验证”。

使用方式：

```bash
bash loom/tools/redcap-e2e-benchmark-carrier.sh init /tmp/md-table-tool-benchmark
```

然后在目标目录中，按照 `REQUEST.md` 启动一次完整用户项目 E2E；真正消费 pending-validations 之前，仍必须满足：

- 创建并消费 `loom/test-reports/e2e-session.yaml`
- 更新 `loom/test-reports/latest-e2e-report.md`
- 处理 `pending-validations.md`
- 通过 `loom/tools/redcap-e2e-postcheck.sh`
