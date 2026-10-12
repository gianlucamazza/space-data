#!/usr/bin/env python3
"""Interroga lo snapshot. Equivale a: python -m spacedata show"""

import sys

from spacedata.catalog import main

if __name__ == "__main__":
    sys.exit(main())
