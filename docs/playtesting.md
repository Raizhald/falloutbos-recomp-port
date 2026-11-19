# Functional testing (2026-11-18)

Use `tools/playtest_session.py` with the local Python environment. It runs the
port without a window, writes completed-frame captures, accepts live controller
commands in the capture directory's `live.txt`, and uses isolated UDATA/TDATA.
Audio is muted by default. Creating `stop.flag` ends the owned game process;
the manifest distinguishes that action from a crash. `--seconds N` sets the
duration limit. An AV/fault, unresolved call or exhausted contiguous arena
produces a failing script exit code. A combat case also requires BAR.ddf
to have loaded; merely surviving in Town Center is not a successful combat test.

Each `--name` must be new. `--load --save-root <existing root>` selects Load Game
from the frontend, after which storage/slot selection is driven live. `--combat`
uses a fresh Nadia and the direct path from the starting position to Ruby.
`--combat-repro` is a candidate timed scenario. Verify its actual GUI phases and
BAR.ddf before interpreting its outcome; conversation text can require another
acknowledgement. Longer button holds and releases are needed for reliable menu
edges at the current frame rate.

Live input format is the toolkit's own: one command per line, e.g. `lup:2000`,
`rright:1500`, `back:700`, `x:700`, `rt+a:6000`. Commands for a pad are serialized
with a 200 ms release between them. Inputs and their execution times are logged.

## Evidence so far

- `build/gameplay-session/`: 623-second run; movement, camera rotation,
  map switching, inventory and pistol equipment. Saved a Town Center position
  via the console. fobos.sav is 334596 bytes, fobos.hdr is 96 bytes; all files
  were hashed. Moving away and loading restored the console position and gear.
  No FAULT, EXCEPTION or unresolved-call log entries.
- `build/gameplay-cold-load/`: a new game process loaded the same position,
  restored the console scene, pistol and 20 rounds. Save hashes remained
  unchanged. No FAULT, EXCEPTION or unresolved calls in 863 seconds.
- `build/gameplay-combat/`: Ruby dialogue/options and Bar transition worked.
  Equipped Home-Made Pistol (20 rounds); after movement and `rt+a:6000`, the last
  completed frame showed 18 rounds. The process then exited with 0xC0000005.
  This is a failing gameplay test, not proof that enemy damage or full combat works.
- Later runs with the texture build (SHA-256 `c0a6c877…5f38f5`), all ended via
  `stop.flag` with no FAULT, EXCEPTION, unresolved call or allocation failure:
  - `build/combat-melee-01/` (542 s, Normal): Bar loaded, Iron Gloves equipped,
    repeated `rt+a` melee.
  - `build/combat-line-of-sight-01/` (650 s, Normal): with Damage Text on,
    `open-burst-09.bmp` shows a 10-point hit on a raider; `raider-on-floor.png`
    shows the raider down and `loot-one-cap.png` one cap picked up. This is the
    first confirmed player kill. The whole Bar fight is still unverified.
  - `build/combat-pansy-01/` (1000 s, Pansy, `--easy --bar-ready --bar-fight`):
    firing in the Bar; no kill captured (character screen shows 0 XP, 0 caps).
  - `build/combat-bar-full-01/` (674 s, Normal, `--bar-ready`, live input):
    pistol hits, then Experience 45 and quest "Bar raiders remaining: 7";
    Iron Gloves (Back, up, A) melee hits 2-10. Nadia then died (death menu,
    `death-menu.bmp`); no save existed. No FAULT/EXCEPTION/allocation failure.
    The quest counter on the Quests page is the progress metric for the fight.

The fault report names `sub_000D944C+0x173`, with a read at guest 0x87FCD0B4.
The input routine takes handle 0x80000289, reads a descriptor at handle+0xA3,
and tests descriptor+0x28. At the fault that descriptor is 0x87FCD08C; in live
pre-shot inspection it was 0x000D82EC. The invalid read is localized, but the
origin was subsequently captured with a Windows hardware write breakpoint
in `build/combat-repro-muted-02/watchpoint.json`: host RIP after the store
0x1402EF615, inside `sub_00084710`, wrote palette color 0x01514432 over guest
0x8000032C. The palette upload loop at guest 0x84880..0x84952 uses the pointer
returned by `sub_000A9E70` (palette lock). That routine reads the palette's
physical data address and ORs 0x80000000 into it. After allocation failure,
physical zero therefore aliases XPP's reserved first page.

The original failing run logged 21 contiguous allocation failures and zero
frees. The longer muted reproduction logged 9118 allocation failures and zero
frees. The dependency deliberately keeps freed contiguous blocks in its legacy
default mode; its `RECOMP_HEAP_RECLAIM` mode actually returns them and also fixes
heap splitting/coalescing. `src/game/main.c` now enables that existing mode
before memory initialization for this title, including direct exe launches.
The invalid input read and original palette code are left intact.

The dependency's four `memory_regressions` CTests pass on Windows x64 Release,
including the contiguous block reuse check in reclaim mode. Runtime validation
is recorded below after the corrected build completes its gameplay test.

There is also a visible geometry artifact behind the in-game Load Game menu
after moving away from the console. It was captured through the completed-frame
path; it is distinct from the old misleading intermediate-surface screenshots.
Occluding roofs/objects were observed while traversing town. No renderer change
has been made in response yet.

## Corrected-build validation

`build/combat-reclaim-01` ran 309.94 seconds with reclaim explicitly enabled:
BAR loaded, pistol fired, no faults/unresolved calls/allocation failures, and
no corrupting write caught by the hardware watchpoint.

`build/combat-memory-fixed` ran 600.17 seconds using
the rebuilt exe's default memory mode (no environment override). BAR loaded;
the timed script fired and repeatedly opened/closed inventory. All nine log
checks passed, with zero contiguous allocation failures and 31440 KB peak
reported usage. The 570.00-second hardware watch kept
the descriptor at 0x000D82EC and caught no corrupting writes. The harness ended
the owned process intentionally at its time limit.

Enemies damaged and eventually killed the character normally. After death,
the timed stress commands reached the load menus rather than inventory.
For the remaining session, the known-good Town Center save was copied into
this case's isolated UDATA and loaded live. The original save directory was
not modified. Frame 0447 confirms the console position, full health and
20 rounds restored; the log confirms fobos.sav opened. Subsequent timed
inventory cycles therefore ran in Town Center, not continuously in Bar.

Exe SHA-256: `2fa480732d3d6b8e7dccca2fe7827798cd0be38c283e828c364335c9891c1cf3`.
The user-facing report and compact results are under the workspace outputs.

## Guard-band clipping (2026-11-18, late)

`raster_xf_clipped` now clips to a 1024-pixel band around the clip rectangle
after the near plane, in clip space. Vertices just in front of the eye used to
reach screen coordinates of 1e9..1e17, where the float edge functions lose the
pixel centre entirely. Regression test: `deps/xboxrecomp/tests/nv2a_guard_band`
(old code: 1536/1440/16384 wrong pixels in its three cases, new: 0). The
`perf-guard-band` run (same benchmark as `perf-texture-2-combat-fixed`)
measured 21.58 FPS against 20.98, all checks passing; the logged coordinate
range is now x -1024..2302. Whether specific visible artifacts disappeared is
not yet shown frame-for-frame.

## Raster speed-up (2026-11-18, late)

Bit-identical changes in `nv2a_combiner.c` (`read_rgb` maps once per input,
dot products and output scale/bias once per stage, `nv2a_rc_unpack` by table)
and `wrap_coord` (mask for power-of-two sizes). Same-session A/B with
`benchmark_runtime.py`: `perf-raster-opt` 24.58 FPS (with `--combat-after`,
no faults) against `perf-raster-before` 21.50 FPS, +14.3 %.

## Bilinear quad fetch (2026-11-18, late)

`sample_quad` fetches the four bilinear texels of P8/A8R8G8B8/X8R8G8B8
swizzled textures at once (bit-identical to four `sample_tex` calls).
A/B: `perf-texture-quad` 25.41 FPS vs `perf-texture-quad-before` 24.76 FPS.

## Texel address split and floor_i32 (2026-11-18, late)

Bit-identical. A/B: `perf-texel-path` 25.32 FPS / 9.92 cores vs
`perf-texel-path-before` 26.17 FPS / 10.43 cores. The same exe measured 25.41
and 26.17 FPS in two runs, so single-run noise is about 3 %: this change and
the quad fetch (+2.6 %) are within noise. Use repeated, alternating A/B runs
for small changes.

## Raster pipeline: where the executor waits (2026-11-19)

`[PIPE]` lines in `runtime.log` (every report, ~10 s) give jobs, ring-full
waits, drains by cause and worker idle time; `RECOMP_PIPE_JOBS=<2..64>` sets
the job ring (default now 32, was 8).

Ring A/B, same exe, alternating (`build/perf-ring*`): 8 -> 26.20 / 25.80 FPS,
32 -> 26.43, 64 -> 26.51 / 26.54. A larger ring removes the ring-full waits
(~1.3 s per 10 s with 8) but the time moves into drains: about 3,000 drains
per 10 s (~11 per frame), the executor waiting ~5 s of every 10, workers ~50 %
idle.

Drains by cause (`build/perf-drain-why`, per 10 s): `0:0200` surface setup
~1,070; `5:0310` D3D KickOff marker ~700; end of pushbuffer scan ~720;
`0:0100` NOP ~270; `0:1D90` clear ~270.

- Surface setup: jobs carry their own surface/clip/pitch/textures and worker
  k owns rows y % n == k of every surface, so a switch needs no drain by
  itself. `pipe_check_hazards` drains only if a job samples (texture or
  palette) a surface still being drawn, or draws over a differently laid out
  overlapping surface; `zbuf_current` drains before recycling a depth
  buffer. `RECOMP_SURFACE_DRAIN=1` restores the old drain, `=unsafe` turns
  both off (tests only). Test: `tests/nv2a_surface_hazard` (render A, sample
  it upside down into B): default and `=1` 0 wrong pixels with 4 and 16
  workers, `=unsafe` 32,768 / 30,645 wrong -- the test sees the race.
- KickOff marker and scan end: these tell D3D the GPU consumed the commands;
  after that the title may rewrite textures the workers read lazily. Left
  draining on purpose.
