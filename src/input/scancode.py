'''
Hardware scancode keyboard injection for Windows.

pyautogui presses keys by virtual key code. Plenty of game clients read the
keyboard through DirectInput or raw input instead, and those only ever see
hardware scancodes, so a virtual key press reaches them as nothing at all -
SendInput still succeeds, no error is raised, and the character simply does not
move. Sending the scancode is what a real keyboard does, so it works for both
kinds of client.

send_key() returns False when the key name has no scancode here, which lets the
caller fall back to pyautogui rather than silently dropping the press.
'''
import ctypes
from ctypes import wintypes

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

# Scancode set 1. Keys marked extended are sent with an E0 prefix, which is how
# the keyboard distinguishes e.g. the arrow keys from the numeric keypad.
SCANCODE = {
    "escape": 0x01, "esc": 0x01,
    "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06,
    "6": 0x07, "7": 0x08, "8": 0x09, "9": 0x0A, "0": 0x0B,
    "-": 0x0C, "=": 0x0D, "backspace": 0x0E, "tab": 0x0F,
    "q": 0x10, "w": 0x11, "e": 0x12, "r": 0x13, "t": 0x14,
    "y": 0x15, "u": 0x16, "i": 0x17, "o": 0x18, "p": 0x19,
    "[": 0x1A, "]": 0x1B, "enter": 0x1C, "return": 0x1C,
    "ctrl": 0x1D, "ctrlleft": 0x1D,
    "a": 0x1E, "s": 0x1F, "d": 0x20, "f": 0x21, "g": 0x22,
    "h": 0x23, "j": 0x24, "k": 0x25, "l": 0x26, ";": 0x27, "'": 0x28, "`": 0x29,
    "shift": 0x2A, "shiftleft": 0x2A, "\\": 0x2B,
    "z": 0x2C, "x": 0x2D, "c": 0x2E, "v": 0x2F, "b": 0x30,
    "n": 0x31, "m": 0x32, ",": 0x33, ".": 0x34, "/": 0x35,
    "shiftright": 0x36, "alt": 0x38, "altleft": 0x38, "space": 0x39,
    "capslock": 0x3A,
    "f1": 0x3B, "f2": 0x3C, "f3": 0x3D, "f4": 0x3E, "f5": 0x3F,
    "f6": 0x40, "f7": 0x41, "f8": 0x42, "f9": 0x43, "f10": 0x44,
    "f11": 0x57, "f12": 0x58,
}

EXTENDED = {
    "home": 0x47, "up": 0x48, "pageup": 0x49, "left": 0x4B,
    "right": 0x4D, "end": 0x4F, "down": 0x50, "pagedown": 0x51,
    "insert": 0x52, "delete": 0x53, "del": 0x53,
    "ctrlright": 0x1D, "altright": 0x38,
}


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


def lookup(key):
    '''
    Return (scancode, is_extended) for a key name, or None when unknown.
    '''
    if not key:
        return None
    name = str(key).strip().lower()
    if name in EXTENDED:
        return EXTENDED[name], True
    if name in SCANCODE:
        return SCANCODE[name], False
    return None


def send_key(key, is_press):
    '''
    Send one key down or key up as a hardware scancode.

    Returns True when the event was sent, False when the key name is unknown
    or the injection was rejected, so the caller can fall back.
    '''
    found = lookup(key)
    if found is None:
        return False
    scan, extended = found

    flags = KEYEVENTF_SCANCODE
    if extended:
        flags |= KEYEVENTF_EXTENDEDKEY
    if not is_press:
        flags |= KEYEVENTF_KEYUP

    event = _INPUT(type=INPUT_KEYBOARD,
                   union=_INPUTUNION(ki=_KEYBDINPUT(wVk=0,
                                                    wScan=scan,
                                                    dwFlags=flags,
                                                    time=0,
                                                    dwExtraInfo=None)))
    sent = ctypes.windll.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(_INPUT))
    return sent == 1
