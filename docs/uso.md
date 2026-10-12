# Uso

I comandi si lanciano dalla radice del repository.

## Leggere

`python -m spacedata` stampa il panorama: conteggi, i gruppi più numerosi, i modi radio più frequenti, le lacune.

`python -m spacedata show` accetta un filtro. Senza filtri è lo stesso panorama.

| Opzione | Effetto |
| --- | --- |
| `--norad 25544` | Scheda: orbita, identità, trasmettitori, osservazioni nello snapshot |
| `--group amateur` | Oggetti etichettati con quel gruppo GP |
| `--name METEOR` | Sottostringa del nome, senza distinzione di maiuscole |
| `--mode APT` | Trasmettitori di quel modo SatNOGS |
| `--mhz-min` / `--mhz-max` | Downlink in MHz |
| `--limit 40` | Righe da stampare. Il totale dei match è sempre la prima riga |

`--mode` e gli estremi in MHz elencano trasmettitori. `--group` da solo elenca orbite. Insieme, tengono i trasmettitori il cui NORAD sta in quel gruppo.

`python catalog.py` è lo stesso ingresso.

## Aggiornare

`python -m spacedata collect` riscarica le fonti e sovrascrive `data/raw/`, `data/catalog/`, `data/manifest.json` e `data/README.md`. Tra una richiesta e l'altra aspetta: 1 secondo su CelesTrak, 0,5 su SatNOGS. Lo User-Agent è `space_data/0.1`. Non accorciare quelle pause per lanciare la raccolta in loop.

| Opzione | Effetto |
| --- | --- |
| `--hours 24` | Finestra delle osservazioni SatNOGS vetted-good |
| `--max-obs-pages 40` | Tetto di pagine. Si ferma prima se la finestra è già coperta |
| `--skip-existing` | Tiene un JSON già presente e valido, scarica il resto |
| `--offline` | Nessuna rete. Ricostruisce il catalogo e segna `absent` i file mancanti |

Esce con codice 1 se una fonte fallisce. Il catalogo viene comunque scritto con quello che è arrivato. `cached`, `not-modified` e `absent` non sono errori. `not-modified` è il 403 di CelesTrak quando lo stesso gruppo risulta già scaricato nelle ultime due ore.

`python collect.py` è lo stesso ingresso.

## Dove stanno i dati

| Percorso | Contenuto |
| --- | --- |
| `data/raw/celestrak/` | GP e SATCAT, un file per gruppo |
| `data/raw/satnogs/` | Satelliti, trasmettitori vivi, modi, TLE |
| `data/raw/swpc/` | Prodotti NOAA SWPC |
| `data/catalog/orbits.json` | Un oggetto per NORAD |
| `data/catalog/signals.json` | Trasmettitori vivi |
| `data/catalog/observations.json` | Passaggi della finestra |
| `data/catalog/stac-collections.json` | Collezioni Copernicus |
| `data/catalog/pds-bundles.json` | Bundle PDS |
| `data/catalog/summary.json` | Conteggi usati dal panorama |
| `data/manifest.json` | URL, ora, SHA-256, byte, licenza, esito |

I byte in `data/raw/` sono la risposta originale quando `kind` nel manifest è `upstream`. Osservazioni, STAC e PDS sono `extracted`: più pagine, campi ridotti.
