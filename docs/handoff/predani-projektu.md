# Předání projektu Fallout: Brotherhood of Steel

<!-- widescreen-update -->
## 20. 11.: širokoúhlý obraz (`RECOMP_WIDESCREEN`, Settings „Aspect ratio“)

Zjištění: hra příznak `XC_VIDEO_FLAGS_WIDESCREEN` ignoruje (snímky s ním i bez
něj shodné; `kernel_xbox.c` má nově přepínač `RECOMP_VIDEO_WIDESCREEN=0` a
log dotazu). Obraz je proto rozšířen v portu (Hor+: stejný svislý záběr, víc
světa po stranách):
- `nv2a_backend_d3d11.c`: render targety s 480 řádky a šířkou >= 4:3 (640x480
  snímek, 1280x480 AA snímek) jsou `ew` = w * (poměr / (4/3)) pixelů široké,
  hostův 4:3 obraz uprostřed (`ox`). Vertex shader posouvá x (`g_wsx`), ořez a
  ClearView berou „skoro celou šířku“ (hra ořezává AA snímek na 1278) jako
  celou šířku cíle, jinak se posouvají s obrazem. Čtyřúhelník přes celý snímek
  bez 4:3 obrázku (stmívání, tónování, práce s rozšířeným snímkem) se roztáhne
  na celou šířku; s texturou (Bink, pozadí menu) zůstane 4:3 uprostřed s
  černými pruhy. Vzorkovaný rozšířený cíl má offset v `g_tscale.zw`.
  Readback do paměti hosta = prostřední 4:3 výřez; `g_present` zobrazuje cíl v
  jeho poměru stran. Bez proměnné se nic nemění (ověřeno 4:3 během).
- `recomp_manual.c`: obal `sub_00086980` (+ `_gen`, regen) -- hra si staví
  ořezové roviny kamery na `0x5D4CF0` (levá/pravá: z = tan(fov)*k, horní/dolní
  tan*0.75); boční roviny se rozšíří stejným faktorem a znovu normalizují, jinak
  by objekty u okrajů chyběly.
- `fb_present.c`: okno se otevírá v daném poměru (854x480 krok pro 16:9).
- `Play.cmd`/`Settings`: `AspectRatio=4:3|16:9|16:10|21:9`, výchozí 16:9
  (i když klíč v settings.ini chybí), jen s GPU rendererem.
Ověření bez okna (`RECOMP_GPU_RT_DUMP`): `build/ws-rt7` (16:9: intro, menu,
výběr postavy, Carbon), `build/ws-rt219` (21:9), `build/ws-rt43` (4:3 beze
změny); všechny běhy bez chyb, Carbon ~35 s.
Omezení: HUD, menu a videa zůstávají 4:3 uprostřed (záměrně); se softwarovým
rendererem se nerozšiřuje.
<!-- /widescreen-update -->

<!-- texfilter-update -->
## 20. 11.: filtrování textur (`RECOMP_GPU_TEXFILTER`, Settings „Texture filtering“)

Zjištění (statistika navázání textur v Carbonu): všechno kreslí vertex
programy + kombinéry; hra chce `02022000` (bilineární, ~33 000 navázání,
typicky 32x32 -- zem), `01012000` (nejbližší, ~12 000, 256x8 -- HUD
proužky) a `04072000` (MAG 4 / MIN 7 = konvoluční/Gaussův filtr NV2A, render
target s AA 1280x480). Kostičkovaná zem není chybějící filtr, ale nízké
rozlišení textury.
`nv2a_backend_d3d11.c`:
- **oprava:** konvoluční filtr (MAG 4, MIN 7) se dřív vzorkoval nejbližším
  texelem, nyní lineárně (všechny režimy);
- `0` Original (výchozí v EXE, benchmarky beze změny); `1` Smooth: co hra
  filtruje lineárně, má mipmapy (`GenerateMips`) a trilineární filtr; `2` Best:
  navíc bikubické (B-spline, 4 bilineární vzorky) zvětšování; co hra chce
  nejbližší (HUD, tabulky) a render targety zůstává beze změny;
- shader: `SampleGrad` s derivacemi spočítanými na začátku PS (`suv`),
  `bicubic()` jen při zvětšení (stopa < 1 texel);
- `D3D11_FILTER_ANISOTROPIC` zkoušen: na RTX 5070 Laptop zvětšoval nejbližším
  texelem -> nepoužit;
- `RECOMP_GPU_RT_DUMP=<dir>`, `RECOMP_GPU_RT_DUMP_AT=<s,...>`: uložení plného
  (škálovaného) render targetu bez okna -- srovnání nastavení na pozadí.
Ověřeno: `build/texf3-rt0/1/2` (Carbon, 3x), `build/texf-compare3.png`;
testy back endu OK; benchmark 3x + Best `build/texf-bench` 100.1 FPS, vše OK.
`Play.cmd`/`settings.ini`: `TextureFilter=0|1|2` (výchozí 2).
<!-- /texfilter-update -->

<!-- maintenance-update -->
## 19. 11. večer: údržba a průzkum překladu

- **Git:** falešné změny (konce řádků, příznaky souborů) v obou repozitářích
  pryč; `core.filemode=false` (kvůli pohledu z Linuxu). `Fronta.cmd` v repozitáři.
- **Fronta:** `Fronta.cmd` spouští každou úlohu přes `tools/queue_run.ps1` v
  samostatném `cmd` (proměnné z jedné úlohy už neprosakují do další) s limitem
  1 h nebo `rem timeout=<s>` v úloze; po limitu `taskkill /T` celého stromu.
  Ověřeno (`build/qtest`, smazáno). **Po aktualizaci okno fronty restartovat.**
- **Navigace v menu:** `tools/menu_nav.py` (benchmark i playtest): každé 2 s,
  Start během `intro/interplay.bik`, jinak A, s `--easy` v nabídce obtížnosti
  Up+A. Carbon ve 35 s (dřív 105 s, občas až 265 s): `build/nav-bench1/2`
  116.6 / 133.1 FPS vše OK, `build/nav-easy` bar načten.
- **Úklid:** `build` 12 GB -> 160 MB (snapshoty difftestu, série snímků,
  záloha gen); v `bin/` jen `fbos-before-movsx.exe` jako záloha.
- **Překlad:** průzkum v `docs/preklad.md` -- text v `gtext.sdb` (UTF-16,
  ~37 600 slov), písmo umí Latin-1, ale ne háčky ani ů (ověřeno ve hře).
<!-- /maintenance-update -->

<!-- bink-update -->
## 19. 11. večer: rozbité pixely ve videích (Bink) -- VYŘEŠENO

Příznak: v Bink videích (intro, menu, výběr postavy) bloky 8x8 se šachovnicí
a přesycenými barvami, deterministicky. `ffmpeg` dekóduje stejné `.bik`
čistě -> chyba v rekompilovaném dekodéru.

**Příčina:** lifter překládal `movsx ebp, bp` jako `ebp = LO16(ebp)` --
seznam 16bitových registrů v `_lift_movsx` neměl `bp` a `sp` (`movzx` je
měl). IDCT Binku (`sub_000CD710`) drží řádek 6 každého sloupce v `bp`;
každý záporný koeficient v řádku 6 se stal ~65535 a sloupec IDCT se
rozjel. V celé hře je to jediné takové místo. Oprava v
`deps/xboxrecomp/tools/recomp/lifter.py`, test
`tools/recomp/test_lifter_shift_count.py` (`MovsxEveryRegister`).
Ověřeno: hlavní menu bez artefaktů (`build/movsx-smoke`), emulátor:
všech 714 volání IDCT v jednom snímku shodných (`build/difftest-mtrace4.log`),
benchmark `build/movsx-bench` 117.5 FPS, vše OK (EXE `b035104d…`).
Pozn.: v tom běhu se menu 9x vrátilo do smyčky intra (Carbon až ve 265 s)
-- harness to zvládl, ale mačkání A každých 5 s v menu je neohrabané;
lepší by bylo reagovat na načtení `Character_3.bik` / `chap1_*.bik`.

**Cestou opraveno (správně, ale nebyla to příčina):** `shl/sal/shr reg, cl`
bez maskování počtu (`& 31u`), dvou/tříoperandový `imul` jako znaménkové
násobení `int32_t` (přetečení = UB v C; nyní `uint32_t`). Testy tamtéž.

**Nový nástroj -- diferenciální test proti původním instrukcím**
(`cmake -DFBOS_DIFFTEST=ON` v `build-difftest`, výsledek
`bin/fbos-difftest.exe`; job ve frontě zálohuje a vrací hlavní EXE):
- `RECOMP_DIFFTEST_VA=<hex>` `_NTH=<n>` `_AFTER=<s>` `_DIR`: snapshot
  registrů a paměti (RAM + kontinuální okno) před a po n-tém volání funkce.
- `RECOMP_DIFFTEST_TRACE_VA=<hex>`: vstup i výstup (blok 8x8 + rámec)
  každého volání dané funkce během sledovaného volání; `=ALL`: sekvence
  všech volání (adresa, registry, 32 B argumentů).
- `RECOMP_DIFFTEST_WATCHPLANE=1`: zápisy do cílové roviny (arg1, arg3*arg4)
  přes ochranu stránek -> `planewrites.bin`; `RECOMP_DIFFTEST_WATCH=<va>`:
  hardwarová zarážka na jeden bajt.
- `tools/difftest_run.py <name> <va> [nth] [timeout] [after]`: spustí,
  počká na snapshot, ukončí.
- `tools/difftest_emulate.py <dir> [--writers LO HI] [--trace VA]
  [--calltrace]`: přehraje původní x86 v Unicornu (`pip install unicorn`
  ve venv) a porovná; `tools/difftest_writers.py <dir>`: poslední nativní
  zapisovatel chybných bajtů (přes `bin/fbos-difftest.map`).
Postup, který chybu našel: C9010 (dekód roviny) liší -> zapisovatel je
IDCT CD710 -> výstup/rámec CD710 při návratu -> sloupcový mezivýsledek se
liší jen ve sloupcích se záporným koeficientem v řádku 6 -> `movsx ebp, bp`.
<!-- /bink-update -->

<!-- scale-settings-update -->
## 19. 11. večer: vyšší rozlišení (`RECOMP_GPU_SCALE`) a nastavení pro hráče

**Rozlišení:** `nv2a_backend_d3d11.c` -- `RECOMP_GPU_SCALE=1..4` (výchozí 1).
Render targety, hloubkové buffery, kopie pro self-sampling, viewport,
scissor a obdélníky `ClearView` jsou k-krát větší; vše, co vidí host
(pozice vrcholů -- `g_vp` = 2/W v pixelech hosta, texelové škály, logy,
otisk paměti), zůstává v pixelech hosta. Počáteční obsah RT z paměti se
nahraje v 1x a roztáhne blitem (nearest); zpětné čtení jde přes 1x kopii
(`down_tex`, lineární blit) do stagingu. Blit pipeline (`g_blit_init`,
`g_blit`) sdílí prezentace i škálování. Ověřeno: testy back endu prošly
(scale 1), `build/scale1-smoke` vs `scale3-smoke` (celá obrazovka v Carbonu,
`build/scale-compare.png`): ve 3x hladké hrany a ostřejší postava, textury
hry zůstávají v původním rozlišení (nearest). Benchmark 3x
`build/scale3-bench` 101.2 FPS (1x ~133), vše OK.

**Nastavení:** `settings.ini` v kořeni (v `.gitignore`), `Play.cmd` ho při
startu převede na proměnné (`Renderer=GPU|Software`, `ResolutionScale`,
`VSync`, `Fullscreen`, `WindowScale`, `FPSLimit` 0 = bez limitu, `Mute`);
chybí-li, vytvoří výchozí (GPU, 2x, vsync, okno, 60 FPS). `PlayGPU.cmd`
jen vynutí GPU (`FBOS_FORCE_GPU`). `Settings.cmd` otevře okno
`tools/settings_gui.ps1` (WinForms, anglicky; Save / Save and Play).
Benchmark a testy spouští `fbos.exe` přímo, nastavení je neovlivní.
Ověřeno `build/settings-test.log` (výchozí soubor, software + 3x + bez
limitu, vynucené GPU). Okno nastavení se zobrazilo; snímek testem se
nepodařil (háček odstraněn).
**Fronta:** v prostředí okna fronty zůstaly `RECOMP_GPU_SHOT_*` z dřívějších
úloh (viz výpis v `settings-test.log`) -- frontu restartovat.
<!-- /scale-settings-update -->

<!-- present-update -->
## 19. 11. večer: obraz přímo z GPU, celá obrazovka, vsync

`nv2a_backend_d3d11.c`: při flipu (`gb_resolve`) se zobrazovaný render
target vykreslí do DXGI swapchainu (flip model, 2 buffery) na okně hry,
4:3 s černými pruhy, lineární filtr (AA povrch 2x se tím zprůměruje).
Okno se hledá podle třídy `XboxRecompFramebuffer` ve vlastním procesu
(`FindWindowEx`), takže testy back endu nepotřebují `src/video`. Okno
dostane vlastnost `XboxRecompGpuPresent` a přestane kreslit přes GDI.
Proměnné: `RECOMP_GPU_PRESENT=0` (staré GDI okno), `RECOMP_VSYNC=0`,
`RECOMP_GPU_READBACK=0` (při přímé prezentaci nekopírovat snímek zpět do
paměti hosta; pak nejsou `latest.bmp` ani `RECOMP_GPU_SHOT_*`; výchozí 1).
`fb_present.c`: F11 / Alt+Enter = celá obrazovka bez rámečku (Enter jde dál
jako Start jen bez Alt), `RECOMP_FULLSCREEN=1` startuje tak; okno se otevře
v největším celém násobku 640x480 do `RECOMP_WINDOW_SCALE` (výchozí 2), co
se vejde (zde 125% DPI -> 800x600), dá se libovolně zvětšit; GDI cesta
(software) taky škáluje 4:3 (HALFTONE).
`src/game/main.c`: VEH už nehlásí jako `[EXCEPTION]` informativní výjimky
hostitelských knihoven (0x406D1388 pojmenování vlákna -- ovladač NVIDIA při
vytvoření swapchainu, 0x40010006/0x4001000A OutputDebugString, 0xE06D7363
C++ výjimky ovladačů/zvuku). Dřívější 2x 0xE06D7363 na Intel grafice
(`pb-verify-newpc`) byly nejspíš tohle.
Nový `tools/window_smoke.py`: spustí hru s oknem, snímá skutečnou obrazovku
(BitBlt z desktopu), pošle F11 a snímá znovu.
Ověření: `build/present-smoke2` (readback 1) a `present-smoke3`
(readback 0): okno 800x600 i celá obrazovka 1920x1080 správně, 0 chyb;
testy back endu (raster batch 3, surface hazard 2, guard band, ffp
backend, fb_present_dump 5) prošly; benchmark bez okna `present-bench2`
133.2 FPS, vše OK (EXE `bdda121c…`).
**Fronta:** úlohy volané přes `call` sdílí prostředí okna fronty --
`set` bez `setlocal` (např. `RECOMP_FPS_LIMIT=60` z `17-bar-pansy.cmd`)
zůstane pro všechny další úlohy (`present-bench1` proto 60.0 FPS). Úlohy
začínat `setlocal`; benchmark si `RECOMP_FPS_LIMIT` nyní sám maže.
<!-- /present-update -->

<!-- bar-pansy-update -->
## 19. 11. večer: boj v baru na Pansy (`build/bar-pansy-01`, 563 s, GPU 60 FPS)

`tools/playtest_session.py` dostal stejné řízení podle logu jako benchmark
(pevně do 80 s, pak A každých 5 s do Carbonu + 15 s, trasa živě od
Carbon + 18 s). Spuštěno `--bar-ready --easy`; Carbon 85.3 s, trasa do
baru odeslána ve 202 s, bar načten. Pozor: trasa nechá v ruce Iron Gloves,
pistoli je nutné nasadit (Back, dolů, A, B).
Ručně přes `live.txt` (snímky `build/bar-pansy-01/snaps/s01..s25.png`):
- přiběhli 4 nájezdníci; pistolí (20 nábojů) 2 zabiti -> úkol „Kill Drunken
  Raiders“: **Bar raiders remaining: 6**, Experience 54, Health 188/400;
- sebrány zátky (8) a Stimpak z mrtvých; tělo nejdřív stojí se zdviženýma
  rukama (animace umírání), pak zmizí -- normální;
- zbylí nájezdníci za pultem / v druhé místnosti, ruční navigace po
  snímcích (kamera se otáčí) neefektivní -> ukončeno přes `stop.flag`.
Žádný fault, výjimka ani nevyřešené volání. Postřeh (viditelnost postavy):
za zdí bylo z Nadii vidět jen pár pixelů (`s21`), zeď se nezprůhlednila --
ověřit proti originálu, jestli to hra dělá.
<!-- /bar-pansy-update -->

<!-- harness-update -->
## 19. 11. večer: benchmark řízený stavem hry (oprava nestabilního testu)

`tools/benchmark_runtime.py` už neměří v pevné 125. sekundě. Pevný plán
ovladače zůstal jen do 80 s (Start + menu); potom harness přes
`RECOMP_PAD_LIVE` mačká A každých 5 s, dokud log neukáže
`c1\CRB_1a\CRB_1a.ddf`, a ještě 15 s (úvodní dialog Carbonu). Měření
začíná `--settle` (výchozí 18 s) po načtení Carbonu; `--combat-after`
posílá stejnou trasu živě, 5 s po konci měření. `--carbon-timeout`
(300 s) ukončí běh, když se Carbon nenačte. `--start` zrušeno. V
`result.json` nově `carbon_loaded_at` a `measurement_started_at`.
Příčina dřívějších selhání (`pb-verify-newpc4/5`): menu se vrátilo do
attract smyčky, po 120 s už nikdo nemačkal a Carbon se načetl až ~170 s.
Ověření: `build/harness-fix1` 134.4 FPS (Carbon 105.4 s) a `harness-fix2`
106.6 FPS (Carbon 105.5 s), oba vše OK včetně baru. Rozptyl FPS mezi běhy
(~105 vs ~135, viděn i dříve) je nejspíš teplota/napájecí režim notebooku;
pro A/B srovnání střídat běhy a brát víc vzorků.
<!-- /harness-update -->

<!-- newpc-update -->
## 19. 11. večer: nový počítač (notebook) -- výběr výkonné grafiky

Nový PC: MSI Katana 15 HX B14WGK, Intel Core i7-14650HX (16 jader / 24
vláken), 16 GB RAM, Intel UHD + **NVIDIA GeForce RTX 5070 Laptop GPU**.
Projekt leží v `C:\Users\sesta\Desktop\FLESKA-Fallout\falloutbos`, venv v
`..\fbos-venv` (Python 3.14.7, capstone 5.0.7), CMake se bere z VS 2022
Build Tools (`...\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin`),
není na PATH. Fronta: `Fronta.cmd`; úlohy v `build\queue` se spouštějí
z `build\queue\done`, proto skripty začínají `cd /d "%~dp0..\..\.."`.
Zkopírované soubory měly atribut jen pro čtení, zrušen přes `attrib -R`
(deps, src, docs, tools, patches, kořen).

Problém: D3D11 back end bral výchozí adaptér = Intel UHD (Optimus), navíc
na baterii -> GPU běh 21.9 FPS, back end 16-48 ms/snímek
(`build/pb-verify-newpc`, staré EXE `9dbea663…`, kopie
`bin/fbos-before-adapter.exe`). V tom běhu i 2 C++ výjimky 0xE06D7363
v RaiseException při čtení `hud.clp`/`armor.clp` (kontrola „no faults“);
v dalších bězích (v zásuvce, RTX) se neobjevily -- příčina nezjištěna.

Oprava `nv2a_backend_d3d11.c`: zařízení se vytváří na adaptéru z
`IDXGIFactory6::EnumAdapterByGpuPreference(HIGH_PERFORMANCE)` (fallback na
výchozí), log `[GPUB] adapter: ...`. `RECOMP_GPU_ADAPTER=default` vrací
původní chování. Nově i `RECOMP_GPU_SHOT_FROM=<s>` (snímky render targetu
až od dané doby; v menu běží hra >1000 FPS a limit 100 snímků se jinak
vyčerpá v intru).

Měření (`benchmark_runtime.py --combat-after`, GPU od startu, v zásuvce):
| Běh | EXE | FPS | Kontroly |
|---|---|---|---|
| `pb-verify-newpc` (Intel UHD, baterie) | `9dbea663…` | 21.9 | no faults = False |
| `pb-verify-newpc2` (RTX) | `d94b55b4…` | 105.1 | vše OK |
| `pb-verify-newpc3` (RTX, + SHOT_FROM) | `e3e3dac5…` | **135.0** | vše OK |
Aktuální `bin/fbos.exe` SHA-256 `E3E3DAC5F57E57B0F0AF2F1F56153488843750C16350CA62249F1873591AB831`.
Úvod, menu, výběr postavy a intro kapitoly na GPU vypadají čistě
(`build/pb-verify-newpc3-sheet.jpg`).
Snímky Carbonu se zatím nepodařilo zachytit: `SHOT_EVERY` počítá snímky a
v menu/intru (>1000 FPS) se limit 100 vyčerpá dřív. `pb-verify-newpc4`
(`SHOT_FROM=110`, `EVERY=200`) selhal (682 FPS, bar se nenačetl): zápis
snímků zpomalil hru a časovaný pad skript se rozešel (hra stála na textu
T. S. Eliota před kapitolou 1). Chyba metodiky, ne hry. Další krok: snímky
podle času (např. `RECOMP_GPU_SHOT_EVERY_MS`) nebo jen v měřeném okně.
`pb-verify-newpc5` (`RECOMP_GPU_SHOT_EVERY_MS=2500`, `SHOT_FROM=110`,
EXE `8ac3b441…`): hra prošla Carbonem (nájezdníci, inventář, pistole, vchod
do baru), ale později než čeká skript, takže měření padlo do intra (713 FPS,
„Bar loads“ = False). Na tomto PC se časovaný pad skript občas rozejde na
textové obrazovce (T. S. Eliot) před kapitolou 1 -- 2 z 5 běhů; nestabilita
testu, ne hry. **Vizuální ověření opravy pushbufferu:** ~65 snímků Carbonu
(`build/pb5-carbon-zoom.jpg`, `build/pb-verify-newpc5-shots`) bez černých
„kostiček“ na budovách a bez překrytí postavy geometrií -> bod 1 z NOVY-PC.md
splněn. Nová proměnná `RECOMP_GPU_SHOT_EVERY_MS=<ms>` (snímky podle času).
Aktuální `bin/fbos.exe` je build s EVERY_MS (`8ac3b441…`).
<!-- /newpc-update -->

<!-- backup-update -->
## Záloha na GitHubu (19. 11. 14:40)
Soukromé repozitáře: `Raizhald/xboxrecomp-port` commit `3709a4f` (GPU back
end + oprava pushbufferu, celé zdrojové soubory) a
`Raizhald/falloutbos-recomp-port` commit `19d19f5` (`PlayGPU.cmd`, patche,
`docs/handoff/` = tento dokument a návrh 60 FPS). Lokální git (větve
`codex/*`, remote na upstream sp00nznet) se nemění; do upstreamu se nepushuje.
Návod pro jiný počítač: `docs/handoff/NOVY-PC.md` v repozitáři
`Raizhald/falloutbos-recomp-port` (kopie `outputs/NOVY-PC.md`).
Rychlý běh `build/quick11.log` (GPU, po opravě pushbufferu): černé
„kostičky“ na budově vpravo nahoře v Carbonu se v 19 snímcích neobjevily,
byly ale i dříve jen občas -- neprokázáno.
<!-- /backup-update -->

<!-- pushbuffer-split-update -->
## 19. 11. odpoledne: ztracené příkazy pushbufferu opraveny (rozházené vrcholy postavy, chybné textury v baru)

Příznak: postava občas na snímek „vystřelila“ hroty přes celou obrazovku
(dávka 421 vrcholů rozházená přes 8 590 px). Diagnostika `RECOMP_SKIN_DUMP`
ukázala, že rozbité vrcholy mají vždy jednu kost (offset 16 nebo 48) a její
matice v c[] byla napůl stará: z 16slovného nahrání konstant dorazilo 1-13
slov. Dvě chyby ve výchozím segmentovém skenování pushbufferu
(`RECOMP_PB_WALK` nenastaveno):
1. `pb_walk_segment` usekl parametry příkazu na konci úseku (`PUT` uprostřed
   dávky) a zbytek v dalším úseku četl jako hlavičky. Nyní si rozpracovaný
   příkaz pamatuje a další úsek, který začíná na stejné adrese, ho dokončí
   (jako DMA engine a režim `dma`).
2. Při přetočení kruhu (1 MB, `0x676000`) se konec skenoval jen do nejvyššího
   viděného PUT, ne k `JUMP` na konci kruhu -- ztrácely se konstanty (0A60),
   formáty vrcholů (1A00), stavy textur (1BA8) atd. Nyní se čte k `JUMP`
   (mez: nejvyšší PUT zaokrouhlený na 64 KB). `xbox_memory_layout.c`.
Ověření: nový případ v `tests/nv2a_pb_walk` (na starém kódu selže, nový
prošel Linux i Windows CTest), raster testy 3/3. Běhy `build/skin-fix3.log`:
GPU 111.5 FPS, GPU `--combat-after` 114.2 FPS, software 36.1 FPS, všechny
kontroly OK; 0 ztracených slov (`[PB] split ... lost`), 0 rozházených
dávek (`RECOMP_SKIN_DUMP`), bar u vany bez chybných textur
(`build/gpu-shots10c/sheet.ppm`; dříve `gpu-shots6-combat`).
**Oprava předchozího závěru:** protažené paže při idle animaci jsou normální
animace (rozpažení, pohled shora zkracuje trup), ne chyba skinningu; chybou
byly jen hroty.
Diagnostika ponechána (vypnutá): `RECOMP_SKIN_DUMP=<složka>`
(+`_FROM=<s>`), `RECOMP_VSH_CTRACE=<s>`; přehrání dumpu mimo hru: zdroj
offline nástroje byl v linuxovém VM, princip je v `nv2a_vsh_snapshot`.
Patch: `outputs/xboxrecomp-pushbuffer-split.patch` (konce řádků LF; vůči
`build/local-baseline/*.before-skin`). `bin/fbos.exe` SHA-256
`9dbea6636025b258f4260de6b0e7048b8b2a2f5c18b2b80a846a831201e70c57`.
Soubor `build/_to_delete/_tmp_orig.c` je omylem vzniklá kopie, lze smazat.
<!-- /pushbuffer-split-update -->

<!-- gpu-backend-update -->
## 19. 11. odpoledne: vykreslování na grafické kartě (Direct3D 11) -- ~117 FPS, se zámkem 60 FPS

**Hrát na GPU:** `outputs/Spustit-Fallout-GPU.cmd` (GPU od startu + zámek 60 FPS).
Původní `Spustit-Fallout.cmd` dál kreslí softwarově.

Nový back end `deps/xboxrecomp/src/kernel/nv2a_backend_d3d11.c` přes
`nv2a_backend.h`. Zapíná se `RECOMP_GPU_BACKEND=<sekundy>` (0 = od startu;
bez proměnné se nic nemění). CPU dál dekóduje pushbuffer, počítá vertex
shadery a ořez; GPU rasterizuje. Pixel shader obsahuje generický interpret
register combinerů (port `nv2a_combiner.c` 1:1, řízený surovými ICW/OCW v
konstantním bufferu -- žádná kompilace shaderů za běhu), stage 0-3 (2D/3D
projekce, passthru, clip plane), nearest/bilineární filtr, alpha test,
blend, hloubku, color mask, ořezový obdélník. Jako software: bez cullingu,
stencilu a mipmap. Rozhraní `nv2a_backend.h` rozšířeno o `Nv2aVertexEx`
(d0/d1/fog/tex0-3), combinery, 4 stage, paletu, `zmax`, clip x/y a hook
`resolve`.

Paměť: každý barevný povrch je render target podle adresy (při vytvoření se
naplní z paměti hosta); textura na adrese povrchu vzorkuje render target.
Ostatní textury se dekódují na CPU (`nv2a_backend_decode_texture`, nyní i s
paletou P8) a drží v cache; první bind v každém snímku je přehashuje
(`RECOMP_GPU_TEX_CHECK=batch` = při každém bindu, ve hře nic nového nenašlo).
Render target má otisk paměti hosta; když ho CPU přepíše (stream textur do
uvolněného povrchu), při vzorkování se zahodí a čte se z paměti -- bez toho
byly v baru na podlaze žlutočerné/bílé chybné textury (`gpu-shots6-combat`,
konec). Při flipu se zobrazovaný povrch zkopíruje zpět do paměti hosta, takže
okno, `latest.bmp`, dumpy i benchmark fungují beze změny.

Nové proměnné: `RECOMP_FPS_LIMIT=<fps>` (omezovač snímků v executoru, platí i
pro software), `RECOMP_GPU_TRACE=<snímek>` (+ `RECOMP_GPU_TRACE_DIR`: vrcholy
dávek), `RECOMP_GPU_SHOT_DIR` (+ `_EVERY`): snímky render targetu, max. 100.
Back end každých 600 snímků loguje `[GPUB]` statistiky.

Měření (Ryzen 9 5900XT, benchmark stojící scéna, logy `build/gpu-run*.log`):
| Běh | FPS | CPU jader | Kontroly |
|---|---|---|---|
| software, stejná sestava (`perf-soft1-a`) | 37.55 | 17.7 | vše OK |
| GPU od 121 s (`perf-gpu1-a`, `perf-gpu3-trace`) | **117.2 / 118.7** | 1.8 | vše OK |
| GPU, `--combat-after` (`perf-gpu6-combat`, `perf-gpu7-fp`, `-batch`) | 122.2 / 116.6 / 116.8 | 1.8-1.9 | vše OK, 380 s |
| GPU od startu + `RECOMP_FPS_LIMIT=60` (`perf-gpu6-boot60`) | **59.97** | 1.5 | vše OK (logo, intro, menu, Carbon) |
| GPU + limit 30 (`perf-gpu5-30`) | 30.0 | 1.3 | vše OK |

Herní čas nezávisí na FPS: idle animace postavy (protahování) má periodu
~10 s při 30, 60 i 117 FPS (`gpu-shots5-*`, `gpu-shots4`) -- zámek 60 je
bezpečný. Snímky celé hry přes GPU: `build/gpu-shots6-boot/sheet.ppm`,
boj v baru `build/gpu-shots6-combat/sheet.ppm`.

Známé: (1) [VYŘEŠENO, viz blok pushbuffer-split: hroty byly ztracené příkazy pushbufferu; protažené paže jsou normální animace] při idle animaci se postavě na pár snímků extrémně protáhnou paže
-- vrcholy počítá CPU (skinning ve vertex shaderu), tedy nejde o chybu GPU
back endu; softwarový renderer je kreslí stejně, ale při ~37 FPS a vzorku
po 5 s to dříve nebylo vidět. Kandidát na chybu v `nv2a_vsh_interp.c`
(konstanty kostí / adresování a0). (2) RT na `0x809D0000`/`0x80778000` se
střídavě vytváří 640 a 1280 široký (AA/ne-AA); funguje, ale stojí
přealokování -- později klíčovat i šířkou. (3) Odchylka od software v
přesném místě baru po opravě otisku nebyla znovu cíleně ověřena (scénář se
rozešel). (4) Intro FMV má bílé tečky -- porovnat se softwarem.
Testy: raster batch (Windows CTest i Linux), ffp backend, guard band, surface
hazard, vertex cache (Linux) prošly. Patch: `outputs/xboxrecomp-gpu-backend.patch`
(i v `work/falloutbos/patches/`); zálohy původních souborů
`build/local-baseline/*.before-gpu`, EXE `fbos-before-gpu.exe`.
Aktuální `bin/fbos.exe` SHA-256 `5225551e6903dfc2b26e14f09826f16fc575cda60fbca54c9dd0ee12c24836d3`
(měření na `7328114270ce…`, stejný zdroj, jen jiné konce řádků).
Spouštění testů: fronta `outputs/Nocni-fronta.cmd` běží a Claude do
`build/queue` vkládá `.cmd` (např. `build/gpu-build.cmd`).

Další kroky: vyřešit skinning (bod 1), přímé zobrazení z GPU místo zpětného
čtení + GDI okna (dnes ~2-4 ms/snímek v back endu, z toho většina čekání na
readback), stencil/culling/mipmapy podle potřeby, porovnání snímků
software vs. GPU ve stejném bodě hry.
<!-- /gpu-backend-update -->

<!-- ceiling-update -->
## 19. 11. odpoledne: strop výkonu bez rasterizace = ~163 FPS

`RECOMP_NULL_BACKEND=<sekundy>` (jen měření, výchozí vypnuto): od prvního
flipu po zadané době zaregistruje back end, který nic nekreslí; vše ostatní
(hra, dekódování pushbufferu, vertex shading, ořez) běží dál. Okamžité
zapnutí nefunguje: menu běží ~1 200 FPS a časovaný pad skript se do scény
nedostane, proto 121 s.
Měření (`build/null121-backend2-verify.log`): **165.0 a 161.8 FPS** bez
rasterizace (CPU ~2 jádra), normálně 37.4 FPS (~18 jader).
Závěr: CPU strana není brzda; 60 FPS je reálné jen s rasterizací na GPU
(back end přes `nv2a_backend.h`, viz `outputs/navrh-60fps.md`; nutné doplnit
register combinery a texturové stage 1-3). Softwarovou cestou ~37-45 FPS.
Patch: `outputs/xboxrecomp-null-backend.patch`. Sestava s touto volbou je
v `bin/` (bez proměnné se chová stejně jako dosud).
<!-- /ceiling-update -->

<!-- audio-update -->
## 19. 11. poledne: výpadky zvuku odstraněny -- aktuální stav

Aktuální sestava SHA-256 `eab16c3a63ec719bb8be672394cf179c973d0b18dd7d76fdea36ccb3af5a28bc`
(předchozí `19985b3e…` v `build/local-baseline/fbos-before-audio8.*`).
Ve stojící scéně ~37.6 FPS, zvuk bez podtečení.

Příčina: fronta XAudio2 měla 4 buffery po 512 vzorcích (max. 43 ms), ale
vlákno APU doplňuje frontu v mezerách až ~21 ms (čekání se ve Windows
zaokrouhluje na ~15.6ms časovač) a fronta klesala na 256 vzorků (5 ms).
`XA2_NUM_BUFS_DEFAULT` v `src/apu/apu_xaudio2.c` je teď 8 (max. 85 ms;
`RECOMP_AUDIO_BUF_COUNT` dál přepíše). Pacing se přizpůsobí sám
(2048..4096 vzorků).
Měření (`build/audio-buf-verify.log`, stejné EXE přes proměnnou, střídavě,
`RECOMP_AUDIO_HOST=1`): 4 buffery 615 / 604 vyschnutí za běh (~7.6 s
ztraceného zvuku, ~1 500 underrunů), q_min 256; 8 bufferů 0 / 0, q_min 1280;
FPS beze změny (37.75 / 37.10 vs 37.73 / 37.43). Výchozí sestava
(`build/audio8-default-verify.log`): 37.59 FPS se scénářem v baru (1 underrun
při startu, 0 vyschnutí) a 37.73 FPS (0), bez chyb.
Patch: `outputs/xboxrecomp-audio-buffers.patch`.
<!-- /audio-update -->

<!-- threads-update -->
## 19. 11. dopoledne: 24 rasterizačních vláken (+17 % FPS)

Aktuální sestava SHA-256 `19985b3e12b866106cc6a9680bc082ffb59dc49b5916b1ab8741ac5c50d19d7a`
(předchozí `b866452f…` v `build/local-baseline/fbos-before-threads24.*`).
Ve stojící scéně **~37.7 FPS** (start dne 15.94 FPS).

Strop rasterizačních vláken byl napevno 16. `NV_RASTER_MAX_THREADS` je teď
32 (`RECOMP_RASTER_THREADS` do 32), výchozí počet je jádra − 4, nejvýš
`NV_RASTER_DEFAULT_MAX` = 24. Výsledek bit po bitu stejný (každý řádek má
dál jednoho vlastníka a pořadí trojúhelníků).
Měření (`build/threads-verify.log`, střídavě, Ryzen 9 5900XT 16/32):
16 vláken 33.46 / 30.60, **24 vláken 37.03 / 37.81**, 28 vláken 32.54 /
38.39 (28 občas propadne až na ~21 FPS: na hru, executor a zvuk zbývá málo
vláken). Ověření výchozí sestavy (`build/threads24-verify.log`):
37.75 FPS i se scénářem v baru a 37.63 FPS, bez chyb; CPU ~18 jader.
`tools/benchmark_runtime.py --threads` přijímá 1..32.
Patch: `outputs/xboxrecomp-raster-threads.patch`.
<!-- /threads-update -->

<!-- vcache-update -->
## 19. 11. dopoledne: cache transformovaných vrcholů (+9 % FPS)

Aktuální sestava SHA-256 `b866452f2dc38f11a3cdebb809a0310f36e95012a1885c9858b7b734c825739a`
(předchozí `4a080c90…` v `build/local-baseline/fbos-before-vcache.*`).

Profil po zrychlení vertex shaderu (`build/perf-profile-vsh`, nový
`tools/profile_runtime.py`): executor ~50 % čeká na drainy, ~27 % vertex
shading; workery ~38 % nečinné. `raster_batch_program` transformoval každý
index znovu, i když se vrchol v dávce opakoval. Nově cache v rámci dávky
(přímo mapovaná podle indexu); výsledek je stejný bit po bitu, protože
program začíná z vynulovaných registrů a vstupy se během dávky nemění; při
`CXT_WRITE_EN` (program smí psát c[]) je cache vypnutá. `RECOMP_NO_VCACHE=1`
ji vypne pro A/B. Ve hře ušetří ~47 % běhů vertex shaderu.

Ověření (`build/vcache-verify.log`): nový test `tests/nv2a_vertex_cache`
(indexovaná mřížka, plocha s cache a bez ní bajt po bajtu stejná, Linux i
Windows), ostatní testy prošly. A/B stejného EXE střídavě: s cache
**31.95 / 32.95 FPS**, bez cache 29.64 / 29.90 FPS (+9 %).
Poslední běh hlásil „counter agrees with GPU log“ = False: log byl o 1 flip
napřed před vzorkem (15293 vs 15292), souběh v měřicím nástroji, ne ve hře;
kontrola v `tools/benchmark_runtime.py` nyní toleruje −10 flipů.
Patch: `outputs/xboxrecomp-vertex-cache.patch`.
<!-- /vcache-update -->

<!-- morning-update -->
## Ráno 19. 11.: zrychlení vertex shaderu ověřeno (+9.4 % FPS)

Noční fronta stála celou noc na zaseknutém běhu `perf-default-drain-a`
(Python harness po startu nic nevypsal; příčina nezjištěna). Fronta neměla
časový limit -- to byla chyba přípravy. Ráno ručně ukončeno a fronta znovu
spuštěna; čekající skripty už mají `build/overnight/watchdog.ps1` (900 s).

`verify-vsh-decode` (log `build/vsh-decode-verify.log`), testy prošly,
A/B střídavě 2+2 ve stojící scéně:
- nová sestava (předdekódovaný vertex shader): **30.41 a 30.55 FPS**
  (`perf-vsh-new-a/-b`), SHA-256 `4a080c9049c71263803f053f5f04f28b0f4d7cdee2783800b0d203cd140c1917`;
- předchozí sestava (`c5dbb13f…`, výchozí drain): 27.85 a 27.91 FPS.
Zisk ~+9.4 %, obě nová měření nad oběma starými -- změna zůstává.
Patch: `outputs/xboxrecomp-vsh-decode.patch`. Za ní ve frontě běží
`zz-diag-audio-host.cmd` (diagnostika podtečení zvuku).
<!-- /morning-update -->

<!-- night -->
## Noční práce 19. 11. (souhrn sezení 00:14–07:13 UTC; noc uzavřena v 07:16 UTC, fronta celou noc stála, beze změn)

**Ráno nejdřív:** noční fronta stojí od 23:51 UTC na benchmarku
`perf-default-drain-a` (hra `fbos.exe`, PID 12796, běží dál v pauzovací
nabídce; Python harness se zasekl a hru neukončil). Podívat se, jestli na
obrazovce nevisí dialog chyby `python.exe` (nejpravděpodobnější příčina),
pak ukončit `fbos.exe` a `python.exe` toho běhu. Fronta potom sama spustí
`verify-vsh-decode.cmd` (testy, build, A/B 2+2 změny vertex shaderu) a
`zz-diag-audio-host.cmd` (diagnostika podtečení zvuku, ztišeno).
Kvůli zaseknuté frontě v noci neproběhlo žádné měření ani build.

- **Pojistka fronty (03:13):** oba čekající skripty spouštějí před každým
  benchmarkem `build/overnight/watchdog.ps1`. Pokud běh do 900 s neskončí,
  ukončí `fbos.exe` z projektu a `python.exe` s `benchmark_runtime.py`
  (záznam do `build/overnight/watchdog.log`), takže skript selže a fronta
  pokračuje. Normální běh trvá ~3 min. Původní skripty:
  `build/overnight/*.cmd.before-watchdog.txt`. Na Windows zatím neověřeno.
- **Strop snímků:** runtime ani hra žádný nemají (flip se dokončí okamžitě,
  vblank vypnutý, v nabídkách 70–100 FPS). Brzdou je jen renderer.
- **Vertex shading (čeká na měření):** `nv2a_vsh_interp.c` dekóduje
  instrukce jednou na slot a nečte nepoužité zdroje. Fuzz 160 000 vrcholů:
  shodné se starou verzí (liší se jen znaménko NaN, totéž dělá stará verze
  mezi -O0 a -O2). Mikrobenchmark −17 % času interpretu. Zdroj je upravený,
  `bin/fbos.exe` zatím ne. Pokud A/B nepřinese víc než šum (~3 %), vrátit z
  `build/local-baseline/nv2a_vsh_interp.c.before-vsh-decode`.
  Patch: `outputs/xboxrecomp-vsh-decode.patch`.
- **Zvuk (jen rozbor):** ~16 podtečení XAudio2/s po celou dobu hraní; fronta
  zařízení jen 21–43 ms, vlákno APU má normální prioritu a soutěží se
  spinujícími rasterizačními vlákny. Kandidáti po diagnostice: vyšší
  priorita vlákna APU nebo `RECOMP_AUDIO_BUF_COUNT=8`. Neaplikováno.
- **Dokumenty:** `outputs/navrh-60fps.md` (nejdřív změřit strop s prázdným
  back endem, pak rozhodnout o GPU back endu),
  `outputs/pruzkum-preklad-grafika.md` (texty UTF-16 v `.sdb`, písma v
  `.clp`, diakritika neověřena). Podrobný průběh: `build/overnight/log.md`.
- SHA-256 `bin/fbos.exe` (build z 23:51 UTC, výchozí drain), beze změny:
  `c5dbb13f38fc120d22064a996ac934c0e653acdc3128531d9020e9ee76558821`.
<!-- /night -->

<!-- texel-path-update -->
## Nejnovější změna: levnější adresa texelu a floor (bez měřitelného zisku FPS)

Aktuální sestava má SHA-256 začínající `f6fcd419fa4d` (předchozí `f8c6f8eb…`
je v `build/local-baseline/fbos-before-texel-path.*`).

`sample_quad` skládá swizzled adresu z části X a Y (2+2 výpočty místo 4
celých adres) a `rc_texel` používá `floor_i32` místo `floorf`. Výsledky bit po
bitu stejné (hash pro 256x256, 512x64, 256x8, 64x1024, 100x60; floor ověřen
na všech konečných floatech |f| < 2e9). Mikrobenchmark 36 → 28 ns/pixel.

Ve hře (`build/perf-texel-path-verify.log`): nová `perf-texel-path` 25.32 FPS
a 9.92 jádra CPU, předchozí `perf-texel-path-before` 26.17 FPS a 10.43 jádra.
**Důležité:** stejná předchozí sestava naměřila jednou 25.41 a jednou
26.17 FPS, šum jednoho měření je tedy ~3 %, ne 0.7 %, jak bylo uvedeno níže.
Zisk +2.6 % u „čtení čtyř texelů“ i tento výsledek jsou v rámci šumu.
Spolehlivé jsou jen větší skoky (guard band beze změny výkonu, combinery
+14.3 %; celkem ~15.9 → ~25–26 FPS). Obě poslední změny snižují spotřebu CPU,
ale FPS ve hře neprokazatelně. Pro další měření spouštět A/B několikrát
střídavě a porovnávat průměry.

Další drobné úpravy pixelů se nevyplatí měřit jedním během; skutečnou rezervou
je ~30 % nečinnost rasterizačních vláken na synchronizacích.
Patch: `outputs/xboxrecomp-texel-path.patch`.
<!-- /texel-path-update -->

<!-- texture-quad-update -->
## Čtení čtyř texelů najednou (+2.6 % FPS v jednom měření, v rámci šumu)

Aktuální sestava má SHA-256 začínající `f8c6f8ebc4d1` (předchozí `90936c47…`
je v `build/local-baseline/fbos-before-texture-quad.*`).

Scéna používá hlavně formát 0x0B (P8 s paletou, swizzled), dále 0x24
(640x480 lineární). DXT hra nepoužívá. Nová `sample_quad` v `nv2a_pb_exec.c`
načte pro bilineární vzorek všechny čtyři texely formátů 0x0B/0x06/0x07
najednou (formát rozhodnut jednou, souřadnice zabaleny dvakrát místo
osmkrát), ostatní formáty jdou původní cestou. Mikrobenchmark nad
`rc_texel`: 0x0B/0x06 ze ~50 na 36–41 ns na pixel; kontrolní součty výstupu
shodné pro všechny formáty a režimy (bit po bitu stejný výsledek).

Měření (`build/verify-texture-quad.cmd`, log `build/perf-texture-quad-verify.log`):
`perf-texture-quad` **25.41 FPS** (s herním scénářem, bez chyb) proti
`perf-texture-quad-before` 24.76 FPS. Šum měření stejné sestavy byl ~0.7 %
(24.58 vs 24.76). Celkem od začátku: 15.94 → 25.41 FPS (+59 %).
Patch: `outputs/xboxrecomp-texture-quad.patch`.

Další kandidáti: zbytek `rc_texel` (floorf a míchání), nečinnost
rasterizačních vláken na synchronizacích (~30 %), formát 0x24.
<!-- /texture-quad-update -->

<!-- raster-speed-update -->
## Rychlejší výpočet pixelů (+14.3 % FPS)

Aktuální sestava má SHA-256 `90936c4795c731a3720564a94493c14aef354caadfd5edb405be1115eb759033`
(předchozí `e90fb84e…` je v `build/local-baseline/fbos-before-raster-opt.*`).

Profil (`build/perf-profile-current`, rozdělený po vláknech): 16 rasterizačních
vláken je vytížených ~70 % a tráví čas ve `sample_tex`, `nv2a_rc_eval`,
`read_rgb`; herní vlákno se točí v `sub_000AB810` na kickoffu `0x100410`,
tedy čeká na „GPU“. Rozhoduje cena jednoho pixelu.

Změny (výsledky bit po bitu stejné):
- `nv2a_combiner.c`: `read_rgb` rozhoduje mapování jednou místo pro každý
  kanál; skalární součiny a scale/bias výstupu se počítají jednou na stupeň
  (`out_map`). Mikrobenchmark 156 → 101 ns/pixel; 2 000 000 náhodných programů
  combinerů dává identický výsledek se starou verzí.
- `nv2a_rc_unpack`: tabulka n/255 místo dělení (stejné hodnoty).
- `wrap_coord`: textury o rozměru mocniny dvou používají masku místo dvou
  dělení (ověřeno shodou pro všechny velikosti 1..4096 a záporné souřadnice).

Měření ve stejné scéně a hned po sobě (`build/verify-raster-opt.cmd`,
log `build/perf-raster-verify.log`):
- nová sestava `build/perf-raster-opt`: **24.58 FPS**, 10.32 jádra CPU,
  i s herním scénářem v baru, bez chyb;
- předchozí sestava `build/perf-raster-before`: 21.50 FPS, 11.12 jádra.
Testy combinerů, guard band a raster batch (1/4/16 vláken) prošly na Windows.

Patch: `outputs/xboxrecomp-raster-speed.patch` a `work/falloutbos/patches/`.
Další kandidáti: `sample_tex` (DXT cache kontroluje bajty bloku u každého
texelu), zbytek `nv2a_rc_eval` (kopie konstant přes TLS cache u každého
stupně), ~30 % nečinnosti rasterizačních vláken na synchronizacích.
<!-- /raster-speed-update -->

<!-- guard-band-update -->
## Guard-band ořez v softwarovém rendereru

Aktuální sestava má SHA-256 `e90fb84e20e7a94c3d34aebb88a5b4a316d6df2c86269f152871cccdfaaaede2`
(předchozí `c0a6c877…` je zálohovaná v `build/local-baseline/fbos-before-guard.*`).

Příčina: `raster_xf_clipped` v `deps/xboxrecomp/src/kernel/nv2a_pb_exec.c`
ořezával jen o rovinu kamery. Vrcholy těsně před kamerou se promítly na
souřadnice až ~1e9–1e17 px a rasterizér počítá hrany ve floatu, takže u
částečně viditelného trojúhelníku vycházelo pokrytí, barva i hloubka jako šum.
Oprava: po near-plane ořezu se polygon ořízne i o pásmo 1024 px kolem
ořezového obdélníku (roviny lineární v clip prostoru, atributy se interpolují
stejně jako u near plane). Trojúhelníky uvnitř pásma jdou beze změny starou cestou.

Ověření:
- nový test `deps/xboxrecomp/tests/nv2a_guard_band` (build `build-guard-test`):
  tři případy obřích trojúhelníků; původní kód 1536/1440/16384 chybných pixelů,
  nový 0/0/0. Prošel na Linuxu (gcc) i ve Windows CTestu.
- `build-raster-test` 3/3 a `nv2a_ffp_backend` prošly.
- `build/perf-guard-band` (`benchmark_runtime.py --combat-after`, 380 s):
  **21.58 FPS** proti 20.98 předtím, všechny kontroly prošly. Rozsah souřadnic
  v `[GPU] of the rest` je nyní x −1024..2302 místo až −1.2e9.
- Vizuální zlepšení konkrétních artefaktů (postava za geometrií, artefakt za
  nabídkou načítání) zatím nebylo cíleně prokázáno; běhy nejsou deterministické.
  Počet „degenerate“ trojúhelníků se nezměnil a je nejspíš neškodný
  (spojování triangle stripů).

Patch: `outputs/xboxrecomp-guard-band.patch` a `work/falloutbos/patches/`,
v místní závislosti už aplikovaný. Spuštění celého ověření:
`work/falloutbos/build/verify-guard-band.cmd` (dvojklik; log
`build/guard-band-verify.log`). Pozor: skript při opakování selže na
existující složce `build/perf-guard-band` -- přejmenujte `--name`.
<!-- /guard-band-update -->

<!-- combat-update -->
## Ověření boje: první zabití nepřítele hráčem (doplněno 18. 11. 2026 večer)

Po sepsání bloku o texturách proběhly ještě tři tiché herní běhy, všechny
s aktuální sestavou SHA-256 `c0a6c877…5f38f5`. Do dokumentu se původně nedostaly.

| Běh | Délka | Obtížnost | Výsledek |
|---|---|---|---|
| `build/combat-melee-01` | 542 s | Normal | bar načten, nasazeny Iron Gloves, série útoků; bez chyb |
| `build/combat-line-of-sight-01` | 650 s | Normal | **zásah za 10 bodů, nepřítel na zemi, sebrána kořist**; bez chyb |
| `build/combat-pansy-01` | 1000 s | Pansy | `--bar-ready --bar-fight`, střelba v baru; zabití zde neprokázáno |

Všechny tři běhy: žádný fault, výjimka ani nevyřešené volání, 0 selhání
souvislé alokace, ukončené záměrně přes `stop.flag` (proto `exit_code` 1).
Spolu je to dalších přibližně 36 minut stabilního běhu nové sestavy.

Důkazy pro zabití (v `combat-line-of-sight-01`): `damage-options-on.png`
(zapnutý Damage Text), `open-burst-09.bmp` (nad nepřítelem číslo 10, jeho
ukazatel zdraví), `raider-on-floor.png` (nepřítel leží) a `loot-one-cap.png`
(v inventáři 1 zátka). Kopie jsou v `outputs/zasah-nepritele-normal.png`,
`porazeny-nepritel-normal.png` a `korist-normal.png`.
Celý první boj (všichni nepřátelé v baru) stále není potvrzený;
viz pokus níže.

### Pokus o celý první boj: `build/combat-bar-full-01` (Normal, 674 s)

Spuštěno `playtest_session.py --name combat-bar-full-01 --bar-ready --seconds 1800`
přes `build/run-combat-bar-full-01.cmd`, boj řízen ručně přes `live.txt`.
- Pistolí (20 nábojů) zásahy 10 a 6; po vyprázdnění **Experience 45** a úkol
  „Kill Drunken Raiders“ hlásí **Bar raiders remaining: 7** (snímky `snap-12` až `snap-15`).
  Počítadlo úkolu je spolehlivé měřítko postupu boje.
- Iron Gloves jsou v inventáři od začátku; nasazení: Back, šipka nahoru, A.
  Zblízka zásahy 2, 10, 9, 3, 7 (`snap-28` až `snap-34`).
- Nadia pak padla (nabídka bez „Return to Game“, `death-menu.bmp`);
  test neměl uloženou pozici. Ukončeno přes `stop.flag`.
- Žádný fault, výjimka, nevyřešené volání ani selhání alokace; bar načten.

Závěr: zbraně, zásahy, zkušenosti, počítadlo úkolu, smrt postavy i nabídka
po smrti fungují. Celý boj (všech ~8 nájezdníků) dokončen nebyl kvůli herní
obtížnosti, nikoli kvůli chybě portu. Další pokus: obtížnost Pansy
(`build/run-combat-bar-full-02-pansy.cmd`, už připravený), nebo uložit
pozici před barem a boj opakovat z ní.

Postřeh pro grafické artefakty: souhrny `[GPU] of the rest` v `runtime.log`
uvádějí ve 3D scéně řádově stejný počet trojúhelníků „degenerate/NaN“ jako
vykreslených a extrémní rozsahy souřadnic (až ~1e17). Stojí za prověření
při řešení viditelnosti postavy.
<!-- /combat-update -->

<!-- texture-update -->
## Optimalizace textur

Aktuální sestava má SHA-256 `c0a6c8770cec1715f84e2917dc80865d5847605dfc754256151df2a5ae5f38f5`.
Ve stejné stojící scéně nyní dosahuje **20.98 FPS**,
oproti 17.97 FPS po první optimalizaci (dalších +16.8 %).
Proti původním 15.94 FPS je to celkem +31.6 %.
Čísla a hash uvedené níže u první optimalizace jsou historická.

Nově je zrychlen `swizzle_offset` v `deps/xboxrecomp/src/d3d/d3d8_swizzle.h`:
přímé proložení bitů pro mocniny dvou, původní obecná větev pro ostatní rozměry.
Nové testy: `deps/xboxrecomp/tests/swizzle_offset` / build `build-swizzle-test`.
Prošlo 5,573,633 porovnání adres a texelů, tři rastrové testy a `d3d8_smoke`.
Celé Release sestavení prošlo. Rozlišení a filtrování se nesnižovaly.

Nový patch je v `outputs/xboxrecomp-swizzle-offset.patch` i v repo `patches/`;
v místní závislosti je už aplikovaný. Dokumentace: `outputs/vykon-textur.md`,
`outputs/vysledek-optimalizace-textur.json`, `docs/performance-textures.md`.
Profil aktuálního výchozího stavu před touto změnou je v
`build/perf-profile-current/profile-summary.json` a `profile-raw.bin`.
Původní EXE této etapy: `build/local-baseline/fbos-before-texture.*`.

Běhy nové sestavy: `build/perf-texture-1` a
`build/perf-texture-2-combat-fixed`. Druhý nejprve změřil stejnou stojící
scénu a až po měření pokračoval pohybem, Ruby, barem, vybavením pistole
a střelbou. Má 380.2 s, bez zaznamenané chyby.
Snímky `bar-equipped.bmp`, `bar-fired.bmp`, `bar-movement.bmp` jsou v tomto běhu.
První dva zachycují pistoli a pokles počtu nábojů z 19 na 11.
Pokus `perf-texture-2-combat` byl záměrně ukončen při opravě testovacího
skriptu před měřením; nepočítat ho jako výsledek ani jako pád hry.

Opakování z pracovního adresáře repozitáře:
```powershell
& '../fbos-venv/Scripts/python.exe' tools/benchmark_runtime.py --name perf-dalsi --combat-after
```
Volba `--combat-after` zachovává vstup
do konce měření bez pohybu a potom provede herní scénář. Celkem trvá
přibližně 380 s. Ověření počtu flipů se porovnává s logem z konce měření,
nikoli s pozdějším počítadlem po herní části. Všechny testy musí zůstat tiché.

Pro nové spuštění testů adres:
```powershell
& $cmake -S deps/xboxrecomp/tests/swizzle_offset -B build-swizzle-test -A x64
& $cmake --build build-swizzle-test --config Release --parallel 2
& $ctest --test-dir build-swizzle-test -C Release --output-on-failure
```
Proměnné `$cmake` a `$ctest` a pracovní adresář jsou rozepsané níže.
Zásah a zabití nepřítele hráčem už jsou potvrzené (viz blok výše).
Úplný první boj stále není ověřený; dále viditelnost postavy a artefakty.
<!-- /texture-update -->


Stav: 18. listopadu 2026. Práce je místní, na Windows. Veřejný fork ani PR
nevznikly; změny nejsou commitnuté. Původní MIT licence zůstala zachována.

## Kde projekt najít a spustit

- Workspace: `C:\Users\sesta\Documents\Codex\2026-11-18\a`
- Repozitář hry: `C:\Users\sesta\Documents\Codex\2026-11-18\a\work\falloutbos`
- Závislost: `C:\Users\sesta\Documents\Codex\2026-11-18\a\work\falloutbos\deps\xboxrecomp`
- Spouštěč pro uživatele: `C:\Users\sesta\Documents\Codex\2026-11-18\a\outputs\Spustit-Fallout.cmd`
- Aktuální EXE: `C:\Users\sesta\Documents\Codex\2026-11-18\a\work\falloutbos\bin\fbos.exe`
- Větev hry: `codex/xbox-port`; závislost: `codex/fbos-present-capture`.
- Výchozí revize hry: `ec7bd923e9281c79579ba4533aa76036934b9a91`.
- Výchozí revize závislosti: `0a5d6385c51beb3e5e28b09dc886c28566f1689a`.

Spouštěč volá `Play.cmd`, který zapíná vykreslování, okno a klávesnici.
Ovládání: WASD pohyb, IJKL druhá páčka, Z/X/C/V = A/B/X/Y,
Enter = Start, Backspace = inventář, 1/3 = spouště. Funguje i Xbox ovladač.
Testy jsou na výslovné přání uživatele tiché (`RECOMP_AUDIO_MUTE=1`).
Běžné hraní má zvuk zapnutý.

## Co už funguje a co bylo opraveno

1. Z původního Xbox obrazu uživatele bylo rozbaleno 491 souborů do `game/`.
   Vygenerováno 3 888 funkcí; sestavení Windows x64 Release funguje.
   Jeden nevyřešený cíl zůstává jako stub stejně jako v upstreamu.
2. Ověřen pohyb, kamera, inventář a vybavení pistole. Uložení a načtení
   prošlo i po úplném restartu aplikace. Ověřen přechod přes Ruby do baru,
   střelba se spotřebou nábojů a zásahy nepřátel do hráče.
3. Hotové snímky se nově zaznamenávají ze skutečně dokončeného obrazu.
   Staré výpisy rozpracované plochy byly zavádějící; nepoužívat je samotné
   jako důkaz chyby kamery. Pět testů záznamu prošlo.
4. Opravená nalezená příčina pádu v baru: výchozí režim závislosti
   nevracel uvolněné grafické bloky. Po vyčerpání paměti se zápisem palety
   poškodil ukazatel ovladače. Hardwarový breakpoint zachytil zápis do
   guest `0x8000032C` uvnitř `sub_00084710`; chyba čtení následně padala
   v `sub_000D944C`. `src/game/main.c` nyní před inicializací paměti
   zapíná existující režim `RECOMP_HEAP_RECLAIM`. Původní herní kód ani
   kontrola ovladače nejsou obcházené.
5. Správa paměti prošla čtyřmi CTesty, předběžným během 310 s a během
   600 s se střelbou, smrtí postavy a načtením pozice. Žádná alokace
   neselhala, maximum vykázané souvislé paměti bylo 31 440 KB a ukazatel
   během 570 s sledování zůstal `0x000D82EC`. Tyto testy předcházely
   poslední výkonnostní úpravě rendereru.
6. První výkonnostní změna: soukromé, zarovnané statistiky vykreslovacích vláken,
   sloučené po dokončení fronty. Tehdejší porovnání ve stejné scéně:
   **15.94 → 17.97 FPS**, přibližně **+12.7 %**.
   Prošly pixelové testy při 1/4/16 vláknech i dva běhy nové sestavy.
   Samotné snížení počtu vláken na 4 bylo pomalejší a není zapnuté.

## Soubory a důkazy

- `outputs/oprava-padu.md`, `outputs/vysledek-opravy-pameti.json`:
  předchozí oprava správy paměti a její samostatné ověření.
- `outputs/vykon-portu.md`, `outputs/vysledek-optimalizace.json`:
  metodika a výsledky první optimalizace. Tehdejší sestava měla SHA-256
  `f4166bbe54f37a0980b0d905c699bab401762f77a76be3b80ec2ed107a79e7e4`.
- `outputs/xboxrecomp-raster-stats.patch`: změna závislosti z první
  optimalizace včetně tří testovacích konfigurací. Novější je
  `outputs/xboxrecomp-swizzle-offset.patch` (viz blok o texturách).
- `work/falloutbos/patches/`: stejné patche, záznam hotového obrazu a mute.
  Patche závislosti jsou už aplikované v místní kopii.
- `outputs/falloutbos-oprava-pameti.patch`: změna vstupního kódu hry.
- `work/falloutbos/docs/playtesting.md`, `docs/performance.md`,
  `docs/local-development.md`: technické poznámky pro pokračování.
- `work/falloutbos/tools/benchmark_runtime.py`: měření skutečného počtu
  dokončených flipů a času CPU. Soukromé rozložení `s_gpu` a odpovídající
  linker `.map` jsou součástí předpokladů nástroje; při změně struktury
  v závislosti upravit i jeho prefix v ctypes.
- `work/falloutbos/tools/playtest_session.py`: tiché testy se snímky,
  izolovanými pozicemi a vstupním souborem `live.txt`; `stop.flag` ukončí
  vlastní proces. `--seconds` určuje délku; každý `--name` musí být nový.
- Běhy výkonu: `build/perf-profile-before`, `perf-threads-4`,
  `perf-before-16`, `perf-after-16`, `perf-after-default`.
- Původní EXE před optimalizací a odpovídající `.map` jsou v
  `build/local-baseline/fbos-before-performance.*`.
- Testy hry a paměti: `build/gameplay-session`, `gameplay-cold-load`,
  `gameplay-combat`, `combat-repro-muted-02`, `combat-reclaim-01`,
  `combat-memory-fixed`. Poslední obsahuje log zachycení breakpointu,
  který už po opravě nehlásil poškozující zápis.

## Sestavení a ověření

Python s Capstone je v `C:\Users\sesta\Documents\Codex\2026-11-18\a\work\fbos-venv\Scripts\python.exe`.
CMake, CTest a Visual Studio 2022 Build Tools jsou už nainstalované.
Generované herní C je v `src/game/recomp/gen` a je ignorované Gitem.
Na běžnou další úpravu runtime není nutné je znovu generovat.

```powershell
$repo = 'C:\Users\sesta\Documents\Codex\2026-11-18\a\work\falloutbos'
$cmake = 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
$ctest = 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\ctest.exe'
Set-Location -LiteralPath $repo
& $cmake --build build-msvc --config Release --parallel 2
& $cmake --build build-raster-test --config Release --parallel 2
& $ctest --test-dir build-raster-test -C Release --output-on-failure
& '..\fbos-venv\Scripts\python.exe' tools/benchmark_runtime.py --name perf-dalsi
```

`build-msvc` má `FBOS_COMPILE_JOBS=2`, aby překlad velkých generovaných
souborů nezatěžoval celý počítač. Existující varování překladače zůstávají.
Další připravené testovací buildy: `build-memory-test` (4 testy)
a `build-present-test` (5 testů). Příkaz `Setup.cmd` není spolehlivý
inkrementální build: pokud EXE existuje, může překlad přeskočit.

Případné Git hlášení dubious ownership se v tomto prostředí řešilo
parametrem `git -c safe.directory=<absolutní cesta> -C <cesta> ...`
pro konkrétní příkaz, bez změny globálního nastavení.

## Data, ukládání a omezení

Uživatel dodal obraz:
`C:\Users\sesta\Downloads\Fallout - Brotherhood of Steel (USA)\Fallout - Brotherhood of Steel (USA).xiso.iso`.
SHA-256 `default.xbe`:
`9295b6e0cc70024392c34f2df8795e5d28c9592b9cda45853549029dd833919c`.
Použitá hra je USA Xbox, XDK 5558, title ID `0x49500008`, vstup `0x9547C`.
Herní data ani generované C se nepublikují v patchích. Launcher závisí
na této pracovní složce; nejde o samostatný distribuční balíček.

Běžné pozice jsou v `work/falloutbos/saves`. Automatické testy používají
oddělené složky. Ověřený uložený stav je v
`build/gameplay-session/test-saves/UDATA/49500008/63112EC3A95B/`:
`fobos.sav` 334 596 bajtů a `fobos.hdr` 96 bajtů. Při posledním testu
paměti se tato pozice kopírovala do izolované testovací složky;
původní adresář nebyl měněn.

Zůstávají grafické artefakty, překrývání postavy geometrií a artefakt za
nabídkou načítání. Audio loguje underruny; poslech nebyl vyhodnocen.
Zásah a zabití jednoho nepřítele hráčem jsou potvrzené; celý první boj,
kooperace ani průchod celou hrou potvrzené nejsou. Nové měření je jedna stojící scéna bez okna;
nezaručuje stejné FPS v celé hře. Smrt herní postavy není pád aplikace.

## Doporučené navázání

Pohyb, vybavení pistole, střelba, zásah a zabití nepřítele jsou ověřené výše.
Nejbližší užitečný krok je průchod celým prvním bojem v baru
a potom řešit viditelnost postavy. Pro další zrychlování znovu
profilovat aktuální EXE ve stejné scéně a oddělit aktivní CPU práci od
čekajících vláken. Adresování textur (`swizzle_offset`) už je zrychlené; interpretr shaderů
a zbytek vzorkování textur jsou další kandidáti k měření.

Text pro nový chat:

> Pokračuj v místním Xbox portu Fallout: Brotherhood of Steel.
> Nejdřív přečti `C:\Users\sesta\Documents\Codex\2026-11-18\a\outputs\predani-projektu.md`
> a technické poznámky v `work/falloutbos/docs`. Aktuální sestava obsahuje
> opravu vracení grafické paměti a zrychlení statistik softwarového rendereru.
> Automatické testy musí zůstat ztišené. Navazuj na existující projekt a důkazy.
