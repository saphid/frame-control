"""Disposable X11 event recorder used for the PR #66 focused-input observation."""
import ctypes as C
import json
import os
import select
import signal
import time

X = C.CDLL('libX11.so.6')
P, U = C.c_void_p, C.c_ulong
for name, restype, args in [
    ('XOpenDisplay', P, [C.c_char_p]), ('XDefaultRootWindow', U, [P]),
    ('XCreateSimpleWindow', U, [P, U, C.c_int, C.c_int, C.c_uint, C.c_uint, C.c_uint, U, U]),
    ('XInternAtom', U, [P, C.c_char_p, C.c_int]),
    ('XChangeProperty', C.c_int, [P, U, U, U, C.c_int, C.c_int, P, C.c_int]),
    ('XStoreName', C.c_int, [P, U, C.c_char_p]),
    ('XSelectInput', C.c_int, [P, U, C.c_long]), ('XMapWindow', C.c_int, [P, U]),
    ('XFlush', C.c_int, [P]), ('XPending', C.c_int, [P]),
    ('XConnectionNumber', C.c_int, [P]), ('XNextEvent', C.c_int, [P, P]),
    ('XLookupString', C.c_int, [P, P, C.c_int, P, P]),
    ('XDestroyWindow', C.c_int, [P, U]), ('XCloseDisplay', C.c_int, [P]),
]:
    fn = getattr(X, name)
    fn.restype, fn.argtypes = restype, args

class InputEvent(C.Structure):
    _fields_ = [('type', C.c_int), ('serial', U), ('send_event', C.c_int),
               ('display', P), ('window', U), ('root', U), ('subwindow', U),
               ('time', U), ('x', C.c_int), ('y', C.c_int), ('x_root', C.c_int),
               ('y_root', C.c_int), ('state', C.c_uint), ('code', C.c_uint),
               ('same_screen', C.c_int)]

class Event(C.Union):
    _fields_ = [('type', C.c_int), ('input', InputEvent), ('pad', C.c_long * 24)]

def say(**row):
    print(json.dumps(row), flush=True)

def end(*_):
    raise TimeoutError('probe ended')

signal.signal(signal.SIGTERM, end)
signal.signal(signal.SIGALRM, end)
signal.alarm(45)
d = X.XOpenDisplay(b':0')
assert d, 'X display unavailable'
w = 0
try:
    w = X.XCreateSimpleWindow(d, X.XDefaultRootWindow(d), 0, 0, 640, 400, 0, 0, 0x224466)
    for name, value in [(b'STEAM_GAME', 2000999066), (b'_NET_WM_PID', os.getpid())]:
        val = U(value)
        X.XChangeProperty(d, w, X.XInternAtom(d, name, 0), 6, 32, 0, C.byref(val), 1)
    X.XStoreName(d, w, b'Frame Control PR66 disposable input probe')
    X.XSelectInput(d, w, 1 | 2 | 4 | 8 | 64 | 32768 | 2097152)
    X.XMapWindow(d, w)
    X.XFlush(d)
    say(ready=True, window=w, pid=os.getpid(), display=':0', appid=2000999066)
    while True:
        while X.XPending(d):
            event = Event()
            X.XNextEvent(d, C.byref(event))
            if event.type in (2, 3, 4, 5, 6):
                e = event.input
                row = dict(type=event.type, window=e.window, x=e.x, y=e.y,
                           synthetic=bool(e.send_event))
                if event.type != 6:
                    row['code'] = e.code
                if event.type == 2:
                    buf, keysym = C.create_string_buffer(32), U()
                    n = X.XLookupString(C.byref(e), buf, 32, C.byref(keysym), None)
                    row.update(text=buf.raw[:n].decode('utf-8', 'replace'), keysym=keysym.value)
                say(**row)
        ready, _, _ = select.select([0, X.XConnectionNumber(d)], [], [], 0.2)
        if 0 in ready and not os.read(0, 1024):
            break
except TimeoutError:
    pass
finally:
    if w:
        X.XDestroyWindow(d, w)
    X.XCloseDisplay(d)
    say(cleaned=True)
