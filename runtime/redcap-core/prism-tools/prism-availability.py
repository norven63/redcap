#!/usr/bin/env python3
# 用途：runtime Prism 兼容外壳；实际实现仍委托 prism/tools 权威脚本。
from __future__ import annotations

import runpy
import sys
from pathlib import Path

REDCAP_ROOT = Path(__file__).resolve().parents[3]
TARGET = REDCAP_ROOT / "prism/tools/prism-availability.py"

if not TARGET.is_file():
    raise SystemExit(f"[redcap-runtime-prism-facade] missing delegated Prism tool: {TARGET}")

sys.path.insert(0, str(TARGET.parent))
sys.argv[0] = str(TARGET)
runpy.run_path(str(TARGET), run_name="__main__")

