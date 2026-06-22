# Cap 灵魂加载器

Cap 灵魂加载器负责把当前 RedCap 工作区连接到私有 Cap 身份源，同时不把私有人格原始内容复制进项目证据。

## 运行入口

- 入口命令：`runtime/bin/redcap soul-load`
- 实现文件：`runtime/core/soul_loader.py`
- 运行证据：
  - `.redcap/evidence/soul/latest-load.json`
  - `.redcap/evidence/soul/load-ledger.jsonl`

## 来源策略

当 `CAP_HOME` 已设置时，加载器把 `$CAP_HOME/identity.md` 作为必需身份源。若 `CAP_HOME` 未设置，则回退到 `~/.cap/identity.md`。旧 AGENTS（代理说明文件）引用的 `~/.codex/skills/redcap/soul.md` 是可选来源，因为这个复活后的工作区里可能不存在它。

如果 `CAP_HOME` 已设置，但目录不存在、缺少 `identity.md`、`identity.md` 为空、`identity.md` 不是普通文件，或当前进程无法读取它，加载器必须报告加载受阻，不能悄悄回退到另一个用户的身份文件。这样可以让多用户机器和迁移后的电脑保持边界明确。

证据记录只允许包含来源状态、哈希、行数、标题存在状态和脱敏计数。证据中不得包含私有身份原始内容、真实私有标题正文、真实私有身份绝对路径或疑似密钥内容。

## 命令

```bash
runtime/bin/redcap soul-load check
runtime/bin/redcap soul-load load --json
runtime/bin/redcap soul-load portability-check
runtime/bin/redcap soul-load self-check
```

`runtime/bin/redcap check` 会运行来源检查和隔离自检。Codex（当前宿主开发环境）的 `SessionStart`（会话启动）钩子也会调用加载器，让后续 RedCap 会话真正尝试加载 Cap，而不是只停留在协议提醒。
