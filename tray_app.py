import argparse
import os
import signal
import subprocess
import sys
import webbrowser
from pathlib import Path

from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw

from src.common_utils.resource_path import get_resource_path

BACKEND = "backend"
DASHBOARD = "dashboard"
DEFAULT_DASHBOARD_URL = "http://127.0.0.1:5000"

IS_WINDOWS = os.name == "nt"
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

processes = {}
icon = None
tray_config = {
    "host": "127.0.0.1",
    "port": 5000,
    "debug": False,
    "url": DEFAULT_DASHBOARD_URL,
}


def build_command(mode, extra_args=None):
    extra_args = extra_args or []
    if getattr(sys, "frozen", False):
        return [sys.executable, "--mode", mode, *extra_args]

    script_path = Path(__file__).resolve()
    return [sys.executable, str(script_path), "--mode", mode, *extra_args]


def _spawn_process(mode, extra_args=None):
    kwargs = {}
    if IS_WINDOWS and CREATE_NEW_PROCESS_GROUP:
        kwargs["creationflags"] = CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(build_command(mode, extra_args), **kwargs)


def start_backend():
    if BACKEND in processes and processes[BACKEND].poll() is None:
        return
    processes[BACKEND] = _spawn_process(BACKEND)
    _update_icon()


def stop_backend():
    _stop_process(BACKEND)


def start_dashboard(open_browser=True, url=None):
    if DASHBOARD in processes and processes[DASHBOARD].poll() is None:
        if open_browser:
            webbrowser.open(url or tray_config["url"])
        return
    args = ["--host", tray_config["host"], "--port", str(tray_config["port"])]
    if tray_config["debug"]:
        args.append("--debug")
    processes[DASHBOARD] = _spawn_process(DASHBOARD, args)
    _update_icon()
    if open_browser:
        webbrowser.open(url or tray_config["url"])


def stop_dashboard():
    _stop_process(DASHBOARD)


def stop_all(icon_obj=None, item=None):
    stop_dashboard()
    stop_backend()
    if icon_obj:
        icon_obj.stop()


def _stop_process(name):
    proc = processes.pop(name, None)
    if not proc:
        _update_icon()
        return

    if proc.poll() is not None:
        _update_icon()
        return

    try:
        if IS_WINDOWS and CREATE_NEW_PROCESS_GROUP:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    finally:
        _update_icon()


def _update_icon():
    if icon is None:
        return
    backend_running = BACKEND in processes and processes[BACKEND].poll() is None
    dash_running = DASHBOARD in processes and processes[DASHBOARD].poll() is None
    icon.icon = _create_image(backend_running, dash_running)


def _create_image(backend_running=False, dash_running=False):
    image_path = get_resource_path("./frontend/static/logo.jpg")
    base = Image.open(image_path).resize((64, 64), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(base)
    if backend_running:
        draw.ellipse((42, 42, 62, 62), fill=(0, 255, 0))
    if dash_running:
        draw.ellipse((2, 42, 22, 62), fill=(255, 255, 255))
    return base


def parse_args():
    parser = argparse.ArgumentParser(description="Shahin tray controller")
    parser.add_argument(
        "--mode", choices=["tray", "backend", "dashboard"], default="tray"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--no-autostart", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--dashboard-url")
    return parser.parse_args()


def tray_main(args):
    global icon
    global tray_config
    tray_config = {
        "host": args.host,
        "port": args.port,
        "debug": args.debug,
        "url": args.dashboard_url or f"http://{args.host}:{args.port}",
    }
    menu = Menu(
        MenuItem("Start backend", lambda _: start_backend()),
        MenuItem("Stop backend", lambda _: stop_backend()),
        MenuItem("Start dashboard", lambda _: start_dashboard()),
        MenuItem("Stop dashboard", lambda _: stop_dashboard()),
        MenuItem("Quit", stop_all),
    )

    icon = Icon("ShahinApp", _create_image(), "Shahin", menu)

    if not args.no_autostart:
        start_backend()
        start_dashboard(open_browser=not args.no_browser, url=tray_config["url"])

    icon.run()


def backend_main():
    from main import main as run_backend

    run_backend()


def dashboard_main(host, port, debug):
    from frontend.app import run_dashboard

    run_dashboard(host=host, port=port, debug=debug)


def main():
    args = parse_args()

    if args.mode == "backend":
        backend_main()
    elif args.mode == "dashboard":
        dashboard_main(args.host, args.port, args.debug)
    else:
        tray_main(args)


if __name__ == "__main__":
    main()
