# Spec 生命周期与准入规范

> **用途**：给 `compass/docs/specs/**` 与 `compass/docs/archive/specs/**` 的新增、替换、归档提供统一规则。
> **机器执行**：`compass/tools/redcap-spec-check.sh`
> **机器策略源**：`references/spec-lifecycle-policy.json`

---

## 1. 先判断这份 spec 放哪里

| 状态 | 应放位置 | 说明 |
|---|---|---|
| `active` | `compass/docs/specs/` | 当前仍在使用、仍会被后续任务直接引用的 spec |
| `reference` | `compass/docs/specs/` 或 `compass/docs/archive/specs/` | 仍值得保留给人阅读，但不再是当前主线入口 |
| `superseded` | `compass/docs/archive/specs/` | 已被新版替代，必须声明由哪份新 spec 接手 |

**红线**：
1. `superseded` spec 不允许继续留在 `compass/docs/specs/`
2. `superseded` spec 必须在 `references/spec-registry.json` 里声明 `replaced_by`
3. `replaced_by` 只能指向已登记、真实存在的 spec 文件

---

## 2. 文件名规范

统一使用 **小写 kebab-case**：

- 允许：`2026-04-13-framework-upgrade-backlog-design.md`
- 允许：`baton-design.md`
- 允许：`engine-upgrade-part2-execution-framework.md`
- 禁止：`BadName_Underscore.md`
- 禁止：`SpecDraft.md`

---

## 3. role（角色）合法值

| role | 含义 |
|---|---|
| `design-snapshot` | 已批准或已冻结的设计快照 |
| `human-guide` | 给 Norven 阅读的人类说明文档 |
| `operator-guide` | 给操作者阅读的运行/使用指南 |

若新增新的 role，必须先更新 `references/spec-lifecycle-policy.json`，再更新 registry 与检查脚本。

---

## 4. registry（登记表）必填规则

每份 spec 在 `references/spec-registry.json` 中至少要说明：

1. `path`：文件路径
2. `title`：人类可读标题
3. `role`：它扮演什么角色
4. `status`：它当前所处生命周期状态
5. `runtime_authority: false`：明确它不是运行时权威
6. `summary`：一句说人话的摘要
7. `paired_control_paths` 或 `paired_debt_ids`：它对应哪条执行链或治理债务

若是 `superseded`，还要补：

- `replaced_by`：哪份新 spec 接手了它

---

## 5. 这条规范解决什么问题

它解决的不是“怎么写好看”，而是两类治理缺口：

1. **spec 生命周期缺口**：旧 spec 不再无限留在 `compass/docs/specs/` 冒充当前入口
2. **规范到 gate 的翻译缺口**：spec 的状态、角色、落点与替代关系，能够被 `redcap-spec-check.sh` 真正检查，而不是只写在说明文档里
