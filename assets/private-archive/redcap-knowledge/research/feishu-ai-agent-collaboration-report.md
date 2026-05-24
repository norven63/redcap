# 飞书 AI Agent 人机协作通知方案技术调研报告

**调研日期**: 2026-03-29  
**调研目标**: 为 AI Agent CLI 工具（Claude Code、kimi cli、gemini cli 等）寻找飞书平台的双向通信通知方案  
**核心需求**: 当 Agent 执行遇到阻塞问题时，能够通知用户并接收用户回复，实现人机协作闭环

---

## 一、需求分析

### 1.1 应用场景

```
┌─────────────────────────────────────────────────────────────────┐
│                     AI Agent 自动化工作流                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Agent 开始执行任务                                           │
│       ↓                                                          │
│  2. 执行自动化操作（代码分析、数据处理等）                          │
│       ↓                                                          │
│  3. 遇到问题（需要确认/需要输入/异常情况）                          │
│       ↓                                                          │
│  4. 【阻塞】发送通知给用户 ───────▶ 用户收到飞书消息               │
│       │                              ↓                          │
│  5. 【等待】等待用户回复 ◀──────── 用户回复解决方案                │
│       ↓                                                          │
│  6. 根据用户指示继续执行                                          │
│       ↓                                                          │
│  7. 任务完成，发送通知                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 功能需求

| 需求项 | 说明 | 优先级 |
|--------|------|--------|
| 消息发送 | 从电脑向手机发送飞书消息通知 | P0 |
| 消息接收 | 接收用户在飞书中的回复 | P0 |
| 交互确认 | 支持确认/取消等按钮交互 | P1 |
| 文本输入 | 支持用户输入文本内容 | P0 |
| 超时处理 | 支持设置等待超时时间 | P1 |
| CLI 集成 | 易于在 Shell 脚本/Python 中调用 | P0 |

### 1.3 约束条件

- **平台限制**: 仅使用飞书平台能力
- **网络环境**: 可能在内网环境，无公网 IP
- **部署方式**: 本地 CLI 工具调用，非服务端部署

---

## 二、飞书平台能力调研

### 2.1 飞书消息相关能力矩阵

| 能力 | 群机器人 | 自建应用 | 飞书 aPaaS | 说明 |
|------|----------|----------|------------|------|
| 发送文本消息 | ✅ | ✅ | ✅ | 基础能力 |
| 发送消息卡片 | ✅ | ✅ | ✅ | 富媒体消息 |
| 接收用户回复 | ❌ | ✅ | ✅ | 需要事件订阅 |
| 交互式按钮 | ❌ | ✅ | ✅ | 卡片回调 |
| 私聊消息 | ❌ | ✅ | ✅ | 需用户授权 |

### 2.2 飞书 aPaaS 核心能力

根据飞书 aPaaS 官方文档调研：

#### 2.2.1 飞书消息连接器

- **文档**: [「飞书消息」连接器](https://ae.feishu.cn/hc/zh-CN/articles/721793695931)
- **能力**: 
  - 发送纯文本、富文本、消息卡片
  - 支持多种接收者 ID（open_id、user_id、union_id、email、chat_id）
  - 可在页面/流程中调用
- **限制**: 功能灰度中，部分租户可能未开放

#### 2.2.2 人工任务流程

- **文档**: [人工任务流程的创建与使用](https://ae.feishu.cn/hc/zh-CN/articles/803926936750)
- **能力**:
  - 创建需要"人"参与的审批/填写流程
  - 支持发起人、审批人、抄送人角色
  - 流程阻塞等待人工处理
  - 支持超时自动处理
- **适用场景**: 审批、工单、任务分配

#### 2.2.3 消息卡片配置

- **文档**: [流程中的消息卡片配置](https://ae.feishu.cn/hc/zh-CN/articles/122095600400)
- **能力**:
  - 可视化配置消息卡片
  - 支持列表组件动态展示数据
  - **案例二**: 机器人回复用户消息，返回待处理工单
  - 支持飞书消息触发流程

#### 2.2.4 Open API

- **文档**: [Open API 使用指南](https://ae.feishu.cn/hc/zh-CN/articles/973092219828)
- **接口域名**: `ae-openapi.feishu.cn`
- **能力**:
  - 自动生成 Open API 文档
  - 支持对象元数据查询
  - 增删改查应用记录
  - 执行流程、云函数
  - 获取 tenantAccessToken

---

## 三、技术方案对比

### 3.1 方案总览

| 方案 | 复杂度 | 实时性 | 双向通信 | 需要条件 | 适用场景 |
|------|--------|--------|----------|----------|----------|
| **方案一：飞书 aPaaS 人工任务** | ⭐⭐ 中 | ✅ 实时 | ✅ 完整 | 飞书 aPaaS 应用 | 正式生产环境 |
| **方案二：自建应用+事件订阅** | ⭐⭐⭐ 高 | ✅ 实时 | ✅ 完整 | 公网地址/ngrok | 有服务器资源 |
| **方案三：多维表格轮询** | ⭐ 低 | ⚠️ 3秒延迟 | ✅ 完整 | 多维表格权限 | 快速验证/内网 |
| **方案四：群机器人（单向）** | ⭐ 低 | ✅ 实时 | ❌ 不支持 | 群机器人 | 仅通知场景 |

### 3.2 方案详细分析

#### 方案一：飞书 aPaaS 人工任务流程（推荐）

**架构设计**:

```
┌─────────────────────────────────────────────────────────────────┐
│                        飞书 aPaaS 平台                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │   流程定义    │─────▶│  人工任务节点  │─────▶│   消息卡片    │  │
│  │              │      │              │      │   发送给用户  │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│         │                     ▲                      │          │
│         │                     │                      │          │
│         ▼                     │                      ▼          │
│  ┌──────────────┐             │              ┌──────────────┐  │
│  │  Open API    │─────────────┘              │   用户回复    │  │
│  │  触发/查询   │◀───────────────────────────│   填写表单    │  │
│  └──────────────┘                            └──────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP API
                              ▼
                    ┌──────────────────┐
                    │   AI Agent CLI   │
                    │  (Claude/kimi)   │
                    └──────────────────┘
```

**实现步骤**:

1. **创建应用**
   - 登录飞书 aPaaS 平台
   - 创建新应用

2. **设计流程**
   ```
   开始 → 人工任务节点 → 结束
            │
            ▼
      发送消息卡片给用户
            │
            ▼
      等待用户填写表单
            │
            ▼
      获取用户输入继续
   ```

3. **配置人工任务节点**
   - 设置接收人（你的飞书账号）
   - 配置表单字段（如：处理方式、备注）
   - 设置超时时间

4. **发布应用**
   - 提交审核（企业内部应用可快速通过）
   - 发布上线

5. **CLI 集成**
   ```python
   import requests
   
   # 触发流程
   def trigger_flow(question: str):
       token = get_tenant_token()
       resp = requests.post(
           "https://ae-openapi.feishu.cn/v1/flow/instances",
           headers={"Authorization": f"Bearer {token}"},
           json={
               "flow_def_id": "YOUR_FLOW_ID",
               "trigger_data": {"question": question}
           }
       )
       return resp.json()["data"]["instance_id"]
   
   # 轮询等待结果
   def wait_for_response(instance_id: str, timeout: int = 300):
       start = time.time()
       while time.time() - start < timeout:
           status = get_flow_status(instance_id)
           if status["state"] == "completed":
               return status["output_data"]["user_response"]
           time.sleep(3)
       return None
   ```

**优点**:
- ✅ 纯飞书生态，无需第三方服务
- ✅ 可视化流程设计，易于维护
- ✅ 支持复杂的审批逻辑
- ✅ 有完整的日志和监控

**缺点**:
- ⚠️ 需要学习和使用飞书 aPaaS 平台
- ⚠️ 首次配置较复杂
- ⚠️ 流程实例有调用频率限制

---

#### 方案二：飞书自建应用 + 事件订阅

**架构设计**:

```
┌─────────────────────────────────────────────────────────────────┐
│                        飞书开放平台                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │   自建应用    │─────▶│   发送消息    │─────▶│   用户手机    │  │
│  │              │      │   API        │      │   飞书客户端  │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│         ▲                                              │        │
│         │                                              │        │
│         │           ┌──────────────┐                   │        │
│         └───────────│   事件订阅    │◀──────────────────┘        │
│                     │   回调地址    │                            │
│                     └──────────────┘                            │
│                            │                                     │
└────────────────────────────┼─────────────────────────────────────┘
                             │ HTTPS
                             ▼
              ┌──────────────────────────┐
              │    本地 HTTP 服务器        │
              │   (Python/Node.js)        │
              │   监听 8080 端口           │
              └──────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
        ┌──────────┐                 ┌──────────┐
        │  ngrok   │                 │  云服务器 │
        │ (开发)   │                 │ (生产)   │
        └──────────┘                 └──────────┘
```

**实现步骤**:

1. **创建自建应用**
   - 访问 [飞书开放平台](https://open.feishu.cn/app)
   - 创建企业自建应用
   - 获取 App ID 和 App Secret

2. **开启机器人能力**
   - 应用后台 → 机器人
   - 启用机器人

3. **配置权限**
   - `im:chat:readonly`（读取群组信息）
   - `im:message:send`（发送消息）
   - `im:message.group_msg`（接收群消息）
   - `im:message.p2p_msg`（接收私聊消息）

4. **配置事件订阅**
   - 开发环境：使用 ngrok
     ```bash
     ngrok http 8080
     # 获得 https://xxx.ngrok.io
     ```
   - 生产环境：部署到云服务器
   - 在应用后台配置请求地址

5. **订阅事件**
   - `im.message.receive_v1`（接收消息）
   - `card.action.trigger`（卡片按钮点击）

6. **实现代码**
   ```python
   from flask import Flask, request
   import requests
   
   app = Flask(__name__)
   
   APP_ID = "cli_xxx"
   APP_SECRET = "xxx"
   USER_ID = "ou_xxx"  # 你的 open_id
   
   pending_responses = {}
   
   def get_tenant_token():
       resp = requests.post(
           "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
           json={"app_id": APP_ID, "app_secret": APP_SECRET}
       )
       return resp.json()["tenant_access_token"]
   
   def send_message(text: str):
       token = get_tenant_token()
       resp = requests.post(
           "https://open.feishu.cn/open-apis/im/v1/messages",
           headers={"Authorization": f"Bearer {token}"},
           params={"receive_id_type": "open_id"},
           json={
               "receive_id": USER_ID,
               "msg_type": "text",
               "content": json.dumps({"text": text})
           }
       )
       return resp.json()
   
   @app.route('/webhook', methods=['POST'])
   def webhook():
       data = request.json
       event_type = data.get("header", {}).get("event_type")
       
       if event_type == "im.message.receive_v1":
           message = data["event"]["message"]
           content = json.loads(message["content"])
           text = content.get("text", "")
           
           # 保存用户回复
           pending_responses["latest"] = text
           print(f"收到回复: {text}")
       
       return {"code": 0}
   
   if __name__ == '__main__':
       app.run(port=8080)
   ```

**优点**:
- ✅ 灵活性最高，可自定义交互逻辑
- ✅ 实时双向通信
- ✅ 支持消息卡片交互

**缺点**:
- ⚠️ 需要公网可访问的回调地址
- ⚠️ 配置复杂度高
- ⚠️ 需要维护 HTTP 服务

---

#### 方案三：飞书多维表格轮询（推荐快速验证）

**架构设计**:

```
┌─────────────────────────────────────────────────────────────────┐
│                        飞书平台                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │  群机器人    │─────▶│   用户手机    │      │  多维表格    │  │
│  │  发送通知    │      │   飞书客户端  │─────▶│   填写回复   │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│                                                       ▲        │
│                                                       │        │
└───────────────────────────────────────────────────────┼────────┘
                                                        │
                              ┌─────────────────────────┘
                              │ 轮询查询 (3秒间隔)
                              ▼
                    ┌──────────────────┐
                    │   AI Agent CLI   │
                    └──────────────────┘
```

**实现步骤**:

1. **创建多维表格**
   - 在飞书中创建多维表格
   - 设置字段：消息内容、状态、用户回复、创建时间

2. **获取表格凭证**
   - 打开表格 → 开发者选项
   - 复制 App Token 和 Table ID

3. **实现代码**
   ```python
   import requests
   import time
   
   APP_TOKEN = "your_app_token"
   TABLE_ID = "your_table_id"
   WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
   
   class FeishuBitableNotifier:
       def __init__(self):
           self.token = self._get_tenant_token()
       
       def _get_tenant_token(self):
           resp = requests.post(
               "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
               json={"app_id": APP_ID, "app_secret": APP_SECRET}
           )
           return resp.json()["tenant_access_token"]
       
       def send_notification(self, message: str) -> str:
           """发送通知并创建表格记录"""
           # 1. 创建表格记录
           url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records"
           resp = requests.post(
               url,
               headers={"Authorization": f"Bearer {self.token}"},
               json={
                   "fields": {
                       "消息内容": message,
                       "状态": "待处理",
                       "创建时间": int(time.time())
                   }
               }
           )
           record_id = resp.json()["data"]["record"]["record_id"]
           
           # 2. 发送飞书通知
           table_url = f"https://base.feishu.cn/{APP_TOKEN}?table={TABLE_ID}"
           requests.post(WEBHOOK, json={
               "msg_type": "interactive",
               "card": {
                   "config": {"wide_screen_mode": True},
                   "header": {
                       "title": {"tag": "plain_text", "content": "🤖 AI Agent 需要协助"},
                       "template": "orange"
                   },
                   "elements": [
                       {"tag": "div", "text": {"tag": "lark_md", "content": message}},
                       {"tag": "action", "actions": [
                           {"tag": "button", "text": {"tag": "plain_text", "content": "点击回复"},
                            "type": "primary", "url": table_url}
                       ]}
                   ]
               }
           })
           
           return record_id
       
       def wait_for_response(self, record_id: str, timeout: int = 300) -> str:
           """轮询等待用户回复"""
           url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/{record_id}"
           start = time.time()
           
           while time.time() - start < timeout:
               resp = requests.get(
                   url,
                   headers={"Authorization": f"Bearer {self.token}"}
               )
               fields = resp.json()["data"]["record"]["fields"]
               
               if fields.get("用户回复"):
                   return fields["用户回复"]
               
               time.sleep(3)
           
           return None
   
   # 使用示例
   notifier = FeishuBitableNotifier()
   record_id = notifier.send_notification("任务遇到问题，请指示如何处理？")
   response = notifier.wait_for_response(record_id, timeout=300)
   print(f"用户回复: {response}")
   ```

**优点**:
- ✅ 无需公网地址，内网可用
- ✅ 配置简单，快速验证
- ✅ 用户回复有持久化存储
- ✅ 可同时查看历史记录

**缺点**:
- ⚠️ 轮询有 3 秒左右的延迟
- ⚠️ 需要用户手动打开表格填写
- ⚠️ 用户体验不如实时交互

---

#### 方案四：群机器人（仅单向通知）

**说明**: 飞书群机器人**不支持接收用户回复**，只能发送消息。

**适用场景**: 仅需通知，无需交互的场景

```python
import requests

def send_feishu_notification(webhook: str, message: str):
    """发送飞书群机器人消息"""
    requests.post(webhook, json={
        "msg_type": "text",
        "content": {"text": message}
    })

# 使用
WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
send_feishu_notification(WEBHOOK, "任务执行完成")
```

---

## 四、方案对比总结

### 4.1 功能对比

| 功能 | 方案一 aPaaS | 方案二 自建应用 | 方案三 多维表格 | 方案四 群机器人 |
|------|-------------|----------------|----------------|----------------|
| 发送消息 | ✅ | ✅ | ✅ | ✅ |
| 接收回复 | ✅ | ✅ | ✅ | ❌ |
| 实时性 | ✅ 实时 | ✅ 实时 | ⚠️ 3秒延迟 | ✅ 实时 |
| 交互按钮 | ✅ | ✅ | ❌ | ❌ |
| 表单输入 | ✅ | ✅ | ✅ | ❌ |
| 内网可用 | ✅ | ❌ | ✅ | ✅ |
| 配置复杂度 | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ |
| 维护成本 | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ |

### 4.2 推荐方案

| 场景 | 推荐方案 | 理由 |
|------|----------|------|
| **正式生产环境** | 方案一：aPaaS 人工任务 | 稳定、可维护、功能完整 |
| **有服务器资源** | 方案二：自建应用 | 灵活性最高 |
| **快速验证/MVP** | 方案三：多维表格 | 配置简单、内网可用 |
| **仅通知场景** | 方案四：群机器人 | 最简单 |

---

## 五、推荐实施方案

### 5.1 分阶段实施建议

```
第一阶段（快速验证）
    │
    ▼
方案三：多维表格轮询
    │
    ├── 1 小时完成配置
    ├── 验证核心流程
    └── 内网环境可用
    │
第二阶段（正式使用）
    │
    ▼
方案一：aPaaS 人工任务
    │
    ├── 学习 aPaaS 平台
    ├── 设计完整流程
    └── 发布正式应用
```

### 5.2 推荐方案一详细设计

#### 5.2.1 流程设计

```
┌─────────────────────────────────────────────────────────────────┐
│                    飞书 aPaaS 流程设计                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────┐    ┌─────────────┐    ┌─────────────────────┐     │
│  │  开始   │───▶│  创建记录   │───▶│  发送消息卡片给用户  │     │
│  │ (API)   │    │  (记录问题) │    │  (人工任务节点)      │     │
│  └─────────┘    └─────────────┘    └─────────────────────┘     │
│                                              │                  │
│                                              ▼                  │
│                                   ┌─────────────────────┐       │
│                                   │  等待用户处理       │       │
│                                   │  - 填写解决方案     │       │
│                                   │  - 选择处理方式     │       │
│                                   │  - 超时自动处理     │       │
│                                   └─────────────────────┘       │
│                                              │                  │
│                                              ▼                  │
│                                   ┌─────────────────────┐       │
│                                   │  获取用户输入       │       │
│                                   │  更新记录状态       │       │
│                                   └─────────────────────┘       │
│                                              │                  │
│                                              ▼                  │
│                                   ┌─────────────────────┐       │
│                                   │  结束 (返回结果)    │       │
│                                   │  (API 可查询)       │       │
│                                   └─────────────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 5.2.2 CLI 集成代码

```python
#!/usr/bin/env python3
"""
飞书 aPaaS 人机协作通知器
"""

import os
import time
import requests
from typing import Optional

class FeishuAPaaSNotifier:
    def __init__(self):
        self.client_id = os.getenv("FEISHU_APAAAS_CLIENT_ID")
        self.client_secret = os.getenv("FEISHU_APAAAS_CLIENT_SECRET")
        self.flow_def_id = os.getenv("FEISHU_APAAAS_FLOW_ID")
        self.base_url = "https://ae-openapi.feishu.cn"
        self._token = None
        self._token_expire = 0
    
    def _get_token(self) -> str:
        """获取 tenant access token"""
        if self._token and time.time() < self._token_expire:
            return self._token
        
        resp = requests.post(
            f"{self.base_url}/auth/v1/tenantAccessToken",
            json={
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
        )
        data = resp.json()
        if data.get("code") == 0:
            self._token = data["token"]
            self._token_expire = time.time() + data["expire"] - 60
            return self._token
        raise Exception(f"获取 token 失败: {data}")
    
    def ask(self, question: str, timeout: int = 300) -> Optional[str]:
        """
        向用户提问并等待回复
        
        Args:
            question: 问题内容
            timeout: 超时时间（秒）
        
        Returns:
            用户回复内容，超时返回 None
        """
        # 1. 触发流程
        instance_id = self._trigger_flow(question)
        print(f"流程已触发: {instance_id}")
        
        # 2. 轮询等待结果
        print(f"⏳ 等待回复中... (超时: {timeout}秒)")
        start = time.time()
        
        while time.time() - start < timeout:
            status = self._get_flow_status(instance_id)
            
            if status["state"] == "completed":
                response = status.get("output_data", {}).get("user_response")
                print(f"✅ 收到回复: {response}")
                return response
            
            if status["state"] == "error":
                raise Exception(f"流程执行失败: {status}")
            
            time.sleep(3)
        
        print("⏰ 等待超时")
        return None
    
    def confirm(self, message: str, timeout: int = 300) -> bool:
        """
        向用户确认
        
        Returns:
            True 表示确认，False 表示取消或超时
        """
        response = self.ask(
            f"{message}\n\n请回复: 确认 / 取消",
            timeout=timeout
        )
        if response is None:
            return False
        return "确认" in response or "是" in response.lower()
    
    def notify(self, message: str):
        """发送纯通知"""
        # 使用飞书消息连接器或群机器人
        pass
    
    def _trigger_flow(self, question: str) -> str:
        """触发流程"""
        resp = requests.post(
            f"{self.base_url}/v1/flow/instances",
            headers={"Authorization": f"Bearer {self._get_token()}"},
            json={
                "flow_def_id": self.flow_def_id,
                "trigger_data": {"question": question}
            }
        )
        data = resp.json()
        if data.get("code") == 0:
            return data["data"]["instance_id"]
        raise Exception(f"触发流程失败: {data}")
    
    def _get_flow_status(self, instance_id: str) -> dict:
        """获取流程状态"""
        resp = requests.get(
            f"{self.base_url}/v1/flow/instances/{instance_id}",
            headers={"Authorization": f"Bearer {self._get_token()}"}
        )
        data = resp.json()
        if data.get("code") == 0:
            return data["data"]
        raise Exception(f"查询流程失败: {data}")


# CLI 入口
if __name__ == "__main__":
    import sys
    
    notifier = FeishuAPaaSNotifier()
    
    if len(sys.argv) < 2:
        print("用法: python3 feishu_apaas_notifier.py <ask|confirm|notify> <内容> [--timeout 秒]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    content = sys.argv[2] if len(sys.argv) > 2 else ""
    timeout = 300
    
    # 解析参数
    for i, arg in enumerate(sys.argv):
        if arg == "--timeout" and i + 1 < len(sys.argv):
            timeout = int(sys.argv[i + 1])
    
    if cmd == "ask":
        response = notifier.ask(content, timeout)
        print(response if response else "TIMEOUT")
        sys.exit(0 if response else 1)
    
    elif cmd == "confirm":
        confirmed = notifier.confirm(content, timeout)
        print("CONFIRMED" if confirmed else "CANCELLED")
        sys.exit(0 if confirmed else 1)
    
    elif cmd == "notify":
        notifier.notify(content)
        print("OK")
    
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
```

#### 5.2.3 环境变量配置

```bash
# 飞书 aPaaS 配置
export FEISHU_APAAAS_CLIENT_ID="cli_xxx"
export FEISHU_APAAAS_CLIENT_SECRET="xxx"
export FEISHU_APAAAS_FLOW_ID="flow_xxx"

# 使用示例
python3 feishu_apaas_notifier.py ask "任务遇到问题，请指示如何处理？" --timeout 300
python3 feishu_apaas_notifier.py confirm "是否继续执行删除操作？" --timeout 60
python3 feishu_apaas_notifier.py notify "任务执行完成"
```

---

## 六、实施计划

### 6.1 第一阶段：快速验证（1-2 天）

| 任务 | 时间 | 产出 |
|------|------|------|
| 创建飞书多维表格 | 30分钟 | 表格 + App Token |
| 创建群机器人 | 15分钟 | Webhook 地址 |
| 实现轮询脚本 | 2小时 | Python 脚本 |
| 集成测试 | 1小时 | 验证完整流程 |

### 6.2 第二阶段：正式方案（1-2 周）

| 任务 | 时间 | 产出 |
|------|------|------|
| 学习飞书 aPaaS 平台 | 1天 | 熟悉操作 |
| 设计流程 | 1天 | 流程图 + 配置 |
| 开发测试 | 2天 | 完整应用 |
| 发布上线 | 1天 | 正式应用 |
| CLI 集成 | 1天 | 命令行工具 |

---

## 七、参考资料

### 7.1 飞书官方文档

1. [飞书 aPaaS 帮助中心](https://ae.feishu.cn/hc/zh-CN)
2. [Open API 使用指南](https://ae.feishu.cn/hc/zh-CN/articles/973092219828)
3. [「飞书消息」连接器](https://ae.feishu.cn/hc/zh-CN/articles/721793695931)
4. [人工任务流程的创建与使用](https://ae.feishu.cn/hc/zh-CN/articles/803926936750)
5. [流程中的消息卡片配置](https://ae.feishu.cn/hc/zh-CN/articles/122095600400)
6. [飞书开放平台 - 消息 API](https://open.feishu.cn/document/server-docs/im-v1/message/create)

### 7.2 相关工具

- [ngrok](https://ngrok.com/) - 内网穿透工具
- [飞书开放平台](https://open.feishu.cn/app) - 自建应用管理
- [飞书 aPaaS](https://apaas.feishu.cn/) - 低代码平台

---

## 八、附录

### 8.1 术语表

| 术语 | 说明 |
|------|------|
| aPaaS | Application Platform as a Service，应用平台即服务 |
| BPM | Business Process Management，业务流程管理 |
| Open API | 开放平台接口，用于外部系统调用 |
| Webhook | HTTP 回调接口，用于接收事件通知 |
| 人工任务 | 需要人工参与处理的流程节点 |
| 消息卡片 | 飞书的富媒体消息格式 |
| open_id | 飞书用户的唯一标识 |
| tenant_access_token | 应用级别的访问令牌 |

### 8.2 常见问题

**Q: 群机器人为什么不能接收回复？**  
A: 群机器人设计为单向推送，只能发送消息，不能接收用户回复。如需双向通信，需使用自建应用或 aPaaS 流程。

**Q: 没有公网地址怎么办？**  
A: 可以使用 ngrok 进行内网穿透（开发测试），或使用多维表格轮询方案（生产可用）。

**Q: 飞书 aPaaS 是否收费？**  
A: 飞书 aPaaS 有免费版和付费版，具体定价请参考官方文档。

**Q: 人工任务流程的超时时间如何设置？**  
A: 在人工任务节点的配置中可以设置超时时间，超时后可配置自动处理逻辑。

---

*报告完成*
