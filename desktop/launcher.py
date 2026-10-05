from __future__ import annotations

import importlib
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import TextIO

APP_NAME = "Benefit Design Stress Lab"
SERVE = "--serve"
CHECK = "--check"
FONT = "/app/static/fonts/Geist-Variable.woff2"
LOG = Path.home() / ".benefit-stress-lab" / "desktop.log"
WINDOW_BACKENDS = {"darwin": "webview.platforms.cocoa", "win32": "webview.platforms.winforms"}
STATE_KEYS = (
    "workforce",
    "workforce_source",
    "workforce_settings",
    "costs",
    "current_plan",
    "alternatives",
    "settings",
    "assumptions",
    "analysis",
    "focus_plan",
    "inputs_version",
    "analysis_inputs_version",
    "run_id",
)


def resource_root() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    return Path(bundled) if bundled else Path(__file__).resolve().parents[1]


def open_log() -> TextIO:
    LOG.parent.mkdir(exist_ok=True)
    return LOG.open("a", encoding="utf-8", buffering=1)


def ensure_streams() -> None:
    if sys.stdout is None or sys.stderr is None:
        stream = open_log()
        sys.stdout = sys.stdout or stream
        sys.stderr = sys.stderr or stream


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def exit_with_parent() -> None:
    try:
        while os.read(0, 1024):
            pass
    except OSError:
        return
    os._exit(0)


def serve(port: int) -> None:
    from streamlit.web import cli

    threading.Thread(target=exit_with_parent, daemon=True).start()
    root = resource_root()
    os.chdir(root)
    sys.argv = [
        "streamlit",
        "run",
        str(root / "app" / "app.py"),
        "--global.developmentMode=false",
        "--server.headless=true",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
    ]
    cli.main()


def start_server(port: int) -> subprocess.Popen:
    command = [sys.executable, SERVE, str(port)]
    if not getattr(sys, "frozen", False):
        command.insert(1, str(Path(__file__).resolve()))
    return subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=open_log(),
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )


def status(port: int, path: str) -> int:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as response:
        return response.status


def wait_until_ready(port: int, server: subprocess.Popen, timeout: float = 120.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server.poll() is not None:
            return False
        try:
            if status(port, "/_stcore/health") == 200:
                return True
        except OSError:
            time.sleep(0.3)
    return False


def stop(server: subprocess.Popen) -> None:
    if server.stdin is not None:
        server.stdin.close()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


def open_window(url: str) -> None:
    import webview

    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.create_window(APP_NAME, url, width=1440, height=900, min_size=(1100, 700))
    webview.start()


def run_app() -> int:
    port = free_port()
    server = start_server(port)
    try:
        if not wait_until_ready(port, server):
            print("The app server did not start. See", LOG)
            return 1
        open_window(f"http://127.0.0.1:{port}")
    finally:
        stop(server)
    return 0


def self_check() -> int:
    from streamlit.testing.v1 import AppTest

    importlib.import_module("webview")
    if sys.platform in WINDOW_BACKENDS:
        importlib.import_module(WINDOW_BACKENDS[sys.platform])
    root = resource_root()
    os.chdir(root)
    sys.path.insert(0, str(root / "app"))

    home = AppTest.from_file(str(root / "app" / "app.py"), default_timeout=300).run()
    demo = next(item for item in home.button if item.label == "Load demonstration")
    demo.click().run()
    if home.exception or home.session_state["analysis"] is None:
        print("Self-check failed: the demonstration did not run.", home.exception)
        return 1

    results = AppTest.from_file(str(root / "app" / "pages" / "4_results.py"), default_timeout=300)
    for key in STATE_KEYS:
        results.session_state[key] = home.session_state[key]
    results.run()
    if results.exception or len(results.tabs) != 5:
        print("Self-check failed: the results page did not render.", results.exception)
        return 1

    port = free_port()
    server = start_server(port)
    try:
        served = wait_until_ready(port, server) and status(port, FONT) == 200
    finally:
        stop(server)
    if not served:
        print("Self-check failed: the server did not serve the app.")
        return 1
    print("Self-check passed.")
    return 0


def main() -> int:
    ensure_streams()
    os.environ.setdefault("STREAMLIT_GLOBAL_DEVELOPMENT_MODE", "false")
    os.environ.setdefault("STREAMLIT_LOGGER_LEVEL", "warning")
    if SERVE in sys.argv:
        serve(int(sys.argv[sys.argv.index(SERVE) + 1]))
        return 0
    if CHECK in sys.argv:
        return self_check()
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
