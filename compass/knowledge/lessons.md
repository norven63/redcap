# RedCap 框架级经验库（Framework Lessons Learned）

> 本文件是经验库首读索引，不承载完整正文。先按热点簇或 L-编号定位，再打开 `compass/knowledge/lessons/<l-id>.md` 精读，避免新会话默认加载巨型经验库。
>
> 模块数：152；正文集合 sha256：c9f48a0a8496a799550a8c1b52840c31f20a1f2ca8371ed0e14c7cb1a0e2cd53。

## 热点主题速览

- **收尾 / 账面一致性**：L-54、L-56~L-61、L-70~L-74、L-86~L-93、L-109、L-118、L-124、L-135、L-148。
- **宿主 / Hook / runtime 边界**：L-15、L-16、L-39、L-41~L-49、L-62~L-69、L-77~L-90、L-155。
- **docs / knowledge / token 风险**：L-50~L-52、L-64~L-66、L-91~L-97、L-122、L-132、L-134、L-150~L-154。
- **评审 / 对抗 / 执行保障**：L-24、L-30、L-32~L-34、L-53、L-91~L-97、L-110、L-124、L-135、L-156。

## 使用规则

- 不要默认 bulk-read `compass/knowledge/lessons/**`。
- `lessons.md#l-xxx` 旧引用会落到下面的短锚点；正文以模块文件为准。
- 新增 lesson 时新增模块文件，并同步本索引、`compass/knowledge/index.md` 与 token-risk 结构治理。

## Lesson 模块索引与旧锚点

> 每个标题保留旧锚点；标题下只放正文模块链接，不复制正文。

### L-4: Agent Fallback 深度不足导致铁律系统性违反
- 正文模块：[`compass/knowledge/lessons/l-4.md`](../../compass/knowledge/lessons/l-4.md)

### L-5: Agent 超时应优先从自身调用方式排查
- 正文模块：[`compass/knowledge/lessons/l-5.md`](../../compass/knowledge/lessons/l-5.md)

### L-6: 模型检测应在项目初始化时完成并缓存
- 正文模块：[`compass/knowledge/lessons/l-6.md`](../../compass/knowledge/lessons/l-6.md)

### L-7: Gemini `--approval-mode auto_edit` 在 headless 模式会永久挂起
- 正文模块：[`compass/knowledge/lessons/l-7.md`](../../compass/knowledge/lessons/l-7.md)

### L-8: 框架变更必须"先测再改"——实测驱动而非假设驱动
- 正文模块：[`compass/knowledge/lessons/l-8.md`](../../compass/knowledge/lessons/l-8.md)

### L-9: 长任务上下文压缩导致框架规则退化——必须用文件重读对冲
- 正文模块：[`compass/knowledge/lessons/l-9.md`](../../compass/knowledge/lessons/l-9.md)

### L-11: Gemini CLI `--output-format json` 长任务下进程不退出但文件已落盘
- 正文模块：[`compass/knowledge/lessons/l-11.md`](../../compass/knowledge/lessons/l-11.md)

### L-12: 指令注入≠执行保证——关键动作必须用脚本/Hooks 而非纯文本指令
- 正文模块：[`compass/knowledge/lessons/l-12.md`](../../compass/knowledge/lessons/l-12.md)

### L-13: Review 必须显式声明检查维度——结构检查≠设计质量检查
- 正文模块：[`compass/knowledge/lessons/l-13.md`](../../compass/knowledge/lessons/l-13.md)

### L-14: 配置格式文档必须与实际配置文件交叉验证
- 正文模块：[`compass/knowledge/lessons/l-14.md`](../../compass/knowledge/lessons/l-14.md)

### L-15: 需认知的关键动作用 Hook + 新 Agent 生命周期兜底
- 正文模块：[`compass/knowledge/lessons/l-15.md`](../../compass/knowledge/lessons/l-15.md)

### L-16: Hook 设计≠部署≠生效——部署链每个环节必须端到端验证
- 正文模块：[`compass/knowledge/lessons/l-16.md`](../../compass/knowledge/lessons/l-16.md)

### L-17: Agent 无法自主发现自身未知的项目资产——排查指引必须显式写入提示词
- 正文模块：[`compass/knowledge/lessons/l-17.md`](../../compass/knowledge/lessons/l-17.md)

### L-18: Agent 间对等讨论优于单向指令——A2A 协作应以共识驱动而非命令驱动
- 正文模块：[`compass/knowledge/lessons/l-18.md`](../../compass/knowledge/lessons/l-18.md)

### L-19: Dispatcher 代劳时 state.yaml 维护纪律会系统性下降
- 正文模块：[`compass/knowledge/lessons/l-19.md`](../../compass/knowledge/lessons/l-19.md)

### L-20: Agent CLI headless 模式的稳定性是多 Agent 协同的实际瓶颈
- 正文模块：[`compass/knowledge/lessons/l-20.md`](../../compass/knowledge/lessons/l-20.md)

### L-22: Layer B 大型任务缺乏断点续传——会话坏死后靠"考古"恢复 ⚙️ 已硬化
- 正文模块：[`compass/knowledge/lessons/l-22.md`](../../compass/knowledge/lessons/l-22.md)

### L-23: Agent 通信协议应以文件管道为主、stdout 嵌入为辅 ⚙️ 已硬化
- 正文模块：[`compass/knowledge/lessons/l-23.md`](../../compass/knowledge/lessons/l-23.md)

### L-24: Layer B 设计阶段缺少前置对抗（Red Teaming），"不可行"判断需 Pre-mortem 挑战 ⚙️ 已硬化
- 正文模块：[`compass/knowledge/lessons/l-24.md`](../../compass/knowledge/lessons/l-24.md)

### L-25: E2E 后置处理必须严格执行——§3.1 最小产出物缺一不可 ⚙️ 已硬化
- 正文模块：[`compass/knowledge/lessons/l-25.md`](../../compass/knowledge/lessons/l-25.md)

### L-26: E2E 预设必须物理锁定——用户指令与实际执行之间不允许漂移
- 正文模块：[`compass/knowledge/lessons/l-26.md`](../../compass/knowledge/lessons/l-26.md)

### L-27: 同一人格双实例差异对比可作为跨载体机制自检手段
- 正文模块：[`compass/knowledge/lessons/l-27.md`](../../compass/knowledge/lessons/l-27.md)

### L-28: 静态源码审计不等于运行时行为——"不可行"结论必须经实测验证
- 正文模块：[`compass/knowledge/lessons/l-28.md`](../../compass/knowledge/lessons/l-28.md)

### L-29: Hook + 子 Agent CLI 模式——同时获得 100% 触发保证 + LLM 认知质量
- 正文模块：[`compass/knowledge/lessons/l-29.md`](../../compass/knowledge/lessons/l-29.md)

### L-30: 并行分析 Agent 的结论必须经独立 Red Teaming 才能用于实施决策
- 正文模块：[`compass/knowledge/lessons/l-30.md`](../../compass/knowledge/lessons/l-30.md)

### L-31: 长任务需求漂移——执行期注意力衰减导致偏离原始需求
- 正文模块：[`compass/knowledge/lessons/l-31.md`](../../compass/knowledge/lessons/l-31.md)

### L-32: 协议文档的"强制"≠机器强制——设计意图必须有执行闸门
- 正文模块：[`compass/knowledge/lessons/l-32.md`](../../compass/knowledge/lessons/l-32.md)

### L-33: 协议先 Pilot 再固化——文档假设不能代替实测记录
- 正文模块：[`compass/knowledge/lessons/l-33.md`](../../compass/knowledge/lessons/l-33.md)

### L-34: 评审提示词需覆盖"假设但未实现"检查——不只是找错
- 正文模块：[`compass/knowledge/lessons/l-34.md`](../../compass/knowledge/lessons/l-34.md)

### L-35: 约束驱动的系统性排错——向 distill 借鉴"不变量优先"思维
- 正文模块：[`compass/knowledge/lessons/l-35.md`](../../compass/knowledge/lessons/l-35.md)

### L-36: "技术债"标签容易成为推迟简单工作的借口——先估实现成本再贴标签
- 正文模块：[`compass/knowledge/lessons/l-36.md`](../../compass/knowledge/lessons/l-36.md)

### L-37: git mv 时目标目录已存在会导致内容嵌套而非覆盖
- 正文模块：[`compass/knowledge/lessons/l-37.md`](../../compass/knowledge/lessons/l-37.md)

### L-38: 三体架构脚本路径规则——REDCAP_ROOT = SCRIPT_DIR/../..
- 正文模块：[`compass/knowledge/lessons/l-38.md`](../../compass/knowledge/lessons/l-38.md)

### L-39: Copilot CLI sessionStart Hook 不暴露 sessionId 字段
- 正文模块：[`compass/knowledge/lessons/l-39.md`](../../compass/knowledge/lessons/l-39.md)

### L-40: Session 续接能力 ≠ Prism Collect 追问能力
- 正文模块：[`compass/knowledge/lessons/l-40.md`](../../compass/knowledge/lessons/l-40.md)

### L-41: Hook 能力存在 ≠ 已部署 ≠ 已生效
- 正文模块：[`compass/knowledge/lessons/l-41.md`](../../compass/knowledge/lessons/l-41.md)

### L-42: Hook stdout 契约必须按宿主隔离，不能复用 Gemini 的 allow JSON
- 正文模块：[`compass/knowledge/lessons/l-42.md`](../../compass/knowledge/lessons/l-42.md)

### L-43: 宿主 Agent 内运行 RedCap 时，必须防 authority inversion
- 正文模块：[`compass/knowledge/lessons/l-43.md`](../../compass/knowledge/lessons/l-43.md)

### L-44: `session_binding_key` 只负责定位，恢复写权限必须显式过 capability gate
- 正文模块：[`compass/knowledge/lessons/l-44.md`](../../compass/knowledge/lessons/l-44.md)

### L-45: closure/notified 成功标记必须绑定到关键副作用真正完成，不能在“尝试过”时提前写入
- 正文模块：[`compass/knowledge/lessons/l-45.md`](../../compass/knowledge/lessons/l-45.md)

### L-46: 跨会话 owner lease 必须在 EXIT 级清理，不能只在成功路径释放
- 正文模块：[`compass/knowledge/lessons/l-46.md`](../../compass/knowledge/lessons/l-46.md)

### L-47: delegation 文件边界必须校验真实路径，不能只看字符串前缀
- 正文模块：[`compass/knowledge/lessons/l-47.md`](../../compass/knowledge/lessons/l-47.md)

### L-48: 宿主通用 skill 只能是 overlay，不能把可自治决策升级成人工阻断
- 正文模块：[`compass/knowledge/lessons/l-48.md`](../../compass/knowledge/lessons/l-48.md)

### L-49: 共享宿主 skill 不是 RedCap 可修改资产
- 正文模块：[`compass/knowledge/lessons/l-49.md`](../../compass/knowledge/lessons/l-49.md)

### L-50: docs / artifact 审计若只看内容正确性，会漏掉目录边界与生命周期污染
- 正文模块：[`compass/knowledge/lessons/l-50.md`](../../compass/knowledge/lessons/l-50.md)

### L-51: 收尾消息必须能直接抽取报告开头的重点摘要，不能只给报告路径
- 正文模块：[`compass/knowledge/lessons/l-51.md`](../../compass/knowledge/lessons/l-51.md)

### L-52: Validator / gate 脚本必须验证失败退出码，不能只看错误输出
- 正文模块：[`compass/knowledge/lessons/l-52.md`](../../compass/knowledge/lessons/l-52.md)

### L-53: 质量关键审查若卡住，必须做等同质量回收，不能因等待而降级
- 正文模块：[`compass/knowledge/lessons/l-53.md`](../../compass/knowledge/lessons/l-53.md)

### L-54: closure obligation 的终态必须与原 identity 绑定，且不能先 clear 再处理晚到红线
- 正文模块：[`compass/knowledge/lessons/l-54.md`](../../compass/knowledge/lessons/l-54.md)

### L-55: 把独立 gate 收口到 validator chain 时，preflight / contract-break 失败也必须留下 closure 证据
- 正文模块：[`compass/knowledge/lessons/l-55.md`](../../compass/knowledge/lessons/l-55.md)

### L-56: closure 入口接入 validator chain 时，必须同时统一判定、redline 映射与 step-level ledger
- 正文模块：[`compass/knowledge/lessons/l-56.md`](../../compass/knowledge/lessons/l-56.md)

### L-57: obligation reconcile 入口必须能权威重写 blocker 集，不能让 redline 只会并集膨胀
- 正文模块：[`compass/knowledge/lessons/l-57.md`](../../compass/knowledge/lessons/l-57.md)

### L-58: closure 证据写失败本身就是 blocker，不能“判定正确但持久化缺失”后仍按成功收尾
- 正文模块：[`compass/knowledge/lessons/l-58.md`](../../compass/knowledge/lessons/l-58.md)

### L-59: authority 脚本的 fail-closed 退出码，不能在宿主分发器里被吞掉
- 正文模块：[`compass/knowledge/lessons/l-59.md`](../../compass/knowledge/lessons/l-59.md)

### L-60: 补偿 warning 与失败 alert 必须使用独立去重 marker，不能共用 `ALERTED_FILE`
- 正文模块：[`compass/knowledge/lessons/l-60.md`](../../compass/knowledge/lessons/l-60.md)

### L-61: advisory 的 auto-reconcile 只能消费“当前可证明且 identity 匹配”的 blocker，不能把 SessionStart 做成隐式清账闸门
- 正文模块：[`compass/knowledge/lessons/l-61.md`](../../compass/knowledge/lessons/l-61.md)

### L-62: continuity authority 必须先落 repo-local manifest，再渲染宿主 mirror；缺 runtime id 时只能显式降级
- 正文模块：[`compass/knowledge/lessons/l-62.md`](../../compass/knowledge/lessons/l-62.md)

### L-63: session resume gate 必须先判 isolation mode；`continuity_state` 不能代替宿主隔离能力
- 正文模块：[`compass/knowledge/lessons/l-63.md`](../../compass/knowledge/lessons/l-63.md)

### L-64: 面向 Norven 的汇报若依赖内部黑话而不解释，理解率会断崖式下降
- 正文模块：[`compass/knowledge/lessons/l-64.md`](../../compass/knowledge/lessons/l-64.md)

### L-65: 长期路线如果只留在说明文档里，状态很快就会陈旧；必须拆成“机器权威 + 人类说明”
- 正文模块：[`compass/knowledge/lessons/l-65.md`](../../compass/knowledge/lessons/l-65.md)

### L-66: 进度汇报若不先交代“现在、上一刀、下一刀、全局位置”，人类会很难接管评审
- 正文模块：[`compass/knowledge/lessons/l-66.md`](../../compass/knowledge/lessons/l-66.md)

### L-67: 任何断言“当前没有 runtime claim”的 acceptance，都必须在 case 内自行清上下文
- 正文模块：[`compass/knowledge/lessons/l-67.md`](../../compass/knowledge/lessons/l-67.md)

### L-68: Copilot hook 没有 sessionId 时，可用 `session-state + inuse.<pid>.lock` 补出 repo-owned 身份锚点
- 正文模块：[`compass/knowledge/lessons/l-68.md`](../../compass/knowledge/lessons/l-68.md)

### L-69: `sessionStart / sessionEnd` 已经落地，不等于 `task-complete` 自动收尾也已经落地
- 正文模块：[`compass/knowledge/lessons/l-69.md`](../../compass/knowledge/lessons/l-69.md)

### L-70: 报告锚点校验不能停留在 glob / `-f` 层
- 正文模块：[`compass/knowledge/lessons/l-70.md`](../../compass/knowledge/lessons/l-70.md)

### L-71: 锁格式升级不能只做 stale prune，还要考虑 live legacy holder 与 PID reuse 的并存
- 正文模块：[`compass/knowledge/lessons/l-71.md`](../../compass/knowledge/lessons/l-71.md)

### L-72: pending anchor 的放行条件必须是“唯一最新 changed report”，不能只看它是否曾经 changed 过
- 正文模块：[`compass/knowledge/lessons/l-72.md`](../../compass/knowledge/lessons/l-72.md)

### L-73: task-report-register 这类 closeout 入口必须区分 live claim 与显式 runtime env 的权威级别
- 正文模块：[`compass/knowledge/lessons/l-73.md`](../../compass/knowledge/lessons/l-73.md)

### L-74: marker anchor 与 pending anchor 不能有两套 stale 语义
- 正文模块：[`compass/knowledge/lessons/l-74.md`](../../compass/knowledge/lessons/l-74.md)

### L-75: acceptance 要锁定目标性质，不能把 root worktree / 当前 HEAD 偶然状态写成硬编码断言
- 正文模块：[`compass/knowledge/lessons/l-75.md`](../../compass/knowledge/lessons/l-75.md)

### L-76: acceptance cleanup 不得对真实仓库 task-report 目录做通配删除
- 正文模块：[`compass/knowledge/lessons/l-76.md`](../../compass/knowledge/lessons/l-76.md)

### L-77: 独立评审执行器必须区分“命令存在”与“当前健康可用”，并透传真实宿主身份
- 正文模块：[`compass/knowledge/lessons/l-77.md`](../../compass/knowledge/lessons/l-77.md)

### L-78: review runner 的 transport error 检测必须让位于结构化评审结果解析
- 正文模块：[`compass/knowledge/lessons/l-78.md`](../../compass/knowledge/lessons/l-78.md)

### L-79: structured review 的接纳条件必须同时满足“结果值归一化”与“CLI 成功退出”
- 正文模块：[`compass/knowledge/lessons/l-79.md`](../../compass/knowledge/lessons/l-79.md)

### L-80: reviewer output 必须分离 payload / stderr / 残余文本，且成功但不可解析的输出必须继续 fallback
- 正文模块：[`compass/knowledge/lessons/l-80.md`](../../compass/knowledge/lessons/l-80.md)

### L-81: fenced JSON 解析必须兼容 bare fence 与大小写变体
- 正文模块：[`compass/knowledge/lessons/l-81.md`](../../compass/knowledge/lessons/l-81.md)

### L-82: transport failure detector 必须匹配“整行 CLI 错误形状”，不能扫 residual prose 的宽子串
- 正文模块：[`compass/knowledge/lessons/l-82.md`](../../compass/knowledge/lessons/l-82.md)

### L-83: bare fence 兼容不能退化成“第一个 bare fence 优先”，而必须选择真正可解析的 JSON 候选
- 正文模块：[`compass/knowledge/lessons/l-83.md`](../../compass/knowledge/lessons/l-83.md)

### L-84: 结构化 payload 选定后，residual transport scan 必须忽略所有 fenced blocks，只看 fence 外 prose
- 正文模块：[`compass/knowledge/lessons/l-84.md`](../../compass/knowledge/lessons/l-84.md)

### L-85: stdout 已有 structured result 时，stderr 与 stdout residual 不能共用同一套 transport detector 语义
- 正文模块：[`compass/knowledge/lessons/l-85.md`](../../compass/knowledge/lessons/l-85.md)

### L-86: `on-complete` 的 validator host 必须来自当前宿主或绑定身份，不能被项目名或陈旧 runtime env 污染
- 正文模块：[`compass/knowledge/lessons/l-86.md`](../../compass/knowledge/lessons/l-86.md)

### L-87: `session-end` 清 pending 前必须刷新并证明当前 pending 仍被本次成功覆盖
- 正文模块：[`compass/knowledge/lessons/l-87.md`](../../compass/knowledge/lessons/l-87.md)

### L-88: reviewer fallback 列表必须覆盖当前可用宿主族，并隔离 CLI 噪声与评审 payload
- 正文模块：[`compass/knowledge/lessons/l-88.md`](../../compass/knowledge/lessons/l-88.md)

### L-89: headless reviewer timeout 必须杀整个进程组，不能只等父进程返回
- 正文模块：[`compass/knowledge/lessons/l-89.md`](../../compass/knowledge/lessons/l-89.md)

### L-90: headless reviewer 的长 prompt 必须从构造开始文件化，不能放进 Bash 大字符串
- 正文模块：[`compass/knowledge/lessons/l-90.md`](../../compass/knowledge/lessons/l-90.md)

### L-91: 收尾评审的 P0/P1 必须能追到同一条物理证据链，不能让报告、验证账本与入口规范分叉
- 正文模块：[`compass/knowledge/lessons/l-91.md`](../../compass/knowledge/lessons/l-91.md)

### L-92: 强制规则必须进入执行保障目录，不能只散落在复活协议或报告里
- 正文模块：[`compass/knowledge/lessons/l-92.md`](../../compass/knowledge/lessons/l-92.md)

### L-93: 上层 validator 消费下层控制面检查时必须显式传播失败
- 正文模块：[`compass/knowledge/lessons/l-93.md`](../../compass/knowledge/lessons/l-93.md)

### L-94: docs catalog 只能止血，彻底防上下文爆炸还需要 plan/budget 渐进披露门
- 正文模块：[`compass/knowledge/lessons/l-94.md`](../../compass/knowledge/lessons/l-94.md)

### L-95: FSM 文档新增状态后，state.yaml 校验器必须同步合法状态集
- 正文模块：[`compass/knowledge/lessons/l-95.md`](../../compass/knowledge/lessons/l-95.md)

### L-96: token 风险不能只治理 docs，还要覆盖入口自动导入、巨型脚本与 ignored 运行残留
- 正文模块：[`compass/knowledge/lessons/l-96.md`](../../compass/knowledge/lessons/l-96.md)

### L-97: 权威规范变大时不能简单贴“token 陷阱”标签，必须拆成核心契约与章节路由
- 正文模块：[`compass/knowledge/lessons/l-97.md`](../../compass/knowledge/lessons/l-97.md)

### L-98: 历史 formal Prism 报告的“索引存在”不等于“可重放审计”
- 正文模块：[`compass/knowledge/lessons/l-98.md`](../../compass/knowledge/lessons/l-98.md)

### L-99: `prism/runs` 物理清理前必须先做 machine-readable 生命周期分类
- 正文模块：[`compass/knowledge/lessons/l-99.md`](../../compass/knowledge/lessons/l-99.md)

### L-100: 完整用户项目 E2E 队列不能只有 benchmark 说明，必须有 repo-owned benchmark carrier
- 正文模块：[`compass/knowledge/lessons/l-100.md`](../../compass/knowledge/lessons/l-100.md)

### L-101: `codex` 宿主下的 stop-review 不能把 `codex` 自己排到最后，也不能让 `copilot` reviewer 子进程再触发 task-complete guard
- 正文模块：[`compass/knowledge/lessons/l-101.md`](../../compass/knowledge/lessons/l-101.md)

### L-102: shell heredoc 调 Python 时，参数位置写反会把数据文件当脚本执行
- 正文模块：[`compass/knowledge/lessons/l-102.md`](../../compass/knowledge/lessons/l-102.md)

### L-103: `on_QA_PASS` 的 state guard 必须 fail-closed，不能把不一致 state 只当警告
- 正文模块：[`compass/knowledge/lessons/l-103.md`](../../compass/knowledge/lessons/l-103.md)

### L-104: 完整用户项目 E2E 可用“固定 benchmark carrier + focused replay 副本”高密度消费历史验证队列
- 正文模块：[`compass/knowledge/lessons/l-104.md`](../../compass/knowledge/lessons/l-104.md)

### L-105: reviewer / Prism 选型不能长期继承某次 live 修补的静态家族偏置，必须回到“模型能力 + 本地稳定性”的统一排序
- 正文模块：[`compass/knowledge/lessons/l-105.md`](../../compass/knowledge/lessons/l-105.md)

### L-106: Prism 真实 E2E 必须把“Agent 席位故障”和“repo-owned 脚本故障”分开记账
- 正文模块：[`compass/knowledge/lessons/l-106.md`](../../compass/knowledge/lessons/l-106.md)

### L-107: 需要在只读 reviewer sandbox 里执行的校验器，不能再用 shell heredoc 承载 Python
- 正文模块：[`compass/knowledge/lessons/l-107.md`](../../compass/knowledge/lessons/l-107.md)

### L-108: 分布式控制面一旦成形，就必须升格成单一协议面，不能继续让实现和文档各说各话
- 正文模块：[`compass/knowledge/lessons/l-108.md`](../../compass/knowledge/lessons/l-108.md)

### L-109: 终态收口一旦涉及“Agent 自追加承诺”，就必须升级成 receipt-driven runtime，不能继续靠分散脚本和口头完成
- 正文模块：[`compass/knowledge/lessons/l-109.md`](../../compass/knowledge/lessons/l-109.md)

### L-110: 运行时重构的独立评审，必须提供“完整可审”的材料包；截断 diff 会制造假 blocker 和盲区
- 正文模块：[`compass/knowledge/lessons/l-110.md`](../../compass/knowledge/lessons/l-110.md)

### L-111: 当前任务卡必须跟随真实任务重锚定，不能让旧 receipt 冒充新任务完成态
- 正文模块：[`compass/knowledge/lessons/l-111.md`](../../compass/knowledge/lessons/l-111.md)

### L-112: 优秀机制不能只存在于 CONTRIBUTING，自然语言规则至少要有诊断活性面
- 正文模块：[`compass/knowledge/lessons/l-112.md`](../../compass/knowledge/lessons/l-112.md)

### L-113: 把“说人话”升级成机器强门时，必须先防止正则误伤 Markdown / 代码 / JSON
- 正文模块：[`compass/knowledge/lessons/l-113.md`](../../compass/knowledge/lessons/l-113.md)

### L-114: 经验沉淀不能只靠作者想起来，必须进入候选池并由 closeout 强制处理
- 正文模块：[`compass/knowledge/lessons/l-114.md`](../../compass/knowledge/lessons/l-114.md)

### L-115: Cap identity 成长信号要保护性沉淀，不能由后台机制直接改 active identity
- 正文模块：[`compass/knowledge/lessons/l-115.md`](../../compass/knowledge/lessons/l-115.md)

### L-116: 临时 provider 冻结必须进入所有启动口，不能只写在健康面或排序面
- 正文模块：[`compass/knowledge/lessons/l-116.md`](../../compass/knowledge/lessons/l-116.md)

### L-117: 关键文件解释应采用“查阅字典 + 文件短反链”，避免把可读性变成新的上下文污染
- 正文模块：[`compass/knowledge/lessons/l-117.md`](../../compass/knowledge/lessons/l-117.md)

### L-118: 任务卡必须审“原始意图覆盖”，不能只审 Agent 自己写下的完成标准
- 正文模块：[`compass/knowledge/lessons/l-118.md`](../../compass/knowledge/lessons/l-118.md)

### L-119: 完成通知需要单向兜底通道，不能被双向窗口的 CLI scope 一票卡死
- 正文模块：[`compass/knowledge/lessons/l-119.md`](../../compass/knowledge/lessons/l-119.md)

### L-120: Prism 可用性 cache 要同时记录时间新鲜度和探测强度
- 正文模块：[`compass/knowledge/lessons/l-120.md`](../../compass/knowledge/lessons/l-120.md)

### L-121: File Lookup Dictionary 必须有 coverage policy，否则会退回一次性人肉索引
- 正文模块：[`compass/knowledge/lessons/l-121.md`](../../compass/knowledge/lessons/l-121.md)

### L-122: 公共知识库要先建立写入边界，再谈历史资产搬迁
- 正文模块：[`compass/knowledge/lessons/l-122.md`](../../compass/knowledge/lessons/l-122.md)

### L-123: 发布安全不能等到 npm publish 那一刻才靠人肉想起
- 正文模块：[`compass/knowledge/lessons/l-123.md`](../../compass/knowledge/lessons/l-123.md)

### L-124: 执行期中插需求必须先重计划，不能让最新子任务覆盖父任务
- 正文模块：[`compass/knowledge/lessons/l-124.md`](../../compass/knowledge/lessons/l-124.md)

### L-125: 可用性缓存不能只证明“还没过期”，还要证明“是在当前运行面生成”
- 正文模块：[`compass/knowledge/lessons/l-125.md`](../../compass/knowledge/lessons/l-125.md)

### L-126: 历史编号恢复必须区分“原始证据恢复”和“后续重构映射”
- 正文模块：[`compass/knowledge/lessons/l-126.md`](../../compass/knowledge/lessons/l-126.md)

### L-127: 执行层物理拆分要先 dry-run 化，不能把路线图当迁移结果
- 正文模块：[`compass/knowledge/lessons/l-127.md`](../../compass/knowledge/lessons/l-127.md)

### L-128: 历史资产迁移要先按集合分类，再生成文件级 apply 清单
- 正文模块：[`compass/knowledge/lessons/l-128.md`](../../compass/knowledge/lessons/l-128.md)

### L-129: 父任务完成必须由聚合 gate 判断，不能由子任务 receipt 推断
- 正文模块：[`compass/knowledge/lessons/l-129.md`](../../compass/knowledge/lessons/l-129.md)

### L-129A: receipt_glob 只是索引，不是完成证据
- 正文模块：[`compass/knowledge/lessons/l-129a.md`](../../compass/knowledge/lessons/l-129a.md)

### L-130: package readiness 要核对“声明的候选清单”和“真实打包面”
- 正文模块：[`compass/knowledge/lessons/l-130.md`](../../compass/knowledge/lessons/l-130.md)

### L-131: Prism provider 可用性要区分“慢启动”和“不可用”，Codex 只能做兜底
- 正文模块：[`compass/knowledge/lessons/l-131.md`](../../compass/knowledge/lessons/l-131.md)

### L-132: 公共库远端绑定必须用最小白名单加 live 对账证明
- 正文模块：[`compass/knowledge/lessons/l-132.md`](../../compass/knowledge/lessons/l-132.md)

### L-133: 旧控制面 FAIL 不能污染当前 Prism pass 收口
- 正文模块：[`compass/knowledge/lessons/l-133.md`](../../compass/knowledge/lessons/l-133.md)

### L-134: 公共库要区分“模板源、耐久本地仓库、远端仓库”
- 正文模块：[`compass/knowledge/lessons/l-134.md`](../../compass/knowledge/lessons/l-134.md)

### L-135: 中插需求不能只入账，还要显性说明重排理由
- 正文模块：[`compass/knowledge/lessons/l-135.md`](../../compass/knowledge/lessons/l-135.md)

### L-136: 通知通道要区分“机制收敛”和“外部 profile 可用”
- 正文模块：[`compass/knowledge/lessons/l-136.md`](../../compass/knowledge/lessons/l-136.md)

### L-137: 首次启动身份不能只停留在“读 identity”，还要写可复验本地状态面
- 正文模块：[`compass/knowledge/lessons/l-137.md`](../../compass/knowledge/lessons/l-137.md)

### L-138: “暂不升级”也要有机器门禁
- 正文模块：[`compass/knowledge/lessons/l-138.md`](../../compass/knowledge/lessons/l-138.md)

### L-139: 飞书不是内部审计日志
- 正文模块：[`compass/knowledge/lessons/l-139.md`](../../compass/knowledge/lessons/l-139.md)

### L-140: 运行时证据目录不能用静态 exact count 当迁移门
- 正文模块：[`compass/knowledge/lessons/l-140.md`](../../compass/knowledge/lessons/l-140.md)

### L-141: 通知降噪不能删除本地终态证据
- 正文模块：[`compass/knowledge/lessons/l-141.md`](../../compass/knowledge/lessons/l-141.md)

### L-142: acceptance fixture 不能依赖真实当前任务卡
- 正文模块：[`compass/knowledge/lessons/l-142.md`](../../compass/knowledge/lessons/l-142.md)

### L-143: “只处理安全项”的工具也必须先扫描危险项
- 正文模块：[`compass/knowledge/lessons/l-143.md`](../../compass/knowledge/lessons/l-143.md)

### L-144: 迁移演练要同时证明隔离环境和旧锚点不丢
- 正文模块：[`compass/knowledge/lessons/l-144.md`](../../compass/knowledge/lessons/l-144.md)

### L-145: 迁移 resolver 必须把“候选新路径”和“权威旧锚点”分开
- 正文模块：[`compass/knowledge/lessons/l-145.md`](../../compass/knowledge/lessons/l-145.md)

### L-146: copy-first apply 的 receipt 只能记录稳定事实，不能记录幂等命令过程数
- 正文模块：[`compass/knowledge/lessons/l-146.md`](../../compass/knowledge/lessons/l-146.md)

### L-147: 活跃任务报告不要参加同一轮历史资产迁移
- 正文模块：[`compass/knowledge/lessons/l-147.md`](../../compass/knowledge/lessons/l-147.md)

### L-148: 长期聚合证据不能只放 `/tmp`
- 正文模块：[`compass/knowledge/lessons/l-148.md`](../../compass/knowledge/lessons/l-148.md)

### L-149: 发布前要审产品形态，不只审打包能力
- 正文模块：[`compass/knowledge/lessons/l-149.md`](../../compass/knowledge/lessons/l-149.md)

### L-150: 信息架构治理要先定义边界，再谈目录清理
- 正文模块：[`compass/knowledge/lessons/l-150.md`](../../compass/knowledge/lessons/l-150.md)

### L-151: 发布前结构手术要先拍片，再开刀
- 正文模块：[`compass/knowledge/lessons/l-151.md`](../../compass/knowledge/lessons/l-151.md)

### L-152: CLI 化时必须先拆“工具位置”和“项目位置”
- 正文模块：[`compass/knowledge/lessons/l-152.md`](../../compass/knowledge/lessons/l-152.md)

### L-153: CLI 诊断产品面不能复用内部门禁流水账
- 正文模块：[`compass/knowledge/lessons/l-153.md`](../../compass/knowledge/lessons/l-153.md)

### L-154: 公共包准备态不能冒充真实发布
- 正文模块：[`compass/knowledge/lessons/l-154.md`](../../compass/knowledge/lessons/l-154.md)

### L-155: 宿主 Hook 要区分“配置存在”和“物理触发”
- 正文模块：[`compass/knowledge/lessons/l-155.md`](../../compass/knowledge/lessons/l-155.md)

### L-156: 架构坏味治理不能只靠报告，必须绑定到索引、生命周期和检查器
- 正文模块：[`compass/knowledge/lessons/l-156.md`](../../compass/knowledge/lessons/l-156.md)

### L-157: 结论性输出不能单人自证，新增规则默认先找固化保障
- 正文模块：[`compass/knowledge/lessons/l-157.md`](../../compass/knowledge/lessons/l-157.md)

### L-158: receipt 与 pending closure 必须分开判定
- 正文模块：[`compass/knowledge/lessons/l-158.md`](../../compass/knowledge/lessons/l-158.md)

### L-159: “继续”类指令必须先确认任务锚点
- 正文模块：[`compass/knowledge/lessons/l-159.md`](../../compass/knowledge/lessons/l-159.md)

### L-160: 进度仪只能是聚合视图，不能成为新真相源
- 正文模块：[`compass/knowledge/lessons/l-160.md`](../../compass/knowledge/lessons/l-160.md)

### L-161: 声明的聚合源必须真的被读取，否则就是假覆盖
- 正文模块：[`compass/knowledge/lessons/l-161.md`](../../compass/knowledge/lessons/l-161.md)
