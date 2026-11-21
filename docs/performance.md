# Zrychlení Xbox portu – 18. listopadu 2026

Nejnovější optimalizace adres textur: **20.98 FPS**
oproti předchozím 17.97 FPS, dalších **+16.8 %**.
Aktuální výsledky a herní ověření jsou ve `vykon-textur.md` a v předání.
Následuje záznam první optimalizace čítačů; jeho hash a čísla jsou historická.


Ve stejné stojící scéně v Carbonu se výkon zvýšil z **15.94
na 17.97 FPS**, přibližně o **12.7 %**. Nová sestava je
už v místním `bin/fbos.exe` a používá ji `Spustit-Fallout.cmd`.

| Sestava | FPS | Průměrné využití CPU v ekvivalentech plně vytíženého logického procesoru |
| --- | ---: | ---: |
| Původní sestava, 16 vláken | 15.94 | 13.18 |
| Původní sestava, 4 vlákna (nepoužito) | 8.15 | 4.59 |
| Optimalizace, 16 vláken | 18.05 | 12.18 |
| Optimalizace, běžné výchozí nastavení | 17.97 | 12.17 |

Počítač: AMD Ryzen 9 5900XT, 16 jader / 32 logických procesorů, Windows x64.
Číslo CPU 12 například znamená souhrnný čas přibližně 12 logických
procesorů; nejde o procenta celého CPU ani počet vytvořených vláken.

## Co se změnilo

Softwarový renderer dříve zapisoval z každého vykreslovacího vlákna při
každém pixelu do společného diagnostického čítače. Navíc čítače jednotlivých
vláken sousedily ve stejných cache řádcích. Nově mají vlákna vlastní
statistiky, oddělené zarovnáním na 64 bajtů; výsledky se sloučí po dokončení
fronty. Odstranil se tím také souběžný nechráněný zápis do těchto statistik.

Počet vláken ani výpočty barev, rozlišení a herní logika se touto změnou
nemění. Pouhé snížení počtu vláken na čtyři se ukázalo jako pomalejší
a není součástí výchozího nastavení.

## Jak se měřilo a testovalo

- Stejná úvodní scéna a ovládací skript; po 120 sekundách žádný další vstup.
- Každý běh má 125 sekund na rozběhnutí, pak přibližně 35 sekund měření.
  FPS je rozdíl počtu dokončených GPU flipů dělený skutečným monotónním
  časem. Počítadlo se čte ze stejné proměnné jako herní log a kontroluje se
  proti němu. CPU čas pochází z Windows GetProcessTimes.
- Vždy běžel jediný herní proces. Při měření neprobíhal překlad ani profilování.
  Výstup hotových snímků 640×480 byl zapnutý, uložení každých 120 flipů.
  Testy běžely bez okna a se ztišeným zvukem.
- Prošly všechny kontroly startu, žádné zaznamenané FAULT/EXCEPTION,
  nevyřešené volání ani vyčerpání souvislé paměti.
- Prošly tři regresní testy rendereru při 1, 4 a 16 vláknech. Každý ověřil
  56 993 pokrytých pixelů bez chyby, pořadí překrývajících se trojúhelníků
  a zachování stavu mezi dávkami.
- Optimalizovaná sestava byla změřena dvakrát, podruhé bez přepsání počtu
  vláken prostředím. Snímky před a po byly vizuálně porovnány.

Je to měření jedné scény bez herního okna, nikoli průměr celé hry.
Příspěvek oddělení čítačů a odstranění společného zápisu nebyl měřen zvlášť.
Grafické artefakty a celý průchod hrou tímto ověřené nejsou.

Zdrojová změna s testy: `xboxrecomp-raster-stats.patch`.
Výsledky: `vysledek-optimalizace.json`; jednotlivé vzorky a logy:
`work/falloutbos/build/perf-*`. Reprodukce:

```powershell
cd "%USERPROFILE%\Documents\Codex\2026-11-18\a\work\falloutbos"
& "..\fbos-venv\Scripts\python.exe" tools/benchmark_runtime.py --name perf-vlastni
```

SHA-256 aktuálního EXE: `f4166bbe54f37a0980b0d905c699bab401762f77a76be3b80ec2ed107a79e7e4`.
