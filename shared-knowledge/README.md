# RedCap Shared Knowledge Repository Template

> 这是未来独立公共知识库/沉淀库的本地模板。它证明目录、schema、append-only 写入、索引和重复识别入口可运行；远端 Gitee 仓库绑定需要用户后续提供 remote。

## 目录约定

| 路径 | 作用 |
|---|---|
| `users/<user>/` | 按用户隔离的沉淀条目。条目文件必须以 UTC 时间戳开头，只新增不改旧文件 |
| `indexes/` | 可再生成索引或追加式审计快照 |
| `schemas/entry.schema.json` | 条目字段、kind 和 append-only 约束 |

## 使用入口

```bash
bash compass/tools/redcap-shared-knowledge.sh init --root shared-knowledge
bash compass/tools/redcap-shared-knowledge.sh append --root shared-knowledge --user norven --kind lesson --title "example" --body-file /tmp/body.md
bash compass/tools/redcap-shared-knowledge.sh index --root shared-knowledge
bash compass/tools/redcap-shared-knowledge.sh check --root shared-knowledge
```

## 读取原则

- 先读索引，不默认打开 `users/**` 全文。
- 先查重复，再新增沉淀。
- 条目是证据和方法论沉淀，不承担当前任务真相源；当前任务真相源仍是 `.dev-task.md`、报告、receipt 和 validator 证据。
