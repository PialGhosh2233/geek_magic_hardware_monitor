"""Receive Windows shutdown / logoff / sleep notifications in a background thread.

Creates a hidden top-level window (message-only windows do not get these broadcasts)
and runs a message loop. Callbacks run on that thread; keep them quick (< 3 s).
"""
import ctypes
import threading
from ctypes import wintypes as w

WM_DESTROY = 0x0002
WM_QUERYENDSESSION = 0x0011
WM_ENDSESSION = 0x0016
WM_POWERBROADCAST = 0x0218
PBT_APMSUSPEND = 0x0004
PBT_APMRESUMESUSPEND = 0x0007
PBT_APMRESUMEAUTOMATIC = 0x0012

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, w.HWND, ctypes.c_uint, w.WPARAM, w.LPARAM)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [w.HWND, ctypes.c_uint, w.WPARAM, w.LPARAM]
user32.CreateWindowExW.restype = w.HWND
user32.ShutdownBlockReasonCreate.argtypes = [w.HWND, w.LPCWSTR]
user32.ShutdownBlockReasonDestroy.argtypes = [w.HWND]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", ctypes.c_uint), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int), ("hInstance", w.HINSTANCE), ("hIcon", w.HICON),
        ("hCursor", w.HANDLE), ("hbrBackground", w.HBRUSH), ("lpszMenuName", w.LPCWSTR),
        ("lpszClassName", w.LPCWSTR),
    ]


WINDOW_TITLE = "GeekMagicMonitorHiddenWindow"


def start(on_end_session, on_suspend, on_resume, log=None):
    """Start the hidden window thread. Returns the (daemon) thread."""
    done = {"end": False}

    def fire(cb, why):
        try:
            if log:
                log.info("windows event: %s", why)
            cb()
        except Exception as e:  # never let a callback kill the message loop
            if log:
                log.error("session hook %s failed: %s", why, e)

    def wndproc(hwnd, msg, wparam, lparam):
        if msg == WM_QUERYENDSESSION:
            user32.ShutdownBlockReasonCreate(hwnd, "Switching GeekMagic display to clock")
            if not done["end"]:
                done["end"] = True
                fire(on_end_session, "shutdown/logoff (query)")
            user32.ShutdownBlockReasonDestroy(hwnd)
            return 1  # TRUE: fine to end the session
        if msg == WM_ENDSESSION:
            if wparam and not done["end"]:
                done["end"] = True
                fire(on_end_session, "shutdown/logoff")
            return 0
        if msg == WM_POWERBROADCAST:
            if wparam == PBT_APMSUSPEND:
                fire(on_suspend, "sleep")
            elif wparam in (PBT_APMRESUMEAUTOMATIC, PBT_APMRESUMESUSPEND):
                done["end"] = False
                fire(on_resume, "resume")
            return 1
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    proc = WNDPROC(wndproc)

    def run():
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.lpfnWndProc = proc
        wc.hInstance = hinst
        wc.lpszClassName = "GeekMagicMonitorClass"
        if not user32.RegisterClassW(ctypes.byref(wc)):
            if log:
                log.error("RegisterClassW failed: %s", ctypes.GetLastError())
            return
        hwnd = user32.CreateWindowExW(0, wc.lpszClassName, WINDOW_TITLE, 0, 0, 0, 0, 0, None, None, hinst, None)
        if not hwnd:
            if log:
                log.error("CreateWindowExW failed: %s", ctypes.GetLastError())
            return
        msg = w.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    t = threading.Thread(target=run, name="session-hooks", daemon=True)
    t._proc_ref = proc  # keep the ctypes callback alive for the life of the thread
    t.start()
    return t
