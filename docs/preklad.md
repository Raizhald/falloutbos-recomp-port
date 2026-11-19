# Český překlad – průzkum (19. 11. 2026)

## Kde je text

| Soubor | Co obsahuje | Rozsah |
|---|---|---|
| `game/resx/gtext.sdb` | menu, dialogy, titulky, úkoly, nápovědy | 3 640 textů, ~37 600 slov, ~210 000 znaků |
| `game/resx/deftexte.sdb` | názvy objektů (zbraně, dveře, předměty) | ~300 textů (zbytek jsou interní klíče) |
| `game/resx/global.sdb`, `resx/c*/*/*.sdb` (60 souborů) | názvy postav a objektů v úrovních | ~15 textů na úroveň |
| `resx/c*/*/*.nfo` | jména mluvčích v úrovních (ASCII) | malé |
| videa `.bik`, textury | „CHAPTER ONE“, citát T. S. Eliota, nadpisy v grafice | text je vypálený v obraze – nepřekládat (nebo nahradit titulky) |

Hlasy zůstávají anglické; titulky (`gtext.sdb`) jdou přeložit.

## Formát `.sdb`

- Hlavička 3× `uint32`: konstanta (1499), počet bajtů textové části, počet řetězců.
- Text: řetězce **UTF-16LE** ukončené nulou (diakritiku formát pojme).
- Za textem hašovací tabulka (u `gtext.sdb` 65 524 B): dvojice *(haš ID, bajtový offset
  textu)*. Hra hledá texty podle ID, ne podle pořadí.
- Ověřeno ve hře: přepsání textu stejnou délkou se zobrazí (hlavní menu).
- Delší/kratší texty: stačí přepočítat offsety v tabulce a velikost v hlavičce
  (stará pozice → nová), haše se nemění. Nástroj na rozbalení/zabalení je jednoduchý.
- Řídicí znaky v textech nutno zachovat: `}` a `\x82`–`\x94` (ikony tlačítek),
  `%s`/`%d` (dosazované hodnoty).

## Písmo – hlavní překážka

Test přímo ve hře (`build/translate/font2-040.png`): **Latin-1 funguje** (`á` se
vykreslilo, tedy i `é í ó ú ý`), ale **háčky a `ů` chybí** – `č ě š ř ž ď ť ň ů`
i velká `Č Ě Š Ř Ž` jsou prázdná. Písmo je `gamefontsmall.fnt` uvnitř
komprimovaného balíku `.clp`.

Možnosti:

1. **Bez háčků** („Nova hra, zluty kun“) – hned, ale vypadá to špatně.
2. **Rozšířit písmo v `.clp`** – rozluštit kompresi `.clp` a formát `.fnt`, doplnit
   glyfy, zabalit zpět. Čisté, ale nejvíc práce a závislé na formátu dat.
3. **Doplnit glyfy v portu (doporučeno)** – port po načtení písma do paměti dokreslí
   do jeho textury chybějící písmena na místa nepoužitých znaků Latin-1
   (např. `¤ ¦ ¨ ª …`) a nástroj překladu je při zabalení na tyto znaky přemapuje
   (č → ¤ …). Herní data zůstanou netknutá, funguje v GPU i softwarovém vykreslování.
   Potřeba zjistit, kde v paměti leží textura a tabulka šířek písma (najde se
   diferenciálním nástrojem / logem textur).

## Postup

1. Nástroj `tools/sdb.py`: rozbalit `.sdb` → tabulka (ID, angličtina, čeština) a zpět
   (s přepočtem offsetů); kontrola řídicích znaků a délek do políček menu.
2. Písmo (možnost 3).
3. Překlad: strojový návrh celého `gtext.sdb` + lidská korektura (styl Falloutu,
   vulgarismy, jména zůstávají). Menu a úkoly mají omezenou šířku – kontrola ve hře.
4. Přepínač jazyka v `Settings.cmd` (Language: English / Čeština) – port načte
   `gtext.sdb` z přeložené kopie, originál zůstane.

Odhad: nástroje a písmo 2–3 sezení; samotný text ~37 600 slov – návrh rychle,
korektura je hlavní práce (desítky hodin člověka, dá se po částech: menu a
úkoly → dialogy kapitoly 1 → zbytek).
