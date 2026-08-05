from __future__ import annotations

from pathlib import Path
import sys

import uvicorn


REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT, REPO_ROOT / "src"):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)


if __name__ == "__main__":
    uvicorn.run(
        "apps.workbench.backend.app:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
    )
