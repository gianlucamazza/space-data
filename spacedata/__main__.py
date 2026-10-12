"""Command line: python -m spacedata [show|collect]"""

from __future__ import annotations

import sys


USAGE = """\
space_data — catalogo locale di dati spaziali pubblici

  python -m spacedata                         panorama dello snapshot
  python -m spacedata show --norad 25544      scheda di un oggetto
  python -m spacedata show --group amateur
  python -m spacedata show --mhz-min 137 --mhz-max 138
  python -m spacedata collect                 aggiorna lo snapshot
  python -m spacedata collect --offline       rilegge i file già scaricati

I comandi show accettano le stesse opzioni di prima. Dettaglio operativo: docs/uso.md.
"""


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        if not args:
            from spacedata.catalog import main as show_main

            return show_main([])
        print(USAGE, end="")
        return 0
    command, rest = args[0], args[1:]
    if command == "show":
        from spacedata.catalog import main as show_main

        return show_main(rest)
    if command == "collect":
        from spacedata.collect import main as collect_main

        return collect_main(rest)
    if command.startswith("-"):
        from spacedata.catalog import main as show_main

        return show_main(args)
    print(USAGE, end="", file=sys.stderr)
    print(f"Comando sconosciuto: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
