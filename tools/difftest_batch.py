"""Test many recompiled functions against the original x86, one run of the game.

    difftest_batch.py [--minutes 20] [--after 5] [--carbon] [--name batch1]

Runs bin/fbos-difftest.exe with RECOMP_DIFFTEST_BATCH: the game snapshots the
first call of every function it has not tested yet, one at a time; this script
replays each in the emulator (tools/difftest_emulate.py), records the verdict
and frees the game for the next one. Results accumulate in
build/difftest-batch/results.jsonl (functions already there are skipped in
later runs); reports of functions that differ are kept in
build/difftest-batch/reports/<va>.txt.

Verdicts:
  same      the emulator returned and every register and byte agrees
  differs   it returned and something the function computed differs
            ("both" bytes or a register) -- worth a look
  missed    only the emulator wrote some bytes (the lifted code skipped a write)
  noemu     the emulator could not run it (kernel call, hardware, too long)
With --carbon the menus are walked into Carbon and Nadia walks and attacks,
so gameplay code gets called too.
"""
import argparse
import importlib.util
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument('--minutes', type=float, default=20)
ap.add_argument('--after', type=float, default=5)
ap.add_argument('--carbon', action='store_true')
ap.add_argument('--name', default='batch')
ap.add_argument('--emu-timeout', type=float, default=90)
ap.add_argument('--limit', type=int, default=30_000_000, help='emulator instruction limit')
ap.add_argument('--only', default='',
                help='test only these (comma-separated hex VAs), again if already tested')
ap.add_argument('--retest', default='',
                help='test these again (comma-separated hex VAs, or "flagged" for every '
                     'function whose last verdict was differs/missed)')
args = ap.parse_args()

out = root / 'build' / 'difftest-batch'
cur = out / 'cur'
reports = out / 'reports'
for d in (out, reports):
    d.mkdir(parents=True, exist_ok=True)
if cur.exists():
    shutil.rmtree(cur)
cur.mkdir()
results = out / 'results.jsonl'
done = set()
if results.exists():
    for line in results.read_text().splitlines():
        try:
            done.add(int(json.loads(line)['va'], 16))
        except (ValueError, KeyError):
            pass
if args.retest:
    last = {}
    if results.exists():
        for line in results.read_text().splitlines():
            try:
                r = json.loads(line)
                last[int(r['va'], 16)] = r['verdict']
            except (ValueError, KeyError):
                pass
    if args.retest == 'flagged':
        again = {v for v, k in last.items() if k in ('differs', 'missed')}
    else:
        again = {int(x, 16) for x in args.retest.split(',') if x.strip()}
    done -= again
    print('retesting %d functions' % len(again), flush=True)
only = out / 'only.txt'
if args.only:
    want = {int(x, 16) for x in args.only.split(',') if x.strip()}
    done -= want
    only.write_text(''.join('%08X\n' % v for v in sorted(want)))
skip = out / 'skip.txt'
skip.write_text(''.join('%08X\n' % v for v in sorted(done)))
run = out / args.name
if run.exists():
    shutil.rmtree(run)
run.mkdir()
(run / 'live.txt').write_text('')

env = dict(os.environ, RECOMP_PB_EXEC='1', RECOMP_AUDIO_MUTE='1', RECOMP_GPU_BACKEND='0',
           RECOMP_FPS_LIMIT='60', RECOMP_PAD_SCRIPT='',
           RECOMP_PAD_LIVE=str(run / 'live.txt'),
           RECOMP_DIFFTEST_BATCH='1', RECOMP_DIFFTEST_DIR=str(cur),
           RECOMP_DIFFTEST_SKIP=str(skip), RECOMP_DIFFTEST_AFTER=str(args.after),
           RECOMP_SAVE_DIR=str(run / 'saves'))
if args.only:
    env['RECOMP_DIFFTEST_ONLY'] = str(only)
for k in ('RECOMP_FB_WINDOW', 'RECOMP_KEYBOARD', 'RECOMP_MKB', 'RECOMP_DIFFTEST_VA'):
    env.pop(k, None)

nav = None
spec = importlib.util.spec_from_file_location('menu_nav', root / 'tools/menu_nav.py')
mn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mn)
nav = mn.MenuNav(run / 'runtime.log')
live = (run / 'live.txt').open('a')
rnd = random.Random(1)


def runs(text, kind, floats=False):
    """Addresses of the differing runs the report lists under `kind`.
    floats=False leaves out runs that are the same float to 1 part in 1e5
    on both sides (x87 rounding: the recompiled code computes in double)."""
    out, on = [], False
    for line in text.splitlines():
        if re.match(r'^(both|emu|native)\s+\d+ runs', line):
            on = line.startswith(kind)
            continue
        m = re.match(r'^\s+([0-9A-F]{8}) \+(\d+)', line)
        if on and m:
            f = re.search(r'\(float (\S+) / (\S+)\)', line)
            if f and not floats:
                try:
                    e, n = float(f.group(1)), float(f.group(2))
                    if e == e and n == n and abs(e - n) <= 1e-5 * max(abs(e), abs(n), 1e-3):
                        continue
                except ValueError:
                    pass
            out.append(int(m.group(1), 16))
        elif on and not line.startswith('    '):
            on = False
    return out


def verdict(text):
    """Bytes below the stack pointer at return are dead (the callees' frames,
    where the recompiled code keeps other temporaries): not a difference."""
    if 'DID NOT RETURN' in text or 'emulation stopped' in text:
        return 'noemu'
    m = re.search(r'esp\s+emulator ([0-9A-F]{8})', text)
    esp = int(m.group(1), 16) if m else 0
    dead = lambda a: esp and esp - 0x20000 <= a < esp
    # ecx and edx are scratch across a call: only the others count.
    regs = any(l.split()[0] in ('eax', 'ebx', 'esi', 'edi', 'esp', 'st0')
               for l in text.splitlines() if l.endswith('<-- differs'))
    both = [a for a in runs(text, 'both') if not dead(a)]
    emu = [a for a in runs(text, 'emu') if not dead(a)]
    if both or regs:
        return 'differs'
    if emu:
        return 'missed'
    return 'same'


counts = {}
t0 = time.monotonic()
pre_seen = None
with (run / 'runtime.log').open('wb') as log, results.open('a') as res:
    p = subprocess.Popen([str(root / 'bin/fbos-difftest.exe')], cwd=root, env=env,
                         stdout=log, stderr=subprocess.STDOUT,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        next_move = 0.0
        while p.poll() is None and time.monotonic() - t0 < args.minutes * 60:
            el = time.monotonic() - t0
            for b in nav.poll(el):
                live.write(b + '\n'); live.flush()
            if args.carbon and nav.carbon_at is not None and el > nav.carbon_at + 20 \
                    and el >= next_move:
                live.write(rnd.choice(['lup:800', 'ldown:800', 'lleft:800', 'lright:800',
                                       'a', 'a', 'rt+a:600', 'y', 'rleft:400']) + '\n')
                live.flush()
                next_move = el + 3
            ready = cur / 'ready'
            if ready.exists():
                va = ready.read_text().strip()
                pre_seen = None
                if (cur / 'pre-mem.bin').exists() and (cur / 'post-mem.bin').exists():
                    try:
                        r = subprocess.run([sys.executable, str(root / 'tools/difftest_emulate.py'),
                                            str(cur), '--limit', str(args.limit)],
                                           capture_output=True, text=True,
                                           timeout=args.emu_timeout)
                        text = r.stdout + r.stderr
                        v = verdict(text) if r.returncode == 0 else 'noemu'
                    except subprocess.TimeoutExpired:
                        text, v = 'emulator timed out', 'noemu'
                else:
                    text, v = 'snapshot incomplete', 'noemu'
                if v in ('differs', 'missed'):
                    (reports / ('%s.txt' % va)).write_text(text)
                res.write(json.dumps({'va': va, 'verdict': v, 'run': args.name,
                                      't': round(el, 1)}) + '\n')
                res.flush()
                counts[v] = counts.get(v, 0) + 1
                print('%7.1f s  %s  %s' % (el, va, v), flush=True)
                for f in cur.iterdir():
                    if f.name != 'ready':
                        f.unlink()
                ready.unlink()
            elif (cur / 'pre-mem.bin').exists():
                # A call that never returns: the game gives it up after 30 s.
                if pre_seen is None:
                    pre_seen = el
                elif el - pre_seen > 40:
                    for f in cur.iterdir():
                        f.unlink()
                    pre_seen = None
            time.sleep(0.05)
    finally:
        if p.poll() is None:
            p.kill()
        p.wait()
        live.close()
print('done:', json.dumps(counts))
