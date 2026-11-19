"""Local interactive runtime test through the toolkit's live pad input file."""
import importlib.util
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--name', default='gameplay-session')
parser.add_argument('--load', action='store_true')
parser.add_argument('--combat', action='store_true')
parser.add_argument('--combat-repro', action='store_true')
parser.add_argument('--bar-ready', action='store_true',
                    help='Follow the Bar route and equip the pistol, then await live input')
parser.add_argument('--bar-fight', action='store_true',
                    help='Navigate around the partition and fire at the raiders')
parser.add_argument('--easy', action='store_true', help='Select Pansy for a separate gameplay test')
parser.add_argument('--combat-stress', action='store_true',
                    help='Repeat inventory and firing after --combat-repro')
parser.add_argument('--seconds', type=float, default=1200,
                    help='Bound the session duration (default: 1200 seconds)')
parser.add_argument('--save-root', type=Path)
args = parser.parse_args()
if args.bar_fight:
    args.bar_ready = True
if args.bar_ready:
    args.combat_repro = True
if args.seconds <= 0:
    parser.error('--seconds must be positive')
if args.load and (args.easy or args.combat_repro or args.combat):
    parser.error('difficulty and scripted Bar routes require a fresh game, not --load')
if args.bar_ready and args.combat_stress:
    parser.error('--bar-ready/--bar-fight cannot be combined with --combat-stress')
if args.combat_stress and not args.combat_repro:
    parser.error('--combat-stress requires --combat-repro')
capture = root / 'build' / args.name
capture.mkdir(parents=True, exist_ok=False)
(capture / 'live.txt').write_text('', encoding='ascii')
spec = importlib.util.spec_from_file_location('boot_check', root / 'tools/boot_check.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
pad = ','.join(step for step in check.PAD.split(',') if int(step.split(':')[0]) <= 120000)
if args.easy:
    pad = ','.join(sorted(pad.split(',') + ['60000:up:700'],
                          key=lambda step: int(step.split(':')[0])))
if args.load:
    pad = '25000:start,35000:down:250,36000:a:250'
if args.combat or args.combat_repro:
    pad += ',125000:ldown:15000,141000:x:400'
if args.combat_repro:
    # From a fresh Nadia: Ruby's final answer, Bar, equip the pistol, then
    # movement and lock-on/fire. Long releases make menu edges observable.
    steps = [(155000, 'a'), (158000, 'down'), (160000, 'down'),
             (162000, 'down'), (164000, 'down'), (167000, 'a'),
             (171000, 'a'), (177000, 'x'), (181000, 'a'),
             (209000, 'a'), (215000, 'back'), (218000, 'down'),
             (221000, 'a'), (224000, 'b')]
    pad += ',' + ','.join('%d:%s:700' % step for step in steps)
    if not args.bar_ready:
        pad += ',227000:lright:6000,235000:rt+a:6000'
    if args.bar_fight:
        fight = [(230000,'lup',6000), (237000,'lright',2000), (240000,'rt',1700),
                 (243000,'lleft',3000), (247000,'lup',3000),
                 (251000,'rt+a',3000), (255000,'rt+b',350),
                 (256000,'rt+a',3000), (260000,'rt+b',350),
                 (261000,'rt+a',3000), (265000,'rt+b',350),
                 (266000,'rt+a',3000), (271000,'start',700)]
        pad += ',' + ','.join('%d:%s:%d' % step for step in fight)
    if args.combat_stress:
        pad += ',270000:lleft:5000,280000:lup:5000,290000:rt+a:12000'
        for start in range(320000, 590000, 40000):
            pad += ',%d:back:700,%d:b:700,%d:rt+a:6000' % (
                start, start + 4000, start + 8000)
env = dict(os.environ, RECOMP_PAD_SCRIPT=pad, RECOMP_PB_EXEC='1',
           RECOMP_AUDIO_MUTE='1',
           RECOMP_PAD_LIVE=str(capture / 'live.txt'),
           RECOMP_SAVE_DIR=str(args.save_root.resolve() if args.save_root else capture / 'test-saves'),
           RECOMP_FB_PRESENT_DUMP=str(capture / 'latest.bmp'),
           RECOMP_FB_PRESENT_DUMP_EVERY='15')
for key in ('RECOMP_FB_WINDOW', 'RECOMP_KEYBOARD', 'RECOMP_FB_DUMP', 'RECOMP_FB_VA'):
    env.pop(key, None)
started = time.monotonic()
executable = root / 'bin/fbos.exe'
executable_sha256 = hashlib.sha256(executable.read_bytes()).hexdigest()
frames = []
next_capture = 0
with (capture / 'runtime.log').open('wb') as log:
    process = subprocess.Popen([str(executable)], cwd=root, env=env,
                               stdout=log, stderr=subprocess.STDOUT,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    print('Session started; PID %d; live input %s' % (process.pid, capture / 'live.txt'), flush=True)
    try:
        while process.poll() is None:
            elapsed = time.monotonic() - started
            if elapsed >= args.seconds or (capture / 'stop.flag').exists():
                break
            if elapsed >= next_capture:
                try:
                    data = (capture / 'latest.bmp').read_bytes()
                    if len(data) == 921654 and data[:2] == b'BM':
                        name = 'frame-%04d.bmp' % elapsed
                        (capture / name).write_bytes(data)
                        frames.append({'file': name, 'elapsed_seconds': round(elapsed, 2)})
                        next_capture = elapsed + 5
                except OSError:
                    pass
            time.sleep(0.2)
    finally:
        intentional_stop = process.poll() is None
        if intentional_stop:
            process.kill()
        process.wait()
text = (capture / 'runtime.log').read_text(encoding='utf-8', errors='replace')
result = {'elapsed_seconds': round(time.monotonic()-started, 2),
          'executable_sha256': executable_sha256,
          'requested_seconds': args.seconds,
          'combat_repro': args.combat_repro, 'combat_stress': args.combat_stress,
          'bar_ready': args.bar_ready, 'bar_fight': args.bar_fight,
          'difficulty': 'Pansy' if args.easy else 'Normal',
          'intentional_stop': intentional_stop, 'exit_code': process.returncode,
          'milestones': {name: bool(test(text)) for name, test in check.MILESTONES},
          'frames': frames, 'save_root': env['RECOMP_SAVE_DIR']}
result['bar_loaded'] = '\\BAR\\BAR.ddf' in text
result['contiguous_allocation_failures'] = text.count('[CONTIG] arena exhausted')
result['milestones']['no contiguous allocation failures'] = (
    result['contiguous_allocation_failures'] == 0)
(capture / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'frames'}), flush=True)
raise SystemExit(0 if intentional_stop and result['milestones']['no faults']
                 and result['milestones']['no unresolved calls']
                 and result['milestones']['no contiguous allocation failures']
                 and (not (args.combat or args.combat_repro) or result['bar_loaded']) else 1)
