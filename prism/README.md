# 棱镜（Prism）

> 多视角协同分析引擎 — RedCap 底层公共能力

---

## 是什么

棱镜是 RedCap 的多 Agent 协同分析子系统。当一个视角不足以得出可信结论时，棱镜将问题"折射"成多束光，让不同模型/视角独立分析，再将结论汇聚成行动指南。

就像棱镜对白光的作用：单色看起来清晰，但经过棱镜才能看见全光谱。

---

## 何时使用

| 情境 | 推荐模式 |
|------|---------|
| 架构决策需要多角度验证 | `explore`（探索） |
| 提交前发现潜在风险 | `redteam`（红队） |
| Agent 连续两轮卡壳，观点分歧 | `council`（议事） |
| soul.md / CONTRIBUTING.md 大改后验证 | `test`（测试） |

**不需要用棱镜的情况**：单一明确任务、改动 <3 个文件且 <20 行、已有 §8/§9 足够的场合。

---

## 快速调用

```
触发：在任务描述中说明需要棱镜，或 Cap 自主判断
模式：explore | redteam | council | test
产出：prism/reports/YYYYMMDD-{mode}-NNN.md + index.yaml 更新
```

详细协议见 → `protocol.md`  
模式说明见 → `modes/README.md`

---

## 设计原则

1. **独立性优先**：各 Agent 在执行阶段不能读取彼此的中间产出（Dispatch Firewall）
2. **落盘保鲜**：所有产出持久化至 `reports/`，git 追踪，跨会话可读
3. **可移植**：不绑定 RedCap 特定逻辑，可迁移至其他框架
4. **有终点**：每种模式都有明确的完成条件，防止无限循环

---

## 与现有机制关系

```
CONTRIBUTING.md §8  →  Prism explore 模式（≥5模块并行分析时优先用此）
CONTRIBUTING.md §9  →  Prism redteam 模式（跨家族模型审查时优先用此）
新增 CONTRIBUTING.md §11  →  棱镜集成指南（见 §11 引用）
```

§8/§9 原有文本保持不变，作为速查版本；棱镜是系统化版本，适用于高后果决策。
