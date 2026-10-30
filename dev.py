"""Start the API (http://localhost:8000) and the web app (http://localhost:8081) together.

    python dev.py

Ctrl+C stops both. If either one exits, the other is stopped too.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WINDOWS = os.name == "nt"
VENV = ROOT / ".venv" / ("Scripts" if WINDOWS else "bin")


def start(name, args, cwd, **kwargs):
    print(f"[dev] starting {name}: {' '.join(args)}", flush=True)
    return name, subprocess.Popen(args, cwd=cwd, **kwargs)


def stop(proc):
    if proc.poll() is not None:
        return
    if WINDOWS:  # npx runs node in a child process, so kill the whole tree
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.terminate()
    proc.wait()


def main():
    uvicorn = VENV / ("uvicorn.exe" if WINDOWS else "uvicorn")
    if not uvicorn.exists():
        sys.exit(f'[dev] {uvicorn} not found: run  python -m venv .venv  and  pip install -e "backend[dev]"')
    if not (ROOT / "frontend" / "node_modules").exists():
        sys.exit("[dev] frontend/node_modules not found: run  npm install  in frontend/")

    procs = [
        start("api", [str(uvicorn), "taste.api.app:app", "--reload", "--port", "8000"],
              cwd=ROOT / "backend", stdin=subprocess.DEVNULL),
        # Expo keeps the terminal's input, so its shortcuts (w, r, ...) still work.
        start("web", ["npx.cmd" if WINDOWS else "npx", "expo", "start", "--web", "--port", "8081"],
              cwd=ROOT / "frontend"),
    ]
    try:
        while True:
            for name, proc in procs:
                if proc.poll() is not None:
                    print(f"[dev] {name} exited with code {proc.returncode}, stopping the rest", flush=True)
                    return
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[dev] stopping", flush=True)
    finally:
        for _, proc in procs:
            stop(proc)


if __name__ == "__main__":
    main()
