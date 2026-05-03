# RedCap Arsenal Template

> 这是 RedCap 公共知识库/沉淀库 `redcap-arsenal` 的最小安全模板。当前绑定远端为 `https://gitee.com/norven63/redcap-arsenal.git`；在 RedCap 仓库中，`shared-knowledge/` 只是模板源，所以刻意没有 `.git`。实体公共库工作区由 `references/shared-knowledge-remote-binding.json` 的 `preferred_local_worktree` 配置，默认应位于 RedCap 仓库外。

## 目录约定

| 路径 | 作用 |
|---|---|
| `users/<user>/` | 按用户隔离的沉淀条目。条目文件必须以 UTC 时间戳开头，只新增不改旧文件 |
| `users/Norven/` | 当前安装的初始用户命名空间占位 |
| `indexes/` | 可再生成索引或追加式审计快照 |
| `schemas/entry.schema.json` | 条目字段、kind 和 append-only 约束 |
| `.gitignore` | 公共库安全边界，阻止 `.env`、密钥和临时文件进入远端 |

## 使用入口

```bash
bash compass/tools/redcap-shared-knowledge.sh init --root ../redcap-arsenal
bash compass/tools/redcap-shared-knowledge.sh append --root ../redcap-arsenal --user Norven --kind lesson --title "example" --body-file /tmp/body.md
bash compass/tools/redcap-shared-knowledge.sh index --root ../redcap-arsenal
bash compass/tools/redcap-shared-knowledge.sh check --root ../redcap-arsenal
```

## 读取原则

- 先读索引，不默认打开 `users/**` 全文。
- 先查重复，再新增沉淀。
- 条目是证据和方法论沉淀，不承担当前任务真相源；当前任务真相源仍是 `.dev-task.md`、报告、receipt 和 validator 证据。
- 远端同步前先跑 `bash compass/tools/redcap-shared-knowledge-remote-check.sh`；需要验证 Gitee 当前 head 和本机实体工作区时再加 `--live --require-worktree`。
