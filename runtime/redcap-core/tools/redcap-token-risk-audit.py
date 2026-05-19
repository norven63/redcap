#!/usr/bin/env python3
# 用途：runtime 公开入口兼容外壳；实际实现仍委托 compass/tools 权威脚本。
from __future__ import annotations

import runpy
import sys
from pathlib import Path

REDCAP_ROOT = Path(__file__).resolve().parents[3]
TARGET = REDCAP_ROOT / "compass/tools/redcap-token-risk-audit.py"

if not TARGET.is_file():
    raise SystemExit(f"[redcap-runtime-facade] missing delegated RedCap tool: {TARGET}")

sys.path.insert(0, str(TARGET.parent))
sys.argv[0] = str(TARGET)
runpy.run_path(str(TARGET), run_name="__main__")
