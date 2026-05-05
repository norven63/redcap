#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORD_PLACEHOLDER_RE = re.compile(r"(?i)(?<![A-Za-z0-9_-])(TODO|TBD)(?![A-Za-z0-9_-])|待补|待定")
BRACE_PLACEHOLDER_RE = re.compile(r"\{([^{}\n]{1,80})\}")
ANGLE_PLACEHOLDER_RE = re.compile(r"<([^<>\n]{1,80})>")
PLACEHOLDER_HINT_RE = re.compile(
    r"(任务|标题|日期|执行者|路径|文件|命令|结果|说明|问题|原因|优先级|编号|核心内容|一句话|用户原文|最终确认|topic|path|title|date|command|result)",
    re.IGNORECASE,
)
HTML_TAG_NAMES = {
    "a",
    "br",
    "code",
    "details",
    "div",
    "em",
    "p",
    "pre",
    "section",
    "span",
    "strong",
    "summary",
}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-human-output-quality-check] {message}")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"cannot read {path}: {exc}")


def section(text: str, heading: str) -> str:
    capture = False
    level = 0
    out: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^(#+)\s+(.+?)\s*$", line)
        if match:
            current_level = len(match.group(1))
            current_heading = match.group(2).strip()
            if capture and current_level <= level:
                break
            if current_heading == heading:
                capture = True
                level = current_level
                continue
        if capture:
            out.append(line)
    return "\n".join(out).strip()


def metadata_value(task_text: str, key: str) -> str:
    meta = section(task_text, "控制面元数据（机器校验）")
    for line in meta.splitlines():
        match = re.match(rf"^{re.escape(key)}:\s*(.*?)\s*$", line)
        if match:
            return match.group(1).strip()
    return ""


def resolve_report_from_task(task_file: Path) -> Path:
    task_text = read_text(task_file)
    report_rel = metadata_value(task_text, "task_report")
    if not report_rel:
        fail(f"task_report missing from {task_file}")
    report_path = Path(report_rel)
    if not report_path.is_absolute():
        report_path = task_file.parent / report_path
    return report_path.resolve()


def require_section(text: str, heading: str) -> str:
    body = section(text, heading)
    if not body:
        fail(f"missing or empty section: {heading}")
    return body


def require_phrase(body: str, phrase: str, heading: str) -> None:
    if phrase not in body:
        fail(f"{heading} missing phrase: {phrase}")


def reject_placeholders(body: str, heading: str) -> None:
    match = placeholder_match(body)
    if match:
        fail(f"{heading} contains placeholder-like text: {match}")


def strip_markdown_code(text: str) -> str:
    lines: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        lines.append(re.sub(r"`[^`]*`", "`CODE`", line))
    return "\n".join(lines)


def strip_markdown_markup_for_words(text: str) -> str:
    text = re.sub(r"\[[^\]\n]*\]\([^)]+\)", " LINK ", text)
    text = re.sub(r"<https?://[^>\n]+>", " URL ", text, flags=re.IGNORECASE)
    text = re.sub(r"https?://\S+", " URL ", text, flags=re.IGNORECASE)
    text = re.sub(r"</?[A-Za-z][A-Za-z0-9:-]*(?:\s+[^<>\n]*)?/?>", " HTML ", text)
    text = re.sub(r'"[^"\n]*"|\'[^\'\n]*\'', " QUOTE ", text)
    return text


def looks_like_placeholder_inner(inner: str, kind: str) -> bool:
    value = inner.strip()
    if not value:
        return False
    if value.startswith(("http://", "https://", "/", "#")):
        return False
    if kind == "angle":
        tag_name = value.lstrip("/").split(None, 1)[0].rstrip("/").lower()
        if tag_name in HTML_TAG_NAMES:
            return False
    if any(token in value for token in ['"', "'", ":", ",", "[", "]", "=", "\\"]):
        return False
    if re.search(r"\s", value) and not PLACEHOLDER_HINT_RE.search(value):
        return False
    if kind == "angle":
        return bool(PLACEHOLDER_HINT_RE.search(value))
    return bool(PLACEHOLDER_HINT_RE.search(value) or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,40}", value))


def placeholder_match(body: str) -> str:
    searchable = strip_markdown_code(body)
    word_searchable = strip_markdown_markup_for_words(searchable)
    word_match = WORD_PLACEHOLDER_RE.search(word_searchable)
    if word_match:
        return word_match.group(0)
    for match in BRACE_PLACEHOLDER_RE.finditer(searchable):
        inner = match.group(1)
        if looks_like_placeholder_inner(inner, "brace"):
            return match.group(0)
    for match in ANGLE_PLACEHOLDER_RE.finditer(searchable):
        inner = match.group(1)
        if looks_like_placeholder_inner(inner, "angle"):
            return match.group(0)
    return ""


def line_after_prefix(body: str, prefix: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return ""


def require_meaningful_line(body: str, prefix: str, heading: str) -> str:
    value = line_after_prefix(body, prefix)
    if len(value) < 2:
        fail(f"{heading} has weak or empty line: {prefix}")
    if placeholder_match(value):
        fail(f"{heading} line still contains placeholder: {prefix}")
    return value


def has_table_data_row(body: str) -> bool:
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if "---" in stripped:
            continue
        cells = [cell.strip(" `") for cell in stripped.strip("|").split("|")]
        if len(cells) < 3:
            continue
        first = cells[0].strip()
        if not first or first in {"术语", "{术语}"}:
            continue
        if placeholder_match(stripped):
            continue
        return True
    return False


def formal_completion_value(body: str) -> str:
    for line in body.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] == "已正式完成":
            return cells[1]
    return ""


def report_has_receipt_evidence(text: str) -> bool:
    receipt_body = section(text, "5.3 closeout runtime / receipt")
    if not receipt_body:
        return False
    for line in receipt_body.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip(" `") for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        label = cells[0].lower()
        value = cells[1].strip()
        if label == "closeout receipt":
            return bool(value) and value not in {"无", "none", "None", "-"}
    return False


def check_report(report_path: Path) -> None:
    text = read_text(report_path)
    if not text.lstrip().startswith("# 任务完成报告："):
        fail(f"{report_path} is not a RedCap task report")

    zero_one = require_section(text, "0.1 当前已完成")
    zero_two = require_section(text, "0.2 上一步完成的是")
    zero_three = require_section(text, "0.3 下一步计划做的是")
    zero_four = require_section(text, "0.4 整体计划脉络图与当前位置")
    zero_five = require_section(text, "0.5 是否需要 Norven 人工介入")
    glossary = require_section(text, "3.2.1 术语对照（按文件/功能解释）")
    completion = require_section(text, "5.4 完成等级（禁止混报）")

    for heading, body in [
        ("0.1 当前已完成", zero_one),
        ("0.2 上一步完成的是", zero_two),
        ("0.3 下一步计划做的是", zero_three),
        ("0.4 整体计划脉络图与当前位置", zero_four),
        ("0.5 是否需要 Norven 人工介入", zero_five),
        ("3.2.1 术语对照（按文件/功能解释）", glossary),
        ("5.4 完成等级（禁止混报）", completion),
    ]:
        reject_placeholders(body, heading)

    require_meaningful_line(zero_one, "- 当前已完成：", "0.1 当前已完成")
    require_meaningful_line(zero_two, "- 上一步完成的是：", "0.2 上一步完成的是")
    next_step = require_meaningful_line(zero_three, "- 下一步计划做的是：", "0.3 下一步计划做的是")
    require_meaningful_line(zero_four, "- 整体计划脉络图是：", "0.4 整体计划脉络图与当前位置")
    require_meaningful_line(zero_four, "- 当前所在位置：", "0.4 整体计划脉络图与当前位置")
    intervention = require_meaningful_line(zero_five, "- 人工介入：", "0.5 是否需要 Norven 人工介入")
    require_meaningful_line(zero_five, "- 说明：", "0.5 是否需要 Norven 人工介入")
    if not any(marker in intervention for marker in ["需要", "不需要"]):
        fail("0.5 是否需要 Norven 人工介入 must explicitly say 需要 or 不需要")

    if not has_table_data_row(glossary) and "无新增术语" not in glossary:
        fail("3.2.1 术语对照 must contain at least one explained term or explicitly say 无新增术语")

    for phrase in ["已实现", "已自检", "已独立验收", "已正式完成"]:
        require_phrase(completion, phrase, "5.4 完成等级（禁止混报）")

    formal_value = formal_completion_value(completion)
    if formal_value.startswith("是"):
        if not report_has_receipt_evidence(text):
            fail("formal completion is yes but closeout receipt evidence is missing")
        stale_next_step_markers = ["执行正式 closeout", "生成 receipt", "生成收据", "正在执行 closeout 收口"]
        if any(marker in next_step for marker in stale_next_step_markers):
            fail("formal completion is yes but next-step summary still says closeout/receipt remains to be done")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate human-facing RedCap report quality.")
    parser.add_argument("--report", help="Path to a task report to check.")
    parser.add_argument("--task-file", help="Task file whose task_report metadata should be checked.")
    args = parser.parse_args()

    if args.report:
        report_path = Path(args.report)
        if not report_path.is_absolute():
            report_path = (Path.cwd() / report_path).resolve()
    else:
        task_file = Path(args.task_file or ROOT / ".dev-task.md")
        if not task_file.is_absolute():
            task_file = (Path.cwd() / task_file).resolve()
        report_path = resolve_report_from_task(task_file)

    check_report(report_path)
    print(f"HUMAN_OUTPUT_QUALITY_OK {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
