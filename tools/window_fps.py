"""Frame rate as the player sees it: the game in its window (direct present,
v-sync as set), driven into Carbon, the FPS read from the window title.

    window_fps.py --name N --seconds 40 [--vsync 1] [--limit 60] [--scale 2]
                  [--texfilter 2] [--aspect 4:3] [--silhouette 1]

Opens a real window on the desktop for about two minutes. Prints the FPS
samples taken once per second after Carbon + 20 s, and their min / mean /
share below 58.
"""
import argparse
import ctypes as c
import importlib.util
import json
import os
import re
import statistics
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument('--name', required=True)
ap.add_argument('--seconds', type=float, default=40)
ap.add_argument('--vsync', default='1')
ap.add_argument('--limit', default='60')
ap.add_argument('--scale', default='2')
ap.add_argument('--texfilter', default='2')
ap.add_argument('--aspect', default='4:3')
ap.add_argument('--silhouette', default='1')
ap.add_argument('--mkb', action='store_true', help='mouse and keyboard on, as Play.cmd does')
ap.add_argument('--level', default='', help='go straight into this level (its table name, e.g. '
                'CARB_1a) through resx\\arguments.txt; measuring starts 25 s in')
ap.add_argument('--bar', action='store_true',
                help='walk Nadia into the bar (the route of playtest_session --bar-ready) '
                     'and measure there')
a = ap.parse_args()

cap = root / 'build' / a.name
cap.mkdir(parents=True, exist_ok=True)
(cap / 'live.txt').write_text('')
env = dict(os.environ, RECOMP_PB_EXEC='1', RECOMP_FB_WINDOW='1', RECOMP_GPU_BACKEND='0',
           RECOMP_GPU_SCALE=a.scale, RECOMP_GPU_TEXFILTER=a.texfilter, RECOMP_VSYNC=a.vsync,
           RECOMP_AUDIO_MUTE='1', RECOMP_PAD_SCRIPT='', RECOMP_PAD_LIVE=str(cap / 'live.txt'),
           RECOMP_SAVE_DIR=str(cap / 'saves'))
for k in ('RECOMP_FPS_LIMIT', 'RECOMP_WIDESCREEN', 'RECOMP_SILHOUETTE', 'RECOMP_MKB',
          'RECOMP_KEYBOARD'):
    env.pop(k, None)
if a.limit != '0':
    env['RECOMP_FPS_LIMIT'] = a.limit
if a.aspect != '4:3':
    env['RECOMP_WIDESCREEN'] = a.aspect
if a.level:
    af = cap / 'arguments.txt'
    af.write_bytes(b'dummy\r\n' + a.level.encode() + b'\r\n')
    env['RECOMP_PATH_OVERRIDE'] = 'resx\\arguments.txt=' + str(af)
if a.mkb:
    env['RECOMP_MKB'] = '1'
    env['RECOMP_MKB_INI'] = str(root / 'mkb.ini')
if a.silhouette == '1':
    env['RECOMP_SILHOUETTE'] = '1'

spec = importlib.util.spec_from_file_location('menu_nav', root / 'tools/menu_nav.py')
mn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mn)
nav = mn.MenuNav(cap / 'runtime.log')
u32 = c.windll.user32
u32.FindWindowW.restype = c.c_void_p
u32.FindWindowW.argtypes = [c.c_wchar_p, c.c_wchar_p]
u32.GetWindowTextW.argtypes = [c.c_void_p, c.c_wchar_p, c.c_int]


def title():
    h = u32.FindWindowW('XboxRecompFramebuffer', None)
    if not h:
        return ''
    buf = c.create_unicode_buffer(256)
    u32.GetWindowTextW(h, buf, 256)
    return buf.value


# playtest_session's Bar route, as seconds after Carbon + 18 s.
route = []
if a.bar:
    steps = [(125000, 'ldown:15000'), (141000, 'x:400')] + [
        (t, b + ':700') for t, b in [(155000, 'a'), (158000, 'down'), (160000, 'down'),
                                     (162000, 'down'), (164000, 'down'), (167000, 'a'),
                                     (171000, 'a'), (177000, 'x'), (181000, 'a'),
                                     (209000, 'a'), (215000, 'back'), (218000, 'down'),
                                     (221000, 'a'), (224000, 'b')]]
    for t, b in steps:
        route.append(((t - 125000) / 1000.0, b))
live = (cap / 'live.txt').open('a')
samples = []
moves = ['lright:1500', 'lup:1500', 'lleft:1500', 'ldown:1500']
t0 = time.monotonic()
with (cap / 'runtime.log').open('wb') as log:
    p = subprocess.Popen([str(root / 'bin/fbos.exe')], cwd=root, env=env, stdout=log,
                         stderr=subprocess.STDOUT)
    try:
        start = None
        nxt = 0.0
        mi = 0
        while p.poll() is None:
            el = time.monotonic() - t0
            if el > 400:
                break
            if not a.level:
                for b in nav.poll(el):
                    live.write(b + '\n'); live.flush()
            elif start is None and el > 25:
                start = el
            while route and nav.carbon_at is not None and el >= nav.carbon_at + 18 + route[0][0]:
                live.write(route.pop(0)[1] + '\n'); live.flush()
            if nav.carbon_at is not None and start is None and \
                    el > nav.carbon_at + (125 if a.bar else 20):
                start = el
            if start is not None:
                if el >= nxt:
                    m = re.search(r'FPS:\s*([0-9.]+)', title())
                    if m:
                        samples.append(float(m.group(1)))
                    if int(el) % 4 == 0 and not a.bar:
                        live.write(moves[mi % 4] + '\n'); live.flush(); mi += 1
                    nxt = el + 1.0
                if el - start >= a.seconds:
                    break
            time.sleep(0.05)
    finally:
        if p.poll() is None:
            p.kill()
        p.wait()
        live.close()
res = {'name': a.name, 'vsync': a.vsync, 'limit': a.limit, 'aspect': a.aspect,
       'samples': samples}
if samples:
    res.update(min=min(samples), mean=round(statistics.mean(samples), 1),
               below58=round(sum(s < 58 for s in samples) / len(samples), 2))
print(json.dumps(res))
(cap / 'result.json').write_text(json.dumps(res))
