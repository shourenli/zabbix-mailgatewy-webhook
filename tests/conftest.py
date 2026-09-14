# -*- coding: utf-8 -*-
"""pytest 根配置：把项目 src/ 加入 sys.path，使 `import gateway` 可用。"""
import sys
from pathlib import Path

# conftest.py 位于仓库根目录下的 tests/ 子目录，
# 仓库根 = 本文件父目录的父目录（parents[1]），src/ 位于仓库根下。
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))