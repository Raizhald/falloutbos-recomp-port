# Development

Notes for building and debugging by hand. Players only need `Setup.cmd` and
`Play.cmd` (see the [README](../README.md)).

This port is a static recompilation: the x86 in `default.xbe` is translated to
C (`regen.sh`, output in `src/game/recomp/gen/`, never committed), compiled and
linked against the xboxrecomp runtime (kernel replacement, NV2A pushbuffer
executor with a Direct3D 11 back end, MCPX APU, USB). Game-specific code is in
`src/game/` (`main.c`, `recomp_manual.c` for hand-written overrides, `aim.c`
for mouse aim and the player silhouette).

The toolkit is https://github.com/Raizhald/xboxrecomp-port (`main`), cloned by
`Setup.cmd` into `deps/xboxrecomp`. Change history: `docs/handoff/` (Czech).

Player options are environment variables set by `Play.cmd` from
`settings.ini`: `RECOMP_GPU_BACKEND`, `RECOMP_GPU_SCALE`, `RECOMP_GPU_TEXFILTER`,
`RECOMP_WIDESCREEN`, `RECOMP_SILHOUETTE`, `RECOMP_VSYNC`, `RECOMP_FULLSCREEN`,
`RECOMP_WINDOW_SCALE`, `RECOMP_FPS_LIMIT`, `RECOMP_MKB` / `RECOMP_MKB_INI`,
`RECOMP_KEYBOARD`, `RECOMP_AUDIO_MUTE`.

## Building by hand

These are the commands `Setup.cmd` runs.

Prerequisites: Windows 10/11 x64; Python 3.10+ with `capstone`
(`py -3 -m pip install capstone`); Git for Windows (it provides `bash`);
CMake 3.20+; Visual Studio 2022 or its Build Tools with the C++ workload.
Use `py -3`, not `python`: the Microsoft Store alias for `python` is not a real
install. After installing anything, open a new terminal so PATH picks it up.

1. Get this repo and the toolkit:

   ```bash
   git clone https://github.com/Raizhald/falloutbos-recomp-port falloutbos
   cd falloutbos
   git clone https://github.com/Raizhald/xboxrecomp-port deps/xboxrecomp
   ```

2. Unpack your disc into `game/`:

   ```bash
   (cd deps/xboxrecomp && py -3 -m tools.xiso unpack "/path/to/Fallout - Brotherhood of Steel (USA).iso" -o ../../game)
   ```

   Expected: `extracted 491 files to ../../game`.

3. Generate the C (about 3 minutes, most of it the disassembler):

   ```bash
   RECOMP=deps/xboxrecomp ./regen.sh --disasm
   ```

   Expected, at the end:

   ```
   3888/3889 functions (0 failed), 543025 lines of C, 8 source files
   1 unresolved call targets stubbed (addresses called but not detected as functions)
   ```

4. Build:

   ```bash
   cmake -S . -B build-msvc -A x64 -DXBOXRECOMP_DIR=deps/xboxrecomp
   cmake --build build-msvc --config Release
   ```

   The executable lands in `bin/fbos.exe`.

5. Run from the repo root (it reads `game/default.xbe`), or use `Play.cmd`:

   ```bash
   RECOMP_PB_EXEC=1 RECOMP_FB_WINDOW=1 RECOMP_KEYBOARD=1 ./bin/fbos.exe
   ```

## Usage

| Variable | Effect |
|---|---|
| `RECOMP_PB_EXEC=1` | execute the title's NV2A pushbuffer, so it actually draws |
| `RECOMP_FB_WINDOW=1` | show the framebuffer in a window. Off by default: runs are headless |
| `RECOMP_FB_DUMP=prefix` | write frames as `prefix00000.bmp` ... |
| `RECOMP_FB_DUMP_FLIPS=<file>` | dump every flip while `<file>` exists |
| `RECOMP_WATCHDOG_SECS=N` | after N seconds, report where the guest is |
| `RECOMP_KERNEL_LOG_BUDGET=N` | log the first N kernel calls (default 200) |
| `RECOMP_KEYBOARD=1` | keyboard as player 1 (see Getting Started) |
| `RECOMP_PAD_SCRIPT="ms:button,..."` | scripted presses for headless runs, e.g. `25000:start,35000:a` |
| `RECOMP_USB_STATS=1` | controller transfer counts every few seconds |
| `RECOMP_RASTER_THREADS=N` | rasteriser worker threads (default: logical cores - 4). On a 6-core/12-thread CPU, 10 gave about 19 fps against 17; 12 starves the game and drops to 9 |
| `FBOS_PROFILE=<start>,<secs>` | sample every thread for `<secs>` seconds starting at `<start>`, print the top functions per thread |

`RECOMP_AC97_READY` and `RECOMP_USB` are set by `main.c` itself: the title
cannot initialise DirectSound without the first, or see a controller without
the second.

From power-on to Carbon, headless:

```bash
S="25000:start,35000:a,50000:a,65000:a"
for t in $(seq 80000 5000 250000); do S="$S,$t:a"; done
RECOMP_PAD_SCRIPT="$S" RECOMP_PB_EXEC=1 RECOMP_FB_DUMP=shot ./bin/fbos.exe
```

Headless capture, no window, works over RDP:

```bash
RECOMP_PB_EXEC=1 RECOMP_FB_DUMP=shot ./bin/fbos.exe
```

## Building from source

`./regen.sh` re-runs func_id, ABI analysis and codegen from the existing
disassembly; `./regen.sh --disasm` starts from the XBE. `RECOMP=<path>` points
it at a toolkit checkout other than `../xboxrecomp`. Entry tracing for
bring-up: list addresses in `config/trace_functions.json` and run
`TRACE_FUNCS=config/trace_functions.json ./regen.sh`.

## License

MIT, see [LICENSE](../LICENSE). That covers the code in this repo only.
Fallout: Brotherhood of Steel and its data belong to their owners; nothing from
the game is in this repo, and the generated C is never committed.
