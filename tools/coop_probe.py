"""Two-player probe: does the game's own co-op start with two emulated pads?

    coop_probe.py --name N [--seconds 260]

Headless (no window), muted, two pads (RECOMP_USB_PADS=2: pad 2 arrives on
the console's port 2). The menus are driven from the log as menu_nav.py
does, except that the first entry of the character menus picks "Two
Player" (down, then A on the next tick) and both players then press A. Writes build/<name>/
(runtime.log, rt-*.bmp from RECOMP_GPU_RT_DUMP, result.json).
"""
import argparse, json, os, re, subprocess, time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument('--name', required=True)
ap.add_argument('--seconds', type=float, default=260)
ap.add_argument('--players', type=int, default=2, help='1 = control run through One Player')
ap.add_argument('--dumps', default='24,27,29,31,33,35,38,42,50,60,75,90,110,140,180,230')
a = ap.parse_args()
out = root / 'build' / a.name
out.mkdir(parents=True, exist_ok=True)
for f in out.glob('rt-*.bmp'):
    f.unlink()
live_path = out / 'live.txt'
live_path.write_text('')
env = dict(os.environ, RECOMP_PB_EXEC='1', RECOMP_AUDIO_MUTE='1', RECOMP_GPU_BACKEND='0',
           RECOMP_GPU_SCALE='1', RECOMP_USB_PADS='2', RECOMP_PAD_SCRIPT='',
           RECOMP_PAD_LIVE=str(live_path), RECOMP_GPU_RT_DUMP=str(out),
           RECOMP_GPU_RT_DUMP_AT=a.dumps, RECOMP_GTEXT_TRACE='Please',
           RECOMP_SAVE_DIR=str(out / 'saves'))
for k in ('RECOMP_FB_WINDOW', 'RECOMP_FPS_LIMIT', 'RECOMP_WIDESCREEN', 'RECOMP_MKB',
          'RECOMP_KEYBOARD', 'RECOMP_PATH_OVERRIDE'):
    env.pop(k, None)
BIK = re.compile(r'\\resx\\([A-Za-z0-9_ ]+)\.bik')
CARBON = 'CRB_1a.ddf'
video, char_presses, carbon_at, pos, tail = '', 0, None, 0, ''
pressed = []
live = live_path.open('a')
t0 = time.monotonic()
nxt = 20.0
log_path = out / 'runtime.log'
with log_path.open('wb') as log:
    p = subprocess.Popen([str(root / 'bin/fbos.exe')], cwd=root, env=env, stdout=log,
                         stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        while p.poll() is None:
            el = time.monotonic() - t0
            if el > a.seconds:
                break
            with log_path.open('rb') as f:
                f.seek(pos)
                chunk = f.read().decode('latin-1')
            pos += len(chunk)
            text = tail + chunk
            tail = chunk[-200:]
            for m in BIK.finditer(text):
                n = m.group(1).lower()
                if n != 'empty':
                    if n.startswith('character_') and not video.startswith('character_'):
                        char_presses = 0
                    video = n
            if carbon_at is None and CARBON in text:
                carbon_at = el
            if el >= nxt and (carbon_at is None or el < carbon_at + 120):
                nxt = el + 2.0
                if carbon_at is not None:
                    btn = ['a', 'p2-a']               # dialogue, both players
                elif video in ('intro', 'interplay'):
                    btn = ['start']
                elif video.startswith('character_'):
                    char_presses += 1
                    if a.players == 2 and char_presses == 1:
                        btn = ['down']                # One Player -> Two Player
                    elif char_presses <= 2:
                        btn = ['a']
                    else:
                        btn = ['a', 'p2-a']
                else:
                    btn = ['a']
                for b in btn:
                    live.write(b + '\n')
                live.flush()
                pressed.append((round(el, 1), video, btn))
            time.sleep(0.2)
    finally:
        if p.poll() is None:
            p.kill()
        p.wait()
        live.close()
text = log_path.read_text(errors='replace')
res = {'name': a.name, 'pad2_arrived': 'pad 2 arriving' in text, 'carbon_at': carbon_at,
       'faults': text.count('[FAULT]'), 'gtext': re.findall(r'\[GTEXT\][^\n]*', text)[:5],
       'videos': list(dict.fromkeys(m.group(1) for m in BIK.finditer(text))),
       'pressed': pressed[:60]}
(out / 'result.json').write_text(json.dumps(res, indent=1))
print(json.dumps({k: v for k, v in res.items() if k != 'pressed'}))
