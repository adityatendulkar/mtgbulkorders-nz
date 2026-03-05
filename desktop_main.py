"""Desktop launcher for Card Optimiser (Flask + native webview)."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import socket
import sys
import threading
import time
import webbrowser

import requests


APP_TITLE = "Card Optimiser"
APP_DATA_FOLDER = "card-optimiser"
LOCAL_HOST = "127.0.0.1"


def _resource_root() -> Path:
    """Return packaged resource directory (or repo root in dev)."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _user_data_dir() -> Path:
    """Return user-writable directory for config/results/cache files."""
    home = Path.home()
    if sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    elif sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else (home / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    data_dir = base / APP_DATA_FOLDER
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _copy_if_missing(source: Path, target: Path) -> None:
    if source.exists() and not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _bootstrap_user_data(data_dir: Path) -> None:
    """Seed writable config/cache from packaged defaults when missing."""
    root = _resource_root()
    _copy_if_missing(root / "config.yaml", data_dir / "config.yaml")
    _copy_if_missing(
        root / "data" / "scryfall_card_names.json",
        data_dir / "data" / "scryfall_card_names.json",
    )


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((LOCAL_HOST, 0))
        return int(sock.getsockname()[1])


def _run_server(port: int) -> None:
    from app import app as flask_app

    flask_app.run(
        host=LOCAL_HOST,
        port=port,
        debug=False,
        use_reloader=False,
        threaded=True,
    )


def _wait_for_server(url: str, timeout_sec: float = 30.0) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=1.5)
            if resp.status_code < 500:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.2)
    return False


def main() -> None:
    data_dir = _user_data_dir()
    _bootstrap_user_data(data_dir)
    os.environ.setdefault("CARD_OPTIMISER_DATA_DIR", str(data_dir))

    port = _find_free_port()
    url = f"http://{LOCAL_HOST}:{port}"

    server_thread = threading.Thread(target=_run_server, args=(port,), daemon=True)
    server_thread.start()

    if not _wait_for_server(url):
        raise RuntimeError("Failed to start local web server for Card Optimiser")

    try:
        import webview
    except ImportError:
        webbrowser.open(url)
        server_thread.join()
        return

    webview.create_window(APP_TITLE, url, width=1400, height=950, min_size=(1100, 740))
    webview.start()


if __name__ == "__main__":
    main()
