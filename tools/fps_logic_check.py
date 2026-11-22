"""Does the game logic depend on the frame rate?

    fps_logic_check.py [--limits 30,60,0] [--level CARB_1a]

Goes straight into a level (resx\\arguments.txt, as level_tour.py), then holds
the left stick up for a fixed wall-clock time at each frame-rate limit
(0 = none) and dumps the render target before and after (RECOMP_GPU_RT_DUMP).
How far the scene moved between the two dumps is the distance walked: equal
at every limit = the logic runs on real time; proportional to the frame rate
= it advances per frame. Output: build/fpslogic/<limit>/, plus
build/fpslogic/result.json (FPS per run; the shift is measured from the
pictures, see the handoff).
"""
import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument('--limits', default='30,60,0')
ap.add_argument('--level', default='CARB_1a')
ap.add_argument('--walk-at', type=float, default=36)
ap.add_argument('--walk-ms', type=int, default=3000)
ap.add_argument('--dump-at', default='33,45')
ap.add_argument('--seconds', type=float, default=50)
a = ap.parse_args()

base = root / 'build' / 'fpslogic'
base.mkdir(parents=True, exist_ok=True)
res = []
for lim in a.limits.split(','):
    out = base / lim
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob('rt-*.bmp'):
        f.unlink()
    args = out / 'arguments.txt'
    args.write_bytes(b'dummy\r\n' + a.level.encode() + b'\r\n')
    (out / 'live.txt').write_text('')
    env = dict(os.environ, RECOMP_PB_EXEC='1', RECOMP_GPU_BACKEND='0', RECOMP_GPU_SCALE='2',
               RECOMP_GPU_TEXFILTER='2', RECOMP_SILHOUETTE='1', RECOMP_AUDIO_MUTE='1',
               RECOMP_PAD_SCRIPT='', RECOMP_PAD_LIVE=str(out / 'live.txt'),
               RECOMP_PATH_OVERRIDE='resx\\arguments.txt=' + str(args),
               RECOMP_GPU_RT_DUMP=str(out), RECOMP_GPU_RT_DUMP_AT=a.dump_at,
               RECOMP_SAVE_DIR=str(out / 'saves'))
    for k in ('RECOMP_FPS_LIMIT', 'RECOMP_WIDESCREEN', 'RECOMP_FB_WINDOW', 'RECOMP_MKB',
              'RECOMP_KEYBOARD'):
        env.pop(k, None)
    if lim != '0':
        env['RECOMP_FPS_LIMIT'] = lim
    presses = [(18, 'a'), (24, 'a'), (30, 'a'), (a.walk_at, 'lup:%d' % a.walk_ms)]
    live = (out / 'live.txt').open('a')
    marks = []
    t0 = time.monotonic()
    with (out / 'runtime.log').open('wb') as log:
        p = subprocess.Popen([str(root / 'bin/fbos.exe')], cwd=root, env=env, stdout=log,
                             stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            while p.poll() is None and time.monotonic() - t0 < a.seconds:
                el = time.monotonic() - t0
                n = len(re.findall(rb'\[GPUB\] frames', (out / 'runtime.log').read_bytes()))
                if not marks or marks[-1][1] != n:
                    marks.append((el, n))
                while presses and el >= presses[0][0]:
                    live.write(presses.pop(0)[1] + '\n')
                    live.flush()
                time.sleep(0.05)
        finally:
            if p.poll() is None:
                p.kill()
            p.wait()
            live.close()
    text = (out / 'runtime.log').read_text(errors='replace')
    fps = None
    if len(marks) >= 3:
        (t1, n1), (t2, n2) = marks[1], marks[-1]
        fps = round((n2 - n1) * 600 / (t2 - t1), 1) if t2 > t1 else None
    res.append({'limit': lim, 'fps': fps, 'faults': text.count('[FAULT]'),
                'gpub_lines': [l for l in text.splitlines() if l.startswith('[GPUB] frames')][-3:],
                'pictures': sorted(f.name for f in out.glob('rt-*.bmp'))})
    print(json.dumps(res[-1]), flush=True)
(base / 'result.json').write_text(json.dumps(res, indent=1))
