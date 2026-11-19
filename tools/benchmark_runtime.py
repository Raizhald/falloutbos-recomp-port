"""Measure completed GPU flips and process CPU time in a stationary Carbon scene.

The run follows the game instead of a fixed clock: after the fixed menu
presses (to 80 s) it presses A every 5 s until the log shows Carbon loading
(and 15 s more for the intro dialog); measurement starts --settle seconds
after Carbon loads, and the --combat-after route is sent through
RECOMP_PAD_LIVE relative to the end of measurement. A fixed timeline broke
whenever the menus took longer (the attract loop can restart the intro).

Windows x64/MSVC build only. The internal counter is resolved from this exe's
linker map; its struct prefix mirrors nv2a_pb_exec.c and is checked against
the log's reported flip count. No profiler or framebuffer window is enabled.
"""
import argparse
import ctypes as c
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import time

root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--name', required=True)
p.add_argument('--threads', type=int, help='Omit to measure the exe default')
p.add_argument('--settle', type=float, default=18,
               help='Seconds after Carbon loads before measuring')
p.add_argument('--carbon-timeout', type=float, default=300,
               help='Give up if Carbon has not loaded by then (s)')
p.add_argument('--seconds', type=float, default=35)
p.add_argument('--exe', type=Path, default=root / 'bin/fbos.exe')
p.add_argument('--combat-after', action='store_true',
               help='After the stationary measurement, run the Bar scenario for 220s')
a = p.parse_args()
if a.seconds <= 0 or a.settle < 0 or (a.threads is not None and not 1 <= a.threads <= 32):
    p.error('invalid measurement interval/thread count')
exe = a.exe.resolve()
out = root / 'build' / a.name
out.mkdir(parents=True, exist_ok=False)
spec = importlib.util.spec_from_file_location('boot', root / 'tools/boot_check.py')
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)

# Prefix through s_gpu.flips, with MSVC's default 8-byte member alignment.
U = c.c_uint32
class GPU(c.Structure):
    _fields_ = [('attr', U * 64), ('prim', U), ('idx', U * 65536),
                ('idx_count', U), ('inline_buf', U * 65536), ('inline_count', U),
                ('imm_attr', c.c_float * 64), ('imm_used', c.c_uint16),
                ('imm_count', U), ('inline_active', c.c_int),
                ('draws', U), ('verts', U), ('nonzero_draws', U),
                ('bounds', c.c_float * 4), ('surface', U * 3), ('drawn_offset', U),
                ('drawn_shape', U * 6), ('drawn_stale', c.c_int),
                ('pixels', c.c_uint64), ('pixel_max', U), ('clip_raw', U * 2),
                ('aa', c.c_float * 2), ('clear_color', U), ('clears', U),
                ('unhandled_total', U), ('flip_read', U), ('flip_write', U),
                ('flip_modulo', U), ('flips', U)]
mapping = exe.with_suffix('.map').read_text(errors='replace')
symbol = re.search(r'\bs_gpu\s+([0-9A-Fa-f]{16})\s', mapping)
if not symbol:
    raise RuntimeError('Keep the matching linker .map beside the exe')
counter_address = int(symbol[1], 16) + GPU.flips.offset
k = c.WinDLL('kernel32', use_last_error=True)
k.ReadProcessMemory.argtypes = [c.c_void_p, c.c_void_p, c.c_void_p, c.c_size_t, c.c_void_p]
k.GetProcessTimes.argtypes = [c.c_void_p] + [c.c_void_p] * 4

pad = ','.join(s for s in boot.PAD.split(',') if int(s.split(':')[0]) < 80000)
CARBON = 'c1\\CRB_1a\\CRB_1a.ddf'
combat = []
if a.combat_after:
    # The same route as playtest_session --combat-repro, starting 5 s after
    # the measured interval. No gameplay inputs contaminate the FPS sample.
    steps = [(125000, 'ldown', 15000), (141000, 'x', 400)]
    steps += [(t, button, 700) for t, button in [
        (155000,'a'), (158000,'down'), (160000,'down'), (162000,'down'),
        (164000,'down'), (167000,'a'), (171000,'a'), (177000,'x'),
        (181000,'a'), (209000,'a'), (215000,'back'), (218000,'down'),
        (221000,'a'), (224000,'b')]]
    steps += [(227000,'lright',6000), (235000,'rt+a',6000),
              (270000,'lleft',5000), (280000,'lup',5000), (290000,'rt+a',12000)]
    combat = [((t - 125000) / 1000 + 5, '%s:%d' % (button, duration))
              for t, button, duration in steps]
(out / 'live.txt').write_text('', encoding='ascii')
env = dict(os.environ, RECOMP_PB_EXEC='1', RECOMP_AUDIO_MUTE='1',
           RECOMP_PAD_SCRIPT=pad, RECOMP_PAD_LIVE=str(out / 'live.txt'),
           RECOMP_SAVE_DIR=str(out / 'test-saves'),
           RECOMP_FB_PRESENT_DUMP=str(out / 'latest.bmp'),
           RECOMP_FB_PRESENT_DUMP_EVERY='120')
for name in ('FBOS_PROFILE', 'RECOMP_FB_WINDOW', 'RECOMP_KEYBOARD',
             'RECOMP_FB_DUMP', 'RECOMP_FB_VA', 'RECOMP_RASTER_THREADS'):
    env.pop(name, None)
if a.threads is not None:
    env['RECOMP_RASTER_THREADS'] = str(a.threads)
samples = []
measurement_done = False
carbon_at = None          # harness seconds when the log first shows Carbon
measure_from = None
measure_end = None
next_a = 80.0
log_pos = 0
log_tail = ''
live = (out / 'live.txt').open('a', encoding='ascii')
def press(line):
    live.write(line + '\n')
    live.flush()
measurement_log = ''
started = time.perf_counter()
with (out / 'runtime.log').open('wb') as log:
    proc = subprocess.Popen([str(exe)], cwd=root, env=env, stdout=log,
                            stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    print('Benchmark PID %d, threads %s, measuring %.0fs from Carbon+%.0fs' % (
        proc.pid, a.threads or 'default', a.seconds, a.settle), flush=True)
    def sample():
        flips = U()
        if not k.ReadProcessMemory(int(proc._handle), counter_address,
                                   c.byref(flips), 4, None):
            raise c.WinError(c.get_last_error())
        times = [c.c_uint64() for _ in range(4)]
        if not k.GetProcessTimes(int(proc._handle), *(c.byref(t) for t in times)):
            raise c.WinError(c.get_last_error())
        return {'elapsed': time.perf_counter() - started, 'flips': flips.value,
                'cpu_seconds': (times[2].value + times[3].value) / 1e7}
    try:
        while proc.poll() is None:
            elapsed = time.perf_counter() - started
            if carbon_at is None:
                with (out / 'runtime.log').open('rb') as f:
                    f.seek(log_pos)
                    chunk = f.read().decode('latin-1')
                    log_pos += len(chunk)
                if CARBON in log_tail + chunk:
                    carbon_at = elapsed
                    measure_from = carbon_at + a.settle
                    print('Carbon loaded at %.1fs' % carbon_at, flush=True)
                log_tail = chunk[-200:]
                if carbon_at is None and elapsed > a.carbon_timeout:
                    print('Carbon did not load within %.0fs' % a.carbon_timeout,
                          flush=True)
                    break
            # Keep pressing A through menus, the attract loop and the intro
            # text until Carbon is up, then 15 s more for its intro dialog.
            if elapsed >= next_a and (carbon_at is None or
                                      elapsed < carbon_at + 15):
                press('a')
                next_a += 5
            if (measure_from is not None and elapsed >= measure_from
                    and not measurement_done):
                samples.append(sample())
                if samples[-1]['elapsed'] - samples[0]['elapsed'] >= a.seconds:
                    measurement_done = True
                    measure_end = elapsed
                    measurement_log = (out / 'runtime.log').read_text(errors='replace')
                    print('Stationary measurement complete', flush=True)
            if measurement_done:
                while combat and elapsed >= measure_end + combat[0][0]:
                    press(combat.pop(0)[1])
                if not a.combat_after or elapsed >= measure_end + 220:
                    break
            time.sleep(0.25)
    finally:
        timed_out = proc.poll() is None
        if timed_out:
            proc.kill()
        proc.wait()
        live.close()
text = (out / 'runtime.log').read_text(errors='replace')
reported = re.findall(r'\[GPU\] [\d.]+ fps \((\d+) flips\)', measurement_log)
checks = {name: bool(fn(text)) for name, fn in boot.MILESTONES}
checks['no contiguous allocation failures'] = 'arena exhausted' not in text
if a.combat_after:
    checks['Bar loads after measurement'] = '\\BAR\\BAR.ddf' in text
checks['counter agrees with GPU log'] = bool(reported and samples and
    -10 <= samples[-1]['flips'] - int(reported[-1]) < 2000)   # log may lead by a flip
if len(samples) < 2:
    raise RuntimeError('Game exited before measurement completed')
dt = samples[-1]['elapsed'] - samples[0]['elapsed']
frames = samples[-1]['flips'] - samples[0]['flips']
cpu = samples[-1]['cpu_seconds'] - samples[0]['cpu_seconds']
checks['completed frames advance'] = frames > 0
result = {'exe_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
          'combat_after': a.combat_after,
          'total_elapsed_seconds': time.perf_counter() - started,
          'threads_override': a.threads, 'logical_cpus': os.cpu_count(),
          'carbon_loaded_at': carbon_at, 'measurement_started_at': measure_from,
          'measurement_seconds': dt, 'completed_flips': frames,
          'fps': frames / dt, 'cpu_core_equivalents': cpu / dt,
          'ended_by_harness': timed_out, 'checks': checks,
          'counter_address': hex(counter_address), 'counter_offset': GPU.flips.offset,
          'samples': samples}
(out / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'samples'}), flush=True)
raise SystemExit(0 if timed_out and all(checks.values()) else 1)
