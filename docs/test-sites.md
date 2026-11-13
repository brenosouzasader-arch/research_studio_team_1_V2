# Test sites for Roof Surplus Match

13 November 2026

## Short answer

Your teammate is right that Bruc 59 is a weak host. It is a residential building (12 flats, 2 shops), so it has no weekday/weekend gap to sell. Keep it as a check on the roof and solar steps.

UPC Campus Nord is a fair pick for **demand data**, but it has two problems. The raw SIRENA data is not public (only yearly PDF reports are), and a university is not quite our user (a large property owner selling surplus). We found four other zones worth testing. Our recommendation is to make **Poblenou around the Quatre Cantons school** the main test zone. A real community already works there the way our model does, so we can check our tool against real numbers.

## Ranked test zones

| # | Zone | Host type | Why it fits | Main risk |
|---|---|---|---|---|
| 1 | Poblenou / 22@ (Quatre Cantons, CEP9) | School + 22@ offices (e.g. MediaTIC) | A working community already shares a school roof's output with 30 homes and 4 public buildings. Offices close weekends and August. Dense flats nearby. | Office meter data needs a building manager's OK |
| 2 | UPC Campus Diagonal Nord | University offices (Nexus II, Vèrtex, Til·lers) | 15-min metering (SIRENA). Campus already has 250 kWp PV with only ~50% used on site, so surplus is real. | Raw data needs UPC permission; high baseload (data centre in Vèrtex) |
| 3 | Port Olímpic and Anella Olímpica (BSM) | Event and leisure venues owned by a city company | Huge roofs (Port Olímpic 3,560 m2, ~825 MWh/yr; Anella Olímpica ~791 MWh/yr). Event-driven use, so many idle hours. Vila Olímpica flats are next to Port Olímpic. | Few flats within 500 m of Montjuïc; owner is public |
| 4 | The 10 municipal roofs ceded to energy communities | Civic centres, libraries, elderly centres (one per district) | Tender closed 4 Nov 2026, so these become real communities soon. Two are near our past areas: Espai de gent gran Sant Antoni (Eixample) and Biblioteca Montserrat Abelló (Les Corts, near UPC). | Small roofs; hosts use much of their own power on weekdays |
| 5 | Our Eixample focus area (Pg. de Gràcia blocks) | Offices and shops on Pg. de Gràcia / Pau Claris | All our data is already there (197 plots ranked). Most hosts in our step 5c run were on Pg. de Gràcia, which is office-heavy. Illa Eficient (Gran Via/Viladomat/Diputació/Calàbria, 22 buildings) is a residential solar cooperative to compare the flats side with. | No metered data for the offices |

## Details per zone

### 1. Poblenou around Quatre Cantons (recommended main zone)

- The Quatre Cantons school roof has 58.32 kWp (108 panels) making about 73,750 kWh a year. Installed late 2021, paid by the city (about 94,000 EUR).
- Output is shared between two schools (Quatre Cantons and Maria Espinalt), Can Felipa civic centre, the Llevant fire station and 30 households. Each household uses 400 to 700 kWh a year from it and saves about 120 to 140 EUR (CEP9 presentation).
- The city studied 13 roofs in the area and built only one. CEP9 now aims for 2 km and more than 1,500 kWp, so there are more host roofs our tool could rank.
- 22@ has the office hosts our concept needs (MediaTIC at Roc Boronat 117, ~11,300 m2, and many converted industrial buildings with big flat roofs), mixed with flats.
- **Why it is the best test:** we can run our pipeline on the Quatre Cantons roof and compare our predicted output, member count and savings with the real ones. No other site gives us that check.

### 2. UPC Campus Diagonal Nord (best for training data)

- The SIRENA 2025 report (May 2026) is a public PDF with yearly figures only. No downloadable data was found, so the 15-min series needs a request to UPC (Álvaro Luna, as your teammate suggests).
- The report lists a 170 kWp and an 80.18 kWp plant on the Aularis buildings of Campus Diagonal Nord with **50% self-consumption**. About half the output already leaves those buildings, which is exactly the surplus our tool is about. This is stronger evidence than anything we have for Nexus II.
- UPC's PV made 858,920 kWh in 2025, only 2.17% of its use, so most buildings use all their own output. Only lightly used buildings (teaching blocks in summer) give surplus.
- Use it to train and test the demand model, and keep the host question open.

### 3. BSM venues (closest to our "big owner")

- Barcelona de Serveis Municipals is adding 4,200 panels on 9,700 m2 (almost 2 MW) within two years of July 2024.
- Port Olímpic (Balcó Gastronòmic): 3,560 m2, over 825,000 kWh a year, already described as the city's largest shared self-consumption install. Anella Olímpica: 2,877 m2, about 791,060 kWh a year (Palau Sant Jordi 2,316 m2). Zoo and Barcelona Nord bus station under study.
- One owner with a lot of roof and use that comes in bursts.

### 4. Municipal roofs for energy communities

- Sites: Centre Cívic Barceloneta, Espai de gent gran Sant Antoni, Centre Cívic Font de la Guatlla, Biblioteca Montserrat Abelló, Centre de Serveis Socials Sant Gervasi, EBM L'Enxaneta, Centre Cívic Casa Groga, Ateneu Popular 9 Barris, Centre Cívic Baró de Viver, Casal de gent gran Parc del Clot.
- The city's pergola scheme (Ronda de Dalt, pl. Alfons Comín) charges 70 EUR a year per 500 W share, open to homes and businesses within 1 km. A useful **price benchmark** for our fixed agreed price.

### 5. Markets: a useful "no" case

- 17 municipal markets have panels (goal 31). Mercat de Sants uses about 91% on site; Sant Antoni 100%. Fridges run all day, so markets have almost no surplus.
- Worth running through the tool to show it can conclude "sharing does not pay here".

## What to do next

1. Run steps 1 to 4 on the Quatre Cantons school roof and compare with the real 58 kWp and 73,750 kWh/yr.
2. Pick 3 to 5 22@ office roofs near the school and run the surplus map with the office demand profile.
3. Email UPC for SIRENA 15-min data (Nexus II, Vèrtex, Til·lers, Aularis) to train the demand model. Use Building Data Genome 2 until it arrives.
4. Use the Open Data BCN electricity dataset (postal code x sector x time band) to check office and home profiles for the test zones.

The 22@ offices and Campus Nord buildings still need Catastro and LiDAR checks before we can say their roofs are big enough. LiDAR sheets for those areas are not downloaded yet; we only have the Eixample sheets 430582 and 430583.

## Sources

- [CEP9 Poblenou energy community presentation](https://elpoblenou.cat/wp-content/uploads/2024/10/presentacio-CEP9_v2.pptx.pdf)
- [Guardian: Barcelona school and residents create solar energy community (2022)](https://www.pressreader.com/usa/the-guardian-usa/20220725/281711208390346)
- [UPC SIRENA global report 2025](https://sostenible.upc.edu/ca/reptes/documents-pla-2030/informe-sirena-global-2025.pdf)
- [BSM venues to add 10,000 m2 of panels](https://www.sostenible.cat/print/noticia/els-equipaments-de-bsm-incorporaran-10000-metres-quadrats-de-plaques-solars)
- [Barcelona cedes 10 roofs to energy communities (Sept 2026)](https://www.energias-renovables.com/autoconsumo/barcelona-impulsa-las-comunidades-energ-ticas-con-20260928/)
- [Municipal shared self-consumption rules (2023)](https://www.sostenible.cat/print/noticia/la-ciutadania-de-barcelona-podra-accedir-a-lautoconsum-municipal-compartit)
- [Mercat de Sants and Sant Antoni panels (2025)](https://beteve.cat/medi-ambient/mercat-sants-sant-antoni-estrenen-plaques-fotovoltaiques/)
- [City plan to triple municipal PV by 2027](https://www.sostenible.cat/print/noticia/barcelona-aprova-mesures-per-triplicar-la-potencia-fotovoltaica-municipal-fins-al-2027)
- [Illa Eficient, 22 Eixample buildings in a solar cooperative (2021)](https://es.ara.cat/sociedad/22-edificios-eixample-alian-cooperativa-energetica-fotovoltaica_1_4133725.amp.html)
- [Open Data BCN electricity consumption](https://opendata-ajuntament.barcelona.cat/data/dataset/consum-electricitat-bcn)
