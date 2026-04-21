# 基准请求

请把当前目录当成一个新的用户项目工作区，按 `loom/test-reports/benchmark-scenario.md` 的固定场景执行完整用户项目 E2E。

项目需求：

- 项目名：`md-table-tool`
- 技术栈：Node.js + TypeScript
- 目标：实现一个 CLI 工具，读取 Markdown 文件中的表格，并转换为 JSON / CSV

命令行目标：

```text
md-table-tool convert input.md -o output.json --format json
md-table-tool convert input.md -o output.csv --format csv --columns "name,age"
md-table-tool convert input.md -o output.json --filter "age>18"
```

执行要求：

1. 启动前按 `compass/CONTRIBUTING.md §3.1` 创建 `loom/test-reports/e2e-session.yaml`（推荐使用 `bash loom/tools/redcap-e2e-session.sh start ...`）
2. 使用 `loom/test-reports/benchmark-scenario.md` 中的 preset / switches
3. 完成后更新 `loom/test-reports/latest-e2e-report.md`
4. 如命中验证项，消费 `loom/test-reports/pending-validations.md`
5. 最后运行 `bash loom/tools/redcap-e2e-postcheck.sh`
