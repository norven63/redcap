#!/usr/bin/env python3
"""
RedCap 飞书通知器 — bot 单聊 + 窗口式接收

功能：
  setup          校验 lark-cli 通道与本地配置
  notify         发送通知；可选打开“任务完成回访窗口”
  ask            发送问题并在前台阻塞等待飞书回复
  resume         恢复等待已有窗口
  confirm        发送确认请求并解析结果
  close-window   主动关闭当前窗口（给控制面兜底）
  watch-window   轮询指定窗口（内部命令，也可手动调试）
  pending-scan   补扫固定单聊历史，把窗口外消息收入待处理入口
  pending-count  输出待处理数量
  pending-list   输出待处理摘要
  pending-dismiss 标记待处理项已删除
  pending-promote 标记待处理项已提取

配置：
  默认读取同级目录的 feishu-config.json，可用 REDCAP_FEISHU_CONFIG_PATH 覆盖。
  当配置缺失或 notify_enabled=false 时：
    - notify / pending-* / close-window 返回成功并静默跳过
    - ask / resume / confirm 返回 SKIP，保持旧兼容语义
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


COMPASS_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(os.environ.get("REDCAP_FEISHU_CONFIG_PATH", COMPASS_ROOT / "tools" / "feishu-config.json"))
STATE_DIR = Path(os.environ.get("REDCAP_FEISHU_STATE_DIR", COMPASS_ROOT / ".workflow" / "feishu"))
WINDOWS_DIR = STATE_DIR / "windows"
ACTIVE_WINDOW_PATH = STATE_DIR / "active-window.json"
PENDING_ITEMS_PATH = STATE_DIR / "pending-items.json"
CHAT_CURSOR_PATH = STATE_DIR / "chat-cursor.json"

DEFAULT_HISTORY_LIMIT = 100
DEFAULT_KNOWN_ID_LIMIT = 200
YES_WORDS = {"确认", "是", "yes", "y", "ok", "确定", "同意", "继续", "继续下一步"}
NO_WORDS = {"取消", "否", "no", "n", "停止", "不用", "算了"}


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def load_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default


def save_json_file(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    temp_path.replace(path)


def utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def trim_text(text: str, limit: int = 80) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def dedupe_ids(values: list[str], limit: int = DEFAULT_KNOWN_ID_LIMIT) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        ordered.append(value)
        seen.add(value)
    if len(ordered) <= limit:
        return ordered
    return ordered[:limit]


def env_or_cfg(raw: dict[str, Any], env_keys: list[str], cfg_keys: list[str], default: Any = "") -> Any:
    for key in env_keys:
        value = os.environ.get(key)
        if value not in (None, ""):
            return value
    for key in cfg_keys:
        value = raw.get(key)
        if value not in (None, ""):
            return value
    return default


def normalize_sender_type(message: dict[str, Any]) -> str:
    sender = message.get("sender") or {}
    sender_type = sender.get("sender_type") or ""
    return str(sender_type).strip().lower()


def is_human_message(message: dict[str, Any]) -> bool:
    if message.get("deleted"):
        return False
    sender_type = normalize_sender_type(message)
    return sender_type not in {"app", "bot", ""}


def normalized_message_text(message: dict[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)
    return str(content).strip()


@dataclass
class FeishuConfig:
    notify_enabled: bool
    transport: str
    cli_bin: str
    profile: str
    chat_id: str
    identity: str
    fast_poll_seconds: int
    fast_poll_window_seconds: int
    slow_poll_seconds: int
    followup_timeout_seconds: int
    history_limit: int
    known_id_limit: int


def load_config() -> Optional[FeishuConfig]:
    if not CONFIG_PATH.exists():
        return None

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        eprint(f"[feishu-notifier] 配置文件读取失败: {exc}")
        return None

    if not raw.get("notify_enabled", False):
        return None

    transport = env_or_cfg(
        raw,
        ["REDCAP_FEISHU_TRANSPORT", "FEISHU_NOTIFY_TRANSPORT"],
        ["transport"],
        "lark_cli_dm",
    )
    if transport != "lark_cli_dm":
        eprint(f"[feishu-notifier] 暂不支持 transport={transport}，当前只支持 lark_cli_dm")
        return None

    cli_bin = str(
        env_or_cfg(
            raw,
            ["REDCAP_FEISHU_CLI_BIN", "FEISHU_NOTIFY_CLI_BIN"],
            ["lark_cli_bin", "cli_bin"],
            "lark-cli",
        )
    )
    profile = str(
        env_or_cfg(
            raw,
            ["REDCAP_FEISHU_PROFILE", "FEISHU_NOTIFY_PROFILE"],
            ["lark_cli_profile", "profile"],
        )
    )
    chat_id = str(
        env_or_cfg(
            raw,
            ["REDCAP_FEISHU_CHAT_ID", "FEISHU_CHAT_ID"],
            ["lark_chat_id", "chat_id"],
        )
    )
    identity = str(
        env_or_cfg(
            raw,
            ["REDCAP_FEISHU_IDENTITY", "FEISHU_NOTIFY_AS"],
            ["lark_identity", "identity"],
            "bot",
        )
    )

    if not profile or not chat_id:
        eprint("[feishu-notifier] 缺少 lark_cli_profile / lark_chat_id，跳过飞书链路")
        return None

    def as_int(value: Any, default: int) -> int:
        try:
            parsed = int(value)
            return parsed if parsed > 0 else default
        except (TypeError, ValueError):
            return default

    return FeishuConfig(
        notify_enabled=True,
        transport=transport,
        cli_bin=cli_bin,
        profile=profile,
        chat_id=chat_id,
        identity=identity,
        fast_poll_seconds=as_int(env_or_cfg(raw, ["REDCAP_FEISHU_FAST_POLL_SECONDS"], ["fast_poll_seconds"], 10), 10),
        fast_poll_window_seconds=as_int(
            env_or_cfg(raw, ["REDCAP_FEISHU_FAST_POLL_WINDOW_SECONDS"], ["fast_poll_window_seconds"], 60),
            60,
        ),
        slow_poll_seconds=as_int(env_or_cfg(raw, ["REDCAP_FEISHU_SLOW_POLL_SECONDS"], ["slow_poll_seconds"], 60), 60),
        followup_timeout_seconds=as_int(
            env_or_cfg(raw, ["REDCAP_FEISHU_FOLLOWUP_TIMEOUT_SECONDS"], ["followup_timeout_seconds"], 1800),
            1800,
        ),
        history_limit=as_int(env_or_cfg(raw, ["REDCAP_FEISHU_HISTORY_LIMIT"], ["history_limit"], DEFAULT_HISTORY_LIMIT), DEFAULT_HISTORY_LIMIT),
        known_id_limit=as_int(env_or_cfg(raw, ["REDCAP_FEISHU_KNOWN_ID_LIMIT"], ["known_id_limit"], DEFAULT_KNOWN_ID_LIMIT), DEFAULT_KNOWN_ID_LIMIT),
    )


class FeishuNotifier:
    def __init__(self, config: FeishuConfig):
        self.config = config
        WINDOWS_DIR.mkdir(parents=True, exist_ok=True)

    def _ensure_cli_available(self) -> None:
        cli_bin = self.config.cli_bin
        if "/" in cli_bin:
            if not Path(cli_bin).exists():
                raise RuntimeError(f"CLI 不存在: {cli_bin}")
            return
        if shutil.which(cli_bin) is None:
            raise RuntimeError(f"CLI 不存在: {cli_bin}")

    def _run_cli_json(self, *args: str) -> dict[str, Any]:
        self._ensure_cli_available()
        command = [self.config.cli_bin, "--profile", self.config.profile, *args]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(detail or f"lark-cli 执行失败: {' '.join(command)}")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"lark-cli 输出不是合法 JSON: {exc}") from exc
        if not payload.get("ok", True):
            error = payload.get("error") or {}
            raise RuntimeError(str(error.get("message") or error or payload))
        return payload

    def _window_path(self, window_id: str) -> Path:
        return WINDOWS_DIR / f"{window_id}.json"

    def _load_window(self, window_id: str) -> Optional[dict[str, Any]]:
        window = load_json_file(self._window_path(window_id), None)
        return window if isinstance(window, dict) else None

    def _save_window(self, window: dict[str, Any]) -> None:
        save_json_file(self._window_path(window["window_id"]), window)

    def _active_window_id(self) -> str:
        active = load_json_file(ACTIVE_WINDOW_PATH, {})
        if isinstance(active, dict):
            return str(active.get("window_id", "") or "")
        return ""

    def _set_active_window(self, window_id: str) -> None:
        save_json_file(ACTIVE_WINDOW_PATH, {"window_id": window_id, "updated_at": utc_now_iso()})

    def _clear_active_window_if_match(self, window_id: str) -> None:
        if self._active_window_id() == window_id:
            try:
                ACTIVE_WINDOW_PATH.unlink()
            except FileNotFoundError:
                pass

    def _pending_items(self) -> list[dict[str, Any]]:
        items = load_json_file(PENDING_ITEMS_PATH, [])
        if isinstance(items, list):
            return items
        return []

    def _save_pending_items(self, items: list[dict[str, Any]]) -> None:
        save_json_file(PENDING_ITEMS_PATH, items)

    def _cursor_state(self) -> dict[str, Any]:
        cursor = load_json_file(CHAT_CURSOR_PATH, {})
        if isinstance(cursor, dict):
            return cursor
        return {}

    def _save_cursor_state(self, cursor: dict[str, Any]) -> None:
        save_json_file(CHAT_CURSOR_PATH, cursor)

    def _recent_messages(self, limit: Optional[int] = None) -> list[dict[str, Any]]:
        remaining = limit or self.config.history_limit
        page_token = ""
        messages: list[dict[str, Any]] = []

        while remaining > 0:
            page_size = str(min(50, remaining))
            args = [
                "im",
                "+chat-messages-list",
                "--as",
                self.config.identity,
                "--chat-id",
                self.config.chat_id,
                "--sort",
                "desc",
                "--page-size",
                page_size,
            ]
            if page_token:
                args.extend(["--page-token", page_token])
            payload = self._run_cli_json(*args)
            data = payload.get("data") or {}
            page_messages = data.get("messages") or []
            if not isinstance(page_messages, list):
                break
            messages.extend(page_messages)
            remaining -= len(page_messages)
            page_token = str(data.get("page_token") or "")
            if not data.get("has_more") or not page_token or not page_messages:
                break

        return messages

    def _snapshot_known_ids(self) -> list[str]:
        messages = self._recent_messages(self.config.history_limit)
        ids = [str(message.get("message_id", "") or "") for message in messages]
        return dedupe_ids(ids, self.config.known_id_limit)

    def _next_poll_seconds(self, window: dict[str, Any]) -> int:
        opened_at_epoch = float(window.get("opened_at_epoch") or time.time())
        elapsed = max(0, time.time() - opened_at_epoch)
        if elapsed <= int(window.get("fast_poll_window_seconds", self.config.fast_poll_window_seconds)):
            return int(window.get("fast_poll_seconds", self.config.fast_poll_seconds))
        return int(window.get("slow_poll_seconds", self.config.slow_poll_seconds))

    def _message_hit_window(self, window: dict[str, Any]) -> Optional[dict[str, Any]]:
        known_ids = set(window.get("known_message_ids") or [])
        consumed_ids = set(window.get("consumed_message_ids") or [])
        messages = self._recent_messages(self.config.history_limit)
        latest_ids = [str(message.get("message_id", "") or "") for message in messages]
        window["known_message_ids"] = dedupe_ids(latest_ids + list(known_ids), self.config.known_id_limit)
        self._save_window(window)

        for message in reversed(messages):
            message_id = str(message.get("message_id", "") or "")
            if not message_id or message_id in known_ids or message_id in consumed_ids:
                continue
            if not is_human_message(message):
                continue
            return message
        return None

    def _send_text(self, text: str) -> dict[str, Any]:
        payload = self._run_cli_json(
            "im",
            "+messages-send",
            "--as",
            self.config.identity,
            "--chat-id",
            self.config.chat_id,
            "--text",
            text,
        )
        return payload.get("data") or {}

    def _reply_text(self, message_id: str, text: str) -> None:
        self._run_cli_json(
            "im",
            "+messages-reply",
            "--as",
            self.config.identity,
            "--message-id",
            message_id,
            "--text",
            text,
        )

    def _close_existing_window(self, reason: str) -> None:
        active_window_id = self._active_window_id()
        if not active_window_id:
            return
        self.close_window(active_window_id, reason)

    def create_window(
        self,
        window_type: str,
        outbound_message: str,
        project: str,
        timeout_seconds: int,
        reply_action: str,
        fsm_state: str = "",
        options: str = "",
        background_watch: bool = False,
    ) -> dict[str, Any]:
        self._close_existing_window("replaced-by-new-window")

        known_ids = self._snapshot_known_ids()
        send_result = self._send_text(outbound_message)
        anchor_message_id = str(send_result.get("message_id", "") or "")
        opened_at_epoch = time.time()
        window_id = uuid.uuid4().hex
        window = {
            "window_id": window_id,
            "type": window_type,
            "status": "active",
            "project": project,
            "fsm_state": fsm_state,
            "options": options,
            "reply_action": reply_action,
            "message": outbound_message,
            "anchor_message_id": anchor_message_id,
            "opened_at": utc_now_iso(),
            "opened_at_epoch": opened_at_epoch,
            "timeout_seconds": timeout_seconds,
            "fast_poll_seconds": self.config.fast_poll_seconds,
            "fast_poll_window_seconds": self.config.fast_poll_window_seconds,
            "slow_poll_seconds": self.config.slow_poll_seconds,
            "known_message_ids": dedupe_ids([anchor_message_id, *known_ids], self.config.known_id_limit),
            "consumed_message_ids": [],
            "last_reply": "",
            "last_reply_message_id": "",
            "close_reason": "",
            "closed_at": "",
            "background_watch": background_watch,
            "background_watch_pid": "",
        }
        self._save_window(window)
        self._set_active_window(window_id)

        if background_watch:
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "watch-window",
                    window_id,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                env=os.environ.copy(),
            )
            window["background_watch_pid"] = str(process.pid)
            self._save_window(window)

        return window

    def close_window(
        self,
        window_id: str,
        reason: str,
        matched_message: Optional[dict[str, Any]] = None,
    ) -> None:
        window = self._load_window(window_id)
        if not window:
            return
        if window.get("status") == "closed":
            self._clear_active_window_if_match(window_id)
            return
        window["status"] = "closed"
        window["close_reason"] = reason
        window["closed_at"] = utc_now_iso()
        if matched_message:
            message_id = str(matched_message.get("message_id", "") or "")
            if message_id:
                window["consumed_message_ids"] = dedupe_ids(
                    [message_id, *(window.get("consumed_message_ids") or [])],
                    self.config.known_id_limit,
                )
                window["last_reply_message_id"] = message_id
            window["last_reply"] = normalized_message_text(matched_message)
        self._save_window(window)
        self._clear_active_window_if_match(window_id)

    def _enqueue_pending(
        self,
        message: dict[str, Any],
        source: str,
        window: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        items = self._pending_items()
        message_id = str(message.get("message_id", "") or "")
        for item in items:
            if item.get("message_id") == message_id:
                return item

        item = {
            "id": f"pending-{time.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
            "status": "open",
            "source": source,
            "project": (window or {}).get("project", ""),
            "window_id": (window or {}).get("window_id", ""),
            "window_type": (window or {}).get("type", ""),
            "message_id": message_id,
            "message_create_time": str(message.get("create_time", "") or ""),
            "captured_at": utc_now_iso(),
            "sender_type": normalize_sender_type(message),
            "content": normalized_message_text(message),
            "summary": trim_text(normalized_message_text(message), 90),
        }
        items.append(item)
        self._save_pending_items(items)

        cursor = self._cursor_state()
        known_ids = list(cursor.get("known_message_ids") or [])
        known_ids = dedupe_ids([message_id, *known_ids], self.config.known_id_limit)
        cursor.update({
            "known_message_ids": known_ids,
            "last_scan_at": utc_now_iso(),
            "bootstrapped": True,
        })
        self._save_cursor_state(cursor)
        return item

    def _ack_reply(self, message_id: str, text: str) -> None:
        try:
            self._reply_text(message_id, text)
        except Exception:
            self._send_text(text)

    def _process_window_reply(self, window: dict[str, Any], message: dict[str, Any]) -> str:
        message_id = str(message.get("message_id", "") or "")
        reply_text = normalized_message_text(message)
        if window.get("reply_action") == "queue":
            item = self._enqueue_pending(message, "followup-window", window)
            if message_id:
                self._ack_reply(
                    message_id,
                    f"已收到这条飞书回复，已记入待处理入口（{item['id']}）。下次回到 CLI 时，我会提醒继续处理。",
                )
        else:
            if message_id:
                self._ack_reply(message_id, "已收到这条飞书回复，当前等待窗口会继续执行。")
        self.close_window(window["window_id"], "reply-received", message)
        return reply_text

    def wait_for_window(self, window_id: str, timeout_override: Optional[int] = None) -> Optional[str]:
        while True:
            window = self._load_window(window_id)
            if not window:
                return None
            if window.get("status") != "active":
                return str(window.get("last_reply") or "") or None
            if self._active_window_id() != window_id:
                self.close_window(window_id, "not-active-anymore")
                return None

            matched_message = self._message_hit_window(window)
            if matched_message:
                return self._process_window_reply(window, matched_message)

            timeout_seconds = timeout_override if (timeout_override is not None and timeout_override > 0) else int(
                window.get("timeout_seconds") or 0
            )
            opened_at_epoch = float(window.get("opened_at_epoch") or time.time())
            if timeout_seconds > 0 and (time.time() - opened_at_epoch) >= timeout_seconds:
                self.close_window(window_id, "timeout")
                return None

            time.sleep(self._next_poll_seconds(window))

    def notify(
        self,
        message: str,
        project: str = "",
        window_type: str = "none",
        window_timeout: int = 0,
        background_watch: bool = True,
    ) -> Optional[str]:
        if window_type == "followup":
            timeout_seconds = window_timeout or self.config.followup_timeout_seconds
            outbound = (
                f"{message}\n\n——\n可直接回复这条单聊。"
                "如果回访窗口仍有效，我会收下这条回复；如果此时任务已经结束，我会把它记入待处理入口，并在你下次回到 CLI 时提醒。"
            )
            window = self.create_window(
                window_type="followup",
                outbound_message=outbound,
                project=project,
                timeout_seconds=timeout_seconds,
                reply_action="queue",
                background_watch=background_watch,
            )
            print(f"FEISHU_WINDOW_ID={window['window_id']}", file=sys.stderr)
            return window["window_id"]

        self._send_text(message)
        return None

    def ask(
        self,
        question: str,
        timeout: int = 0,
        project: str = "",
        fsm_state: str = "",
        options: str = "",
    ) -> Optional[str]:
        display = question.strip()
        if options:
            display += f"\n\n可选项：{options}"
        display += "\n\n——\n可直接回复这条单聊；只要当前等待窗口仍有效，我会继续执行。"
        window = self.create_window(
            window_type="wait-reply",
            outbound_message=display,
            project=project,
            timeout_seconds=timeout,
            reply_action="return",
            fsm_state=fsm_state,
            options=options,
            background_watch=False,
        )
        print(f"FEISHU_RECORD_ID={window['window_id']}", file=sys.stderr)
        return self.wait_for_window(window["window_id"])

    def resume(self, window_id: str, timeout: int = 0) -> Optional[str]:
        window = self._load_window(window_id)
        if not window:
            eprint(f"[feishu-notifier] 窗口不存在: {window_id}")
            return None
        if window.get("status") == "closed":
            return str(window.get("last_reply") or "") or None
        self._set_active_window(window_id)
        return self.wait_for_window(window_id, timeout_override=timeout or None)

    def confirm(self, message: str, timeout: int = 120, project: str = "") -> bool:
        response = self.ask(
            question=message,
            timeout=timeout,
            project=project,
            options="确认,取消",
        )
        if response is None:
            return False
        normalized = response.lower().strip()
        if normalized in YES_WORDS:
            return True
        if normalized in NO_WORDS:
            return False
        return False

    def close_active_window(self, reason: str) -> None:
        active_window_id = self._active_window_id()
        if active_window_id:
            self.close_window(active_window_id, reason)

    def pending_scan(self) -> int:
        active_window_id = self._active_window_id()
        if active_window_id:
            return 0

        messages = self._recent_messages(self.config.history_limit)
        latest_ids = [str(message.get("message_id", "") or "") for message in messages]
        cursor = self._cursor_state()
        known_ids = set(cursor.get("known_message_ids") or [])

        if not cursor.get("bootstrapped"):
            cursor["bootstrapped"] = True
            cursor["known_message_ids"] = dedupe_ids(latest_ids, self.config.known_id_limit)
            cursor["last_scan_at"] = utc_now_iso()
            self._save_cursor_state(cursor)
            return 0

        new_count = 0
        for message in reversed(messages):
            message_id = str(message.get("message_id", "") or "")
            if not message_id or message_id in known_ids:
                continue
            if not is_human_message(message):
                continue
            self._enqueue_pending(message, "history-scan")
            new_count += 1

        cursor["known_message_ids"] = dedupe_ids(latest_ids + list(known_ids), self.config.known_id_limit)
        cursor["last_scan_at"] = utc_now_iso()
        cursor["bootstrapped"] = True
        self._save_cursor_state(cursor)
        return new_count

    def pending_count(self) -> int:
        return sum(1 for item in self._pending_items() if item.get("status") == "open")

    def pending_list(self, limit: int = 20) -> list[str]:
        items = [item for item in self._pending_items() if item.get("status") == "open"]
        items.sort(key=lambda item: str(item.get("captured_at") or ""), reverse=True)
        lines = []
        for item in items[:limit]:
            source = item.get("source", "unknown")
            captured_at = item.get("captured_at", "unknown")
            lines.append(f"{item['id']} | {captured_at} | {source} | {item.get('summary', '')}")
        return lines

    def _mark_pending(self, item_id: str, status: str) -> bool:
        items = self._pending_items()
        changed = False
        for item in items:
            if item.get("id") != item_id:
                continue
            item["status"] = status
            item["resolved_at"] = utc_now_iso()
            changed = True
            break
        if changed:
            self._save_pending_items(items)
        return changed

    def pending_dismiss(self, item_id: str) -> bool:
        return self._mark_pending(item_id, "dismissed")

    def pending_promote(self, item_id: str) -> bool:
        return self._mark_pending(item_id, "promoted")

    def setup(self) -> None:
        self._ensure_cli_available()
        payload = self._run_cli_json(
            "im",
            "+messages-send",
            "--as",
            self.config.identity,
            "--chat-id",
            self.config.chat_id,
            "--text",
            "RedCap 飞书 setup dry-run",
            "--dry-run",
        )
        save_json_file(
            CHAT_CURSOR_PATH,
            {
                "bootstrapped": False,
                "known_message_ids": [],
                "last_scan_at": "",
                "validated_at": utc_now_iso(),
            },
        )
        print("TRANSPORT=lark_cli_dm")
        print(f"CLI_BIN={self.config.cli_bin}")
        print(f"PROFILE={self.config.profile}")
        print(f"CHAT_ID={self.config.chat_id}")
        print(f"IDENTITY={self.config.identity}")
        print(f"STATE_DIR={STATE_DIR}")
        print(f"DRY_RUN_OK={'ok' if payload.get('ok', True) else 'fail'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap 飞书通知器")
    parser.add_argument(
        "command",
        choices=[
            "setup",
            "notify",
            "ask",
            "resume",
            "confirm",
            "close-window",
            "watch-window",
            "pending-scan",
            "pending-count",
            "pending-list",
            "pending-dismiss",
            "pending-promote",
        ],
        help="命令",
    )
    parser.add_argument("message", nargs="?", default="", help="消息内容；resume/watch-window/close-window 时为 window_id")
    parser.add_argument("--timeout", type=int, default=0, help="等待超时秒数")
    parser.add_argument("--project", default="", help="项目名")
    parser.add_argument("--fsm-state", default="", help="FSM 当前状态")
    parser.add_argument("--options", default="", help="可选项，逗号分隔")
    parser.add_argument("--window-type", choices=["none", "followup"], default="none", help="notify 是否打开回访窗口")
    parser.add_argument("--window-timeout", type=int, default=0, help="回访窗口超时秒数")
    parser.add_argument("--limit", type=int, default=20, help="pending-list 的输出上限")
    parser.add_argument("--no-background-watch", action="store_true", help="notify followup 时不拉起后台 watch")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    raw_config_exists = CONFIG_PATH.exists()
    config = load_config()

    if args.command == "setup":
        if config is None:
            if raw_config_exists:
                eprint("[feishu-notifier] 当前配置已存在，但缺少 lark_cli_profile / lark_chat_id 或 notify_enabled=false")
            else:
                eprint(f"[feishu-notifier] 配置不存在：{CONFIG_PATH}")
            sys.exit(1)
        FeishuNotifier(config).setup()
        return

    if config is None:
        if args.command in {"notify", "pending-scan", "pending-count", "pending-list", "pending-dismiss", "pending-promote", "close-window"}:
            if args.command == "pending-count":
                print("0")
            elif args.command == "pending-list":
                print("")
            elif args.command in {"pending-dismiss", "pending-promote"}:
                print("MISSING")
                sys.exit(1)
            else:
                print("OK")
            return
        print("SKIP")
        return

    notifier = FeishuNotifier(config)

    if args.command == "notify":
        if not args.message:
            raise SystemExit("notify 需要 message")
        notifier.notify(
            args.message,
            project=args.project,
            window_type=args.window_type,
            window_timeout=args.window_timeout,
            background_watch=not args.no_background_watch,
        )
        print("OK")
        return

    if args.command == "ask":
        if not args.message:
            raise SystemExit("ask 需要 message")
        response = notifier.ask(
            args.message,
            timeout=args.timeout,
            project=args.project,
            fsm_state=args.fsm_state,
            options=args.options,
        )
        if response:
            print(response)
            return
        print("TIMEOUT")
        raise SystemExit(1)

    if args.command == "resume":
        if not args.message:
            raise SystemExit("resume 需要 window_id")
        response = notifier.resume(args.message, timeout=args.timeout)
        if response:
            print(response)
            return
        print("TIMEOUT")
        raise SystemExit(1)

    if args.command == "confirm":
        if not args.message:
            raise SystemExit("confirm 需要 message")
        confirmed = notifier.confirm(args.message, timeout=args.timeout or 120, project=args.project)
        print("CONFIRMED" if confirmed else "CANCELLED")
        raise SystemExit(0 if confirmed else 1)

    if args.command == "close-window":
        if not args.message:
            raise SystemExit("close-window 需要 window_id")
        notifier.close_window(args.message, "closed-by-cli")
        print("OK")
        return

    if args.command == "watch-window":
        if not args.message:
            raise SystemExit("watch-window 需要 window_id")
        response = notifier.wait_for_window(args.message)
        if response:
            print(response)
        else:
            print("TIMEOUT")
        return

    if args.command == "pending-scan":
        print(str(notifier.pending_scan()))
        return

    if args.command == "pending-count":
        print(str(notifier.pending_count()))
        return

    if args.command == "pending-list":
        print("\n".join(notifier.pending_list(limit=args.limit)))
        return

    if args.command == "pending-dismiss":
        if not args.message:
            raise SystemExit("pending-dismiss 需要 item_id")
        if notifier.pending_dismiss(args.message):
            print("OK")
            return
        print("MISSING")
        raise SystemExit(1)

    if args.command == "pending-promote":
        if not args.message:
            raise SystemExit("pending-promote 需要 item_id")
        if notifier.pending_promote(args.message):
            print("OK")
            return
        print("MISSING")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
