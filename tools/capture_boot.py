"""Capture completed display frames and upstream boot milestones, without a window.

Requires our xboxrecomp present-capture patch. Each run uses a new directory;
the result distinguishes a normal test timeout from an early game exit.
"""
import argparse
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import time

from boot_check import MILESTONES, PAD, TIMEOUT_S

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build" /
                        ("capture-" + datetime.now().strftime("%Y%m%d-%H%M%S")))
    parser.add_argument("--timeout", type=float, default=TIMEOUT_S)
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be a finite positive number")
    exe = ROOT / "bin/fbos.exe"
    if not exe.is_file() or not (ROOT / "game/default.xbe").is_file():
        parser.error("build bin/fbos.exe and unpack your game into game/ first")
    capture = args.output.resolve()
    capture.mkdir(parents=True, exist_ok=False)
    latest = capture / "latest.bmp"
    env = dict(os.environ, RECOMP_PAD_SCRIPT=PAD, RECOMP_PB_EXEC="1", RECOMP_AUDIO_MUTE="1",
               RECOMP_FB_PRESENT_DUMP=str(latest), RECOMP_FB_PRESENT_DUMP_EVERY="60")
    for name in ("RECOMP_FB_WINDOW", "RECOMP_KEYBOARD", "RECOMP_FB_DUMP",
                 "RECOMP_FB_DUMP_FLIPS", "RECOMP_FB_VA"):
        env.pop(name, None)
    frames = []
    previous = 0
    started = time.monotonic()
    timed_out = False

    def retain_frame():
        nonlocal previous
        try:
            stamp = latest.stat().st_mtime_ns
            if stamp == previous:
                return
            data = latest.read_bytes()
        except OSError:
            return
        if len(data) < 54 or data[:2] != b"BM":
            return
        if struct.unpack_from("<I", data, 2)[0] != len(data):
            return  # writer has not finished yet
        name = "frame-%03d.bmp" % len(frames)
        (capture / name).write_bytes(data)
        frames.append({"file": name, "elapsed_seconds": round(time.monotonic()-started, 2)})
        previous = stamp

    print("Capturing boot to %s" % capture, flush=True)
    with (capture / "runtime.log").open("wb") as log_file:
        process = subprocess.Popen([str(exe)], cwd=ROOT, env=env, stdout=log_file,
                                   stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            while process.poll() is None:
                retain_frame()
                if time.monotonic() - started >= args.timeout:
                    timed_out = True
                    break
                time.sleep(0.2)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
    retain_frame()
    log = (capture / "runtime.log").read_text(encoding="utf-8", errors="replace")
    milestones = {name: bool(test(log)) for name, test in MILESTONES}
    result = {"elapsed_seconds": round(time.monotonic()-started, 2),
              "ended_by_test_timeout": timed_out, "process_exit_code": process.returncode,
              "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
              "milestones": milestones, "passed": sum(milestones.values()),
              "of": len(milestones), "completed_display_frames": frames}
    (capture / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Boot: %d/%d; completed frames: %d; ended by test timeout: %s" %
          (result["passed"], result["of"], len(frames), timed_out), flush=True)
    return 0 if all(milestones.values()) and timed_out and frames else 1


if __name__ == "__main__":
    raise SystemExit(main())
