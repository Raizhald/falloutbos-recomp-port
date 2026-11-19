"""Windowed smoke test: run the game with a window, capture what the screen
shows (not guest memory), toggle full screen with F11 and capture again.

    window_smoke.py --name <dir> [--seconds 70] [--env K=V ...]
Writes build/<name>/{runtime.log,win-*.bmp,result.json}. Audio is muted."""
import argparse, ctypes as c, ctypes.wintypes as w, json, os, subprocess, time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--name', required=True)
p.add_argument('--seconds', type=float, default=70)
p.add_argument('--shots', default='40,55')
p.add_argument('--fullscreen-at', type=float, default=60)
p.add_argument('--env', action='append', default=[])
a = p.parse_args()
out = root / 'build' / a.name
out.mkdir(parents=True, exist_ok=False)
u, g = c.WinDLL('user32'), c.WinDLL('gdi32')
u.FindWindowExA.restype = w.HWND
u.FindWindowExA.argtypes = [w.HWND, w.HWND, c.c_char_p, c.c_char_p]
u.GetDC.restype = w.HDC
u.GetDC.argtypes = [w.HWND]
g.CreateCompatibleDC.restype = w.HDC
g.CreateCompatibleDC.argtypes = [w.HDC]
g.CreateCompatibleBitmap.argtypes = [w.HDC, c.c_int, c.c_int]
g.DeleteObject.argtypes = [w.HGDIOBJ]
g.DeleteDC.argtypes = [w.HDC]
u.ReleaseDC.argtypes = [w.HWND, w.HDC]
u.GetClientRect.argtypes = [w.HWND, c.c_void_p]
u.ClientToScreen.argtypes = [w.HWND, c.c_void_p]
u.SetForegroundWindow.argtypes = [w.HWND]
u.PostMessageA.argtypes = [w.HWND, c.c_uint, w.WPARAM, w.LPARAM]
u.GetWindowThreadProcessId.argtypes = [w.HWND, c.c_void_p]
g.CreateCompatibleBitmap.restype = w.HBITMAP
g.SelectObject.restype = w.HGDIOBJ
g.SelectObject.argtypes = [w.HDC, w.HGDIOBJ]
g.BitBlt.argtypes = [w.HDC, c.c_int, c.c_int, c.c_int, c.c_int, w.HDC, c.c_int, c.c_int, w.DWORD]
g.GetDIBits.argtypes = [w.HDC, w.HBITMAP, c.c_uint, c.c_uint, c.c_void_p, c.c_void_p, c.c_uint]
try:
    u.SetProcessDPIAware()
except Exception:
    pass

def find(pid):
    h = None
    while True:
        h = u.FindWindowExA(None, h, b'XboxRecompFramebuffer', None)
        if not h:
            return None
        q = w.DWORD()
        u.GetWindowThreadProcessId(h, c.byref(q))
        if q.value == pid:
            return h

def capture(hwnd, path):
    r = w.RECT(); u.GetClientRect(hwnd, c.byref(r))
    pt = w.POINT(0, 0); u.ClientToScreen(hwnd, c.byref(pt))
    W, H = r.right, r.bottom
    sdc = u.GetDC(None); mdc = g.CreateCompatibleDC(sdc)
    bmp = g.CreateCompatibleBitmap(sdc, W, H); g.SelectObject(mdc, bmp)
    g.BitBlt(mdc, 0, 0, W, H, sdc, pt.x, pt.y, 0x00CC0020)
    class BIH(c.Structure):
        _fields_ = [('size', w.DWORD), ('w', c.c_long), ('h', c.c_long), ('planes', w.WORD),
                    ('bpp', w.WORD), ('comp', w.DWORD), ('isize', w.DWORD), ('xp', c.c_long),
                    ('yp', c.c_long), ('cu', w.DWORD), ('ci', w.DWORD)]
    bi = BIH(c.sizeof(BIH), W, -H, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = c.create_string_buffer(W * H * 4)
    g.GetDIBits(mdc, bmp, 0, H, buf, c.byref(bi), 0)
    g.DeleteObject(bmp); g.DeleteDC(mdc); u.ReleaseDC(None, sdc)
    hdr = b'BM' + (54 + W * H * 4).to_bytes(4, 'little') + b'\0' * 4 + (54).to_bytes(4, 'little')
    hdr += bytes(bi)[:40]
    Path(path).write_bytes(hdr + buf.raw)
    return W, H

env = dict(os.environ, RECOMP_PB_EXEC='1', RECOMP_FB_WINDOW='1', RECOMP_KEYBOARD='1',
           RECOMP_AUDIO_MUTE='1', RECOMP_PAD_SCRIPT='25000:start,35000:a',
           RECOMP_SAVE_DIR=str(out / 'test-saves'))
for kv in a.env:
    k, v = kv.split('=', 1); env[k] = v
shots = sorted(float(s) for s in a.shots.split(',') if s)
taken, fs_done = [], False
started = time.perf_counter()
with (out / 'runtime.log').open('wb') as log:
    proc = subprocess.Popen([str(root / 'bin/fbos.exe')], cwd=root, env=env, stdout=log,
                            stderr=subprocess.STDOUT)
    try:
        while proc.poll() is None:
            t = time.perf_counter() - started
            hwnd = find(proc.pid)
            if hwnd and shots and t >= shots[0]:
                u.SetForegroundWindow(hwnd); time.sleep(0.3)
                name = 'win-%03d%s.bmp' % (shots[0], '-fs' if fs_done else '')
                size = capture(hwnd, out / name)
                taken.append({'file': name, 'at': round(t, 1), 'client': size})
                shots.pop(0)
            if hwnd and not fs_done and t >= a.fullscreen_at:
                u.SetForegroundWindow(hwnd)
                u.PostMessageA(hwnd, 0x0100, 0x7A, 0)        # WM_KEYDOWN VK_F11
                u.PostMessageA(hwnd, 0x0101, 0x7A, 0xC0000000)
                fs_done = True
            if t >= a.seconds:
                break
            time.sleep(0.2)
    finally:
        alive = proc.poll() is None
        if alive:
            proc.kill()
        proc.wait()
text = (out / 'runtime.log').read_text(errors='replace')
res = {'shots': taken, 'ended_by_harness': alive,
       'direct_present': '[GPUB] presenting directly' in text,
       'faults': text.count('[FAULT]') + text.count('[EXCEPTION]')}
(out / 'result.json').write_text(json.dumps(res, indent=2))
print(json.dumps(res))
