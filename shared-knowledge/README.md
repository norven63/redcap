# RedCap Arsenal Template

> 这是 RedCap 公共知识库/沉淀库 `redcap-arsenal` 的最小安全模板。当前绑定远端为 `https://gitee.com/norven63/redcap-arsenal.git`；在 RedCap 仓库中，`shared-knowledge/` 只是模板源，所以刻意没有 `.git`。真实公共库工作区应由 RedCap 安装环境配置，并位于 RedCap 工程目录之外。
>
> 公共条目必须先经过 `RedCap Forge`：把私有报告、lessons、失败链路或 Prism verdict 蒸馏、脱敏、去重、结构化和索引化之后，才允许 append 到 `redcap-arsenal`。原始报告、identity、runtime evidence 和私有 knowledge 不得直接进入公共库。
>
> 本目录状态：template-source。它只保存公共库模板、schema 和安全边界，不能冒充真实公共库工作区。
>
> 外部 `redcap-arsenal` 绑定状态：reviewed-substantive。当前本机绑定的公共库工作区已经有首批经过 RedCap Forge 风格审查的 append-only 公共沉淀条目；但不能声称已有历史知识批量迁移、已填充成熟公共知识库、已形成成熟公共 skill arsenal，或已经证明 RedCap public release ready。

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
- 先过 RedCap Forge，不直接搬运私有原文。
- 条目是证据和方法论沉淀，不承担当前任务真相源；当前任务真相源仍是 `.dev-task.md`、报告、receipt 和 validator 证据。
- 远端同步前先跑 `bash compass/tools/redcap-shared-knowledge-remote-check.sh`；需要验证 Gitee 当前 head 和本机实体工作区时再加 `--live --require-worktree`。
