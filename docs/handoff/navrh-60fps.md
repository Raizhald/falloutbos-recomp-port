# Návrh: cesta k 60 FPS (19. 11. 2026, noční rozbor)

> **Stav 19. 11. odpoledne:** krok 0 změřen (strop ~163 FPS), krok 2
> implementován jako prototyp s combinery, stage 0-3, paletami a
> render-to-texture: ~117 FPS ve stojící scéně, 59.97 FPS se zámkem
> `RECOMP_FPS_LIMIT=60` od startu hry. Herní čas na FPS nezávisí.
> Podrobnosti v `predani-projektu.md` (blok gpu-backend-update).

Jen návrh. Nic z toho není implementováno, kromě drobných bezpečných kroků
zapsaných v `predani-projektu.md`.

## Kde jsme

- Stojící scéna v Carbonu: ~26 FPS (šum jednoho běhu ~3 %), v baru ~19 FPS.
  Snímek trvá ~38 ms, pro 60 FPS je rozpočet 16,7 ms (2,3× rychleji).
- **Strop snímků nemá runtime ani hra.** `NV097_FLIP_STALL` v
  `nv2a_pb_exec.c` dokončí flip okamžitě, vblank (`RECOMP_VBLANK`) je ve
  výchozím stavu vypnutý a benchmark ho nezapíná. V nabídkách hra běží
  70–100 FPS (`[GPU] 103.57 fps` na začátku každého `runtime.log`).
  Brzdou je tedy jen softwarový renderer.
- Executor (vlákno, které čte pushbuffer, transformuje vrcholy a rozdává
  práci) čeká ~30–50 % času na drainy; nutné jsou hlavně u D3D KickOff
  (`5:0310`) a na konci scanu, protože po nich titul smí přepsat textury,
  které rasterizační vlákna čtou líně. Rasterizační vlákna jsou 50–60 %
  nečinná. Zbytek času executoru je hlavně vertex shading (`nv2a_vsh_run`,
  ~36 %).

## Proč drobné úpravy na 60 nestačí

I kdyby drainy zmizely úplně, executor by byl nanejvýš ~2× rychlejší
a rasterizace by ho musela stíhat. Realistický strop softwarové cesty s
dalšími úpravami odhaduji na 35–45 FPS. 60 FPS ve hře znamená přesunout
rasterizaci na GPU.

## Doporučené pořadí

### Krok 0 – změřit strop (1 den, malé riziko)
Zaregistrovat „prázdný“ back end (`nv2a_backend_register`, `draw`/`clear`
nic nedělají) zapnutý proměnnou prostředí, a změřit FPS stejným
benchmarkem. Výsledek je horní mez pro *jakýkoli* renderer: kolik stojí
herní logika + dekódování pushbufferu + vertex shading. Pokud vyjde pod 60,
je nutné zrychlit i CPU stranu (vertex shading, viz níže), jinak GPU back end
sám nestačí.

Zároveň ověřit, že herní logika nezávisí na počtu snímků (hra by při 60 FPS
neměla běžet rychleji): porovnat dobu chůze po stejné trase při
`RECOMP_RASTER_THREADS=4` (pomalé) a 16.

### Krok 1 – CPU strana (průběžně, malé riziko)
- Vertex shading: předdekódování instrukcí (zkoušeno tuto noc, ~-17 % času
  interpretu), dál případně JIT/specializace na typické D3D programy
  (4× DP4 + epilog) – výsledky bit po bitu stejné, testovatelné fuzzem proti
  interpretu.
- Snímek textur při KickOff místo drainu: zkopírovat jen textury, které čtou
  rozpracované joby (copy-on-kickoff). Odstraní největší čekání, ale je to
  zásah do synchronizace; nutný test typu `nv2a_surface_hazard` (titul
  přepíše texturu hned po KickOff).

### Krok 2 – GPU back end (D3D11) přes `nv2a_backend.h`
Rozhraní už existuje (clear/draw/flip, vrcholy v pixelech plochy, render
state, dekódování textur), ale dnes předává jen texturu stage 0 a difuzní
barvu. Pro tuto hru je potřeba:

1. **Register combinery** – hra je používá (combinery daly +14 % už na CPU).
   Rozšířit `Nv2aBatch` o stav combinerů a generovat z něj pixel shader
   (HLSL), cache podle hashe stavu. Logiku lze převzít z `nv2a_combiner.c`
   a testovat porovnáním s CPU výsledkem.
2. **Texturové stage 1–3** a jejich souřadnice (výstupy `tex[1..3]`).
3. **Textury s paletou (formát 0x0B, P8)** – hlavní formát scény. Buď
   dekódovat na CPU při změně (cache podle adresy + hashe obsahu/palety),
   nebo paletu jako 1D texturu a převod v shaderu.
4. **Koherence s pamětí hosta** – titul přepisuje textury a palety; potřeba
   sledovat změny (hash při bindu, nebo ochrana stránek). Největší zdroj chyb.
5. **Render-to-texture** – titul vzorkuje plochy, do kterých kreslil
   (důvod hazard trackingu). GPU back end musí plochy držet jako GPU textury
   a poznat jejich adresu při bindu.
6. **Zpětné čtení do paměti hosta** jen tam, kde ho titul potřebuje
   (např. snímek pro uložení hry) – zjistit, zda vůbec.
7. Stencil, alpha test, mlha, AA faktor (`aa_sx/aa_sy`), point/line
   primitiva podle toho, co hra skutečně používá (`[GPU]` statistiky metod).

**Odhad pracnosti:** prototyp, který kreslí scénu bez combinerů (vizuálně
špatně, ale ukáže FPS): 3–5 dní. Úplný back end se shodou se softwarovým
rendererem na testovacích scénách: 3–6 týdnů soustředěné práce.

**Rizika:** rozdíly v rasterizaci (pravidla pokrytí, přesnost hloubky) –
porovnávat snímky s CPU rendererem (`RECOMP_FB_PRESENT_DUMP`) ve stejném
bodě hry; koherence textur; render-to-texture; vazba na Windows/D3D11.
Softwarový renderer zůstane jako referenční a záložní cesta.

## Doporučení
Nejdřív krok 0 (jednodenní měření stropu). Podle výsledku rozhodnout, zda
investovat týdny do GPU back endu. Do té doby pokračovat v bezpečných
úpravách CPU strany, které mají smysl v obou případech.
