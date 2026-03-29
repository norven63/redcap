#!/usr/bin/env python3
"""
RedCap 飞书通知器 — 多维表格轮询方案

功能：
  setup    自动创建独立多维表格 + 10个字段，更新配置文件
  ask      发送问题并等待用户在多维表格中回复（阻塞）
  confirm  发送确认请求，用户回复"确认/取消"（阻塞）
  notify   发送纯通知，不等待回复（非阻塞）

配置：
  读取同级目录的 ../feishu-config.json（已在 .gitignore 中排除）
  如果配置文件不存在或 notify_enabled=false，则静默跳过

用法：
  python3 feishu-notifier.py setup              # 首次运行，自动创建表
  python3 feishu-notifier.py ask "问题描述" [--timeout 300] [--project 项目名]
  python3 feishu-notifier.py confirm "是否继续？" [--timeout 120]
  python3 feishu-notifier.py notify "任务完成"
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("[feishu-notifier] requests 库未安装，请执行 pip3 install requests", file=sys.stderr)
    sys.exit(1)

# 抑制 LibreSSL 警告
import warnings
warnings.filterwarnings("ignore", message=".*urllib3.*OpenSSL.*")

# ── 配置加载 ──────────────────────────────────────────────

CONFIG_PATH = Path(__file__).resolve().parent.parent / "feishu-config.json"


def load_config() -> Optional[dict]:
    """加载配置文件，不存在或禁用时返回 None"""
    if not CONFIG_PATH.exists():
        return None
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if not cfg.get("notify_enabled", False):
            return None
        required = ["webhook", "app_id", "app_secret", "bitable_app_token", "bitable_table_id"]
        for key in required:
            if not cfg.get(key):
                print(f"[feishu-notifier] 配置缺少 {key}，跳过通知", file=sys.stderr)
                return None
        return cfg
    except (json.JSONDecodeError, IOError) as e:
        print(f"[feishu-notifier] 配置文件读取失败: {e}", file=sys.stderr)
        return None


# ── 飞书 API ──────────────────────────────────────────────

class FeishuNotifier:
    def __init__(self, config: dict):
        self.webhook = config["webhook"]
        self.app_id = config["app_id"]
        self.app_secret = config["app_secret"]
        self.app_token = config["bitable_app_token"]
        self.table_id = config["bitable_table_id"]
        self.base_url = config.get("bitable_base_url", "https://open.feishu.cn")
        self._token: Optional[str] = None
        self._token_expire: float = 0

    # ── Token 管理 ──

    def _get_tenant_token(self) -> str:
        if self._token and time.time() < self._token_expire:
            return self._token
        resp = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=10,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取 tenant_access_token 失败: {data.get('msg', data)}")
        self._token = data["tenant_access_token"]
        self._token_expire = time.time() + data.get("expire", 7200) - 60
        return self._token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_tenant_token()}"}

    # ── 群机器人通知 ──

    def _send_webhook(self, title: str, content: str, table_link: Optional[str] = None):
        elements = [
            {"tag": "div", "text": {"tag": "lark_md", "content": content}},
        ]
        if table_link:
            elements.append({
                "tag": "action",
                "actions": [{
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "点击回复"},
                    "type": "primary",
                    "url": table_link,
                }],
            })
        elements.append({
            "tag": "note",
            "elements": [{"tag": "plain_text", "content": f"RedCap · {datetime.now().strftime('%H:%M:%S')}"}],
        })
        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {"title": {"tag": "plain_text", "content": title}, "template": "orange"},
                "elements": elements,
            },
        }
        resp = requests.post(self.webhook, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"[feishu-notifier] Webhook 发送失败: {resp.status_code} {resp.text}", file=sys.stderr)

    # ── 多维表格操作 ──

    def _create_record(self, fields: dict) -> str:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records"
        resp = requests.post(url, headers=self._headers(), json={"fields": fields}, timeout=10)
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"创建记录失败: {data.get('msg', data)}")
        return data["data"]["record"]["record_id"]

    def _get_record(self, record_id: str) -> dict:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/{record_id}"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"查询记录失败: {data.get('msg', data)}")
        return data["data"]["record"]["fields"]

    def _update_record(self, record_id: str, fields: dict):
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/{record_id}"
        resp = requests.put(url, headers=self._headers(), json={"fields": fields}, timeout=10)
        data = resp.json()
        if data.get("code") != 0:
            print(f"[feishu-notifier] 更新记录失败: {data.get('msg', data)}", file=sys.stderr)

    def _table_link(self) -> str:
        return f"{self.base_url}/base/{self.app_token}?table={self.table_id}"

    # ── 公开接口 ──

    @staticmethod
    def _now_ms() -> int:
        """当前时间的毫秒时间戳（飞书日期字段要求）"""
        return int(time.time() * 1000)

    def notify(self, message: str, project: str = ""):
        """发送纯通知，不等待回复"""
        self._send_webhook("📢 RedCap 通知", message)
        self._create_record({
            "标题": f"[通知] {message[:50]}",
            "类型": "notify",
            "问题内容": message,
            "状态": "已通知",
            "项目名": project,
            "时间": self._now_ms(),
        })

    def ask(self, question: str, timeout: int = 300, project: str = "", fsm_state: str = "", options: str = "") -> Optional[str]:
        """发送问题并等待用户回复"""
        display = question
        if options:
            display += f"\n\n**可选项**: {options}"

        record_id = self._create_record({
            "标题": f"[提问] {question[:50]}",
            "类型": "ask",
            "问题内容": question,
            "可选项": options,
            "状态": "待处理",
            "项目名": project,
            "FSM状态": fsm_state,
            "时间": self._now_ms(),
        })

        self._send_webhook(
            "🤖 AI Agent 需要协助",
            display,
            table_link=self._table_link(),
        )

        print(f"[feishu-notifier] 已发送通知，等待回复中... (超时: {timeout}s)", file=sys.stderr)
        start = time.time()
        while time.time() - start < timeout:
            try:
                fields = self._get_record(record_id)
                reply = fields.get("用户回复")
                if reply:
                    # 处理多维表格返回的列表类型
                    if isinstance(reply, list):
                        reply = reply[0].get("text", str(reply[0])) if reply else ""
                    reply = str(reply).strip()
                    if reply:
                        self._update_record(record_id, {"状态": "已回复"})
                        print(f"[feishu-notifier] 收到回复: {reply}", file=sys.stderr)
                        return reply
            except Exception as e:
                print(f"[feishu-notifier] 轮询异常: {e}", file=sys.stderr)
            time.sleep(3)

        self._update_record(record_id, {"状态": "已超时"})
        print("[feishu-notifier] 等待超时", file=sys.stderr)
        return None

    def confirm(self, message: str, timeout: int = 120, project: str = "") -> bool:
        """发送确认请求，返回 True/False"""
        response = self.ask(
            question=message,
            timeout=timeout,
            project=project,
            options="确认, 取消",
        )
        if response is None:
            return False
        r = response.lower().strip()
        return r in ("确认", "是", "yes", "y", "ok", "确定", "同意")


# ── Setup：自动创建多维表格 ───────────────────────────────

BITABLE_FIELDS = [
    {"field_name": "通知ID",    "type": 1005},  # 自动编号
    {"field_name": "时间",      "type": 5},     # 日期
    {"field_name": "来源",      "type": 3,      # 单选
     "property": {"options": [{"name": "Dispatcher"}, {"name": "产品经理"}, {"name": "架构师"}, {"name": "程序员"}, {"name": "测试QA"}, {"name": "Reviewer"}]}},
    {"field_name": "类型",      "type": 3,      # 单选
     "property": {"options": [{"name": "ask"}, {"name": "confirm"}, {"name": "notify"}]}},
    {"field_name": "问题内容",  "type": 1},     # 文本
    {"field_name": "可选项",    "type": 3,      # 单选
     "property": {"options": [{"name": "确认"}, {"name": "取消"}]}},
    {"field_name": "用户回复",  "type": 1},     # 文本
    {"field_name": "状态",      "type": 3,      # 单选
     "property": {"options": [{"name": "待处理"}, {"name": "已通知"}, {"name": "已回复"}, {"name": "已超时"}]}},
    {"field_name": "项目名",    "type": 1},     # 文本
    {"field_name": "FSM状态",   "type": 1},     # 文本
]


def run_setup():
    """自动创建独立多维表格 + 全部字段，更新 feishu-config.json"""
    if not CONFIG_PATH.exists():
        print("[setup] feishu-config.json 不存在，请先创建配置文件", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    for key in ("app_id", "app_secret"):
        if not cfg.get(key):
            print(f"[setup] 配置缺少 {key}", file=sys.stderr)
            sys.exit(1)

    # 获取 token
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": cfg["app_id"], "app_secret": cfg["app_secret"]},
        timeout=10,
    )
    token_data = resp.json()
    if token_data.get("code") != 0:
        print(f"[setup] 获取 token 失败: {token_data}", file=sys.stderr)
        sys.exit(1)
    token = token_data["tenant_access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. 创建独立多维表格
    print("[setup] 正在创建多维表格...")
    resp = requests.post(
        "https://open.feishu.cn/open-apis/bitable/v1/apps",
        headers=headers,
        json={"name": "RedCap 通知中心"},
        timeout=15,
    )
    data = resp.json()
    if data.get("code") != 0:
        print(f"[setup] 创建多维表格失败: {data}", file=sys.stderr)
        sys.exit(1)
    app_token = data["data"]["app"]["app_token"]
    # 获取默认表格 ID
    resp = requests.get(
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables",
        headers=headers,
        timeout=10,
    )
    tables_data = resp.json()
    if tables_data.get("code") != 0 or not tables_data["data"]["items"]:
        print(f"[setup] 获取表格列表失败: {tables_data}", file=sys.stderr)
        sys.exit(1)
    table_id = tables_data["data"]["items"][0]["table_id"]
    print(f"[setup] 多维表格已创建: app_token={app_token}, table_id={table_id}")

    # 2. 创建字段
    print("[setup] 正在创建字段...")
    for field_def in BITABLE_FIELDS:
        body = {"field_name": field_def["field_name"], "type": field_def["type"]}
        if "property" in field_def:
            body["property"] = field_def["property"]
        resp = requests.post(
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            headers=headers,
            json=body,
            timeout=10,
        )
        fd = resp.json()
        status = "✅" if fd.get("code") == 0 else f"❌ {fd.get('msg', fd)}"
        print(f"  {field_def['field_name']}: {status}")

    # 3. 获取 base_url（从配置或默认飞书域名）
    base_url = cfg.get("bitable_base_url", "https://open.feishu.cn")

    # 4. 更新配置文件
    cfg["bitable_app_token"] = app_token
    cfg["bitable_table_id"] = table_id
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"[setup] 配置已更新: {CONFIG_PATH}")

    table_link = f"{base_url}/base/{app_token}?table={table_id}"
    print(f"[setup] 多维表格链接: {table_link}")
    print("[setup] ✅ 完成！请在飞书中打开以上链接确认。")


# ── CLI 入口 ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RedCap 飞书通知器")
    parser.add_argument("command", choices=["setup", "ask", "confirm", "notify"], help="命令")
    parser.add_argument("message", nargs="?", default="", help="消息内容")
    parser.add_argument("--timeout", type=int, default=300, help="等待超时秒数 (默认 300)")
    parser.add_argument("--project", default="", help="项目名")
    parser.add_argument("--fsm-state", default="", help="FSM 当前状态")
    parser.add_argument("--options", default="", help="可选项，逗号分隔")
    args = parser.parse_args()

    # setup 命令独立处理
    if args.command == "setup":
        run_setup()
        return

    if not args.message:
        parser.error(f"命令 '{args.command}' 需要提供 message 参数")

    config = load_config()
    if config is None:
        print("[feishu-notifier] 配置不存在或已禁用，跳过通知", file=sys.stderr)
        # 非阻塞命令直接退出；阻塞命令返回空
        if args.command == "notify":
            sys.exit(0)
        else:
            print("SKIP")
            sys.exit(0)

    notifier = FeishuNotifier(config)

    if args.command == "notify":
        notifier.notify(args.message, project=args.project)
        print("OK")

    elif args.command == "ask":
        response = notifier.ask(
            args.message,
            timeout=args.timeout,
            project=args.project,
            fsm_state=args.fsm_state,
            options=args.options,
        )
        if response:
            print(response)
            sys.exit(0)
        else:
            print("TIMEOUT")
            sys.exit(1)

    elif args.command == "confirm":
        confirmed = notifier.confirm(args.message, timeout=args.timeout, project=args.project)
        print("CONFIRMED" if confirmed else "CANCELLED")
        sys.exit(0 if confirmed else 1)


if __name__ == "__main__":
    main()
