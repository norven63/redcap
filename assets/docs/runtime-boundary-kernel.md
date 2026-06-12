# RedCap 运行边界内核

本文件说明 RedCap（当前复活工程）如何区分自身代码、被管理项目、项目运行产物和用户私有状态。

## 四个物理位置

- RedCap 运行时根目录：当前仓库，只放 RedCap 自身代码、合同、文档和自研证据。
- 项目工作区：RedCap 正在帮助用户开发的外部项目。
- 项目运行目录：外部项目自己的 `<项目工作区>/.redcap/`，只放 RedCap 服务该项目时产生的状态、证据、日志和临时文件。
- 用户私有状态：默认 `~/.cap/`，只放身份、偏好、私密状态和跨项目个人信息。

## 旧保护为什么存在

上一版内核拒绝把外部项目证据目录放进项目工作区。它主要是在防三类问题：

- 运行证据被 `git add .` 误提交到被管理项目。
- 项目源码和 RedCap 运行产物混在一起，后续扫描时无法判断哪些是用户项目，哪些是 RedCap 过程状态。
- 外部项目的证据误流入 RedCap 仓库，导致 RedCap 自身代码被污染。

这个保护方向正确，但执行方式过粗。它把项目级运行产物赶到 `~/.cap/redcap-runtime/evidence/<项目哈希>/`，导致项目复盘、迁移、删除和验收都缺少直观的项目级边界。

## 新保护如何替代

新内核允许外部项目拥有项目级 RedCap 运行目录，但只允许一个位置：

```text
<项目工作区>/.redcap/
```

外部项目默认路径如下：

- `state_root`：`<项目工作区>/.redcap/state`
- `evidence_root`：`<项目工作区>/.redcap/evidence`
- `logs_root`：`<项目工作区>/.redcap/logs`
- `tmp_root`：`<项目工作区>/.redcap/tmp`

校验规则同步收紧：

- 外部项目工作区不能位于 RedCap 运行时根目录内。
- 外部项目的运行目录必须等于 `<项目工作区>/.redcap/`。
- 外部项目的状态、证据、日志和临时目录必须全部位于 `.redcap/` 内。
- 外部项目的状态、证据、日志和临时目录不能位于 RedCap 运行时根目录内。
- 用户私有状态不能位于 RedCap 仓库、项目工作区或项目 `.redcap/` 内。
- 任务文件不能位于项目 `.redcap/` 内。

## 自研例外

自研例外只用解析后的真实路径做判断：

```text
project_workspace.resolve() == runtime_root.resolve()
```

只有这个条件成立，且当前工作目录位于 RedCap 运行时根目录内，才进入 `self-development` 模式。该模式允许 RedCap 把自研证据留在 `assets/evidence/`，但不允许把外部项目伪装成 RedCap 自研任务。

## 旧证据位置

旧内核曾把外部项目证据放在：

```text
~/.cap/redcap-runtime/evidence/<项目哈希>/
```

新内核不会自动迁移这类旧证据。原因是旧目录可能混有历史会话、私有状态或已经失效的中间产物，自动搬迁容易制造新的污染。边界解析结果会继续暴露 `legacy_external_evidence_root` 字段，供后续专门的证据恢复工具按项目、按证据清单、按人工许可迁移。

## `.redcap` 误提交防护

`runtime/bin/redcap boundary init` 会创建项目 `.redcap/` 及其子目录，并写入：

```gitignore
*
!.gitignore
```

这样即使用户在被管理项目中运行 `git add .`，运行状态、证据、日志和临时文件也不会被默认加入版本历史。边界检查会在 `.redcap/` 已存在但缺少保护性 `.gitignore` 时失败。

## 命令入口

```bash
runtime/bin/redcap boundary resolve
runtime/bin/redcap boundary check
runtime/bin/redcap boundary init
runtime/bin/redcap boundary self-check
```

`resolve` 只解析路径。`check` 校验边界。`init` 创建项目级运行目录。`self-check` 同时验证外部项目、自研例外、私有状态泄漏和错误运行目录覆盖会被正确处理。
