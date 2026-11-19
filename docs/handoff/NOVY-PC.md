# Pokračování na jiném počítači

Stav k 19. 11. 2026 15:00. Všechen kód je ve dvou soukromých repozitářích:

| Repozitář | Co obsahuje |
|---|---|
| `Raizhald/falloutbos-recomp-port` | projekt hry (sestavení, nástroje, patche, tyto dokumenty) |
| `Raizhald/xboxrecomp-port` | runtime / toolkit včetně GPU back endu a dnešních oprav |

Na GitHubu **nejsou** (a nesmí být): herní data z disku, vygenerované C
(`src/game/recomp/gen`), sestavené `bin/fbos.exe`, pozice ve hře (`saves/`).
Tyto věci se na novém PC vytvoří znovu z tvého vlastního ISO.

## Co potřebuješ

- Windows 10/11 x64, grafická karta s Direct3D 11.
- Obraz disku `Fallout - Brotherhood of Steel (USA).xiso.iso`
  (na starém PC v `C:\Users\sesta\Downloads\Fallout - Brotherhood of Steel (USA)\`).
  Ověření: `game/default.xbe` po rozbalení má SHA-256
  `9295b6e0cc70024392c34f2df8795e5d28c9592b9cda45853549029dd833919c`.
- Git, Python 3 (`py`), Visual Studio 2022 Build Tools (C++), CMake.
  `Setup.cmd` chybějící věci nabídne doinstalovat přes winget.

## Postup (v tomto pořadí)

```bat
cd %USERPROFILE%\Documents
git clone https://github.com/Raizhald/falloutbos-recomp-port falloutbos
git clone https://github.com/Raizhald/xboxrecomp-port falloutbos\deps\xboxrecomp
cd falloutbos
Setup.cmd
```

**Důležité:** toolkit naklonuj do `deps\xboxrecomp` **dřív**, než spustíš
`Setup.cmd`. Jinak si Setup stáhne původní upstream (sp00nznet) bez
dnešních změn (GPU back end, oprava pushbufferu, zvuk, rychlejší renderer).

`Setup.cmd` se zeptá na ISO (najde ho sám v `Downloads`), rozbalí ho do
`game\`, vygeneruje C (~3 min) a sestaví hru (několik minut).

## Hraní

- `PlayGPU.cmd` -- grafická karta, zámek 60 FPS (doporučeno).
- `Play.cmd` -- původní softwarové vykreslování (~36 FPS), záloha.
- Ovládání: WASD pohyb, IJKL druhá páčka, Z/X/C/V = A/B/X/Y, Enter = Start,
  Backspace = inventář, 1/3 = spouště. Funguje i Xbox ovladač.

## Pro nový chat s Claudem

Připoj v Claude desktop aplikaci na novém PC složku projektu (tlačítko
„Add folder“), a napiš:

> Pokračuj na Xbox portu Fallout: Brotherhood of Steel. Projekt je v
> `<cesta>\falloutbos`, toolkit v `deps\xboxrecomp`. Nejdřív si přečti
> `docs\handoff\predani-projektu.md` (nahoře je nejnovější stav) a
> `docs\handoff\NOVY-PC.md`. Testy spouštěj ztišené. Zálohy jdou do mých
> repozitářů Raizhald/falloutbos-recomp-port a Raizhald/xboxrecomp-port.

Tip: Claude na Windows nemůže psát do terminálu. Na starém PC proto běžela
„fronta“: okno, které spouští `.cmd` skripty, jež Claude uloží do
`build\queue`. Spusť ji na novém PC jednou ručně, ať může překládat a
měřit sám. Skript je níže (uložit jako `Fronta.cmd` do složky projektu):

```bat
@echo off
setlocal enabledelayedexpansion
title Fallout port - fronta (zavrenim okna se fronta ukonci)
cd /d "%~dp0"
if not exist build\queue\done mkdir build\queue\done
:loop
echo %date% %time% > build\queue\alive.txt
for %%f in (build\queue\*.cmd) do (
  set "JOB=%%~nxf"
  echo [!date! !time!] start !JOB! >> build\queue\queue.log
  move /y "%%f" "build\queue\done\!JOB!" >nul
  call "build\queue\done\!JOB!"
  echo [!date! !time!] end !JOB! exit !errorlevel! >> build\queue\queue.log
  cd /d "%~dp0"
)
timeout /t 15 /nobreak >nul
goto loop
```

Benchmark potřebuje Python venv s balíčkem capstone: na starém PC byl v
`..\fbos-venv` (vedle složky projektu). Vytvoření:
`py -3 -m venv ..\fbos-venv` a `..\fbos-venv\Scripts\pip install capstone`.

## Co dál (podle priority)

1. Jedním testovacím během ověřit, zda oprava pushbufferu neodstranila i
   překrývání postavy geometrií a černé „kostičky“ na budovách v Carbonu.
2. Dohrát první boj v baru (všech ~8 nájezdníků), pak další úrovně.
3. Zobrazovat obraz přímo z GPU (dnes se kopíruje zpět do paměti a kreslí
   přes GDI okno, ~2-4 ms/snímek); celá obrazovka, vsync.
4. Mipmapy, stencil, culling, cube mapy podle toho, co hra používá.
5. Zkontrolovat bílé tečky v intru, poslechnout zvuk, kooperaci pro 2 hráče.
6. Případně překlad do češtiny (zatím jen průzkum).

Podrobnosti, měření a seznam všech proměnných prostředí jsou v
`predani-projektu.md`.
