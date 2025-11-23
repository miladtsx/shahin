import os
import shutil
import signal
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path
import threading
from typing import Any, Dict, Mapping, Optional

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


def _normalize_args(raw: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "mode": "tray",
        "host": "127.0.0.1",
        "port": 5000,
        "debug": False,
        "no_autostart": False,
        "no_browser": False,
        "dashboard_url": None,
    }
    if raw is None:
        return base
    if not isinstance(raw, Mapping):
        raise TypeError("tray arguments must be provided as a mapping")
    for key, value in raw.items():
        base[key] = value
    base["mode"] = str(base.get("mode", "tray")).lower()
    base["host"] = str(base.get("host", "127.0.0.1"))
    base["port"] = int(base.get("port", 5000))
    base["debug"] = bool(base.get("debug", False))
    base["no_autostart"] = bool(base.get("no_autostart", False))
    base["no_browser"] = bool(base.get("no_browser", False))
    dashboard_url = base.get("dashboard_url")
    base["dashboard_url"] = str(dashboard_url) if dashboard_url else None
    return base


def build_command(mode, extra_args=None):
    extra_args = extra_args or []
    launcher = os.environ.get("WIN_ENTRY")
    if launcher:
        return [launcher, "--mode", mode, *extra_args]
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
    status = license_utils.license_status()
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
    _clear_model_cache()
    if icon_obj:
        icon_obj.stop()


def _clear_model_cache():
    root = os.environ.get("WIN_MDL") or str(
        Path(tempfile.gettempdir()) / "win_mlds_shared"
    )
    cache_path = Path(root)
    try:
        if cache_path.exists():
            shutil.rmtree(cache_path, ignore_errors=False)
    except Exception as exc:
        pass


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


def _open_activation_dialog(reason=None):
    def _launch():
        acquired = _activation_window_open.acquire(blocking=False)
        if not acquired:
            return
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.title("فعال‌سازی شاهین")
            root.resizable(False, False)
            fingerprint = ""
            try:
                fingerprint = license_utils.get_machine_fingerprint()
            except Exception as exc:  # pragma: no cover - UI helper
                fingerprint = f"<error: {exc}>"

            tk.Label(root, text="اثر انگشت دستگاه شما:").grid(
                row=0, column=0, sticky="w", padx=10, pady=(10, 0)
            )

            fp_value = tk.Entry(root, width=60)
            fp_value.insert(0, fingerprint)
            fp_value.configure(state="readonly")
            fp_value.grid(row=1, column=0, columnspan=2, padx=10, pady=5)

            def copy_fp():
                root.clipboard_clear()
                root.clipboard_append(fingerprint)
                messagebox.showinfo("کپی شد", "اثر انگشت کپی شد")

            copy_btn = tk.Button(root, text="کپی اثر انگشت", command=copy_fp)
            copy_btn.grid(row=1, column=2, padx=5, pady=5)

            tk.Label(root, text="کلید اهراز هویت را در زیر وارد نمایید").grid(
                row=2, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 0)
            )

            license_input = tk.Text(root, height=5, width=60, wrap="word")
            license_input.grid(row=3, column=0, columnspan=3, padx=10, pady=5)

            if reason:
                tk.Label(root, text=f"آخرین خطا: {reason}", fg="red", anchor="w").grid(
                    row=4, column=0, columnspan=3, sticky="w", padx=10
                )

            def on_validate():
                blob = license_input.get("1.0", "end").strip()
                if not blob:
                    messagebox.showwarning(
                        "ورودی ناموجود", "لطفاً کلید اهراز هویت را وارد نمایید"
                    )
                    return
                status = license_utils.activate_license(blob)
                if status.valid:
                    messagebox.showinfo(
                        "فعال‌سازی موفق", "فرایند اهراز هویت با موفقیت انجام شد"
                    )
                    try:
                        logger.info(
                            "License activated; auto-starting backend and dashboard"
                        )
                        start_dashboard()
                        start_backend()
                    except Exception as exc:
                        logger.exception(
                            "autostart_failed_after_activation",
                            extra={"error": str(exc)},
                        )
                    root.destroy()
                else:
                    messagebox.showerror(
                        "فعال‌سازی ناموفق",
                        f"کلید نامعتبر ({status.reason}). لطفاً بررسی کرده و دوباره تلاش کنید",
                    )

            action_btn = tk.Button(root, text="تأیید", command=on_validate)
            action_btn.grid(row=5, column=0, padx=10, pady=(5, 10), sticky="w")

            tk.Button(root, text="بستن", command=root.destroy).grid(
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


def tray_main(args: Mapping[str, Any]):
    global icon
    global tray_config
    tray_config = {
        "host": args["host"],
        "port": args["port"],
        "debug": args["debug"],
        "url": args["dashboard_url"] or f"http://{args['host']}:{args['port']}",
    }
    logger.info(
        "Launching tray mode",
        extra={
            "host": tray_config["host"],
            "port": tray_config["port"],
            "debug": tray_config["debug"],
            "no_autostart": args["no_autostart"],
        },
    )
    service_controls = MenuItem(
        "شاهین",
        Menu(
            MenuItem("شروع", lambda _: start_backend()),
            MenuItem("توقف", lambda _: stop_backend()),
        ),
    )
    dashboard_controls = MenuItem(
        "مدیریت",
        Menu(
            MenuItem("شروع", lambda _: start_dashboard()),
            MenuItem("توقف", lambda _: stop_dashboard()),
        ),
    )
    menu = Menu(
        service_controls,
        dashboard_controls,
        MenuItem("فعال‌سازی", lambda _: _open_activation_dialog()),
        MenuItem("خروج", stop_all),
    )

    icon = Icon("ShahinApp", _create_image(), "شاهین", menu)

    if not args["no_autostart"]:
        if license_utils.license_is_valid():
            start_backend()
            start_dashboard(open_browser=not args["no_browser"], url=tray_config["url"])
        else:
            logger.warning("Skipping autostart: license missing or invalid")
            _open_activation_dialog()

    icon.run()


def backend_main(_args: Mapping[str, Any]):
    try:
        from main import main as run_backend
    except Exception as exc:  # pragma: no cover - backend import should succeed
        logger.exception(
            "backend_entry_import_failed",
            extra={"error": str(exc)},
        )
        sys.exit(4)
    logger.info("Launching backend mode")
    run_backend()


def dashboard_main(args: Mapping[str, Any]):
    from frontend.app import run_dashboard

    status = license_utils.license_status()
    if not status.valid:
        logger.error(
            "Dashboard blocked: license invalid",
            extra={"reason": status.reason},
        )
        sys.exit(3)
    logger.info(
        "Launching dashboard mode",
        extra={
            "host": args["host"],
            "port": args["port"],
            "debug": args["debug"],
        },
    )
    run_dashboard(
        host=args["host"],
        port=args["port"],
        debug=args["debug"],
    )


def main(args: Optional[Mapping[str, Any]] = None):
    params = _normalize_args(args)
    mode = params["mode"]
    logger.info("Entry dispatch", extra={"mode": mode})

    if mode == "backend":
        backend_main(params)
    elif mode == "dashboard":
        dashboard_main(params)
    else:
        tray_main(params)
