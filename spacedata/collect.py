#!/usr/bin/env python3
"""Download a bounded snapshot of public space catalogs into data/.

Stdlib only. One run overwrites data/raw, data/catalog and data/README.md.
Be polite: CelesTrak and SatNOGS are volunteer-scale services, so the
client waits between requests and sends an identifying User-Agent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from spacedata import build_catalog as catalog
from spacedata.paths import CATALOG, DATA, RAW, ROOT

USER_AGENT = "space_data/0.1 (personal research snapshot)"

# Public GP groups from the CelesTrak index, minus the three debris catalogs
# (fengyun-1c-debris, iridium-33-debris, cosmos-2251-debris): those are large
# fragment lists and are not part of this snapshot.
# `active` is the full catalog. CelesTrak answers 403 "has not updated" when
# the same GROUP was fetched in the last two hours, so a repeat run records
# not-modified instead of failing. Catalog numbers gained a 6th digit on
# 2026-07-11; the JSON GP keeps them intact.
GP_GROUPS = (
    "active",
    "last-30-days",
    "stations",
    "visual",
    "analyst",
    "weather",
    "goes",
    "resource",
    "sar",
    "sarsat",
    "dmc",
    "tdrss",
    "argos",
    "planet",
    "spire",
    "geo",
    "intelsat",
    "ses",
    "eutelsat",
    "telesat",
    "starlink",
    "oneweb",
    "qianfan",
    "hulianwang",
    "kuiper",
    "iridium-NEXT",
    "orbcomm",
    "globalstar",
    "amateur",
    "satnogs",
    "x-comm",
    "other-comm",
    "gnss",
    "gps-ops",
    "glo-ops",
    "galileo",
    "beidou",
    "sbas",
    "science",
    "geodetic",
    "engineering",
    "education",
    "military",
    "radar",
    "cubesat",
)

SWPC_PRODUCTS = (
    ("kp-index", "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"),
    (
        "kp-forecast",
        "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json",
    ),
    ("goes-xray-6h", "https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json"),
    ("f107", "https://services.swpc.noaa.gov/json/f107_cm_flux.json"),
    ("rtsw-mag-1m", "https://services.swpc.noaa.gov/json/rtsw/rtsw_mag_1m.json"),
    ("rtsw-wind-1m", "https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json"),
    (
        "propagated-solar-wind-1h",
        "https://services.swpc.noaa.gov/products/geospace/propagated-solar-wind-1-hour.json",
    ),
    (
        "summary-solar-wind-speed",
        "https://services.swpc.noaa.gov/products/summary/solar-wind-speed.json",
    ),
    ("summary-10cm-flux", "https://services.swpc.noaa.gov/products/summary/10cm-flux.json"),
    ("noaa-scales", "https://services.swpc.noaa.gov/products/noaa-scales.json"),
)

LICENSES = {
    "celestrak": "celestrak-attribution",
    "satnogs": "cc-by-sa-4.0",
    "swpc": "us-gov-public-domain",
    "copernicus": "copernicus-catalog-metadata",
    "pds": "nasa-pds",
}


class FetchError(Exception):
    def __init__(self, url, status, detail):
        super().__init__(f"{status} {url} {detail[:180]}")
        self.url = url
        self.status = status
        self.detail = detail


class Response:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self.body = body


def log(message):
    print(message, file=sys.stderr, flush=True)


def iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def delay_for(url):
    host = urllib.parse.urlparse(url).netloc
    if "celestrak.org" in host:
        return 1.0
    if "satnogs.org" in host:
        return 0.5
    return 0.25


def fetch(url, timeout=120, attempts=2):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json, */*;q=0.1"},
    )
    last = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
                headers = {key.lower(): value for key, value in response.headers.items()}
                return Response(response.status, headers, body)
        except urllib.error.HTTPError as exc:
            detail = exc.read(400).decode("utf-8", "replace")
            last = FetchError(url, exc.code, detail)
            if exc.code not in {429, 500, 502, 503, 504}:
                raise last from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            reason = getattr(exc, "reason", exc)
            last = FetchError(url, None, str(reason))
        if attempt + 1 < attempts:
            time.sleep(2 * (attempt + 1))
    raise last


def polite_fetch(url):
    try:
        return fetch(url), None
    except FetchError as exc:
        return None, exc
    finally:
        time.sleep(delay_for(url))


def save_bytes(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_bytes(body)
    temporary.replace(path)


def dump_json(path, obj, pretty=False):
    if pretty:
        text = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    else:
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"
    data = text.encode()
    save_bytes(path, data)
    return data


def rel(path):
    return str(path.relative_to(ROOT))


def entry_ok(entry_id, url, path, body, records, license_id, kind):
    return {
        "id": entry_id,
        "url": url,
        "retrieved_at": iso_now(),
        "sha256": hashlib.sha256(body).hexdigest() if body is not None else None,
        "bytes": len(body) if body is not None else None,
        "records": records,
        "path": rel(path) if path is not None else None,
        "license": license_id,
        "kind": kind,
        "status": "ok",
        "error": None,
    }


def entry_error(entry_id, url, license_id, exc):
    status = exc.status if isinstance(exc, FetchError) else None
    return {
        "id": entry_id,
        "url": url,
        "retrieved_at": iso_now(),
        "sha256": None,
        "bytes": None,
        "records": None,
        "path": None,
        "license": license_id,
        "kind": "upstream",
        "status": f"error:{status}" if status else "error",
        "error": str(exc),
    }


def is_not_modified(exc):
    """CelesTrak 403 when this GROUP was already pulled within two hours."""
    return (
        isinstance(exc, FetchError)
        and exc.status == 403
        and "has not updated" in (exc.detail or "").lower()
    )


def entry_not_modified(entry_id, url, license_id, exc):
    record = entry_error(entry_id, url, license_id, exc)
    record["status"] = "not-modified"
    return record


def load_cached(path):
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def cached_entry(entry_id, url, path, payload, license_id, kind):
    body = path.read_bytes()
    stamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    record = entry_ok(
        entry_id,
        url,
        path,
        body,
        catalog.count_records(payload),
        license_id,
        kind,
    )
    record["status"] = "cached"
    record["retrieved_at"] = stamp
    return record


def entry_absent(entry_id, url, license_id):
    record = entry_error(entry_id, url, license_id, FetchError(url, None, "file assente"))
    record["status"] = "absent"
    record["error"] = None
    return record


def ok_status(status):
    return status in {"ok", "cached", "not-modified", "absent"}


def load_json_bytes(body, url):
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise FetchError(url, 200, f"JSON non valido: {exc}") from exc


def collect_gp(manifest, skip_existing, offline):
    grouped = {}
    for group in GP_GROUPS:
        url = f"https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=json"
        entry_id = f"celestrak-gp-{group}"
        path = RAW / "celestrak" / f"gp-{group}.json"
        if skip_existing:
            cached = load_cached(path)
            if isinstance(cached, list):
                grouped[group] = cached
                manifest.append(
                    cached_entry(entry_id, url, path, cached, LICENSES["celestrak"], "upstream")
                )
                log(f"GP {group} in cache ({len(cached)})")
                continue
        if offline:
            log(f"GP {group} assente")
            manifest.append(entry_absent(entry_id, url, LICENSES["celestrak"]))
            continue
        log(f"GP {group}")
        response, error = polite_fetch(url)
        if error and is_not_modified(error):
            log("  non modificato nelle ultime due ore, salto")
            manifest.append(entry_not_modified(entry_id, url, LICENSES["celestrak"], error))
            continue
        if error:
            log(f"  errore: {error}")
            manifest.append(entry_error(entry_id, url, LICENSES["celestrak"], error))
            continue
        try:
            rows = load_json_bytes(response.body, url)
            if not isinstance(rows, list):
                raise FetchError(url, response.status, "atteso un array JSON")
        except FetchError as exc:
            log(f"  errore: {exc}")
            manifest.append(entry_error(entry_id, url, LICENSES["celestrak"], exc))
            continue
        save_bytes(path, response.body)
        grouped[group] = rows
        manifest.append(
            entry_ok(
                entry_id,
                url,
                path,
                response.body,
                len(rows),
                LICENSES["celestrak"],
                "upstream",
            )
        )
        log(f"  {len(rows)} oggetti, {len(response.body)} byte")
    return grouped


def collect_satcat(manifest, skip_existing, offline):
    """SATCAT per thematic group.

    The single GROUP=active query is a multi-megabyte response that stalls
    from this network before the body finishes, and CelesTrak then treats
    the attempt as a successful download for two hours. The thematic files
    are small and cover the same objects we tag in the GP groups.
    """
    merged = []
    seen = set()
    for group in GP_GROUPS:
        # `active` is the giant dump that stalls. `analyst` objects are
        # CelesTrak estimates and are not rows of the public SATCAT.
        if group in {"active", "analyst"}:
            continue
        url = f"https://celestrak.org/satcat/records.php?GROUP={group}&FORMAT=json"
        entry_id = f"celestrak-satcat-{group}"
        path = RAW / "celestrak" / f"satcat-{group}.json"
        rows = None
        if skip_existing:
            cached = load_cached(path)
            if isinstance(cached, list):
                rows = cached
                manifest.append(
                    cached_entry(entry_id, url, path, cached, LICENSES["celestrak"], "upstream")
                )
                log(f"SATCAT {group} in cache ({len(cached)})")
        if rows is None and offline:
            log(f"SATCAT {group} assente")
            manifest.append(entry_absent(entry_id, url, LICENSES["celestrak"]))
            continue
        if rows is None:
            log(f"SATCAT {group}")
            response, error = polite_fetch(url)
            if error and is_not_modified(error):
                log("  non modificato nelle ultime due ore, salto")
                manifest.append(entry_not_modified(entry_id, url, LICENSES["celestrak"], error))
                continue
            if error:
                log(f"  errore: {error}")
                manifest.append(entry_error(entry_id, url, LICENSES["celestrak"], error))
                continue
            try:
                rows = load_json_bytes(response.body, url)
                if not isinstance(rows, list):
                    raise FetchError(url, response.status, "atteso un array JSON")
            except FetchError as exc:
                log(f"  errore: {exc}")
                manifest.append(entry_error(entry_id, url, LICENSES["celestrak"], exc))
                continue
            save_bytes(path, response.body)
            manifest.append(
                entry_ok(
                    entry_id,
                    url,
                    path,
                    response.body,
                    len(rows),
                    LICENSES["celestrak"],
                    "upstream",
                )
            )
            log(f"  {len(rows)} record, {len(response.body)} byte")
        for row in rows:
            norad = catalog.as_int(row.get("NORAD_CAT_ID"))
            if norad is None or norad in seen:
                continue
            seen.add(norad)
            merged.append(row)
    log(f"SATCAT unito: {len(merged)} oggetti")
    return merged


def collect_json_list(manifest, entry_id, url, path, license_id, skip_existing, offline):
    if skip_existing or offline:
        cached = load_cached(path)
        if cached is not None:
            manifest.append(cached_entry(entry_id, url, path, cached, license_id, "upstream"))
            log(f"{entry_id} in cache")
            return cached if isinstance(cached, list) else []
    if offline:
        log(f"{entry_id} assente")
        manifest.append(entry_absent(entry_id, url, license_id))
        return []
    log(entry_id)
    response, error = polite_fetch(url)
    if error:
        log(f"  errore: {error}")
        manifest.append(entry_error(entry_id, url, license_id, error))
        return []
    try:
        payload = load_json_bytes(response.body, url)
    except FetchError as exc:
        manifest.append(entry_error(entry_id, url, license_id, exc))
        return []
    save_bytes(path, response.body)
    records = catalog.count_records(payload)
    manifest.append(entry_ok(entry_id, url, path, response.body, records, license_id, "upstream"))
    log(f"  {records} record, {len(response.body)} byte")
    return payload if isinstance(payload, list) else []


def collect_swpc(manifest, skip_existing, offline):
    for name, url in SWPC_PRODUCTS:
        collect_json_list(
            manifest,
            f"swpc-{name}",
            url,
            RAW / "swpc" / f"{name}.json",
            LICENSES["swpc"],
            skip_existing,
            offline,
        )


def collect_observations(manifest, hours, max_pages, skip_existing, offline):
    path = CATALOG / "observations.json"
    start_url = (
        "https://network.satnogs.org/api/observations/"
        "?format=json&status=good&vetted_status=good"
    )
    if skip_existing:
        cached = load_cached(path)
        if isinstance(cached, list):
            manifest.append(
                cached_entry(
                    "satnogs-observations-good",
                    start_url,
                    path,
                    cached,
                    LICENSES["satnogs"],
                    "extracted",
                )
            )
            log(f"osservazioni in cache ({len(cached)})")
            return cached
    if offline:
        log("osservazioni assenti")
        manifest.append(entry_absent("satnogs-observations-good", start_url, LICENSES["satnogs"]))
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    url = start_url
    kept = []
    pages = 0
    seen = set()
    error = None
    log(f"SatNOGS observations, ultime {hours:g} h, max {max_pages} pagine")
    while url and pages < max_pages and url not in seen:
        seen.add(url)
        response, error = polite_fetch(url)
        pages += 1
        if error:
            log(f"  errore pagina {pages}: {error}")
            break
        try:
            batch = load_json_bytes(response.body, url)
            if not isinstance(batch, list):
                raise FetchError(url, response.status, "atteso un array JSON")
        except FetchError as exc:
            error = exc
            break
        stop = False
        for raw in batch:
            slim = catalog.slim_observation(raw)
            start = catalog.parse_time(slim.get("start"))
            if start is not None and start < cutoff:
                stop = True
                continue
            kept.append(slim)
        log(f"  pagina {pages}: +{len(batch)} in pagina, {len(kept)} tenute")
        if stop:
            break
        url = catalog.parse_next_link(response.headers.get("link"))
    body = dump_json(path, kept)
    record = entry_ok(
        "satnogs-observations-good",
        start_url,
        path,
        body,
        len(kept),
        LICENSES["satnogs"],
        "extracted",
    )
    record["pages"] = pages
    record["hours"] = hours
    if error and not kept:
        record["status"] = "error"
        record["error"] = str(error)
    elif error:
        record["status"] = "partial"
        record["error"] = str(error)
    manifest.append(record)
    return kept


def collect_stac(manifest, skip_existing, offline):
    path = CATALOG / "stac-collections.json"
    start_url = "https://catalogue.dataspace.copernicus.eu/stac/collections"
    if skip_existing:
        cached = load_cached(path)
        if isinstance(cached, list):
            manifest.append(
                cached_entry(
                    "copernicus-stac-collections",
                    start_url,
                    path,
                    cached,
                    LICENSES["copernicus"],
                    "extracted",
                )
            )
            log(f"STAC in cache ({len(cached)})")
            return cached
    if offline:
        log("STAC assente")
        manifest.append(entry_absent("copernicus-stac-collections", start_url, LICENSES["copernicus"]))
        return []
    url = start_url
    collections = []
    seen = set()
    pages = 0
    error = None
    log("STAC Copernicus collections")
    while url and url not in seen and pages < 60:
        seen.add(url)
        response, error = polite_fetch(url)
        pages += 1
        if error:
            log(f"  errore: {error}")
            break
        try:
            payload = load_json_bytes(response.body, url)
        except FetchError as exc:
            error = exc
            break
        for collection in payload.get("collections") or []:
            collections.append(catalog.slim_stac(collection))
        log(f"  pagina {pages}: {len(collections)} collezioni")
        url = None
        for link in payload.get("links") or []:
            if link.get("rel") == "next" and link.get("href"):
                url = link["href"]
                break
    body = dump_json(path, collections)
    record = entry_ok(
        "copernicus-stac-collections",
        start_url,
        path,
        body,
        len(collections),
        LICENSES["copernicus"],
        "extracted",
    )
    record["pages"] = pages
    if error and not collections:
        record["status"] = "error"
        record["error"] = str(error)
    elif error:
        record["status"] = "partial"
        record["error"] = str(error)
    manifest.append(record)
    return collections


def collect_pds(manifest, skip_existing, offline):
    path = CATALOG / "pds-bundles.json"
    if skip_existing:
        cached = load_cached(path)
        if isinstance(cached, list):
            manifest.append(
                cached_entry(
                    "nasa-pds-bundles",
                    "https://pds.nasa.gov/services/search/search",
                    path,
                    cached,
                    LICENSES["pds"],
                    "extracted",
                )
            )
            log(f"PDS in cache ({len(cached)})")
            return cached
    if offline:
        log("PDS assente")
        manifest.append(
            entry_absent("nasa-pds-bundles", "https://pds.nasa.gov/services/search/search", LICENSES["pds"])
        )
        return []
    docs = []
    found = None
    start = 0
    rows = 200
    error = None
    start_url = None
    log("PDS bundles")
    while found is None or start < found:
        query = urllib.parse.urlencode(
            {
                "q": "product_class:Product_Bundle",
                "wt": "json",
                "rows": str(rows),
                "start": str(start),
                "fl": "lid,title,bundle_type,agency_name,citation_publication_year,description",
            }
        )
        url = f"https://pds.nasa.gov/services/search/search?{query}"
        if start_url is None:
            start_url = url
        response, error = polite_fetch(url)
        if error:
            log(f"  errore: {error}")
            break
        try:
            payload = load_json_bytes(response.body, url)
        except FetchError as exc:
            error = exc
            break
        header = payload.get("responseHeader") or {}
        if header.get("status") not in (0, None):
            error = FetchError(url, header.get("status"), "PDS Solr status non zero")
            break
        response_body = payload.get("response") or {}
        found = int(response_body.get("numFound") or 0)
        batch = response_body.get("docs") or []
        if not batch:
            break
        docs.extend(catalog.slim_pds(doc) for doc in batch)
        start += len(batch)
        log(f"  {start}/{found}")
        if start > 5000:
            break
    body = dump_json(path, docs)
    record = entry_ok(
        "nasa-pds-bundles",
        start_url or "https://pds.nasa.gov/services/search/search",
        path,
        body,
        len(docs),
        LICENSES["pds"],
        "extracted",
    )
    if error and not docs:
        record["status"] = "error"
        record["error"] = str(error)
    elif error:
        record["status"] = "partial"
        record["error"] = str(error)
    manifest.append(record)
    return docs


def build(manifest, gp, satcat_rows, satnogs_rows, transmitters, observations, stac, pds):
    orbits = catalog.merge_orbits(gp, satcat_rows, satnogs_rows)
    signals = catalog.build_signals(transmitters, satnogs_rows, orbits)
    retrieved_at = iso_now()
    summary = catalog.summarize(
        retrieved_at, orbits, signals, observations, stac, pds, manifest
    )
    dump_json(CATALOG / "orbits.json", orbits)
    dump_json(CATALOG / "signals.json", signals)
    dump_json(CATALOG / "summary.json", summary, pretty=True)
    dump_json(DATA / "manifest.json", manifest, pretty=True)
    readme = catalog.render_snapshot_readme(summary)
    (DATA / "README.md").write_text(readme, encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="Scarica lo snapshot space_data in data/.")
    parser.add_argument(
        "--hours",
        type=float,
        default=24,
        help="Ore di osservazioni SatNOGS vetted-good da tenere (default 24).",
    )
    parser.add_argument(
        "--max-obs-pages",
        type=int,
        default=40,
        help="Tetto di pagine SatNOGS Network (25 osservazioni per pagina).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Non riscaricare un file JSON già presente e valido.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Ricostruisce il catalogo dai file già presenti, senza rete.",
    )
    args = parser.parse_args(argv)
    if args.hours <= 0 or args.max_obs_pages <= 0:
        parser.error("--hours e --max-obs-pages devono essere positivi")
    if args.offline:
        args.skip_existing = True

    DATA.mkdir(parents=True, exist_ok=True)
    CATALOG.mkdir(parents=True, exist_ok=True)
    manifest = []

    gp = collect_gp(manifest, args.skip_existing, args.offline)
    satcat_rows = collect_satcat(manifest, args.skip_existing, args.offline)
    satnogs_rows = collect_json_list(
        manifest,
        "satnogs-satellites",
        "https://db.satnogs.org/api/satellites/?format=json",
        RAW / "satnogs" / "satellites.json",
        LICENSES["satnogs"],
        args.skip_existing,
        args.offline,
    )
    transmitters = collect_json_list(
        manifest,
        "satnogs-transmitters-alive",
        "https://db.satnogs.org/api/transmitters/?format=json&alive=true",
        RAW / "satnogs" / "transmitters-alive.json",
        LICENSES["satnogs"],
        args.skip_existing,
        args.offline,
    )
    collect_json_list(
        manifest,
        "satnogs-modes",
        "https://db.satnogs.org/api/modes/?format=json",
        RAW / "satnogs" / "modes.json",
        LICENSES["satnogs"],
        args.skip_existing,
        args.offline,
    )
    collect_json_list(
        manifest,
        "satnogs-tle",
        "https://db.satnogs.org/api/tle/?format=json",
        RAW / "satnogs" / "tle.json",
        LICENSES["satnogs"],
        args.skip_existing,
        args.offline,
    )
    collect_swpc(manifest, args.skip_existing, args.offline)
    observations = collect_observations(
        manifest, args.hours, args.max_obs_pages, args.skip_existing, args.offline
    )
    stac = collect_stac(manifest, args.skip_existing, args.offline)
    pds = collect_pds(manifest, args.skip_existing, args.offline)
    summary = build(
        manifest,
        gp,
        satcat_rows,
        satnogs_rows,
        transmitters,
        observations,
        stac,
        pds,
    )
    print(
        f"orbite={summary['orbits']} segnali={summary['signals_alive']} "
        f"osservazioni={summary['observations']} stac={summary['stac_collections']} "
        f"pds={summary['pds_bundles']}"
    )
    print(f"catalogo: {rel(CATALOG / 'summary.json')}")
    failed = [item for item in manifest if not ok_status(item["status"])]
    if failed:
        print(f"fonti con errore: {len(failed)} (vedi data/manifest.json)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
