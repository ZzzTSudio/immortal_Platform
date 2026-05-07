#!/usr/bin/env python3
"""Dev launcher: starts both backend and frontend dev servers."""

from __future__ import annotations

import os
import subprocess
import sys
import time


def run_backend() -> subprocess.Popen:
    env = {**os.environ, "IMMORTAL_RELOAD": "1"}
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.web.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"],
        env=env,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )


def run_frontend() -> subprocess.Popen:
    web_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
    return subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=web_dir,
    )


def main() -> None:
    print("Starting Immortal dev servers...")
    be = run_backend()
    time.sleep(2)
    fe = run_frontend()
    print(f"Backend: http://127.0.0.1:8000")
    print(f"Frontend: http://localhost:3000")
    print("Press Ctrl+C to stop both.")
    try:
        be.wait()
    except KeyboardInterrupt:
        pass
    finally:
        fe.terminate()
        be.terminate()
        fe.wait()
        be.wait()


if __name__ == "__main__":
    main()
