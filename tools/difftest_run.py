"""Run bin/fbos-difftest.exe until it has written its snapshot, then stop it.

    difftest_run.py <name> <va hex> [nth] [timeout s] [count calls after s]
Writes build/difftest/<name>/{runtime.log,pre-*,post-*}."""
import os, subprocess, sys, time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
name, va = sys.argv[1], sys.argv[2]
nth = sys.argv[3] if len(sys.argv) > 3 else '60'
limit = float(sys.argv[4]) if len(sys.argv) > 4 else 150
after = sys.argv[5] if len(sys.argv) > 5 else '0'
out = root / 'build' / 'difftest' / name
out.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, RECOMP_PB_EXEC='1', RECOMP_AUDIO_MUTE='1',
           RECOMP_PAD_SCRIPT='25000:start,35000:a',
           RECOMP_DIFFTEST_VA=va, RECOMP_DIFFTEST_NTH=nth,
           RECOMP_DIFFTEST_DIR=str(out), RECOMP_DIFFTEST_AFTER=after, RECOMP_SAVE_DIR=str(out / 'saves'))
for k in ('RECOMP_FB_WINDOW', 'RECOMP_GPU_SHOT_DIR', 'RECOMP_FPS_LIMIT'):
    env.pop(k, None)
t0 = time.time()
with open(out / 'runtime.log', 'wb') as log:
    p = subprocess.Popen([str(root / 'bin/fbos-difftest.exe')], cwd=root, env=env,
                         stdout=log, stderr=subprocess.STDOUT)
    done = False
    while p.poll() is None and time.time() - t0 < limit:
        time.sleep(0.5)
        if b'[DIFFTEST]' in (out / 'runtime.log').read_bytes() and \
                b'dumped' in (out / 'runtime.log').read_bytes():
            done = True
            time.sleep(1)
            break
    if p.poll() is None:
        p.kill()
    p.wait()
print('snapshot written' if done else 'NO SNAPSHOT', round(time.time() - t0, 1), 's')
