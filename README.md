# space_data

Catalogo locale di dati spaziali pubblici. Mette insieme, in file interrogabili, le orbite pubblicate da CelesTrak, i trasmettitori aperti di SatNOGS, i passaggi radio recenti della rete, lo space weather NOAA e i metadati di collezione di Copernicus e del NASA Planetary Data System.

I granuli immagine e i prodotti scientifici restano negli archivi di origine. Qui ci sono gli indici, gli elementi orbitali e i segnali dichiarati.

## Panorama

```bash
python -m spacedata
```

La scheda dello snapshot corrente è [`data/README.md`](data/README.md). Le fonti, le licenze e i limiti d'uso sono in [`docs/fonti.md`](docs/fonti.md). I campi dei JSON sono in [`docs/schema.md`](docs/schema.md). Il modo di aggiornare e di filtrare è in [`docs/uso.md`](docs/uso.md).

## Scheda di un oggetto

```bash
python -m spacedata show --norad 25544
python -m spacedata show --group science
python -m spacedata show --mhz-min 137 --mhz-max 138
python -m spacedata show --name METEOR
```

## Aggiornare

```bash
python -m spacedata collect
python -m spacedata collect --offline
```

`--offline` riscrive il catalogo dai file già scaricati, senza rete. Python 3.11 o successivo, solo libreria standard.

## Repository

| Percorso | Ruolo |
| --- | --- |
| `spacedata/` | Raccolta, fusione del catalogo, interrogazione |
| `data/catalog/` | Orbite, trasmettitori, osservazioni, collezioni, bundle |
| `data/raw/` | Risposte originali, con SHA-256 nel manifest |
| `data/manifest.json` | Provenienza di ogni file |
| `docs/` | Fonti, schema, uso |
| `NOTICE.md` | Attribuzioni delle terze parti |

`collect.py` e `catalog.py` nella radice sono gli stessi comandi, in forma breve.

## Licenze

Il codice di questo repository organizza i dati. Non ne cambia la licenza. Ogni voce di `data/manifest.json` porta il codice della fonte: CelesTrak con attribuzione, SatNOGS in CC BY-SA 4.0, NOAA in pubblico dominio USA, metadati Copernicus e PDS secondo le loro politiche. Il dettaglio è in [`NOTICE.md`](NOTICE.md).

## Lacuna di questo snapshot

I GP `active` e `starlink`, e il SATCAT Starlink, non sono nel campione del 2026-10-12. Un trasferimento interrotto ha fatto rispondere a CelesTrak 403 per due ore, e il SATCAT Starlink è arrivato troncato. Gli altri gruppi tematici ci sono: OneWeb, Kuiper, Qianfan, GEO, GNSS, stazioni, scienza, radioamatori. Per ritentare solo i file mancanti: `python -m spacedata collect --skip-existing`.
