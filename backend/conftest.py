"""pytest 根配置：把 backend/ 加入 sys.path，保证 `import nia` 在任何 cwd 下可用。

测试全部离线运行：不依赖 MySQL / Redis / DeepSeek / 外网 DNS
（需要解析的地方用 monkeypatch 替换 ``url_safety._resolve_host``）。
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
