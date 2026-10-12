"""Pure transforms from upstream payloads to the local catalogs.

Network access stays in collect.py. The functions here are deterministic
and safe to test without hitting CelesTrak or SatNOGS.
"""

from __future__ import annotations

import re
from datetime import datetime

# GP JSON uses the CelesTrak / OMM names. The catalog stores short snake names.
ELEMENT_FIELDS = {
    "OBJECT_NAME": "object_name",
    "OBJECT_ID": "object_id",
    "EPOCH": "epoch",
    "MEAN_MOTION": "mean_motion",
    "ECCENTRICITY": "eccentricity",
    "INCLINATION": "inclination_deg",
    "RA_OF_ASC_NODE": "raan_deg",
    "ARG_OF_PERICENTER": "arg_of_perigee_deg",
    "MEAN_ANOMALY": "mean_anomaly_deg",
    "BSTAR": "bstar",
    "MEAN_MOTION_DOT": "mean_motion_dot",
    "MEAN_MOTION_DDOT": "mean_motion_ddot",
    "REV_AT_EPOCH": "rev_at_epoch",
    "CLASSIFICATION_TYPE": "classification",
}

DEMOD_URL_CAP = 8


def as_int(value):
    """Return an int catalog number, or None when the field is absent."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            return int(text)
    return None


def none_if_blank(value):
    if value is None:
        return None
    if isinstance(value, str) and value.strip() in {"", "None", "null", "N/A"}:
        return None
    return value


def clean_text(value, limit):
    if value is None:
        return None
    if isinstance(value, list):
        value = " ".join(str(item) for item in value if item is not None)
    text = " ".join(str(value).split())
    if not text or text in {"None", "null"}:
        return None
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def as_scalar(value):
    if isinstance(value, list):
        if not value:
            return None
        if len(value) == 1:
            return value[0]
        return value
    return value


def parse_time(value):
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def parse_next_link(header):
    """Extract the URL marked rel=next from an RFC 5988 Link header."""
    if not header:
        return None
    for part in header.split(","):
        section = part.strip()
        match = re.search(r'rel="?([^";]+)"?', section)
        if not match or match.group(1) != "next":
            continue
        url_match = re.search(r"<([^>]+)>", section)
        if url_match:
            return url_match.group(1)
    return None


def _blank_orbit(norad):
    orbit = {
        "norad_cat_id": norad,
        "groups": [],
        "owner": None,
        "launch_date": None,
        "launch_site": None,
        "object_type": None,
        "ops_status": None,
        "period_min": None,
        "apogee_km": None,
        "perigee_km": None,
        "rcs": None,
        "orbit_type": None,
        "decay_date": None,
        "satnogs_id": None,
        "satnogs_status": None,
        "countries": None,
        "operator": None,
        "names": None,
    }
    for dest in ELEMENT_FIELDS.values():
        orbit[dest] = None
    return orbit


def _apply_elements(orbit, row):
    for source, dest in ELEMENT_FIELDS.items():
        if source in row and row[source] is not None:
            orbit[dest] = row[source]


def _status_rank(row):
    status = (row.get("status") or "").lower()
    rank = 0
    if "orbit" in status or status == "alive":
        rank += 2
    if row.get("decayed"):
        rank -= 3
    return rank


def index_satnogs(rows):
    """Index SatNOGS satellites by NORAD id and by SatNOGS sat_id.

    When several rows share a NORAD id, keep the one that still looks in orbit.
    """
    by_norad = {}
    by_sat = {}
    for row in rows:
        sat_id = row.get("sat_id")
        if sat_id:
            by_sat[sat_id] = row
        norad = as_int(row.get("norad_cat_id"))
        if norad is None:
            continue
        previous = by_norad.get(norad)
        if previous is None or _status_rank(row) > _status_rank(previous):
            by_norad[norad] = row
    return by_norad, by_sat


def merge_orbits(gp_by_group, satcat_rows, satnogs_rows):
    """Union GP groups and overlay SATCAT plus SatNOGS identity fields.

    A newer GP epoch replaces the elements. Group labels accumulate.
    SatNOGS rows that are not already in the GP/SATCAT set are left out:
    that feed contains many decayed objects with no current elements.
    """
    by_id = {}
    for group, rows in gp_by_group.items():
        for row in rows:
            norad = as_int(row.get("NORAD_CAT_ID"))
            if norad is None:
                continue
            orbit = by_id.get(norad)
            if orbit is None:
                orbit = _blank_orbit(norad)
                by_id[norad] = orbit
            epoch = row.get("EPOCH") or ""
            if orbit["epoch"] is None or epoch > orbit["epoch"]:
                _apply_elements(orbit, row)
            if group not in orbit["groups"]:
                orbit["groups"].append(group)

    for row in satcat_rows:
        norad = as_int(row.get("NORAD_CAT_ID"))
        if norad is None:
            continue
        orbit = by_id.get(norad)
        if orbit is None:
            orbit = _blank_orbit(norad)
            orbit["groups"].append("satcat")
            by_id[norad] = orbit
        if not orbit["object_name"]:
            orbit["object_name"] = none_if_blank(row.get("OBJECT_NAME"))
        if not orbit["object_id"]:
            orbit["object_id"] = none_if_blank(row.get("OBJECT_ID"))
        orbit["owner"] = none_if_blank(row.get("OWNER"))
        orbit["launch_date"] = none_if_blank(row.get("LAUNCH_DATE"))
        orbit["launch_site"] = none_if_blank(row.get("LAUNCH_SITE"))
        orbit["object_type"] = none_if_blank(row.get("OBJECT_TYPE"))
        orbit["ops_status"] = none_if_blank(row.get("OPS_STATUS_CODE"))
        orbit["period_min"] = row.get("PERIOD")
        orbit["apogee_km"] = row.get("APOGEE")
        orbit["perigee_km"] = row.get("PERIGEE")
        orbit["rcs"] = row.get("RCS")
        orbit["orbit_type"] = none_if_blank(row.get("ORBIT_TYPE"))
        orbit["decay_date"] = none_if_blank(row.get("DECAY_DATE"))

    by_norad, _ = index_satnogs(satnogs_rows)
    for norad, row in by_norad.items():
        orbit = by_id.get(norad)
        if orbit is None:
            continue
        if not orbit["object_name"]:
            orbit["object_name"] = none_if_blank(row.get("name"))
        orbit["satnogs_id"] = row.get("sat_id")
        orbit["satnogs_status"] = none_if_blank(row.get("status"))
        orbit["countries"] = none_if_blank(row.get("countries"))
        orbit["operator"] = none_if_blank(row.get("operator"))
        orbit["names"] = none_if_blank(row.get("names"))

    return [by_id[key] for key in sorted(by_id)]


def build_signals(transmitters, satnogs_rows, orbits):
    """One record per alive transmitter, with a display name when we have one."""
    by_norad, by_sat = index_satnogs(satnogs_rows)
    orbit_names = {orbit["norad_cat_id"]: orbit.get("object_name") for orbit in orbits}
    signals = []
    for tx in transmitters:
        if tx.get("alive") is False:
            continue
        norad = as_int(tx.get("norad_cat_id"))
        sat_id = tx.get("sat_id")
        name = None
        if sat_id and sat_id in by_sat:
            name = none_if_blank(by_sat[sat_id].get("name"))
        if name is None and norad in by_norad:
            name = none_if_blank(by_norad[norad].get("name"))
        if name is None and norad in orbit_names:
            name = orbit_names[norad]
        signals.append(
            {
                "uuid": tx.get("uuid"),
                "norad_cat_id": norad,
                "sat_id": sat_id,
                "name": name,
                "description": none_if_blank(tx.get("description")),
                "downlink_hz": tx.get("downlink_low"),
                "uplink_hz": tx.get("uplink_low"),
                "mode": none_if_blank(tx.get("mode")),
                "uplink_mode": none_if_blank(tx.get("uplink_mode")),
                "baud": tx.get("baud"),
                "service": none_if_blank(tx.get("service")),
                "status": none_if_blank(tx.get("status")),
                "unconfirmed": tx.get("unconfirmed"),
                "iaru_coordination": none_if_blank(tx.get("iaru_coordination")),
                "invert": tx.get("invert"),
                "citation": none_if_blank(tx.get("citation")),
            }
        )
    signals.sort(
        key=lambda item: (
            item["downlink_hz"] is None,
            item["downlink_hz"] or 0,
            item["norad_cat_id"] or 0,
            item["uuid"] or "",
        )
    )
    return signals


def slim_observation(raw):
    """Keep pass geometry and demod links. Drop operator nicknames.

    Station coordinates stay: the station owner published them as part of
    the observation, and without them the pass cannot be interpreted.
    Payload bytes are not copied; demod_urls point back at SatNOGS.
    """
    demod = raw.get("demoddata") or []
    urls = []
    if isinstance(demod, list):
        for item in demod:
            if isinstance(item, dict):
                url = item.get("payload_demod")
            elif isinstance(item, str):
                url = item
            else:
                url = None
            if url:
                urls.append(url)
    return {
        "id": raw.get("id"),
        "start": raw.get("start"),
        "end": raw.get("end"),
        "norad_cat_id": as_int(raw.get("norad_cat_id")),
        "sat_id": raw.get("sat_id"),
        "transmitter_uuid": raw.get("transmitter_uuid") or raw.get("transmitter"),
        "mode": raw.get("transmitter_mode"),
        "downlink_hz": raw.get("transmitter_downlink_low"),
        "baud": raw.get("transmitter_baud"),
        "center_frequency": raw.get("center_frequency"),
        "observation_frequency": raw.get("observation_frequency"),
        "ground_station": raw.get("ground_station"),
        "station_name": raw.get("station_name"),
        "station_lat": raw.get("station_lat"),
        "station_lng": raw.get("station_lng"),
        "station_alt": raw.get("station_alt"),
        "max_altitude": raw.get("max_altitude"),
        "rise_azimuth": raw.get("rise_azimuth"),
        "set_azimuth": raw.get("set_azimuth"),
        "status": raw.get("status"),
        "demod_count": len(urls),
        "demod_urls": urls[:DEMOD_URL_CAP],
        "archive_url": raw.get("archive_url"),
        "has_waterfall": bool(raw.get("waterfall")),
    }


def slim_stac(collection):
    license_href = None
    for link in collection.get("links") or []:
        if link.get("rel") == "license" and link.get("href"):
            license_href = link["href"]
            break
    extent = collection.get("extent") or {}
    spatial = (extent.get("spatial") or {}).get("bbox") or []
    temporal = (extent.get("temporal") or {}).get("interval") or []
    return {
        "id": collection.get("id"),
        "title": collection.get("title"),
        "description": clean_text(collection.get("description"), 500),
        "license": collection.get("license"),
        "license_href": license_href,
        "keywords": collection.get("keywords") or [],
        "bbox": spatial[0] if spatial else None,
        "temporal": temporal[0] if temporal else None,
    }


def slim_pds(doc):
    lid = doc.get("lid")
    if lid is None:
        lid = as_scalar(doc.get("identifier"))
        if isinstance(lid, list):
            lid = lid[0]
    return {
        "lid": lid,
        "title": clean_text(doc.get("title"), 200),
        "bundle_type": clean_text(as_scalar(doc.get("bundle_type")), 80),
        "agency": clean_text(as_scalar(doc.get("agency_name")), 120),
        "year": as_scalar(doc.get("citation_publication_year")),
        "description": clean_text(doc.get("description"), 400),
    }


def count_records(payload):
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list):
                return len(value)
        return 1
    return None


def summarize(retrieved_at, orbits, signals, observations, stac, pds, manifest):
    groups = {}
    for orbit in orbits:
        for group in orbit["groups"]:
            groups[group] = groups.get(group, 0) + 1
    modes = {}
    for signal in signals:
        mode = signal.get("mode") or "unknown"
        modes[mode] = modes.get(mode, 0) + 1
    starts = [item["start"] for item in observations if item.get("start")]
    return {
        "retrieved_at": retrieved_at,
        "orbits": len(orbits),
        "orbits_by_group": dict(sorted(groups.items(), key=lambda item: (-item[1], item[0]))),
        "signals_alive": len(signals),
        "signals_by_mode": dict(sorted(modes.items(), key=lambda item: (-item[1], item[0]))),
        "observations": len(observations),
        "observation_earliest": min(starts) if starts else None,
        "observation_latest": max(starts) if starts else None,
        "stac_collections": len(stac),
        "pds_bundles": len(pds),
        "sources": [
            {
                "id": item["id"],
                "status": item["status"],
                "records": item.get("records"),
                "bytes": item.get("bytes"),
                "path": item.get("path"),
                "license": item.get("license"),
            }
            for item in manifest
        ],
    }


def _family(source_id):
    if source_id.startswith("celestrak-gp-"):
        return "GP CelesTrak"
    if source_id.startswith("celestrak-satcat-"):
        return "SATCAT"
    if source_id.startswith("satnogs-"):
        return "SatNOGS"
    if source_id.startswith("swpc-"):
        return "NOAA SWPC"
    if source_id.startswith("copernicus-"):
        return "Copernicus"
    if source_id.startswith("nasa-pds"):
        return "NASA PDS"
    return "Altro"


def gaps(sources):
    """Sources that are not a usable file in this snapshot."""
    return [
        source
        for source in sources
        if source["status"] in {"absent", "not-modified", "partial"}
        or str(source["status"]).startswith("error")
    ]


def render_snapshot_readme(summary):
    """Human index of the snapshot. Regenerated on every collect run."""
    lines = [
        "# Snapshot",
        "",
        f"Generato il {summary['retrieved_at']}.",
        "Si sovrascrive a ogni raccolta. Fonti e licenze: `docs/fonti.md`.",
        "Inventario di ogni file, con URL e SHA-256: `data/manifest.json`.",
        "",
        "| Serie | Valore |",
        "| --- | --- |",
        f"| Orbite | {summary['orbits']} |",
        f"| Trasmettitori vivi | {summary['signals_alive']} |",
        f"| Osservazioni SatNOGS | {summary['observations']} |",
    ]
    if summary.get("observation_earliest"):
        lines.append(
            "| Finestra osservazioni | "
            f"{summary['observation_earliest']} → {summary['observation_latest']} |"
        )
    lines.append(f"| Collezioni STAC Copernicus | {summary['stac_collections']} |")
    lines.append(f"| Bundle PDS | {summary['pds_bundles']} |")
    lines.extend(["", "## Gruppi", ""])
    lines.append("| Gruppo | Oggetti |")
    lines.append("| --- | ---: |")
    for group, count in summary["orbits_by_group"].items():
        lines.append(f"| {group} | {count} |")
    lines.extend(["", "## Modi radio", ""])
    lines.append("| Modo | Trasmettitori |")
    lines.append("| --- | ---: |")
    for mode, count in list(summary["signals_by_mode"].items())[:12]:
        lines.append(f"| {mode} | {count} |")
    missing = gaps(summary["sources"])
    if missing:
        lines.extend(["", "## Lacune", ""])
        for source in missing:
            lines.append(f"- `{source['id']}` — {source['status']}")
    families = {}
    for source in summary["sources"]:
        family = _family(source["id"])
        families[family] = families.get(family, 0) + 1
    lines.extend(["", "## Famiglie di file", ""])
    lines.append("| Famiglia | File |")
    lines.append("| --- | ---: |")
    for family, count in families.items():
        lines.append(f"| {family} | {count} |")
    lines.append("")
    return "\n".join(lines)
