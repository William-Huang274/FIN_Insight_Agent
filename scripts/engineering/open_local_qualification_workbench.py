"""Pair the current Windows account's local qualification viewer or open it in the default browser."""

import argparse
import json
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


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
    window = tk.Tk()
    window.title("FinSight 研究工作台")
    window.attributes("-topmost", True)
    window.resizable(False, False)
    window.geometry(
        "430x115+%d+%d"
        % (
            max(0, (window.winfo_screenwidth() - 430) // 2),
            max(0, (window.winfo_screenheight() - 115) // 2),
        )
    )
    status = tk.Label(window, text="正在连接本机研究工作台…", padx=12, pady=12)
    status.pack()
    window.update()
    origin = f"http://127.0.0.1:{args.port}"
    report_url = origin + args.page

    def copy_url():
        window.clipboard_clear()
        window.clipboard_append(report_url)
        status.config(text="报告地址已复制，可以粘贴到浏览器地址栏。")

    try:
        from tests.integration.fixtures.local_workbench_access import DeviceStore

        store = DeviceStore(args.db)
        if args.approve_browser:
            status.config(text="浏览器登录页显示配对码时，在这里输入。")
            window.update()
            code = simpledialog.askstring(
                "FinSight 本机授权", "输入浏览器登录页显示的配对码：", parent=window
            )
            if code:
                ok = store.approve(code.strip().lower())
                messagebox.showinfo(
                    "FinSight",
                    "浏览器已授权，返回原页面即可。" if ok else "配对码无效或已过期。",
                    parent=window,
                )
            return

        # A system HTTP proxy must not intercept a loopback readiness check.
        opener = build_opener(ProxyHandler({}))

        def ready():
            with opener.open(origin + "/auth/status", timeout=2) as response:
                if json.load(response).get("browser_login") is not True:
                    raise RuntimeError("本机工作台尚未启用浏览器登录。")

        try:
            ready()
        except URLError:
            if not args.service_launcher:
                raise
            status.config(text="正在启动本机工作台服务…")
            window.update()
            subprocess.run(
                [sys.executable, str(args.service_launcher)],
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            for _ in range(40):
                try:
                    ready()
                    break
                except URLError:
                    window.update()
                    time.sleep(0.5)
            else:
                raise RuntimeError("本机工作台服务未能启动。")
        identifier, secret = store.pair(approved=True)
        login_url = (
            origin
            + "/auth/login?"
            + urlencode({"next": args.page})
            + "#"
            + identifier
            + "."
            + secret
        )
        window.attributes("-topmost", False)
        if not webbrowser.open(login_url):
            raise RuntimeError("Windows 未能打开默认浏览器。")
        status.config(text="已请求默认浏览器打开 FinSight。")
        tk.Button(window, text="复制报告地址", command=copy_url).pack()
        window.after(4500, window.destroy)
        window.mainloop()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        status.config(text="工作台未能打开。")
        messagebox.showerror("FinSight 研究工作台", str(exc), parent=window)
    finally:
        try:
            window.destroy()
        except tk.TclError:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # pythonw has no console. Even a missing GUI/runtime dependency must be visible.
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            0,
            f"启动失败（{type(exc).__name__}）。请检查本机 FinSight 安装。",
            "FinSight",
            0x40010,
        )
        raise SystemExit(1) from None
