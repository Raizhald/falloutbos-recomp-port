# Další zrychlení: adresování textur

Nová sestava dosahuje ve stejné scéně **20.98 FPS** místo
předchozích **17.97 FPS**, tedy dalších **+16.8 %**.
Proti původním 15.94 FPS je celkové zlepšení **+31.6 %**.
Je už v běžném spouštěči `Spustit-Fallout.cmd`.

| Sestava ve stejné stojící scéně Carbonu | FPS |
| --- | ---: |
| Původní sestava | 15.94 |
| Po první optimalizaci čítačů | 17.97 |
| Nový výpočet adres textur, první měření | 21.07 |
| Nový výpočet adres textur, opakované měření | 20.98 |

## Změna a její ověření

Nový profil stávající sestavy ukázal 22 366 vzorků ve `sample_tex` z 93 293
vzorků uvnitř programu, přibližně 24 %. Jde o vzorkování všech vláken podle
reálného času, včetně čekání; není to přesné procento aktivního CPU času.
Surový profil i souhrn zůstávají v `build/perf-profile-current`.

Nejčastější adresy ve vzorkování textur odpovídaly smyčkám, které pro každý
texel stavěly masky a prokládaly bity souřadnic. Nový výpočet přímo proloží
nižší bity a připojí vyšší bity delšího rozměru. Platí pro rozměry tvořené
mocninou dvou do 65 536; ostatní hodnoty používají původní výpočet.

Výstupní rozlišení, filtrování a samotné texely se nemění. Změna je
v `deps/xboxrecomp/src/d3d/d3d8_swizzle.h`, nikoli v generovaném herním C.

- Prošlo 5,573,633 kontrol adres a texelů: úplné porovnání všech souřadnic
  pro kombinace mocnin dvou od 1 do 1024, velké a krajní hodnoty, nesymetrické textury,
  souřadnice mimo rozsah i původní obecná větev. Samostatně se porovnal
  výstup s řádkovým swizzle/unswizzle pro 1/2/4 bajty na texel.
- Prošly 3 pixelové testy rendereru při 1/4/16 vláknech a stávající
  `d3d8_smoke` včetně ověřování adres textur. Prošlo celé Release sestavení.
- Dvě samostatná měření trvala přibližně 35 s po 125 s rozběhu, se stejným
  ovládacím skriptem a skutečným počtem dokončených flipů. Neběželo okno,
  profiler ani překlad. AMD Ryzen 9 5900XT, 16 jader / 32 logických procesorů.
- Při druhém běhu začal pohyb až po měření. Ve stejném procesu se pak
  prošlo k Ruby, do baru, vybavení pistole a střelba. Zachované snímky
  dokládají vybavení, pokles počtu nábojů z 19 na 11 a další pohyb.
- Žádný zaznamenaný FAULT/EXCEPTION, nevyřešené volání nebo vyčerpání
  souvislé paměti. Proces ukončil test po 380.2 s.
  Zvuk obou běhů byl ztišený.

Měření platí pro tuto jednu scénu, nikoli pro průměr celé hry. Zásahy
nepřátel hráčem, celý první boj, grafické artefakty a kooperace zůstávají
k ověření. Oba výsledky výkonu pocházejí z přesně této binárky:
`c0a6c8770cec1715f84e2917dc80865d5847605dfc754256151df2a5ae5f38f5`.

Patch: `xboxrecomp-swizzle-offset.patch`; výsledky:
`vysledek-optimalizace-textur.json`. Benchmark a navazující herní test:

```powershell
cd "C:\Users\sesta\Documents\Codex\2026-11-18\a\work\falloutbos"
& '..\fbos-venv\Scripts\python.exe' tools/benchmark_runtime.py --name perf-novy-test --combat-after
```

První rozpracovaný kombinovaný běh `perf-texture-2-combat` byl záměrně
ukončen před měřením při opravě testovacího skriptu. Do výsledků není započítán.
