"""Walk the front-end menus by a script and keep a frame every second.

    menu_peek.py --name NAME --steps "3:down,4:down,5:a,8:a" [--seconds 60]

Step times are seconds after the main menu video (Main_Menu.bik) first
appears in the log; until then Start is pressed every 2 s to skip the intro.
With --carbon the steps count from 15 s after Carbon loads instead.
A step "dump=NAME" saves guest RAM to build/NAME_DIR/NAME.bin (GPU back end).
Frames go to build/NAME/frame-SSS.bmp (the presented 640x480 picture). For
reading screens the harnesses cannot reach otherwise (options, controls).
"""
import argparse
import os
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument('--name', required=True)
ap.add_argument('--steps', default='')
ap.add_argument('--seconds', type=float, default=60)
ap.add_argument('--carbon', action='store_true',
                help='Start a new game first (tools/menu_nav.py); steps count from Carbon + 15 s')
ap.add_argument('--level', default='',
                help='go straight into this level (table name, e.g. CARB_1a) through '
                     'resx\\arguments.txt; steps count from boot')
args = ap.parse_args()
cap = root / 'build' / args.name
cap.mkdir(parents=True, exist_ok=False)
(cap / 'live.txt').write_text('', encoding='ascii')
steps = []
for s in filter(None, args.steps.split(',')):
    t, b = s.split(':', 1)
    steps.append((float(t), b))
env = dict(os.environ, RECOMP_PAD_SCRIPT='', RECOMP_PB_EXEC='1', RECOMP_AUDIO_MUTE='1',
           RECOMP_PAD_LIVE=str(cap / 'live.txt'),
           RECOMP_MEMDUMP_DIR=str(cap),
           RECOMP_SAVE_DIR=str(cap / 'test-saves'),
           RECOMP_FB_PRESENT_DUMP=str(cap / 'latest.bmp'),
           RECOMP_FB_PRESENT_DUMP_EVERY='15')
if args.level:
    af = cap / 'arguments.txt'
    af.write_bytes(b'dummy\r\n' + b''.join(w.encode() + b'\r\n' for w in args.level.split()))
    env['RECOMP_PATH_OVERRIDE'] = 'resx\\arguments.txt=' + str(af)
for k in ('RECOMP_FB_WINDOW', 'RECOMP_KEYBOARD', 'RECOMP_FB_DUMP', 'RECOMP_FB_VA'):
    env.pop(k, None)
live = (cap / 'live.txt').open('a', encoding='ascii')
nav = None
if args.carbon:
    import importlib.util
    spec = importlib.util.spec_from_file_location('menu_nav', root / 'tools/menu_nav.py')
    mn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mn)
    nav = mn.MenuNav(cap / 'runtime.log')
t0 = time.monotonic()
menu_at = 0.0 if args.level else None
next_start = 15.0
next_cap = 0.0
with (cap / 'runtime.log').open('wb') as log:
    p = subprocess.Popen([str(root / 'bin/fbos.exe')], cwd=root, env=env, stdout=log,
                         stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        while p.poll() is None:
            el = time.monotonic() - t0
            if el >= args.seconds:
                break
            if nav is not None and menu_at is None:
                for b in nav.poll(el):
                    live.write(b + '\n'); live.flush()
                if nav.carbon_at is not None and el >= nav.carbon_at + 15:
                    menu_at = el
                    print('carbon + 15 s at %.1f' % el, flush=True)
            elif menu_at is None:
                txt = (cap / 'runtime.log').read_bytes().decode('latin-1')
                if 'Main_Menu.bik' in txt:
                    menu_at = el
                    print('main menu at %.1f' % el, flush=True)
                elif el >= next_start:
                    live.write('start\n'); live.flush()
                    next_start = el + 2
            else:
                while steps and el >= menu_at + steps[0][0]:
                    b = steps.pop(0)[1]
                    if b.startswith('dump='):   # guest RAM -> NAME.bin (back end)
                        (cap / 'req').write_text(b[5:] + '\n', encoding='ascii')
                    else:
                        live.write(b + '\n'); live.flush()
            if menu_at is not None and el >= next_cap:
                try:
                    d = (cap / 'latest.bmp').read_bytes()
                    if d[:2] == b'BM':
                        (cap / ('frame-%03d.bmp' % (el - menu_at))).write_bytes(d)
                except OSError:
                    pass
                next_cap = el + 1
            time.sleep(0.1)
    finally:
        if p.poll() is None:
            p.kill()
        p.wait()
        live.close()
