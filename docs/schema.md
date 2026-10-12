# Schema del catalogo

I file in `data/raw/` sono il corpo della risposta, senza trasformazione, così il SHA-256 nel manifest coincide con i byte scaricati. I file in `data/catalog/` sono derivati. Le osservazioni, le collezioni STAC e i bundle PDS nascono già derivati: uniscono più pagine e scartano campi.

## `data/catalog/orbits.json`

Un oggetto per `norad_cat_id`. L'insieme è l'unione dei gruppi GP scaricati e dei record SATCAT `active` che non compaiono nei GP. I satelliti SatNOGS privi di elementi (tipicamente già rientrati) non vengono aggiunti; se il NORAD è già presente, arricchiscono la scheda.

| Campo | Origine | Note |
| --- | --- | --- |
| `norad_cat_id` | GP `NORAD_CAT_ID` | Intero. Può avere 6 cifre. |
| `object_name`, `object_id` | GP, altrimenti SATCAT | `object_id` è il designatore COSPAR, per esempio `1998-067A`. |
| `epoch` | GP `EPOCH` | Se il NORAD compare in più gruppi, resta l'epoca più recente e con essa gli elementi. |
| `mean_motion` | GP | Rivoluzioni per giorno. |
| `eccentricity` | GP | |
| `inclination_deg`, `raan_deg`, `arg_of_perigee_deg`, `mean_anomaly_deg` | GP | Gradi. |
| `bstar`, `mean_motion_dot`, `mean_motion_ddot` | GP | Trascinamento e derivate del moto medio, quando il JSON li include. |
| `rev_at_epoch`, `classification` | GP | `classification` è il carattere di classificazione del set (`U` pubblico). |
| `groups` | nome del `GROUP` GP | Include `active` quando l'oggetto sta nel catalogo attivo. `satcat` compare solo se il record arriva dal SATCAT senza GP. |
| `owner`, `launch_date`, `launch_site`, `object_type`, `ops_status` | SATCAT | `ops_status` è il codice CelesTrak, vedi `docs/fonti.md`. |
| `period_min`, `apogee_km`, `perigee_km`, `rcs`, `orbit_type`, `decay_date` | SATCAT | Apogeo e perigeo in km. |
| `satnogs_id`, `satnogs_status`, `countries`, `operator`, `names` | SatNOGS DB | Se per lo stesso NORAD ci sono più schede, resta quella con stato in orbita. La stringa `None` dell'API diventa JSON `null`. |

## `data/catalog/signals.json`

Un oggetto per trasmettitore SatNOGS con `alive` vero. Ordinato per `downlink_hz`.

| Campo | Note |
| --- | --- |
| `uuid` | Identificatore del trasmettitore nel DB. È la chiave usata anche nelle osservazioni (`transmitter_uuid`). |
| `norad_cat_id`, `sat_id`, `name` | `name` arriva dalla scheda SatNOGS, altrimenti dall'orbita. |
| `description` | Testo del DB, per esempio `APRS` o `LRPT`. |
| `downlink_hz`, `uplink_hz` | Hertz, estremi bassi dichiarati. |
| `mode`, `uplink_mode`, `baud` | `mode` è il nome, non l'id numerico. L'elenco id sta in `data/raw/satnogs/modes.json`. |
| `service` | Per esempio `Amateur`. |
| `status`, `unconfirmed` | Stato della scheda trasmettitore. |
| `iaru_coordination` | Riferimento di coordinamento, quando c'è. |
| `invert` | Inversione di spettro dichiarata, per i modi che la usano. |
| `citation` | URL di citazione inserito da chi ha proposto il trasmettitore. |

## `data/catalog/observations.json`

Passaggi SatNOGS `status=good` e `vetted_status=good`, nella finestra chiesta alla raccolta.

| Campo | Note |
| --- | --- |
| `id`, `start`, `end` | Id Network e intervallo UTC del passaggio. |
| `norad_cat_id`, `sat_id`, `transmitter_uuid` | Collegamento a orbita e trasmettitore. |
| `mode`, `downlink_hz`, `baud` | Copiati dalla scheda trasmettitore al momento dell'osservazione. |
| `center_frequency`, `observation_frequency` | Frequenza a cui la stazione ha ascoltato. |
| `ground_station`, `station_name`, `station_lat`, `station_lng`, `station_alt` | Stazione. Latitudine e longitudine in gradi, quota in metri, come pubblicate dalla rete. |
| `max_altitude`, `rise_azimuth`, `set_azimuth` | Geometria del passaggio, gradi. |
| `status` | Qui è `good`, per il filtro della raccolta. |
| `demod_count` | Numero di frame demodulati annunciati. |
| `demod_urls` | Al massimo 8 URL. Il conteggio intero resta in `demod_count`. |
| `archive_url` | Pagina o archivio dell'osservazione, se la rete lo manda. |
| `has_waterfall` | Vero se l'osservazione ha un waterfall. L'immagine non è scaricata. |

Campi presenti nella API e non copiati: `observer`, `vetted_user`, `client_metadata`, i tre righi TLE (gli elementi stanno nel GP), `payload`.

## `data/catalog/stac-collections.json`

| Campo | Note |
| --- | --- |
| `id`, `title` | Identificatore STAC e titolo. |
| `description` | Testo ripulito, al massimo 500 caratteri. |
| `license`, `license_href` | Valore STAC e, se c'è, il link `rel=license`. `other` significa che i termini stanno fuori dal campo, spesso su quel link. |
| `keywords` | Lista della collezione. |
| `bbox` | Primo bbox dichiarato, `[ovest, sud, est, nord]`. |
| `temporal` | Primo intervallo `[inizio, fine]`. `fine` può essere null se la collezione è aperta. |

## `data/catalog/pds-bundles.json`

| Campo | Note |
| --- | --- |
| `lid` | Logical identifier, da citare. |
| `title`, `bundle_type`, `agency`, `year` | Metadati brevi. |
| `description` | Testo ripulito, al massimo 400 caratteri. |

## `data/manifest.json` e `summary.json`

Ogni voce del manifest ha `id`, `url`, `retrieved_at`, `sha256`, `bytes`, `records`, `path`, `license`, `kind`, `status`, `error`.

`kind` vale `upstream` quando il file è il corpo originale, `extracted` quando è stato ricostruito da più pagine. `status` vale `ok`, `cached` (file già presente, con `--skip-existing` o `--offline`), `not-modified` (CelesTrak ha rifiutato un gruppo già scaricato nelle ultime due ore), `absent` (manca il file e la corsa è `--offline`), `partial` (qualcosa è stato salvato e una pagina successiva è fallita) o `error:<codice http>`.

`data/raw/satnogs/tle.json` è il dump TLE del DB (righe `tle0`/`tle1`/`tle2`). Non è fuso in `orbits.json`: gli elementi di quel catalogo arrivano dai GP.

`summary.json` ripete i conteggi per gruppo GP e per modo radio, più la finestra temporale delle osservazioni.
