# E2E 验证报告

> 每次 E2E 执行后更新此文件。仅保留最近一次完整报告，旧报告直接覆盖（精华已融入 lessons.md 和 pending-validations.md）。

## 最近一次 E2E

**日期**：2026-04-07  
**项目**：trpg-web（TRPG 角色卡管理器）— 旧基准项目，已替换为 md-table-tool  
**执行者**：Cap（Dispatcher）  
**框架版本**：commit `928ab33` 之前的版本  

### 覆盖范围

| 路径 | 状态 | 备注 |
|------|------|------|
| PM_WORKING → PM_DONE | ✅ 通过 | 需求采集完整 |
| ARCH_WORKING → ARCH_DONE | ✅ 通过 | 架构设计输出完整 |
| DEV_WORKING → DEV_DONE | ✅ 通过 | 代码可运行 |
| QA_WORKING → QA_DONE | ✅ 通过 | 测试通过 |
| REVIEW_WORKING → REVIEW_DONE | ✅ 通过 | 独立评审完成 |
| QA_FAIL → DEV_WORKING 回退 | ❌ 未测 | — |
| QA_FAIL → ARCH_WORKING 回退 | ❌ 未测 | — |
| ESCALATE_L1/L2 升级 | ❌ 未测 | — |
| PAUSED → Resume | ❌ 未测 | — |

### 核心发现

1. **outbox 文件交付**：100% 可靠（所有角色均正确写入 outbox）
2. **`__redcap_status` stdout 嵌入**：0% 合规（所有 Agent 均未在 stdout 末尾嵌入 JSON）
3. **Dispatcher 代劳率**：~60%（9/15 Session 由 Dispatcher 手动执行，触发 L-4）
4. **回退路径**：0% 覆盖（正向流转全量测试，非正常路径完全未触及）

### 产出的经验条目

- L-21: CLI 独立 Agent 可靠性仍是根本瓶颈
- L-22: __redcap_status outbox 文件模式 100% 可靠
- L-23: 文件管道为主、stdout 为辅（双管齐下）

### 遗留问题

参见 `testing/pending-validations.md` 中 V-1 ~ V-9 的 🔴 待验证条目。

---

> 下次 E2E 执行时，从 `testing/pending-validations.md` 获取待验证清单，对照 `testing/benchmark-scenario.md` 的验证矩阵执行。
