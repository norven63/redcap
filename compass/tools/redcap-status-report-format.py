#!/usr/bin/env python3
# 用途：运行时与收尾脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#runtime-and-closeout

from __future__ import annotations

import argparse


def line(value: str, fallback: str) -> str:
    value = " ".join((value or "").split())
    return value if value else fallback


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a compact human-facing RedCap status surface.")
    parser.add_argument("--manual", default="不需要")
    parser.add_argument("--blocked", default="无")
    parser.add_argument("--next-start", default="是")
    parser.add_argument("--panorama", default="未声明")
    parser.add_argument("--position", default="未声明")
    parser.add_argument("--done", default="未声明")
    parser.add_argument("--previous", default="未声明")
    parser.add_argument("--next", default="未声明")
    parser.add_argument("--validation", default="未声明")
    args = parser.parse_args()

    print("## RedCap 状态面")
    print(f"- 人工协助：{line(args.manual, '不需要')}")
    print(f"- 阻塞状态：{line(args.blocked, '无')}")
    print(f"- 下一步可直接开始：{line(args.next_start, '是')}")
    print(f"- 任务全景图：{line(args.panorama, '未声明')}")
    print(f"- 当前位置：{line(args.position, '未声明')}")
    print(f"- 当前已完成：{line(args.done, '未声明')}")
    print(f"- 上一步完成的是：{line(args.previous, '未声明')}")
    print(f"- 下一步计划做的是：{line(args.next, '未声明')}")
    print(f"- 验收/风险：{line(args.validation, '未声明')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
