# Fallout: Brotherhood of Steel - PC port

Fallout: Brotherhood of Steel (Xbox, 2004) running natively on Windows.
The game never had a PC version; this is a static recompilation of the Xbox
original, with no emulator, built on [xboxrecomp](https://github.com/Raizhald/xboxrecomp-port).

![Carbon in 16:9](docs/images/carbon-widescreen.jpg)

**You need your own copy of the game** (the USA Xbox disc image, `.iso`).
Nothing from the game is included here: the setup builds the port from your disc.

## How to play

1. **Download** this repository: green **Code** button, **Download ZIP**, and unpack it
   (or `git clone https://github.com/Raizhald/falloutbos-recomp-port`).
2. **Run `Setup.cmd`.** It checks what is needed (Python, Git, CMake, Visual Studio
   C++ build tools) and asks before installing anything. Then it asks for your
   disc image, builds the game and can put shortcuts on the desktop.
   The first run takes about 15-30 minutes; running it again continues where it stopped.
3. **Run `Play.cmd`** (or the desktop shortcut). **`Settings.cmd`** changes the options.

Later, **`Update.cmd`** fetches the newest version and rebuilds it. Your game
files, settings and saves are kept.

Requirements: Windows 10/11 64-bit, a graphics card with Direct3D 11, about 8 GB of disk
space (most of it the C++ build tools).

## Controls

An Xbox controller (XInput) works as on the console. Mouse and keyboard:

| | |
|---|---|
| Move | W A S D (Shift: walk) |
| Aim | mouse - the character turns toward the sight |
| Attack | left mouse button |
| Lock on target | right mouse button (hold) |
| Special attack | F or side mouse button |
| Jump / dodge | Space |
| Talk / open | E |
| Stimpak | Q |
| Next / previous weapon | mouse wheel or R |
| Crouch | C or Ctrl |
| Turn camera | hold middle mouse button and move, or Z / X |
| Map mode | M / N |
| Inventory | Tab or I |
| Pause | Esc |
| Menus | arrows, Enter, Backspace |
| Free the mouse | F9 |
| Full screen | F11 or Alt+Enter |

Holding attack keeps attacking, on the mouse and on a controller (`autofire` and
`autofire_rate` in `mkb.ini`). Keys can be changed in `mkb.ini`.

**Two players (co-op, experimental).** Set **Players** to 2 in `Settings.cmd`,
plug in two Xbox controllers, then choose Start New Game > Two Player. The
first controller is player 1, the second is player 2 (it presses A to pick
its character). Mouse and keyboard stay with player 1.

## Settings

![Character select](docs/images/character-select.jpg)

`Settings.cmd` opens a small window:

- **Renderer** - graphics card (Direct3D 11, default) or software
- **Resolution** - 1x to 4x the original 480 lines
- **Texture filtering** - original, smooth or best (bicubic)
- **Aspect ratio** - 4:3 (original), 16:9, 16:10, 21:9 (widescreen is experimental:
  indoors and in conversations the sides can stay black)
- **Silhouette** - the player shows through walls
- **Players** - 1, or 2 for co-op with two Xbox controllers
- **Display mode, window size, frame rate limit, v-sync, controls, mute**

## What has been done

Compared with the Xbox original:

- **Graphics card renderer** (Direct3D 11) with higher resolutions, v-sync and full screen
- **Widescreen** 16:9 / 16:10 / 21:9 (experimental)
- **Texture filtering** - mipmaps and bicubic smoothing
- **Mouse and keyboard** - aiming with the mouse, rebindable keys
- **Player silhouette** behind walls
- Fixed: broken pixels in the videos, crashes and stalls found while testing

![Player behind a post](docs/images/silhouette.jpg)

## Status

Early access. Played by hand from the start through Carbon and the raiders'
warehouse; saving and loading work. All 53 levels of the game load and draw
without errors in an automated tour, but the game has not been played through
to the end yet.

Known problems:

- Widescreen is experimental: indoors and in conversations the sides can stay black.
- One crash on entering the warehouse (once; it did not happen again).
- On a laptop, set Windows to **Best performance** (Settings > System > Power) and
  keep it plugged in: the game draws on the processor, and power saving halves
  the frame rate.

Found a bug? Open an Issue with what you were doing and attach `logs\last-run.log`
(every run writes it; the run before is `logs\previous-run.log`).

For developers (building by hand, debugging switches, how it works):
[docs/development.md](docs/development.md).

## License

MIT, see [LICENSE](LICENSE). It covers the code in this repository only.
Fallout: Brotherhood of Steel and its data belong to their owners; nothing from the
game is in this repository.
