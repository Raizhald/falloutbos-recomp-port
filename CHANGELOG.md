# Changelog

All notable changes to this project are documented here. Format: [Keep a
Changelog](https://keepachangelog.com/en/1.1.0/); versions follow SemVer.

## [Unreleased]

### Added (player-facing, November 2026)
- One-click `Setup.cmd` (also takes an unpacked game folder, makes desktop
  shortcuts) and `Update.cmd`; `Settings.cmd` options window.
- Direct3D 11 renderer: up to 4x resolution, v-sync, full screen.
- Widescreen 16:9 / 16:10 / 21:9 (Hor+, wider culling).
- Texture filtering: mipmaps, bicubic.
- Mouse and keyboard with mouse aim and a sight, keys in `mkb.ini`.
- Player silhouette behind walls.
- Fixed: Bink video artifacts (lifter: `movsx` of `bp`/`sp`).
- Fixed: the controller is on the console's port 1 (was port 3); a level
  started directly no longer stops at "Please reconnect the controller".
- README rewritten for players; developer notes moved to `docs/development.md`.
- Faster widescreen: the frame is copied back to guest memory without
  waiting for the GPU (bar 16:9, no v-sync: 45 -> 56 FPS).
- Two-player co-op (experimental): `Players=2` in Settings plugs a second
  controller into the console's port 2; Start New Game > Two Player.
- The console's time zone is the PC's (it was all zeros: daylight time on
  with month-0 dates, suspected in a hang after an autosave).
- Vertex programs run 8 vertices at a time (bit-identical results): bar 16:9
  ~50 -> ~62 FPS, Carbon 16:9 ~76 -> ~84 FPS without a frame limit.

### Earlier

### Added
- Project from the xboxrecomp new-game template and the Half-Life 2 port's
  layout: `regen.sh`, CMake, `main.c`, netlab recipe `falloutbos-recomp`.
- Boots to the main menu with no arguments: Interplay logo, intro FMV, menu
  over `Main_Menu.bik`. 0 faults, 0 unresolved indirect calls in 150 s.
- GPU fence mirror for the D3D device at `0x000B5E58`.
- `RECOMP_AC97_READY` on by default, so DirectSound initialises.
- Deferred file I/O APCs turned on (needs xboxrecomp `fix/io-apc-delivery`).
- Native override of Bink's MMX probe `sub_000A4E60` (until xboxrecomp #186).
- Seeds: `0x00095408` (main thread entry), `0x000D845C` (XPP table entry).
- `docs/boot.md`: each wall on the way to the menu and how it was found.
- Controller: `RECOMP_USB` on by default, and the window pages that alias the
  image are claimed so the OHCI model resolves the driver's descriptors. The
  pad enumerates; scripted presses reach the first level, Carbon.
- Seed `0x0002F110` (a virtual method reached in Carbon).
- `FBOS_PROFILE=<start>,<secs>`: a sampling profiler in `main.c`, per thread.
  It found the 5 fps: the pushbuffer executor rasterised every small triangle
  itself while the worker pool slept (fixed in xboxrecomp #228, 15 fps).
- Carbon at ~17 fps on the toolkit branch `work/falloutbos`, which now also
  carries xboxrecomp #230 (no per-kick trace line) and #231 (rasteriser
  pipelined behind the executor).
- README: `RECOMP_RASTER_THREADS` and what it does on a 12-thread CPU.

- Quick start: `Setup.cmd` (prerequisites, asks before installing, disc,
  regen, build) and `Play.cmd` (window, pad or keyboard).
- `tools/boot_check.py`: boot conformance, 8 milestones logo-to-Carbon, against
  a baseline; netlab QA step.
- Dialogue text confirmed drawing in Carbon (the empty box earlier was a
  capture mid fade-in).

### Changed
- The profiler samples about 35 times faster (raw addresses, named at the
  end; thread list refreshed once a second).

### Fixed
- `regen.sh` resolves `TRACE_FUNCS` to an absolute path; the toolkit runs from
  its own directory and could not find a relative one.
