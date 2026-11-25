# Veleho – pelisuunnitelma (prototyyppi)

## 1. Visio

**Veleho** on 2D-roguelite, jossa koko maailma on simuloitu pikseli pikseliltä. Hiekka valuu,
vesi virtaa, öljy palaa, happo syövyttää ja räjähdykset repivät luolaa auki. Pelaaja on
huppupäinen velho, joka laskeutuu proseduraalisesti luotujen luolastojen ja vieraiden
ulottuvuuksien läpi taikasauvojen, taikakeppien ja miekkojen voimin.

- **Hardcore / permadeath:** kuolema päättää juoksun. Tallennus poistetaan ja seuraava
  juoksu luodaan uudesta siemenestä (seed) – mikään ei ole koskaan samanlaista.
- **Tallennus:** jokaisen kentän alussa peli tallentaa juoksun tilan. *Tallenna ja lopeta* tai
  ikkunan sulkeminen tallentaa koko pikselimaailman juuri siihen kohtaan. Kesken kentän tehty
  tallennus käytetään kerran, joten sitä ei voi ladata uudelleen kuoleman välttämiseksi.
- **Kaikki proseduraalista:** kenttien muoto, materiaalit, nesteet, viholliset, aseiden
  ominaisuudet, loitsut, aseiden ulkonäkö ja ulottuvuuksien järjestys.

## 2. Pelisilmukka

1. Pelaaja ilmestyy kentän alkuun (portaali).
2. Tutkii luolastoa, taistelee, kaivaa ja räjäyttää tietä, löytää uusia aseita ja
   elämänkristalleja.
3. Löytää **ulottuvuusportin** kentän toisesta päästä.
4. Portin läpi mentäessä valitaan yksi kolmesta **siunauksesta** (pysyvä bonus juoksun ajaksi).
5. Uusi kenttä luodaan satunnaisesta ulottuvuudesta, vaikeus kasvaa syvyyden mukana.
6. Kuolema → kuolinruutu ja tilastot → maailma syntyy uudelleen.

## 3. Ohjaus

| Toiminto | Näppäin |
|---|---|
| Liiku | A / D |
| Hyppy / leijunta (pidä pohjassa ilmassa) | W tai Välilyönti |
| Tähtää | Hiiri |
| Käytä asetta (sauva: ammu, keppi: lataa ja vapauta, miekka: lyö, pullo: kaada) | Hiiren vasen |
| Heitä pullo | Hiiren oikea |
| Juo pullosta | F |
| Reppu (loitsujen ja aseiden järjestely, peli pysähtyy) | Tab / I |
| Vaihda asetta | 1–4 tai hiiren rulla |
| Poimi esine / vaihda ase | E |
| Tauko ja asetukset | Esc |

Kaikki tärkeimmät toiminnot voi määrittää uudelleen asetuksista.

## 4. Maailma ja materiaalit

Maailma on ruudukko, jossa jokainen pikseli on materiaali. Simulaatio päivittää vain
**aktiiviset 32×32-lohkot**, joten levossa oleva maailma ei maksa mitään.

| Tyyppi | Materiaalit | Käytös |
|---|---|---|
| Kiinteä | kallio, multa, puu, jää, kristalli, basaltti, hiili, sieni, sammal, metalli, tiili, obsidiaani, tyhjyyskivi, kallioperä (tuhoutumaton) | ei liiku, tuhoutuu räjähdyksissä kovuuden mukaan |
| Jauhe | hiekka, sora, lumi, ruuti, tuhka, irtomulta | putoaa ja valuu kasoiksi, uppoaa nesteisiin |
| Neste | vesi, öljy, happo, laava, myrkkyliete, veri, eetteri | virtaa, kerrostuu tiheyden mukaan |
| Kaasu | höyry, savu, myrkkykaasu | nousee ja haihtuu |
| Erityinen | tuli, palava aine | leviää syttyviin aineisiin, sammuu veteen |

**Reaktiot:** tuli + syttyvä → palaa; vesi + tuli → höyry; laava + vesi → obsidiaani + höyry;
happo syövyttää lähes kaiken; jää ja lumi sulavat kuumuudessa; ruuti räjähtää;
höyry tiivistyy takaisin vedeksi; palanut puu murenee tuhkaksi.

Tuhoutunut kallio murenee soraksi, joka putoaa – luolat sortuvat oikeasti.

## 5. Ulottuvuudet (biomit)

| Ulottuvuus | Tunnelma | Materiaalit | Erikoisuus |
|---|---|---|---|
| **Hämyluolat** | kostea kiviluola | kallio, multa, hiekka, vesi, puutuet, sammal | ensimmäinen kenttä aina täällä |
| **Sienisyvänne** | hehkuvat sienet | sieni, sammal, myrkkyliete | pimeä, valoa antavat sienet |
| **Routaulottuvuus** | jäinen ja valoisa | jää, lumi, vesi | lumi sulaa tulesta |
| **Ahjoulottuvuus** | hehkuva ahjo | basaltti, hiili, laava, öljy | palovaara kaikkialla |
| **Kristalliulottuvuus** | kimaltava | kristalli, kvartsihiekka, happo | kova kallio, happoaltaat |
| **Tyhjyys** | leijuvat saaret tähtien keskellä | tyhjyyskivi, eetteri | matala painovoima |

Kenttägeneraattori: kohinapohjaiset luolat + soluautomaattitasoitus → taattu reitti
alusta porttiin → materiaalitaskut ja suonet → nestealtaat painanteisiin → rakenteet
(puutasot, tiiliraunioit, alttarit aseille) → vihollisten ja esineiden sijoittelu.

## 6. Aseet

Kaikki aseet luodaan proseduraalisesti: tilastot, loitsut ja **ulkonäkö** (varsi, koriste,
kärkikivi väritetään pääloitsun elementin mukaan).

- **Taikasauva** (yhden käden): nopea, 2–8 loitsupaikkaa, jotka loitsitaan järjestyksessä.
  Kuluttaa manaa. Ominaisuudet: loitsuviive, latausaika, hajonta, loitsuja kerralla
  (multicast) ja nopeuskerroin.
- **Taikakeppi** (kaksikätinen): 1–3 loitsupaikkaa. Pidä pohjassa ladataksesi (enintään noin
  1,2 s) ja vapauta. Lataus kasvattaa ammuksen kokoa, vahinkoa ja räjähdyksen sädettä. Hyvä
  kaivamiseen.
- **Juomapullo:** 0–100 yksikköä yhtä nestettä. Kaada, heitä (pullo särkyy) tai juo. Pullo
  täyttyy, kun sen suun upottaa nesteeseen.
- **Miekka** (lähitaistelu): kaarilyönti, joka vahingoittaa vihollisia, torjuu vihollisten
  ammuksia ja leikkaa pehmeää maastoa (multa, puu, sieni, sammal, jää, lumi). Elementtimiekat
  (tuli, jää, happo, tyhjyys) lisäävät efektin.

### Loitsujen sijoittelu

Repussa (Tab) loitsuja raahataan vapaasti sauvojen, keppien ja 16-paikkaisen loitsupussin
välillä. Loitsimisessa ase nostaa paikoista seuraavan loitsun. Ensin kerätään muokkaimet,
kunnes vastaan tulee ammusloitsu, joka saa niiden vaikutukset. Kun viimeinen paikka on
loitsittu, sauva latautuu.

| Muokkain | Vaikutus |
|---|---|
| Tehostus | +50 % vahinko |
| Kiihdytys | +60 % nopeus |
| Hakeutuvuus | ammus hakeutuu vihollisiin |
| Kimmoisuus | +4 kimmahdusta |
| Kaksois-/Kolmoisloitsu | seuraavat 2/3 loitsua lähtevät yhtä aikaa |
| Räjähtävä | lisää räjähdyksen osumaan |
| Lävistävä | läpäisee 3 vihollista |
| Tarkkuus | ei hajontaa |
| Jättiläinen | suurempi ja voimakkaampi ammus |

### Loitsut

| Loitsu | Kuvaus |
|---|---|
| Kipinä | nopea halpa salama |
| Tulipallo | räjähtää liekkeihin, sytyttää |
| Pomppuhelmi | kimpoilee seinistä |
| Jääpiikki | lävistää, jäädyttää veden, sammuttaa tulen |
| Happolima | kaareva lento, roiskii happoa |
| Pommi | sytytinlanka, iso räjähdys |
| Taikaohjus | hakeutuu vihollisiin |
| Meteori | hidas, raskas, tuhoaa paljon maastoa |
| Poraterä | kaivaa tunnelia |
| Vesipallo | luo vettä, sammuttaa |
| Järistys | murentaa kallion soraksi |
| Salama | välitön sahalaitainen säde |

## 7. Viholliset

| Vihollinen | Käytös |
|---|---|
| Lima | hyppii pelaajaa kohti, sävy vaihtelee ulottuvuuden mukaan |
| Siipiö | lentää säntäillen, puree |
| Varjomaagi | pitää etäisyyttä, ampuu pimeyden ammuksia |
| Tulihenki | leijuu, sytyttää ympäristön, räjähtää kuollessaan |
| Kivikolossi | hidas, kestävä, iskee maahan (shokkiaalto murentaa maastoa) |

Vihollisten määrä, kestävyys ja vahinko kasvavat syvyyden mukaan.

### Pomo: Portinvartija

Joka kolmannella tasolla generaattori kaivaa portin eteen ison areenan. Portti on sinetöity,
kunnes Portinvartija (leijuva kivinen vartija, jolla on yksi hehkuva silmä) on kukistettu.
Hyökkäykset ovat sirpaleryöppy, apurien kutsu ja maastoa repivä syöksy. Alle 50 %:n
elämillä pomo raivostuu: se nopeutuu, ampuu tuplaryöppyjä ja sataa ulottuvuuden elementtiä
(tuli, happo, jää tai sirpaleet). Palkintona on kultaa, elämänkristalli, korkeamman tason ase
ja kaksi loitsua. Pomotaistelulla on oma musiikki.

## 8. Eteneminen

- **Siunaukset** portilla (valitse 1/3): esim. +25 maks. elämä, nopeampi manan palautus,
  tulenkestävyys, pidempi leijunta, +20 % loitsuvahinko, verenimu, nopeampi liike,
  räjähdyskestävyys, pidempi miekan ulottuvuus.
- **Elämänkristalli**: parantaa ja nostaa maksimielämää.
- **Loitsukäärö**: uusi loitsu tai muokkain loitsupussiin.
- **Pullot**: satunnaisia nesteitä kentissä (vesi, öljy, happo, Elonneste, Eetteri, …).
- **Kulta**: pisteet (tulevaisuudessa kaupat).

## 9. Tekninen arkkitehtuuri (Godot 4.7, GDScript, GL Compatibility)

```
scripts/
  autoload/   game_state.gd (juoksu, siemen, tallennus), audio.gd
  world/      materials.gd, pixel_world.gd (simulaatio), world_gen.gd, dimensions.gd
  entities/   actor.gd (pikselifysiikka), player.gd, enemy*.gd, projectile.gd, pickup.gd, portal.gd
  combat/     spells.gd, weapon.gd, weapon_gen.gd, weapon_art.gd
  fx/         particles.gd, lighting
  ui/         hud.gd, menut
shaders/      world.gdshader (materiaalien väritys), light.gdshader (pimeys ja valot)
assets/       spritet, fontti, äänet (generoitu skripteillä tools/-kansiossa)
```

- **Simulaatio:** solut `PackedByteArray`-taulukossa (materiaali + väri/elinikä-tavu).
  Ruudukko ladataan GPU:lle RG8-tekstuurina, ja shader värittää materiaalit, reunat,
  nesteiden välkkeen ja tulen.
- **Valaistus:** koko ruudun shader, joka tummentaa luolan ja lisää valot (pelaaja, ammukset,
  räjähdykset) sekä hehkuvien materiaalien (laava, tuli, kristallit) oman valon.
- **Fysiikka:** omat pikselitarkat törmäykset ruudukkoa vasten (askelluskiipeily, nesteiden
  noste ja vastus), ei Godotin fysiikkamoottoria.
- **Determinismi:** kenttä = f(juoksun siemen, kentän numero), joten kentän alun
  tallennukseen riittää siemen ja pelaajan tila.
- **Kesken kentän tallennus:** solutaulukko (zstd-pakattu), pelaajan tila ja sijainti,
  viholliset, esineet, portti ja pomo tallentuvat tiedostoon `user://veleho_world.save`, joka
  poistetaan, kun peliä jatketaan.
- **Asetukset:** `user://settings.cfg`. Äänet kulkevat Music- ja SFX-kanavien kautta.

## 10. Prototyypin rajaus

Mukana:

- kaikki yllä oleva perustasolla, 6 ulottuvuutta, 5 vihollistyyppiä ja pomo
- 12 loitsua ja 10 muokkainta sekä loitsujen vapaa sijoittelu
- sauvat, kepit, miekat ja juomapullot sekä siunaukset
- asetukset ja näppäinten uudelleenmääritys
- tallennus (kentän alku ja kesken kentän) ja permadeath
- äänet ja ambient-musiikki

Myöhemmin: kaupat, useampia pomoja, salaisuudet ja salahuoneet, ohjainohjaus,
nesteiden sekoittuminen pulloissa, tasapainotus.
