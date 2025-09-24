import os, sys, subprocess, webbrowser
from src.common_utils.resource_path import get_resource_path

from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw

processes = {}

BACKEND = "backend"
DASHBOARD = "dashboard"

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
MAIN_EXE = os.path.join(BASE_DIR, "main.exe")
DASH_EXE = os.path.join(BASE_DIR, "dashboard.exe")


def start_backend():
    if BACKEND not in processes:
        processes[BACKEND] = subprocess.Popen([MAIN_EXE])
        _update_icon()

def stop_backend():
    proc = processes.pop(BACKEND, None)
    if proc:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)])
    _update_icon()
    

def start_dashboard():
    if DASHBOARD not in processes:
        processes[DASHBOARD] = subprocess.Popen([DASH_EXE])
    _update_icon()
    webbrowser.open("http://127.0.0.1:5000")

def stop_all(icon=None, item=None):
    for proc in list(processes.values()):
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)])
    processes.clear()
    _update_icon()
    if icon: icon.stop()

def _update_icon():
    backend_running = "backend" in processes and processes["backend"].poll() is None
    dash_running = "dashboard" in processes and processes["dashboard"].poll() is None
    icon.icon = _create_image(backend_running, dash_running)
    
def _create_image(backend_running=False, dash_running=False):
    image_path = get_resource_path("./frontend/static/logo.jpg")
    base = Image.open(image_path).resize((64, 64), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(base)
    # backend green dot (bottom-right)
    if backend_running:
        draw.ellipse((42, 42, 62, 62), fill=(0, 255, 0))
    # dashboard white dot (bottom-left)
    if dash_running:
        draw.ellipse((2, 42, 22, 62), fill=(255, 255, 255))
    return base

menu = Menu(
    MenuItem("Start backend", lambda _: start_backend()),
    MenuItem("Stop backend", lambda _: stop_backend()),
    MenuItem("Start dashboard", lambda _: start_dashboard()),
    MenuItem("Quit", stop_all)
)

icon = Icon("ShahinApp", _create_image(), "ShahinApp", menu)
icon.run()