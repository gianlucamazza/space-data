#!/usr/bin/env python3
"""Aggiorna lo snapshot. Equivale a: python -m spacedata collect"""

import sys

from spacedata.collect import main

if __name__ == "__main__":
    sys.exit(main())
