"""Start the API (http://localhost:8000) and the web app (http://localhost:8081) together.

    python dev.py

With TASTE_PG_BIN in .env (a folder with pg_ctl, e.g. D:/Tools/pgsql/bin), it also starts the
local Postgres in data/pg (create it once: see README, Accounts) and applies migrations first.
Ctrl+C stops everything. If either one exits, the other is stopped too.
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


def env_file() -> dict[str, str]:
    path = ROOT / ".env"
    if not path.exists():
        return {}
    pairs = (line.split("=", 1) for line in path.read_text().splitlines() if "=" in line and not line.startswith("#"))
    return {k.strip(): v.strip().strip('"') for k, v in pairs}


def postgres(bin_dir: Path) -> bool:
    """Start the local Postgres in data/pg if it isn't running; True if this started it."""
    exe = lambda name: str(bin_dir / (f"{name}.exe" if WINDOWS else name))
    if subprocess.run([exe("pg_isready"), "-h", "localhost", "-q"]).returncode == 0:
        return False
    print("[dev] starting postgres (data/pg)", flush=True)
    # Its output goes to a log: pg_ctl's server keeps any pipe it's given open.
    subprocess.run([exe("pg_ctl"), "-D", str(ROOT / "data" / "pg"), "-l", str(ROOT / "data" / "pg.log"),
                    "-o", "-c listen_addresses=localhost", "-w", "start"],
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return True


def main():
    uvicorn = VENV / ("uvicorn.exe" if WINDOWS else "uvicorn")
    if not uvicorn.exists():
        sys.exit(f'[dev] {uvicorn} not found: run  python -m venv .venv  and  pip install -e "backend[dev]"')
    if not (ROOT / "frontend" / "node_modules").exists():
        sys.exit("[dev] frontend/node_modules not found: run  npm install  in frontend/")

    pg_bin = env_file().get("TASTE_PG_BIN")
    started_pg = postgres(Path(pg_bin)) if pg_bin else False
    if pg_bin:
        alembic = VENV / ("alembic.exe" if WINDOWS else "alembic")
        subprocess.run([str(alembic), "upgrade", "head"], cwd=ROOT / "backend", check=True)

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
        if started_pg:
            pg_ctl = Path(pg_bin) / ("pg_ctl.exe" if WINDOWS else "pg_ctl")
            subprocess.run([str(pg_ctl), "-D", str(ROOT / "data" / "pg"), "-m", "fast", "stop"], capture_output=True)


if __name__ == "__main__":
    main()
