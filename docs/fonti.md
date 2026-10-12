# Fonti

Verifica degli endpoint: 2026-10-12. `python -m spacedata collect` scarica solo le righe segnate «snapshot». Le altre restano documentazione d'uso, perché chiedono un account, sono troppo grandi, o non sono redistribuibili.

Il 2026-07-11 CelesTrak ha esaurito i catalog number a 5 cifre. Da allora i NORAD id nuovi hanno 6 cifre. Il JSON GP li contiene per intero. Il TLE classico a 69 caratteri no: per questo lo snapshot tiene il JSON, non i due righi di testo.

## Orbite

| Fonte | Cosa | Accesso | Snapshot |
| --- | --- | --- | --- |
| [CelesTrak GP](https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=json) | Elementi medi (GP) per gruppo. Parametro `GROUP`, `FORMAT=json`. | HTTPS, senza account. Attribuzione a CelesTrak. Lo stesso `GROUP` riscaricato entro due ore riceve HTTP 403 «has not updated»: i GP si aggiornano ogni due ore. | Sì: tutti i gruppi dell'indice pubblico tranne i tre cataloghi di detriti (`fengyun-1c-debris`, `iridium-33-debris`, `cosmos-2251-debris`). Include `active` quando CelesTrak lo consegna. `goes` non è più una riga dell'indice ma al 2026-10-12 rispondeva ancora ed è nello snapshot. `GROUP=noaa` nello stesso giorno risponde «not found» e non è raccolto. |
| [CelesTrak SATCAT](https://celestrak.org/satcat/records.php?GROUP=stations&FORMAT=json) | Nome, proprietario, lancio, tipo oggetto, stato operativo, periodo, apogeo, perigeo, RCS. | Come sopra. Legenda campi: [SATCAT documentation](https://celestrak.org/satcat/satcat-format.php). | Sì, un file per gruppo tematico. Il dump unico `GROUP=active` è lo stesso insieme, ma la risposta è grande e da questa rete si interrompe a metà: CelesTrak la conta comunque come download e per due ore non la ripete. |
| [Space-Track](https://www.space-track.org/) | Catalogo upstream USA, storico incluso. | Account gratuito e accordo d'uso. La redistribuzione bulk è limitata dall'accordo. | No. Si usa la redistribuzione pubblica di CelesTrak. |

`active` è l'unione. I gruppi tematici (Starlink, GEO, GNSS, radioamatori, scienza, e gli altri elencati in `GP_GROUPS`) restano nello snapshot anche quando `active` risponde `not-modified`, così ogni oggetto porta l'etichetta del gruppo. Un secondo `python -m spacedata collect --skip-existing` non ribatte sugli file già validi.

Codici `ops_status` del SATCAT, come pubblicati da CelesTrak: `+` operativo, `-` non operativo, `P` parzialmente operativo, `B` backup, `S` spare, `X` missione estesa, `D` decaduto, `?` sconosciuto. `object_type` usa `PAY` (payload), `R/B` (stadio), `DEB` (detrito) e le altre sigle del formato SATCAT.

## Segnali

| Fonte | Cosa | Accesso | Snapshot |
| --- | --- | --- | --- |
| [SatNOGS DB satelliti](https://db.satnogs.org/api/satellites/?format=json) | Anagrafica, stato, paese, operatore, NORAD id. | HTTPS, senza account. | Sì, file intero. |
| [SatNOGS DB trasmettitori](https://db.satnogs.org/api/transmitters/?format=json&alive=true) | Downlink, uplink, modo, baud, servizio, coordinamento IARU, uuid. | Come sopra. | Sì, solo `alive=true`. |
| [SatNOGS DB modi](https://db.satnogs.org/api/modes/?format=json) | Elenco modi (`APT`, `BPSK`, `FSK`, …). | Come sopra. | Sì. |
| [SatNOGS DB TLE](https://db.satnogs.org/api/tle/?format=json) | TLE correnti dei satelliti seguiti dal DB, in formato a tre righe. | Come sopra. Circa mezzo megabyte. | Sì, file grezzo. Gli elementi propagabili usati nel catalogo orbite restano i GP JSON di CelesTrak. |
| [SatNOGS Network](https://network.satnogs.org/api/observations/?format=json&status=good&vetted_status=good) | Passaggi ricevuti dalla rete di stazioni. Paginazione a cursore nell'header `Link`. | Come sopra. | Sì, estratto: ultime 24 ore (o `--hours`), al massimo 40 pagine, solo status good e vetted good. Geometria della stazione e fino a 8 URL di frame demodulati. Niente waterfall, niente byte di payload, niente nickname. |
| [AMSAT](https://www.amsat.org/) | Coordinamento e band plan dei satelliti radioamatoriali. | Pagine pubbliche. | No. I trasmettitori già coordinati sono nel DB SatNOGS (`iaru_coordination`). |
| Decoder | [`gr-satellites`](https://github.com/daniestevez/gr-satellites), [`satnogs-decoders`](https://gitlab.com/librespacefoundation/satnogs/satnogs-decoders). | Codice aperto, da compilare in locale. | No. |

Il maintainer SatNOGS descrive i dati di DB e Network come Creative Commons Attribution-ShareAlike 4.0 ([filo sul forum Libre Space](https://community.libre.space/t/tle-and-magnetic-info-from-db/13138)). Il codice dei due progetti è AGPL-3.0: non è venduto in questo repository. Chi ridistribuisce `data/raw/satnogs/` e `data/catalog/signals.json` / `observations.json` resta sotto CC BY-SA 4.0.

Bande che il catalogo rende interrogabili subito, perché i trasmettitori le dichiarano:

- 137–138 MHz: APT/LRPT dei meteorologici in LEO (`python -m spacedata show --mhz-min 137 --mhz-max 138`).
- 145 e 435 MHz: servizio radioamatoriale, beacon universitari, APRS sulla ISS.
- bande GNSS civili: i trasmettitori dei payload di navigazione compaiono nel gruppo `gnss`, non come IQ. Le osservabili RINEX dell'[IGS su CDDIS](https://cddis.nasa.gov/) richiedono un login NASA Earthdata e non sono nello snapshot.

TinyGS è un'altra rete aperta orientata ai beacon LoRa. Non è inclusa: licenza e API non sono state fissate in questo snapshot.

## Space weather

Prodotti NOAA Space Weather Prediction Center, senza chiave, pubblico dominio USA. Gli URL storici `products/solar-wind/plasma-*.json` e `mag-*.json` al 2026-10-12 rispondono 404. Lo snapshot usa i percorsi vivi:

| File | URL |
| --- | --- |
| `kp-index.json` | `https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json` |
| `kp-forecast.json` | `https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json` |
| `goes-xray-6h.json` | `https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json` |
| `f107.json` | `https://services.swpc.noaa.gov/json/f107_cm_flux.json` |
| `rtsw-mag-1m.json` | `https://services.swpc.noaa.gov/json/rtsw/rtsw_mag_1m.json` |
| `rtsw-wind-1m.json` | `https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json` |
| `propagated-solar-wind-1h.json` | `https://services.swpc.noaa.gov/products/geospace/propagated-solar-wind-1-hour.json` |
| `summary-solar-wind-speed.json` | `https://services.swpc.noaa.gov/products/summary/solar-wind-speed.json` |
| `summary-10cm-flux.json` | `https://services.swpc.noaa.gov/products/summary/10cm-flux.json` |
| `noaa-scales.json` | `https://services.swpc.noaa.gov/products/noaa-scales.json` |

RTSW è il vento solare in tempo reale (DSCOVR/ACE) a 1 minuto: campo magnetico e plasma. Il file propagato a 1 ora è la stima geospace. Kp è l'indice planetario a 3 ore. F10.7 è il flusso radio solare a 10,7 cm, lo stesso indice che entra nei modelli di densità atmosferica insieme al BSTAR dei GP.

Il portale space weather ESA è complementare e non è scaricato.

## Osservazione della Terra

Lo snapshot contiene il catalogo, non le scene.

| Fonte | Cosa | Accesso | Snapshot |
| --- | --- | --- | --- |
| [Copernicus STAC](https://catalogue.dataspace.copernicus.eu/stac/collections) | Collezioni del Data Space Ecosystem, paginate (`rel=next`). Al 2026-10-12 il catalogo dichiara centinaia di collezioni. | Root STAC in lettura. Il download del granulo chiede un account Data Space. | Sì: id, titolo, descrizione breve, `license`, eventuale link di licenza, bbox, intervallo temporale, keyword. |
| [Browser Copernicus](https://browser.dataspace.copernicus.eu/) | Ispezione interattiva delle scene. | Account per il download. | No. |
| [NASA CMR](https://cmr.earthdata.nasa.gov/search/collections.json) | Discovery di Landsat, MODIS, VIIRS, raccolte ESA ospitate. | Ricerca pubblica. I granuli NASA spesso passano da Earthdata. | No. Esempio: `?keyword=Sentinel-2&page_size=5`. |
| [USGS EarthExplorer](https://earthexplorer.usgs.gov/) | Landsat e archivi USGS. | Account gratuito per il download. Pubblico dominio USA sui prodotti Landsat. | No. |
| PRISMA (ASI) | Iperspettrale italiano. | Accesso scientifico su proposta. | No. |
| COSMO-SkyMed | SAR dual-use italiano. | Non è open data. | No. |

Sentinel-1 (SAR), Sentinel-2 (ottico), Sentinel-3 e Sentinel-5P ricadono nella politica free-and-open di Copernicus, con attribuzione. Le collezioni *contributing mission* nello stesso STAC hanno licenze diverse: il campo `license` dello snapshot è la fonte, non una frase unica per tutte.

## Archivi scientifici

| Fonte | Cosa | Accesso | Snapshot |
| --- | --- | --- | --- |
| [NASA PDS search](https://pds.nasa.gov/services/search/search?q=product_class:Product_Bundle&wt=json&rows=1) | Indice Solr dei bundle PDS4. | Ricerca pubblica. I prodotti si citano con il LID (`urn:nasa:pds:…`). | Sì: lid, titolo, tipo, agenzia, anno, descrizione breve. |
| [NAIF SPICE](https://naif.jpl.nasa.gov/naif/) | Kernel di traiettoria, assetto e tempi delle missioni. | Download pubblico per missione. | No. |
| [MAST](https://mast.stsci.edu/) | Hubble, JWST, Kepler, TESS. | Ricerca pubblica, download anche grande. | No. |
| [Archivio Gaia](https://gea.esac.esa.int/archive/) | Catalogo astrometrico ESA. | Interrogazione pubblica, citazione obbligatoria secondo la data release. | No. |
| SDO / SOHO | Sole, immagini e serie temporali. | Portali NASA/ESA. | No. Il flusso X di GOES nello SWPC copre il monitoraggio in tempo reale, non l'archivio di immagine. |

## Limiti d'uso

Lo snapshot serve a studiare orbite, piani di frequenza pubblicati e metadati di archivio.

- I frame demodulati restano sugli URL SatNOGS. Scaricarli in massa tira dentro nominativi e, a volte, telemetria che il team del satellite non ha documentato come open. Il DB SatNOGS stesso ricorda che senza lo schema del team l'esadecimale non si decodifica.
- Le coordinate di stazione sono quelle pubblicate dall'operatore insieme al passaggio. Servono a ricostruire la geometria. Il nome utente no, e non è copiato.
- Downlink utente di costellazioni commerciali, telemetria non pubblica e payload cifrati non sono materiale di questa raccolta. Decifrarli non è un uso dei dati pubblici descritti qui.
- EU SST operativo non è un catalogo aperto. Per le effemeridi pubbliche basta CelesTrak.
- Rifare la raccolta in continuo contro CelesTrak o SatNOGS non è un uso corretto di quei servizi. Lo snapshot è un campione datato: la data è `retrieved_at` in `data/catalog/summary.json`.
