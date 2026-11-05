"""Pair the current Windows account's local qualification viewer or open it in the default browser."""

import argparse
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.integration.fixtures.local_workbench_access import DeviceStore


def main():
    import tkinter as tk
    from tkinter import messagebox, simpledialog

    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--page", default="/workspace/projects")
    parser.add_argument("--service-launcher", type=Path)
    parser.add_argument("--approve-browser", action="store_true")
    args = parser.parse_args()
    if os.name != "nt" or not args.page.startswith("/workspace"):
        parser.error("local Windows workspace required")
    store = DeviceStore(args.db)
    if args.approve_browser:
        window = tk.Tk()
        window.withdraw()
        code = simpledialog.askstring(
            "FinSight 本机授权", "输入当前浏览器登录页显示的配对码：", parent=window
        )
        if code:
            ok = store.approve(code.strip().lower())
            messagebox.showinfo(
                "FinSight",
                "浏览器已授权，返回原页面即可。" if ok else "配对码无效或已过期。",
                parent=window,
            )
        window.destroy()
        return
    origin = f"http://127.0.0.1:{args.port}"
    try:
        with urlopen(origin + "/auth/status", timeout=2):
            pass
    except URLError:
        if not args.service_launcher:
            raise
        subprocess.run(
            [sys.executable, str(args.service_launcher)],
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for _ in range(40):
            try:
                with urlopen(origin + "/auth/status", timeout=1):
                    break
            except URLError:
                time.sleep(0.5)
        else:
            messagebox.showerror("FinSight", "本机工作台服务没有启动。")
            return
    identifier, secret = store.pair(approved=True)
    webbrowser.open(
        origin
        + "/auth/login?"
        + urlencode({"next": args.page})
        + "#"
        + identifier
        + "."
        + secret
    )


if __name__ == "__main__":
    main()
