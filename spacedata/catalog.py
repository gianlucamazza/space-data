#!/usr/bin/env python3
"""Query the local snapshot. Run collect.py first."""

from __future__ import annotations

import argparse
import json
import sys

from spacedata.paths import CATALOG


def load(name):
    path = CATALOG / name
    if not path.exists():
        sys.exit(f"Manca {path}. Esegui prima: python3 collect.py")
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_hz(hz):
    if hz is None:
        return "—"
    value = float(hz)
    if value >= 1_000_000:
        return f"{value / 1_000_000:.3f} MHz"
    if value >= 1_000:
        return f"{value / 1_000:.3f} kHz"
    return f"{value:.0f} Hz"


def _line(label, value):
    print(f"  {label:18} {value}")


def show_summary():
    summary = load("summary.json")
    print(f"space_data  ·  {summary['retrieved_at']}")
    print()
    _line("Orbite", summary["orbits"])
    _line("Trasmettitori", f"{summary['signals_alive']} vivi")
    window = ""
    if summary.get("observation_earliest"):
        window = f"  {summary['observation_earliest']} → {summary['observation_latest']}"
    _line("Osservazioni", f"{summary['observations']}{window}")
    _line("Copernicus", f"{summary['stac_collections']} collezioni")
    _line("NASA PDS", f"{summary['pds_bundles']} bundle")
    print()
    print("Gruppi")
    groups = list(summary["orbits_by_group"].items())
    for group, count in groups[:12]:
        print(f"  {group:18} {count}")
    if len(groups) > 12:
        print(f"  … altri {len(groups) - 12} gruppi")
    print()
    print("Modi radio")
    for mode, count in list(summary["signals_by_mode"].items())[:8]:
        print(f"  {mode:18} {count}")
    missing = [
        source
        for source in summary["sources"]
        if source["status"] in {"absent", "not-modified", "partial"}
        or str(source["status"]).startswith("error")
    ]
    if missing:
        print()
        print("Lacune")
        for source in missing:
            print(f"  {source['id']:32} {source['status']}")
    return 0


def show_norad(norad, limit):
    orbits = load("orbits.json")
    signals = load("signals.json")
    observations = load("observations.json")
    orbit = next((item for item in orbits if item["norad_cat_id"] == norad), None)
    own_signals = [item for item in signals if item["norad_cat_id"] == norad]
    own_obs = [item for item in observations if item["norad_cat_id"] == norad]
    if orbit is None and not own_signals:
        print(f"Nessun oggetto con NORAD {norad} nello snapshot.")
        return 1
    if orbit:
        print(orbit.get("object_name") or "(senza nome)")
        print(f"NORAD {orbit['norad_cat_id']}  ·  COSPAR {orbit.get('object_id') or '—'}")
        print()
        print("Orbita")
        _line("gruppi", ", ".join(orbit["groups"]) or "—")
        _line("epoca GP", orbit.get("epoch") or "—")
        _line("inclinazione", f"{orbit.get('inclination_deg')}°")
        _line("moto medio", f"{orbit.get('mean_motion')} rev/giorno")
        _line("perigeo", f"{orbit.get('perigee_km')} km")
        _line("apogeo", f"{orbit.get('apogee_km')} km")
        _line("periodo", f"{orbit.get('period_min')} min")
        print()
        print("Identità")
        _line("proprietario", orbit.get("owner") or "—")
        _line("lancio", orbit.get("launch_date") or "—")
        _line("tipo", orbit.get("object_type") or "—")
        _line("stato ops", orbit.get("ops_status") or "—")
        _line("SatNOGS", orbit.get("satnogs_status") or "—")
        _line("paesi", orbit.get("countries") or "—")
        _line("operatore", orbit.get("operator") or "—")
    else:
        print(f"NORAD {norad}")
        print("Presente solo fra i trasmettitori SatNOGS.")
    print()
    print(f"Trasmettitori vivi ({len(own_signals)})")
    for signal in own_signals[:limit]:
        baud = signal.get("baud")
        baud_text = "—" if baud is None else str(baud)
        print(
            f"  {fmt_hz(signal['downlink_hz']):14}  "
            f"{(signal.get('mode') or '—'):8}  "
            f"{baud_text:<8}  "
            f"{signal.get('description') or ''}"
        )
    if len(own_signals) > limit:
        print(f"  … altri {len(own_signals) - limit} (alza --limit)")
    print()
    if own_obs:
        latest = max(item["start"] for item in own_obs if item.get("start"))
        print(f"Osservazioni nello snapshot: {len(own_obs)}, ultima {latest}")
    else:
        print("Osservazioni nello snapshot: 0")
    return 0


def list_orbits(group, name, limit):
    orbits = load("orbits.json")
    matches = orbits
    if group:
        matches = [item for item in matches if group in item["groups"]]
    if name:
        needle = name.casefold()
        matches = [
            item
            for item in matches
            if needle in (item.get("object_name") or "").casefold()
            or needle in (item.get("names") or "").casefold()
        ]
    print(f"{len(matches)} orbite")
    for orbit in matches[:limit]:
        print(
            f"{orbit['norad_cat_id']:7}  "
            f"{(orbit.get('object_name') or '—')[:42]:42}  "
            f"{','.join(orbit['groups'][:4])}"
        )
    if len(matches) > limit:
        print(f"… altri {len(matches) - limit} (alza --limit)")
    return 0 if matches else 1


def list_signals(mode, name, mhz_min, mhz_max, group, limit):
    signals = load("signals.json")
    group_ids = None
    if group:
        group_ids = {
            orbit["norad_cat_id"]
            for orbit in load("orbits.json")
            if group in orbit["groups"]
        }
    matches = []
    for signal in signals:
        if mode and (signal.get("mode") or "").casefold() != mode.casefold():
            continue
        if name and name.casefold() not in (signal.get("name") or "").casefold():
            continue
        if group_ids is not None and signal.get("norad_cat_id") not in group_ids:
            continue
        downlink = signal.get("downlink_hz")
        if mhz_min is not None or mhz_max is not None:
            if downlink is None:
                continue
            mhz = float(downlink) / 1_000_000
            if mhz_min is not None and mhz < mhz_min:
                continue
            if mhz_max is not None and mhz > mhz_max:
                continue
        matches.append(signal)
    print(f"{len(matches)} trasmettitori")
    for signal in matches[:limit]:
        norad = signal["norad_cat_id"] if signal["norad_cat_id"] is not None else "—"
        print(
            f"{str(norad):7}  "
            f"{(signal.get('name') or '—')[:32]:32}  "
            f"{fmt_hz(signal.get('downlink_hz')):14}  "
            f"{(signal.get('mode') or '—'):8}  "
            f"{signal.get('description') or ''}"
        )
    if len(matches) > limit:
        print(f"… altri {len(matches) - limit} (alza --limit)")
    return 0 if matches else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Interroga il catalogo locale space_data.")
    parser.add_argument("--norad", type=int, help="Scheda di un catalog number.")
    parser.add_argument("--group", help="Gruppo GP CelesTrak, per esempio amateur o gnss.")
    parser.add_argument("--mode", help="Modo SatNOGS, per esempio APT o BPSK.")
    parser.add_argument("--name", help="Sottostringa del nome, senza distinzione di maiuscole.")
    parser.add_argument("--mhz-min", type=float, help="Downlink minimo, in MHz.")
    parser.add_argument("--mhz-max", type=float, help="Downlink massimo, in MHz.")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)

    if args.norad is not None:
        return show_norad(args.norad, args.limit)
    signal_query = (
        args.mode or args.mhz_min is not None or args.mhz_max is not None
    )
    if signal_query:
        return list_signals(args.mode, args.name, args.mhz_min, args.mhz_max, args.group, args.limit)
    if args.group or args.name:
        return list_orbits(args.group, args.name, args.limit)
    return show_summary()


if __name__ == "__main__":
    sys.exit(main())
