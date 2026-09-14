"""Diagnose why the bot's key presses do not move the character.

Run it from the SAME terminal you start the bot from:

    python tools/input_check.py

It reports three things in order, and stops at the first one that fails:

1. Elevation. Windows silently drops synthetic input sent from a process at a
   lower integrity level than the target window (UIPI). If the game runs
   elevated and this process does not, every keystroke the bot sends is
   discarded with no error at all.
2. The foreground window check KeyBoardController.run() does before it sends
   anything.
3. A real key press, exactly the way the bot sends it.
"""
import ctypes
import sys
import time

sys.path.insert(0, ".")

import pyautogui
import pygetwindow as gw
import win32gui
import win32process

from src.utils.common import load_yaml, override_cfg

pyautogui.PAUSE = 0

TOKEN_QUERY = 0x0008
TOKEN_ELEVATION = 20
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def is_elevated(pid=None):
    """True / False, or None when the token cannot be read."""
    k32, a32 = ctypes.windll.kernel32, ctypes.windll.advapi32
    if pid is None:
        handle = k32.GetCurrentProcess()
        opened = False
    else:
        handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        opened = True
        if not handle:
            return None
    try:
        token = ctypes.c_void_p()
        if not a32.OpenProcessToken(ctypes.c_void_p(handle), TOKEN_QUERY,
                                    ctypes.byref(token)):
            return None
        try:
            elevated, size = ctypes.c_uint(), ctypes.c_uint()
            ok = a32.GetTokenInformation(token, TOKEN_ELEVATION,
                                         ctypes.byref(elevated), 4,
                                         ctypes.byref(size))
            return bool(elevated.value) if ok else None
        finally:
            k32.CloseHandle(token)
    finally:
        if opened:
            k32.CloseHandle(ctypes.c_void_p(handle))


cfg = override_cfg(load_yaml("config/config_default.yaml"),
                   load_yaml("config/config_custom.yaml"))
want = cfg["game_window"]["title"]
print(f"\nconfig game_window.title = {want!r}")

# ---- 1. elevation ---------------------------------------------------------
me = is_elevated()
hwnd = win32gui.FindWindow(None, want)
if not hwnd:
    print(f"\nCannot find a window titled {want!r}. Start the game first.")
    sys.exit(1)
_, game_pid = win32process.GetWindowThreadProcessId(hwnd)
game = is_elevated(game_pid)

label = {True: "ELEVATED", False: "not elevated", None: "unknown"}
print(f"\n1. elevation")
print(f"     this process        : {label[me]}")
print(f"     game (pid {game_pid:<6}): {label[game]}")

if game and not me:
    print("\n   FAIL. The game runs elevated and this process does not, so Windows")
    print("   discards every synthetic keystroke sent to it, silently. This is why")
    print("   the character never moves even though the bot computes the right")
    print("   commands. Start the terminal with 'Run as administrator' and run the")
    print("   bot from there.")
    sys.exit(1)
print("     -> ok, input is not blocked by integrity level")

# ---- 2. foreground window -------------------------------------------------
print(f"\n2. foreground window - click the GAME window now")
for i in range(5, 0, -1):
    print(f"     {i} ...")
    time.sleep(1)

hits = 0
for i in range(10):
    try:
        w = gw.getActiveWindow()
        title = w.title if w else None
    except Exception as exc:
        title = f"<{type(exc).__name__}: {exc}>"
    ok = bool(title and want in title)
    hits += ok
    print(f"     {i / 2:.1f}s  active={ok}  foreground={title!r}")
    time.sleep(0.5)

if hits == 0:
    print("\n   FAIL. KeyBoardController skips its whole loop while the game is not")
    print("   the foreground window, so no key is ever sent. Keep the game focused.")
    sys.exit(1)
print(f"     -> ok, game was in front for {hits}/10 samples")

# ---- 3. real key press, both injection methods ----------------------------
from src.input import scancode

print("\n3. pressing keys for real. Watch the character, not this window.")

print("\n   (a) virtual key code, what pyautogui sends - RIGHT for 2s ...")
pyautogui.keyDown("right")
time.sleep(2)
pyautogui.keyUp("right")
print("       done. Pausing 2s so you can tell the two apart.")
time.sleep(2)

print("\n   (b) hardware scancode, what a real keyboard sends - LEFT for 2s ...")
ok_down = scancode.send_key("left", True)
time.sleep(2)
scancode.send_key("left", False)
print(f"       done (SendInput accepted: {ok_down}).")

print("\n   Which one moved the character?")
print("     (a) only  -> keep pyautogui, nothing to change")
print("     (b) only  -> the client needs scancodes; KeyBoardController now sends")
print("                  those first, so the bot will work as is")
print("     both      -> either works")
print("     neither   -> input is still blocked by something else; report back")
