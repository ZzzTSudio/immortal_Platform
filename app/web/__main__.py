"""Entry point: python -m app.web"""

from __future__ import annotations

import os
import sys


def main() -> None:
    import uvicorn
    from app.paths import project_root

    # Ensure dist exists for static files
    dist_dir = project_root() / "web" / "dist"
    if not dist_dir.is_dir():
        print("Warning: web/dist not found. Run `cd web && npm run build` first.", file=sys.stderr)

    host = os.environ.get("IMMORTAL_HOST", "0.0.0.0")
    port = int(os.environ.get("IMMORTAL_PORT", "8800"))
    reload = os.environ.get("IMMORTAL_RELOAD", "0") == "1"

    uvicorn.run(
        "app.web.main:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
