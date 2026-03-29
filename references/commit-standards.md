# Commit 规范

> **用途**：项目 Agent 在 `on_QA_PASS` hook 执行 git commit 时必须遵守本规范。
> **适用范围**：所有通过 RedCap 开发的项目。

---

## 格式

```
type(scope): 简要描述

正文（可选，说明动机和关键变更）
```

- **首行**（subject line）：≤ 72 字符，不以句号结尾
- **正文**：空一行后开始，每行 ≤ 100 字符，说明「为什么」而非「做了什么」
- **语言**：中文为主，技术术语保留英文原文

## type 取值

| type | 用途 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(支付): 接入微信支付回调` |
| `fix` | 缺陷修复 | `fix(鉴权): 修复 token 过期后未刷新` |
| `refactor` | 重构（不改变外部行为） | `refactor(数据层): 统一 DAO 接口` |
| `docs` | 文档变更 | `docs(API): 更新接口文档` |
| `test` | 测试相关 | `test(支付): 补充退款边界测试` |
| `chore` | 构建、依赖、配置 | `chore: 升级 Node 到 v20` |
| `style` | 格式调整（不影响逻辑） | `style: 统一缩进为 2 空格` |
| `perf` | 性能优化 | `perf(查询): 添加索引优化慢查询` |

## scope 取值

scope 由项目架构决定，通常为模块名或功能域。进度日志中的「当前步骤名」是最佳来源。

示例：`支付模块`、`用户鉴权`、`数据库`、`CI`

## 末尾标记

每条 commit message 末尾追加 `作者:redcap`，标识为框架自动提交。

## Dispatcher 执行规则

- commit 仅在 `on_QA_PASS` hook 中执行，由 Dispatcher 调用 `git add -A && git commit`
- Dispatcher **不得自动 push**，仅在用户明确指示时执行
- commit message 由 Dispatcher 根据本步骤 Agent 产出的 summary 生成
