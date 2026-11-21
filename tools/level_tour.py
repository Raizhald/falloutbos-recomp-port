"""Load every level directly and check it: loads, no faults, frame rate, pictures.

    level_tour.py [--aspect 4:3] [--only CRB_2,MILL_1] [--seconds 80]

The title reads resx\\arguments.txt at boot ("dummy", then a level's directory
name from its level table) and goes straight into that level. The port hands
it a generated file through RECOMP_PATH_OVERRIDE; the game data is untouched.
Per level: build/levels/<aspect>/<DIR>/ (runtime.log, rt-*.bmp from
RECOMP_GPU_RT_DUMP) and one line in build/levels/results.jsonl.
"""
import argparse
import json
import os
import re
import struct
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument('--aspect', default='4:3')
ap.add_argument('--only', default='')
ap.add_argument('--seconds', type=float, default=80)
ap.add_argument('--scale', default='2')
a = ap.parse_args()


def levels():
    d = (root / 'game/default.xbe').read_bytes()
    out, i, end = [], 0xF5040, 0xF5040 + 0x1200
    while i < end:
        if d[i - 1] == 0 and re.match(rb'c[123]\x00', d[i:i + 3]):
            j, strs = i + 3, []
            while len(strs) < 2 and j < i + 64:
                if d[j]:
                    k = d.index(b'\x00', j)
                    strs.append(d[j:k].decode('latin1'))
                    j = k
                j += 1
            if len(strs) == 2 and (root / 'game/resx' / d[i:i + 2].decode() / strs[0]).is_dir():
                out.append((d[i:i + 2].decode(), strs[0], strs[1]))
            i = j
            continue
        i += 1
    return out


tag = a.aspect.replace(':', 'x')
base = root / 'build' / 'levels' / tag
base.mkdir(parents=True, exist_ok=True)
results = root / 'build' / 'levels' / 'results.jsonl'
only = {x.strip() for x in a.only.split(',') if x.strip()}
for chap, ldir, name in levels():
    if only and ldir not in only:
        continue
    out = base / ldir
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob('rt-*.bmp'):
        f.unlink()
    args = out / 'arguments.txt'
    args.write_bytes(b'dummy\r\n' + name.encode() + b'\r\n')
    (out / 'live.txt').write_text('')
    env = dict(os.environ, RECOMP_PB_EXEC='1', RECOMP_GPU_BACKEND='0', RECOMP_GPU_SCALE=a.scale,
               RECOMP_GPU_TEXFILTER='2', RECOMP_SILHOUETTE='1', RECOMP_AUDIO_MUTE='1',
               RECOMP_PAD_SCRIPT='', RECOMP_PAD_LIVE=str(out / 'live.txt'),
               RECOMP_PATH_OVERRIDE='resx\\arguments.txt=' + str(args),
               RECOMP_GPU_RT_DUMP=str(out), RECOMP_GPU_RT_DUMP_AT='30,50,70',
               RECOMP_SAVE_DIR=str(out / 'saves'))
    for k in ('RECOMP_FPS_LIMIT', 'RECOMP_WIDESCREEN', 'RECOMP_FB_WINDOW', 'RECOMP_MKB',
              'RECOMP_KEYBOARD'):
        env.pop(k, None)
    if a.aspect != '4:3':
        env['RECOMP_WIDESCREEN'] = a.aspect
    t0 = time.monotonic()
    frames = []                       # (seconds, frame count) from the back end's report
    pos = 0
    live = (out / 'live.txt').open('a')
    # A for dialogue and a little walking. (No Start: player 1 is bound to
    # port 1 now, so Start would open the pause menu.)
    presses = ['a', 'lup:800', 'a', 'lleft:800', 'ldown:800', 'a', 'lright:800']
    pi, nxt = 0, 18.0
    with (out / 'runtime.log').open('wb') as log:
        p = subprocess.Popen([str(root / 'bin/fbos.exe')], cwd=root, env=env, stdout=log,
                             stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            while p.poll() is None and time.monotonic() - t0 < a.seconds:
                el = time.monotonic() - t0
                if el >= nxt:
                    live.write(presses[pi % len(presses)] + '\n'); live.flush()
                    pi += 1
                    nxt = el + 4
                with (out / 'runtime.log').open('rb') as f:
                    f.seek(pos)
                    chunk = f.read()
                pos += len(chunk)
                for m in re.finditer(rb'\[GPUB\] frames (\d+):', chunk):
                    frames.append((el, int(m.group(1))))
                time.sleep(0.5)
        finally:
            crashed = p.poll() is not None
            if p.poll() is None:
                p.kill()
            p.wait()
            live.close()
    text = (out / 'runtime.log').read_text(errors='replace')
    want = '\\%s\\%s\\' % (chap, ldir)
    loaded = want.lower() in text.lower() and '.ddf' in text.lower()
    fps = None
    if len(frames) >= 2:
        (t1, f1), (t2, f2) = frames[-2], frames[-1]
        if t2 > t1:
            fps = round((f2 - f1) / (t2 - t1), 1)
    res = {'level': ldir, 'chapter': chap, 'name': name, 'aspect': a.aspect,
           'loaded': loaded, 'faults': text.count('[FAULT]'),
           'unresolved': len(re.findall(r'UNRESOLVED|unresolved call', text)),
           'exited_early': crashed, 'fps': fps,
           'pictures': sorted(f.name for f in out.glob('rt-*.bmp'))}
    with results.open('a') as r:
        r.write(json.dumps(res) + '\n')
    print(json.dumps(res), flush=True)
