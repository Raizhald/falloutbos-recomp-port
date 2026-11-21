# Independent Xbox port development

Current gameplay/memory evidence is in `docs/playtesting.md`; the subsequent
renderer performance work is in `docs/performance.md`. The workspace outputs
also contain a Czech handoff, test summaries and the local launcher.
The subsequent texture address optimization and gameplay verification are in
`docs/performance-textures.md`.

User preference: automated runs must be silent. Set `RECOMP_AUDIO_MUTE=1`;
the versioned capture/playtest tools now do this by default. This only mutes
the host mastering voice and keeps the APU and its completion timing active.

## Starting point (2026-11-18)

- Local development branch: `codex/xbox-port`.
- Upstream: https://github.com/sp00nznet/falloutbos-recomp
- Upstream baseline: `ec7bd923e9281c79579ba4533aa76036934b9a91`.
- Toolkit: https://github.com/sp00nznet/xboxrecomp, branch `work/falloutbos`.
- Toolkit baseline recorded in `config/toolkit-revision.txt`.
- Keep the original MIT license and attribution.

The repository and toolkit have been downloaded. Game data is locally extracted
from the user's supplied USA XISO and stays gitignored; it is not distributed.

Local verification completed:
- Toolkit configured with CMake 3.31.6, Visual Studio 2022 generator, x64.
- All default toolkit targets built in Release with MSVC 19.44.35230.0
  and Windows SDK 10.0.26100.0. Existing compiler warnings remain.
- Python 3.12 environment is in the sibling directory `../fbos-venv`.
- Capstone package installed there (`pip` distribution 5.0.9; module reports 5.0.7).
- Preflight passes with explicit tool paths and the locally supplied game data.
- XBE SHA-256: `9295b6e0cc70024392c34f2df8795e5d28c9592b9cda45853549029dd833919c`.
- Generation: 3888/3889 functions, 0 failed, 543025 C lines, one unresolved stub.
- Game Release x64 build passed with Visual Studio 2022, `FBOS_COMPILE_JOBS=2`.
- A 240-second headless capture using upstream boot_check PAD and MILESTONES
  passed 8/8, including Carbon load and no logged faults/unresolved calls.
- `build/local-baseline/` retains runtime.log, result.json and 23 BMP frames.
- Steady Carbon samples: roughly 15.8-16.3 FPS with occasional frame dumps.
- Intermediate draw-surface captures show a large black wedge; subsequent
  capture of the actual window did not reproduce it. See the investigation below.
- Audio underruns are logged; audio playback has not been assessed by listening.
- Later tests cover movement, inventory, saving/loading and the Bar transition;
  see `docs/playtesting.md` for exact scope. Co-op remains untested.

## Completed-frame investigation (2026-11-18)

The executor's `RECOMP_FB_DUMP` is a draw-surface dump, often taken at a report
mid-frame. In Carbon it can be a 1278x448 AA render surface without the final
HUD/composite. Treating that image as the displayed frame was misleading.

A 190-second unmodified run with the GDI window and its existing dump path
produced 51 window images. Selected Carbon frames at 126, 148 and 189 seconds
showed the correct 640x480 composition; the earlier black wedge did not appear.
Three complete GPU frames were traced at 125, 160 and 180 seconds. This does
not establish that the upstream camera bug cannot occur elsewhere.

The toolkit now provides opt-in `RECOMP_FB_PRESENT_DUMP` capture from the same
finished, converted copy sent to the window. It also runs without a window.
The change does not alter geometry, shaders, camera, game logic or renderer
selection. Five standalone presenter regression tests passed (RGB32, RGB565,
2x1 AA, 2x2 AA and disabled capture).

The rebuilt port passed a further 240-second run with 8/8 boot checks and
87 completed display captures. Selected late Carbon captures, including the
last one, show the HUD and no black wedge. There is no automated visual verdict.
Performance remains about 16 FPS, and the movie artifacts/audio underruns remain.
Evidence: `build/graphics-probe/` and `build/present-capture-verified/`.

For a clean dependency checkout, use the patch and instructions under `docs/patches/`.
The current executable includes this capture change. No public fork or upstream
message has been created.

Local preflight command from the repository directory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/check_environment.ps1 -Python '../fbos-venv/Scripts/python.exe' -CMake 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
```

## Preflight

Run `powershell -NoProfile -File tools/check_environment.ps1`.
If tools are outside PATH, supply their executable paths with `-Python`
and `-CMake`. The check does not install tools, extract a disc or run the game.
Exit code 1 means a prerequisite is missing or the toolkit revision differs;
exit code 0 is only a preflight success, not a gameplay test.

The revision file records the baseline; it does not update the dependency
automatically. Keep the toolkit at that revision until a change is reviewed.

## First milestone

The local title entry point now enables `RECOMP_HEAP_RECLAIM` before memory
initialization. Keep this default: the legacy allocator retains freed GPU
palettes until the contiguous arena fills, after which palette writes can
overwrite the controller descriptor. See `docs/playtesting.md` for the captured
writer and the runtime regression evidence. This uses an existing dependency
feature; no generated game code or input exception handler is patched.

1. Supply a USA Xbox disc image or extracted game directory.
2. Verify the executable identity before generating C. Addresses and seeds
   are specific to the supported build.
3. Generate and compile the existing code before modifying game behavior.
4. Reproduce the boot check and manually test movement, combat and saving.
5. Profile the same scene before choosing a performance change. Record
   hardware, settings, frame rate and observed failures for comparisons.

The upstream `Setup.cmd` is interactive and may offer software installations.
It also skips rebuilding when `bin/fbos.exe` exists. For development, use
the explicit generation/build commands in README instead of treating Setup
as an incremental build tool.
