# Local xboxrecomp changes

`xboxrecomp-swizzle-offset.patch` adds a direct Morton address calculation
for power-of-two texture dimensions up to 65536, retaining the old general
path for other inputs. It includes exhaustive address/texel equivalence
and swizzle round-trip tests. It applies independently to the pinned revision
and is already applied locally. See `docs/performance-textures.md`.

```powershell
cmake -S deps/xboxrecomp/tests/swizzle_offset -B build-swizzle-test -A x64
cmake --build build-swizzle-test --config Release --parallel 2
ctest --test-dir build-swizzle-test -C Release --output-on-failure
../fbos-venv/Scripts/python.exe tools/benchmark_runtime.py --name perf-with-gameplay --combat-after
```

The combined benchmark measures the stationary scene first; only afterward
does it start the Bar route and firing. Its FPS interval excludes those inputs.
The full combined run is approximately 380 seconds and remains muted.

`xboxrecomp-raster-stats.patch` isolates the raster workers' counters on
64-byte boundaries and replaces per-pixel writes to shared diagnostic counters
with private worker statistics, merged after the pipeline drains. It also
tests the raster batch at 1, 4 and 16 threads. It is already applied locally.
Apply independently to the pinned dependency revision; it does not change
pixel shading, resolution or the worker count. See `docs/performance.md`.

```powershell
cmake -S deps/xboxrecomp/tests/nv2a_raster_batch -B build-raster-test -G "Visual Studio 17 2022" -A x64
cmake --build build-raster-test --config Release
ctest --test-dir build-raster-test -C Release --output-on-failure
../fbos-venv/Scripts/python.exe tools/benchmark_runtime.py --name perf-new-default
```

`xboxrecomp-audio-mute.patch` adds opt-in `RECOMP_AUDIO_MUTE=1` for the Windows
XAudio2 mastering voice. Apply it independently of the present-capture patch.
Our automated test tools enable it by default at the user's request.

`xboxrecomp-present-capture.patch` applies to the toolkit revision recorded in
`config/toolkit-revision.txt`. It contains the Windows framebuffer capture
change and five standalone regression tests; no game data or generated code.
The patch is already applied in our local `deps/xboxrecomp` checkout on branch
`codex/fbos-present-capture`. Do not apply it again there.

For a fresh dependency checkout at the baseline revision:

```powershell
git -C deps/xboxrecomp apply --check ../../patches/xboxrecomp-present-capture.patch
git -C deps/xboxrecomp apply ../../patches/xboxrecomp-present-capture.patch
```

Build the port normally after applying it. Capture a new boot:

```powershell
../fbos-venv/Scripts/python.exe tools/capture_boot.py
```

The tool creates a new `build/capture-<timestamp>` directory containing
`runtime.log`, `result.json`, and completed 640x480 display frames. It uses the
same controller script and milestone predicates as upstream `boot_check.py`.
It tests boot progression and logged failures; it does not validate gameplay.

Runtime options (read at the first present):

- `RECOMP_FB_PRESENT_DUMP=<file.bmp>` overwrites one BMP from the completed
  display copy. Works with or without the framebuffer window.
- `RECOMP_FB_PRESENT_DUMP_EVERY=N` captures every N presents; default 60.
- The older `RECOMP_FB_DUMP` retains its original draw-surface semantics.
  It can capture intermediate rendering and should not be used alone to
  diagnose a fault in the displayed image.

Standalone tests, from the port root with CMake/MSVC available:

```powershell
cmake -S deps/xboxrecomp/tests/fb_present_dump -B build-present-test -G "Visual Studio 17 2022" -A x64
cmake --build build-present-test --config Release
ctest --test-dir build-present-test -C Release --output-on-failure
```

The tests check disabled capture, 32-bit RGB, RGB565, horizontal AA and 2x2 AA;
they also verify BMP orientation, capture cadence, invalid-surface skipping,
and retention of a completed image while the next frame's memory changes.
