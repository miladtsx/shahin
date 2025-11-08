import argparse
import os
import signal
import subprocess
import sys
import webbrowser
from pathlib import Path
import threading

from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw

from src.common_utils.app_logger import get_logger
from src.common_utils.resource_path import get_resource_path
from src.common_utils import license_utils

BACKEND = "backend"
DASHBOARD = "dashboard"
DEFAULT_DASHBOARD_URL = "http://127.0.0.1:5000"

IS_WINDOWS = os.name == "nt"
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

processes = {}
icon = None
_activation_window_open = threading.Lock()
tray_config = {
    "host": "127.0.0.1",
    "port": 5000,
    "debug": False,
    "url": DEFAULT_DASHBOARD_URL,
}

logger = get_logger("tray.app")


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
    proc = subprocess.Popen(build_command(mode, extra_args), **kwargs)
    threading.Thread(
        target=_watch_process_exit,
        args=(mode, proc),
        name=f"{mode}-exit-watcher",
        daemon=True,
    ).start()
    return proc


def _license_allows(component):
    status = license_utils.license_status(force_reload=True)
    if status.valid:
        return True
    logger.warning(
        "License missing or invalid",
        extra={"component": component, "reason": status.reason},
    )
    _open_activation_dialog(status.reason)
    return False


def start_backend():
    if BACKEND in processes and processes[BACKEND].poll() is None:
        logger.info("Backend already running", extra={"component": BACKEND})
        return
    if not _license_allows(BACKEND):
        return
    logger.info("Starting backend process", extra={"component": BACKEND})
    processes[BACKEND] = _spawn_process(BACKEND)
    _update_icon()


def stop_backend():
    logger.info("Stopping backend process", extra={"component": BACKEND})
    _stop_process(BACKEND)


def start_dashboard(open_browser=True, url=None):
    if DASHBOARD in processes and processes[DASHBOARD].poll() is None:
        if open_browser:
            webbrowser.open(url or tray_config["url"])
        return
    if not _license_allows(DASHBOARD):
        return
    args = ["--host", tray_config["host"], "--port", str(tray_config["port"])]
    if tray_config["debug"]:
        args.append("--debug")
    logger.info(
        "Starting dashboard process",
        extra={
            "component": DASHBOARD,
            "host": tray_config["host"],
            "port": tray_config["port"],
        },
    )
    processes[DASHBOARD] = _spawn_process(DASHBOARD, args)
    _update_icon()
    if open_browser:
        webbrowser.open(url or tray_config["url"])


def stop_dashboard():
    logger.info("Stopping dashboard process", extra={"component": DASHBOARD})
    _stop_process(DASHBOARD)


def stop_all(icon_obj=None, item=None):
    logger.info("Stopping all components")
    stop_dashboard()
    stop_backend()
    if icon_obj:
        icon_obj.stop()


def _stop_process(name):
    proc = processes.pop(name, None)
    if not proc:
        logger.info("No process to stop", extra={"component": name})
        _update_icon()
        return

    if proc.poll() is not None:
        logger.info(
            "Process already exited",
            extra={"component": name, "returncode": proc.returncode},
        )
        _update_icon()
        return

    try:
        if IS_WINDOWS and CREATE_NEW_PROCESS_GROUP:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except (ProcessLookupError, OSError):
                pass
    except (ProcessLookupError, OSError):
        # Process may already have exited between poll and terminate; that's OK.
        pass
    finally:
        logger.info("Process stopped", extra={"component": name})
        _update_icon()


def _watch_process_exit(name, proc):
    try:
        returncode = proc.wait()
    except Exception as exc:
        logger.exception(
            "Process watcher failed", extra={"component": name, "error": str(exc)}
        )
        return
    logger.info(
        "Process exited",
        extra={"component": name, "returncode": returncode},
    )
    if processes.get(name) is proc:
        processes.pop(name, None)
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


def _open_activation_dialog(reason=None):
    def _launch():
        acquired = _activation_window_open.acquire(blocking=False)
        if not acquired:
            return
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.title("Shahin Activation")
            root.resizable(False, False)
            fingerprint = ""
            try:
                fingerprint = license_utils.get_machine_fingerprint()
            except Exception as exc:  # pragma: no cover - UI helper
                fingerprint = f"<error: {exc}>"

            tk.Label(root, text="Machine fingerprint:").grid(
                row=0, column=0, sticky="w", padx=10, pady=(10, 0)
            )

            fp_value = tk.Entry(root, width=60)
            fp_value.insert(0, fingerprint)
            fp_value.configure(state="readonly")
            fp_value.grid(row=1, column=0, columnspan=2, padx=10, pady=5)

            def copy_fp():
                root.clipboard_clear()
                root.clipboard_append(fingerprint)
                messagebox.showinfo("Copied", "Fingerprint copied to clipboard.")

            copy_btn = tk.Button(root, text="Copy fingerprint", command=copy_fp)
            copy_btn.grid(row=1, column=2, padx=5, pady=5)

            tk.Label(root, text="Paste the signed license key below:").grid(
                row=2, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 0)
            )

            license_input = tk.Text(root, height=5, width=60, wrap="word")
            license_input.grid(row=3, column=0, columnspan=3, padx=10, pady=5)

            if reason:
                tk.Label(
                    root, text=f"Last error: {reason}", fg="red", anchor="w"
                ).grid(row=4, column=0, columnspan=3, sticky="w", padx=10)

            def on_validate():
                blob = license_input.get("1.0", "end").strip()
                if not blob:
                    messagebox.showwarning("Missing input", "Please paste the license key.")
                    return
                status = license_utils.activate_license(blob)
                if status.valid:
                    messagebox.showinfo("Activation successful", "License stored successfully.")
                    root.destroy()
                else:
                    messagebox.showerror(
                        "Activation failed",
                        f"License rejected ({status.reason}). Please verify and try again.",
                    )

            action_btn = tk.Button(root, text="Validate", command=on_validate)
            action_btn.grid(row=5, column=0, padx=10, pady=(5, 10), sticky="w")

            tk.Button(root, text="Close", command=root.destroy).grid(
                row=5, column=2, padx=10, pady=(5, 10), sticky="e"
            )

            root.mainloop()
        except Exception as exc:  # pragma: no cover - UI helper
            logger.exception(
                "activation_dialog_failed",
                extra={"error": str(exc)},
            )
        finally:
            _activation_window_open.release()

    threading.Thread(target=_launch, name="activation-dialog", daemon=True).start()


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
        MenuItem("Activate…", lambda _: _open_activation_dialog()),
        MenuItem("Quit", stop_all),
    )

    icon = Icon("ShahinApp", _create_image(), "Shahin", menu)

    if not args.no_autostart:
        if license_utils.license_is_valid():
            start_backend()
            start_dashboard(open_browser=not args.no_browser, url=tray_config["url"])
        else:
            logger.warning("Skipping autostart: license missing or invalid")

    icon.run()


def backend_main():
    from main import main as run_backend

    run_backend()


def dashboard_main(host, port, debug):
    from frontend.app import run_dashboard

    status = license_utils.license_status(force_reload=True)
    if not status.valid:
        logger.error(
            "Dashboard blocked: license invalid",
            extra={"reason": status.reason},
        )
        sys.exit(3)
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
